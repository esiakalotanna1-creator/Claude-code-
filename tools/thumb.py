"""Cover / thumbnail maker for 9:16 reels.

The YouTube Shorts shelf shows covers at about 2:3, cutting ~150 px off the top and bottom of a
1080x1920 cover, and Instagram's grid shows the middle 3:4. All text is kept inside the band that
survives both crops (y 400-1520 at 1080x1920). Writes the cover plus a *_shelf.jpg preview of the
2:3 crop.

  python tools/thumb.py SRC OUT --line "THE BABYSITTER:#F2EFE6:120" --line "RULES.:#FF5A3C:250"
      [--zoom 1.0 --cx 0.5 --cy 0.5] [--y 1480]   (--y = bottom of the text block)
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "toon"))
from toon import font_path  # noqa: E402

FONT = font_path()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--line", action="append", required=True, help="TEXT:#RRGGBB:SIZE")
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--cx", type=float, default=0.5)
    ap.add_argument("--cy", type=float, default=0.5)
    ap.add_argument("--y", type=int, default=1480)
    a = ap.parse_args()

    im = Image.open(a.src).convert("RGB")
    # cover-fit to 9:16, then zoom about (cx, cy)
    s = max(W / im.width, H / im.height) * a.zoom
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x0 = min(max(round(a.cx * im.width - W / 2), 0), im.width - W)
    y0 = min(max(round(a.cy * im.height - H / 2), 0), im.height - H)
    im = im.crop((x0, y0, x0 + W, y0 + H))

    lines = []
    for spec in a.line:
        text, col, size = spec.rsplit(":", 2)
        f = ImageFont.truetype(FONT, int(size))
        while f.getlength(text) > W - 120:
            f = ImageFont.truetype(FONT, f.size - 4)
        lines.append((text, col, f))
    heights = [f.getbbox(t)[3] - f.getbbox(t)[1] for t, _, f in lines]
    gap = 24
    top = a.y - sum(heights) - gap * (len(lines) - 1)

    # soft dark band behind the text so it reads on any frame
    shade = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shade).rectangle((0, top - 140, W, a.y + 120), fill=170)
    shade = shade.filter(ImageFilter.GaussianBlur(90))
    im = Image.composite(Image.new("RGB", (W, H)), im, shade)

    d = ImageDraw.Draw(im)
    y = top
    for (text, col, f), h in zip(lines, heights):
        bb = f.getbbox(text)
        x = (W - f.getlength(text)) / 2
        d.text((x + 8, y - bb[1] + 8), text, font=f, fill="#000000")
        d.text((x, y - bb[1]), text, font=f, fill=col)
        y += h + gap
    im.save(a.out, quality=95)
    shelf = im.crop((0, (H - 1620) // 2, W, (H + 1620) // 2))
    shelf.resize((360, 540), Image.LANCZOS).save(a.out.rsplit(".", 1)[0] + "_shelf.jpg", quality=90)
    print("cover", a.out, "text block y", top, "-", a.y)


if __name__ == "__main__":
    main()
