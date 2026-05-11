from parser.page1 import parse_lme_prices, parse_settlement, parse_ev_metals
from parser.page2 import parse_inventory, parse_shfe_spread, parse_market_factors


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
    assert cu["lme_settle"]["cash"] == 12916.40
    assert cu["lme_settle"]["3m"] == 12996.50
    assert cu["prev_monthly_avg"]["cash"] == 12891.38
    assert cu["prev_monthly_avg"]["3m"] == 12969.88
    assert len(cu["forwards"]) == 3


def test_parse_ev_metals():
    result = parse_ev_metals(SAMPLE_TABLE3)
    assert result["cobalt"]["may26"] == 57761.04
    assert result["cobalt"]["jul26"] == 59634.97
    assert result["lithium"]["may26"] == 45966.33


SAMPLE_INVENTORY = [
    ['전일 반입 반출 금일 ON CANCELLED CW\n변동폭\n최종재고 (IN) (OUT) 최종재고 WRNT WRNT 변동폭', None, None, None, None, None, None, None, None],
    [None, '399725', '725', '1775', '398675', '-1050', '346250', '52425', '3550'],
    [None, '367050', '0', '2325', '364725', '-2325', '332600', '32125', '-2325'],
    [None, '98650', '0', '2400', '96250', '-2400', '86000', '10250', '-1825'],
    [None, '269575', '0', '1075', '268500', '-1075', '262825', '5675', '-1075'],
    [None, '277398', '0', '1002', '276396', '-1002', '262758', '13638', '-1002'],
    [None, '8590', '20', '135', '8475', '-115', '7940', '535', '65'],
]

SAMPLE_SHFE_SPREAD = [
    ['LME 3M LME 최근월물 ...header...', None, None, None, None, None, None, None, None, None],
    [None, '6.8265', '88,925', '88,561', '13%', '100,486', '100,074', '101,090', '101,080', '147.35'],
    [None, '6.8265', '23,961', '24,431', '13%', '27,076', '27,608', '24,485', '24,440', '-464.00'],
    [None, '6.8265', '23,138', '23,150', '13%', '26,146', '26,159', '23,700', '23,645', '-368.27'],
    [None, '6.8265', '13,291', '13,314', '13%', '15,019', '15,045', '16,675', '16,645', '234.35'],
    [None, '6.8265', '133,868', '132,853', '13%', '151,270', '150,124', '149,920', '149,430', '-101.66'],
    ['SN', '6.8265', '335,864', '335,154', '13%', '379,526', '378,724', '384,190', '383,270', '665.96'],
    ['Market Factors', None, None, None, None, None, None, None, None, None],
]

SAMPLE_MARKET_FACTORS = [
    ['7240.58', '49626.53', '110 22/32', '101.46', '1471.94', '1.1741', '156.9200', '0.7213', '16.6239'],
    ['31.57', '-25.61', '3/32', '-3.61', '-5.63', '0.0010', '0.40', '0.00', '-0.08'],
    ['0.44%', '-0.05%', '0.07%', '-3.44%', '-0.38%', '0.09%', '0.25%', '0.37%', '-0.49%'],
]


def test_parse_inventory_copper():
    result = parse_inventory(SAMPLE_INVENTORY)
    cu = result["copper"]
    assert cu["prev"] == 399725
    assert cu["in"] == 725
    assert cu["out"] == 1775
    assert cu["current"] == 398675
    assert cu["change"] == -1050
    assert cu["on_warrant"] == 346250
    assert cu["cancelled_warrant"] == 52425
    assert cu["cw_change"] == 3550


def test_parse_inventory_all_metals():
    result = parse_inventory(SAMPLE_INVENTORY)
    assert set(result.keys()) == {"copper", "aluminum", "zinc", "lead", "nickel", "tin"}


def test_parse_shfe_spread():
    result = parse_shfe_spread(SAMPLE_SHFE_SPREAD)
    assert result["cny_usd"] == 6.8265
    cu = result["metals"]["copper"]
    assert cu["shfe_settle"] == 101080
    assert cu["premium_usd"] == 147.35
    sn = result["metals"]["tin"]
    assert sn["premium_usd"] == 665.96


def test_parse_market_factors():
    result = parse_market_factors(SAMPLE_MARKET_FACTORS)
    assert result["krw_usd"] == 1471.94
    assert result["sp500"] == 7240.58


from parser.page3 import parse_precious_metals


SAMPLE_PRECIOUS = [
    ['SPOT LBMA / LPPM', None, None, None, None, None],
    ['', '현재가\n고가 저가', None, None, 'Price(구 London Fix)', None],
    ['', '(ASK)', None, None, 'AM PM', None],
    [None, '4642.23', '4660.07', '4560.40', '', None],
    [None, '76.180', '76.948', '73.018', '', None],
    [None, '2009.15', '2016.85', '1961.05', '1963.00', '1990.00'],
    [None, '1542.95', '1557.88', '1513.33', '1515.00', '1529.00'],
]


def test_parse_precious_metals():
    result = parse_precious_metals(SAMPLE_PRECIOUS)
    assert result["gold"]["spot"] == 4642.23
    assert result["gold"]["high"] == 4660.07
    assert result["gold"]["low"] == 4560.40
    assert result["silver"]["spot"] == 76.180
    assert result["platinum"]["spot"] == 2009.15
    assert result["platinum"]["am_fix"] == 1963.00
    assert result["palladium"]["pm_fix"] == 1529.00
