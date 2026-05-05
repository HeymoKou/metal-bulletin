import argparse
import json
import os
from datetime import datetime
from pathlib import Path
import requests

BOK_API_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
STAT_CODE = "731Y001"
ITEM_CODE = "0000001"


def parse_bok_response(data: dict) -> list[dict]:
    rows = data.get("StatisticSearch", {}).get("row", [])
    rates = []
    for row in rows:
        time_str = row["TIME"]
        date = f"{time_str[:4]}-{time_str[4:6]}-{time_str[6:8]}"
        rates.append({
            "date": date,
            "rate": float(row["DATA_VALUE"]),
        })
    return rates


def fetch_rates(api_key: str, start_date: str, end_date: str) -> list[dict]:
    start = start_date.replace("-", "")
    end = end_date.replace("-", "")
    url = f"{BOK_API_URL}/{api_key}/json/kr/1/10000/{STAT_CODE}/D/{start}/{end}/{ITEM_CODE}"
    resp = requests.get(url)
    resp.raise_for_status()
    return parse_bok_response(resp.json())


def run(data_dir: Path, api_key: str, start_date: str | None = None):
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "exchange.bok.json"

    if out_path.exists():
        existing = json.loads(out_path.read_text())
        existing_rates = existing.get("rates", [])
    else:
        existing_rates = []

    existing_dates = {r["date"] for r in existing_rates}

    if start_date is None:
        # 첫 실행: 5년치. 이후: 최근 60일만 보강 (영업일 갭 + 정정 대비)
        if existing_rates:
            from datetime import timedelta
            start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        else:
            start_date = (datetime.now().replace(year=datetime.now().year - 5)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    new_rates = fetch_rates(api_key, start_date, end_date)
    for rate in new_rates:
        if rate["date"] not in existing_dates:
            existing_rates.append(rate)
            existing_dates.add(rate["date"])

    existing_rates.sort(key=lambda r: r["date"], reverse=True)

    output = {
        "rates": existing_rates,
        "last_updated": existing_rates[0]["date"] if existing_rates else None,
    }
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Exchange rates: {len(existing_rates)} entries, latest: {output['last_updated']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--start-date", type=str, default=None)
    args = ap.parse_args()
    api_key = os.environ.get("ECOS_API_KEY", "")
    if not api_key:
        print("ERROR: ECOS_API_KEY environment variable not set")
        exit(1)
    run(args.data_dir, api_key, args.start_date)
