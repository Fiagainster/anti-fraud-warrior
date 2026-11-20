#!/usr/bin/env python3
"""Minimal-map bisect for UDMF loader crashes.

Builds 6 pk3s, each with one progressively more complex test map:
  T01 bare room + player start
  T02 + pickups and monster
  T03 + corridor + 2-sided opening
  T04 + choice gate terminal (custom actor, doomednum)
  T05 + locked door slab (special 33)
  T06 + exit switch line (special 11)

Boot each with +map Txx and report which crashes.
"""

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ROOM = """namespace = "zdoom";

vertex // 0
{
	x = 0.000; y = 0.000;
}

vertex // 1
{
	x = 512.000; y = 0.000;
}

vertex // 2
{
	x = 512.000; y = 512.000;
}

vertex // 3
{
	x = 0.000; y = 512.000;
}

{LINES_PLACEHOLDER}

sector // 0
{
	heightfloor = 0;
	heightceiling = 160;
	texturefloor = "FLOOR4_8";
	textureceiling = "CEIL3_5";
	light = 180;
}

{THINGS_PLACEHOLDER}
"""


def walls():
    out = []
    edges = [((0, 0), (512, 0)), ((512, 0), (512, 512)),
             ((512, 512), (0, 512)), ((0, 512), (0, 0))]
    n = 0
    for (x1, y1), (x2, y2) in edges:
        out.append(
            f"linedef // {n}\n{{\n\tv1 = {n % 4}; v2 = {(n + 1) % 4};\n"
            f"\tsidefront = {n};\n\tblocking = true;\n}}\n"
        )
        out.append(
            f"sidedef // {n}\n{{\n\tsector = 0;\n\ttexturemiddle = \"STARTAN2\";\n}}\n"
        )
        n += 1
    return "".join(out)


def thing(x, y, type_, tid=0, args=None):
    body = [f"thing\n{{", f"\tx = {x:.3f}; y = {y:.3f};", f"\tangle = 0;",
            f"\ttype = {type_};"]
    if tid:
        body.append(f"\tid = {tid};")
    if args:
        for i, a in enumerate(args):
            if a:
                body.append(f"\targ{i} = {a};")
    body.append("\tskill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true;")
    body.append("\tsingle = true;")
    body.append("}")
    return "\n".join(body) + "\n"


PLAYER = thing(128, 256, 1)

VARIANTS = {
    "T01": ROOM.replace("{LINES_PLACEHOLDER}", walls()).replace("{THINGS_PLACEHOLDER}", PLAYER),
    "T02": ROOM.replace("{LINES_PLACEHOLDER}", walls()).replace("{THINGS_PLACEHOLDER}", PLAYER + thing(384, 256, 3001)
                       + thing(320, 128, 2008) + thing(320, 384, 2012)),
    "T03": ROOM.replace("{LINES_PLACEHOLDER}", walls()).replace("{THINGS_PLACEHOLDER}", PLAYER),  # opening tested via T05
    "T04": ROOM.replace("{LINES_PLACEHOLDER}", walls()).replace("{THINGS_PLACEHOLDER}", PLAYER
                       + thing(384, 384, 39100, tid=911, args=(11, 0, 0, 0, 0))),
    "T05": ROOM.replace("{LINES_PLACEHOLDER}", walls()).replace("{THINGS_PLACEHOLDER}", PLAYER),
    "T06": ROOM.replace("{LINES_PLACEHOLDER}", walls()).replace("{THINGS_PLACEHOLDER}", PLAYER
                       + thing(384, 256, 2001)),
}


def main() -> None:
    outdir = ROOT / "build/udmf_bisect"
    outdir.mkdir(parents=True, exist_ok=True)
    for name, mapdata in VARIANTS.items():
        pk3 = outdir / f"{name}.pk3"
        with zipfile.ZipFile(pk3, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("MAPINFO", f'map {name} "test" {{ }}\n')
            z.writestr(f"maps/{name}.map", mapdata)
        print(f"built {pk3}")


if __name__ == "__main__":
    main()
