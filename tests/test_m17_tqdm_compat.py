# ruff: noqa: C408
"""tqdm drop-in compatibility (demo-derived scenarios).

Every scenario runs against ``widgets.tqdm`` and ``widgets.vtqdm`` and, when the real ``tqdm`` is
installed, against it too, so behavioural differences show up as test failures.
"""

from __future__ import annotations

import inspect
import io
import logging
import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest

import widgets
from widgets.progress import meter

try:
    import tqdm as real_tqdm_pkg
except ImportError:  # pragma: no cover - optional dev dependency
    real_tqdm_pkg = None

IMPLS = ["widgets", "vtqdm", *(["tqdm"] if real_tqdm_pkg else [])]


@pytest.fixture(params=IMPLS)
def T(request: pytest.FixtureRequest) -> Any:
    if request.param == "widgets":
        return widgets.tqdm
    if request.param == "vtqdm":
        return widgets.vtqdm
    return real_tqdm_pkg.tqdm  # type: ignore[union-attr]


def _trange(T: Any, *a: Any, **k: Any) -> Any:
    return T(range(*a), **k)


# -- demo scenarios ----------------------------------------------------------------------------


@pytest.mark.req("FR-PROG-018")
def test_basic_loop_and_trange(T: Any) -> None:
    out = io.StringIO()
    assert list(T(range(5), file=out)) == [0, 1, 2, 3, 4]
    assert sum(1 for _ in _trange(T, 3, file=out)) == 3


@pytest.mark.req("FR-PROG-018")
def test_desc_unit_scale_and_total(T: Any) -> None:
    out = io.StringIO()
    with T(total=100, desc="dl", unit="B", unit_scale=True, file=out) as bar:
        for _ in range(10):
            bar.update(10)
        assert bar.n == 100
        assert bar.total == 100
        assert bar.desc.startswith("dl")


@pytest.mark.req("FR-PROG-018")
def test_manual_update_returns_and_close_twice(T: Any) -> None:
    bar = T(total=3, file=io.StringIO())
    bar.update(1)
    bar.update(2)
    bar.close()
    bar.close()
    assert bar.n == 3


@pytest.mark.req("FR-PROG-018")
def test_nested_bars_leave_false_and_position(T: Any) -> None:
    out = io.StringIO()
    seen = []
    for i in T(range(2), desc="outer", file=out):
        for j in T(range(3), desc="inner", leave=False, position=1, file=out):
            seen.append((i, j))
    assert len(seen) == 6


@pytest.mark.req("FR-PROG-018")
def test_set_description_and_postfix(T: Any) -> None:
    bar = T(range(3), file=io.StringIO())
    for i in bar:
        bar.set_description(f"step {i}")
        bar.set_postfix(loss=1.0 / (i + 1), ok=True)
        bar.set_postfix_str("raw")
    bar.set_description_str("final")
    bar.close()


@pytest.mark.req("FR-PROG-018")
def test_write_does_not_raise(T: Any) -> None:
    out = io.StringIO()
    bar = T(range(2), file=out)
    for i in bar:
        T.write(f"msg {i}", file=out)
    assert "msg 0" in out.getvalue()


@pytest.mark.req("FR-PROG-018")
def test_disable(T: Any) -> None:
    out = io.StringIO()
    assert list(T(range(4), disable=True, file=out)) == [0, 1, 2, 3]
    assert out.getvalue() == ""


@pytest.mark.req("FR-PROG-018")
def test_generator_without_total(T: Any) -> None:
    def gen() -> Iterator[int]:
        yield from range(4)

    assert list(T(gen(), file=io.StringIO())) == [0, 1, 2, 3]


@pytest.mark.req("FR-PROG-018")
def test_break_and_exception_close_the_bar(T: Any) -> None:
    out = io.StringIO()
    for i in T(range(10), file=out):
        if i == 2:
            break
    with pytest.raises(RuntimeError), T(total=5, file=out) as bar:
        bar.update(1)
        raise RuntimeError("boom")


@pytest.mark.req("FR-PROG-018")
def test_n_and_total_assignment_and_refresh(T: Any) -> None:
    bar = T(total=10, file=io.StringIO())
    bar.n = 4
    bar.total = 20
    bar.refresh()
    bar.reset()
    assert bar.n == 0
    bar.reset(total=7)
    assert bar.total == 7
    bar.close()


@pytest.mark.req("FR-PROG-018")
def test_initial_and_len_and_bool(T: Any) -> None:
    bar = T(range(5), initial=0, file=io.StringIO())
    assert len(bar) == 5
    assert bool(bar)
    bar.close()


@pytest.mark.req("FR-PROG-018")
def test_clear_and_display_and_format_dict(T: Any) -> None:
    bar = T(total=4, desc="d", file=io.StringIO())
    bar.update(2)
    fd = bar.format_dict
    assert fd["n"] == 2
    assert fd["total"] == 4
    assert {"elapsed", "unit", "ncols", "prefix"} <= set(fd)
    bar.clear()
    bar.display()
    bar.close()


@pytest.mark.req("FR-PROG-018")
def test_unknown_kwarg_raises_like_tqdm(T: Any) -> None:
    with pytest.raises(KeyError):
        T(range(2), file=io.StringIO(), bogus_option=1)


@pytest.mark.req("FR-PROG-018")
def test_unit_divisor_ascii_colour_bar_format_accepted(T: Any) -> None:
    out = io.StringIO()
    for _ in T(
        range(3),
        file=out,
        ascii=True,
        colour="green",
        unit_divisor=1000,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}",
        mininterval=0,
        maxinterval=1,
        miniters=1,
        smoothing=0.3,
        dynamic_ncols=False,
        ncols=60,
        position=0,
        postfix={"a": 1},
        leave=True,
    ):
        pass


@pytest.mark.req("FR-PROG-018")
def test_get_lock_and_set_lock(T: Any) -> None:
    lock = T.get_lock()
    assert hasattr(lock, "acquire")
    T.set_lock(lock)


@pytest.mark.req("FR-PROG-018")
def test_external_write_mode_and_wrapattr(T: Any, tmp_path: Any) -> None:
    out = io.StringIO()
    with T.external_write_mode(file=out):
        out.write("x")
    src = tmp_path / "f.bin"
    src.write_bytes(b"abc" * 100)
    with open(src, "rb") as raw, T.wrapattr(raw, "read", file=out) as wrapped:
        assert len(wrapped.read()) == 300


@pytest.mark.req("FR-PROG-018")
def test_reversed_and_contains_and_str(T: Any) -> None:
    bar = T(range(3), file=io.StringIO())
    assert isinstance(str(bar), str)
    bar.close()


# -- module-level helpers ----------------------------------------------------------------------

FORMAT_CASES: list[tuple[dict[str, Any], str]] = [
    (dict(n=5, total=10, elapsed=2.0), " 50%|█████     | 5/10 [00:02<00:02,  2.50it/s]"),
    (dict(n=0, total=10, elapsed=0.0, ncols=40), "  0%|            | 0/10 [00:00<?, ?it/s]"),
    (dict(n=1500, total=None, elapsed=61, unit="B", unit_scale=True), "1.50kB [01:01, 24.6B/s]"),
    (
        dict(n=3, total=4, elapsed=3, prefix="dl", ncols=50, ascii=True),
        "dl:  75%|########2  | 3/4 [00:03<00:01,  1.00it/s]",
    ),
    (
        dict(n=7, total=10, elapsed=7, postfix="a=1", ncols=60),
        " 70%|█████████████▎     | 7/10 [00:07<00:03,  1.00it/s, a=1]",
    ),
]


@pytest.mark.parametrize(("kwargs", "expected"), FORMAT_CASES)
@pytest.mark.req("FR-PROG-018")
def test_format_meter_matches_recorded_tqdm_output(kwargs: dict[str, Any], expected: str) -> None:
    assert widgets.tqdm.format_meter(**kwargs) == expected
    assert meter.format_meter(**kwargs) == expected
    assert widgets.vtqdm.format_meter(**kwargs) == expected


@pytest.mark.req("FR-PROG-018")
def test_helper_functions_match_recorded_output() -> None:
    assert widgets.tqdm.format_interval(3661) == "1:01:01"
    assert widgets.tqdm.format_sizeof(123456789) == "123M"
    assert widgets.tqdm.format_num(0.000123) == "0.000123"


@pytest.mark.skipif(real_tqdm_pkg is None, reason="tqdm not installed")
@pytest.mark.parametrize(("kwargs", "_"), FORMAT_CASES)
@pytest.mark.req("FR-PROG-018")
def test_format_meter_matches_live_tqdm(kwargs: dict[str, Any], _: str) -> None:
    assert widgets.tqdm.format_meter(**kwargs) == real_tqdm_pkg.tqdm.format_meter(**kwargs)  # type: ignore[union-attr]


# -- API surface ---------------------------------------------------------------------------------


@pytest.mark.skipif(real_tqdm_pkg is None, reason="tqdm not installed")
@pytest.mark.parametrize("cls_name", ["tqdm", "vtqdm"])
@pytest.mark.req("FR-PROG-018")
def test_public_members_cover_real_tqdm(cls_name: str) -> None:
    ours = getattr(widgets, cls_name)
    real = real_tqdm_pkg.tqdm  # type: ignore[union-attr]
    missing = [
        n
        for n in dir(real)
        if not n.startswith("_") and n not in {"pandas", "monitor", "monitor_interval"}
        if not hasattr(ours, n)
    ]
    assert missing == []


@pytest.mark.skipif(real_tqdm_pkg is None, reason="tqdm not installed")
@pytest.mark.parametrize("cls_name", ["tqdm", "vtqdm"])
@pytest.mark.req("FR-PROG-018")
def test_constructor_parameters_cover_real_tqdm(cls_name: str) -> None:
    ours = inspect.signature(getattr(widgets, cls_name).__init__).parameters
    real = inspect.signature(real_tqdm_pkg.tqdm.__init__).parameters  # type: ignore[union-attr]
    if cls_name == "vtqdm":  # forwards everything to tqdm and adds ``height``
        kinds = {p.kind for p in ours.values()}
        assert inspect.Parameter.VAR_KEYWORD in kinds
        assert "height" in ours
        return
    missing = [p for p in real if p not in ours and p != "kwargs"]
    assert missing == []


@pytest.mark.req("FR-PROG-018")
def test_exception_classes_hierarchy() -> None:
    from widgets import TqdmDeprecationWarning, TqdmKeyError, TqdmTypeError, TqdmWarning

    assert issubclass(TqdmKeyError, KeyError)
    assert issubclass(TqdmTypeError, TypeError)
    assert issubclass(TqdmDeprecationWarning, TqdmWarning)


# -- contrib / submodules ------------------------------------------------------------------------


@pytest.mark.req("FR-PROG-018")
def test_contrib_helpers() -> None:
    from widgets.progress.contrib import tenumerate, tmap, tzip
    from widgets.progress.contrib.concurrent import thread_map
    from widgets.progress.contrib.itertools import product

    assert list(tenumerate("ab", file=io.StringIO())) == [(0, "a"), (1, "b")]
    assert list(tzip([1, 2], "ab", file=io.StringIO())) == [(1, "a"), (2, "b")]
    assert list(tmap(str, [1, 2], file=io.StringIO())) == ["1", "2"]
    assert thread_map(lambda x: x * 2, range(4), file=io.StringIO()) == [0, 2, 4, 6]
    assert list(product("ab", [1, 2], file=io.StringIO())) == [
        ("a", 1),
        ("a", 2),
        ("b", 1),
        ("b", 2),
    ]


@pytest.mark.req("FR-PROG-018")
def test_logging_redirect_and_dummy_file() -> None:
    from widgets.progress.contrib import DummyTqdmFile
    from widgets.progress.contrib.logging import logging_redirect_tqdm, tqdm_logging_redirect

    buf = io.StringIO()
    DummyTqdmFile(buf).write("hello\n")
    log = logging.getLogger("m17")
    log.setLevel(logging.INFO)
    with logging_redirect_tqdm(loggers=[log]):
        log.info("inside")
    with tqdm_logging_redirect(total=1, file=io.StringIO(), loggers=[log]) as bar:
        log.info("inside2")
        bar.update(1)


@pytest.mark.req("FR-PROG-018")
def test_asyncio_iteration() -> None:
    import asyncio

    from widgets.progress.asyncio import tarange, tqdm_asyncio

    async def go() -> list[int]:
        got = [i async for i in tarange(3, file=io.StringIO())]
        got += [i async for i in tqdm_asyncio(_agen(), total=2, file=io.StringIO())]
        return got

    assert asyncio.run(go()) == [0, 1, 2, 0, 1]


async def _agen() -> Any:
    for i in range(2):
        yield i


@pytest.mark.req("FR-PROG-018")
def test_pandas_progress_apply() -> None:
    pd = pytest.importorskip("pandas")
    widgets.tqdm.pandas(file=io.StringIO())
    df = pd.DataFrame({"a": range(5)})
    assert df.a.progress_apply(lambda v: v + 1).tolist() == [1, 2, 3, 4, 5]


@pytest.mark.req("FR-PROG-018")
def test_vertical_bar_extras() -> None:
    bar = widgets.vtqdm(total=4, height=6, file=io.StringIO())
    bar.update(2)
    assert bar.n == 2
    bar.close()
    assert list(widgets.vtrange(3, file=io.StringIO())) == [0, 1, 2]


# -- source swap: unmodified tqdm-style code -----------------------------------------------------

DEMO = """
from tqdm import tqdm, trange
from tqdm.auto import tqdm as auto_tqdm
from tqdm.contrib.concurrent import thread_map
from tqdm.contrib.itertools import product
import io

out = io.StringIO()
total = 0
for i in tqdm(range(5), desc="loop", file=out):
    total += i
for i in trange(3, file=out):
    total += i
with tqdm(total=10, unit="B", unit_scale=True, file=out) as pbar:
    pbar.update(10)
for _ in auto_tqdm(range(2), file=out):
    pass
res = thread_map(lambda x: x + 1, range(3), file=out)
combos = list(product("ab", range(2), file=out))
RESULT = (total, res, len(combos))
"""


@pytest.mark.parametrize("name", ["tqdm", "vtqdm"])
@pytest.mark.req("FR-PROG-018")
def test_source_swap_runs_unmodified_demo(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import widgets.progress.asyncio as w_asyncio
    import widgets.progress.auto as w_auto
    import widgets.progress.contrib as w_contrib
    import widgets.progress.contrib.concurrent as w_conc
    import widgets.progress.contrib.itertools as w_iter
    import widgets.progress.contrib.logging as w_log
    import widgets.progress.std as w_std
    from widgets.progress import tqdm as w_tqdm_mod

    cls = getattr(widgets, name)
    rng = widgets.vtrange if name == "vtqdm" else widgets.trange
    root = types.ModuleType("tqdm")
    root.__dict__.update(
        {k: getattr(w_tqdm_mod, k) for k in dir(w_tqdm_mod) if not k.startswith("__")}
    )
    root.tqdm = cls  # type: ignore[attr-defined]
    root.trange = rng  # type: ignore[attr-defined]
    root.__path__ = []  # type: ignore[attr-defined]
    auto = types.ModuleType("tqdm.auto")
    auto.tqdm = cls  # type: ignore[attr-defined]
    auto.trange = rng  # type: ignore[attr-defined]
    for mod_name, mod in {
        "tqdm": root,
        "tqdm.auto": auto,
        "tqdm.std": w_std,
        "tqdm.asyncio": w_asyncio,
        "tqdm.contrib": w_contrib,
        "tqdm.contrib.concurrent": w_conc,
        "tqdm.contrib.itertools": w_iter,
        "tqdm.contrib.logging": w_log,
    }.items():
        monkeypatch.setitem(sys.modules, mod_name, mod)
    _ = w_auto
    ns: dict[str, Any] = {}
    exec(compile(DEMO, "<demo>", "exec"), ns)
    assert ns["RESULT"] == (13, [1, 2, 3], 4)
