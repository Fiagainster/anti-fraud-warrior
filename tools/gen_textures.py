#!/usr/bin/env python3
"""Texture pipeline: turn hand-drawn art into engine-ready textures and flats.

Two modes:

  python tools/gen_textures.py check     # default: audit game/textures + flats
  python tools/gen_textures.py fit       # resize art/ source art into place

Naming rule (enforced): a texture name is what the engine sees, so it must be
ASCII, <= 8 characters and unique across textures/flats. `check` refuses to
pass otherwise; the map generator refuses to reference a name that has no PNG
(see gen_maps.own_tex_names).

Sizing rules that come from the engine, not from taste:
  * flats live in the FLATS namespace and the software renderer only tiles
    square power-of-two sizes - 64, 128 or 256. Anything else needs a TEXTURES
    definition *and* a scaling factor, which we do not generate for flats.
  * wall textures only need power-of-two sides (128x128, 256x128). Non-power-
    of-two works in the hardware renderer but breaks in software, so `check`
    treats it as a warning and `fit` will not produce one.
  * both namespaces can take true-colour PNG: no palette quantization needed.

Seamlessness: a wall texture repeats, so its left column must match its right
column (and top row its bottom row). `check` measures that and prints the mean
channel difference; anything above a few units is a visible seam.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"
SRC = ROOT / "art"
SHEET = ROOT / "_staging" / "texsheet.png"
MANIFEST = SRC / "textures.json"

# The slots the maps actually reference today. `fit` uses this to turn
# "art/fz03_wall_tile.png" into "game/textures/FZW3TILE.png" without the
# artist having to think about eight-character lump names.
SLOTS = {
    # 章, 角色, 引擎名 (<=8 字符), 命名空间, 目标尺寸
    "fz01_wall_main": ("FZW1WALL", "textures", (128, 128)),
    "fz01_wall_accent": ("FZW1ACNT", "textures", (128, 128)),
    "fz01_floor": ("FZF1FLR", "flats", (128, 128)),
    "fz01_ceil": ("FZC1CEIL", "flats", (128, 128)),
    "fz02_wall_main": ("FZW2WALL", "textures", (128, 128)),
    "fz02_wall_accent": ("FZW2ACNT", "textures", (128, 128)),
    "fz02_floor": ("FZF2FLR", "flats", (128, 128)),
    "fz02_ceil": ("FZC2CEIL", "flats", (128, 128)),
    "fz03_wall_main": ("FZW3WALL", "textures", (128, 128)),
    "fz03_wall_accent": ("FZW3ACNT", "textures", (128, 128)),
    "fz03_floor": ("FZF3FLR", "flats", (128, 128)),
    "fz03_ceil": ("FZC3CEIL", "flats", (128, 128)),
    # shared across chapters
    "door_trial": ("FZDOOR", "textures", (128, 128)),
    "door_track": ("FZTRACK", "textures", (64, 128)),
    "exit_switch": ("FZSWEXIT", "textures", (128, 128)),
    # skies are 256 wide by convention; Doom tiles them horizontally
    "sky_fz01": ("FZSKY1", "textures", (256, 128)),
    "sky_fz02": ("FZSKY2", "textures", (256, 128)),
    "sky_fz03": ("FZSKY3", "textures", (256, 128)),
}

POW2 = {64, 128, 256, 512, 1024, 2048}


def fail(msg: str) -> None:
    print("FAIL " + msg)


def warn(msg: str) -> None:
    print("WARN " + msg)


def seam_score(im: Image.Image) -> float:
    """Mean channel difference between opposite edges (0 = perfect tile)."""
    im = im.convert("RGB")
    w, h = im.size
    px = im.load()
    left = [px[0, y] for y in range(h)]
    right = [px[w - 1, y] for y in range(h)]
    top = [px[x, 0] for x in range(w)]
    bottom = [px[x, h - 1] for x in range(w)]

    def diff(a, b):
        return sum(abs(x - y) for p, q in zip(a, b) for x, y in zip(p, q))\
            / (3.0 * len(a))

    return (diff(left, right) + diff(top, bottom)) / 2.0


def scan():
    rows, problems = [], []
    seen: dict[str, str] = {}
    for sub in ("textures", "flats"):
        d = GAME / sub
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.png")):
            name = p.stem.upper()
            if len(name) > 8:
                problems.append("%s: name longer than 8 chars" % p)
            if not name.isascii() or not name.replace("_", "").isalnum():
                problems.append("%s: name must be ASCII letters/digits/_" % p)
            if name in seen:
                problems.append("%s: duplicate of %s" % (p, seen[name]))
            seen[name] = str(p)
            im = Image.open(p)
            w, h = im.size
            if sub == "flats":
                if w != h or w not in POW2:
                    problems.append(
                        "%s: flat must be square 64/128/256, got %dx%d"
                        % (p.name, w, h))
            else:
                if w not in POW2 or h not in POW2:
                    warn("%s: non power-of-two %dx%d (software renderer)"
                         % (p.name, w, h))
            rows.append((name, sub, "%dx%d" % (w, h), seam_score(im), str(p)))
    return rows, problems


def sheet(rows):
    if not rows:
        print("no textures yet - nothing to preview")
        return
    cell, pad, cols = 136, 8, 6
    rowsn = (len(rows) + cols - 1) // cols
    img = Image.new("RGB", (cols * (cell + pad) + pad,
                            rowsn * (cell + 26) + pad), (20, 20, 24))
    d = ImageDraw.Draw(img)
    for i, (name, sub, size, seam, path) in enumerate(rows):
        x = pad + (i % cols) * (cell + pad)
        y = pad + (i // cols) * (cell + 26 + pad)
        thumb = Image.open(path).convert("RGB").resize((cell, cell),
                                                       Image.NEAREST)
        img.paste(thumb, (x, y))
        col = (255, 255, 255)
        if seam > 12:
            col = (255, 140, 120)
        d.text((x, y + cell + 4), "%s %s" % (name, size), fill=col)
        d.text((x, y + cell + 14), "seam %.1f" % seam, fill=col)
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    img.save(SHEET)
    print("preview -> %s" % SHEET)


def cmd_check() -> int:
    rows, problems = scan()
    if rows:
        print("%-10s %-8s %-9s %s" % ("NAME", "NS", "SIZE", "SEAM"))
        for name, sub, size, seam, _p in rows:
            flag = "  <-- seam?" if seam > 12 else ""
            print("%-10s %-8s %-9s %6.1f%s" % (name, sub, size, seam, flag))
    for p in problems:
        fail(p)
    sheet(rows)
    if problems:
        print("\n%d problem(s)" % len(problems))
        return 1
    print("\n%d texture(s) OK" % len(rows))
    return 0


def cmd_fit() -> int:
    """Resize `art/<slot>.png` to the slot's engine size and file name."""
    if not SRC.is_dir():
        print("no art/ folder yet - drop source images there named after the "
              "slots in SLOTS and rerun")
        for slot, (name, ns, size) in SLOTS.items():
            print("  art/%-18s -> game/%s/%s.png  %dx%d"
                  % (slot + ".png", ns, name, size[0], size[1]))
        return 0
    written, missing = 0, []
    for slot, (name, ns, size) in SLOTS.items():
        src = SRC / (slot + ".png")
        if not src.exists():
            missing.append(slot)
            continue
        out_dir = GAME / ns
        out_dir.mkdir(parents=True, exist_ok=True)
        im = Image.open(src).convert("RGB")
        if im.size != size:
            im = im.resize(size, Image.LANCZOS)
            print("resize %s %s -> %dx%d"
                  % (src.name, Image.open(src).size, size[0], size[1]))
        dest = out_dir / (name + ".png")
        im.save(dest)
        written += 1
        print("wrote %s  (seam %.1f)" % (dest.relative_to(ROOT), seam_score(im)))
    if missing:
        print("\n%d slot(s) still empty: %s" % (len(missing), ", ".join(missing)))
    manifest = {slot: {"name": SLOTS[slot][0], "namespace": SLOTS[slot][1],
                       "size": list(SLOTS[slot][2])}
                for slot in SLOTS}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("manifest -> %s" % MANIFEST.relative_to(ROOT))
    print("%d file(s) written" % written)
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv else "check"
    if mode == "check":
        return cmd_check()
    if mode == "fit":
        return cmd_fit()
    raise SystemExit("usage: gen_textures.py [check|fit]")


if __name__ == "__main__":
    sys.exit(main())
