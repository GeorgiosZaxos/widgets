"""M4 assets: FR-ASSET-001..010 and legacy shims (FR-API-008)."""

from __future__ import annotations

import importlib
import unicodedata
import warnings

import pytest

from widgets.assets import bars, borders, fonts, registry, spinners, symbols
from widgets.base_elements import color_manager as cm


def _cells(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


@pytest.mark.req("FR-ASSET-001")
def test_bar_style_counts_and_errors() -> None:
    assert len(bars.list_bar_styles("horizontal")) >= 8
    assert len(bars.list_bar_styles("vertical")) >= 8
    with pytest.raises(KeyError, match="available"):
        bars.get_bar_style("nope")


@pytest.mark.req("FR-ASSET-001", "FR-ASSET-009")
@pytest.mark.parametrize("orientation", ["horizontal", "vertical"])
def test_every_bar_has_single_cell_glyphs_and_ascii_fallback(orientation: str) -> None:
    for name in bars.list_bar_styles(orientation):
        style = bars.get_bar_style(name, orientation)
        for ch in (style.fill, style.empty, *style.partials):
            assert _cells(ch) == 1, (name, ch)
        assert all(ord(c) < 128 for c in "".join(style.glyphs(True)[0:2]))


@pytest.mark.req("FR-ASSET-002")
def test_borders_complete_and_aliases() -> None:
    names = borders.list_border_styles()
    assert len(names) >= 10
    for required in ("ascii", "single", "double", "rounded", "heavy"):
        assert required in names
    assert borders.get_border_style("bold") is borders.get_border_style("heavy")
    with pytest.raises(KeyError):
        borders.get_border_style("zzz")


@pytest.mark.req("FR-ASSET-002", "FR-ASSET-009")
def test_border_glyphs_single_cell_and_ascii() -> None:
    for name in borders.list_border_styles():
        style = borders.get_border_style(name)
        assert all(len(c) == 1 and _cells(c) == 1 for c in style.chars()), name
        assert all(ord(c) < 128 for c in style.chars(ascii_only=True)), name


@pytest.mark.req("FR-ASSET-003")
def test_colors_are_reexports_of_color_service() -> None:
    from widgets.assets import colors

    assert colors.parse_color is cm.parse_color
    assert len(colors.list_colors()) >= 100
    assert len(colors.list_gradients()) >= 100
    assert colors.parse_color("crimson") == cm.RGB(220, 20, 60)


@pytest.mark.req("FR-ASSET-004")
def test_large_font_covers_ascii_with_uniform_height() -> None:
    for name in fonts.list_fonts():
        font = fonts.get_font(name)
        fonts.validate_font(font)
        assert all(chr(c) in font.glyphs for c in range(0x20, 0x7F)), name
        assert fonts.font_height(name) == font.height
    assert {fonts.font_height(n) for n in fonts.list_fonts()} >= {3, 4, 5, 6, 7}


@pytest.mark.req("FR-ASSET-004")
def test_render_text_placeholder_for_unsupported() -> None:
    font = fonts.get_font("original-7")
    assert fonts.render_text("é", font) == fonts.render_text("?", font)
    rows = fonts.render_text("AB", font)
    assert len(rows) == 7 and len({len(r) for r in rows}) == 1


@pytest.mark.req("FR-ASSET-004")
def test_validate_font_rejects_bad_rows() -> None:
    with pytest.raises(ValueError):
        fonts.validate_font(fonts.Font("bad", 2, {"a": ("x",)}))
    with pytest.raises(ValueError):
        fonts.validate_font(fonts.Font("bad", 2, {"a": ("x", "xy")}))


@pytest.mark.req("FR-ASSET-005")
def test_vertical_fonts() -> None:
    assert fonts.list_vertical_fonts()
    name = fonts.list_vertical_fonts()[0]
    out = fonts.render_vertical("AB", name)
    h = fonts.get_vertical_font(name).height
    assert len(out) == 2 * h
    assert fonts.render_vertical("é", name) == fonts.render_vertical("?", name)


@pytest.mark.req("FR-ASSET-006")
def test_spinner_catalog() -> None:
    names = spinners.list_spinners()
    assert len(names) >= 20
    for name in names:
        spec = spinners.get_spinner(name)
        assert len(spec.frames) >= 2 and spec.interval > 0
        assert len({_cells(f) for f in spec.frames}) == 1, name
        assert spec.ascii_safe == all(ord(c) < 128 for f in spec.frames for c in f)
    with pytest.raises(KeyError):
        spinners.get_spinner("zzz")


@pytest.mark.req("FR-ASSET-009")
def test_spinner_ascii_fallback() -> None:
    for name in spinners.list_spinners():
        frames = spinners.spinner_frames(name, ascii_only=True)
        assert all(ord(c) < 128 for f in frames for c in f), name


@pytest.mark.req("FR-ASSET-007")
def test_symbol_lookup_and_search() -> None:
    assert symbols.lookup("UP_ARROW").char == "↑"
    assert symbols.lookup("upwards-arrow").char == "↑"
    assert {"arrows", "misc"} <= set(symbols.list_symbol_groups())
    assert symbols.search("half-block")
    with pytest.raises(KeyError):
        symbols.lookup("not-a-symbol")
    for sym in symbols.list_symbols():
        assert unicodedata.name(sym.char).lower().replace(" ", "-") == sym.name
        assert all(ord(c) < 128 for c in sym.ascii)


@pytest.mark.req("FR-ASSET-007")
def test_unicode_blocks() -> None:
    block = symbols.find_block("█")
    assert block is not None and "block" in block.name.lower()
    assert symbols.find_block(0x10FFFF + 1) is None
    assert symbols.search_blocks("arrows")


@pytest.mark.req("FR-ASSET-008")
def test_asset_groups_enumerate() -> None:
    groups = registry.list_asset_groups()
    assert set(groups) >= {"bars", "borders", "colors", "fonts", "spinners", "symbols"}
    for group in groups:
        assert registry.list_assets(group)
    with pytest.raises(KeyError):
        registry.list_assets("zzz")


@pytest.mark.req("FR-ASSET-010")
def test_license_file_present() -> None:
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    assert "Bundled asset provenance" in (root / "LICENSES.md").read_text(encoding="utf-8")


@pytest.mark.req("FR-API-008")
@pytest.mark.parametrize(
    "module",
    [
        "border_types",
        "spinners",
        "barstyles",
        "large_text_characters",
        "vertical_large_text_characters",
        "unicode_arrows",
        "unicode_misc",
        "unicode_blocks",
        "unicode_CharacterSets",
        "color_constants",
    ],
)
def test_legacy_import_paths_warn_and_resolve(module: str) -> None:
    import sys

    sys.modules.pop(f"widgets.include.{module}", None)
    with pytest.warns(DeprecationWarning):
        mod = importlib.import_module(f"widgets.include.{module}")
    assert all(hasattr(mod, n) for n in mod.__all__)
    warnings.simplefilter("default")


@pytest.mark.req("FR-COLOR-001")
def test_register_color_roundtrip() -> None:
    cm.register_color("my-test-red", "#123456", replace=True)
    assert cm.parse_color("my_test_red").to_hex().lower() == "#123456"
    with pytest.raises(ValueError):
        cm.register_color("my-test-red", "#000000")
