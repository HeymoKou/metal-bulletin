"""Smoke tests for structural changes in this session:

- Settlement monthly_avg ↔ prev_monthly_avg swap (parser fix + raw/series migration)
- News source narrowed to snmnews-only + PPS added
- classify bypass for source=pps
- Sb FE default region switched to rotterdam

Each block fails loudly on regression rather than silently drifting.
"""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


# ----------------------------- settlement migration -----------------------------

def test_lme_settle_column_for_copper_2026_05_08():
    """PDF col[6-7] = LME 정산가 (London 17:00) — stored as sett_lme_settle_*.
    Verify spot value preserved through rename migration.
    """
    t = pq.read_table(DATA / "series" / "copper" / "latest.parquet").to_pandas()
    row = t[t["date"] == "2026-05-08"].iloc[0]
    # The exact LME settle Cash value at London 17:00 for Cu 5/8
    assert row["sett_lme_settle_cash"] == pytest.approx(13515.39, abs=0.01)
    assert row["sett_prev_mavg_cash"] == pytest.approx(12891.38, abs=0.01)


def test_prev_month_avg_pinned_within_month():
    """sett_prev_mavg_cash should be constant within a month (previous month's mean
    doesn't change as days pass within the current month).
    """
    t = pq.read_table(DATA / "series" / "copper" / "latest.parquet").to_pandas()
    may = t[t["date"].str.startswith("2026-05") & t["sett_prev_mavg_cash"].notna()]
    assert len(may) >= 3
    distinct = may["sett_prev_mavg_cash"].nunique()
    assert distinct == 1, (
        f"sett_prev_mavg_cash should be constant within May (April's mean), "
        f"got {distinct} distinct values"
    )


def test_raw_json_settlement_keys_use_lme_settle():
    """Migrated raw JSON must use lme_settle (not legacy monthly_avg) key."""
    t = pq.read_table(DATA / "raw" / "2026.parquet").to_pandas()
    for s in t["json"]:
        d = json.loads(s)
        for metal, m in d.get("metals", {}).items():
            sett = m.get("settlement") or {}
            assert "monthly_avg" not in sett, (
                f"legacy 'monthly_avg' key still present for metal={metal}"
            )


def test_current_month_avg_matches_pdf():
    """builder.current_month_avg.cash must equal daily-mean(sett_cash) for current month.
    This is the true MTD value displayed in FE 당월평균 row.
    """
    import json as _json
    m = _json.loads((DATA / "manifest.json").read_text())
    for metal_key, meta in m["metals"].items():
        cma = meta.get("current_month_avg")
        if not cma or cma.get("cash") is None:
            continue
        t = pq.read_table(DATA / "series" / metal_key / "latest.parquet").to_pandas()
        cur_month = cma["month"]
        same_month = t[t["date"].str.startswith(cur_month) & t["sett_cash"].notna()]
        if same_month.empty:
            continue
        expected = round(same_month["sett_cash"].mean(), 2)
        assert cma["cash"] == pytest.approx(expected, abs=0.01), (
            f"{metal_key} current_month_avg.cash={cma['cash']} ≠ daily mean {expected}"
        )


# ----------------------------- news source pipeline -----------------------------

def test_rss_feeds_is_snmnews_only():
    from scraper.news.rss import RSS_FEEDS
    sources = {f["source"] for f in RSS_FEEDS}
    assert sources == {"snmnews"}, f"unexpected RSS sources: {sources}"


def test_default_scrapers_are_rss_only():
    """Default pipeline = RSS (snmnews). PPS defer (한국 gov GH IP block).
    GDELT/Nonferrous fully removed.
    """
    import inspect

    from scraper.news import run as run_mod

    src = inspect.getsource(run_mod.main)
    assert "RSSScraper()" in src
    assert "GDELTScraper" not in src
    assert "NonferrousScraper" not in src
    # PPSScraper code still imported (manual local runs use it) but not instantiated
    # in default scrapers list
    assert "PPSScraper()" not in src


# ----------------------------- classify PPS bypass -----------------------------

def test_classifier_bypass_for_pps_source():
    """Even a generic title ('주간 경제·비철금속 시장동향') from source=pps must pass.
    Same title from a different source would normally hit through ko keywords,
    but PPS bypass must work regardless of title content.
    """
    from datetime import datetime, timezone

    from parser.news.classify import is_relevant
    from parser.news.models import RawNewsItem

    item = RawNewsItem(
        source="pps",
        url="https://www.pps.go.kr/common/fileDown.do?key=X&sn=1",
        title="알 수 없는 정부 자료",  # No metal keywords
        snippet=None,
        fetched_at=datetime.now(timezone.utc),
        lang="ko",
    )
    assert is_relevant(item) is True


def test_classifier_still_filters_non_pps_irrelevant():
    """Non-pps items with no metal keywords still rejected."""
    from datetime import datetime, timezone

    from parser.news.classify import is_relevant
    from parser.news.models import RawNewsItem

    item = RawNewsItem(
        source="snmnews",
        url="https://example.com/cooking",
        title="레시피와 요리법",
        snippet=None,
        fetched_at=datetime.now(timezone.utc),
        lang="ko",
    )
    assert is_relevant(item) is False


# ----------------------------- Sb FE default region -----------------------------

def test_sb_frontend_defaults_to_rotterdam():
    js = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    # Default arg in minorPriceSeries
    assert "region = 'rotterdam'" in js, "minorPriceSeries default must be rotterdam"
    # Hero usage
    assert "latest.rotterdam" in js
    # No exw_china in hero/pill render paths — keep only the 5-region comparison
    # table reference allowed (in `regions` array)
    forbidden_patterns = [
        "latest.exw_china",
        "ts.data[1]?.exw_china",
        "latest?.exw_china",
        "ts?.data?.[1]?.exw_china",
    ]
    for pat in forbidden_patterns:
        assert pat not in js, f"FE still uses exw_china in hero/pill: {pat!r}"
    # Hero label string must match the actual displayed region
    assert "EXW China · 기준" not in js, "hero label still says EXW China"
    assert "Rotterdam · 기준" in js, "hero label must say Rotterdam"


# ----------------------------- PPS module sanity -----------------------------

def test_pps_module_imports_and_class_shape():
    """PPS scraper class respects NewsSource interface."""
    from scraper.news.base import NewsSource
    from scraper.news.pps import PPSScraper

    s = PPSScraper(limit=1)
    assert isinstance(s, NewsSource)
    assert s.name == "pps"
    assert s.lang == "ko"


# ----------------------------- parquet schema invariants -----------------------

def test_series_parquet_has_expected_settlement_columns():
    """series parquet schema must keep sett_lme_settle_* and sett_prev_mavg_* columns
    (don't accidentally drop on rebuild).
    """
    t = pq.read_table(DATA / "series" / "copper" / "latest.parquet")
    cols = set(t.column_names)
    required = {
        "sett_cash", "sett_3m",
        "sett_lme_settle_cash", "sett_lme_settle_3m",
        "sett_prev_mavg_cash", "sett_prev_mavg_3m",
    }
    missing = required - cols
    assert not missing, f"series parquet missing columns: {missing}"


def test_manifest_has_monthly_6m_per_metal():
    """manifest.metals.{metal}.monthly_6m: list of 6 entries, desc, complete months only."""
    import json as _json
    m = _json.loads((DATA / "manifest.json").read_text())
    for metal_key, meta in m["metals"].items():
        rows = meta.get("monthly_6m")
        assert isinstance(rows, list), f"{metal_key} missing monthly_6m"
        assert len(rows) == 6, f"{metal_key} monthly_6m has {len(rows)} rows (expected 6)"
        months = [r["month"] for r in rows]
        # desc order
        assert months == sorted(months, reverse=True), f"{metal_key} monthly_6m not desc"
        # all distinct
        assert len(set(months)) == 6, f"{metal_key} monthly_6m has dupes"
        # current month excluded
        latest_in_manifest = m["last_updated"][:7]
        assert all(ym < latest_in_manifest for ym in months), (
            f"{metal_key} monthly_6m includes current month {latest_in_manifest}"
        )
        # each row has cash/3m/days
        for r in rows:
            assert "cash" in r and "3m" in r and "days" in r
            assert r["days"] > 0


def test_antimony_series_has_rotterdam_column():
    """Sb series must include rotterdam (FE now defaults to it)."""
    t = pq.read_table(DATA / "series" / "antimony" / "latest.parquet")
    assert "rotterdam" in t.column_names
