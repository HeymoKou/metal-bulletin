"""End-to-end smoke (no network, no LLM)."""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pyarrow.parquet as pq

from parser.news.models import EnrichedNewsItem, RawNewsItem


def test_full_pipeline_with_mocks(tmp_path, monkeypatch):
    """scrape (mocked) → parse → summarize (mocked) → build. 파일 결과 검증."""
    monkeypatch.chdir(tmp_path)
    Path("data").mkdir()

    titles = [
        "Copper hits 5-year high on China demand",
        "Nickel oversupply weighs on Indonesian miners",
        "Aluminum LME stocks fall to record low",
    ]
    items = [
        RawNewsItem(
            source="mining.com",
            url=f"https://e.com/{i}",
            title=titles[i],
            fetched_at=datetime.now(timezone.utc),
            lang="en",
        )
        for i in range(3)
    ]
    Path("data/news_pending.json").write_text(
        json.dumps([i.model_dump(mode="json") for i in items], ensure_ascii=False)
    )

    from parser.news.run import main as parse_main
    parse_main()

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    fake_provider = MagicMock()
    fake_provider.name = "fake"
    fake_provider.summarize_batch.side_effect = lambda items: [
        EnrichedNewsItem(
            **i.model_dump(exclude={"url_hash"}),
            summary_ko="요약", metals=["copper"], sentiment=1,
            event_type="supply", confidence=0.8,
        ) for i in items
    ]
    with patch("summarizer.run.GeminiProvider", lambda: fake_provider):
        from summarizer.run import main as summ_main
        summ_main()

    from builder.news_build import main as build_main
    build_main()

    out_files = list(Path("data/news").glob("*.parquet"))
    assert len(out_files) == 1
    table = pq.read_table(out_files[0])
    assert table.num_rows == 3
    summaries = table.column("summary_ko").to_pylist()
    assert all(s == "요약" for s in summaries)
