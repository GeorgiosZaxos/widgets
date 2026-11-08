# Manual terminal checklist (NFR-PORT-005)

Run in each terminal you support, then tick the box and record the date and version.
Terminals: Windows Terminal, PyCharm console (emulated terminal), iTerm2 / Terminal.app, GNOME Terminal,
one of Alacritty / kitty / WezTerm, and `tmux`.

For each terminal:

- [ ] `python examples/color_gallery.py` - colours, gradients and the 256-colour cube look continuous (no banding or wrong hues)
- [ ] `python examples/color_gallery.py --text` prints and exits cleanly
- [ ] `python examples/dev_showcase.py` - press `n` through all 40 entries; no garbled glyphs, no flicker, `q` restores the terminal
- [ ] `python examples/all_widgets.py` - tour completes, no traceback
- [ ] `python examples/rss_ticker.py` - four lanes move in the stated directions at different speeds; `+`/`-`, `[`/`]`, space, `d` work
- [ ] `python examples/progress_demo.py` - bars update in place; Ctrl+C leaves the cursor visible
- [ ] Resize the window while a demo runs - no crash, redraws correctly
- [ ] `NO_COLOR=1 python examples/color_gallery.py --text` - no colour codes
- [ ] Wide glyphs (CJK, emoji) in `Box` stay inside their borders

Record results in the pull request or in `docs/COMPATIBILITY.md`.
