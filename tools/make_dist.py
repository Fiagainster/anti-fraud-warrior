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
setlocal EnableExtensions
rem Keep this file pure ASCII: cmd.exe parses .bat in the system code page.
rem Never trust the caller's working directory: anchor everything on %~dp0.

set "HERE=%~dp0"
pushd "%HERE%" 2>nul
if errorlevel 1 goto nodir

rem Double-clicking run.bat from inside a zip preview makes Explorer extract
rem only this .bat to a temp folder, so every game file looks "missing".
if /i not "%HERE%"=="%HERE:AppData\\Local\\Temp=%" goto inzip

set "STOP="
call :need "uzdoom.exe"      "game engine"
call :need "freedoom1.wad"   "game data"
call :need "fanzha-demo.pk3" "game content"
call :need "uzdoom.cfg"      "default settings"
call :need "maps\\FZ01.wad"   "chapter 1"
call :need "maps\\FZ02.wad"   "chapter 2"
call :need "maps\\FZ03.wad"   "chapter 3"
if defined STOP goto missing

rem uzdoom.cfg is a read-only template. The engine rewrites the file it is
rem handed via -config, so play on a copy - delete fz-settings.cfg to reset.
if not exist "fz-settings.cfg" copy "uzdoom.cfg" "fz-settings.cfg" >nul

start "" "uzdoom.exe" -config "fz-settings.cfg" -iwad "freedoom1.wad" ^
 -file "maps\\FZ01.wad" -file "maps\\FZ02.wad" -file "maps\\FZ03.wad" ^
 -file "fanzha-demo.pk3" ^
 +set vid_fullscreen 0 +set vid_defwidth 1280 +set vid_defheight 720 ^
 +set language "zh-Hans" +set gl_texture_filter 0
if errorlevel 1 goto nocreate
popd
exit /b 0

:need
if exist "%~1" exit /b 0
echo   missing: %~1  (%~2)
echo     expected at %HERE%%~1
set "STOP=1"
exit /b 0

:inzip
echo [Anti-Fraud Warrior] This window runs from a temporary folder inside the ZIP.
echo Please EXTRACT the whole ZIP to a normal folder, then double-click run.bat there.
pause
popd
exit /b 1

:nodir
echo [Anti-Fraud Warrior] Cannot open the folder that holds this file:
echo   %HERE%
echo Try extracting to a simple path such as D:\\fanzha and run again.
pause
exit /b 1

:missing
echo.
echo [Anti-Fraud Warrior] Files missing. Re-extract the whole package.
echo If ONLY uzdoom.exe is reported, an antivirus (Defender / 360 / Huorong)
echo probably quarantined it: restore it from the quarantine list, whitelist
echo this folder, then run run.bat again. Details in README.txt.
pause
popd
exit /b 1

:nocreate
echo [Anti-Fraud Warrior] uzdoom.exe could not start. See README.txt.
pause
popd
exit /b 1
"""

README = """反诈战士 · 三章试玩版 v0.1
=================================

一款用 DOOM 引擎制作的反诈宣传 FPS（公安 / 社区 / 校园向）。

启动
----
1. 先把整个 zip 完整解压到一个普通文件夹（例如 D:\fanzha-demo），
   不要在压缩包预览窗口里直接双击 run.bat。
2. 双击 run.bat（窗口 1280x720）。标题画面按回车 → 选章节 → 开始。

打不开？
--------
- 窗口提示 This window runs from a temporary folder inside the ZIP：
  说明是在压缩包里直接双击的，先完整解压再运行。
- 窗口提示 Files missing / 只缺 uzdoom.exe：多半是杀毒软件（Windows
  Defender / 360 / 火绒）把引擎当可疑程序隔离了。到隔离区恢复该文件、
  把解压目录加入信任，再双击 run.bat。
- 没反应也没报错：确认解压目录能写入（不要放在 Program Files 下），
  或换一个简单路径重试。

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
竞技场北侧三个小房间各有 1 件证据，集齐 3 件才算证据链完整（HUD 右下出现
红字「红卡」），红卡门后是本章 Boss；击败后拾取主谋证据，走进出口小间即结案。
三章：刷单深渊 / 装备黑市 / 警服幻影，每章结束是引擎标准结算页（回车进下一章）。

提示：游戏内按 F1 可看物品帮助；如遇启动崩溃，删除
%LOCALAPPDATA%\\doom\\uzdoom\\vulkanpipelinecache 后重试。
按键/画面设置想恢复默认：删掉 fz-settings.cfg 再启动（uzdoom.cfg 是模板）。

内容说明
--------
- 角色（6 种敌人 78 帧、2 把武器 9 帧）与三个流程物件（数据终端 / 证据箱 /
  主谋证据）已全部换成自研像素图，不再出现 Freedoom 的护甲 / 背包 / 蓝钥匙
- 墙地贴图部分自研、部分沿用 Freedoom 同名素材
- 音效为程序化合成；五首配乐为本次自制（标题 + 三章 + Boss）
- 敌人语音仍是 Freedoom 原版怪叫（配音待录）
- 弹药 / 护甲 / 血包的图也还是 Freedoom 的
- 抉择菜单目前仅键盘操作
- 本包为宣传演示用途；剧情与知识点见 docs/剧情.md

许可
----
UZDoom 5.0.3        GPL-3.0（源码见 https://github.com/UZDoom/UZDoom）
Freedoom 0.13.0     BSD 3-Clause（freedoom1.wad）
Fusion Pixel 字体    SIL Open Font License 1.1
本作剧情 / 地图 / 脚本 / 界面素材：项目自产
配乐：项目自制，音源与 AI 参与说明见 LICENSES/music-credits.txt
详见 LICENSES/ 目录。
"""

MUSIC_CREDITS = """反诈战士 · 配乐来源说明

游戏内 BGM（game/music/title.ogg、ch1.ogg、ch2.ogg、ch3.ogg、boss.ogg）为本项目自制：
2026-11-23 由 DSH Agent 编写乐谱，再用本地 SoundFont 渲染成音频。旋律、和声与编排
均为本次原创，未使用任何第三方采样，也未使用既有曲目的旋律。

音源：GeneralUser GS（GeneralUser GS License v2.0）。它只在制作时于本机用于渲染，
不随本包分发；本包内是渲染后的音频，不含 SoundFont 文件本身。

乐谱源文件与 AI 参与登记见仓库：
  assets_src/audio/music/   乐谱 JSON 与循环点清单
  assets_src/CREDITS.md     工具、日期、提示词摘要、人工修改程度
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

    # 配乐不是第三方素材，但音源与 AI 参与要留痕，别让成品包说不清来源
    (lic / "music-credits.txt").write_text(MUSIC_CREDITS, encoding="utf-8-sig",
                                           newline="\r\n")

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
