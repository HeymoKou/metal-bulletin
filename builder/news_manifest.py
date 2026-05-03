"""Lightweight manifest updater for news pipeline.

Reads existing data/manifest.json, augments with news/events sections,
writes back. Does NOT touch price-pipeline keys (metals, years, latest_window, etc).

Called from news.yml workflow after news_build, so manifest reflects fresh data
without re-running the price pipeline.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def update_manifest(data_dir: Path = Path("data")) -> None:
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        logger.warning("manifest.json missing, skip news manifest update")
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    news_dir = data_dir / "news"
    if news_dir.exists():
        years = sorted(int(p.stem) for p in news_dir.glob("*.parquet") if p.stem.isdigit())
        if years:
            try:
                latest_file = news_dir / f"{years[-1]}.parquet"
                table = pq.read_table(latest_file, columns=["fetched_at"])
                last_updated = table.column("fetched_at").to_pylist()[-1] if table.num_rows else None
                total = sum(pq.read_metadata(news_dir / f"{y}.parquet").num_rows for y in years)
                manifest["news"] = {
                    "available_years": years,
                    "last_updated": last_updated.isoformat() if last_updated else None,
                    "total_records": total,
                }
                logger.info("manifest.news updated: %d records, years=%s", total, years)
            except Exception as e:
                logger.warning("manifest news augment failed: %s", e)

    events_dir = data_dir / "events"
    if events_dir.exists():
        years = sorted(int(p.stem) for p in events_dir.glob("*.parquet") if p.stem.isdigit())
        if years:
            manifest["events"] = {"available_years": years}

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    update_manifest()


if __name__ == "__main__":
    main()
