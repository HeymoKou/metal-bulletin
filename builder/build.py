"""Builder — daily JSONs → Parquet series + manifest.

Output layout:
  data/series/{metal}/{year}.parquet   per-metal yearly chunks
  data/series/{metal}/latest.parquet   last 90 trading days
  data/raw/{year}.parquet              all-metal wide rows (archival, optional)
  data/exchange.parquet                USD/KRW timeseries
  data/manifest.json                   metadata (single source of truth)
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

METALS = {
    "copper":   {"symbol": "Cu", "unit": "$/ton", "name_ko": "전기동",   "name_en": "Copper"},
    "aluminum": {"symbol": "Al", "unit": "$/ton", "name_ko": "알루미늄", "name_en": "Aluminium"},
    "zinc":     {"symbol": "Zn", "unit": "$/ton", "name_ko": "아연",     "name_en": "Zinc"},
    "nickel":   {"symbol": "Ni", "unit": "$/ton", "name_ko": "니켈",     "name_en": "Nickel"},
    "lead":     {"symbol": "Pb", "unit": "$/ton", "name_ko": "납",       "name_en": "Lead"},
    "tin":      {"symbol": "Sn", "unit": "$/ton", "name_ko": "주석",     "name_en": "Tin"},
}

LATEST_WINDOW = 90
SCHEMA_VERSION = 1


# ---------- Rate resolution ----------

def resolve_rate(daily: dict, rates_map: dict[str, float]) -> tuple[float | None, str | None]:
    """Resolve USD/KRW. Priority: BOK ECOS → PDF market.krw_usd → None."""
    bok_rate = rates_map.get(daily["date"])
    if bok_rate:
        return bok_rate, "bok"
    pdf_rate = (daily.get("market") or {}).get("krw_usd")
    if pdf_rate:
        return pdf_rate, "pdf"
    return None, None


# ---------- Flatten daily metal data → flat row ----------

def _gv(d, *path):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def flatten_metal_row(daily: dict, metal: str, rate: float | None, rate_source: str | None) -> dict | None:
    """One flat row for (date, metal). Returns None if metal missing in daily."""
    m = (daily.get("metals") or {}).get(metal)
    if not m:
        return None

    lme  = m.get("lme") or {}
    cash = lme.get("cash") or {}
    tm   = lme.get("3m") or {}
    sett = m.get("settlement") or {}
    inv  = m.get("inventory") or {}
    shfe = m.get("shfe") or {}

    cash_close = cash.get("close")
    tm_close   = tm.get("close")

    krw_cash = round(cash_close * rate) if (cash_close is not None and rate) else None
    krw_3m   = round(tm_close   * rate) if (tm_close   is not None and rate) else None

    return {
        "date": daily["date"],

        # LME cash
        "lme_cash_open":   cash.get("open"),
        "lme_cash_high":   cash.get("high"),
        "lme_cash_low":    cash.get("low"),
        "lme_cash_close":  cash.get("close"),
        "lme_cash_change": cash.get("change"),
        "lme_cash_prev":   cash.get("prev_close"),

        # LME 3M
        "lme_3m_open":     tm.get("open"),
        "lme_3m_high":     tm.get("high"),
        "lme_3m_low":      tm.get("low"),
        "lme_3m_close":    tm.get("close"),
        "lme_3m_change":   tm.get("change"),
        "lme_3m_prev":     tm.get("prev_close"),

        # bid/ask/OI
        "lme_bid":         lme.get("bid"),
        "lme_ask":         lme.get("ask"),
        "lme_oi":          lme.get("open_interest"),

        # Settlement
        "sett_cash":              sett.get("cash"),
        "sett_3m":                sett.get("3m"),
        "sett_mavg_cash":         _gv(sett, "monthly_avg", "cash"),
        "sett_mavg_3m":           _gv(sett, "monthly_avg", "3m"),
        "sett_prev_mavg_cash":    _gv(sett, "prev_monthly_avg", "cash"),
        "sett_prev_mavg_3m":      _gv(sett, "prev_monthly_avg", "3m"),
        "sett_fwd_m1":            _gv(sett, "forwards", "m1"),
        "sett_fwd_m2":            _gv(sett, "forwards", "m2"),
        "sett_fwd_m3":            _gv(sett, "forwards", "m3"),

        # Inventory
        "inv_prev":              inv.get("prev"),
        "inv_in":                inv.get("in"),
        "inv_out":               inv.get("out"),
        "inv_current":           inv.get("current"),
        "inv_change":            inv.get("change"),
        "inv_on_warrant":        inv.get("on_warrant"),
        "inv_cancelled_warrant": inv.get("cancelled_warrant"),
        "inv_cw_change":         inv.get("cw_change"),

        # SHFE
        "shfe_lme_3m_cny":          shfe.get("lme_3m_cny"),
        "shfe_lme_near_cny":        shfe.get("lme_near_cny"),
        "shfe_lme_3m_incl_tax":     shfe.get("lme_3m_incl_tax"),
        "shfe_lme_near_incl_tax":   shfe.get("lme_near_incl_tax"),
        "shfe_3m":                  shfe.get("shfe_3m"),
        "shfe_settle":              shfe.get("shfe_settle"),
        "shfe_premium_usd":         shfe.get("premium_usd"),

        # KRW
        "krw_cash":   krw_cash,
        "krw_3m":     krw_3m,
        "krw_rate":   rate,
        "krw_source": rate_source,
    }


# ---------- Schema + table builders ----------

# Field types for a metal row (date string, others float/int/string)
_FLOAT = pa.float64()
_INT   = pa.int64()
_STR   = pa.string()

METAL_SCHEMA = pa.schema([
    pa.field("date", _STR),
    *(pa.field(c, _FLOAT) for c in [
        "lme_cash_open", "lme_cash_high", "lme_cash_low", "lme_cash_close", "lme_cash_change", "lme_cash_prev",
        "lme_3m_open", "lme_3m_high", "lme_3m_low", "lme_3m_close", "lme_3m_change", "lme_3m_prev",
        "lme_bid", "lme_ask",
        "sett_cash", "sett_3m",
        "sett_mavg_cash", "sett_mavg_3m",
        "sett_prev_mavg_cash", "sett_prev_mavg_3m",
        "sett_fwd_m1", "sett_fwd_m2", "sett_fwd_m3",
        "shfe_premium_usd",
        "krw_rate",
    ]),
    *(pa.field(c, _INT) for c in [
        "lme_oi",
        "inv_prev", "inv_in", "inv_out", "inv_current", "inv_change",
        "inv_on_warrant", "inv_cancelled_warrant", "inv_cw_change",
        "shfe_lme_3m_cny", "shfe_lme_near_cny", "shfe_lme_3m_incl_tax", "shfe_lme_near_incl_tax",
        "shfe_3m", "shfe_settle",
        "krw_cash", "krw_3m",
    ]),
    pa.field("krw_source", _STR),
])


def rows_to_table(rows: list[dict], schema: pa.Schema) -> pa.Table:
    """Convert list of dicts → pyarrow Table with explicit schema (handles None as null)."""
    cols = {f.name: [] for f in schema}
    for r in rows:
        for f in schema:
            cols[f.name].append(r.get(f.name))
    arrays = []
    for f in schema:
        if pa.types.is_integer(f.type):
            # Cast None preserved; floats coerced to int when not None.
            arr = pa.array(
                [int(v) if v is not None else None for v in cols[f.name]],
                type=f.type,
            )
        else:
            arr = pa.array(cols[f.name], type=f.type)
        arrays.append(arr)
    return pa.Table.from_arrays(arrays, schema=schema)


def write_parquet(table: pa.Table, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        table,
        path,
        compression="zstd",
        compression_level=9,
        use_dictionary=True,
        write_statistics=True,
    )


# ---------- Series writer ----------

def split_by_year(rows: list[dict]) -> dict[int, list[dict]]:
    by_year: dict[int, list[dict]] = {}
    for r in rows:
        year = int(r["date"][:4])
        by_year.setdefault(year, []).append(r)
    return by_year


def write_metal_series(metal: str, rows: list[dict], series_root: Path) -> list[int]:
    metal_dir = series_root / metal
    metal_dir.mkdir(parents=True, exist_ok=True)

    # Sort newest → oldest
    rows_sorted = sorted(rows, key=lambda r: r["date"], reverse=True)

    # latest.parquet
    latest_rows = rows_sorted[:LATEST_WINDOW]
    write_parquet(rows_to_table(latest_rows, METAL_SCHEMA), metal_dir / "latest.parquet")

    # Per-year
    by_year = split_by_year(rows_sorted)
    years = sorted(by_year.keys(), reverse=True)
    for y in years:
        yrows = sorted(by_year[y], key=lambda r: r["date"], reverse=True)
        write_parquet(rows_to_table(yrows, METAL_SCHEMA), metal_dir / f"{y}.parquet")
    return years


# ---------- Exchange writer ----------

def write_exchange(rates_map: dict[str, float], path: Path,
                   eur_map: dict[str, float] | None = None,
                   cny_map: dict[str, float] | None = None):
    """exchange.parquet: date, rate(=USD, 호환), usd, eur, cny."""
    eur_map = eur_map or {}
    cny_map = cny_map or {}
    all_dates = sorted(set(rates_map) | set(eur_map) | set(cny_map))
    table = pa.table({
        "date": all_dates,
        "rate": [float(rates_map[d]) if d in rates_map else None for d in all_dates],
        "usd":  [float(rates_map[d]) if d in rates_map else None for d in all_dates],
        "eur":  [float(eur_map[d])   if d in eur_map   else None for d in all_dates],
        "cny":  [float(cny_map[d])   if d in cny_map   else None for d in all_dates],
    })
    write_parquet(table, path)


# ---------- Raw archive (bundle daily JSONs by year) ----------

def write_raw_archives(dailies: list[dict], raw_root: Path) -> list[int]:
    """Bundle daily entries into raw/{year}.parquet (JSON string column).

    Schema: date (string) + json (string, full daily JSON).
    Compressed with zstd — typically 6-10× smaller than raw JSON files.
    """
    by_year: dict[int, list[dict]] = {}
    for d in dailies:
        y = int(d["date"][:4])
        by_year.setdefault(y, []).append(d)

    raw_root.mkdir(parents=True, exist_ok=True)
    years = sorted(by_year.keys())
    for y in years:
        rows = sorted(by_year[y], key=lambda d: d["date"])
        table = pa.table({
            "date": [r["date"] for r in rows],
            "json": [json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows],
        })
        write_parquet(table, raw_root / f"{y}.parquet")
    return years


# ---------- Manifest ----------

def _augment_manifest_with_news(manifest: dict, data_dir: Path) -> dict:
    """Add news/events sections if files exist. Silent skip otherwise."""
    news_dir = data_dir / "news"
    if news_dir.exists():
        years = sorted(int(p.stem) for p in news_dir.glob("*.parquet") if p.stem.isdigit())
        if years:
            try:
                latest_file = news_dir / f"{years[-1]}.parquet"
                table = pq.read_table(latest_file, columns=["fetched_at"])
                last_updated = table.column("fetched_at").to_pylist()[-1] if table.num_rows else None
                total = sum(pq.read_metadata(news_dir / f"{y}.parquet").num_rows for y in years)
                manifest["news"] = {
                    "available_years": years,
                    "last_updated": last_updated.isoformat() if last_updated else None,
                    "total_records": total,
                }
            except Exception as e:
                print(f"manifest news augment failed: {e}")

    events_dir = data_dir / "events"
    if events_dir.exists():
        years = sorted(int(p.stem) for p in events_dir.glob("*.parquet") if p.stem.isdigit())
        if years:
            manifest["events"] = {"available_years": years}

    return manifest


# Minor metals — non-LME, separate schema (USD/MT normalized, region columns).
# Kept apart from `metals` so FE can branch on schema cleanly.
MINOR_METALS = {
    "antimony": {
        "symbol": "Sb",
        "unit": "$/ton",
        "name_ko": "안티몬",
        "name_en": "Antimony",
        "grade": "99.65% min ingot",
        "schema": "minor_regional",  # FE marker: regional columns, no LME OHLC
        "regions": ["exw_china", "fob_china", "port_india", "rotterdam", "baltimore"],
        "source": "scrapmonster",
        "update_freq": "monthly",
    },
}


def _augment_manifest_with_minor(manifest: dict, data_dir: Path) -> dict:
    """Add minor_metals section based on data/series/{key}/ directories."""
    series_dir = data_dir / "series"
    if not series_dir.exists():
        return manifest
    minor: dict = {}
    for key, meta in MINOR_METALS.items():
        mdir = series_dir / key
        if not mdir.exists():
            continue
        years = sorted(
            (int(p.stem) for p in mdir.glob("*.parquet") if p.stem.isdigit()),
            reverse=True,
        )
        if not years:
            continue
        latest_date = None
        try:
            latest_file = mdir / "latest.parquet"
            if latest_file.exists():
                t = pq.read_table(latest_file, columns=["date"])
                dates = t.column("date").to_pylist()
                latest_date = max(dates) if dates else None
        except Exception as e:
            print(f"manifest minor augment failed ({key}): {e}")
        minor[key] = {**meta, "years": years, "latest_date": latest_date}
    if minor:
        manifest["minor_metals"] = minor
    return manifest


def _augment_manifest_with_monthly_6m(manifest: dict, dailies: list[dict]) -> dict:
    """Add metals.{metal}.monthly_6m: last 6 complete months of settlement Cash/3M average.

    Excludes current calendar month (partial). Output sorted desc (most recent first).
    """
    from collections import defaultdict

    if not dailies:
        return manifest

    latest_ym = max(d["date"][:7] for d in dailies)

    # by_metal[metal][YYYY-MM] = {"cash": [...], "m3": [...]}
    by_metal: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: {"cash": [], "m3": []})
    )
    for d in dailies:
        ym = d["date"][:7]
        if ym >= latest_ym:  # skip current/incomplete month
            continue
        for metal, mdata in (d.get("metals") or {}).items():
            sett = (mdata or {}).get("settlement") or {}
            cash = sett.get("cash")
            m3 = sett.get("3m")
            if cash is None and m3 is None:
                continue
            bucket = by_metal[metal][ym]
            if cash is not None:
                bucket["cash"].append(cash)
            if m3 is not None:
                bucket["m3"].append(m3)

    for metal in manifest.get("metals", {}):
        per_month = by_metal.get(metal, {})
        months = sorted(per_month.keys(), reverse=True)[:6]
        rows = []
        for ym in months:
            data = per_month[ym]
            cash_avg = sum(data["cash"]) / len(data["cash"]) if data["cash"] else None
            m3_avg = sum(data["m3"]) / len(data["m3"]) if data["m3"] else None
            rows.append({
                "month": ym,
                "cash": round(cash_avg, 2) if cash_avg is not None else None,
                "3m": round(m3_avg, 2) if m3_avg is not None else None,
                "days": max(len(data["cash"]), len(data["m3"])),
            })
        manifest["metals"][metal]["monthly_6m"] = rows
    return manifest


def build_manifest(dailies: list[dict], years_per_metal: dict[str, list[int]]) -> dict:
    dates = sorted(d["date"] for d in dailies)
    all_years = sorted({y for ys in years_per_metal.values() for y in ys})
    return {
        "schema": SCHEMA_VERSION,
        "format": "parquet",
        "compression": "zstd",
        "last_updated": dates[-1] if dates else None,
        # Order preserved → frontend uses Object.keys(metals) as canonical metal order.
        "metals": {
            m: {
                **METALS[m],
                "years": years_per_metal.get(m, []),
            }
            for m in METALS
        },
        "years": all_years,
        "total_days": len(dates),
        "date_range": {
            "from": dates[0] if dates else None,
            "to":   dates[-1] if dates else None,
        },
        "latest_window": LATEST_WINDOW,
    }


# ---------- Cleanup legacy ----------

def cleanup_legacy(data_dir: Path):
    """Remove pre-Parquet data layout."""
    legacy_paths = [
        data_dir / "metals",       # old per-metal JSON dirs
        data_dir / "exchange",     # old usd_krw.json directory
        data_dir / "index.json",   # renamed to manifest.json
    ]
    for p in legacy_paths:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()


# ---------- Entry point ----------

def load_dailies(data_dir: Path) -> list[dict]:
    """Load daily entries. Prefers data/daily/*.json; falls back to data/raw/*.parquet archives."""
    daily_dir = data_dir / "daily"
    raw_dir = data_dir / "raw"
    dailies: list[dict] = []

    if daily_dir.exists():
        for f in sorted(daily_dir.glob("*.json")):
            try:
                dailies.append(json.loads(f.read_text()))
            except Exception as e:
                print(f"skip {f.name}: {e}")

    if not dailies and raw_dir.exists():
        # Restore from raw archives
        for f in sorted(raw_dir.glob("*.parquet")):
            table = pq.read_table(f)
            for row in table.to_pylist():
                try:
                    dailies.append(json.loads(row["json"]))
                except Exception:
                    pass
        if dailies:
            print(f"restored {len(dailies)} daily entries from raw/")

    return dailies


def run(data_dir: Path):
    series_dir = data_dir / "series"

    dailies = load_dailies(data_dir)

    if not dailies:
        print("No daily data found")
        return

    # Load BOK rates (optional). 신 스키마: currencies.{USD,EUR,CNY}.rates / 구: rates[]
    rates_map: dict[str, float] = {}
    eur_map: dict[str, float] = {}
    cny_map: dict[str, float] = {}
    bok_path = data_dir / "exchange.bok.json"
    legacy_bok_path = data_dir / "exchange" / "usd_krw.json"
    if bok_path.exists():
        doc = json.loads(bok_path.read_text())
        currencies = doc.get("currencies", {})
        if currencies:
            rates_map.update({r["date"]: r["rate"] for r in currencies.get("USD", {}).get("rates", [])})
            eur_map.update({r["date"]: r["rate"] for r in currencies.get("EUR", {}).get("rates", [])})
            cny_map.update({r["date"]: r["rate"] for r in currencies.get("CNY", {}).get("rates", [])})
        else:
            rates_map.update({r["date"]: r["rate"] for r in doc.get("rates", [])})
    elif legacy_bok_path.exists():
        rates_map.update({r["date"]: r["rate"] for r in json.loads(legacy_bok_path.read_text()).get("rates", [])})

    cleanup_legacy(data_dir)
    series_dir.mkdir(parents=True, exist_ok=True)

    # Build per-metal series + collect resolved rates for exchange parquet
    years_per_metal: dict[str, list[int]] = {}
    resolved_rates: dict[str, float] = dict(rates_map)  # start with BOK
    for metal in METALS:
        rows = []
        for daily in dailies:
            rate, source = resolve_rate(daily, rates_map)
            if rate and daily["date"] not in resolved_rates:
                resolved_rates[daily["date"]] = rate
            r = flatten_metal_row(daily, metal, rate, source)
            if r:
                rows.append(r)
        years = write_metal_series(metal, rows, series_dir)
        years_per_metal[metal] = years
        print(f"series: {metal} ({len(rows)} rows, years {years[-1] if years else '-'}~{years[0] if years else '-'})")

    # Exchange parquet (USD + EUR + CNY)
    write_exchange(resolved_rates, data_dir / "exchange.parquet", eur_map, cny_map)
    print(f"exchange: USD={len(resolved_rates)}, EUR={len(eur_map)}, CNY={len(cny_map)}")

    # Raw archive
    raw_years = write_raw_archives(dailies, data_dir / "raw")
    print(f"raw: {len(dailies)} entries archived in {len(raw_years)} year files")

    # Manifest
    manifest = build_manifest(dailies, years_per_metal)
    manifest = _augment_manifest_with_monthly_6m(manifest, dailies)
    manifest = _augment_manifest_with_news(manifest, data_dir)
    manifest = _augment_manifest_with_minor(manifest, data_dir)
    (data_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"manifest: {manifest['total_days']} days, years {manifest['years']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    args = ap.parse_args()
    run(args.data_dir)
