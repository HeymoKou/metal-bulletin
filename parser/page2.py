from parser.page1 import _num, _int_num, METALS_ORDER


def parse_inventory(table: list[list]) -> dict:
    result = {}
    for i, metal in enumerate(METALS_ORDER):
        row = table[i + 1]
        result[metal] = {
            "prev": _int_num(row[1]),
            "in": _int_num(row[2]),
            "out": _int_num(row[3]),
            "current": _int_num(row[4]),
            "change": _int_num(row[5]),
            "on_warrant": _int_num(row[6]),
            "cancelled_warrant": _int_num(row[7]),
            "cw_change": _int_num(row[8]),
        }
    return result


def parse_shfe_spread(table: list[list]) -> dict:
    cny_usd = _num(table[1][1])
    metals = {}
    for i, metal in enumerate(METALS_ORDER):
        row = table[i + 1]
        metals[metal] = {
            "lme_3m_cny": _int_num(row[2]),
            "lme_near_cny": _int_num(row[3]),
            "lme_3m_incl_tax": _int_num(row[5]),
            "lme_near_incl_tax": _int_num(row[6]),
            "shfe_3m": _int_num(row[7]),
            "shfe_settle": _int_num(row[8]),
            "premium_usd": _num(row[9]),
        }
    return {"cny_usd": cny_usd, "metals": metals}


def parse_market_factors(table: list[list]) -> dict:
    values = table[0]
    changes = table[1]
    return {
        "sp500": _num(values[0]),
        "dow": _num(values[1]),
        "wti": _num(values[3]),
        "krw_usd": _num(values[4]),
        "eur_usd": _num(values[5]),
        "jpy_usd": _num(values[6]),
        "sp500_change": _num(changes[0]),
        "dow_change": _num(changes[1]),
        "wti_change": _num(changes[3]),
        "krw_change": _num(changes[4]),
    }
