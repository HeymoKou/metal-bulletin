"""Keyword-based 1차 필터.

LLM 호출 비용 줄이려고 명백히 무관한 헤드라인 제거.
6 metals 영문/한국어 키워드 ANY-HIT 시 통과.
"""
from __future__ import annotations

from parser.news.models import RawNewsItem

METAL_KEYWORDS: dict[str, list[str]] = {
    "copper":   ["copper", "cu ", "전기동", "구리"],
    "aluminum": ["aluminum", "aluminium", "알루미늄"],
    "zinc":     ["zinc", "아연"],
    "nickel":   ["nickel", "니켈"],
    "lead":     ["lead", "납"],
    "tin":      ["tin", "주석"],
}

LME_GLOBAL_KEYWORDS = ["lme ", "london metal exchange", "shfe", "비철"]


def classify_metals(item: RawNewsItem) -> list[str]:
    """Return matched metal codes. Empty if no match. 'all' if only LME-global hit."""
    haystack = (item.title + " " + (item.snippet or "")).lower()
    matched: list[str] = []
    for metal, kws in METAL_KEYWORDS.items():
        if any(kw in haystack for kw in kws):
            matched.append(metal)

    if not matched and any(kw in haystack for kw in LME_GLOBAL_KEYWORDS):
        matched.append("all")
    return matched


def is_relevant(item: RawNewsItem) -> bool:
    return len(classify_metals(item)) > 0
