"""The Bird of the Day pictures.

`hero()`, `closeup()` and `quiet()` each return a grayscale canvas of exactly
CANVAS (the drawable area of a TRMNL X full view, displayed 1:1). `finish()`
quantizes it to 16 grays.

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


def fit_font(d, s, name, max_w, start, minimum=10, weight=None):
    """Largest size (stepping down by 2) at which `s` fits in max_w."""
    size = start
    while size > minimum:
        f = font(name, size, weight)
        if text_w(d, s, f) <= max_w:
            return f
        size -= 2
    return font(name, minimum, weight)


def alpha_points(im: Image.Image, thresh=120):
    a = np.asarray(im.getchannel("A")) > thresh
    ys, xs = np.nonzero(a)
    return xs, ys


def _paste_clip(canvas: Image.Image, im: Image.Image, x: int, y: int):
    """alpha_composite that tolerates images hanging off the canvas."""
    l, t = max(0, -x), max(0, -y)
    r, b = min(im.width, canvas.width - x), min(im.height, canvas.height - y)
    if r <= l or b <= t:
        return
    canvas.alpha_composite(im.crop((l, t, r, b)), (x + l, y + t))


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


# ---------------------------------------------------------------- small print

LATIN_PX, FACTS_PX, GAP_FACTS = 50, 28, 26


def _gap_name(size: int) -> int:
    """Air between the name block and the small print under (or above) it."""
    return max(40, int(size * 0.14))


def _name_block_bounds(lines, size, corner, rect):
    """Top and bottom of the glyphs as _draw_block paints them."""
    f = font("sans", size, 900)
    lead = size * 0.86
    x0, y0, x1, y1 = rect
    y = y0 if corner[0] == "t" else y1 - lead * len(lines)
    bb = f.getbbox(lines[-1])
    return y + size * 0.04, y + lead * (len(lines) - 1) + size * 0.04 + (bb[3] - bb[1])


def _box_free(occ: np.ndarray, box, cell=24) -> bool:
    """True when no occupied grid cell touches the pixel box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    gy0, gy1 = max(0, y0 // cell), min(occ.shape[0], y1 // cell + 1)
    gx0, gx1 = max(0, x0 // cell), min(occ.shape[1], x1 // cell + 1)
    return not occ[gy0:gy1, gx0:gx1].any()


def _put(d, s, f, x_anchor, y_top, fill, right):
    """Draw `s` with its glyph box starting at y_top; right-aligned to x_anchor if asked."""
    bb = f.getbbox(s)
    x = x_anchor - (bb[2] - bb[0]) if right else x_anchor
    d.text((x - bb[0], y_top - bb[1]), s, font=f, fill=fill)
    return bb[3] - bb[1]


def small_print(d, lines, size, corner, rect, latin, facts, bird, xy, under=False):
    """Latin name and facts in small type. In a free corner the name does not
    use, else right under (or above) the name, with real gaps between the
    name, the Latin name and the facts; there the facts are trimmed one by
    one until the block clears the bird. `under` skips the corner search."""
    W, H = CANVAS
    fi, fm = font("serif-italic", LATIN_PX), font("mono", FACTS_PX)
    occ = _occupancy(bird, xy)

    def rows_for(n):
        rows = [(latin, fi)] + ([("  /  ".join(facts[:n]), fm)] if n else [])
        heights = [f.getbbox(t)[3] - f.getbbox(t)[1] for t, f in rows]
        return rows, heights, sum(heights) + GAP_FACTS * (len(rows) - 1), max(text_w(d, t, f) for t, f in rows) + 10

    rows, heights, block_h, need_w = rows_for(len(facts))
    pick, free = None, {}
    if not under:
        free = {c: r for c, r in reversed(_free_rects(occ, 24, W, H, 48))}  # tallest per corner
        for c in ("tl", "tr", "bl", "br"):
            if c == corner or c not in free:
                continue
            x0, y0, x1, y1 = free[c]
            if x1 - x0 >= need_w and y1 - y0 >= block_h + 20:
                pick = c
                break
    if pick:
        x0, y0, x1, y1 = free[pick]
        right = pick[1] == "r"
        xa = x1 if right else x0
        y = y0 if pick[0] == "t" else y1 - block_h
    else:
        x0, y0, x1, y1 = rect
        right = corner[1] == "r"
        xa = x1 if right else x0
        top, bottom = _name_block_bounds(lines, size, corner, rect)
        for n in range(len(facts), -1, -1):
            rows, heights, block_h, need_w = rows_for(n)
            y = bottom + _gap_name(size) if corner[0] == "t" else top - _gap_name(size) - block_h
            box = (xa - need_w, int(y), xa, int(y + block_h)) if right else (xa, int(y), xa + need_w, int(y + block_h))
            if _box_free(occ, box):
                break
    for (t, f), h in zip(rows, heights):
        _put(d, t, f, xa, y, col(DARK), right)
        y += h + GAP_FACTS


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
    small_print(d, lines, size, corner, rect, info["scientific"], info["facts"][:4], bird, xy)
    return cv


# ---------------------------------------------------------------- closeup

def _head(st: Sticker):
    """(hx, hy, cx): the head, taken as the topmost band of the silhouette.
    Right for perched and standing birds, which is nearly all of the
    stickers; a bird in flight with a raised wing gets the wingtip instead."""
    xs, ys = alpha_points(st.im)
    top = ys.min()
    band = xs[ys < top + max(3, st.h * 0.08)]
    return float(np.median(band)), float(top), float(np.median(xs))


def closeup(st: Sticker, info: dict) -> Image.Image:
    """Head and shoulders, larger than the screen. Name small, in a corner."""
    W, H = CANVAS
    base = min(W / st.w, H / st.h)
    xs, ys = alpha_points(st.im)
    margin = 30
    if info.get("lifestyle") == "Aerial":
        # swifts, raptors, hummingbirds: often drawn in flight, so the top of the
        # silhouette is a wingtip. Frame the body instead, a little less tight.
        k = base * 1.4
        bx, by = float(np.median(xs)), float(np.median(ys))
        x, y = int(W * 0.5 - bx * k), int(H * 0.52 - by * k)
    else:
        k = base * 1.75
        hx, hy, cx = _head(st)
        # the head rows (top 30% of the silhouette, bill included) must fit on screen
        head_rows = ys < ys.min() + st.h * 0.30
        hx0, hx1 = float(xs[head_rows].min()), float(xs[head_rows].max())
        k = max(base * 1.15, min(k, (W - 2 * margin) / max(1.0, hx1 - hx0)))
        # head towards the emptier side, a third down the screen
        px = W * (0.60 if hx > cx else 0.40)
        py = H * 0.30
        x, y = int(px - hx * k), int(py - hy * k)
        x = min(x, int(margin - hx0 * k))          # bill/left edge of the head inside
        x = max(x, int(W - margin - hx1 * k))      # right edge of the head inside
    bird = sharpen(scaled(st, k))
    cv = new_canvas(WHITE)
    _paste_clip(cv, bird, x, y)
    d = ImageDraw.Draw(cv)
    occ = _occupancy(bird, (x, y))
    words = info["name"].upper().replace("-", "- ").split()
    r = _fit_name_in(d, words, _free_rects(occ, 24, W, H, 48), min_size=40)
    if r:
        size, lines, corner, rect = r
        size = min(size, 170)
        _draw_block(d, lines, size, corner, rect, col(BLACK))
        small_print(d, lines, size, corner, rect, info["scientific"], [], bird, (x, y), under=True)
    else:
        plate = Image.new("RGBA", (W - 96, 120), (WHITE, WHITE, WHITE, 230))
        cv.alpha_composite(plate, (48, H - 48 - 120))
        d.text((64, H - 48 - 110), info["name"].upper(),
               font=fit_font(d, info["name"].upper(), "sans", W - 140, 80, weight=900), fill=col(BLACK))
    return cv


# ---------------------------------------------------------------- quiet

def quiet(st: Sticker, info: dict) -> Image.Image:
    """The bird as big as it gets; one small line with both names, nothing else."""
    W, H = CANVAS
    M = 48
    fn, fl = font("sans", 60, 500), font("serif-italic", 50)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    name_w = text_w(d0, info["name"], fn)
    cap_w, cap_h = name_w + 30 + text_w(d0, info["scientific"], fl), 72
    choice = None
    for frac in (0.94, 0.86, 0.78):
        bird = fit(st, W * 0.96, H * frac)
        for ax in (1.0, 0.5, 0.0):  # right, centre, left
            x = int(ax * (W - 80 - bird.width)) + 40
            y = H - 40 - bird.height
            occ = _occupancy(bird, (x, y))
            for cy in (H - M - cap_h, M):  # caption bottom left, else top left
                cx = M if ax > 0 else W - M - cap_w
                if _box_free(occ, (cx - 16, cy - 10, cx + cap_w + 16, cy + cap_h + 10)):
                    choice = (bird, (x, y), cx, cy, False)
                    break
            if choice:
                break
        if choice:
            break
    if not choice:
        bird = fit(st, W * 0.96, H * 0.94)
        choice = (bird, (W - 40 - bird.width, H - 40 - bird.height), M, H - M - cap_h, True)
    bird, xy, cx, cy, plate = choice
    cv = new_canvas(WHITE)
    cv.alpha_composite(sharpen(bird), xy)
    if plate:
        pl = Image.new("RGBA", (cap_w + 32, cap_h + 20), (WHITE, WHITE, WHITE, 230))
        cv.alpha_composite(pl, (cx - 16, cy - 10))
    d = ImageDraw.Draw(cv)
    _put(d, info["name"], fn, cx, cy, col(BLACK), False)
    _put(d, info["scientific"], fl, cx + name_w + 30, cy + 12, col(MID), False)
    return cv


