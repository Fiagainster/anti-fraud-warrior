#!/usr/bin/env python3
"""Pack the playable game data into build/fanzha-demo.pk3.

Contents:
    MAPINFO
    zscript.txt
    zscript/*.zs
    fonts/fzfont*/...
    graphics/*.png        (HUD panel + Chinese main-menu patches)
    sprites/*.png         (sprite lumps, e.g. FZTRA0.png for "FZTR A")
    sounds/*              (sound lumps)

`game/menudef/` is intentionally not packed: the main menu is localized by
overriding the stock M_* patches, not by replacing MENUDEF.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"
OUT = ROOT / "build" / "fanzha-demo.pk3"


def ensure_fonts() -> None:
    """Font atlases are generated from the ZScript strings; regenerate if
    a fresh clone has none (needs vendor Fusion Pixel ttf)."""
    if (GAME / "fonts" / "fzfont" / "font.inf").exists():
        return
    # CI has the IWAD (BSD, downloadable) but not the font ttf, so it packs
    # without atlases to still exercise map generation + packing. The HUD
    # will print nothing in that state - hence the loud warning and the
    # explicit opt-in. Never set this for a release build.
    if os.environ.get("FZ_ALLOW_NO_FONTS") == "1":
        print("WARN fonts missing -> packing WITHOUT font atlases "
              "(CI smoke build only; in-game text will not render). "
              "Generate them with: python tools/gen_font.py")
        return
    print("fonts missing -> generating via tools/gen_font.py")
    import subprocess
    import sys as _sys
    r = subprocess.run([_sys.executable, "-I", str(ROOT / "tools/gen_font.py")],
                       cwd=str(ROOT))
    if r.returncode != 0:
        raise SystemExit("font generation failed; import vendor files first: "
                         "python tools/fetch_vendor.py import --font <ttf>")


def ensure_maps() -> None:
    """Maps are generated from tools/gen_maps.py (the source of truth);
    regenerate them when a fresh clone has none."""
    mapdir = GAME / "maps"
    if mapdir.exists() and any(mapdir.glob("*.wad")):
        return
    print("maps missing -> generating via tools/gen_maps.py")
    import subprocess
    import sys as _sys
    r = subprocess.run([_sys.executable, "-I", str(ROOT / "tools/gen_maps.py")],
                       cwd=str(ROOT))
    if r.returncode != 0:
        raise SystemExit("map generation failed; import vendor files first: "
                         "python tools/fetch_vendor.py import ...")


def main() -> None:
    ensure_fonts()
    ensure_maps()
    required = [
        GAME / "mapinfo" / "MAPINFO",
        GAME / "zscript.txt",
        GAME / "zscript" / "fz_hud.zs",
        GAME / "graphics" / "FZPANEL.png",
        GAME / "graphics" / "M_DOOM.png",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit("missing required files:\n" + "\n".join(missing))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(GAME / "mapinfo" / "MAPINFO", "MAPINFO")
        z.write(GAME / "zscript.txt", "zscript.txt")
        if (GAME / "sndinfo" / "SNDINFO").exists():
            z.write(GAME / "sndinfo" / "SNDINFO", "SNDINFO")
        if (GAME / "language" / "language.txt").exists():
            z.write(GAME / "language" / "language.txt", "LANGUAGE")
        # GAMEINFO sets the window title and startup screen type; must sit at the
        # pk3 root and is the *last* GAMEINFO the engine sees (d_main:CheckGameInfo).
        if (GAME / "gameinfo" / "GAMEINFO").exists():
            z.write(GAME / "gameinfo" / "GAMEINFO", "GAMEINFO")
        # textures/flats/patches are read by the engine as image namespaces,
        # music by MAPINFO's Music field. All four are optional: a checkout
        # with no custom art still builds.
        for sub in ("zscript", "fonts", "graphics", "sprites", "sounds",
                    "textures", "flats", "patches", "music"):
            d = GAME / sub
            if not d.is_dir():
                continue
            for p in sorted(d.rglob("*")):
                if p.is_file():
                    z.write(p, str(p.relative_to(GAME)).replace("\\", "/"))

    # Map WADs are shipped as loose files next to the pk3: the engine's
    # full-name lookup inside pk3 archives proved unreliable in 5.0.3.
    mapdir = GAME / "maps"
    if mapdir.exists():
        out_maps = ROOT / "build" / "maps"
        out_maps.mkdir(parents=True, exist_ok=True)
        for p in sorted(mapdir.glob("*.wad")):
            (out_maps / p.name).write_bytes(p.read_bytes())
            print("map file:", p.name)

    with zipfile.ZipFile(OUT) as z:
        entries = z.namelist()
    print(f"built {OUT} ({OUT.stat().st_size:,} bytes, {len(entries):,} entries)")
    print("root:", [n for n in entries if "/" not in n])


if __name__ == "__main__":
    main()
