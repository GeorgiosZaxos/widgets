"""tqdm options: bar_format, delay, unit_divisor, write_bytes, pandas hook."""

from __future__ import annotations

import io
import time

import pytest

from widgets.errors import MissingDependencyError
from widgets.progress.indicators import HorizontalBar, format_number
from widgets.progress.state import ProgressState
from widgets.progress.tqdm import tqdm
from widgets.render.buffer import Buffer


def _line(bar: HorizontalBar, width: int = 60) -> str:
    buf = Buffer(width, 1)
    bar.render(buf)
    return "".join(c.glyph for c in buf.row(0)).rstrip()


def test_unit_divisor_scales_binary() -> None:
    assert format_number(2048, scale=True, divisor=1024) == "2.0k"
    assert format_number(2048, scale=True) == "2.0k"
    assert format_number(1500, scale=True, divisor=1024) == "1.5k"
    with pytest.raises(ValueError):
        HorizontalBar(ProgressState(10), 20, unit_divisor=1)


def test_bar_format_placeholders() -> None:
    state = ProgressState(100, n=50, description="job")
    bar = HorizontalBar(
        state, 60, bar_format="{desc} {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}"
    )
    text = _line(bar)
    assert text.startswith("job  50%|") and text.endswith("| 50/100")
    assert "█" in text


def test_bar_format_without_bar_and_unknown_key() -> None:
    bar = HorizontalBar(ProgressState(10, n=5), 40, bar_format="{n_fmt} of {total_fmt}{nope}")
    assert _line(bar, 40) == "5 of 10"


def test_tqdm_bar_format_and_unit_divisor() -> None:
    out = io.StringIO()
    with tqdm(
        total=4096,
        file=out,
        bar_format="{n_fmt}/{total_fmt}",
        unit_scale=True,
        unit_divisor=1024,
        mininterval=0,
    ) as bar:
        bar.update(2048)
    assert "2.0k/4.0k" in out.getvalue()


def test_delay_hides_short_bars() -> None:
    out = io.StringIO()
    with tqdm(total=3, file=out, delay=60, mininterval=0) as bar:
        bar.update(1)
        bar.update(1)
    assert out.getvalue().strip() == ""
    out2 = io.StringIO()
    with tqdm(total=3, file=out2, delay=0.01, mininterval=0) as bar2:
        time.sleep(0.03)
        bar2.update(1)
    assert "1/3" in out2.getvalue()
    with pytest.raises(ValueError):
        tqdm(total=1, delay=-1, disable=True)


def test_write_bytes_encodes_output() -> None:
    raw = io.BytesIO()
    with tqdm(total=2, file=raw, write_bytes=True, mininterval=0) as bar:
        bar.update(2)
    assert b"2/2" in raw.getvalue()


def test_pandas_hook() -> None:
    pd = pytest.importorskip("pandas")
    out = io.StringIO()
    tqdm.pandas(file=out, mininterval=0)
    frame = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    assert frame.progress_apply(lambda row: row["a"] + row["b"], axis=1).tolist() == [5, 7, 9]
    assert frame["a"].progress_map(lambda v: v * 2).tolist() == [2, 4, 6]
    assert frame.groupby("a").progress_apply(lambda g: len(g)).tolist() == [1, 1, 1]
    assert "3/3" in out.getvalue()


def test_pandas_hook_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "pandas", None)
    with pytest.raises(MissingDependencyError):
        tqdm.pandas()
