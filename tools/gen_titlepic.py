#!/usr/bin/env python3
"""Generate the title screen (TITLEPIC): 640x480 with the emblem slot."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TTF = ROOT / "vendor/fusion-pixel-2026.11.10/fusion-pixel-12px-proportional-zh_hans.ttf"
EMBLEM = ROOT / "build/emblem.png"
OUT = ROOT / "game/graphics/TITLEPIC.png"

W, H = 640, 480


def main() -> None:
    img = Image.new("RGBA", (W, H), (8, 11, 16, 255))
    d = ImageDraw.Draw(img)
    # subtle grid backdrop (data-space vibe)
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=(14, 20, 26))
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=(14, 20, 26))
    # emblem: Blender render if present, else a drawn shield
    if EMBLEM.exists():
        em = Image.open(EMBLEM).convert("RGBA")
        em = em.resize((220, 220), Image.Resampling.NEAREST)
        img.alpha_composite(em, ((W - 220) // 2, 30))
    else:
        d.polygon([(W // 2, 40), (W // 2 + 90, 80), (W // 2 + 90, 170),
                   (W // 2, 220), (W // 2 - 90, 170), (W // 2 - 90, 80)],
                  fill=(12, 24, 20), outline=(0, 200, 120))
        d.text((W // 2, 120), "FZ", font=ImageFont.truetype(str(TTF), 48),
               fill=(96, 255, 144), anchor="mm")

    f_big = ImageFont.truetype(str(TTF), 64)
    f_sub = ImageFont.truetype(str(TTF), 16)
    d.text((W // 2, 280), "反诈战士", font=f_big, fill=(96, 255, 144), anchor="mm")
    d.text((W // 2, 340), "净网行动 · 三章演示", font=f_sub, fill=(236, 246, 240), anchor="mm")
    d.text((W // 2, 380), "刷单深渊 · 装备黑市 · 警服幻影", font=f_sub,
           fill=(150, 200, 170), anchor="mm")
    d.text((W // 2, 430), "按 ENTER 开始行动", font=f_sub, fill=(255, 220, 96), anchor="mm")
    d.text((W - 12, H - 12), "96110", font=ImageFont.truetype(str(TTF), 14),
           fill=(255, 220, 96), anchor="rd")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(OUT)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
