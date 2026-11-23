#!/usr/bin/env python3
"""Build the hand-weapon reference sheet: where each IWAD frame actually lands
on a 320x200 screen, plus a pixel grid to draw over.

Reference-only tool (like refsheet.py): output goes to _staging/weapon_ref/ and
is never committed. The frames themselves are Freedoom's (BSD-3-Clause); this
is a drawing aid, not a shippable asset.

    D:/System/Python/python.exe tools/weapon_ref.py

Why the sheet exists: the held weapon is the one piece of art still borrowed
from the IWAD. The frames are 3D renders, and each frame has its own canvas
because recoil and muzzle flash grew the bounding box (PISGA0 is 82x92,
PISGE0 is 86x120). Drawing one 82x92 gun and scaling it will drift; the sheet
shows the real per-frame footprint and the calibrated screen anchor
(x = -LeftOffset, bottom row = WEAPON_BOTTOM_ROW).
"""
from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
WAD = ROOT / "vendor" / "freedoom-0.13.0" / "freedoom1.wad"
SRC = ROOT / "source" / "freedoom" / "sprites"
OUT = ROOT / "_staging" / "weapon_ref"

# 320x200 virtual screen; the value tools/fix_offsets.py calibrated for where
# the bottom of the gun sits (see WEAPON_BOTTOM_ROW there).
SCREEN_W, SCREEN_H = 320, 200
WEAPON_BOTTOM_ROW = 148
HUD_TOP = 168

BG = (18, 20, 24)
GRID = (44, 48, 56)
GRID_STRONG = (70, 76, 88)
TEXT = (200, 205, 214)
ACCENT = (232, 168, 96)


def patch_header(lump: str) -> tuple[int, int, int, int]:
    data = WAD.read_bytes()
    _, numlumps, diroff = struct.unpack("<4sii", data[:12])
    for i in range(numlumps):
        off, size, name = struct.unpack("<ii8s", data[diroff + 16 * i:diroff + 16 * i + 16])
        if name.split(b"\0")[0].decode("latin1") == lump:
            return struct.unpack("<hhhh", data[off:off + 8])
    raise SystemExit(f"{lump} not in {WAD}")


def frames(prefix: str) -> list[tuple[str, Image.Image, tuple[int, int, int, int]]]:
    rows = []
    for path in sorted(SRC.glob(prefix.lower() + "[a-z]0.png")):
        lump = path.stem.upper()
        w, h, left, top = patch_header(lump)
        img = Image.open(path).convert("RGBA")
        if img.size != (w, h):
            img = img.resize((w, h), Image.NEAREST)
        rows.append((lump, img, (w, h, left, top)))
    if not rows:
        raise SystemExit(f"no source frames for {prefix} under {SRC}")
    return rows


def screen_mock(frame: tuple[str, Image.Image, tuple[int, int, int, int]],
                scale: int) -> Image.Image:
    """Frame placed where the engine draws it on a 320x200 screen."""
    lump, img, (w, h, left, top) = frame
    canvas = Image.new("RGB", (SCREEN_W * scale, SCREEN_H * scale), BG)
    # virtual-screen grid every 16 px
    d = ImageDraw.Draw(canvas)
    for x in range(0, SCREEN_W + 1, 16):
        d.line([(x * scale, 0), (x * scale, SCREEN_H * scale)],
               fill=GRID_STRONG if x in (160,) else GRID)
    for y in range(0, SCREEN_H + 1, 16):
        d.line([(0, y * scale), (SCREEN_W * scale, y * scale)],
               fill=GRID_STRONG if y in (100, 148) else GRID)
    # HUD strip + weapon bottom line
    d.rectangle([0, HUD_TOP * scale, SCREEN_W * scale, SCREEN_H * scale], fill=(26, 30, 36))
    d.line([(0, WEAPON_BOTTOM_ROW * scale), (SCREEN_W * scale, WEAPON_BOTTOM_ROW * scale)],
           fill=ACCENT, width=2)
    big = img.resize((w * scale, h * scale), Image.NEAREST)
    x = -left * scale
    y = (WEAPON_BOTTOM_ROW - h) * scale
    canvas.paste(big, (x, y), big)
    d.text((6 * scale, 4 * scale), f"{lump} {w}x{h}  left={left} top={top}", fill=TEXT)
    d.text((6 * scale, (WEAPON_BOTTOM_ROW + 2) * scale),
           f"bottom row {WEAPON_BOTTOM_ROW} / HUD from {HUD_TOP}", fill=ACCENT)
    return canvas


def strip(rows: list[tuple[str, Image.Image, tuple[int, int, int, int]]],
          scale: int) -> Image.Image:
    pad = 10
    cell_h = max(img.height for _, img, _ in rows) * scale
    cell_w = max(img.width for _, img, _ in rows) * scale
    W = len(rows) * (cell_w + pad) + pad
    H = cell_h + pad * 2 + 16
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    for i, (lump, img, (w, h, left, top)) in enumerate(rows):
        big = img.resize((w * scale, h * scale), Image.NEAREST)
        x = pad + i * (cell_w + pad)
        canvas.paste(big, (x, pad + cell_h - big.height), big)
        # 1-pixel grid at this scale
        for gx in range(0, big.width, scale):
            d.line([(x + gx, pad), (x + gx, pad + cell_h)], fill=GRID)
        for gy in range(0, cell_h, scale):
            d.line([(x, pad + gy), (x + cell_w, pad + gy)], fill=GRID)
        d.rectangle([x, pad, x + cell_w, pad + cell_h], outline=GRID_STRONG)
        d.text((x, 2), f"{lump} {w}x{h}", fill=TEXT)
    return canvas


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for prefix, title in (("PISG", "pistol"), ("SHTG", "shotgun")):
        rows = frames(prefix)
        mock = screen_mock(rows[0], 2)
        frames_sheet = strip(rows, 4)
        width = max(mock.width, frames_sheet.width)
        img = Image.new("RGB", (width, mock.height + frames_sheet.height + 8), BG)
        img.paste(mock, (0, 0))
        img.paste(frames_sheet, (0, mock.height + 8))
        dest = OUT / f"{title}.png"
        img.save(dest)
        print(f"{dest}  {img.width}x{img.height}  ({len(rows)} 帧)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
