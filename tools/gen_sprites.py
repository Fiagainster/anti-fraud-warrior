#!/usr/bin/env python3
"""Sprite pipeline: audit, preview and palette-variant the character art.

  python tools/gen_sprites.py check              # default: audit game/sprites
  python tools/gen_sprites.py sheet              # contact sheet per sprite name
  python tools/gen_sprites.py tint FZFR "60,90,55" out/

Engine rules this enforces (they are not style choices):
  * a sprite lump name is 8 characters max: 4 name + frame letter + rotation.
    We enforce exactly 4+1+1 so every file is unambiguous.
  * frame letters are A-Z; rotation is 0-8, where 0 means "single, always
    faces the player" - that is the only rotation this project draws.
  * PNG sprites default to "centred horizontally, bottom on the floor". If the
    drawn figure never reaches the bottom row, the character will float, so
    `check` measures the empty bottom margin and complains.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SPR = ROOT / "game" / "sprites"
SHEET = ROOT / "_staging" / "spritesheet.png"
NAME_RE = re.compile(r"^([A-Z][A-Z0-9]{3})([A-Z])([0-8])$")

CELL = 72
PAD = 6


def parse(path: Path):
    m = NAME_RE.match(path.stem.upper())
    if not m:
        return None
    return m.group(1), m.group(2), int(m.group(3))


def scan():
    rows, problems = [], []
    if not SPR.is_dir():
        return rows, problems
    for p in sorted(SPR.rglob("*.png")):
        got = parse(p)
        if got is None:
            problems.append("%s: name must be 4 chars + frame letter + rotation "
                            "(e.g. FZFRA1.png)" % p.name)
            continue
        name, frame, rot = got
        im = Image.open(p).convert("RGBA")
        w, h = im.size
        # bottom margin: rows between the last non-transparent row and the edge
        alpha = im.split()[3]
        bbox = alpha.getbbox()
        margin = h - bbox[3] if bbox else h
        if margin > 2:
            problems.append("%s: figure floats %d px above the bottom edge"
                            % (p.name, margin))
        rows.append((name, frame, rot, w, h, margin, str(p)))
    return rows, problems


def cmd_check() -> int:
    rows, problems = scan()
    if not rows and not problems:
        print("no sprites yet - nothing to check")
        return 0
    print("%-6s %-5s %-4s %-9s %s" % ("NAME", "FRAME", "ROT", "SIZE", "FOOT"))
    for name, frame, rot, w, h, margin, _p in rows:
        print("%-6s %-5s %-4d %-9s %d" % (name, frame, rot, "%dx%d" % (w, h),
                                          margin))
    by_name: dict[str, list[str]] = {}
    for name, frame, rot, *_ in rows:
        by_name.setdefault(name, []).append(frame)
    for name, frames in sorted(by_name.items()):
        missing = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                   if min(frames) <= c <= max(frames) and c not in frames]
        if missing:
            print("WARN %s: frame gap at %s" % (name, "".join(missing)))
    for p in problems:
        print("FAIL " + p)
    print("\n%d sprite(s), %d problem(s)" % (len(rows), len(problems)))
    return 1 if problems else 0


def cmd_sheet() -> int:
    rows, _ = scan()
    if not rows:
        print("no sprites yet")
        return 0
    by_name: dict[str, list] = {}
    for r in rows:
        by_name.setdefault(r[0], []).append(r)
    widest = max(len(v) for v in by_name.values())
    img = Image.new("RGB", (widest * (CELL + PAD) + PAD,
                            len(by_name) * (CELL + 24 + PAD) + PAD), (18, 18, 22))
    d = ImageDraw.Draw(img)
    for row, (name, items) in enumerate(sorted(by_name.items())):
        y = PAD + row * (CELL + 24 + PAD)
        d.text((PAD, y), name, fill=(255, 255, 255))
        for col, (name, frame, rot, w, h, margin, path) in enumerate(
                sorted(items, key=lambda r: (r[1], r[2]))):
            x = PAD + col * (CELL + PAD)
            im = Image.open(path).convert("RGBA")
            im.thumbnail((CELL, CELL), Image.NEAREST)
            tile = Image.new("RGB", (CELL, CELL), (40, 40, 46))
            tile.paste(im, ((CELL - im.width) // 2, CELL - im.height), im)
            img.paste(tile, (x, y + 14))
            d.text((x + 2, y + 14 + CELL + 2), "%s%d" % (frame, rot),
                   fill=(200, 200, 200))
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    img.save(SHEET)
    print("preview -> %s" % SHEET)
    return 0


def cmd_tint(args) -> int:
    """Re-colour a whole sprite set so one skeleton serves several variants.

    Luminance is mapped onto a ramp between two colours, which keeps the
    shading readable instead of flat-filling the silhouette."""
    if len(args) < 3:
        raise SystemExit('usage: tint NAME "r,g,b" OUTDIR [NAME2,r,g,b,OUT2...]')
    src_name, rgb = args[0].upper(), [int(v) for v in args[1].split(",")]
    out = Path(args[2])
    out.mkdir(parents=True, exist_ok=True)
    dark = tuple(int(c * 0.35) for c in rgb)
    done = 0
    for p in sorted(SPR.glob(src_name + "*.png")):
        im = Image.open(p).convert("RGBA")
        px = im.load()
        for y in range(im.height):
            for x in range(im.width):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
                px[x, y] = (int(dark[0] + (rgb[0] - dark[0]) * lum),
                            int(dark[1] + (rgb[1] - dark[1]) * lum),
                            int(dark[2] + (rgb[2] - dark[2]) * lum), a)
        im.save(out / p.name)
        done += 1
    print("%d frame(s) tinted -> %s" % (done, out))
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv else "check"
    if mode == "check":
        return cmd_check()
    if mode == "sheet":
        return cmd_sheet()
    if mode == "tint":
        return cmd_tint(argv[1:])
    raise SystemExit("usage: gen_sprites.py [check|sheet|tint]")


if __name__ == "__main__":
    sys.exit(main())
