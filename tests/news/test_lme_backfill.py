"""LME backfill / validate / fallback tests."""
import json
from datetime import date
from pathlib import Path

from builder.lme_backfill import (
    _build_synth_json,
    _by_date,
    backfill,
    fallback_today,
    validate,
)
from scraper.lme.prices import LMEDailyPrice


def _wm(d: date, metal: str, cash: float, three: float, inv: int) -> LMEDailyPrice:
    return LMEDailyPrice(date=d, metal=metal, sett_cash=cash, sett_3m=three, inv_current=inv)


def test_build_synth_json_shape():
    d = date(2026, 5, 4)
    per_metal = {
        m: _wm(d, m, 1000.0 + i, 1010.0 + i, 100 + i)
        for i, m in enumerate(["copper", "aluminum", "zinc", "nickel", "lead", "tin"])
    }
    j = _build_synth_json(d, per_metal)
    assert j["date"] == "2026-05-04"
    assert j["_source"] == "westmetall"
    assert "_fetched_at" in j
    cu = j["metals"]["copper"]
    assert cu["settlement"]["cash"] == 1000.0
    assert cu["settlement"]["3m"] == 1010.0
    assert cu["inventory"]["current"] == 100
    assert cu["lme"]["cash"]["close"] == 1000.0


def test_backfill_skips_existing(tmp_path: Path, monkeypatch):
    daily = tmp_path / "daily"
    daily.mkdir()
    existing = daily / "2026-05-01.json"
    existing.write_text('{"date": "2026-05-01", "metals": {}}')

    histories = {
        m: [_wm(date(2026, 5, 1), m, 1000, 1010, 100), _wm(date(2026, 5, 2), m, 1100, 1110, 110)]
        for m in ["copper", "aluminum", "zinc", "nickel", "lead", "tin"]
    }
    monkeypatch.setattr(
        "builder.lme_backfill._load_all_histories",
        lambda: histories,
    )
    written = backfill(daily)
    assert written == 1  # only 2026-05-02 (existing 2026-05-01 skipped)
    assert (daily / "2026-05-02.json").exists()
    # existing untouched
    assert json.loads(existing.read_text())["metals"] == {}


def test_backfill_skips_partial_dates(tmp_path: Path, monkeypatch):
    daily = tmp_path / "daily"
    histories = {
        # only 3 of 6 metals on 2026-05-02 → skip
        "copper": [_wm(date(2026, 5, 2), "copper", 1000, 1010, 100)],
        "aluminum": [_wm(date(2026, 5, 2), "aluminum", 2000, 2010, 200)],
        "zinc": [_wm(date(2026, 5, 2), "zinc", 3000, 3010, 300)],
        "nickel": [],
        "lead": [],
        "tin": [],
    }
    monkeypatch.setattr("builder.lme_backfill._load_all_histories", lambda: histories)
    written = backfill(daily)
    assert written == 0


def test_validate_detects_divergence(tmp_path: Path, monkeypatch):
    daily = tmp_path / "daily"
    daily.mkdir()
    nh_json = {
        "date": "2026-05-01",
        "metals": {
            "copper": {
                "settlement": {"cash": 9000.0, "3m": 9020.0},
                "inventory": {"current": 100},
            }
        },
    }
    (daily / "2026-05-01.json").write_text(json.dumps(nh_json))

    # Westmetall says different cash price → divergence
    histories = {
        "copper": [_wm(date(2026, 5, 1), "copper", 9050.0, 9020.0, 100)],
        "aluminum": [], "zinc": [], "nickel": [], "lead": [], "tin": [],
    }
    monkeypatch.setattr("builder.lme_backfill._load_all_histories", lambda: histories)
    result = validate(daily)
    assert result["checked_dates"] == 1
    assert result["issues"] == 1
    issue = result["issue_detail"][0]
    assert issue["metal"] == "copper"
    assert issue["field"] == "sett_cash"
    assert issue["diff"] == -50.0


def test_validate_skips_synth(tmp_path: Path, monkeypatch):
    """Files marked _source=westmetall must not self-compare."""
    daily = tmp_path / "daily"
    daily.mkdir()
    synth = {
        "date": "2026-05-01",
        "_source": "westmetall",
        "metals": {"copper": {"settlement": {"cash": 9000}, "inventory": {"current": 100}}},
    }
    (daily / "2026-05-01.json").write_text(json.dumps(synth))

    histories = {
        "copper": [_wm(date(2026, 5, 1), "copper", 9050, 9020, 100)],
        "aluminum": [], "zinc": [], "nickel": [], "lead": [], "tin": [],
    }
    monkeypatch.setattr("builder.lme_backfill._load_all_histories", lambda: histories)
    result = validate(daily)
    assert result["checked_dates"] == 0
    assert result["issues"] == 0


def test_fallback_writes_when_missing(tmp_path: Path, monkeypatch):
    daily = tmp_path / "daily"
    today = date(2026, 5, 4)
    yesterday = date(2026, 5, 1)
    # New trading: 5/4 differs from 5/1
    histories = {
        m: [
            _wm(today, m, 1100.0 + i, 1110.0 + i, 200 + i),
            _wm(yesterday, m, 1000.0 + i, 1010.0 + i, 100 + i),
        ]
        for i, m in enumerate(["copper", "aluminum", "zinc", "nickel", "lead", "tin"])
    }
    monkeypatch.setattr("builder.lme_backfill._load_all_histories", lambda: histories)
    used = fallback_today(today=today, daily_dir=daily)
    assert used is True
    out = daily / "2026-05-04.json"
    assert out.exists()
    j = json.loads(out.read_text())
    assert j["_source"] == "westmetall"


def test_fallback_skips_lme_holiday_carry_over(tmp_path: Path, monkeypatch):
    """5/4 row identical to 5/1 row → LME holiday → skip, keep 5/1 as latest."""
    daily = tmp_path / "daily"
    today = date(2026, 5, 4)
    yesterday = date(2026, 5, 1)
    # Identical values across days = LME holiday
    histories = {
        m: [
            _wm(today, m, 1000.0 + i, 1010.0 + i, 100 + i),
            _wm(yesterday, m, 1000.0 + i, 1010.0 + i, 100 + i),
        ]
        for i, m in enumerate(["copper", "aluminum", "zinc", "nickel", "lead", "tin"])
    }
    monkeypatch.setattr("builder.lme_backfill._load_all_histories", lambda: histories)
    used = fallback_today(today=today, daily_dir=daily)
    assert used is False
    assert not (daily / "2026-05-04.json").exists()


def test_fallback_skips_when_nh_present(tmp_path: Path, monkeypatch):
    daily = tmp_path / "daily"
    daily.mkdir()
    today = date(2026, 5, 4)
    (daily / "2026-05-04.json").write_text('{"date": "2026-05-04"}')
    monkeypatch.setattr("builder.lme_backfill._load_all_histories", lambda: {})
    used = fallback_today(today=today, daily_dir=daily)
    assert used is False
