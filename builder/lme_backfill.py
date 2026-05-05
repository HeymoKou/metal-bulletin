"""LME backfill via westmetall — historical fill + holiday fallback + cross-validation.

Modes:
  --mode backfill   : fetch westmetall histories, synthesize JSONs for missing dates
  --mode validate   : compare existing daily JSONs vs westmetall, log discrepancies
  --mode fallback   : check today only — if NH JSON missing, write westmetall synthesized JSON

Synthesized JSONs preserve only fields westmetall exposes:
  - settlement.cash (sett_cash)
  - settlement['3m'] (sett_3m)
  - inventory.current (inv_current)
  - lme.cash.close (mirrors sett_cash for plot continuity)
Other fields (lme open/high/low, bid/ask, OI, forwards, monthly_avg, shfe, full inventory)
are omitted — null in parquet, FE shows '—' for those days.

Source attribution: every synthesized JSON has `"_source": "westmetall"`.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable

from scraper.lme.prices import (
    LMEDailyPrice,
    METAL_TO_SYMBOL,
    fetch_metal_history,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

DAILY_DIR = Path("data/daily")

# Cross-validation tolerance — westmetall and NH PDF cross-validated to Δ=0.00
# on 90 days. Strict 0.01 catches any divergence; loosen if rounding causes noise.
TOLERANCE_USD = 0.01
TOLERANCE_TONNES = 1


def _synth_metal_block(p: LMEDailyPrice) -> dict:
    """Westmetall row → minimal NH-format metal block."""
    return {
        "lme": {
            "cash": {"close": p.sett_cash},  # mirror for FE chart continuity
        },
        "settlement": {
            "cash": p.sett_cash,
            "3m": p.sett_3m,
        },
        "inventory": {
            "current": p.inv_current,
        },
    }


def _build_synth_json(d: date, per_metal: dict[str, LMEDailyPrice]) -> dict:
    return {
        "date": d.isoformat(),
        "_source": "westmetall",
        "_fetched_at": datetime.now(UTC).isoformat(),
        "metals": {metal: _synth_metal_block(p) for metal, p in per_metal.items()},
    }


def _load_all_histories() -> dict[str, list[LMEDailyPrice]]:
    """Per-metal full history from westmetall."""
    out: dict[str, list[LMEDailyPrice]] = {}
    for metal in METAL_TO_SYMBOL:
        history = fetch_metal_history(metal)
        out[metal] = history
        logger.info("westmetall %s: %d days", metal, len(history))
    return out


def _by_date(histories: dict[str, list[LMEDailyPrice]]) -> dict[date, dict[str, LMEDailyPrice]]:
    by_date: dict[date, dict[str, LMEDailyPrice]] = {}
    for metal, rows in histories.items():
        for r in rows:
            by_date.setdefault(r.date, {})[metal] = r
    return by_date


def backfill(daily_dir: Path = DAILY_DIR) -> int:
    """Write synthetic JSONs for dates missing NH data. Returns count written."""
    daily_dir.mkdir(parents=True, exist_ok=True)
    existing: set[date] = {
        date.fromisoformat(p.stem) for p in daily_dir.glob("*.json")
        if _is_iso_date(p.stem)
    }

    histories = _load_all_histories()
    by_date = _by_date(histories)
    written = 0
    for d, per_metal in sorted(by_date.items()):
        if d in existing:
            continue
        if len(per_metal) < 6:
            logger.debug("skip %s — only %d metals available (need 6)", d, len(per_metal))
            continue
        out_path = daily_dir / f"{d.isoformat()}.json"
        out_path.write_text(
            json.dumps(_build_synth_json(d, per_metal), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written += 1
    logger.info("backfill: wrote %d synthetic daily JSONs", written)
    return written


def validate(daily_dir: Path = DAILY_DIR, max_dates: int | None = None) -> dict:
    """Compare existing NH JSONs vs westmetall. Return summary dict."""
    histories = _load_all_histories()
    by_date = _by_date(histories)

    issues: list[dict] = []
    checked = 0
    for json_path in sorted(daily_dir.glob("*.json")):
        if not _is_iso_date(json_path.stem):
            continue
        d = date.fromisoformat(json_path.stem)
        if d not in by_date:
            continue
        try:
            nh_data = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if nh_data.get("_source") == "westmetall":
            continue  # synth file, skip self-comparison
        for metal, wm in by_date[d].items():
            nh_metal = (nh_data.get("metals") or {}).get(metal)
            if not nh_metal:
                continue
            nh_cash = (nh_metal.get("settlement") or {}).get("cash")
            nh_3m = (nh_metal.get("settlement") or {}).get("3m")
            nh_inv = (nh_metal.get("inventory") or {}).get("current")
            for label, nh_val, wm_val, tol in [
                ("sett_cash", nh_cash, wm.sett_cash, TOLERANCE_USD),
                ("sett_3m", nh_3m, wm.sett_3m, TOLERANCE_USD),
                ("inv_current", nh_inv, wm.inv_current, TOLERANCE_TONNES),
            ]:
                if nh_val is None:
                    continue
                if abs(nh_val - wm_val) > tol:
                    issues.append({
                        "date": d.isoformat(),
                        "metal": metal,
                        "field": label,
                        "nh": nh_val,
                        "wm": wm_val,
                        "diff": nh_val - wm_val,
                    })
        checked += 1
        if max_dates and checked >= max_dates:
            break

    summary = {"checked_dates": checked, "issues": len(issues), "issue_detail": issues[:20]}
    logger.info("validate: checked %d dates, %d divergences", checked, len(issues))
    return summary


def fallback_today(today: date | None = None, daily_dir: Path = DAILY_DIR) -> bool:
    """If today's NH JSON missing, write westmetall synth. Return True if fallback used."""
    today = today or date.today()
    target = daily_dir / f"{today.isoformat()}.json"
    if target.exists():
        logger.info("fallback skip: %s exists (NH provided)", target.name)
        return False
    histories = _load_all_histories()
    by_date = _by_date(histories)
    per_metal = by_date.get(today)
    if not per_metal or len(per_metal) < 6:
        logger.warning("fallback: westmetall has no/partial data for %s (got %d)",
                       today, len(per_metal or {}))
        return False
    daily_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_build_synth_json(today, per_metal), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("fallback: wrote %s from westmetall", target.name)
    return True


def _is_iso_date(s: str) -> bool:
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["backfill", "validate", "fallback"], required=True)
    ap.add_argument("--max-dates", type=int, default=None, help="validate: cap dates checked")
    ap.add_argument("--date", type=str, default=None, help="fallback: explicit KST date YYYY-MM-DD")
    ap.add_argument("--daily-dir", type=Path, default=DAILY_DIR)
    args = ap.parse_args()

    if args.mode == "backfill":
        backfill(args.daily_dir)
    elif args.mode == "validate":
        result = validate(args.daily_dir, max_dates=args.max_dates)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif args.mode == "fallback":
        target_date = date.fromisoformat(args.date) if args.date else None
        fallback_today(today=target_date, daily_dir=args.daily_dir)


if __name__ == "__main__":
    main()
