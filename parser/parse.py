import argparse
import json
import re
from pathlib import Path
import pdfplumber

from parser.page1 import parse_lme_prices, parse_settlement, parse_ev_metals
from parser.page2 import parse_inventory, parse_shfe_spread, parse_market_factors
from parser.page3 import parse_precious_metals

METALS_ORDER = ["copper", "aluminum", "zinc", "lead", "nickel", "tin"]
DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def extract_date_from_pdf(pdf: pdfplumber.PDF) -> str:
    first_page_text = pdf.pages[0].extract_text() or ""
    for line in first_page_text.split("\n")[:5]:
        match = DATE_PATTERN.search(line)
        if match:
            return match.group(1)
    raise ValueError("Cannot extract date from PDF")


def parse_pdf(pdf_path: Path) -> dict:
    pdf = pdfplumber.open(pdf_path)
    if len(pdf.pages) < 3:
        raise ValueError(f"Expected at least 3 pages, got {len(pdf.pages)}")

    date = extract_date_from_pdf(pdf)

    p1_tables = pdf.pages[0].extract_tables()
    if len(p1_tables) < 3:
        raise ValueError(f"Page 1: expected 3+ tables, got {len(p1_tables)}")
    lme_prices = parse_lme_prices(p1_tables[0])
    settlement = parse_settlement(p1_tables[1])
    ev_metals = parse_ev_metals(p1_tables[2])

    p2_tables = pdf.pages[1].extract_tables()
    if len(p2_tables) < 7:
        raise ValueError(f"Page 2: expected 7+ tables, got {len(p2_tables)}")
    inventory = parse_inventory(p2_tables[0])
    shfe = parse_shfe_spread(p2_tables[5])
    market = parse_market_factors(p2_tables[6])

    p3_tables = pdf.pages[2].extract_tables()
    if len(p3_tables) < 1:
        raise ValueError(f"Page 3: expected 1+ tables, got {len(p3_tables)}")
    precious = parse_precious_metals(p3_tables[0])

    metals = {}
    for metal in METALS_ORDER:
        metals[metal] = {
            "lme": lme_prices[metal],
            "settlement": settlement[metal],
            "inventory": inventory[metal],
            "shfe": shfe["metals"][metal],
        }

    pdf.close()

    return {
        "date": date,
        "metals": metals,
        "ev_metals": ev_metals,
        "precious": precious,
        "fx": {"cny_usd": shfe["cny_usd"]},
        "market": market,
    }


def run(mode: str, data_dir: Path, tmp_dir: Path):
    daily_dir = data_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = tmp_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        pdfs = sorted(tmp_dir.glob("*.pdf"))
        manifest = [{"date": p.stem, "path": str(p)} for p in pdfs]

    parsed = 0
    for entry in manifest:
        pdf_path = Path(entry["path"])

        if not pdf_path.exists():
            print(f"SKIP (not found): {pdf_path}")
            continue

        try:
            data = parse_pdf(pdf_path)
            actual_date = data["date"]
            out_path = daily_dir / f"{actual_date}.json"
            if out_path.exists():
                continue
            out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            parsed += 1
            print(f"Parsed: {actual_date}")
        except Exception as e:
            print(f"ERROR parsing {pdf_path.name}: {e}")

    print(f"Total parsed: {parsed}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["latest", "backfill"], default="latest")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--tmp-dir", type=Path, default=Path("tmp/pdfs"))
    args = ap.parse_args()
    run(args.mode, args.data_dir, args.tmp_dir)
