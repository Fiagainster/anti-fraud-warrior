#!/usr/bin/env python3
"""Check charset coverage: extract every CJK/fullwidth char used by the
game's fzfont-drawn strings (fz_gates.zs, fz_hud.zs) and verify each exists
in the Fusion Pixel TTF. Prints missing chars."""

import re
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
TTF = ROOT / "vendor/fusion-pixel-2026.11.10/fusion-pixel-12px-proportional-zh_hans.ttf"
SOURCES = [
    ROOT / "game/zscript/fz_gates.zs",
    ROOT / "game/zscript/fz_hud.zs",
    ROOT / "game/zscript/fz_defs.zs",
]

# Current CHARSET content from gen_font.py (latin subset always available)
LATIN = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    ":/%.,!?-+()[]<>#*_=|"
)

def main() -> None:
    f = TTFont(str(TTF))
    cmap = f.getBestCmap()

    used = set()
    for p in SOURCES:
        text = p.read_text(encoding="utf-8")
        # take only double-quoted strings (the actual display text)
        for m in re.findall(r'"([^"]*)"', text):
            for ch in m:
                if ch in LATIN or ch == " ":
                    continue
                used.add(ch)

    missing = sorted(c for c in used if ord(c) not in cmap)
    print(f"unique non-latin chars used: {len(used)}")
    print(f"missing from font: {len(missing)}")
    if missing:
        print("".join(missing))
        # emit as a paste-ready charset addition
        print("\nadd to gen_font.py CHARSET:")
        print("    \"" + "".join(missing) + "\"")


if __name__ == "__main__":
    main()
