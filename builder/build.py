import argparse
import json
from pathlib import Path

METALS = {
    "copper": {"symbol": "Cu", "unit": "$/ton"},
    "aluminum": {"symbol": "Al", "unit": "$/ton"},
    "zinc": {"symbol": "Zn", "unit": "$/ton"},
    "lead": {"symbol": "Pb", "unit": "$/ton"},
    "nickel": {"symbol": "Ni", "unit": "$/ton"},
    "tin": {"symbol": "Sn", "unit": "$/ton"},
}


def resolve_rate(daily: dict, rates_map: dict[str, float]) -> tuple[float | None, str | None]:
    """Resolve USD/KRW for a daily entry.

    Priority: BOK ECOS (rates_map) → PDF market.krw_usd → None.
    Returns (rate, source) where source is 'bok' | 'pdf' | None.
    """
    bok_rate = rates_map.get(daily["date"])
    if bok_rate:
        return bok_rate, "bok"
    pdf_rate = (daily.get("market") or {}).get("krw_usd")
    if pdf_rate:
        return pdf_rate, "pdf"
    return None, None


def build_metal_timeseries(metal: str, dailies: list[dict], rates_map: dict[str, float]) -> dict:
    info = METALS[metal]
    data = []
    for daily in dailies:
        date = daily["date"]
        m = daily["metals"].get(metal)
        if not m:
            continue

        rate, rate_source = resolve_rate(daily, rates_map)
        cash_close = None
        tm_close = None

        lme = m.get("lme", {})
        if "cash" in lme:
            cash_close = lme["cash"].get("close")
        if "3m" in lme:
            tm_close = lme["3m"].get("close")

        krw = {}
        if rate:
            if cash_close is not None:
                krw["cash"] = round(cash_close * rate)
            if tm_close is not None:
                krw["3m"] = round(tm_close * rate)
            krw["rate"] = rate
            krw["source"] = rate_source

        data.append({
            "date": date,
            "lme": lme,
            "settlement": m.get("settlement", {}),
            "inventory": m.get("inventory", {}),
            "shfe": m.get("shfe", {}),
            "krw": krw,
        })

    data.sort(key=lambda d: d["date"], reverse=True)

    return {
        "metal": metal,
        "symbol": info["symbol"],
        "unit": info["unit"],
        "last_updated": data[0]["date"] if data else None,
        "data": data,
    }


def build_index(dates: list[str]) -> dict:
    sorted_dates = sorted(dates)
    return {
        "last_updated": sorted_dates[-1] if sorted_dates else None,
        "metals": list(METALS.keys()),
        "total_days": len(sorted_dates),
        "date_range": {
            "from": sorted_dates[0] if sorted_dates else None,
            "to": sorted_dates[-1] if sorted_dates else None,
        },
    }


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

    for metal in METALS:
        ts = build_metal_timeseries(metal, dailies, rates_map)
        out = metals_dir / f"{metal}.json"
        out.write_text(json.dumps(ts, ensure_ascii=False, indent=2))
        print(f"Built: {metal} ({len(ts['data'])} days)")

    dates = [d["date"] for d in dailies]
    index = build_index(dates)
    index_path = data_dir / "index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2))
    print(f"Index: {index['total_days']} days, {index['date_range']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    args = ap.parse_args()
    run(args.data_dir)
