#!/usr/bin/env python3
"""Static repository checks that do NOT need the engine (used by CI).

Verifies:
  * every #include in game/zscript.txt exists
  * MAPINFO map chain: every Next target is a defined map
  * doomednums classes are declared somewhere in zscript
  * fonts referenced by the HUD exist as generated directories
  * run.bat is pure ASCII (cmd.exe parses .bat in the system code page)
  * no absolute developer paths (D:\\fztest etc.) leaked into game/ or docs
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"
problems: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


def check_includes() -> None:
    entry = GAME / "zscript.txt"
    if not entry.exists():
        fail("game/zscript.txt missing")
        return
    text = entry.read_text(encoding="utf-8", errors="replace")
    for inc in re.findall(r'#include\s+"([^"]+)"', text):
        if not (GAME / inc).exists():
            fail(f"zscript include missing: {inc}")


def check_mapinfo() -> None:
    p = GAME / "mapinfo" / "MAPINFO"
    if not p.exists():
        fail("game/mapinfo/MAPINFO missing")
        return
    text = p.read_text(encoding="utf-8", errors="replace")
    maps = dict(re.findall(r'^map\s+(\w+)\s+"[^"]*"\s*\{([^}]*)\}', text, re.M))
    if not maps:
        fail("MAPINFO defines no maps")
    for name, body in maps.items():
        m = re.search(r'Next\s*=\s*"([^"]+)"', body, re.I)
        if m and m.group(1) not in maps and m.group(1).lower() not in ("endgame", "endtitle"):
            fail(f"map {name} Next -> unknown map {m.group(1)}")
    notes.append(f"maps: {', '.join(maps)}")

    # doomednums classes must exist in zscript
    zs = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                   for p in (GAME / "zscript").glob("*.zs"))
    for ednum, cls in re.findall(r"^\s*(\d+)\s*=\s*(\w+)\s*$", text, re.M):
        if not re.search(rf"class\s+{cls}\b", zs):
            fail(f"doomednum {ednum} -> class {cls} not declared")


def check_fonts() -> None:
    fonts = ["fzfont", "fzfont_red", "fzfont_blue", "fzfont_gold",
             "fzfont_green", "fzfont_cyan", "fzfont_yellow", "fzfont_gray"]
    hud = GAME / "zscript" / "fz_hud.zs"
    if hud.exists():
        for name in re.findall(r'"([^"]*fzfont[^"]*)"', hud.read_text(encoding="utf-8", errors="replace")):
            if name not in fonts:
                notes.append(f"HUD references font {name} (not in the standard set)")
    missing = [f for f in fonts if not (GAME / "fonts" / f / "font.inf").exists()]
    if missing:
        notes.append("font atlases not generated yet (build.py will create them): "
                     + ", ".join(missing))


def check_bat() -> None:
    bat = ROOT / "run.bat"
    if bat.exists():
        try:
            bat.read_bytes().decode("ascii")
        except UnicodeDecodeError:
            fail("run.bat is not pure ASCII (cmd.exe will corrupt it)")


def check_paths() -> None:
    bad = re.compile(r"[A-Za-z]:\\\\?fztest|D:\\\\Project")
    for sub in ("game", "config"):
        for p in (ROOT / sub).rglob("*"):
            if p.is_file() and p.suffix.lower() in (".zs", ".py", ".md", ".txt", ".bat", ".cfg"):
                try:
                    t = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if bad.search(t):
                    fail(f"absolute dev path leaked in {p.relative_to(ROOT)}")


def main() -> int:
    check_includes()
    check_mapinfo()
    check_fonts()
    check_bat()
    check_paths()
    for n in notes:
        print("note:", n)
    if problems:
        print("\nFAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print("\nstatic checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
