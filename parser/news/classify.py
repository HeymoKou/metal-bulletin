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

# Korean ambiguous keyword 제외 패턴 — 동음이의 지명/일반어 false positive 차단.
# "구리시" (경기도 구리시), "구리역", "구리아트홀" 등이 "구리" (copper)로 오분류되는 문제.
METAL_KO_NEG_PATTERNS: dict[str, list[re.Pattern]] = {
    "copper": [
        re.compile(r"구리시(?!장|민|장학|청|기[관][^동])"),  # 구리시 (지명) — 구리시청, 구리시민, 구리시장 포함
        re.compile(r"구리시청|구리시민|구리시장|구리시\s|구리시$|구리시[\.,!?]"),
        re.compile(r"구리역"),
        re.compile(r"구리(?:한강|아트홀|타워|도서관|갈매|시청|시민|시장|시청|로|에서|으로|행)"),
        re.compile(r"경기\s*구리|구리\s*아트홀|구리\s*시민|구리\s*한강"),
    ],
    # 다른 한국어 키워드는 충분히 metal-specific (알루미늄, 아연, 니켈, 주석, 연 시세).
}

# 한국어 매칭 시 추가 metal-context 단서 (있으면 false positive 가능성 ↓).
METAL_KO_CONTEXT = re.compile(
    r"(?:가격|시세|생산|광산|제련|정련|수요|공급|재고|비축|광물|금속|메탈|"
    r"톤|kt|LME|SHFE|선물|현물|인플레|관세|금속|광|제련소|smelter|"
    r"비철|니켈|알루미늄|아연|주석|구리\s*값|copper)",
    re.I,
)

_LME_GLOBAL_REMOVED = True  # noqa: F841 — kept as marker; see classify_metals docstring


def classify_metals(item: RawNewsItem) -> list[str]:
    """Return matched metal codes. Empty if no specific metal hit.

    Bare LME/SHFE/비철 mention WITHOUT a specific metal returns []. Reason:
    'LME announces holiday' or 'SHFE trading halt' have no actionable metal-specific signal,
    and 'all' tagged everything to bypass classify, polluting downstream LLM/storage.

    동음이의 차단: 한국어 ambiguous keyword (e.g. "구리") 매칭 후 negative pattern (구리시 등)이
    걸리면, 영어 metal keyword 또는 metal context 단서가 함께 있을 때만 통과.
    """
    haystack = item.title + " " + (item.snippet or "")
    matched: list[str] = []
    for metal in METAL_PATTERNS:
        en_hit = any(p.search(haystack) for p in METAL_PATTERNS[metal])
        ko_hit = any(kw in haystack for kw in METAL_KO_KEYWORDS[metal])
        if not (en_hit or ko_hit):
            continue

        # Negative pattern check (한국어 ambiguous keyword 만)
        neg_patterns = METAL_KO_NEG_PATTERNS.get(metal, [])
        if neg_patterns and ko_hit and not en_hit:
            neg_hit = any(p.search(haystack) for p in neg_patterns)
            if neg_hit:
                # "전기동" (unambiguous copper) 매칭이면 통과
                unambig_kw = [kw for kw in METAL_KO_KEYWORDS[metal] if kw not in ("구리",)]
                if not any(kw in haystack for kw in unambig_kw):
                    # context 단서도 없으면 false positive로 보고 reject
                    if not METAL_KO_CONTEXT.search(haystack):
                        continue

        matched.append(metal)
    return matched


def is_relevant(item: RawNewsItem) -> bool:
    return len(classify_metals(item)) > 0
