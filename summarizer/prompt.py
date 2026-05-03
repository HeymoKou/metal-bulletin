"""LLM prompt builder + response parser."""
from __future__ import annotations

import json
import logging

from parser.news.models import EnrichedNewsItem, RawNewsItem

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """\
당신은 비철금속 시장 뉴스 분석가다. 주어진 뉴스 헤드라인 배열을 분석해
각 항목에 대해 JSON 객체를 반환하라. 출력은 JSON 배열만 포함하고 다른 설명 금지.

각 객체:
- id: 입력의 id 그대로 복사
- summary_ko: 한국어 1문장 요약 (50자 이내)
- metals: ["copper","aluminum","zinc","nickel","lead","tin"] 중 영향받는 광물 (없으면 [])
- sentiment: -1 (가격 하락 압력), 0 (중립), 1 (가격 상승 압력)
- event_type: "supply" | "demand" | "policy" | "macro" | "other"
- confidence: 0.0~1.0 (분석 확신도)
"""


def build_batch_prompt(items: list[RawNewsItem]) -> str:
    payload = [
        {
            "id": item.url_hash,
            "title": item.title,
            "snippet": (item.snippet or "")[:300],
            "lang": item.lang,
        }
        for item in items
    ]
    return (
        SYSTEM_INSTRUCTION
        + "\n\n다음 뉴스 배열을 분석하라:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nJSON 배열만 출력:"
    )


def parse_batch_response(items: list[RawNewsItem], raw_response: str) -> list[EnrichedNewsItem]:
    """Parse LLM response. Missing items → enriched with null summary fields."""
    enrichments: dict[str, dict] = {}
    try:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            for entry in parsed:
                eid = entry.get("id")
                if eid:
                    enrichments[eid] = entry
    except (json.JSONDecodeError, ValueError, IndexError) as e:
        logger.warning("LLM response parse failed: %s", e)

    out: list[EnrichedNewsItem] = []
    for item in items:
        e = enrichments.get(item.url_hash)
        if e:
            out.append(EnrichedNewsItem(
                **item.model_dump(exclude={"url_hash"}),
                summary_ko=e.get("summary_ko"),
                metals=e.get("metals", []),
                sentiment=e.get("sentiment"),
                event_type=e.get("event_type"),
                confidence=e.get("confidence"),
            ))
        else:
            out.append(EnrichedNewsItem(**item.model_dump(exclude={"url_hash"})))
    return out
