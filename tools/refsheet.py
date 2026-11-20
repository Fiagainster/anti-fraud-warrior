#!/usr/bin/env python3
"""Build contact sheets of the Freedoom source pixel art currently sitting in
source/freedoom/. Reference-only tool: output goes to _staging/refsheet/ and is
never committed.

Run with the system interpreter (Pillow is required):
    D:/System/Python/python.exe tools/refsheet.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FREE = ROOT / "source" / "freedoom"
OUT = ROOT / "_staging" / "refsheet"

BG = (22, 24, 28)
CELL = (32, 34, 40)
TEXT = (196, 200, 208)
ACCENT = (232, 168, 96)

# Pickups / props: the things our maps borrow from Freedoom right now are in
# BORROWED, and they get an amber label so the art pass knows what to replace.
BORROWED = {"ARM1", "BPAK", "BKEY"}
ITEMS = [
    "ARM1", "ARM2", "BPAK", "BKEY", "RKEY", "YKEY", "MEDI", "STIM",
    "SHOT", "SBOX", "CLIP", "AMMO", "SHEL", "BROK", "CELL", "CELP",
    "ROCK", "BAL1", "BAL2", "PLAS", "SAWG", "SUIT", "SOUL", "MEGA",
    "PINS", "PSTR", "PVIS", "PMUP", "BON1", "BON2", "SKUL", "BRS1",
    "POL2", "POL3", "TRE1", "CAND",
]
MONSTERS = [
    "POSS", "SPOS", "CPOS", "TROO", "SARG", "HEAD", "SKEL", "FATT",
    "PAIN", "VILE", "BOS2", "BOSS", "CYBR", "SPID", "PLAY", "SSWV",
]


def pick(prefix: str) -> Path | None:
    """Prefer the front-facing frame, then any A frame."""
    d = FREE / "sprites"
    for want in (prefix.lower() + "a2a8", prefix.lower() + "a1",
                 prefix.lower() + "a0"):
        p = d / (want + ".png")
        if p.exists():
            return p
    hits = sorted(d.glob(prefix.lower() + "a*.png"))
    return hits[0] if hits else None


def sheet(entries: list[tuple[str, Path]], cols: int, cell: int,
          title: str, dest: Path) -> None:
    rows = (len(entries) + cols - 1) // cols
    pad = 8
    top = 34
    W = cols * (cell + pad) + pad
    H = top + rows * (cell + pad + 14) + pad
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("consola.ttf", 11)
        tfont = ImageFont.truetype("consola.ttf", 13)
    except OSError:
        font = tfont = ImageFont.load_default()
    dr.text((pad, 10), title, font=tfont, fill=(240, 240, 240))

    for i, (name, path) in enumerate(entries):
        cx = pad + (i % cols) * (cell + pad)
        cy = top + (i // cols) * (cell + pad + 14)
        dr.rectangle([cx, cy, cx + cell, cy + cell], fill=CELL)
        try:
            im = Image.open(path)
        except Exception:
            continue
        im = im.convert("RGBA")
        w, h = im.size
        scale = max(1, min((cell - 6) // max(w, 1), (cell - 6) // max(h, 1)))
        im = im.resize((w * scale, h * scale), Image.NEAREST)
        img.paste(im, (cx + (cell - im.width) // 2,
                       cy + (cell - im.height) // 2), im)
        color = ACCENT if name in BORROWED else TEXT
        dr.text((cx + 2, cy + cell + 2), name, font=font, fill=color)

    img.save(dest)
    print(dest.relative_to(ROOT), img.size)


def main() -> None:
    if not FREE.exists():
        raise SystemExit("source/freedoom/ missing - this tree is not in git; "
                         "re-clone freedoom source next to the repo")
    OUT.mkdir(parents=True, exist_ok=True)

    items = []
    for name in ITEMS:
        p = pick(name)
        if p:
            items.append((name, p))
    sheet(items, cols=9, cell=56,
          title=f"Freedoom 源码拾取物/道具 ({len(items)} 个, 琥珀色=我们正在借用的)",
          dest=OUT / "01-items.png")

    monsters = []
    for name in MONSTERS:
        p = pick(name)
        if p:
            monsters.append((name, p))
    sheet(monsters, cols=8, cell=96,
          title=f"Freedoom 源码怪物/角色正面帧 ({len(monsters)} 个)",
          dest=OUT / "02-monsters.png")

    flats = sorted((FREE / "flats").glob("*.png"))[:48]
    sheet([(p.stem.upper(), p) for p in flats], cols=12, cell=56,
          title=f"Freedoom 源码扁平/地板 (前 {len(flats)} 张, 均为 64x64)",
          dest=OUT / "03-flats.png")

    for p in sorted(OUT.glob("*.png")):
        if p.stat().st_size == 0:
            raise SystemExit(f"empty sheet: {p}")


if __name__ == "__main__":
    sys.exit(main())
