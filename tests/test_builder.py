import json

import pyarrow.parquet as pq

from builder.build import (
    build_manifest,
    flatten_metal_row,
    resolve_rate,
    rows_to_table,
    METAL_SCHEMA,
    write_exchange,
    write_metal_series,
)


DAILY_SAMPLE = {
    "date": "2026-05-01",
    "metals": {
        "copper": {
            "lme": {
                "cash": {"prev_close": 12942.76, "open": 12968.90, "high": 13041.90, "low": 12875.90, "close": 12896.40, "change": -46.36},
                "3m": {"prev_close": 13017.00, "open": 13047.00, "high": 13120.00, "low": 12954.00, "close": 12974.50, "change": -42.50},
                "bid": -82.10, "ask": -78.10, "open_interest": 265325,
            },
            "settlement": {
                "cash": 12895.00, "3m": 12967.00,
                "monthly_avg": {"cash": 12891.38, "3m": 12969.88},
                "prev_monthly_avg": {"cash": 12916.40, "3m": 12996.50},
                "forwards": {"m1": 12943.14, "m2": 12970.73, "m3": 12987.01},
            },
            "inventory": {"prev": 399725, "in": 725, "out": 1775, "current": 398675, "change": -1050, "on_warrant": 346250, "cancelled_warrant": 52425, "cw_change": 3550},
            "shfe": {"lme_3m_cny": 88925, "lme_near_cny": 88561, "lme_3m_incl_tax": 100486, "lme_near_incl_tax": 100074, "shfe_3m": 101090, "shfe_settle": 101080, "premium_usd": 147.35},
        },
    },
    "market": {"krw_usd": 1471.94},
}


def test_resolve_rate_bok_priority():
    rate, source = resolve_rate(DAILY_SAMPLE, {"2026-05-01": 1365.20})
    assert rate == 1365.20
    assert source == "bok"


def test_resolve_rate_pdf_fallback():
    rate, source = resolve_rate(DAILY_SAMPLE, {})
    assert rate == 1471.94
    assert source == "pdf"


def test_resolve_rate_none():
    rate, source = resolve_rate({"date": "2026-05-01", "market": {}}, {})
    assert rate is None
    assert source is None


def test_flatten_metal_row_copper():
    row = flatten_metal_row(DAILY_SAMPLE, "copper", 1365.20, "bok")
    assert row["date"] == "2026-05-01"
    assert row["lme_cash_close"] == 12896.40
    assert row["lme_3m_close"] == 12974.50
    assert row["lme_oi"] == 265325
    assert row["sett_fwd_m1"] == 12943.14
    assert row["inv_current"] == 398675
    assert row["shfe_premium_usd"] == 147.35
    assert row["krw_3m"] == round(12974.50 * 1365.20)
    assert row["krw_rate"] == 1365.20
    assert row["krw_source"] == "bok"


def test_flatten_metal_row_missing_metal():
    assert flatten_metal_row(DAILY_SAMPLE, "tin", 1300, "bok") is None


def test_flatten_metal_row_no_rate():
    row = flatten_metal_row(DAILY_SAMPLE, "copper", None, None)
    assert row["krw_cash"] is None
    assert row["krw_3m"] is None
    assert row["krw_source"] is None


def test_rows_to_table_handles_none():
    rows = [flatten_metal_row(DAILY_SAMPLE, "copper", 1365.20, "bok")]
    table = rows_to_table(rows, METAL_SCHEMA)
    assert table.num_rows == 1
    assert "lme_3m_close" in table.column_names


def test_write_metal_series_creates_files(tmp_path):
    rows = [
        flatten_metal_row({**DAILY_SAMPLE, "date": "2026-05-01"}, "copper", 1365.20, "bok"),
        flatten_metal_row({**DAILY_SAMPLE, "date": "2025-12-30"}, "copper", 1370.0, "bok"),
    ]
    years = write_metal_series("copper", rows, tmp_path)
    assert years == [2026, 2025]
    assert (tmp_path / "copper" / "latest.parquet").exists()
    assert (tmp_path / "copper" / "2026.parquet").exists()
    assert (tmp_path / "copper" / "2025.parquet").exists()

    table = pq.read_table(tmp_path / "copper" / "2026.parquet")
    assert table.num_rows == 1
    assert table.column("date").to_pylist() == ["2026-05-01"]


def test_write_exchange(tmp_path):
    rates = {"2026-05-01": 1365.20, "2026-04-30": 1370.5}
    write_exchange(rates, tmp_path / "exchange.parquet")
    assert (tmp_path / "exchange.parquet").exists()
    table = pq.read_table(tmp_path / "exchange.parquet")
    assert table.num_rows == 2
    assert table.column("date").to_pylist() == ["2026-04-30", "2026-05-01"]


def test_build_manifest():
    dailies = [{"date": "2026-01-02"}, {"date": "2026-05-01"}]
    years_per_metal = {"copper": [2026], "aluminum": [2026]}
    m = build_manifest(dailies, years_per_metal)
    assert m["schema"] == 1
    assert m["format"] == "parquet"
    assert m["compression"] == "zstd"
    assert m["last_updated"] == "2026-05-01"
    assert m["total_days"] == 2
    assert m["years"] == [2026]
    assert m["metals"]["copper"]["symbol"] == "Cu"
    assert m["metals"]["copper"]["years"] == [2026]
    assert m["latest_window"] == 90
