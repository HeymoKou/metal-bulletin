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


# --- 한국어 동음이의 false positive 차단 ---

def test_guri_city_festival_not_copper():
    """구리시 축제 뉴스가 copper로 분류되면 안 됨 (지명 동음이의)."""
    metals = classify_metals(_item("구리시 한강시민공원 축제 개막", "구리시민 환영"))
    assert "copper" not in metals


def test_guri_station_not_copper():
    metals = classify_metals(_item("구리역 인근 교통체증", "출퇴근 혼잡"))
    assert metals == []


def test_copper_korean_unambiguous_passes():
    """전기동 (unambiguous) 키워드는 negative 패턴 무관하게 통과."""
    metals = classify_metals(_item("전기동 가격 사상 최고", "LME 시세 급등"))
    assert "copper" in metals


def test_copper_korean_with_context_passes():
    """'구리' + metal context (가격/시세/생산 등)는 통과."""
    metals = classify_metals(_item("구리 가격 급등 LME", "구리 광산 파업"))
    assert "copper" in metals


def test_copper_english_overrides_neg():
    """영어 'copper' 매칭이면 한국어 negative 무시 (영어가 명확한 신호)."""
    metals = classify_metals(_item("Copper market update", "구리시 행사 무관"))
    assert "copper" in metals


def test_pps_source_bypasses_keyword_filter():
    from datetime import datetime, timezone

    item = RawNewsItem(
        source="pps",
        url="https://www.pps.go.kr/common/fileDown.do?key=X&sn=1",
        title="주간 경제·비철금속 시장동향(26.5.6)",
        snippet=None,
        fetched_at=datetime.now(timezone.utc),
        lang="ko",
    )
    assert is_relevant(item) is True
