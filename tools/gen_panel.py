#!/usr/bin/env python3
"""Generate the HUD bottom panel (FZPANEL.png), 320x48 for a 48px bar."""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path("game/graphics/FZPANEL.png")
OUT_BKPT = Path("game/graphics/FZBKPT.png")


def main() -> None:
    img = Image.new("RGBA", (320, 48), (6, 10, 14, 220))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 319, 1], fill=(0, 200, 120, 255))
    draw.rectangle([0, 46, 319, 47], fill=(0, 70, 55, 255))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    bkpt = Image.new("RGBA", (8, 8), (6, 10, 14, 255))
    bkpt.save(OUT_BKPT)
    print(f"saved {OUT} (320x48) + {OUT_BKPT}")


if __name__ == "__main__":
    main()
