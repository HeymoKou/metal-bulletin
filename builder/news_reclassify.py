"""기존 data/news/{year}.parquet 재분류.

새 classify_metals 적용해서 false positive (예: 구리시 축제 뉴스가 copper 태그된 것) 제거.
metals 빈 리스트 결과는 row drop.

Usage:
  uv run python -m builder.news_reclassify --data-dir data
  uv run python -m builder.news_reclassify --data-dir data --dry-run
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from datetime import datetime, timezone

from parser.news.classify import classify_metals
from parser.news.models import RawNewsItem


def reclassify_year(path: Path, dry_run: bool = False) -> tuple[int, int, int]:
    """Return (total, kept, dropped). 변경된 metals는 in-place update."""
    table = pq.read_table(path)
    rows = table.to_pylist()
    total = len(rows)

    kept = []
    dropped = 0
    changed = 0
    for r in rows:
        # title + summary 합쳐서 분류 (snippet 없음 → summary_ko 활용)
        item = RawNewsItem(
            source=r.get("source") or "",
            url=r.get("url") or "",
            title=r.get("title") or "",
            snippet=r.get("summary_ko") or "",
            published_at=None,
            fetched_at=datetime.now(timezone.utc),
            lang=r.get("lang") or "en",
        )
        new_metals = classify_metals(item)
        if not new_metals:
            dropped += 1
            print(f"  DROP: {r.get('title', '')[:80]}  (was: {r.get('metals')})")
            continue
        if list(new_metals) != list(r.get("metals") or []):
            changed += 1
            print(f"  CHG : {r.get('title', '')[:60]}  {r.get('metals')} → {new_metals}")
        r["metals"] = new_metals
        kept.append(r)

    print(f"\n{path.name}: total={total} kept={len(kept)} dropped={dropped} changed={changed}")

    if dry_run or (dropped == 0 and changed == 0):
        return total, len(kept), dropped

    new_table = pa.Table.from_pylist(kept, schema=table.schema)
    pq.write_table(
        new_table, path,
        compression="zstd", compression_level=9,
        use_dictionary=True, write_statistics=True,
    )
    return total, len(kept), dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    news_dir = args.data_dir / "news"
    if not news_dir.exists():
        print(f"no news dir: {news_dir}")
        return

    grand_total = grand_kept = grand_dropped = 0
    for f in sorted(news_dir.glob("*.parquet")):
        t, k, d = reclassify_year(f, args.dry_run)
        grand_total += t
        grand_kept += k
        grand_dropped += d

    print(f"\nALL: total={grand_total} kept={grand_kept} dropped={grand_dropped}")
    if args.dry_run:
        print("(dry-run — no files written)")


if __name__ == "__main__":
    main()
