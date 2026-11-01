#!/usr/bin/env python3
"""Bird of the Day: pick today's species, render the sticker for TRMNL X, write today.json.

Usage:
  python scripts/build.py --source SRC_DIR --out OUT_DIR [--date YYYY-MM-DD] [--region PAL]

SRC_DIR is a (sparse) checkout of github.com/alchaincyf/huashu-bird-sticker.
Only data/species.json is read first; the one sticker for the chosen species is
fetched afterwards by the workflow (see --print-sticker).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SEED = "trmnl-bird-of-the-day"
TZ = ZoneInfo("Europe/Berlin")

# Output image, in physical pixels of the TRMNL X panel (1872x1404).
# The sticker column takes about 60% of the width; the height is the panel
# minus the title bar and the layout padding.
IMG_W = int(os.environ.get("IMG_W", 1064))
IMG_H = int(os.environ.get("IMG_H", 1278))
LEVELS = 16

REGIONS_DE = {
    "PAL": "Paläarktis",
    "NA": "Nordamerika",
    "MA": "Mittelamerika",
    "SA": "Südamerika",
    "AF": "Afrika",
    "OR": "Süd- und Südostasien",
    "AU": "Australasien",
    "AN": "Antarktis",
    "PO": "Pazifik",
    "IO": "Indischer Ozean",
    "AO": "Atlantik",
    "SO": "Südpolarmeer",
    "TrO": "Tropische Ozeane",
    "NO": "Nördliche Ozeane",
    "Worldwide": "Weltweit",
    "Worldwide but disjunctly": "Weltweit, verstreut",
}
REGIONS_EN = {
    "PAL": "Palearctic",
    "NA": "North America",
    "MA": "Middle America",
    "SA": "South America",
    "AF": "Africa",
    "OR": "Oriental Region",
    "AU": "Australasia",
    "AN": "Antarctica",
    "PO": "Pacific Ocean",
    "IO": "Indian Ocean",
    "AO": "Atlantic Ocean",
    "SO": "Southern Ocean",
    "TrO": "Tropical Oceans",
    "NO": "Northern Oceans",
    "Worldwide": "Worldwide",
    "Worldwide but disjunctly": "Worldwide, disjunct",
}
IUCN_DE = {
    "LC": "Nicht gefährdet",
    "NT": "Potenziell gefährdet",
    "VU": "Gefährdet",
    "EN": "Stark gefährdet",
    "CR": "Vom Aussterben bedroht",
    "EW": "In der Natur ausgestorben",
    "EX": "Ausgestorben",
    "DD": "Datenlage ungenügend",
}
HABITAT_DE = {
    "Forest": "Wald",
    "Woodland": "Lichter Wald",
    "Shrubland": "Buschland",
    "Grassland": "Grasland",
    "Wetland": "Feuchtgebiete",
    "Riverine": "Flussufer",
    "Coastal": "Küste",
    "Marine": "Meer",
    "Rock": "Fels",
    "Desert": "Wüste",
    "Human Modified": "Kulturland",
}
MIGRATION_DE = {
    "sedentary": "Standvogel",
    "partially migratory": "Teilzieher",
    "migratory": "Zugvogel",
}
TROPHIC_DE = {
    "Invertivore": "Wirbellose",
    "Omnivore": "Allesfresser",
    "Frugivore": "Früchte",
    "Granivore": "Samen",
    "Nectarivore": "Nektar",
    "Aquatic predator": "Wassertiere",
    "Vertivore": "Wirbeltiere",
    "Herbivore terrestrial": "Pflanzen",
    "Herbivore aquatic": "Wasserpflanzen",
    "Scavenger": "Aas",
}
WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]

# UI text must not contain these (house rule).
FORBIDDEN = {"\u2014": "-", "\u2013": "-", "\u00b7": ",", "\u2027": ","}


def clean(s: str | None) -> str:
    if not s:
        return ""
    s = " ".join(str(s).split()).strip(" /")
    for bad, good in FORBIDDEN.items():
        s = s.replace(bad, good)
    return s


def regions(code: str | None) -> list[str]:
    if not code:
        return []
    if code.strip() in REGIONS_DE:
        return [code.strip()]
    return [c.strip() for c in code.split(",") if c.strip()]


def eligible(species: list[dict], region: str) -> list[dict]:
    out = [s for s in species if (s.get("sticker") or {}).get("meetsQualityBar") is True
           and (s.get("sticker") or {}).get("file")]
    if region and region.upper() != "ALL":
        want = {r.strip() for r in region.split(",")}
        out = [s for s in out if want & set(regions((s.get("range") or {}).get("breedingRegion")))]
    return out


def pick(pool: list[dict], day: dt.date) -> tuple[dict, int]:
    """Deterministic: a fixed hash-shuffle of the pool, stepped one per day.

    Every species appears once before any repeats. The order depends only on the
    species ids, so it is stable across Python versions and machines.
    """
    order = sorted(pool, key=lambda s: hashlib.sha256(f"{SEED}:{s['id']}".encode()).hexdigest())
    idx = (day - dt.date(2026, 1, 1)).days % len(order)
    return order[idx], idx


def fmt_num(x: float, decimals: int) -> str:
    s = f"{x:,.{decimals}f}"  # 1,234.5
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_mass(g) -> str:
    if g is None:
        return ""
    g = float(g)
    if g >= 1000:
        return f"{fmt_num(g / 1000, 1 if g < 10000 else 0)} kg"
    if g < 10:
        return f"{fmt_num(g, 1)} g"
    return f"{fmt_num(g, 0)} g"


def fmt_mm(mm) -> str:
    """AVONET lengths are in mm; show cm (one decimal below 10 cm).

    Kiwis carry a 0.1 mm placeholder for their vestigial wings: treat values
    under 5 mm as missing so the field is hidden.
    """
    if mm is None or float(mm) < 5:
        return ""
    cm = float(mm) / 10
    return f"{fmt_num(cm, 1 if cm < 10 else 0)} cm"


def fmt_date(day: dt.date) -> str:
    return f"{WEEKDAYS_DE[day.weekday()]}, {day.day}. {MONTHS_DE[day.month - 1]} {day.year}"


def name_size(name: str) -> str:
    """Size tier for the headline so long names step down instead of overflowing.

    The tier follows the longest single word (German compounds cannot wrap) and
    the total length. Tuned for the right column of the TRMNL X layout.
    """
    longest_word = max((len(p) for p in name.replace("-", " ").split()), default=0)
    if longest_word <= 16 and len(name) <= 32:
        return "xl"
    if longest_word <= 18:
        return "l"
    if longest_word <= 24:
        return "m"
    return "s"


def record(s: dict, day: dt.date, idx: int, pool_size: int, region: str,
           families_de: dict, image_url: str) -> dict:
    names = s.get("names") or {}
    tax = s.get("taxonomy") or {}
    rng = s.get("range") or {}
    traits = s.get("traits") or {}
    cons = s.get("conservation") or {}

    name_de = clean(names.get("de"))
    name_en = clean(names.get("en"))
    primary = name_de or name_en or clean(s.get("scientificName"))
    fam_lat = tax.get("family") or ""
    fam_de = families_de.get(fam_lat, "")
    family = clean(fam_de or tax.get("familyEnglish") or fam_lat)

    codes = regions(rng.get("breedingRegion"))
    iucn = (cons.get("iucn") or "").upper()

    rec = {
        "date": day.isoformat(),
        "date_de": fmt_date(day),
        "id": s["id"],
        "name": primary,
        "name_size": name_size(primary),
        "name_de": name_de,
        "name_en": name_en if name_en != primary else "",
        "name_en_raw": name_en,
        "scientific_name": clean(s.get("scientificName")),
        "family": family,
        "family_latin": fam_lat,
        "family_en": clean(tax.get("familyEnglish")),
        "family_de": fam_de,
        "order": tax.get("order") or "",
        "weight": fmt_mass(traits.get("massG")),
        "wing": fmt_mm(traits.get("wingMm")),
        "tail": fmt_mm(traits.get("tailMm")),
        "habitat": HABITAT_DE.get(traits.get("habitat") or "", clean(traits.get("habitat"))),
        "migration": MIGRATION_DE.get(traits.get("migration") or "", clean(traits.get("migration"))),
        "diet": TROPHIC_DE.get(traits.get("trophicNiche") or "", clean(traits.get("trophicNiche"))),
        "traits_inferred": bool(traits.get("inferred")),
        "iucn_code": iucn if iucn in IUCN_DE else "",
        "iucn": IUCN_DE.get(iucn, ""),
        "iucn_alert": iucn in {"VU", "EN", "CR", "EW", "EX"},
        "region_codes": codes,
        "region": ", ".join(REGIONS_DE.get(c, c) for c in codes),
        "region_en": ", ".join(REGIONS_EN.get(c, c) for c in codes),
        "has_facts": False,  # set below
        "image_url": image_url,
        "sticker_file": s["sticker"]["file"],
        "pool": {"region": region or "ALL", "size": pool_size, "index": idx},
        "credit": "Sticker: huashu-bird-sticker (PolyForm Shield 1.0.0). Daten: IOC 15.2, AVONET, Wikidata",
    }
    rec["has_facts"] = any(rec[k] for k in ("weight", "wing", "habitat", "migration"))
    return rec


def render_png(src: Path, dst: Path, w: int = IMG_W, h: int = IMG_H) -> None:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    im = Image.open(src).convert("RGBA")
    bbox = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)

    # Fit into the canvas with a small margin, keep the aspect ratio.
    margin = 0.03
    scale = min(w * (1 - 2 * margin) / im.width, h * (1 - 2 * margin) / im.height)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)

    # Flatten onto white.
    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    canvas.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2))
    mask = Image.new("L", (w, h), 0)
    mask.paste(im.getchannel("A"), ((w - im.width) // 2, (h - im.height) // 2))
    gray = canvas.convert("RGB").convert("L")

    # Contrast: stretch the bird's own tonal range (ignore the white page), then
    # a gentle extra contrast and sharpening for e-paper.
    body = mask.point(lambda a: 255 if a > 200 else 0)
    gray = ImageOps.autocontrast(gray, cutoff=(1, 1), mask=body)
    gray = ImageEnhance.Contrast(gray).enhance(1.25)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))

    # Quantize to 16 evenly spaced grays with Floyd-Steinberg.
    pal = Image.new("P", (1, 1))
    levels = [round(i * 255 / (LEVELS - 1)) for i in range(LEVELS)]
    pal.putpalette([v for lv in levels for v in (lv, lv, lv)] + [0] * 3 * (256 - LEVELS))
    q = gray.convert("RGB").quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG)
    q = q.convert("L")
    dst.parent.mkdir(parents=True, exist_ok=True)
    q.save(dst, optimize=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "site")
    ap.add_argument("--date", help="YYYY-MM-DD, default: today in Europe/Berlin")
    ap.add_argument("--region", default=os.environ.get("REGION", "ALL"))
    ap.add_argument("--base-url", default=os.environ.get("PAGES_URL", ""))
    ap.add_argument("--id", help="force a species id (for testing layouts)")
    ap.add_argument("--print-sticker", action="store_true",
                    help="only print the sticker path for the pick and exit")
    a = ap.parse_args(argv)

    day = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(TZ).date()
    data = json.loads((a.source / "data" / "species.json").read_text(encoding="utf-8"))
    species = data["species"]
    pool = eligible(species, a.region)
    if not pool:
        print(f"no species for region {a.region!r}", file=sys.stderr)
        return 2
    if a.id:
        s = next(x for x in species if x["id"] == a.id)
        idx = -1
    else:
        s, idx = pick(pool, day)

    if a.print_sticker:
        print(s["sticker"]["file"])
        return 0

    families_de = json.loads((ROOT / "data" / "families_de.json").read_text(encoding="utf-8"))["families"]
    base = a.base_url.rstrip("/")
    image_url = f"{base}/today.png?v={day.isoformat()}" if base else f"today.png?v={day.isoformat()}"

    rec = record(s, day, idx, len(pool), a.region, families_de, image_url)
    rec["source"] = {"taxonomy": data.get("taxonomy"), "version": data.get("version"),
                     "ref": os.environ.get("SOURCE_REF", "")}

    a.out.mkdir(parents=True, exist_ok=True)
    render_png(a.source / s["sticker"]["file"], a.out / "today.png")
    (a.out / "today.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{day} {a.region or 'ALL'} #{idx}/{len(pool)}: {rec['name']} ({rec['scientific_name']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
