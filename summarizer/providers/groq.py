"""Groq provider — Llama 3.3 70B via Groq Cloud (free tier: 30 req/min)."""
from __future__ import annotations

import json
import logging
import os
import time

import requests

from parser.news.models import EnrichedNewsItem, RawNewsItem
from summarizer.prompt import SYSTEM_INSTRUCTION, build_batch_prompt, parse_batch_response

logger = logging.getLogger(__name__)

MODEL = "llama-3.3-70b-versatile"
API_URL = "https://api.groq.com/openai/v1/chat/completions"

_TRANSIENT_STATUS = {429, 500, 502, 503, 504}


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str | None = None, max_retries: int = 2):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY not set")
        self.max_retries = max_retries

    def summarize_batch(self, items: list[RawNewsItem]) -> list[EnrichedNewsItem]:
        if not items:
            return []
        prompt = build_batch_prompt(items)
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(API_URL, json=payload, headers=headers, timeout=60)
                if resp.status_code in _TRANSIENT_STATUS:
                    raise requests.HTTPError(
                        f"{resp.status_code} {resp.text[:200]}", response=resp
                    )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return parse_batch_response(items, content)
            except Exception as e:
                last_exc = e
                if not _is_transient(e) or attempt >= self.max_retries:
                    break
                backoff = 2 ** attempt
                logger.warning("groq attempt %d transient: %s — retry in %ds", attempt + 1, e, backoff)
                time.sleep(backoff)
        assert last_exc is not None
        raise last_exc


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, requests.HTTPError):
        resp = getattr(exc, "response", None)
        if resp is not None:
            return resp.status_code in _TRANSIENT_STATUS
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    return False
