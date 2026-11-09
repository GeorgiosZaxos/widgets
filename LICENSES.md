# Licences and provenance

The project itself is released under the MIT licence (see `LICENSE`). This file records the
origin of everything bundled in the package and the third-party material that applies.

## 1. Runtime dependencies

None. The package installs and runs with the Python standard library only. Optional extras
(`wcwidth`, `tzdata`, `pandas`, `openpyxl`, `numpy`, `rich`, `psutil`, `pillow`, `qrcode`) are
installed separately by the user under their own licences and are **not** redistributed here.

## 2. Bundled asset provenance (bundled data and code)

| Item | Location | Origin | Licence |
|---|---|---|---|
| Border styles, bar styles, large and vertical fonts, symbol and colour catalogues | `src/widgets/assets/` | Authored by the project owner (legacy modules `border_types.py`, `barstyles.py`, `large_text_characters.py`, `vertical_large_text_characters.py`, `unicode_*.py`, `color_constants.py`), plus 26 punctuation glyphs drawn for this project | MIT (project licence) |
| Spinner catalogue | `src/widgets/assets/_spinner_data.py` | Authored by the project owner (legacy `spinners.py`). Many spinner names and frame sequences (for example `dots`, `line`, `bounce`, `arc`) are also used by the widely copied *cli-spinners* collection; see section 3 | MIT (project licence); notice in section 3 |
| Colour names (`aliceblue` ... `yellowgreen`) | `src/widgets/assets/colors.py` | The W3C CSS / X11 colour keywords. Names and RGB values are standard facts, not creative works | n/a |
| Unicode block names and ranges | `src/widgets/assets/_block_data.py` | Unicode Character Database (`Blocks.txt`) | Unicode License v3 (section 4) |
| Symbol names | `src/widgets/assets/symbols.py` | Read at run time from Python's `unicodedata` module | Python Software Foundation licence (standard library) |
| tqdm-compatible API | `src/widgets/progress/` | Independent implementation of a compatible interface. No tqdm source is bundled; tqdm is used only as a development/test dependency to check that output is identical | tqdm is MPL-2.0 / MIT (not redistributed) |

## 3. Notice: cli-spinners

Some spinner frame sequences coincide with those published in *cli-spinners*. The notice below
is included for completeness.

```
MIT License

Copyright (c) Sindre Sorhus <sindresorhus@gmail.com> (https://sindresorhus.com)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 4. Notice: Unicode data

```
UNICODE LICENSE V3

Copyright (c) 1991-2024 Unicode, Inc. All rights reserved.
Distributed under the Terms of Use in https://www.unicode.org/copyright.html.

Permission is hereby granted, free of charge, to any person obtaining a copy of the Unicode
data files and any associated documentation (the "Data Files") or Unicode software and any
associated documentation (the "Software") to deal in the Data Files or Software without
restriction, including without limitation the rights to use, copy, modify, merge, publish,
distribute, and/or sell copies of the Data Files or Software, and to permit persons to whom
the Data Files or Software are furnished to do so, provided that either (a) this copyright
and permission notice appear with all copies of the Data Files or Software, or (b) this
copyright and permission notice appear in associated Documentation.

THE DATA FILES AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT OF THIRD PARTY RIGHTS. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR HOLDERS INCLUDED IN THIS NOTICE BE LIABLE FOR ANY CLAIM, OR ANY SPECIAL INDIRECT OR
CONSEQUENTIAL DAMAGES, OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
CONNECTION WITH THE USE OR PERFORMANCE OF THE DATA FILES OR SOFTWARE.

Except as contained in this notice, the name of a copyright holder shall not be used in
advertising or otherwise promoting the sale, use or other dealings in these Data Files or
Software without prior written authorization of the copyright holder.
```

## 5. Owner declaration

The project owner (Georgios Zachos) declares that the legacy modules listed in section 2 were
written by the owner, that no code from other projects was copied into this repository other than
as stated above, and that the owner has the right to release them under the MIT licence.

Signed: Georgios Zachos  Date: 09/11/2026
(Replace the line above with your name and date in the commit that publishes the repository.)

