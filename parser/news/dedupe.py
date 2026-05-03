"""Dedupe: 1) URL hash exact match, 2) title fuzzy match (rapidfuzz)."""
from __future__ import annotations

from rapidfuzz import fuzz

from parser.news.models import RawNewsItem


def dedupe(items: list[RawNewsItem], fuzzy_threshold: float = 0.90) -> list[RawNewsItem]:
    """Return items with duplicates removed.

    First pass: exact url_hash match.
    Second pass: title similarity above threshold (token_set_ratio).
    Preserves first occurrence.
    """
    if not items:
        return []

    seen_hashes: set[str] = set()
    pass1: list[RawNewsItem] = []
    for item in items:
        h = item.url_hash
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        pass1.append(item)

    threshold_pct = fuzzy_threshold * 100
    out: list[RawNewsItem] = []
    seen_titles: list[str] = []
    for item in pass1:
        is_dup = any(
            fuzz.token_set_ratio(item.title, t) > threshold_pct
            for t in seen_titles
        )
        if is_dup:
            continue
        seen_titles.append(item.title)
        out.append(item)

    return out
