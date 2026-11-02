"""The Bird of the Day pictures.

`hero()`, `closeup()` and `quiet()` each return a grayscale canvas for one
render target (a `Spec`): the drawable area of a TRMNL full view, displayed
1:1 on the panel. `finish()` quantizes it to the target's gray levels, 16 on
the X and 2 on the OG.

Flat areas use exact 16-level grays (multiples of 17) so they stay clean after
dithering; only the bird artwork and soft edges get dithered. On a 1-bit panel
every piece of type is pure black, since any gray would dither to speckle, and
the small facts line is left out.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"

WHITE, PAPER, PALE, LIGHT, MID, DARK, BLACK = 255, 238, 221, 204, 136, 68, 0


# ---------------------------------------------------------------- targets

@dataclass(frozen=True)
class Spec:
    """One render target: the view inside the panel's frame, shown 1:1."""
    key: str        # file name suffix, "" for the X landscape original
    size: tuple     # (W, H) of the view in panel pixels
    levels: int     # gray levels the panel shows: 16 (X) or 2 (OG)
    s: float = 1.0  # type and spacing scale relative to the X

    @property
    def W(self) -> int:
        return self.size[0]

    @property
    def H(self) -> int:
        return self.size[1]

    def px(self, v: float) -> int:
        """A length tuned on the X, scaled to this target."""
        return max(1, round(v * self.s))

    @property
    def cell(self) -> int:
        return self.px(24)

    @property
    def margin(self) -> int:
        return self.px(48)

    @property
    def facts(self) -> bool:
        return self.levels > 2

    @property
    def ink_small(self) -> int:
        return DARK if self.levels > 2 else BLACK

    @property
    def ink_latin(self) -> int:
        return MID if self.levels > 2 else BLACK


# TRMNL X: 1872x1404 panel, 16 grays, the full view leaves an 18 px frame.
# TRMNL OG: 800x480 panel, 1-bit, a 10 px frame (both measured on TRMNL's renderer).
X_LANDSCAPE = Spec("", (1836, 1368), 16)
X_PORTRAIT = Spec("portrait", (1368, 1836), 16)
OG_LANDSCAPE = Spec("og", (780, 460), 2, 0.5)
OG_PORTRAIT = Spec("og_portrait", (460, 780), 2, 0.5)
SPECS = [X_LANDSCAPE, X_PORTRAIT, OG_LANDSCAPE, OG_PORTRAIT]
CANVAS = X_LANDSCAPE.size


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


def latin_font(sp: Spec) -> ImageFont.FreeTypeFont:
    """Instrument Serif Italic on the X; its hairlines break up in 1-bit, so
    the OG gets Inter Italic Medium, never smaller than 24 px."""
    if sp.levels > 2:
        return font("serif-italic", sp.px(50))
    return font("sans-italic", max(24, sp.px(50)), 500)


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


def sharpen(im: Image.Image, sp: Spec = X_LANDSCAPE) -> Image.Image:
    radius = 2 if sp.s >= 1 else 1
    rgb = im.convert("RGB").filter(ImageFilter.UnsharpMask(radius=radius, percent=70, threshold=2))
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


def new_canvas(sp: Spec = X_LANDSCAPE, level=WHITE) -> Image.Image:
    return Image.new("RGBA", sp.size, (level, level, level, 255))


def finish(canvas: Image.Image, dst: Path, levels=16) -> None:
    """Floyd-Steinberg to `levels` grays; 2 levels are saved as a 1-bit PNG."""
    gray = canvas.convert("RGB").convert("L")
    pal = Image.new("P", (1, 1))
    lv = [round(i * 255 / (levels - 1)) for i in range(levels)]
    pal.putpalette([v for x in lv for v in (x, x, x)] + [0] * 3 * (256 - levels))
    q = gray.convert("RGB").quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG).convert("L")
    if levels == 2:
        q = q.convert("1", dither=Image.Dither.NONE)
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


def _biggest_type(d, words, max_w, max_h, sp, start=None, min_lines=1, max_lines=4, lead=0.86):
    """Largest Inter Black that sets `words` in 1..max_lines lines inside max_w x max_h."""
    start = start or sp.px(700)
    floor, step = sp.px(60), sp.px(16)
    best = None
    for nl in range(min_lines, min(max_lines, len(words)) + 1):
        for split in _splits(words, nl):
            lines = [" ".join(p).replace("- ", "-") for p in split]
            size = start
            while size > floor:
                f = font("sans", size, 900)
                lw = max(text_w(d, s_, f) for s_ in lines)
                if lw <= max_w and size * lead * len(lines) <= max_h:
                    break
                size -= step
            if best is None or size > best[0]:
                best = (size, lines)
    return best


# ---------------------------------------------------------------- small print

def _gap_name(size: int, sp: Spec) -> int:
    """Air between the name block and the small print under (or above) it."""
    return max(sp.px(40), int(size * 0.14))


def _name_block_bounds(lines, size, corner, rect):
    """Top and bottom of the glyphs as _draw_block paints them."""
    f = font("sans", size, 900)
    lead = size * 0.86
    x0, y0, x1, y1 = rect
    y = y0 if corner[0] == "t" else y1 - lead * len(lines)
    bb = f.getbbox(lines[-1])
    return y + size * 0.04, y + lead * (len(lines) - 1) + size * 0.04 + (bb[3] - bb[1])


def _box_free(occ: np.ndarray, box, cell: int) -> bool:
    """True when no occupied grid cell touches the pixel box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    gy0, gy1 = max(0, y0 // cell), min(occ.shape[0], y1 // cell + 1)
    gx0, gx1 = max(0, x0 // cell), min(occ.shape[1], x1 // cell + 1)
    return not occ[gy0:gy1, gx0:gx1].any()


def _mark(occ: np.ndarray, box, cell: int) -> None:
    """Mark the grid cells the pixel box (x0, y0, x1, y1) touches as occupied."""
    x0, y0, x1, y1 = box
    gy0, gy1 = max(0, y0 // cell), min(occ.shape[0], y1 // cell + 1)
    gx0, gx1 = max(0, x0 // cell), min(occ.shape[1], x1 // cell + 1)
    occ[gy0:gy1, gx0:gx1] = True


def _put(d, s, f, x_anchor, y_top, fill, right):
    """Draw `s` with its glyph box starting at y_top; right-aligned to x_anchor if asked."""
    bb = f.getbbox(s)
    x = x_anchor - (bb[2] - bb[0]) if right else x_anchor
    d.text((x - bb[0], y_top - bb[1]), s, font=f, fill=fill)
    return bb[3] - bb[1]


def small_print(d, sp, lines, size, corner, rect, latin, facts, bird, xy, under=False):
    """Latin name and facts in small type. On the X: in a free corner the name
    does not use, else right under (or above) the name, with real gaps between
    the name, the Latin name and the facts; there the facts are trimmed one by
    one until the block clears the bird. On a 1-bit panel there is only the
    Latin name, and a lone line in the opposite corner looks orphaned, so it
    goes under the name first and into a corner only when that spot is taken.
    `under` skips the corner search altogether."""
    W, H = sp.size
    fi, fm = latin_font(sp), font("mono", sp.px(28))
    gap = sp.px(26)
    occ = _occupancy(bird, xy, sp)
    top, bottom = _name_block_bounds(lines, size, corner, rect)

    def rows_for(n):
        rows = [(latin, fi)] + ([("  /  ".join(facts[:n]), fm)] if n else [])
        heights = [f.getbbox(t)[3] - f.getbbox(t)[1] for t, f in rows]
        return rows, heights, sum(heights) + gap * (len(rows) - 1), max(text_w(d, t, f) for t, f in rows) + sp.px(10)

    def under_name(n):
        """Rows and position for n facts right under (or above) the name, and whether the spot is free."""
        rows, heights, block_h, need_w = rows_for(n)
        x0, y0, x1, y1 = rect
        right = corner[1] == "r"
        xa = x1 if right else x0
        y = bottom + _gap_name(size, sp) if corner[0] == "t" else top - _gap_name(size, sp) - block_h
        box = (xa - need_w, int(y), xa, int(y + block_h)) if right else (xa, int(y), xa + need_w, int(y + block_h))
        return rows, heights, xa, y, right, _box_free(occ, box, sp.cell)

    def corner_search():
        # for the corner search the name block (with its air) is occupied too;
        # in the narrow portrait views the name spans the width, and a corner
        # that only dodges the bird would run straight into it
        rows, heights, block_h, need_w = rows_for(len(facts))
        fb = font("sans", size, 900)
        name_w = max(fb.getbbox(s_)[2] - fb.getbbox(s_)[0] for s_ in lines)
        nx0 = rect[0] if corner[1] == "l" else rect[2] - name_w
        occ_c = occ.copy()
        _mark(occ_c, (nx0, int(top - _gap_name(size, sp)), nx0 + name_w, int(bottom + _gap_name(size, sp))), sp.cell)
        free = {c: r for c, r in reversed(_free_rects(occ_c, sp))}  # tallest per corner
        for c in ("tl", "tr", "bl", "br"):
            if c == corner or c not in free:
                continue
            x0, y0, x1, y1 = free[c]
            if x1 - x0 >= need_w and y1 - y0 >= block_h + sp.px(20):
                right = c[1] == "r"
                return rows, heights, (x1 if right else x0), (y0 if c[0] == "t" else y1 - block_h), right
        return None

    placed = None
    if under or not sp.facts:
        rows, heights, xa, y, right, ok = under_name(len(facts))
        if ok or under:
            placed = (rows, heights, xa, y, right)
    if placed is None:
        placed = corner_search()
    if placed is None:
        for n in range(len(facts), -1, -1):
            rows, heights, xa, y, right, ok = under_name(n)
            if ok:
                break
        placed = (rows, heights, xa, y, right)
    rows, heights, xa, y, right = placed
    for (t, f), h in zip(rows, heights):
        _put(d, t, f, xa, y, col(sp.ink_small), right)
        y += h + gap


# ---------------------------------------------------------------- bird first

def _free_rects(occ: np.ndarray, sp: Spec):
    """Corner-anchored empty rectangles (x0, y0, x1, y1) in a coarse occupancy grid."""
    cell, W, H, margin = sp.cell, sp.W, sp.H, sp.margin
    gh, gw = occ.shape
    m = margin // cell
    rects = []
    for corner in ("tl", "tr", "bl", "br"):
        grid = occ.copy()
        if corner[1] == "r":
            grid = grid[:, ::-1]
        if corner[0] == "b":
            grid = grid[::-1, :]
        # for each height from the corner, the widest free span; the far
        # margin counts too, or a name in a narrow view runs into the edge
        width = gw - 2 * m
        for h in range(1, gh - m):
            row = grid[m + h - 1, m:gw - m]
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


def _occupancy(bird: Image.Image, xy, sp: Spec):
    """Coarse grid of cells the bird's alpha touches (vectorised)."""
    cell, W, H = sp.cell, sp.W, sp.H
    gh, gw = H // cell + 1, W // cell + 1
    a = np.zeros((gh * cell, gw * cell), dtype=bool)
    x, y = xy
    l, t = max(0, x), max(0, y)
    r, b = min(W, x + bird.width), min(H, y + bird.height)
    if r > l and b > t:
        a[t:b, l:r] = np.asarray(bird.getchannel("A"))[t - y:b - y, l - x:r - x] > 40
    return a.reshape(gh, cell, gw, cell).any(axis=(1, 3))


def _fit_name_in(d, words, rects, sp, min_size=None):
    """Biggest Inter Black setting of `words` inside any of the rects."""
    min_size = min_size or sp.px(48)
    best = None
    for corner, (x0, y0, x1, y1) in rects:
        w, h = x1 - x0, y1 - y0
        if w < sp.px(200) or h < sp.px(60):
            continue
        r = _biggest_type(d, words, w, h, sp, start=min(sp.px(620), int(h / 0.86) + sp.px(8)), max_lines=3, lead=0.86)
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


def hero(st: Sticker, info: dict, sp: Spec = X_LANDSCAPE) -> Image.Image:
    """The bird as big as it gets; the name takes whatever space is left."""
    W, H = sp.size
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    words = info["name"].upper().replace("-", "- ").split()
    best = None
    for frac in (0.92, 0.82, 0.72):
        bird = fit(st, W * 0.96, H * frac)
        for ax in (0.5, 0.64, 0.36):
            x = int(ax * W - bird.width / 2)
            x = max(sp.px(20), min(W - bird.width - sp.px(20), x))
            y = int(H - sp.px(40) - bird.height) if frac > 0.85 else int((H - bird.height) / 2)
            occ = _occupancy(bird, (x, y), sp)
            r = _fit_name_in(d0, words, _free_rects(occ, sp), sp)
            if r and (best is None or r[0] > best[0]):
                best = (r[0], r[1], r[2], r[3], bird, (x, y))
            if best and best[0] >= sp.px(200):
                break
        if best and best[0] >= sp.px(200):
            break
    size, lines, corner, rect, bird, xy = best
    cv = new_canvas(sp)
    cv.alpha_composite(sharpen(bird, sp), xy)
    d = ImageDraw.Draw(cv)
    _draw_block(d, lines, size, corner, rect, col(BLACK))
    facts = info["facts"][:4] if sp.facts else []
    small_print(d, sp, lines, size, corner, rect, info["scientific"], facts, bird, xy)
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


def closeup(st: Sticker, info: dict, sp: Spec = X_LANDSCAPE) -> Image.Image:
    """Head and shoulders, larger than the screen. Name small, in a corner."""
    W, H = sp.size
    base = min(W / st.w, H / st.h)
    xs, ys = alpha_points(st.im)
    margin = sp.px(30)
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
        px_ = W * (0.60 if hx > cx else 0.40)
        py = H * 0.30
        x, y = int(px_ - hx * k), int(py - hy * k)
        x = min(x, int(margin - hx0 * k))          # bill/left edge of the head inside
        x = max(x, int(W - margin - hx1 * k))      # right edge of the head inside
    bird = sharpen(scaled(st, k), sp)
    cv = new_canvas(sp)
    _paste_clip(cv, bird, x, y)
    d = ImageDraw.Draw(cv)
    occ = _occupancy(bird, (x, y), sp)
    words = info["name"].upper().replace("-", "- ").split()
    r = _fit_name_in(d, words, _free_rects(occ, sp), sp, min_size=sp.px(40))
    if r:
        size, lines, corner, rect = r
        size = min(size, sp.px(170))
        _draw_block(d, lines, size, corner, rect, col(BLACK))
        small_print(d, sp, lines, size, corner, rect, info["scientific"], [], bird, (x, y), under=True)
    else:
        m, ph = sp.px(48), sp.px(120)
        plate = Image.new("RGBA", (W - 2 * m, ph), (WHITE, WHITE, WHITE, 230))
        cv.alpha_composite(plate, (m, H - m - ph))
        d.text((sp.px(64), H - m - sp.px(110)), info["name"].upper(),
               font=fit_font(d, info["name"].upper(), "sans", W - sp.px(140), sp.px(80), weight=900), fill=col(BLACK))
    return cv


# ---------------------------------------------------------------- quiet

def quiet(st: Sticker, info: dict, sp: Spec = X_LANDSCAPE) -> Image.Image:
    """The bird as big as it gets; one small line with both names, nothing else.
    When the line would not fit the width, the Latin name goes under the name."""
    W, H = sp.size
    M = sp.margin
    fn, fl = font("sans", sp.px(60), 500), latin_font(sp)
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    name_w, latin_w = text_w(d0, info["name"], fn), text_w(d0, info["scientific"], fl)
    cap_w, cap_h = name_w + sp.px(30) + latin_w, sp.px(72)
    stacked = cap_w > W - 2 * M
    if stacked:
        cap_w, cap_h = max(name_w, latin_w), sp.px(72) + sp.px(58)
    choice = None
    for frac in (0.94, 0.86, 0.78):
        bird = fit(st, W * 0.96, H * frac)
        for ax in (1.0, 0.5, 0.0):  # right, centre, left
            x = int(ax * (W - sp.px(80) - bird.width)) + sp.px(40)
            y = H - sp.px(40) - bird.height
            occ = _occupancy(bird, (x, y), sp)
            for cy in (H - M - cap_h, M):  # caption bottom left, else top left
                cx = M if ax > 0 else W - M - cap_w
                if _box_free(occ, (cx - sp.px(16), cy - sp.px(10), cx + cap_w + sp.px(16), cy + cap_h + sp.px(10)), sp.cell):
                    choice = (bird, (x, y), cx, cy, False)
                    break
            if choice:
                break
        if choice:
            break
    if not choice:
        bird = fit(st, W * 0.96, H * 0.94)
        choice = (bird, (W - sp.px(40) - bird.width, H - sp.px(40) - bird.height), M, H - M - cap_h, True)
    bird, xy, cx, cy, plate = choice
    cv = new_canvas(sp)
    cv.alpha_composite(sharpen(bird, sp), xy)
    if plate:
        pl = Image.new("RGBA", (cap_w + 2 * sp.px(16), cap_h + 2 * sp.px(10)), (WHITE, WHITE, WHITE, 230))
        cv.alpha_composite(pl, (cx - sp.px(16), cy - sp.px(10)))
    d = ImageDraw.Draw(cv)
    _put(d, info["name"], fn, cx, cy, col(BLACK), False)
    if stacked:
        _put(d, info["scientific"], fl, cx, cy + sp.px(72), col(sp.ink_latin), False)
    else:
        _put(d, info["scientific"], fl, cx + name_w + sp.px(30), cy + sp.px(12), col(sp.ink_latin), False)
    return cv
