"""One-shot purge: drop news rows where source not in {snmnews, pps}.

Reason: pipeline was narrowed to snmnews+pps but old gdelt/mining.com/moneytoday
rows remained in data/news/*.parquet (upsert by url_hash never deleted).
"""
from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

NEWS_DIR = Path("data/news")
KEEP = {"snmnews", "pps"}


def main() -> None:
    for path in sorted(NEWS_DIR.glob("*.parquet")):
        t = pq.read_table(path)
        df = t.to_pandas()
        before = len(df)
        df = df[df["source"].isin(KEEP)].reset_index(drop=True)
        after = len(df)
        if after == before:
            print(f"{path.name}: no change ({before} rows)")
            continue
        out = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(out, path, compression="zstd")
        print(f"{path.name}: {before} → {after} ({before - after} dropped)")


if __name__ == "__main__":
    main()
