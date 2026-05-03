from builder.build import build_metal_timeseries, build_index, resolve_rate, split_by_year, write_metal_files


DAILY_SAMPLE = {
    "date": "2026-05-01",
    "metals": {
        "copper": {
            "lme": {
                "cash": {"prev_close": 12942.76, "open": 12968.90, "high": 13041.90, "low": 12875.90, "close": 12896.40, "change": -46.36},
                "3m": {"prev_close": 13017.00, "open": 13047.00, "high": 13120.00, "low": 12954.00, "close": 12974.50, "change": -42.50},
                "bid": -82.10, "ask": -78.10, "open_interest": 265325,
            },
            "settlement": {"cash": 12895.00, "3m": 12967.00, "monthly_avg": {"cash": 12891.38, "3m": 12969.88}, "prev_monthly_avg": {"cash": 12916.40, "3m": 12996.50}, "forwards": {"m1": 12943.14, "m2": 12970.73, "m3": 12987.01}},
            "inventory": {"prev": 399725, "in": 725, "out": 1775, "current": 398675, "change": -1050, "on_warrant": 346250, "cancelled_warrant": 52425, "cw_change": 3550},
            "shfe": {"lme_3m_cny": 88925, "lme_near_cny": 88561, "lme_3m_incl_tax": 100486, "lme_near_incl_tax": 100074, "shfe_3m": 101090, "shfe_settle": 101080, "premium_usd": 147.35},
        },
    },
    "ev_metals": {"cobalt": {"may26": 57761.04}},
    "precious": {"gold": {"spot": 4642.23}},
    "fx": {"cny_usd": 6.8265},
    "market": {"krw_usd": 1471.94},
}


def test_build_metal_timeseries():
    dailies = [DAILY_SAMPLE]
    rates_map = {"2026-05-01": 1365.20}
    result = build_metal_timeseries("copper", dailies, rates_map)
    assert result["metal"] == "copper"
    assert result["symbol"] == "Cu"
    assert len(result["data"]) == 1
    day = result["data"][0]
    assert day["date"] == "2026-05-01"
    assert day["lme"]["cash"]["close"] == 12896.40
    assert day["inventory"]["current"] == 398675
    assert day["krw"]["cash"] == round(12896.40 * 1365.20)
    assert day["krw"]["rate"] == 1365.20
    assert day["krw"]["source"] == "bok"


def test_resolve_rate_bok_priority():
    rate, source = resolve_rate(DAILY_SAMPLE, {"2026-05-01": 1365.20})
    assert rate == 1365.20
    assert source == "bok"


def test_resolve_rate_pdf_fallback():
    rate, source = resolve_rate(DAILY_SAMPLE, {})
    assert rate == 1471.94
    assert source == "pdf"


def test_resolve_rate_none():
    daily = {"date": "2026-05-01", "market": {}}
    rate, source = resolve_rate(daily, {})
    assert rate is None
    assert source is None


def test_build_metal_timeseries_pdf_fallback():
    dailies = [DAILY_SAMPLE]
    result = build_metal_timeseries("copper", dailies, {})
    day = result["data"][0]
    assert day["krw"]["rate"] == 1471.94
    assert day["krw"]["source"] == "pdf"
    assert day["krw"]["cash"] == round(12896.40 * 1471.94)


def test_build_index():
    dates = ["2026-01-02", "2026-05-01"]
    years_per_metal = {"copper": [2026], "aluminum": [2026]}
    result = build_index(dates, years_per_metal)
    assert result["last_updated"] == "2026-05-01"
    assert result["total_days"] == 2
    assert result["date_range"]["from"] == "2026-01-02"
    assert result["date_range"]["to"] == "2026-05-01"
    assert result["years"] == [2026]
    assert result["years_per_metal"]["copper"] == [2026]
    assert "metal_info" in result


def test_split_by_year():
    entries = [
        {"date": "2026-05-01", "lme": {}},
        {"date": "2025-12-30", "lme": {}},
        {"date": "2025-01-02", "lme": {}},
        {"date": "2024-06-15", "lme": {}},
    ]
    by_year = split_by_year(entries)
    assert set(by_year.keys()) == {2024, 2025, 2026}
    assert len(by_year[2025]) == 2
    assert len(by_year[2026]) == 1


def test_write_metal_files(tmp_path):
    entries = [
        {"date": "2026-05-01", "lme": {"3m": {"close": 12974.5}}},
        {"date": "2025-12-30", "lme": {"3m": {"close": 12000}}},
    ]
    years = write_metal_files("copper", entries, tmp_path)
    assert years == [2026, 2025]
    assert (tmp_path / "copper" / "latest.json").exists()
    assert (tmp_path / "copper" / "2026.json").exists()
    assert (tmp_path / "copper" / "2025.json").exists()

    import json as _json
    latest = _json.loads((tmp_path / "copper" / "latest.json").read_text())
    assert latest["metal"] == "copper"
    assert latest["symbol"] == "Cu"
    assert latest["window_days"] == 90
    assert len(latest["data"]) == 2
    assert latest["data"][0]["date"] == "2026-05-01"

    y2026 = _json.loads((tmp_path / "copper" / "2026.json").read_text())
    assert y2026["year"] == 2026
    assert len(y2026["data"]) == 1
