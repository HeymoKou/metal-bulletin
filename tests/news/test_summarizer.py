"""Summarizer tests — Gemini provider + prompt builder + failover client."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from parser.news.models import EnrichedNewsItem, RawNewsItem
from summarizer.prompt import build_batch_prompt, parse_batch_response
from summarizer.providers.gemini import GeminiProvider


def _raw(title: str = "Copper hits 5y high", url: str = "https://e.com/1") -> RawNewsItem:
    return RawNewsItem(
        source="s", url=url, title=title,
        fetched_at=datetime.now(timezone.utc), lang="en",
    )


def test_build_batch_prompt_contains_items():
    items = [_raw(title="Copper up"), _raw(title="Nickel down", url="https://e.com/2")]
    prompt = build_batch_prompt(items)
    assert "Copper up" in prompt
    assert "Nickel down" in prompt
    assert "JSON" in prompt or "json" in prompt
    assert items[0].url_hash in prompt


def test_parse_batch_response_valid():
    items = [_raw()]
    raw_response = f'''[
        {{"id": "{items[0].url_hash}", "summary_ko": "구리 5년 고점", "metals": ["copper"], "sentiment": 1, "event_type": "supply", "confidence": 0.9}}
    ]'''
    enriched = parse_batch_response(items, raw_response)
    assert len(enriched) == 1
    assert enriched[0].summary_ko == "구리 5년 고점"
    assert enriched[0].metals == ["copper"]
    assert enriched[0].confidence == 0.9


def test_parse_batch_response_partial_failure_returns_raw():
    items = [_raw(title="A", url="https://e.com/a"), _raw(title="B", url="https://e.com/b")]
    raw_response = f'[{{"id": "{items[0].url_hash}", "summary_ko": "a요약", "metals": ["copper"], "sentiment": 0, "event_type": "other", "confidence": 0.7}}]'
    enriched = parse_batch_response(items, raw_response)
    assert len(enriched) == 2
    assert enriched[0].summary_ko == "a요약"
    assert enriched[1].summary_ko is None


def test_parse_batch_response_invalid_json_returns_all_raw():
    items = [_raw()]
    enriched = parse_batch_response(items, "not json at all")
    assert len(enriched) == 1
    assert enriched[0].summary_ko is None


def test_gemini_provider_calls_sdk(monkeypatch):
    items = [_raw()]
    fake_response = MagicMock()
    fake_response.text = f'[{{"id": "{items[0].url_hash}", "summary_ko": "요약", "metals": ["copper"], "sentiment": 0, "event_type": "other", "confidence": 0.8}}]'
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response
    monkeypatch.setattr("summarizer.providers.gemini.genai.Client", lambda **k: fake_client)

    provider = GeminiProvider(api_key="fake")
    enriched = provider.summarize_batch(items)
    assert len(enriched) == 1
    assert enriched[0].summary_ko == "요약"
    fake_client.models.generate_content.assert_called_once()


def test_gemini_provider_propagates_failure(monkeypatch):
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = RuntimeError("rate limit")
    monkeypatch.setattr("summarizer.providers.gemini.genai.Client", lambda **k: fake_client)

    provider = GeminiProvider(api_key="fake")
    with pytest.raises(RuntimeError):
        provider.summarize_batch([_raw()])
