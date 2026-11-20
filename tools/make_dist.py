#!/usr/bin/env python3
"""Build the distributable demo folder (and zip) from the repo.

Layout of dist/fanzha-demo-v0.1:
  uzdoom.exe + engine pk3s/dlls   (vendor/uzdoom-5.0.3)
  freedoom1.wad                   (vendor/freedoom-0.13.0, BSD)
  fanzha-demo.pk3                 (build/, our content)
  maps/FZ01-03.wad                (build/maps)
  uzdoom.cfg                      (known-good config incl. Escape=menu_main)
  run.bat                         (ASCII launcher)
  README.txt                      (player-facing, UTF-8 BOM)
  docs/剧情.md                     (design/story)
  LICENSES/                       (engine + iwad + font licenses)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
NAME = "fanzha-demo-v0.1"
PKG = DIST / NAME

ENGINE = ROOT / "vendor/uzdoom-5.0.3"
IWAD = ROOT / "vendor/freedoom-0.13.0/freedoom1.wad"
FONT_DIR = ROOT / "vendor/fusion-pixel-2026.11.10"

ENGINE_FILES = [
    "uzdoom.exe", "uzdoom.pk3", "game_support.pk3", "lights.pk3",
    "brightmaps.pk3", "game_widescreen_gfx.pk3",
    "libcurl-x64.dll", "sndfile.dll", "soft_oal.dll",
]

RUN_BAT = """@echo off
setlocal
rem Keep this file pure ASCII: cmd.exe parses .bat in the system code page.
cd /d "%~dp0"

if not exist "uzdoom.exe" goto missing
if not exist "freedoom1.wad" goto missing
if not exist "fanzha-demo.pk3" goto missing

start "" "uzdoom.exe" -config "uzdoom.cfg" -iwad "freedoom1.wad" ^
 -file "maps\\FZ01.wad" -file "maps\\FZ02.wad" -file "maps\\FZ03.wad" ^
 -file "fanzha-demo.pk3" ^
 +set vid_fullscreen 0 +set vid_defwidth 1280 +set vid_defheight 720 ^
 +set language "zh-Hans" +set gl_texture_filter 0
exit /b 0

:missing
echo [Anti-Fraud Warrior] Files missing. Re-extract the whole package.
pause
exit /b 1
"""

README = """反诈战士 · 三章试玩版 v0.1
=================================

一款用 DOOM 引擎制作的反诈宣传 FPS（公安 / 社区 / 校园向）。

启动
----
双击 run.bat（窗口 1280x720）。标题画面按回车 → 选章节 → 开始。

操作
----
W A S D        移动
鼠标            转向
鼠标左键        开火
E              使用（开门 / 出口开关）
空格           使用（备用）
ESC            打开主菜单（注意：需要按住约 2 秒）
               UZDoom 的按键重复机制会吞掉短按，长按即可稳定弹出
↑ ↓ / 回车      菜单选择与确认

玩法
----
走近发光的「数据终端」会自动弹出抉择菜单（↑↓ 选择，回车确认）。
- 选对：防骗盾 +10、证据 +1，获得关卡进度
- 选错：警惕值 -25，并会引来妖魔伏击
竞技场北侧三个小房间各有 1 件证据，集齐 3 件获得「证据链」（红卡）。
红卡门后是本章 Boss；击败后拾取主谋证据，到出口开关（E）结案。
三章：刷单深渊 / 装备黑市 / 警服幻影，每章结束有案件卷宗结算页。

提示：游戏内按 F1 可看物品帮助；如遇启动崩溃，删除
%LOCALAPPDATA%\\doom\\uzdoom\\vulkanpipelinecache 后重试。

内容说明
--------
- 敌人 / 武器模型仍为 Freedoom 占位素材（后续替换为 Blender 渲染的
  反诈主题角色）
- 抉择菜单目前仅键盘操作
- 本包为宣传演示用途；剧情与知识点见 docs/剧情.md

许可
----
UZDoom 5.0.3        GPL-3.0（源码见 https://github.com/UZDoom/UZDoom）
Freedoom 0.13.0     BSD 3-Clause（freedoom1.wad）
Fusion Pixel 字体    SIL Open Font License 1.1
本作剧情 / 地图 / 脚本 / 界面素材：项目自产
详见 LICENSES/ 目录。
"""


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def main() -> int:
    # always package from freshly generated content
    run([sys.executable, "-I", "tools/gen_maps.py"])
    run([sys.executable, "-I", "tools/build.py"])

    if PKG.exists():
        shutil.rmtree(PKG)
    (PKG / "maps").mkdir(parents=True)
    (PKG / "docs").mkdir()
    (PKG / "LICENSES").mkdir()

    for name in ENGINE_FILES:
        src = ENGINE / name
        if src.exists():
            shutil.copy2(src, PKG / name)
        else:
            print(f"WARN missing engine file: {src}")
    shutil.copy2(IWAD, PKG / "freedoom1.wad")
    shutil.copy2(ROOT / "build/fanzha-demo.pk3", PKG / "fanzha-demo.pk3")
    for w in ("FZ01.wad", "FZ02.wad", "FZ03.wad"):
        shutil.copy2(ROOT / "build/maps" / w, PKG / "maps" / w)

    # known-good config: has Escape=menu_main, backtick=toggleconsole,
    # WASD/mouse binds, windowed 1280x720, zh-Hans, nearest filtering
    shutil.copy2(ROOT / "config/uzdoom.cfg", PKG / "uzdoom.cfg")

    (PKG / "run.bat").write_text(RUN_BAT, encoding="ascii", newline="\r\n")
    (PKG / "README.txt").write_text(README, encoding="utf-8-sig",
                                    newline="\r\n")

    story = ROOT / "docs/剧情.md"
    if story.exists():
        shutil.copy2(story, PKG / "docs/剧情.md")
    checklist = ROOT / "docs/晨间验收清单.md"
    if checklist.exists():
        shutil.copy2(checklist, PKG / "docs/验收清单.md")
    handoff = ROOT / "docs/开发日志-2026-11-20.md"
    if handoff.exists():
        shutil.copy2(handoff, PKG / "docs/开发日志.md")

    lic = PKG / "LICENSES"
    for src, dst in [
        (ENGINE / "licenses.zip", "uzdoom-licenses.zip"),
        (ROOT / "vendor/freedoom-0.13.0/COPYING.txt", "freedoom-COPYING.txt"),
        (ROOT / "vendor/freedoom-0.13.0/CREDITS.txt", "freedoom-CREDITS.txt"),
    ]:
        if src.exists():
            shutil.copy2(src, lic / dst)
    for p in FONT_DIR.glob("*OFL*"):
        shutil.copy2(p, lic / p.name)
    for name in ("OFL.txt", "LICENSE"):
        p = FONT_DIR / name
        if p.exists():
            shutil.copy2(p, lic / f"fusion-pixel-{name}")

    print(f"\npackage ready: {PKG}")
    total = sum(f.stat().st_size for f in PKG.rglob("*") if f.is_file())
    print(f"files: {sum(1 for f in PKG.rglob('*') if f.is_file())}, "
          f"{total/1e6:.1f} MB")

    # zip next to the folder (ASCII name for portability)
    zpath = DIST / (NAME + ".zip")
    if zpath.exists():
        zpath.unlink()
    shutil.make_archive(str(DIST / NAME), "zip", root_dir=str(DIST),
                        base_dir=NAME)
    print(f"zip: {zpath}  {zpath.stat().st_size/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
