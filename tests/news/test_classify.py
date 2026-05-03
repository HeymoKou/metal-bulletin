"""Keyword-based pre-filter for metal relevance."""
from datetime import datetime, timezone
from parser.news.classify import classify_metals, is_relevant
from parser.news.models import RawNewsItem


def _item(title: str, snippet: str | None = None, lang: str = "en") -> RawNewsItem:
    return RawNewsItem(
        source="s", url=f"https://e.com/{title[:5]}", title=title,
        snippet=snippet, fetched_at=datetime.now(timezone.utc), lang=lang,
    )


def test_classify_copper_en():
    metals = classify_metals(_item("Copper prices surge"))
    assert metals == ["copper"]


def test_classify_copper_ko():
    metals = classify_metals(_item("전기동 가격 급등"))
    assert metals == ["copper"]


def test_classify_multiple_metals():
    metals = classify_metals(_item("Copper and nickel both up", "Aluminum flat"))
    assert set(metals) == {"copper", "nickel", "aluminum"}


def test_classify_no_match():
    metals = classify_metals(_item("Stock market hits new high"))
    assert metals == []


def test_is_relevant_true_when_metal_match():
    assert is_relevant(_item("Tin smelter shutdown")) is True


def test_is_relevant_false_when_no_match():
    assert is_relevant(_item("Bitcoin reaches $200k")) is False


def test_classify_handles_none_snippet():
    metals = classify_metals(_item("Zinc imports rise", snippet=None))
    assert metals == ["zinc"]


def test_lme_only_no_metal_returns_empty():
    """Codex review: bare LME/SHFE 단독 언급은 false positive 양산 → 빈 리스트.
    Metal-specific 언급 있을 때만 matched."""
    metals = classify_metals(_item("LME warehouse stocks at record low"))
    assert metals == []
    metals = classify_metals(_item("LME copper stocks at record low"))
    assert metals == ["copper"]
