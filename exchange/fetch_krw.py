"""BOK ECOS 환율 fetcher.

지원 통화: USD, EUR, CNY (대원화 매매기준율).

출력: data/exchange.bok.json
{
  "currencies": {
    "USD": {"item_code": "0000001", "rates": [{"date": "...", "rate": ...}, ...]},
    "EUR": {"item_code": "0000003", "rates": [...]},
    "CNY": {"item_code": "0000053", "rates": [...]}
  },
  "rates": [...],          # USD mirror (builder backward-compat)
  "last_updated": "YYYY-MM-DD"
}
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import requests

BOK_API_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
STAT_CODE = "731Y001"

# 731Y001 item codes
CURRENCIES: dict[str, dict] = {
    "USD": {"item_code": "0000001", "start_history": "2015-01-01"},
    "EUR": {"item_code": "0000003", "start_history": "2015-01-01"},
    "CNY": {"item_code": "0000053", "start_history": "2016-01-04"},  # CNY 데이터 시작일
}


def parse_bok_response(data: dict) -> list[dict]:
    rows = data.get("StatisticSearch", {}).get("row", [])
    rates = []
    for row in rows:
        time_str = row["TIME"]
        date = f"{time_str[:4]}-{time_str[4:6]}-{time_str[6:8]}"
        try:
            rate = float(row["DATA_VALUE"])
        except (ValueError, TypeError):
            continue
        rates.append({"date": date, "rate": rate})
    return rates


def fetch_currency(api_key: str, item_code: str, start_date: str, end_date: str) -> list[dict]:
    start = start_date.replace("-", "")
    end = end_date.replace("-", "")
    url = f"{BOK_API_URL}/{api_key}/json/kr/1/10000/{STAT_CODE}/D/{start}/{end}/{item_code}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return parse_bok_response(resp.json())


def merge_rates(existing: list[dict], new: list[dict]) -> list[dict]:
    by_date = {r["date"]: r for r in existing}
    for r in new:
        by_date[r["date"]] = r  # 신규 우선 (정정값 반영)
    return sorted(by_date.values(), key=lambda r: r["date"], reverse=True)


def run(data_dir: Path, api_key: str, start_date: str | None = None):
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "exchange.bok.json"

    if out_path.exists():
        existing_doc = json.loads(out_path.read_text())
    else:
        existing_doc = {}

    existing_currencies = existing_doc.get("currencies", {})
    end_date = datetime.now().strftime("%Y-%m-%d")

    out_currencies: dict[str, dict] = {}
    for code, meta in CURRENCIES.items():
        prev = existing_currencies.get(code, {})
        prev_rates = prev.get("rates", [])

        if start_date is not None:
            window_start = start_date
        elif prev_rates:
            window_start = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        else:
            window_start = meta["start_history"]

        try:
            fetched = fetch_currency(api_key, meta["item_code"], window_start, end_date)
        except Exception as e:
            print(f"  {code}: fetch error ({e}); 기존 데이터 보존")
            out_currencies[code] = prev or {"item_code": meta["item_code"], "rates": []}
            continue

        merged = merge_rates(prev_rates, fetched)
        out_currencies[code] = {
            "item_code": meta["item_code"],
            "rates": merged,
        }
        latest = merged[0]["date"] if merged else "-"
        print(f"  {code}: {len(merged)} entries ({len(fetched)} fetched), latest {latest}")

    usd_rates = out_currencies.get("USD", {}).get("rates", [])
    last_updated = max(
        (c.get("rates", [{}])[0].get("date", "") for c in out_currencies.values() if c.get("rates")),
        default="",
    )

    output = {
        "currencies": out_currencies,
        "rates": usd_rates,  # builder backward-compat
        "last_updated": last_updated or None,
    }
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Exchange: USD/EUR/CNY → {out_path.name}, last {last_updated}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--start-date", type=str, default=None,
                    help="강제 시작일 (예: 2015-01-01). 미지정시 incremental.")
    args = ap.parse_args()
    api_key = os.environ.get("ECOS_API_KEY", "")
    if not api_key:
        print("ERROR: ECOS_API_KEY environment variable not set")
        exit(1)
    run(args.data_dir, api_key, args.start_date)
