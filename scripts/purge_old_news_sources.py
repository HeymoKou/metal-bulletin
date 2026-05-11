"""One-shot purge: drop news rows where source not in {snmnews, pps}.

Reason: pipeline was narrowed to snmnews+pps but old gdelt/mining.com/moneytoday
rows remained in data/news/*.parquet (upsert by url_hash never deleted).
"""
from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from builder.news_build import NEWS_SCHEMA

NEWS_DIR = Path("data/news")
KEEP = {"snmnews", "pps"}


def main() -> None:
    for path in sorted(NEWS_DIR.glob("*.parquet")):
        t = pq.read_table(path)
        mask = [s in KEEP for s in t.column("source").to_pylist()]
        before = t.num_rows
        # Preserve canonical NEWS_SCHEMA on write so news_build's concat stays consistent.
        t = t.filter(mask).cast(NEWS_SCHEMA)
        after = t.num_rows
        if after == before:
            print(f"{path.name}: no change ({before} rows)")
            continue
        pq.write_table(t, path, compression="zstd")
        print(f"{path.name}: {before} → {after} ({before - after} dropped)")


if __name__ == "__main__":
    main()
