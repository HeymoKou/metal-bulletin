import argparse
import json
import shutil
from pathlib import Path

METALS = {
    "copper": {"symbol": "Cu", "unit": "$/ton"},
    "aluminum": {"symbol": "Al", "unit": "$/ton"},
    "zinc": {"symbol": "Zn", "unit": "$/ton"},
    "lead": {"symbol": "Pb", "unit": "$/ton"},
    "nickel": {"symbol": "Ni", "unit": "$/ton"},
    "tin": {"symbol": "Sn", "unit": "$/ton"},
}

LATEST_WINDOW = 90


def resolve_rate(daily: dict, rates_map: dict[str, float]) -> tuple[float | None, str | None]:
    """Resolve USD/KRW. Priority: BOK ECOS → PDF market.krw_usd → None."""
    bok_rate = rates_map.get(daily["date"])
    if bok_rate:
        return bok_rate, "bok"
    pdf_rate = (daily.get("market") or {}).get("krw_usd")
    if pdf_rate:
        return pdf_rate, "pdf"
    return None, None


def build_entry(daily: dict, metal: str, rates_map: dict[str, float]) -> dict | None:
    m = daily["metals"].get(metal)
    if not m:
        return None
    rate, rate_source = resolve_rate(daily, rates_map)
    lme = m.get("lme", {})
    cash_close = lme.get("cash", {}).get("close") if "cash" in lme else None
    tm_close = lme.get("3m", {}).get("close") if "3m" in lme else None

    krw = {}
    if rate:
        if cash_close is not None:
            krw["cash"] = round(cash_close * rate)
        if tm_close is not None:
            krw["3m"] = round(tm_close * rate)
        krw["rate"] = rate
        krw["source"] = rate_source

    return {
        "date": daily["date"],
        "lme": lme,
        "settlement": m.get("settlement", {}),
        "inventory": m.get("inventory", {}),
        "shfe": m.get("shfe", {}),
        "krw": krw,
    }


def build_metal_timeseries(metal: str, dailies: list[dict], rates_map: dict[str, float]) -> dict:
    """Backwards-compatible: returns full timeseries (used by tests)."""
    info = METALS[metal]
    data = []
    for daily in dailies:
        entry = build_entry(daily, metal, rates_map)
        if entry:
            data.append(entry)
    data.sort(key=lambda d: d["date"], reverse=True)
    return {
        "metal": metal,
        "symbol": info["symbol"],
        "unit": info["unit"],
        "last_updated": data[0]["date"] if data else None,
        "data": data,
    }


def split_by_year(entries: list[dict]) -> dict[int, list[dict]]:
    by_year: dict[int, list[dict]] = {}
    for e in entries:
        year = int(e["date"][:4])
        by_year.setdefault(year, []).append(e)
    return by_year


def build_index(dates: list[str], years_per_metal: dict[str, list[int]]) -> dict:
    sorted_dates = sorted(dates)
    all_years = sorted({y for ys in years_per_metal.values() for y in ys})
    return {
        "last_updated": sorted_dates[-1] if sorted_dates else None,
        "metals": list(METALS.keys()),
        "metal_info": {m: {"symbol": v["symbol"], "unit": v["unit"]} for m, v in METALS.items()},
        "years": all_years,
        "years_per_metal": years_per_metal,
        "total_days": len(sorted_dates),
        "date_range": {
            "from": sorted_dates[0] if sorted_dates else None,
            "to": sorted_dates[-1] if sorted_dates else None,
        },
        "latest_window": LATEST_WINDOW,
    }


def write_metal_files(metal: str, entries: list[dict], out_root: Path):
    """Write {metal}/{year}.json and {metal}/latest.json."""
    info = METALS[metal]
    metal_dir = out_root / metal
    metal_dir.mkdir(parents=True, exist_ok=True)

    # Sort newest-first overall
    entries_sorted = sorted(entries, key=lambda e: e["date"], reverse=True)

    # latest.json — last LATEST_WINDOW entries
    latest = {
        "metal": metal,
        "symbol": info["symbol"],
        "unit": info["unit"],
        "last_updated": entries_sorted[0]["date"] if entries_sorted else None,
        "window_days": LATEST_WINDOW,
        "data": entries_sorted[:LATEST_WINDOW],
    }
    (metal_dir / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2))

    # Per-year files (full data, newest-first within year)
    by_year = split_by_year(entries_sorted)
    years = sorted(by_year.keys(), reverse=True)
    for year in years:
        year_data = sorted(by_year[year], key=lambda e: e["date"], reverse=True)
        year_obj = {
            "metal": metal,
            "symbol": info["symbol"],
            "unit": info["unit"],
            "year": year,
            "data": year_data,
        }
        (metal_dir / f"{year}.json").write_text(json.dumps(year_obj, ensure_ascii=False, indent=2))

    return years


def cleanup_legacy(metals_dir: Path):
    """Remove pre-refactor flat files (data/metals/copper.json etc)."""
    for metal in METALS:
        legacy = metals_dir / f"{metal}.json"
        if legacy.exists() and legacy.is_file():
            legacy.unlink()


def run(data_dir: Path):
    daily_dir = data_dir / "daily"
    metals_dir = data_dir / "metals"
    metals_dir.mkdir(parents=True, exist_ok=True)

    dailies = []
    for f in sorted(daily_dir.glob("*.json")):
        dailies.append(json.loads(f.read_text()))

    if not dailies:
        print("No daily data found")
        return

    exchange_path = data_dir / "exchange" / "usd_krw.json"
    rates_map = {}
    if exchange_path.exists():
        exchange_data = json.loads(exchange_path.read_text())
        for r in exchange_data.get("rates", []):
            rates_map[r["date"]] = r["rate"]

    cleanup_legacy(metals_dir)

    years_per_metal: dict[str, list[int]] = {}
    for metal in METALS:
        entries = []
        for daily in dailies:
            e = build_entry(daily, metal, rates_map)
            if e:
                entries.append(e)
        years = write_metal_files(metal, entries, metals_dir)
        years_per_metal[metal] = years
        print(f"Built: {metal} ({len(entries)} days, years {years[-1] if years else '-'}~{years[0] if years else '-'})")

    dates = [d["date"] for d in dailies]
    index = build_index(dates, years_per_metal)
    (data_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2))
    print(f"Index: {index['total_days']} days, years {index['years']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    args = ap.parse_args()
    run(args.data_dir)
