#!/usr/bin/env python3
"""Replace Doom's English main-menu patches with Chinese PNGs.

The stock menu uses patch graphics (M_NGAME, M_OPTION, ...), not text.
Overriding those texture names keeps the original menu layout, skull
selector and hotkeys while making every entry Chinese.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TTF = Path("vendor/fusion-pixel-2026.11.10/fusion-pixel-12px-proportional-zh_hans.ttf")
OUT = Path("game/graphics")
SIZE = 12

# name, width, height, text, scale, color
PATCHES = [
    ("M_DOOM", 159, 37, "反诈战士", 3, (96, 255, 144)),
    ("M_NGAME", 88, 15, "开始行动", 1, (236, 246, 240)),
    ("M_OPTION", 78, 15, "设置", 1, (236, 246, 240)),
    ("M_LOADG", 98, 15, "读取进度", 1, (236, 246, 240)),
    ("M_SAVEG", 98, 15, "保存进度", 1, (236, 246, 240)),
    ("M_RDTHIS", 98, 15, "操作说明", 1, (236, 246, 240)),
    ("M_QUITG", 98, 15, "退出", 1, (236, 246, 240)),
]


def render_line(text: str, color: tuple[int, int, int], scale: int) -> Image.Image:
    font = ImageFont.truetype(str(TTF), size=SIZE)
    ascent, descent = font.getmetrics()
    height = ascent + descent
    width = max(1, int(round(font.getlength(text))))
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((0, ascent), text, font=font, fill=(*color, 255), anchor="ls")

    px = img.load()
    for y in range(height):
        for x in range(width):
            r, g, b, a = px[x, y]
            px[x, y] = (*color, 255) if a >= 128 else (0, 0, 0, 0)

    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    return img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, width, height, text, scale, color in PATCHES:
        panel = Image.new("RGBA", (width, height), (6, 10, 14, 214))
        draw = ImageDraw.Draw(panel)
        draw.rectangle([0, 0, width - 1, 0], fill=(0, 200, 120, 255))
        draw.rectangle([0, height - 1, width - 1, height - 1], fill=(0, 70, 55, 255))

        line = render_line(text, color, scale)
        x = (width - line.width) // 2
        y = (height - line.height) // 2
        panel.alpha_composite(line, (x, y))
        panel.save(OUT / f"{name}.png")
        print(f"{name}.png {width}x{height} <- {text}")


if __name__ == "__main__":
    main()
