from exchange.fetch_krw import parse_bok_response


SAMPLE_RESPONSE = {
    "StatisticSearch": {
        "row": [
            {"TIME": "20260501", "DATA_VALUE": "1365.2"},
            {"TIME": "20260430", "DATA_VALUE": "1370.5"},
            {"TIME": "20260429", "DATA_VALUE": "1368.0"},
        ]
    }
}


def test_parse_bok_response():
    rates = parse_bok_response(SAMPLE_RESPONSE)
    assert len(rates) == 3
    assert rates[0]["date"] == "2026-05-01"
    assert rates[0]["rate"] == 1365.2
    assert rates[2]["date"] == "2026-04-29"


def test_parse_bok_response_empty():
    rates = parse_bok_response({"StatisticSearch": {"row": []}})
    assert rates == []
