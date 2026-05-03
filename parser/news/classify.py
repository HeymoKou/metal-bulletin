"""Keyword-based 1차 필터.

LLM 호출 비용 줄이려고 명백히 무관한 헤드라인 제거.
6 metals 영문/한국어 키워드 word-boundary 매칭 시 통과.

Word boundary regex로 "lead time", "tin-foil hat" 같은 false positive 회피.
한국어는 단어 경계가 없으므로 substring 사용.
"""
from __future__ import annotations

import re

from parser.news.models import RawNewsItem

# 영문은 word-boundary regex (false positive 회피).
# 한국어는 substring (어절 경계 미정형).
METAL_PATTERNS: dict[str, list[re.Pattern]] = {
    "copper":   [re.compile(r"\bcoppers?\b", re.I)],
    "aluminum": [re.compile(r"\b(?:aluminium|aluminum)\b", re.I), re.compile(r"\balumina\b", re.I)],
    "zinc":     [re.compile(r"\bzincs?\b", re.I)],
    "nickel":   [re.compile(r"\bnickels?\b", re.I)],
    "lead":     [re.compile(r"\blead\s+(?:price|production|smelter|metal|mine|ore|concentrate|ingot|stock|stocks|inventories)\b", re.I), re.compile(r"\b(?:lme|shfe)\s+lead\b", re.I)],
    "tin":      [re.compile(r"\btin\s+(?:price|production|smelter|metal|mine|ore|concentrate|ingot|stock|stocks|inventories|market)\b", re.I), re.compile(r"\b(?:lme|shfe)\s+tin\b", re.I)],
}

METAL_KO_KEYWORDS: dict[str, list[str]] = {
    "copper":   ["전기동", "구리"],
    "aluminum": ["알루미늄"],
    "zinc":     ["아연"],
    "nickel":   ["니켈"],
    "lead":     ["연 시세", "연괴", "연 가격", "연 생산"],
    "tin":      ["주석"],
}

LME_GLOBAL_PATTERNS = [
    re.compile(r"\blme\b", re.I),
    re.compile(r"\blondon metal exchange\b", re.I),
    re.compile(r"\bshfe\b", re.I),
]
LME_GLOBAL_KO = ["비철", "비철금속"]


def classify_metals(item: RawNewsItem) -> list[str]:
    """Return matched metal codes. Empty if no match. 'all' if only LME-global hit."""
    haystack = item.title + " " + (item.snippet or "")
    matched: list[str] = []
    for metal in METAL_PATTERNS:
        en_hit = any(p.search(haystack) for p in METAL_PATTERNS[metal])
        ko_hit = any(kw in haystack for kw in METAL_KO_KEYWORDS[metal])
        if en_hit or ko_hit:
            matched.append(metal)

    if not matched:
        lme_en = any(p.search(haystack) for p in LME_GLOBAL_PATTERNS)
        lme_ko = any(kw in haystack for kw in LME_GLOBAL_KO)
        if lme_en or lme_ko:
            matched.append("all")
    return matched


def is_relevant(item: RawNewsItem) -> bool:
    return len(classify_metals(item)) > 0
