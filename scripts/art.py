"""The Bird of the Day picture.

`hero()` returns a grayscale canvas of exactly CANVAS (the drawable area of a
TRMNL X full view, displayed 1:1). `finish()` quantizes it to 16 grays.

Flat areas use exact 16-level grays (multiples of 17) so they stay clean after
dithering; only the bird artwork and soft edges get dithered.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"

# TRMNL X: 1872x1404 panel, the full view leaves an 18 px frame.
CANVAS = (1836, 1368)

WHITE, PAPER, PALE, LIGHT, MID, DARK, BLACK = 255, 238, 221, 204, 136, 68, 0


def col(v: int) -> tuple:
    """Opaque RGBA ink from a gray value (ImageDraw reads a bare int on RGBA as packed RGBA)."""
    return (v, v, v, 255)


# ---------------------------------------------------------------- fonts

_FONT_CACHE: dict = {}


def font(name: str, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    key = (name, size, weight)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    f = _font(name, size, weight)
    _FONT_CACHE[key] = f
    return f


def _font(name: str, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    files = {
        "serif": "InstrumentSerif-Regular.ttf",
        "serif-italic": "InstrumentSerif-Italic.ttf",
        "mono": "IBMPlexMono-Regular.ttf",
        "mono-medium": "IBMPlexMono-Medium.ttf",
        "sans": "Inter.ttf",
        "sans-italic": "Inter-Italic.ttf",
    }
    f = ImageFont.truetype(str(FONTS / files[name]), size)
    if weight and name.startswith("sans"):
        try:
            f.set_variation_by_axes([min(32, max(14, size // 4)), weight])
        except Exception:
            pass
    return f


def text_w(d: ImageDraw.ImageDraw, s: str, f) -> int:
    b = d.textbbox((0, 0), s, font=f)
    return b[2] - b[0]


# ---------------------------------------------------------------- stickers

@dataclass
class Sticker:
    im: Image.Image  # RGBA, gray content, trimmed

    @property
    def w(self):
        return self.im.width

    @property
    def h(self):
        return self.im.height


def load_sticker(path: Path) -> Sticker:
    im = Image.open(path).convert("RGBA")
    a = im.getchannel("A")
    bbox = a.point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
        a = im.getchannel("A")
    gray = im.convert("RGB").convert("L")
    body = a.point(lambda v: 255 if v > 200 else 0)
    gray = ImageOps.autocontrast(gray, cutoff=(1, 1), mask=body)
    gray = ImageEnhance.Contrast(gray).enhance(1.2)
    out = Image.merge("RGBA", (gray, gray, gray, a))
    return Sticker(out)


def scaled(st: Sticker, factor: float) -> Image.Image:
    w, h = max(1, round(st.w * factor)), max(1, round(st.h * factor))
    return st.im.resize((w, h), Image.LANCZOS)


def fit(st: Sticker, max_w: float, max_h: float) -> Image.Image:
    return scaled(st, min(max_w / st.w, max_h / st.h))


def sharpen(im: Image.Image) -> Image.Image:
    rgb = im.convert("RGB").filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2))
    out = rgb.convert("RGBA")
    out.putalpha(im.getchannel("A"))
    return out


def new_canvas(level=WHITE) -> Image.Image:
    return Image.new("RGBA", CANVAS, (level, level, level, 255))


def finish(canvas: Image.Image, dst: Path, levels=16) -> None:
    gray = canvas.convert("RGB").convert("L")
    pal = Image.new("P", (1, 1))
    lv = [round(i * 255 / (levels - 1)) for i in range(levels)]
    pal.putpalette([v for x in lv for v in (x, x, x)] + [0] * 3 * (256 - levels))
    q = gray.convert("RGB").quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG).convert("L")
    dst.parent.mkdir(parents=True, exist_ok=True)
    q.save(dst, optimize=True)


def _splits(words, n):
    """All ways to break `words` into n consecutive non-empty lines."""
    if n == 1:
        yield [words]
        return
    for i in range(1, len(words) - n + 2):
        for rest in _splits(words[i:], n - 1):
            yield [words[:i]] + rest


def _biggest_type(d, words, max_w, max_h, start=700, min_lines=1, max_lines=4, lead=0.86):
    """Largest Inter Black that sets `words` in 1..max_lines lines inside max_w x max_h."""
    best = None
    for nl in range(min_lines, min(max_lines, len(words)) + 1):
        for split in _splits(words, nl):
            lines = [" ".join(p).replace("- ", "-") for p in split]
            size = start
            while size > 60:
                f = font("sans", size, 900)
                lw = max(text_w(d, s_, f) for s_ in lines)
                if lw <= max_w and size * lead * len(lines) <= max_h:
                    break
                size -= 16
            if best is None or size > best[0]:
                best = (size, lines)
    return best


# ---------------------------------------------------------------- bird first

def _free_rects(occ: np.ndarray, cell: int, W: int, H: int, margin: int):
    """Corner-anchored empty rectangles (x0, y0, x1, y1) in a coarse occupancy grid."""
    gh, gw = occ.shape
    m = margin // cell
    rects = []
    for corner in ("tl", "tr", "bl", "br"):
        grid = occ.copy()
        if corner[1] == "r":
            grid = grid[:, ::-1]
        if corner[0] == "b":
            grid = grid[::-1, :]
        # for each height from the corner, the widest free span
        width = gw - m
        for h in range(1, gh - m):
            row = grid[m + h - 1, m:]
            free = np.argmax(row) if row.any() else len(row)
            width = min(width, free)
            if width < 6:
                break
            if h % 3:
                continue
            rect = [m * cell, m * cell, (m + width) * cell, (m + h) * cell]
            if corner[1] == "r":
                rect[0], rect[2] = W - rect[2], W - rect[0]
            if corner[0] == "b":
                rect[1], rect[3] = H - rect[3], H - rect[1]
            rects.append((corner, tuple(rect)))
    return rects


def _occupancy(bird: Image.Image, xy, cell=24):
    """Coarse grid of cells the bird's alpha touches (vectorised)."""
    W, H = CANVAS
    gh, gw = H // cell + 1, W // cell + 1
    a = np.zeros((gh * cell, gw * cell), dtype=bool)
    x, y = xy
    l, t = max(0, x), max(0, y)
    r, b = min(W, x + bird.width), min(H, y + bird.height)
    if r > l and b > t:
        a[t:b, l:r] = np.asarray(bird.getchannel("A"))[t - y:b - y, l - x:r - x] > 40
    return a.reshape(gh, cell, gw, cell).any(axis=(1, 3))


def _fit_name_in(d, words, rects, min_size=48):
    """Biggest Inter Black setting of `words` inside any of the rects."""
    best = None
    for corner, (x0, y0, x1, y1) in rects:
        w, h = x1 - x0, y1 - y0
        if w < 200 or h < 60:
            continue
        r = _biggest_type(d, words, w, h, start=min(620, int(h / 0.86) + 8), max_lines=3, lead=0.86)
        if r and r[0] >= min_size and (best is None or r[0] > best[0]):
            best = (r[0], r[1], corner, (x0, y0, x1, y1))
    return best


def _draw_block(d, lines, size, corner, rect, fill):
    f = font("sans", size, 900)
    lead = size * 0.86
    x0, y0, x1, y1 = rect
    block_h = lead * len(lines)
    y = y0 if corner[0] == "t" else y1 - block_h
    for s_ in lines:
        bb = f.getbbox(s_)
        tw = bb[2] - bb[0]
        x = x0 if corner[1] == "l" else x1 - tw
        d.text((x - bb[0], y - bb[1] + size * 0.04), s_, font=f, fill=fill)
        y += lead
    return f


def hero(st: Sticker, info: dict) -> Image.Image:
    """The bird as big as it gets; the name takes whatever space is left."""
    W, H = CANVAS
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    words = info["name"].upper().replace("-", "- ").split()
    best = None
    for frac in (0.92, 0.82, 0.72):
        bird = fit(st, W * 0.96, H * frac)
        for ax in (0.5, 0.64, 0.36):
            x = int(ax * W - bird.width / 2)
            x = max(20, min(W - bird.width - 20, x))
            y = int(H - 40 - bird.height) if frac > 0.85 else int((H - bird.height) / 2)
            occ = _occupancy(bird, (x, y))
            r = _fit_name_in(d0, words, _free_rects(occ, 24, W, H, 48))
            if r and (best is None or r[0] > best[0]):
                best = (r[0], r[1], r[2], r[3], bird, (x, y))
            if best and best[0] >= 200:
                break
        if best and best[0] >= 200:
            break
    size, lines, corner, rect, bird, xy = best
    cv = new_canvas(WHITE)
    cv.alpha_composite(sharpen(bird), xy)
    d = ImageDraw.Draw(cv)
    _draw_block(d, lines, size, corner, rect, col(BLACK))
    # small print: a free corner other than the name's, else under the name
    fm = font("mono", 26)
    fi = font("serif-italic", 48)
    small = [info["scientific"], "  /  ".join(info["facts"][:4])]
    need_w = max(text_w(d, small[0], fi), text_w(d, small[1], fm)) + 10
    occ = _occupancy(bird, xy)
    free = {c: r for c, r in reversed(_free_rects(occ, 24, W, H, 48))}  # tallest per corner
    pick = None
    for c in ("tl", "tr", "bl", "br"):
        if c == corner or c not in free:
            continue
        x0, y0, x1, y1 = free[c]
        if x1 - x0 >= need_w and y1 - y0 >= 110:
            pick = c
            break
    if pick:
        x0, y0, x1, y1 = free[pick]
        sx = x0 if pick[1] == "l" else x1
        sy = y0 if pick[0] == "t" else y1 - 110
    else:
        x0, y0, x1, y1 = rect
        sx = x0 if corner[1] == "l" else x1
        sy = (y1 - size * 0.86 * len(lines) - 120) if corner[0] == "b" else (y0 + size * 0.86 * len(lines) + 10)
        pick = corner
    for i, s_ in enumerate(small):
        ff = fi if i == 0 else fm
        tw = text_w(d, s_, ff)
        d.text((sx if pick[1] == "l" else sx - tw, sy + i * 54), s_, font=ff, fill=col(DARK))
    return cv


