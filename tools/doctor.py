#!/usr/bin/env python3
"""One-shot environment check for new contributors.

  python tools/doctor.py
  python tools/doctor.py --blender "D:/System/Blender/blender-launcher.exe"

Checks Python, Pillow, vendor binaries, the shipped config bindings and
the generated content. Every failure prints the exact command that fixes it.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# This script prints Chinese on every machine, including English Windows and
# CI runners whose console encoding is cp1252 - without this the first line
# raises UnicodeEncodeError before any check even runs.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "uzdoom.cfg"

OK, BAD, WARN = "PASS", "FAIL", "WARN"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "", fix: str = "", warn: bool = False) -> None:
    status = OK if ok else (WARN if warn else BAD)
    results.append((status, name, detail))
    line = f"{status:4}  {name}"
    if detail:
        line += f"  [{detail}]"
    print(line)
    if not ok and fix:
        print(f"      fix: {fix}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", help="optional path to blender executable")
    args = ap.parse_args()

    print("== 反诈战士 · 开发环境自检 ==\n")

    check("Python >= 3.10", sys.version_info >= (3, 10),
          sys.version.split()[0], "安装 Python 3.10+ 并确保 `python` 可用")
    try:
        import PIL  # noqa: F401
        check("Pillow installed", True, getattr(PIL, "__version__", ""))
    except Exception:  # noqa: BLE001
        check("Pillow installed", False, "", "python -m pip install pillow")

    vendor_ok = True
    for rel in ("vendor/uzdoom-5.0.3/uzdoom.exe",
                "vendor/freedoom-0.13.0/freedoom1.wad",
                "vendor/fusion-pixel-2026.11.10/fusion-pixel-12px-proportional-zh_hans.ttf"):
        p = ROOT / rel
        if not p.exists():
            vendor_ok = False
            check(f"vendor: {rel}", False, "missing",
                  "python tools/fetch_vendor.py import --uzdoom <dir> --freedoom <wad> --font <ttf>")
    if vendor_ok:
        check("vendor binaries present", True)

    cfg_text = CFG.read_text(encoding="utf-8", errors="replace") if CFG.exists() else ""
    need_binds = ["Escape=menu_main", "W=+forward", "A=+moveleft",
                  "Mouse1=+attack", "`=toggleconsole"]
    missing = [b for b in need_binds if b not in cfg_text]
    check("config/uzdoom.cfg bindings", not missing,
          ", ".join(missing) if missing else "ESC / WASD / 鼠标 / 控制台",
          "从 git 恢复 config/uzdoom.cfg；不要手写精简配置（会清空默认绑定）")

    for rel in ("game/zscript.txt", "game/mapinfo/MAPINFO",
                "game/zscript/fz_hud.zs", "game/zscript/fz_gates.zs",
                "game/graphics/FZPANEL.png", "tools/gen_maps.py",
                "tools/build.py"):
        check(f"content: {rel}", (ROOT / rel).exists(), "",
              "git checkout 恢复缺失文件")

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("gm", ROOT / "tools/gen_maps.py")
        gm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gm)  # type: ignore[union-attr]
        flats, tex = gm.iwad_names()
        check("IWAD texture names readable", bool(flats and tex),
              f"{len(flats)} flats / {len(tex)} textures")
    except Exception as exc:  # noqa: BLE001
        check("IWAD texture names readable", False, str(exc),
              "确认 vendor/freedoom-0.13.0/freedoom1.wad 完整")

    if args.blender:
        b = Path(args.blender)
        if b.exists():
            try:
                out = subprocess.run([str(b), "--version"], capture_output=True,
                                     text=True, timeout=30).stdout.splitlines()
                check("Blender", True, out[0] if out else str(b))
            except Exception as exc:  # noqa: BLE001
                check("Blender", False, str(exc), "检查 Blender 安装")
        else:
            check("Blender", False, f"not found: {b}", "修正 --blender 路径", warn=True)
    else:
        check("Blender (optional, art only)", True, "未指定 --blender", warn=True)

    failed = [r for r in results if r[0] == BAD]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("按上面的 fix 逐条处理后重跑。")
        return 1
    print("环境就绪：python tools\\build.py 即可构建，run.bat 游玩。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
