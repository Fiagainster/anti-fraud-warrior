#!/usr/bin/env python3
"""Import / verify the large external binaries the project needs.

Nothing here downloads from the internet: the team downloads the official
releases once and imports them; this script copies them into `vendor/`,
verifies sha256 against `vendor/manifest.json`, and tells every clone what
is missing.

Usage:
  python tools/fetch_vendor.py status
  python tools/fetch_vendor.py import --uzdoom  <dir-or-zip>
  python tools/fetch_vendor.py import --freedoom <freedoom1.wad>
  python tools/fetch_vendor.py import --font     <ttf-or-zip-or-dir>
  python tools/fetch_vendor.py import --uzdoom ... --freedoom ... --font ...

Official sources (see manifest for pinned versions):
  UZDoom      https://github.com/UZDoom/UZDoom/releases
  Freedoom    https://freedoom.github.io/
  Fusion Pixel https://github.com/TakWolf/fusion-pixel-font/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

# Manifest descriptions are Chinese, but English Windows consoles (and the
# GitHub Actions runner) default to cp1252, where printing them raises
# UnicodeEncodeError and turns a status check into a crash. Force UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
MANIFEST = VENDOR / "manifest.json"

ENGINE_FILES = [
    "uzdoom.exe", "uzdoom.pk3", "game_support.pk3", "lights.pk3",
    "brightmaps.pk3", "game_widescreen_gfx.pk3",
    "libcurl-x64.dll", "sndfile.dll", "soft_oal.dll",
]
ENGINE_DIR = VENDOR / "uzdoom-5.0.3"
IWAD_DIR = VENDOR / "freedoom-0.13.0"
FONT_DIR = VENDOR / "fusion-pixel-2026.11.10"
FONT_NAME = "fusion-pixel-12px-proportional-zh_hans.ttf"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    if not MANIFEST.exists():
        raise SystemExit(f"missing {MANIFEST}")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def cmd_status() -> int:
    man = load_manifest()
    bad = 0
    for item in man["files"]:
        p = ROOT / item["path"]
        if not p.exists():
            print(f"MISSING  {item['path']}  ({item['desc']})")
            bad += 1
            continue
        got = sha256(p)
        if got != item["sha256"]:
            print(f"MISMATCH {item['path']}\n  expected {item['sha256']}\n  got      {got}")
            bad += 1
        else:
            print(f"OK       {item['path']}")
    print()
    for key, src in man["sources"].items():
        print(f"source {key}: {src['pin']}  <{src['homepage']}>")
    if bad:
        print(f"\n{bad} file(s) missing or mismatched. Import them with:")
        print("  python tools/fetch_vendor.py import --uzdoom <dir-or-zip> "
              "--freedoom <freedoom1.wad> --font <ttf-or-zip>")
        return 1
    print("\nall vendor files verified")
    return 0


def _copy_engine(src: Path) -> None:
    ENGINE_DIR.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        for name in ENGINE_FILES:
            s = src / name
            if s.exists():
                shutil.copy2(s, ENGINE_DIR / name)
        # copy the rest of the release (soundfonts, licenses, ...) too
        for s in src.iterdir():
            if s.is_file() and not (ENGINE_DIR / s.name).exists():
                shutil.copy2(s, ENGINE_DIR / s.name)
    elif src.suffix.lower() == ".zip":
        with zipfile.ZipFile(src) as z:
            members = z.namelist()
            for m in members:
                base = Path(m).name
                if base in ENGINE_FILES or "/" not in m:
                    z.extract(m, ENGINE_DIR)
        # some zips nest everything one level deep
        nested = next((ENGINE_DIR / d for d in ENGINE_DIR.iterdir()
                       if d.is_dir() and (d / "uzdoom.exe").exists()), None)
        if nested:
            for f in nested.iterdir():
                shutil.move(str(f), ENGINE_DIR / f.name)
            nested.rmdir()
    else:
        raise SystemExit(f"--uzdoom expects a directory or .zip, got {src}")
    print(f"engine imported -> {ENGINE_DIR}")


def _copy_iwad(src: Path) -> None:
    IWAD_DIR.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        src = src / "freedoom1.wad"
    if not src.exists():
        raise SystemExit(f"freedoom1.wad not found at {src}")
    shutil.copy2(src, IWAD_DIR / "freedoom1.wad")
    # keep the licence/credits next to it when available
    for name in ("COPYING.txt", "CREDITS.txt"):
        s = src.parent / name
        if s.exists():
            shutil.copy2(s, IWAD_DIR / name)
    print(f"iwad imported -> {IWAD_DIR / 'freedoom1.wad'}")


def _copy_font(src: Path) -> None:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        matches = list(src.rglob("fusion-pixel-12px-proportional-zh_hans.ttf"))
        if not matches:
            raise SystemExit(f"{FONT_NAME} not found under {src}")
        src = matches[0]
    if src.suffix.lower() == ".zip":
        with zipfile.ZipFile(src) as z:
            for m in z.namelist():
                if Path(m).name == FONT_NAME or Path(m).suffix.lower() == ".txt":
                    data = z.read(m)
                    (FONT_DIR / Path(m).name).write_bytes(data)
        print(f"font imported -> {FONT_DIR}")
        return
    shutil.copy2(src, FONT_DIR / FONT_NAME)
    print(f"font imported -> {FONT_DIR / FONT_NAME}")


def cmd_import(args) -> int:
    if not (args.uzdoom or args.freedoom or args.font):
        raise SystemExit("nothing to import; pass --uzdoom/--freedoom/--font")
    if args.uzdoom:
        _copy_engine(Path(args.uzdoom))
    if args.freedoom:
        _copy_iwad(Path(args.freedoom))
    if args.font:
        _copy_font(Path(args.font))
    return cmd_status()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="verify vendor files against the manifest")
    imp = sub.add_parser("import", help="copy official downloads into vendor/")
    imp.add_argument("--uzdoom")
    imp.add_argument("--freedoom")
    imp.add_argument("--font")
    args = ap.parse_args()
    return cmd_status() if args.cmd == "status" else cmd_import(args)


if __name__ == "__main__":
    sys.exit(main())
