#!/usr/bin/env python3
"""Give every sprite PNG the `grAb` chunk the engine actually reads.

  python tools/fix_offsets.py check     # 只报告，不改文件
  python tools/fix_offsets.py apply     # 写入 grAb（原图备份到 _staging/offsets_bak）

为什么非做不可：UZDoom 的 PNG 精灵只在 PNG 里存在 `grAb`（grab）块时才用里面
的偏移，否则一律按 (0,0) 处理。而 (0,0) 的语义是"图片左边缘对齐角色中心、
图片顶部对齐角色头顶"，于是每张图都会向右偏半个身位、双脚扎进地板——玩家
看到的就是"怪物埋在地里只露半个身子"。

偏移规则（与 Doom 传统 patch 一致，真值见下方注释）：
  人形怪        (w/2, h-4)      水平居中，脚底埋进地板 4px 免得看着发飘
  地上道具      (w/2, h)        水平居中，图片底边正好落在原点
  第一人称武器  (w/2-160, h-148) 另一套坐标系，见 WEAPON_BOTTOM_ROW
  弹道/烟/爆炸  (w/2, h/2)      没有"脚"，水平和垂直都居中
"""
from __future__ import annotations

import shutil
import struct
import sys
import zlib
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPR = ROOT / "game" / "sprites"
BAK = ROOT / "_staging" / "offsets_bak"

# 第一人称武器：单独一套坐标系，见 WEAPON_BOTTOM_ROW。
WEAPONS = {"PISG", "SHTG", "CHGG", "MISG", "PLSG", "BFGG", "SAWG"}
# 火球/爆炸/烟：没有"脚"，水平和垂直都居中即可。
AIMLESS = {"BAL1", "BAL2", "BAL7", "PUFF", "PLSS", "PLSE", "MISL", "BFS1",
           "TFOG", "FATB", "MANB", "BAL3", "BAL4", "BAL5", "BAL6"}
PNG_SIG = b"\x89PNG\r\n\x1a\n"


def parse_name(stem: str):
    s = stem.upper()
    if len(s) != 6:
        return None
    return s[:4]


def chunk(kind: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))


def split_chunks(data: bytes):
    """Yield (kind, payload) for every chunk, signature excluded."""
    i = 8
    while i < len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        kind = data[i + 4:i + 8]
        payload = data[i + 8:i + 8 + ln]
        yield kind, payload
        i += 12 + ln
        if kind == b"IEND":
            break


# 第一人称武器（psprite）跟场景精灵不是一套坐标系，得单独算：
#
#   src/common/textures/gametexture.cpp:SetSpriteRect()
#       mSpriteRect.left = -LeftOffset;  .top = -TopOffset;      // 取负
#   src/rendering/hwrenderer/scene/hw_weapon.cpp:GetWeaponRect()
#       tx = sx - (160 - r.left);  x1 = tx * scalex + vw / 2;    // sx 默认 0
#       ftexturemid = 100 - sy - r.top;  y1 = vh/2 - ftexturemid * scale;
#
# 水平方向代进去很干净（把 160 当虚拟屏 320 宽的中线）：
#   x1 = (LeftOffset - 160) * scalex + 160   -> 图片左边缘的屏幕坐标
# 想让 w 宽的枪水平居中，x1 = 160 - w*0.375，反解得 LeftOffset = w/2 - 160。
#
# 垂直方向算不准：y1 里除了 TopOffset 还有个 (vh/2 - 100*scale) 的常数项，
# 而 vh 是"扣掉状态栏之后"的视口高，引擎没把它暴露出来。所以 VH_WEAPON_BOTTOM
# 是拿截图反推的（先让枪飘在屏幕中间量一次、再落到 HUD 上量一次，线性解方程），
# 不是从公式里算出来的。换 HUD 高度就得重新标定。
#
# 原版参照（freedoom1.wad 的 patch 头 w,h,left,top）：
#   PISGA0  82x 92  left=-125  top= -97
#   SHTGA0  67x 62  left=-122  top=-107
#   SAWGA0  96x132  left=-176  top= -60
# 都是「负的、量级一百多」，因为武器是相对屏幕中线画的。
VW_CENTER = 160          # 虚拟屏半宽，武器水平居中的基准
WEAPON_BOTTOM_ROW = 148  # 标定值：枪底边落在 320x200 虚拟屏的哪一行
FIGURE_SINK = 4          # 人形怪脚底埋进地板几像素，抄原版 POSSA1/TROOA1

# 场景精灵（怪物/道具）的原版真值，从 vendor/freedoom-0.13.0/freedoom1.wad
# 的 patch 头 (w,h,left,top) 直接读出来的，不是估的：
#   POSSA1  41x57  left=22 top=53   -> left=w/2, top=h-4
#   TROOA1  48x60  left=23 top=56   -> 同上
#   SARGA1  38x59  left=17 top=55   -> 同上
#   BOSSA1  49x69  left=24 top=69   -> top=h
#   MEDIA0  29x20  left=14 top=20   -> top=h
#   CLIPA0   7x12  left= 4 top=12   -> top=h
#   STIMA0  19x10  left=10 top=10   -> top=h
# 也就是说：left 永远取 w/2；top 取 h（道具）或 h-4（人形怪）。
# 写 0 等于把整张图挂在原点下方，64 高的怪就会埋到胸口——之前就是这个错。


def desired_offset(name: str, w: int, h: int) -> tuple[int, int]:
    if name in WEAPONS:
        return w // 2 - VW_CENTER, h - WEAPON_BOTTOM_ROW
    if name in AIMLESS:
        return w // 2, h // 2
    if name.startswith("FZ"):
        # 人形怪：原版统一是 top = h-4，脚多半档埋进地板，站着才不像飘。
        return w // 2, h - FIGURE_SINK
    # 地上道具：top = h，图片底边正好落在原点（原版 MEDI/CLIP/STIM 都是 top=h）。
    return w // 2, h


def read_grab(data: bytes):
    for kind, payload in split_chunks(data):
        if kind == b"grAb" and len(payload) >= 8:
            return struct.unpack(">ii", payload[:8])
    return None


def rewrite(path: Path, hotx: int, hoty: int, backup: bool) -> None:
    data = path.read_bytes()
    if not data.startswith(PNG_SIG):
        raise SystemExit("%s is not a PNG" % path.name)
    out = bytearray(PNG_SIG)
    inserted = False
    for kind, payload in split_chunks(data):
        if kind == b"grAb":
            continue                     # 旧的要丢掉，后面重写一份
        out += chunk(kind, payload)
        if kind == b"IHDR" and not inserted:
            out += chunk(b"grAb", struct.pack(">ii", hotx, hoty))
            inserted = True
    if backup:
        BAK.mkdir(parents=True, exist_ok=True)
        dst = BAK / path.name
        if not dst.exists():
            shutil.copy2(path, dst)
    path.write_bytes(bytes(out))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv else "check"
    apply = mode == "apply"
    if mode not in ("check", "apply"):
        raise SystemExit("usage: fix_offsets.py [check|apply]")

    rows, changed = [], 0
    for p in sorted(SPR.rglob("*.png")):
        name = parse_name(p.stem)
        if name is None:
            print("SKIP %s: 文件名不是 4字符+帧+旋转" % p.name)
            continue
        with Image.open(p) as im:
            w, h = im.size
        want = desired_offset(name, w, h)
        have = read_grab(p.read_bytes())
        if have != want:
            changed += 1
            if apply:
                rewrite(p, want[0], want[1], backup=True)
        rows.append((p.name, name, w, h, want, have, have == want))

    for fname, name, w, h, want, have, ok in rows:
        if ok and not apply:
            continue
        print("%-14s %-5s %3dx%-3d want %-9s have %s"
              % (fname, name, w, h, "%d,%d" % want,
                 "%d,%d" % have if have else "-"))
    print("\n%d sprite(s), %d need offset" % (len(rows), changed)
          + (", all rewritten" if apply and changed else ""))
    if not apply and changed:
        print("run: python tools/fix_offsets.py apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
