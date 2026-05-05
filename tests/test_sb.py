"""Tests for antimony (Sb) scraper + builder."""
from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from scraper.sb import REGIONS, parse, to_usd_per_mt
from builder.sb_build import (
    REGION_KEYS,
    load_existing,
    merge,
    rows_from_scrape,
    write_series,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sb_scrapmonster.html"


def test_unit_conversion():
    assert to_usd_per_mt(1.0, "$US/MT") == 1.0
    assert to_usd_per_mt(1.0, "$US/Kg") == 1000.0
    assert abs(to_usd_per_mt(1.0, "$US/Lb") - 2204.62262) < 1e-3


def test_parse_fixture_all_regions():
    html = FIXTURE.read_text()
    rows = parse(html)
    assert rows, "no rows parsed"
    regions = {r.region for r in rows}
    assert regions == set(REGIONS.values())
    # Each region should have 7 rows in static HTML
    for region in REGIONS.values():
        n = sum(1 for r in rows if r.region == region)
        assert n == 7, f"{region}: expected 7 rows, got {n}"


def test_parse_normalizes_units():
    html = FIXTURE.read_text()
    rows = parse(html)
    # Find a Port India row ($US/Kg) and verify normalization
    india = next(r for r in rows if r.region == "port_india")
    assert india.unit == "$US/Kg"
    assert abs(india.usd_per_mt - india.price * 1000.0) < 0.01
    # Baltimore row ($US/Lb)
    balt = next(r for r in rows if r.region == "baltimore")
    assert balt.unit == "$US/Lb"
    assert abs(balt.usd_per_mt - balt.price * 2204.62262) < 0.1


def test_rows_from_scrape_groups_by_date():
    html = FIXTURE.read_text()
    prices = parse(html)
    grouped = rows_from_scrape(prices)
    # Same date across regions → one row with multiple region values
    assert "2026-03-24" in grouped
    row = grouped["2026-03-24"]
    assert all(k in row for k in REGION_KEYS)
    assert row["fob_china"] is not None
    assert row["_source"] == "scrapmonster"


def test_merge_idempotent(tmp_path: Path):
    html = FIXTURE.read_text()
    prices = parse(html)
    scraped = rows_from_scrape(prices)

    metal_dir = tmp_path / "antimony"
    existing = load_existing(metal_dir)
    merged, new = merge(existing, scraped)
    assert len(new) == len(scraped)
    write_series(merged, metal_dir)

    # Second run with same data
    existing2 = load_existing(metal_dir)
    merged2, new2 = merge(existing2, scraped)
    assert new2 == [], "second run should add no new dates"
    assert len(merged2) == len(merged)


def test_merge_upserts_new_region_value(tmp_path: Path):
    metal_dir = tmp_path / "antimony"
    metal_dir.mkdir(parents=True)

    # Seed: one date, only fob_china set
    seed = {
        "2026-03-24": {
            "date": "2026-03-24",
            "exw_china": None, "fob_china": 30000.0, "port_india": None,
            "rotterdam": None, "baltimore": None, "_source": "scrapmonster",
        }
    }
    write_series(seed, metal_dir)

    # Scrape later adds rotterdam value for same date
    new_scrape = {
        "2026-03-24": {
            "date": "2026-03-24",
            "exw_china": None, "fob_china": None, "port_india": None,
            "rotterdam": 25000.0, "baltimore": None, "_source": "scrapmonster",
        }
    }
    existing = load_existing(metal_dir)
    merged, new = merge(existing, new_scrape)
    assert new == []  # date already existed
    assert merged["2026-03-24"]["fob_china"] == 30000.0  # preserved
    assert merged["2026-03-24"]["rotterdam"] == 25000.0  # upserted


def test_write_series_creates_year_files(tmp_path: Path):
    html = FIXTURE.read_text()
    scraped = rows_from_scrape(parse(html))
    metal_dir = tmp_path / "antimony"
    years = write_series(scraped, metal_dir)
    assert years  # at least one
    assert (metal_dir / "latest.parquet").exists()
    for y in years:
        f = metal_dir / f"{y}.parquet"
        assert f.exists()
        t = pq.read_table(f)
        assert "date" in t.column_names
        assert "fob_china" in t.column_names
        assert "_source" in t.column_names
