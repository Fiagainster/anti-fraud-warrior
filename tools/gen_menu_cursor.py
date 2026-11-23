"""Draw the menu cursor used by the custom difficulty menu (FZSELECT).

The stock Doom cursor is the grinning skull (M_CURS1).  This one is a
magnifying glass: it reads as "核查线索" and matches the HUD's cyan/white
plate.  Drawn on a 16x16 grid and scaled 2x so the pixels stay square, which
is the size the 320x200 menu canvas expects for a cursor patch.
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "game" / "graphics" / "FZSELECT.png"

RING = (232, 244, 255, 255)
GLASS = (28, 74, 102, 255)
HANDLE = (255, 196, 64, 255)
SPARK = (120, 220, 255, 255)


def draw() -> Image.Image:
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # lens: a filled disc with a lighter rim
    d.ellipse((1, 1, 11, 11), fill=GLASS, outline=RING, width=1)
    # highlight in the upper-left of the glass
    d.point((4, 4), fill=SPARK)
    d.point((5, 3), fill=SPARK)
    d.point((3, 5), fill=SPARK)

    # handle running to the lower-right corner
    for i in range(4):
        d.line((11 + i, 11 + i, 12 + i, 12 + i), fill=HANDLE)
    d.point((14, 14), fill=RING)

    return img.resize((32, 32), Image.NEAREST)


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    draw().save(OUT)
    print(OUT)
