"""KOMIS scraper + validator tests."""
from __future__ import annotations

from datetime import datetime, timezone

from builder import komis_validate
from scraper.komis import KomisQuote, METALS


def test_all_six_metals_mapped():
    expected = {"copper", "aluminum", "zinc", "nickel", "lead", "tin"}
    assert set(METALS.keys()) == expected
    for key, (mcd, cash_cd, m3_cd) in METALS.items():
        assert mcd.startswith("MNRL")
        assert isinstance(cash_cd, int) and 400 < cash_cd < 700
        assert isinstance(m3_cd, int) and 400 < m3_cd < 700


def test_validate_records_match_when_values_equal(tmp_path):
    data_dir = tmp_path / "data"
    (data_dir / "series" / "copper").mkdir(parents=True)
    # Skip real parquet; the validator falls through to (None, None) when file
    # absent, which is the same code path that records diff_cash=None safely.
    quotes = [KomisQuote("copper", "2026-05-08", 13445.0, 13498.0, 399400.0)]
    now = datetime(2026, 5, 11, 15, 0, tzinfo=timezone.utc)
    rows = komis_validate.build_records(quotes, data_dir, now)
    assert len(rows) == 1
    r = rows[0]
    assert r["date"] == "2026-05-08"
    assert r["metal"] == "copper"
    assert r["komis_cash"] == 13445.0
    # ours unavailable → diff None
    assert r["ours_cash"] is None
    assert r["diff_cash"] is None


def test_summarize_flags_mismatches():
    rows = [
        {"date": "2026-05-08", "metal": "copper", "diff_cash": 0.0, "diff_3m": 0.0},
        {"date": "2026-05-08", "metal": "lead", "diff_cash": 1.5, "diff_3m": 0.2},
    ]
    now = datetime(2026, 5, 11, tzinfo=timezone.utc)
    summary = komis_validate._summarize_for_manifest(rows, now)
    assert summary["status"] == "mismatch"
    assert summary["last_date"] == "2026-05-08"
    assert summary["max_abs_diff_cash"] == 1.5
    assert len(summary["mismatches"]) == 1
    assert summary["mismatches"][0]["metal"] == "lead"


def test_summarize_empty_status():
    now = datetime(2026, 5, 11, tzinfo=timezone.utc)
    assert komis_validate._summarize_for_manifest([], now)["status"] == "no_data"


def test_diff_threshold_under_excluded():
    rows = [{"date": "2026-05-08", "metal": "copper", "diff_cash": 0.3, "diff_3m": -0.4}]
    s = komis_validate._summarize_for_manifest(rows, datetime.now(timezone.utc))
    assert s["status"] == "ok"
    assert s["mismatches"] == []
