METALS_ORDER = ["copper", "aluminum", "zinc", "lead", "nickel", "tin"]


def _num(val: str | None) -> float | None:
    if val is None or val.strip() == "" or val.strip() == "#N/A":
        return None
    return float(val.replace(",", ""))


def _int_num(val: str | None) -> int | None:
    n = _num(val)
    return int(n) if n is not None else None


def parse_lme_prices(table: list[list]) -> dict:
    result = {}
    for metal, cash_row_idx, tm_row_idx in [("copper", 2, 3), ("aluminum", 4, 5)]:
        cash_row = table[cash_row_idx]
        tm_row = table[tm_row_idx]
        result[metal] = {
            "cash": {
                "prev_close": _num(cash_row[1]),
                "open": _num(cash_row[2]),
                "high": _num(cash_row[3]),
                "low": _num(cash_row[4]),
                "close": _num(cash_row[5]),
                "change": _num(cash_row[6]),
            },
            "3m": {
                "prev_close": _num(tm_row[1]),
                "open": _num(tm_row[2]),
                "high": _num(tm_row[3]),
                "low": _num(tm_row[4]),
                "close": _num(tm_row[5]),
                "change": _num(tm_row[6]),
            },
            "bid": _num(tm_row[7]),
            "ask": _num(tm_row[8]),
            "open_interest": _int_num(tm_row[9]),
        }
    for metal, row_idx in [("zinc", 6), ("lead", 7), ("nickel", 8), ("tin", 9)]:
        row = table[row_idx]
        result[metal] = {
            "3m": {
                "prev_close": _num(row[1]),
                "open": _num(row[2]),
                "high": _num(row[3]),
                "low": _num(row[4]),
                "close": _num(row[5]),
                "change": _num(row[6]),
            },
            "bid": _num(row[7]),
            "ask": _num(row[8]),
            "open_interest": _int_num(row[9]),
        }
    return result


def parse_settlement(table: list[list]) -> dict:
    result = {}
    for i, metal in enumerate(METALS_ORDER):
        row = table[i + 2]
        result[metal] = {
            "cash": _num(row[1]),
            "3m": _num(row[2]),
            "monthly_avg": {
                "cash": _num(row[4]),
                "3m": _num(row[5]),
            },
            "prev_monthly_avg": {
                "cash": _num(row[6]),
                "3m": _num(row[7]),
            },
            "forwards": {
                "m1": _num(row[8]),
                "m2": _num(row[9]),
                "m3": _num(row[10]),
            },
        }
    return result


def parse_ev_metals(table: list[list]) -> dict:
    contracts_row = table[3]
    values_row = table[4]
    result = {"cobalt": {}, "lithium": {}}
    for col, metal in [(1, "cobalt"), (2, "cobalt"), (3, "lithium")]:
        contract = contracts_row[col]
        value = _num(values_row[col])
        if contract and value is not None:
            result[metal][contract.lower()] = value
    return result
