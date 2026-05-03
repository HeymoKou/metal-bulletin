import argparse
import json
import re
from pathlib import Path
import pdfplumber

from parser.page1 import parse_lme_prices, parse_settlement, parse_ev_metals
from parser.page2 import parse_inventory, parse_shfe_spread, parse_market_factors
from parser.page3 import parse_precious_metals

METALS_ORDER = ["copper", "aluminum", "zinc", "lead", "nickel", "tin"]
DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
DATE_DMY = re.compile(r"(\d{2})-(\d{2})-(\d{4})")  # DD-MM-YYYY (older PDFs)
DATE_DOTTED = re.compile(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})")  # YYYY. MM. DD


def extract_date_from_pdf(pdf: pdfplumber.PDF) -> str:
    first_page_text = pdf.pages[0].extract_text() or ""
    for line in first_page_text.split("\n")[:8]:
        m = DATE_ISO.search(line)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        m = DATE_DMY.search(line)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        m = DATE_DOTTED.search(line)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    raise ValueError("Cannot extract date from PDF")


def _safe(fn, *args, **kwargs):
    """Run a parser fn; return ({}, error_msg) on failure."""
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return {}, f"{fn.__name__}: {e}"


def parse_pdf(pdf_path: Path) -> dict:
    pdf = pdfplumber.open(pdf_path)
    try:
        if not pdf.pages:
            raise ValueError("Empty PDF")

        date = extract_date_from_pdf(pdf)
        warnings: list[str] = []

        # Page 1
        p1_tables = pdf.pages[0].extract_tables() if len(pdf.pages) >= 1 else []
        lme_prices, err = _safe(parse_lme_prices, p1_tables[0]) if len(p1_tables) >= 1 else ({}, "no p1 table 0")
        if err: warnings.append(f"lme: {err}")
        settlement, err = _safe(parse_settlement, p1_tables[1]) if len(p1_tables) >= 2 else ({}, "no p1 table 1")
        if err: warnings.append(f"settlement: {err}")
        ev_metals, err = _safe(parse_ev_metals, p1_tables[2]) if len(p1_tables) >= 3 else ({}, None)
        if err: warnings.append(f"ev: {err}")

        # Page 2
        p2_tables = pdf.pages[1].extract_tables() if len(pdf.pages) >= 2 else []
        inventory, err = _safe(parse_inventory, p2_tables[0]) if p2_tables else ({}, "no p2")
        if err: warnings.append(f"inv: {err}")

        shfe_idx = None
        market_idx = None
        for idx, t in enumerate(p2_tables):
            header = str(t[0][0]) if t and t[0] else ""
            if "SHFE" in header and "LME" in header:
                shfe_idx = idx
            if shfe_idx is not None and idx == shfe_idx + 1:
                market_idx = idx
        if shfe_idx is None:
            for idx, t in enumerate(p2_tables):
                if len(t) >= 7 and t[0] and len(t[0]) >= 10:
                    cell = str(t[0][0]) if t[0][0] else ""
                    if "CNY" in cell or "증치세" in cell:
                        shfe_idx = idx
                        break

        if shfe_idx is not None:
            shfe, err = _safe(parse_shfe_spread, p2_tables[shfe_idx])
            if err: warnings.append(f"shfe: {err}")
        else:
            shfe = {}
            warnings.append("shfe: table not found")

        if market_idx is not None and market_idx < len(p2_tables):
            market, err = _safe(parse_market_factors, p2_tables[market_idx])
            if err: warnings.append(f"market: {err}")
        else:
            market = {}

        # Page 3
        p3_tables = pdf.pages[2].extract_tables() if len(pdf.pages) >= 3 else []
        precious, err = _safe(parse_precious_metals, p3_tables[0]) if p3_tables else ({}, None)
        if err: warnings.append(f"precious: {err}")

        # Combine per-metal
        shfe_metals = (shfe or {}).get("metals", {}) if isinstance(shfe, dict) else {}
        metals = {}
        for metal in METALS_ORDER:
            metals[metal] = {
                "lme": lme_prices.get(metal, {}) if isinstance(lme_prices, dict) else {},
                "settlement": settlement.get(metal, {}) if isinstance(settlement, dict) else {},
                "inventory": inventory.get(metal, {}) if isinstance(inventory, dict) else {},
                "shfe": shfe_metals.get(metal, {}),
            }

        # Require at least LME prices for at least one metal — otherwise too broken to keep
        if not any(m["lme"] for m in metals.values()):
            raise ValueError(f"no LME data extracted (warnings: {warnings})")

        out = {
            "date": date,
            "metals": metals,
            "ev_metals": ev_metals if isinstance(ev_metals, dict) else {},
            "precious": precious if isinstance(precious, dict) else {},
            "fx": {"cny_usd": (shfe or {}).get("cny_usd")} if isinstance(shfe, dict) else {},
            "market": market if isinstance(market, dict) else {},
        }
        if warnings:
            out["_warnings"] = warnings
        return out
    finally:
        pdf.close()


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
