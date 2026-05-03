from parser.page1 import _num

PRECIOUS_ORDER = ["gold", "silver", "platinum", "palladium"]


def parse_precious_metals(table: list[list]) -> dict:
    result = {}
    for i, metal in enumerate(PRECIOUS_ORDER):
        row = table[i + 3]
        entry = {
            "spot": _num(row[1]),
            "high": _num(row[2]),
            "low": _num(row[3]),
        }
        am = _num(row[4])
        pm = _num(row[5]) if len(row) > 5 else None
        if am is not None:
            entry["am_fix"] = am
        if pm is not None:
            entry["pm_fix"] = pm
        result[metal] = entry
    return result
