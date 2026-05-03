"""Gemini 2.5 Flash provider with structured JSON output (response_schema enforced).

Codex MED fix: response_json_schema constrains output shape — eliminates batch-level
JSON parse failures from prompt injection or model drift. Per-item enrichment may still
be null (model can output null fields), but the array-of-objects shape is guaranteed.
"""
from __future__ import annotations

import os

from google import genai
from google.genai import types

from parser.news.models import EnrichedNewsItem, RawNewsItem
from summarizer.prompt import build_batch_prompt, parse_batch_response

MODEL = "gemini-2.5-flash"

# JSON schema for structured output. Single object with results[] — Gemini doesn't
# accept top-level array, must wrap. parse_batch_response unwraps.
RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "summary_ko": {"type": "string"},
                    "metals": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["copper", "aluminum", "zinc", "nickel", "lead", "tin"],
                        },
                    },
                    "sentiment": {"type": "integer", "minimum": -1, "maximum": 1},
                    "event_type": {
                        "type": "string",
                        "enum": ["supply", "demand", "policy", "macro", "other"],
                    },
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                },
                "required": ["id", "summary_ko", "metals", "sentiment", "event_type", "confidence"],
            },
        },
    },
    "required": ["results"],
}


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

    def summarize_batch(self, items: list[RawNewsItem]) -> list[EnrichedNewsItem]:
        if not items:
            return []
        client = genai.Client(api_key=self.api_key)
        prompt = build_batch_prompt(items)
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=RESPONSE_SCHEMA,
            ),
        )
        return parse_batch_response(items, response.text)
