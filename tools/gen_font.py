#!/usr/bin/env python3
"""Generate GZDoom Unicode folder fonts from a TTF.

Output layout:
    game/fonts/fzfont/<HEX_CODEPOINT>.png          (white)
    game/fonts/fzfont_red/<HEX_CODEPOINT>.png      (pre-colored)
    game/fonts/fzfont_blue/...
    game/fonts/fzfont_gold/...
    game/fonts/fzfont_green/...
    game/fonts/fzfont_cyan/...
    game/fonts/fzfont_yellow/...
    game/fonts/fzfont_gray/...

Why pre-colored fonts? GZDoom's palette translations (Font.CR_RED etc.)
darken truecolor folder-font glyphs. Baking the color into the glyph is
deterministic and keeps the pixel-art look.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_TTF = Path("vendor/fusion-pixel-2026.11.10/fusion-pixel-12px-proportional-zh_hans.ttf")
DEFAULT_SIZE = 12
FONT_ROOT = Path("game/fonts")

# Extra ZScript sources whose quoted strings must be covered by the font.
SCAN_SOURCES = [
    Path("game/zscript/fz_gates.zs"),
    Path("game/zscript/fz_hud.zs"),
    Path("game/zscript/fz_defs.zs"),
]

def collect_charset() -> str:
    """Base charset + every char found in quoted strings of SCAN_SOURCES."""
    import re
    base = set(CHARSET)
    for src in SCAN_SOURCES:
        if not src.exists():
            continue
        text = src.read_text(encoding="utf-8")
        for m in re.findall(r'"([^"]*)"', text):
            for ch in m:
                if not ch.isspace():
                    base.add(ch)
    return "".join(sorted(base))

COLORS: dict[str, tuple[int, int, int]] = {
    "fzfont": (255, 255, 255),
    "fzfont_red": (255, 72, 72),
    "fzfont_blue": (96, 168, 255),
    "fzfont_gold": (255, 200, 72),
    "fzfont_green": (96, 255, 144),
    "fzfont_cyan": (96, 224, 255),
    "fzfont_yellow": (255, 236, 96),
    "fzfont_gray": (176, 176, 176),
}

# Characters used by the demo UI and test strings. Extend this list freely.
CHARSET = (
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    ":/%.,!?-+()[]<>#*_=|"
    "，。！？：；、（）《》“”‘’·—…"
    "反诈战士警惕值防骗盾证据案件进度任务目标分数时间生命护甲弹药钥匙线索骗局识破失误安全危险提示电话网络转账刷单返利客服群主托儿警察银行冻结链喇叭国家中心"
    "开始继续退出设置帮助返回重试得分评级知识档案行动简报结算成功失败完成已达成未达成"
    "操作说明读取保存新游戏载入存档主菜单确认取消是否宣传互动游戏"
    "当前等级骗术虚假投资理财冒充公检法杀猪盘养老换脸不要垫付共享屏幕点击链接陌生来电个人信息汇款多核实"
    "第一二三四五关共层进入到离开启关闭门宝箱你好欢迎勇士特勤探员"
    "预防预警举报止损挽回金额案例复盘教训牢记"
)


def render_glyphs(ttf: Path, out_dir: Path, size: int, color: tuple[int, int, int], charset: str) -> tuple[int, int, int]:
    font = ImageFont.truetype(str(ttf), size=size)
    ascent, descent = font.getmetrics()
    height = ascent + descent
    space_width = max(1, int(round(font.getlength(" "))))

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()

    seen: set[str] = set()
    generated = 0
    for ch in charset:
        if ch.isspace() or ch in seen:
            continue
        seen.add(ch)
        code = ord(ch)
        advance = max(1, int(round(font.getlength(ch))))
        img = Image.new("RGBA", (advance, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((0, ascent), ch, font=font, fill=(*color, 255), anchor="ls")

        # Pixel fonts should be 1-bit; kill FreeType's grey edge pixels.
        px = img.load()
        for y in range(height):
            for x in range(advance):
                r, g, b, a = px[x, y]
                px[x, y] = (*color, 255) if a >= 128 else (0, 0, 0, 0)

        img.save(out_dir / f"{code:04X}.png")
        generated += 1

    (out_dir / "font.inf").write_text(
        f"FontHeight {height}\nSpaceWidth {space_width}\n",
        encoding="ascii",
    )
    return generated, height, space_width


def render_preview(ttf: Path, size: int, path: Path) -> None:
    font = ImageFont.truetype(str(ttf), size=size)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    lines = [
        "反诈战士 警惕值 100",
        "防骗盾 50  证据 30",
        "案件进度 1/5  识破骗局 3",
        "提示：不要垫付，不要共享屏幕",
        "96110 国家反诈中心",
    ]
    img = Image.new("RGBA", (260, line_h * len(lines) + 12), (16, 16, 16, 255))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((4, 4 + ascent + i * line_h), line, font=font, fill=(255, 255, 255, 255), anchor="ls")
    img = img.resize((img.width * 3, img.height * 3), Image.Resampling.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ttf", type=Path, default=DEFAULT_TTF)
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE)
    parser.add_argument("--preview", type=Path, default=Path("build/font_preview.png"))
    args = parser.parse_args()

    if not args.ttf.exists():
        raise SystemExit(f"TTF not found: {args.ttf}")

    charset = collect_charset()
    print(f"charset: {len(charset)} chars")
    for name, color in COLORS.items():
        count, height, space = render_glyphs(args.ttf, FONT_ROOT / name, args.size, color, charset)
        print(f"{name}: {count} glyphs, height={height}, space={space}")

    render_preview(args.ttf, args.size, args.preview)
    print(f"preview -> {args.preview}")


if __name__ == "__main__":
    main()
