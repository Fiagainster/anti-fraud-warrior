#!/usr/bin/env python3
"""Draw the three custom pickup sprites (placeholder art) and land them.

  python tools/gen_props.py            # 重画母版 + 落位到 game/sprites
  python tools/gen_props.py check      # 只看现状，不写文件

三个物件是流程上必经的（抉择终端 / 证据箱 / 主谋证据），原来借的是
Freedoom 的护甲、背包、蓝钥匙——语义完全错位。这里先画占位图把"借图"
这件事断掉，美术之后按 `art/sprites/<精灵名>/A.png` 覆盖同名母版即可，
尺寸和配色按 docs/角色美术设计.md §4.4 / §5 来。

母版写 art/sprites/（入库），引擎副本写 game/sprites/（入库），
锚点复用 tools/fix_offsets.py 的规则——不要在别处硬编码偏移。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

import fix_offsets

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "art" / "sprites"
GAME = ROOT / "game" / "sprites"

# 配色：一律压暗、低饱和。高饱和只留给玩家武器上的橙条。
INK = (18, 20, 26, 255)        # 1px 描边
STEEL_D = (40, 47, 60, 255)    # 外壳暗面
STEEL = (66, 78, 96, 255)      # 外壳中间调
STEEL_L = (98, 112, 132, 255)  # 外壳亮面
GLASS = (14, 16, 22, 255)      # 屏幕底
CYAN = (95, 208, 216, 255)     # 数据行 / 自发光
CYAN_D = (44, 104, 112, 255)   # 数据行暗部
PAPER = (216, 210, 192, 255)   # 纸、标签
PAPER_D = (160, 152, 132, 255)
RED = (140, 43, 43, 255)       # 封条、公章（压暗的红）
RED_L = (178, 66, 58, 255)


class Canvas:
    """Tiny drawing surface: inclusive integer boxes, 1px outlines, no AA."""

    def __init__(self, w: int, h: int):
        self.im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.px = self.im.load()
        self.w, self.h = w, h

    def rect(self, x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(self.h - 1, y1) + 1):
            for x in range(max(0, x0), min(self.w - 1, x1) + 1):
                self.px[x, y] = c

    def outline(self, x0, y0, x1, y1, c=INK):
        self.rect(x0, y0, x1, y0, c)
        self.rect(x0, y1, x1, y1, c)
        self.rect(x0, y0, x0, y1, c)
        self.rect(x1, y0, x1, y1, c)

    def result(self) -> Image.Image:
        return self.im


# ------------------------------------------------------------- terminal --

def terminal():
    """48x56 立式机柜：下面底座、中间屏幕、顶上红灯表示"有抉择待答"。

    读法靠轮廓：竖长方形 + 一条亮青屏幕。远看是"一台机器"，不是"一坨东西"。
    """
    c = Canvas(48, 56)

    # 底座：比机身宽，让人一眼看出它立在地上
    c.rect(5, 50, 42, 54, STEEL_D)
    c.outline(5, 50, 42, 54)

    # 机身：左边一列亮面，右边压暗，给个体积
    c.rect(7, 3, 40, 49, STEEL)
    c.rect(7, 3, 12, 49, STEEL_L)
    c.rect(34, 3, 40, 49, STEEL_D)
    c.outline(7, 3, 40, 49)

    # 屏幕凹槽
    c.rect(14, 9, 34, 36, GLASS)
    c.outline(14, 9, 34, 36, STEEL_D)

    # 屏幕上的"数据行"：长度不一，像在滚日志
    rows = [(13, 30), (15, 29), (18, 33), (13, 26), (16, 31), (14, 28)]
    for i, (xa, xb) in enumerate(rows):
        y = 12 + i * 4
        c.rect(xa, y, xb, y, CYAN if i % 3 == 0 else CYAN_D)
    # 屏幕底部一条亮青高光，暗示自发光
    c.rect(14, 35, 34, 35, CYAN_D)

    # 指示灯：暗红底 + 亮红点，表示"等你作答"
    c.rect(36, 5, 39, 8, RED)
    c.rect(37, 6, 38, 7, RED_L)

    # 顶部天线
    c.rect(23, 0, 24, 2, STEEL_L)
    c.rect(23, 0, 24, 0, CYAN)

    # 键盘条
    c.rect(14, 40, 34, 46, STEEL_D)
    for x in range(15, 34, 3):
        c.rect(x, 42, x + 1, 44, STEEL)

    return c.result()


# --------------------------------------------------------------- crate --

def evidence():
    """32x24 证物箱：米白箱体 + 红十字封条 + 顶部标签。

    轮廓矮而宽，和终端（竖长）形成对比；红色是唯一的暖色，远看就是个
    "被查封的东西"。
    """
    c = Canvas(32, 24)

    # 箱体
    c.rect(3, 6, 28, 21, PAPER)
    c.rect(3, 17, 28, 21, PAPER_D)   # 下半截压暗，像有厚度
    c.outline(3, 6, 28, 21)

    # 封条：横带压满，竖带偏右。居中的十字会读成"礼物盒丝带"，偏一点才像
    # 一条贴歪的封条胶带。
    c.rect(20, 6, 22, 21, RED)
    c.rect(3, 12, 28, 13, RED)
    c.rect(20, 12, 22, 13, RED_L)    # 交叠处亮一点，别糊成一片

    # 顶上的标签：一张塞在箱子上的纸，压住封条上端
    c.rect(7, 2, 19, 6, PAPER)
    c.outline(7, 2, 19, 6, PAPER_D)
    c.rect(9, 4, 17, 4, PAPER_D)     # 标签上的一行"字"

    # 箱底一道阴影，让它"坐"在地上
    c.rect(4, 22, 27, 22, STEEL_D)
    return c.result()


# ---------------------------------------------------------------- proof --

def master_proof():
    """26x26 主谋证据：一叠账本 + 一枚红章。

    红章是"铁证"的视觉锤——第三章底色是藏蓝，这枚红点是全画面最跳的东西，
    捡它的理由不用文字解释。
    """
    c = Canvas(26, 26)

    # 纸摞：三张错开的边，暗示"一叠"
    for i, (x0, x1, y0) in enumerate(((4, 21, 12), (5, 22, 10), (3, 20, 8))):
        c.rect(x0, y0, x1, 23, PAPER if i % 2 == 0 else PAPER_D)
        c.outline(x0, y0, x1, 23)
    # 账本上的横线（"数字"）
    for y in range(13, 22, 3):
        c.rect(7, y, 18, y, PAPER_D)

    # 红章：切掉四个角，圆形感靠这一手，不然就是个红方块
    c.rect(12, 2, 23, 11, RED)
    for x, y in ((12, 2), (23, 2), (12, 11), (23, 11)):
        c.px[x, y] = (0, 0, 0, 0)
    c.rect(13, 2, 22, 2, RED)
    c.rect(13, 11, 22, 11, RED)
    c.rect(12, 3, 12, 10, RED)
    c.rect(23, 3, 23, 10, RED)
    c.rect(14, 4, 21, 9, RED_L)
    # 章里的图案抽象成一个小十字，别画字（这个尺寸画字必糊）
    c.rect(17, 5, 18, 8, RED)
    c.rect(15, 6, 20, 7, RED)

    # 底部一道书挡阴影
    c.rect(3, 24, 22, 24, STEEL_D)
    return c.result()


# ---------------------------------------------------------------- land --

# 精灵名 → (画布, 生成函数, 一句话说明)
PROPS = [
    ("FZGT", terminal, "抉择终端：立式机柜，屏幕亮青，顶上红灯=有题待答"),
    ("FZEV", evidence, "证据箱：米白箱体 + 红十字封条"),
    ("FZPF", master_proof, "主谋证据：一叠账本 + 一枚红章"),
]


def land(name: str, im: Image.Image, mode: str) -> None:
    """母版进 art/sprites/，引擎副本进 game/sprites/，并按规则写 grAb。

    mode 三档，关键点是 `apply` **绝不覆盖已有母版**：母版一旦被你手画过，
    它就是这个物件的唯一真源，生成器只负责把它同步进引擎并补锚点。
    """
    src = ART / name / "A.png"
    dst = GAME / (name + "A0.png")

    if mode == "check":
        have = "有母版" if src.exists() else "缺母版"
        print("  %-6s %-6s %dx%-3d -> %s" % (name, have, im.width, im.height,
                                             dst.relative_to(ROOT)))
        return

    if mode == "force" or not src.exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        im.save(src)
        action = "重画占位" if mode == "force" else "新建占位"
    else:
        action = "沿用母版"

    im = Image.open(src)                      # 以母版为准，别用刚生成的
    im.save(dst)                              # 引擎副本到这里还是裸 PNG
    hotx, hoty = fix_offsets.desired_offset(name, im.width, im.height)
    fix_offsets.rewrite(dst, hotx, hoty, backup=False)   # 写 grAb
    print("  %-6s %-8s %dx%-3d  grAb=(%d,%d)"
          % (name, action, im.width, im.height, hotx, hoty))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv else "apply"
    if mode not in ("check", "apply", "force"):
        raise SystemExit("usage: gen_props.py [check|apply|force]\n"
                         "  check  只报告，不写文件\n"
                         "  apply  生成缺的占位，同步已有母版到引擎并补锚点\n"
                         "  force  连已有母版一起重画成占位（会覆盖手画的图）")
    print({"check": "核对", "apply": "同步", "force": "强制重画"}[mode]
          + " 三个自定义物件")
    for name, fn, note in PROPS:
        print(" ", note)
        land(name, fn(), mode)
    if mode != "check":
        print("\n锚点已按 tools/fix_offsets.py 的规则写入；"
              "复跑 `fix_offsets.py check` 应报 0 need offset")
    return 0


if __name__ == "__main__":
    sys.exit(main())
