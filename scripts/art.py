"""Image compositions for the Bird of the Day variants.

Every function returns a grayscale canvas of exactly CANVAS (the drawable area
of a TRMNL X full view, displayed 1:1). `finish()` quantizes it to 16 grays.

Flat areas use exact 16-level grays (multiples of 17) so they stay clean after
dithering; only the bird artwork and soft edges get dithered.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"

# TRMNL X: 1872x1404 panel, the full view leaves an 18 px frame.
CANVAS = (1836, 1368)
# 10.3" 4:3 panel -> 20.93 cm wide -> 89.4 px per cm. Override with PX_PER_CM.
PX_PER_CM = 1872 / 20.93

WHITE, PAPER, PALE, LIGHT, MID, DARK, BLACK = 255, 238, 221, 204, 136, 68, 0


def col(v: int) -> tuple:
    """Opaque RGBA ink from a gray value (ImageDraw reads a bare int on RGBA as packed RGBA)."""
    return (v, v, v, 255)


def g(level: int) -> int:
    """Gray for 16-level index 0..15."""
    return level * 17


# ---------------------------------------------------------------- fonts

def font(name: str, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
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


def fit_font(d, s, name, max_w, start, minimum=10, weight=None):
    size = start
    while size > minimum:
        f = font(name, size, weight)
        if text_w(d, s, f) <= max_w:
            return f
        size -= 2
    return font(name, minimum, weight)


def wrap(d, s, f, max_w):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if text_w(d, t, f) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def spaced(s: str, n: int = 1) -> str:
    return (" " * n).join(s)


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


def with_border(im: Image.Image, px: int, fill=WHITE) -> Image.Image:
    """Die-cut sticker edge: grow the alpha by px and fill it with `fill`."""
    pad = px + 2
    big = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    big.alpha_composite(im, (pad, pad))
    a = big.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    grown = a.filter(ImageFilter.MaxFilter(2 * (px // 2) + 1))
    if px > 6:
        grown = grown.filter(ImageFilter.MaxFilter(2 * (px - px // 2) + 1))
    grown = grown.filter(ImageFilter.GaussianBlur(1)).point(lambda v: 255 if v > 110 else 0)
    base = Image.new("RGBA", big.size, (fill, fill, fill, 0))
    base.putalpha(grown)
    base.alpha_composite(big)
    return base


def silhouette(im: Image.Image, level=BLACK) -> Image.Image:
    a = im.getchannel("A").point(lambda v: 255 if v > 90 else 0)
    out = Image.new("RGBA", im.size, (level, level, level, 0))
    out.putalpha(a)
    return out


def drop(canvas: Image.Image, im: Image.Image, xy, shadow=(10, 12), shade=MID):
    """Paste with a hard offset shadow (print-like, no blur noise on e-paper)."""
    x, y = int(xy[0]), int(xy[1])
    if shadow:
        _paste_clip(canvas, silhouette(im, shade), x + shadow[0], y + shadow[1])
    _paste_clip(canvas, im, x, y)


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


def alpha_points(im: Image.Image, thresh=120):
    a = np.asarray(im.getchannel("A")) > thresh
    ys, xs = np.nonzero(a)
    return xs, ys


# ---------------------------------------------------------------- 1 life size

def life_size(st: Sticker, info: dict, px_per_cm: float = PX_PER_CM) -> Image.Image:
    """The bird at true size on the glass, with a real centimetre ruler.

    Small birds fit whole. Bigger ones show a true-size window around the head;
    when that would mean upscaling the sticker more than ~3x, the window is
    drawn as a crisp hatched outline instead of a blurry enlargement.
    """
    W, H = CANVAS
    cv = new_canvas(WHITE)
    d = ImageDraw.Draw(cv)
    factor = info["length_cm"] * px_per_cm / max(st.w, st.h)
    ruler_h = 92
    view_h = H - ruler_h
    mode = "whole"
    if st.w * factor > W - 120 or st.h * factor > view_h - 300:
        mode = "detail" if factor <= 3.2 else "outline"

    if mode == "whole":
        bird = sharpen(scaled(st, factor))
        bx = min((W - bird.width) // 2 + 160, W - bird.width - 50)
        by = view_h - bird.height - 50
        cv.alpha_composite(bird, (bx, by))
    else:
        xs, ys = alpha_points(st.im)
        win_w, win_h = W / factor, view_h / factor
        top = ys.min()
        if mode == "detail":
            # head: the topmost part of the silhouette
            band = xs[ys < top + max(3, st.h * 0.06)]
            hx, hy = float(np.median(band)), float(top)
            x0, y0 = hx - 0.62 * win_w, hy - 0.08 * win_h
        else:
            # bill tip: the point of the upper third that sticks out furthest
            upper = ys < top + st.h * 0.33
            ux, uy = xs[upper], ys[upper]
            cx = float(np.median(xs))
            i = int(np.argmin(ux)) if cx - ux.min() > ux.max() - cx else int(np.argmax(ux))
            tx, ty = float(ux[i]), float(uy[i])
            x0 = tx - 0.10 * win_w if tx < cx else tx - 0.90 * win_w
            y0 = ty - 0.55 * win_h
        box = (round(x0), round(y0), round(x0 + win_w), round(y0 + win_h))
        crop = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
        src = st.im.crop((max(0, box[0]), max(0, box[1]), min(st.w, box[2]), min(st.h, box[3])))
        crop.alpha_composite(src, (max(0, -box[0]), max(0, -box[1])))
        if mode == "detail":
            cv.alpha_composite(sharpen(crop.resize((W, view_h), Image.LANCZOS)), (0, 0))
        else:
            cv.alpha_composite(_screenprint(crop, (W, view_h)), (0, 0))
        # "you are here" map
        thumb = sharpen(fit(st, 300, 300))
        tf = thumb.width / st.w
        card = Image.new("RGBA", (thumb.width + 60, thumb.height + 110), col(WHITE))
        cd = ImageDraw.Draw(card)
        card.alpha_composite(thumb, (30, 30))
        r = [30 + box[0] * tf, 30 + box[1] * tf, 30 + box[2] * tf, 30 + box[3] * tf]
        r = [max(6, r[0]), max(6, r[1]), min(card.width - 7, r[2]), min(card.height - 80, r[3])]
        cd.rectangle(r, outline=col(BLACK), width=4)
        cd.rectangle([0, 0, card.width - 1, card.height - 1], outline=col(BLACK), width=3)
        cd.text((30, card.height - 64), "you are here", font=font("serif-italic", 38), fill=col(BLACK))
        drop(cv, card, (W - card.width - 44, view_h - card.height - 40), shadow=(8, 10), shade=LIGHT)

    # ruler, true centimetres
    d.rectangle([0, view_h, W, H], fill=col(WHITE))
    d.line([0, view_h, W, view_h], fill=col(BLACK), width=3)
    fm = font("mono", 24)
    mm = 0
    while mm * px_per_cm / 10 <= W:
        x = round(mm * px_per_cm / 10)
        tick = 46 if mm % 10 == 0 else 28 if mm % 5 == 0 else 14
        d.line([x, view_h, x, view_h + tick], fill=col(BLACK), width=3 if mm % 10 == 0 else 2)
        if mm % 10 == 0 and mm:
            d.text((x + 6, view_h + 44), f"{mm // 10}" + (" cm" if mm == 10 else ""), font=fm, fill=col(BLACK))
        mm += 1

    # caption card
    title = {"whole": "Actual size.", "detail": "Actual size, in part.",
             "outline": "Actual size, abstracted."}[mode]
    how = "" if info["length_how"] == "measured" else f" ({info['length_how']})"
    note = [f"About {info['length_cm']:.0f} cm long{how}." if info["length_cm"] >= 10
            else f"About {info['length_cm']:.1f} cm long{how}."]
    if mode != "whole":
        note.append(f"The screen holds {W / px_per_cm:.0f} x {view_h / px_per_cm:.0f} cm of it.")
    rows = [(title, font("serif-italic", 112), BLACK),
            (info["name"], fit_font(d, info["name"], "serif", W * 0.5, 72), BLACK),
            (info["scientific"], font("serif-italic", 44), DARK)]
    rows += [(n, font("mono", 25), DARK) for n in note]
    pad, y, wmax = 40, 0, 0
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    for s_, f, _ in rows:
        b = tmp.textbbox((0, 0), s_, font=f)
        wmax = max(wmax, b[2])
        y += (b[3] - b[1]) + 22
    card = Image.new("RGBA", (wmax + 2 * pad, y + 2 * pad), col(WHITE))
    cd = ImageDraw.Draw(card)
    y = pad
    for s_, f, c in rows:
        b = cd.textbbox((pad, y), s_, font=f)
        cd.text((pad, y - (b[1] - y)), s_, font=f, fill=col(c))
        y += (b[3] - b[1]) + 22
    if mode != "whole":
        cd.rectangle([0, 0, card.width - 1, card.height - 1], outline=col(BLACK), width=3)
        drop(cv, card, (30, 30), shadow=(8, 10), shade=LIGHT)
    else:
        cv.alpha_composite(card, (20, 20))
    return cv


def _screenprint(crop: Image.Image, size) -> Image.Image:
    """Big enlargement as flat tone bands with a crisp edge: reads as a print,
    not as a blurry photo."""
    up = crop.resize(size, Image.BICUBIC)
    base = Image.new("RGBA", size, col(WHITE))
    base.alpha_composite(up)
    gray = base.convert("L").filter(ImageFilter.GaussianBlur(5))
    tones = gray.point(lambda v: 0 if v < 70 else 85 if v < 140 else 187 if v < 215 else 238)
    tones = tones.filter(ImageFilter.ModeFilter(9))
    m = up.getchannel("A").filter(ImageFilter.GaussianBlur(3)).point(lambda v: 255 if v > 128 else 0)
    edge = ImageChops.subtract(m.filter(ImageFilter.MaxFilter(7)), m.filter(ImageFilter.MinFilter(5)))
    out = Image.merge("RGBA", (tones, tones, tones, m))
    ink = Image.new("RGBA", size, col(BLACK))
    ink.putalpha(edge)
    out.alpha_composite(ink)
    return out


# ---------------------------------------------------------------- 2 flock

def flock(today: tuple[Sticker, dict], others: list[tuple[Sticker, dict]], seed: str,
          caption: dict) -> Image.Image:
    """Sticker-bomb of today's bird and relatives, each scaled by wing length."""
    W, H = CANVAS
    rnd = random.Random(seed)
    cv = new_canvas(PALE)
    birds = [today] + others
    lens = [b[1]["wing_mm"] for b in birds]
    # scale so that stickers cover ~60% of the canvas
    def area(k):
        return sum((st.w * k * l / max(st.w, st.h)) * (st.h * k * l / max(st.w, st.h)) for (st, _), l in zip(birds, lens))
    k = math.sqrt(0.60 * W * H / area(1.0))
    k = min(k, 0.62 * H / max(lens))
    C, P = 8, 160  # grid cell in px, padding in cells
    gh, gw = H // C + 1, W // C + 1
    occupied = np.zeros((gh + 2 * P, gw + 2 * P), dtype=np.int16)
    onscreen = np.zeros_like(occupied, dtype=bool)
    onscreen[P:P + gh, P:P + gw] = True
    placed = []
    order = sorted(range(len(birds)), key=lambda i: -lens[i])
    label_box = (0, H - 330, 760, H)
    for i in order:
        st, info = birds[i]
        L = lens[i] * k
        im = scaled(st, L / max(st.w, st.h))
        im = with_border(sharpen(im), max(6, int(L * 0.022)))
        ang = rnd.uniform(-16, 16) if i else rnd.uniform(-6, 6)
        im = im.rotate(ang, resample=Image.BICUBIC, expand=True)
        m = np.asarray(im.getchannel("A").resize((max(1, im.width // C), max(1, im.height // C)))) > 60
        mh, mw = m.shape
        total = m.sum()
        best = None
        for _ in range(600 if i == 0 else 350):
            if i == 0:
                cx, cy = rnd.uniform(0.40, 0.62) * W, rnd.uniform(0.34, 0.52) * H
            else:
                cx, cy = rnd.uniform(-0.04, 1.04) * W, rnd.uniform(-0.04, 1.04) * H
            x, y = int(cx - im.width / 2), int(cy - im.height / 2)
            gx, gy = x // C + P, y // C + P
            if gx < 0 or gy < 0 or gx + mw > occupied.shape[1] or gy + mh > occupied.shape[0]:
                continue
            ov = float((occupied[gy:gy + mh, gx:gx + mw][m] > 0).sum())
            off = total - float(onscreen[gy:gy + mh, gx:gx + mw][m].sum())
            lb = _rect_overlap((x, y, x + im.width, y + im.height), label_box) / (C * C)
            score = ov + off * 0.9 + lb * 0.6
            if best is None or score < best[0]:
                best = (score, x, y, gx, gy)
        _, x, y, gx, gy = best
        occupied[gy:gy + mh, gx:gx + mw] += m
        placed.append((i, im, x, y))
    # draw: relatives first, today's bird last (on top)
    for i, im, x, y in sorted(placed, key=lambda p: p[0] == 0):
        drop(cv, im, (x, y), shadow=(12, 14), shade=LIGHT if i else MID)
    d = ImageDraw.Draw(cv)
    # today's tag
    _, im0, x0, y0 = next(p for p in placed if p[0] == 0)
    tag = "TODAY"
    ft = font("mono-medium", 30)
    tw = text_w(d, tag, ft)
    tx, ty = min(max(20, x0 + im0.width // 2 - tw // 2 - 22), W - tw - 64), max(16, y0 - 64)
    d.rounded_rectangle([tx, ty, tx + tw + 44, ty + 54], radius=27, fill=col(BLACK))
    d.text((tx + 22, ty + 8), tag, font=ft, fill=col(WHITE))
    # label card, a white sticker of its own
    card = _label_card(caption, 700)
    card = with_border(card, 4, WHITE).rotate(2.2, resample=Image.BICUBIC, expand=True)
    drop(cv, card, (40, H - card.height - 30), shadow=(10, 12), shade=MID)
    return cv


def _rect_overlap(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0, w) * max(0, h)


def _label_card(c: dict, width: int) -> Image.Image:
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    pad = 36
    f1 = fit_font(tmp, c["title"], "serif", width - 2 * pad, 84)
    f2 = font("serif-italic", 38)
    f3 = font("mono", 24)
    sub = wrap(tmp, c["subtitle"], f2, width - 2 * pad)
    foot = wrap(tmp, c["footer"], f3, width - 2 * pad)
    h = pad + 90 + 46 * len(sub) + 14 + 32 * len(foot) + pad
    card = Image.new("RGBA", (width, h), (WHITE, WHITE, WHITE, 255))
    d = ImageDraw.Draw(card)
    y = pad - 10
    d.text((pad, y), c["title"], font=f1, fill=col(BLACK))
    y += 92
    for s in sub:
        d.text((pad, y), s, font=f2, fill=col(DARK))
        y += 46
    y += 14
    for s in foot:
        d.text((pad, y), s, font=f3, fill=col(DARK))
        y += 32
    return card


# ---------------------------------------------------------------- 3 album

def album(days: list[dict], today_idx: int, month_title: str, year: str, first_weekday: int,
          tagline: str) -> Image.Image:
    """Month as a sticker calendar. days[i] = {"st": Sticker|None, "day": n}."""
    W, H = CANVAS
    cv = new_canvas(WHITE)
    d = ImageDraw.Draw(cv)
    head = 190
    d.text((48, 18), month_title, font=font("serif", 150), fill=col(BLACK))
    mw = text_w(d, month_title, font("serif", 150))
    d.text((48 + mw + 28, 104), year, font=font("mono", 40), fill=col(DARK))
    ft = font("serif-italic", 40)
    for j, s in enumerate(wrap(d, tagline, ft, W - mw - 420)[:2]):
        tw = text_w(d, s, ft)
        d.text((W - 48 - tw, 70 + j * 50), s, font=ft, fill=col(DARK))
    ndays = len(days)
    rows = math.ceil((first_weekday + ndays) / 7)
    gx0, gy0 = 30, head + 46
    cw, ch = (W - 2 * gx0) / 7, (H - gy0 - 20) / rows
    fw = font("mono", 22)
    for c, wd in enumerate(["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]):
        d.text((gx0 + c * cw + 14, head + 6), wd, font=fw, fill=col(MID))
    rnd = random.Random(month_title + year)
    fd = font("mono-medium", 24)
    for i, info in enumerate(days):
        cell = first_weekday + i
        r, c = divmod(cell, 7)
        x0, y0 = gx0 + c * cw, gy0 + r * ch
        box = [x0 + 6, y0 + 6, x0 + cw - 6, y0 + ch - 6]
        future = i > today_idx
        if i == today_idx:
            d.rounded_rectangle(box, radius=18, fill=col(PAPER), outline=col(BLACK), width=5)
        elif future:
            _dashed_round_rect(d, box, PALE, 3)
        else:
            d.rounded_rectangle(box, radius=18, fill=col(PAPER))
        st = info.get("st")
        if st is not None:
            mx, my = (box[2] - box[0]) * 0.84, (box[3] - box[1]) * 0.80
            im = fit(st, mx, my)
            if future:
                im = silhouette(im, PALE)
                xy = (box[0] + (box[2] - box[0] - im.width) / 2, box[1] + (box[3] - box[1] - im.height) / 2 + 8)
                _paste_clip(cv, im, int(xy[0]), int(xy[1]))
            else:
                im = with_border(sharpen(im), 5).rotate(rnd.uniform(-7, 7), resample=Image.BICUBIC, expand=True)
                xy = (box[0] + (box[2] - box[0] - im.width) / 2, box[1] + (box[3] - box[1] - im.height) / 2 + 8)
                drop(cv, im, xy, shadow=(5, 6), shade=LIGHT)
        n = str(info["day"])
        if i == today_idx:
            tw = text_w(d, n, fd)
            d.rounded_rectangle([box[0] + 10, box[1] + 10, box[0] + 34 + tw, box[1] + 50], radius=20, fill=col(BLACK))
            d.text((box[0] + 22, box[1] + 12), n, font=fd, fill=col(WHITE))
        else:
            d.text((box[0] + 14, box[1] + 10), n, font=fd, fill=col(LIGHT) if future else MID)
    return cv


def _dashed_round_rect(d, box, color, width, dash=14, gap=10):
    x0, y0, x1, y1 = box
    for (ax, ay, bx, by) in [(x0, y0, x1, y0), (x1, y0, x1, y1), (x0, y1, x1, y1), (x0, y0, x0, y1)]:
        length = math.hypot(bx - ax, by - ay)
        n = int(length // (dash + gap))
        for k in range(n + 1):
            t0, t1 = k * (dash + gap) / length, min(1, (k * (dash + gap) + dash) / length)
            d.line([ax + (bx - ax) * t0, ay + (by - ay) * t0, ax + (bx - ax) * t1, ay + (by - ay) * t1], fill=col(color), width=width)


# ---------------------------------------------------------------- 4 poster

def poster(st: Sticker, info: dict) -> Image.Image:
    W, H = CANVAS
    cv = new_canvas(WHITE)
    d = ImageDraw.Draw(cv)
    words = info["name"].upper().replace("-", "- ").split()
    margin = 54
    best = None
    # try 1..4 lines, pick the biggest type that fits
    for nl in range(1, min(4, len(words)) + 1):
        for split in _splits(words, nl):
            lines = [" ".join(p).replace("- ", "-") for p in split]
            size = 700
            while size > 60:
                f = font("sans", size, 900)
                lw = max(text_w(d, s, f) for s in lines)
                lh = size * 0.86 * len(lines)
                if lw <= W - 2 * margin and lh <= H * 0.80:
                    break
                size -= 8
            if best is None or size > best[0]:
                best = (size, lines)
    size, lines = best
    f = font("sans", size, 900)
    lead = size * 0.86
    y = H - margin - lead * len(lines) + size * 0.06
    for s in lines:
        asc = f.getbbox(s)[1]
        d.text((margin - f.getbbox(s)[0], y - asc), s, font=f, fill=col(BLACK))
        y += lead
    # the bird, overlapping the type, with a die-cut white edge
    bird = fit(st, W * 0.66, H * 0.86)
    bird = with_border(sharpen(bird), 16)
    bx, by = W - bird.width - 10, (H - bird.height) // 2 - 40
    _paste_clip(cv, bird, bx, max(0, by))
    # small print
    fi = font("serif-italic", 52)
    d.text((margin, 40), info["scientific"], font=fi, fill=col(BLACK))
    fm = font("mono", 26)
    y = 112
    for s in info["facts"][:5]:
        d.text((margin, y), s, font=fm, fill=col(DARK))
        y += 38
    return cv


def _splits(words, n):
    if n == 1:
        yield [words]
        return
    for i in range(1, len(words) - n + 2):
        for rest in _splits(words[i:], n - 1):
            yield [words[:i]] + rest


# ---------------------------------------------------------------- 5 specimen

def specimen(st: Sticker, info: dict, seed: str) -> Image.Image:
    W, H = CANVAS
    rnd = random.Random(seed)
    cv = new_canvas(PAPER)
    d = ImageDraw.Draw(cv)
    m = 34
    d.rectangle([m, m, W - m, H - m], outline=col(BLACK), width=4)
    d.rectangle([m + 12, m + 12, W - m - 12, H - m - 12], outline=col(BLACK), width=1)
    # header
    fh = font("mono", 26)
    head = spaced(info["family_latin"].upper(), 1)
    d.text((m + 48, m + 40), head, font=fh, fill=col(BLACK))
    d.text((m + 48, m + 80), info["family_en"], font=font("serif-italic", 40), fill=col(DARK))
    plate = f"No. {info['seq']}"
    fp = font("serif", 64)
    d.text((W - m - 48 - text_w(d, plate, fp), m + 34), plate, font=fp, fill=col(BLACK))
    # bird
    area = (m + 60, m + 150, W * 0.64, H - m - 210)
    bird = sharpen(fit(st, area[2] - area[0], area[3] - area[1]))
    bx = int(area[0] + (area[2] - area[0] - bird.width) / 2)
    by = int(area[1] + (area[3] - area[1] - bird.height) / 2)
    cv.alpha_composite(bird, (bx, by))
    # caption under the bird
    fn = fit_font(d, info["name"], "serif", W * 0.58, 96)
    d.text((m + 60, H - m - 190), info["name"], font=fn, fill=col(BLACK))
    d.text((m + 60, H - m - 88), f"{info['scientific']}  {info['authority']}".strip(), font=font("serif-italic", 46), fill=col(DARK))
    # specimen tag tied to the lowest point of the bird
    xs, ys = alpha_points(bird)
    low = ys.max()
    foot_x = int(np.median(xs[ys > low - max(4, bird.height * 0.04)])) + bx
    foot_y = int(low) + by - 6
    tag = _tag(info)
    ang = rnd.uniform(-9, -4)
    tag_r = tag.rotate(ang, resample=Image.BICUBIC, expand=True)
    tx = int(W - m - 60 - tag_r.width)
    ty = int(H * 0.40)
    # string: from the foot to the tag's eyelet (left end, rotated)
    ex, ey = 46, tag.height / 2
    cxr, cyr = tag.width / 2, tag.height / 2
    a = math.radians(-ang)
    rx = (ex - cxr) * math.cos(a) - (ey - cyr) * math.sin(a) + tag_r.width / 2 + tx
    ry = (ex - cxr) * math.sin(a) + (ey - cyr) * math.cos(a) + tag_r.height / 2 + ty
    pts = _bezier((foot_x, foot_y), (foot_x + 120, foot_y + 160), (rx - 220, ry + 120), (rx, ry))
    d.line(pts, fill=col(BLACK), width=3, joint="curve")
    drop(cv, tag_r, (tx, ty), shadow=(8, 10), shade=LIGHT)
    # knot over the tag eyelet
    d.ellipse([rx - 7, ry - 7, rx + 7, ry + 7], fill=col(BLACK))
    return cv


def _bezier(p0, p1, p2, p3, n=60):
    out = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0]
        y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
        out.append((x, y))
    return out


def _tag(info: dict) -> Image.Image:
    w = 600
    rows = [r for r in info["tag_rows"] if r[1]]
    h = 150 + 46 * len(rows) + 40
    tag = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(tag)
    # tag shape: rectangle with clipped corners on the eyelet side
    c = 46
    d.polygon([(c, 0), (w, 0), (w, h), (c, h), (0, h - c), (0, c)], fill=col(WHITE), outline=col(BLACK))
    d.line([(c, 0), (w - 1, 0), (w - 1, h - 1), (c, h - 1), (0, h - c), (0, c), (c, 0)], fill=col(BLACK), width=3)
    d.ellipse([46 - 14, h / 2 - 14, 46 + 14, h / 2 + 14], outline=col(BLACK), width=3, fill=col(PAPER))
    x = 100
    d.text((x, 26), info["name"], font=fit_font(d, info["name"], "serif", w - x - 30, 50), fill=col(BLACK))
    d.text((x, 84), info["scientific"], font=font("serif-italic", 34), fill=col(DARK))
    d.line([(x, 136), (w - 30, 136)], fill=col(LIGHT), width=2)
    y = 150
    fk, fv = font("mono", 24), font("mono-medium", 26)
    for k, v in rows:
        d.text((x, y + 2), k, font=fk, fill=col(MID))
        vv = v
        while text_w(d, vv, fv) > w - x - 160 - 24 and len(vv) > 4:
            vv = vv[:-2].rstrip(", ") + "."
        d.text((x + 150, y), vv, font=fv, fill=col(BLACK))
        y += 46
    return tag


# ---------------------------------------------------------------- 6 guess

def guess(st: Sticker, info: dict, reveal: bool) -> Image.Image:
    W, H = CANVAS
    cv = new_canvas(WHITE)
    d = ImageDraw.Draw(cv)
    bird = fit(st, W * 0.56, H * 0.84)
    bx, by = 50, (H - bird.height) // 2
    if reveal:
        cv.alpha_composite(sharpen(bird), (bx, by))
    else:
        cv.alpha_composite(silhouette(bird, BLACK), (bx, by))
    x = int(W * 0.62)
    maxw = W - x - 50
    if reveal:
        d.text((x, 70), "It was", font=font("serif-italic", 64), fill=col(DARK))
        for size in range(120, 40, -4):
            fn = font("serif", size)
            lines = wrap(d, info["name"], fn, maxw)
            if len(lines) <= 2 and all(text_w(d, l_, fn) <= maxw for l_ in lines):
                break
        y = 150
        for s in lines[:3]:
            d.text((x, y), s, font=fn, fill=col(BLACK))
            y += int(fn.size * 1.0)
        d.text((x, y + 28), info["scientific"], font=font("serif-italic", 48), fill=col(DARK))
        y += 18
        y += 90
    else:
        d.text((x, 60), "Who", font=font("serif-italic", 150), fill=col(BLACK))
        d.text((x, 200), "am I?", font=font("serif-italic", 150), fill=col(BLACK))
        y = 400
    fm = font("mono", 30)
    for i, s in enumerate(info["clues"], 1):
        for j, line in enumerate(wrap(d, s, fm, maxw - 56)):
            if j == 0:
                d.text((x, y), f"{i}", font=font("mono-medium", 30), fill=col(MID))
            d.text((x + 50, y), line, font=fm, fill=col(BLACK))
            y += 42
        y += 14
        if y > H - 160:
            break
    foot = "Answer after 6 pm." if not reveal else "New bird tomorrow."
    d.text((x, H - 100), foot, font=font("serif-italic", 44), fill=col(MID))
    return cv
