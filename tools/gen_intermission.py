#!/usr/bin/env python3
"""Generate the chapter intermission backgrounds (FZBKGRD1-3).

Each 640x400 "case file" summarises the chapter: verdicts, knowledge
points, and the 96110 hotline. Rendered with the Fusion Pixel 12px font.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TTF = ROOT / "vendor/fusion-pixel-2026.11.10/fusion-pixel-12px-proportional-zh_hans.ttf"
OUT = ROOT / "game/graphics"

W, H = 640, 400
SCALE = 2  # render at 2x, downscale with NEAREST for chunky pixels

PAGES = [
    ("FZBKGRD1", "案件卷宗 · 第一章：刷单深渊", "主谋：群主“闪电哥”", [
        "识破点一：垫资刷单",
        "　先给甜头后宰客，凡是垫资的刷单都是诈骗",
        "识破点二：卡单要共享屏幕",
        "　共享屏幕=把银行卡密码拱手送人",
        "",
        "【牢记】刷单本身就是违法行为，",
        "所有“轻松高薪”的兼职刷单都是诈骗。",
        "如遇诈骗，请立即拨打 96110",
    ]),
    ("FZBKGRD2", "案件卷宗 · 第二章：装备黑市", "主谋：黑市商人“暗影”", [
        "识破点一：脱离平台私下交易",
        "　私下转账=放弃一切保障，转完就拉黑",
        "识破点二：低价皮肤钓鱼链接",
        "　索要账号密码的“官方活动”都是钓鱼",
        "",
        "【牢记】游戏交易认准官方渠道，",
        "担保交易才安全，账号密码绝不外借。",
        "如遇诈骗，请立即拨打 96110",
    ]),
    ("FZBKGRD3", "案件卷宗 · 第三章：警服幻影", "主谋：影子会长", [
        "识破点一：“安全账户”",
        "　公检法不设安全账户，要求转账都是诈骗",
        "识破点二：“协查 APP”与保密话术",
        "　真警察不会电话办案；“不许告诉家人”",
        "　恰恰说明他是骗子——告诉家人就是反诈",
        "",
        "【牢记】接到自称公检法的电话，",
        "直接挂断并拨打 96110 核实。",
    ]),
]

GREEN = (96, 255, 144)
WHITE = (236, 246, 240)
GRAY = (150, 160, 155)
YELLOW = (255, 220, 96)


def text_img(lines: list[tuple[str, tuple[int, int, int], int]], width: int) -> Image.Image:
    font = ImageFont.truetype(str(TTF), size=12)
    ascent, descent = font.getmetrics()
    h = ascent + descent
    total = sum((font.getlength(t) * sc // 1 or 1) and max(1, int(font.getlength(t) * sc)) for t, _, sc in lines)
    img = Image.new("RGBA", (max(width, int(total)) + 8, h * len(lines) + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = 4
    for text, color, sc in lines:
        # draw at 1x then scale the glyph pixels via integer resize of the row? keep simple: draw directly at size*sc
        f2 = ImageFont.truetype(str(TTF), size=int(12 * sc))
        d.text((4, y), text, font=f2, fill=(*color, 255), anchor="ls")
        y += int(h * sc) + 6
    px = img.load()
    for yy in range(img.height):
        for xx in range(img.width):
            r, g, b, a = px[xx, yy]
            if a >= 128:
                px[xx, yy] = (r, g, b, 255)
            else:
                px[xx, yy] = (0, 0, 0, 0)
    return img


def page(title: str, culprit: str, points: list[str]) -> Image.Image:
    img = Image.new("RGBA", (W * SCALE, H * SCALE), (10, 14, 18, 255))
    d = ImageDraw.Draw(img)
    # case-file frame
    d.rectangle([8, 8, W * SCALE - 9, H * SCALE - 9], outline=(0, 160, 100), width=4)
    d.rectangle([20, 60, W * SCALE - 21, H * SCALE - 21], outline=(0, 90, 70), width=2)

    title_img = text_img([(title, GREEN, 3)], W * SCALE)
    img.alpha_composite(title_img, (30, 18))

    cul_img = text_img([(culprit, YELLOW, 2)], W * SCALE)
    img.alpha_composite(cul_img, (34, 78))

    body = [(t, WHITE if t.startswith("识破") or t.startswith("　") else GRAY, 2) if t else (" ", WHITE, 2)
            for t in points]
    body_img = text_img(body, W * SCALE)
    img.alpha_composite(body_img, (40, 130))

    hot = text_img([("反诈专线 96110 · 国家反诈中心 APP", YELLOW, 3)], W * SCALE)
    img.alpha_composite(hot, (40, H * SCALE - 90))

    return img.convert("RGB").resize((W, H), Image.Resampling.NEAREST)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, title, culprit, points in PAGES:
        img = page(title, culprit, points)
        path = OUT / f"{name}.png"
        img.save(path)
        print(f"saved {path}")


if __name__ == "__main__":
    main()
