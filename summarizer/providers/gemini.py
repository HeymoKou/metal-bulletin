"""Gemini 2.5 Flash provider."""
from __future__ import annotations

import os

from google import genai

from parser.news.models import EnrichedNewsItem, RawNewsItem
from summarizer.prompt import build_batch_prompt, parse_batch_response

MODEL = "gemini-2.5-flash"


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
        response = client.models.generate_content(model=MODEL, contents=prompt)
        return parse_batch_response(items, response.text)
