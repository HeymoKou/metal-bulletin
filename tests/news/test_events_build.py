"""Events parquet builder tests."""
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from builder.events_build import EVENTS_SCHEMA, build_events_parquet
from parser.news.models import EventItem


def _ev(metal: str = "copper", d: str = "2026-05-04", mag: float = -1050.0) -> EventItem:
    return EventItem(
        date=d, type="lme_stock", metal=metal,
        magnitude=mag, title=f"LME {metal} stock change",
        url="https://westmetall.com/x", source="westmetall",
    )


def test_build_writes_parquet(tmp_path: Path):
    out_dir = tmp_path / "events"
    build_events_parquet([_ev("copper"), _ev("aluminum")], out_dir, year=2026)

    out_file = out_dir / "2026.parquet"
    assert out_file.exists()
    table = pq.read_table(out_file)
    assert table.num_rows == 2
    assert set(table.column_names) == {f.name for f in EVENTS_SCHEMA}


def test_dedupe_on_append_same_day_metal(tmp_path: Path):
    """Same (date, type, metal) → keep latest write."""
    out_dir = tmp_path / "events"
    build_events_parquet([_ev("copper", mag=-1000.0)], out_dir, year=2026)
    build_events_parquet([_ev("copper", mag=-1500.0)], out_dir, year=2026)

    table = pq.read_table(out_dir / "2026.parquet")
    assert table.num_rows == 1
    assert table.column("magnitude").to_pylist()[0] == -1500.0  # last wins


def test_separate_dates_kept(tmp_path: Path):
    out_dir = tmp_path / "events"
    build_events_parquet([_ev("copper", d="2026-05-04")], out_dir, year=2026)
    build_events_parquet([_ev("copper", d="2026-05-05")], out_dir, year=2026)

    table = pq.read_table(out_dir / "2026.parquet")
    assert table.num_rows == 2


def test_empty_input_no_op(tmp_path: Path):
    out_dir = tmp_path / "events"
    build_events_parquet([], out_dir, year=2026)
    assert not (out_dir / "2026.parquet").exists()
