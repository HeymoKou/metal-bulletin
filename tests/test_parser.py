from parser.page1 import parse_lme_prices, parse_settlement, parse_ev_metals


SAMPLE_TABLE1 = [
    ['전일 금 일 Cash - 3M 미결제약정(O/I)\n변동폭', None, None, None, None, None, None, None, None, None],
    ['종가', None, '시가 고가(B) 저가(A) 종가(A)', None, None, None, '', 'BID ASK', None, '전일 변동폭'],
    [None, '12,942.76', '12,968.90', '13,041.90', '12,875.90', '12,896.40', '-46.36', '', '', ''],
    [None, '13,017.00', '13,047.00', '13,120.00', '12,954.00', '12,974.50', '-42.50', '-82.10', '-78.10', '265,325'],
    [None, '3,540.17', '3,548.31', '3,599.81', '3,547.81', '3,577.81', '37.64', '', '', ''],
    [None, '3,482.00', '3,482.50', '3,534.00', '3,482.00', '3,512.00', '30.00', '61.81', '65.81', '676,743'],
    [None, '3,358.00', '3,368.00', '3,395.00', '3,331.50', '3,338.00', '-20.00', '-9.86', '-7.86', '232,402'],
    [None, '1,952.50', '1,958.00', '1,963.00', '1,943.50', '1,950.50', '-2.00', '-7.05', '-5.05', '175,151'],
    [None, '19,355.00', '19,455.00', '19,645.00', '19,260.00', '19,345.00', '-10.00', '-187.87', '-177.87', '253,610'],
    [None, '49,005.00', '49,005.00', '49,645.00', '49,005.00', '49,620.00', '615.00', '-164.00', '-154.00', '20,837'],
]

SAMPLE_TABLE2 = [
    ['금 일 당월평균 전월평균', None, None, None, None, None, 'LME 정산가 (LONDON 17시00분)', None, None, None, None],
    ['', 'Cash 3M', None, 'Cash', 'Cash 3M', None, 'Cash 3M May Jun Jul', None, None, None, None],
    [None, '12895.00', '12967.00', '12895.00', '12891.38', '12969.88', '12916.40', '12996.50', '12943.14', '12970.73', '12987.01'],
    [None, '3584.00', '3523.00', '3584.00', '3600.63', '3545.73', '3585.81', '3522.00', '3590.91', '3562.08', '3540.84'],
    [None, '3349.00', '3343.00', '3349.00', '3361.55', '3368.83', '3335.64', '3344.50', '3346.13', '3353.55', '3352.11'],
    [None, '1945.00', '1956.00', '1945.00', '1922.65', '1946.15', '1942.95', '1949.00', '1952.39', '1951.12', '1948.08'],
    [None, '19180.00', '19385.00', '19180.00', '18005.75', '18193.25', '19182.13', '19365.00', '19216.38', '19282.38', '19348.00'],
    [None, '49200.00', '49350.00', '49200.00', '48941.75', '49092.50', '49264.00', '49423.00', '49319.00', '49359.00', '49422.00'],
]

SAMPLE_TABLE3 = [
    ['EV Metals', None, None, None, None, None, None, None, None, None, None],
    ['품목', '코발트 (CME Fastmarket MB)', None, '리튬 (CME Fastmarket MB)', None, None, '', None, None, None, None],
    [None, '2026-05-01', '2026-05-01', '2026-05-01', '2026-05-01', '', '', '', '', '', ''],
    [None, 'May26', 'Jul26', 'May26', None, None, None, None, None, None, None],
    [None, '57761.04', '59634.97', '45966.33', None, None, None, None, None, None, None],
    [None, '-154.32', '595.25', '771.62', None, None, None, None, None, None, None],
    [None, '-0.27%', '1.00%', '1.68%', None, None, None, None, None, None, None],
    [None, '', '', '', None, None, None, None, None, None, None],
]


def test_parse_lme_prices_copper():
    result = parse_lme_prices(SAMPLE_TABLE1)
    cu = result["copper"]
    assert cu["cash"]["prev_close"] == 12942.76
    assert cu["cash"]["close"] == 12896.40
    assert cu["cash"]["change"] == -46.36
    assert cu["3m"]["open"] == 13047.00
    assert cu["3m"]["high"] == 13120.00
    assert cu["3m"]["low"] == 12954.00
    assert cu["3m"]["close"] == 12974.50
    assert cu["3m"]["change"] == -42.50
    assert cu["bid"] == -82.10
    assert cu["ask"] == -78.10
    assert cu["open_interest"] == 265325


def test_parse_lme_prices_zinc():
    result = parse_lme_prices(SAMPLE_TABLE1)
    zn = result["zinc"]
    assert zn["3m"]["prev_close"] == 3358.00
    assert zn["3m"]["open"] == 3368.00
    assert zn["3m"]["close"] == 3338.00
    assert zn["bid"] == -9.86
    assert zn["open_interest"] == 232402


def test_parse_lme_prices_all_metals_present():
    result = parse_lme_prices(SAMPLE_TABLE1)
    assert set(result.keys()) == {"copper", "aluminum", "zinc", "lead", "nickel", "tin"}


def test_parse_settlement():
    result = parse_settlement(SAMPLE_TABLE2)
    cu = result["copper"]
    assert cu["cash"] == 12895.00
    assert cu["3m"] == 12967.00
    assert cu["monthly_avg"]["cash"] == 12891.38
    assert cu["monthly_avg"]["3m"] == 12969.88
    assert cu["prev_monthly_avg"]["cash"] == 12916.40
    assert cu["prev_monthly_avg"]["3m"] == 12996.50
    assert len(cu["forwards"]) == 3


def test_parse_ev_metals():
    result = parse_ev_metals(SAMPLE_TABLE3)
    assert result["cobalt"]["may26"] == 57761.04
    assert result["cobalt"]["jul26"] == 59634.97
    assert result["lithium"]["may26"] == 45966.33
