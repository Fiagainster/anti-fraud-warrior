#!/usr/bin/env python3
"""Build the title screen and the attract-mode credit pages.

The cover illustration is AI-generated art (registered in assets_src/CREDITS.md);
everything readable on top of it is drawn here with the Fusion Pixel font, because
image models cannot set Chinese text reliably.

    python tools/gen_title.py

Outputs (1920x1080, 16:9):
    game/graphics/TITLEPIC.png   title screen
    game/graphics/FZCRED1.png    attract page 1: the three chapters
    game/graphics/FZCRED2.png    attract page 2: anti-fraud reminders
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TTF = ROOT / "vendor/fusion-pixel-2026.11.10/fusion-pixel-12px-proportional-zh_hans.ttf"
ART = ROOT / "art/title/cover.jpg"
ENDING_ART = ROOT / "art/title/ending.jpg"
GFX = ROOT / "game/graphics"

W, H = 1920, 1080
GREEN = (126, 255, 158)
WHITE = (238, 246, 240)
MUTED = (150, 196, 170)
AMBER = (255, 214, 92)
INK = (5, 9, 13)
BG = (7, 12, 19)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(TTF), size)


def scrim(img: Image.Image) -> Image.Image:
    """Top-left falloff plus a bottom band, so text always sits on dark pixels."""
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    diag = (xx / w) * 0.62 + (yy / h) * 0.38
    top = np.clip(1.0 - diag / 0.62, 0.0, 1.0) ** 1.7 * 205.0
    bottom = np.clip((yy - (h - 280)) / 280.0, 0.0, 1.0) ** 1.3 * 185.0
    a = np.clip(np.maximum(top, bottom), 0, 255).astype(np.uint8)
    layer = Image.new("RGBA", (w, h), (4, 8, 14, 0))
    layer.putalpha(Image.fromarray(a, "L"))
    return Image.alpha_composite(img.convert("RGBA"), layer)


def pixelize(img: Image.Image, colors: int = 56) -> Image.Image:
    return (img.convert("RGB")
            .quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
            .convert("RGB"))


def outlined(d: ImageDraw.ImageDraw, xy, s, f, fill, ow=3):
    x, y = xy
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx or dy:
                d.text((x + dx, y + dy), s, font=f, fill=INK)
    d.text((x, y), s, font=f, fill=fill)


def fit_crop(img: Image.Image) -> Image.Image:
    target = W / H
    w, h = img.size
    if w / h > target:
        nw = int(h * target)
        img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / target)
        img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return img.resize((W, H), Image.LANCZOS)


def titlepic() -> None:
    img = scrim(fit_crop(Image.open(ART).convert("RGB")))
    d = ImageDraw.Draw(img)
    outlined(d, (110, 64), "反诈战士", font(132), GREEN, 4)
    d.text((116, 236), "净网行动 · 三章演示", font=font(32), fill=WHITE)
    d.text((116, 286), "刷单深渊 · 装备黑市 · 警服幻影", font=font(26), fill=MUTED)
    d.line([(110, 906), (700, 906)], fill=GREEN, width=3)
    outlined(d, (110, 926), "按 ENTER 开始行动", font(38), AMBER, 3)
    d.text((W - 40, H - 44), "96110", font=font(24), fill=AMBER, anchor="rs")
    out = GFX / "TITLEPIC.png"
    pixelize(img).save(out)
    print(f"{out}  {out.stat().st_size / 1024:.0f} KB")


def page_base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 同一套网格底纹，和游戏内的数据风一致
    for x in range(0, W, 60):
        d.line([(x, 0), (x, H)], fill=(10, 17, 26))
    for y in range(0, H, 60):
        d.line([(0, y), (W, y)], fill=(10, 17, 26))
    d.text((110, 70), "反诈战士 · 净网行动", font=font(26), fill=MUTED)
    d.line([(110, 116), (W - 110, 116)], fill=(22, 58, 40), width=2)
    d.text((W - 40, H - 44), "96110", font=font(24), fill=AMBER, anchor="rs")
    return img, d


def cred_page1() -> None:
    img, d = page_base()
    d.text((110, 190), "三章行动", font=font(96), fill=GREEN)
    rows = [
        ("第一章", "刷单深渊", "流水线一样的刷单群，越刷越深"),
        ("第二章", "装备黑市", "油滑的市集与中介，句句是套"),
        ("第三章", "警服幻影", "冒充公检法的「权威」，最像真的那个"),
    ]
    y = 380
    for num, name, desc in rows:
        d.text((116, y), num, font=font(30), fill=AMBER)
        d.text((260, y - 14), name, font=font(52), fill=WHITE)
        d.text((260, y + 62), desc, font=font(28), fill=MUTED)
        d.line([(116, y + 130), (W - 116, y + 130)], fill=(20, 46, 34), width=2)
        y += 180
    d.text((116, 960), "每章三道抉择 · 选错掉警惕值 · 集齐证据才能开门", font=font(28), fill=GREEN)
    out = GFX / "FZCRED1.png"
    img.save(out)
    print(f"{out}  {out.stat().st_size / 1024:.0f} KB")


def cred_page2() -> None:
    img, d = page_base()
    d.text((110, 190), "记住三条", font=font(96), fill=GREEN)
    rows = [
        ("01", "刷单返利，都是诈骗", "先给甜头的单子，后面一定是垫付"),
        ("02", "高额回报，先想本金", "收益越离谱，钱越拿不回来"),
        ("03", "96110 来电，别挂", "说明你可能已经被盯上了"),
    ]
    y = 390
    for num, head, sub in rows:
        d.text((116, y), num, font=font(44), fill=AMBER)
        d.text((240, y - 10), head, font=font(50), fill=WHITE)
        d.text((240, y + 62), sub, font=font(28), fill=MUTED)
        y += 175
    d.text((116, 960), "遇到可疑情况，拨打 96110 反诈专线", font=font(30), fill=AMBER)
    out = GFX / "FZCRED2.png"
    img.save(out)
    print(f"{out}  {out.stat().st_size / 1024:.0f} KB")


def endpic() -> None:
    """终章图：片尾最后一张，按任意键回标题。"""
    img = scrim(fit_crop(Image.open(ENDING_ART).convert("RGB")))
    d = ImageDraw.Draw(img)
    outlined(d, (110, 90), "净网行动 · 完", font(108), GREEN, 4)
    d.text((116, 250), "刷单深渊 · 装备黑市 · 警服幻影", font=font(28), fill=MUTED)
    d.line([(110, 906), (700, 906)], fill=GREEN, width=3)
    outlined(d, (110, 926), "按任意键返回标题", font(38), AMBER, 3)
    d.text((W - 40, H - 44), "96110", font=font(24), fill=AMBER, anchor="rs")
    out = GFX / "FZENDPIC.png"
    pixelize(img).save(out)
    print(f"{out}  {out.stat().st_size / 1024:.0f} KB")


def castbg() -> None:
    """怪物巡礼的底图：引擎会在正中央画演员，提示条放顶部避开。"""
    img = Image.new("RGB", (W, H), (6, 9, 14))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 60):
        d.line([(x, 0), (x, H)], fill=(10, 16, 24))
    for y in range(0, H, 60):
        d.line([(0, y), (W, y)], fill=(10, 16, 24))
    d.text((110, 74), "反诈战士 · 净网行动", font=font(24), fill=MUTED)
    d.line([(110, 118), (W - 110, 118)], fill=(22, 58, 40), width=2)
    d.text((110, 150), "按 使用键 / 回车：让当前这个倒下，看下一个", font=font(28), fill=GREEN)
    d.text((110, 196), "ESC：打开菜单，可退出或回标题", font=font(26), fill=(128, 156, 140))
    d.line([(110, H - 120), (W - 110, H - 120)], fill=(20, 44, 32), width=2)
    d.text((110, H - 96), "三章结束 · 主谋伏法", font=font(26), fill=MUTED)
    d.text((W - 40, H - 44), "96110", font=font(24), fill=AMBER, anchor="rs")
    out = GFX / "FZCASTBG.png"
    img.save(out)
    print(f"{out}  {out.stat().st_size / 1024:.0f} KB")


def main() -> int:
    GFX.mkdir(parents=True, exist_ok=True)
    if not ART.exists():
        raise SystemExit(f"missing cover art: {ART}")
    if not ENDING_ART.exists():
        raise SystemExit(f"missing ending art: {ENDING_ART}")
    titlepic()
    cred_page1()
    cred_page2()
    endpic()
    castbg()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
