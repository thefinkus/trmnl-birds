#!/usr/bin/env python3
"""Bird of the Day: pick today's species and render its pictures for TRMNL X.

  python scripts/build.py --source SRC --out site [--date YYYY-MM-DD] [--region PAL] [--id Genus_species] [--variant hero]
  python scripts/build.py --source SRC --print-stickers   # the sticker path the build needs

SRC is a (sparse) checkout of github.com/alchaincyf/huashu-bird-sticker.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SEED = "trmnl-bird-of-the-day"
TZ = ZoneInfo("Europe/Berlin")
EPOCH = dt.date(2026, 1, 1)

# One picture a day, stepping through these framings; VARIANT_EPOCH shows the first.
VARIANTS = ["hero", "closeup", "quiet"]
VARIANT_EPOCH = dt.date(2026, 11, 2)

REGIONS = {
    "PAL": "Palearctic", "NA": "North America", "MA": "Middle America", "SA": "South America",
    "AF": "Africa", "OR": "Oriental Region", "AU": "Australasia", "AN": "Antarctica",
    "PO": "Pacific Ocean", "IO": "Indian Ocean", "AO": "Atlantic Ocean", "SO": "Southern Ocean",
    "TrO": "tropical oceans", "NO": "northern oceans", "Worldwide": "worldwide",
    "Worldwide but disjunctly": "worldwide, patchily",
}
IUCN = {
    "LC": "Least Concern", "NT": "Near Threatened", "VU": "Vulnerable", "EN": "Endangered",
    "CR": "Critically Endangered", "EW": "Extinct in the Wild", "EX": "Extinct", "DD": "Data Deficient",
}
HABITAT = {
    "Human Modified": "farmland and towns", "Riverine": "riversides", "Rock": "rocky places",
    "Marine": "the open sea", "Coastal": "coasts", "Wetland": "wetlands",
}
FORBIDDEN = {"—": "-", "–": "-", "·": ",", "‧": ","}


def clean(s) -> str:
    if not s:
        return ""
    s = " ".join(str(s).split()).strip(" /")
    for bad, good in FORBIDDEN.items():
        s = s.replace(bad, good)
    return s


def regions(code) -> list[str]:
    if not code:
        return []
    if code.strip() in REGIONS:
        return [code.strip()]
    return [c.strip() for c in code.split(",") if c.strip()]


def eligible(species, region: str):
    out = [s for s in species if (s.get("sticker") or {}).get("meetsQualityBar") is True
           and (s.get("sticker") or {}).get("file")]
    if region and region.upper() != "ALL":
        want = {r.strip() for r in region.split(",")}
        out = [s for s in out if want & set(regions((s.get("range") or {}).get("breedingRegion")))]
    return out


def pick(pool, day: dt.date):
    """Fixed hash-shuffle of the pool, one step per day: no repeats within a cycle."""
    order = sorted(pool, key=lambda s: hashlib.sha256(f"{SEED}:{s['id']}".encode()).hexdigest())
    idx = (day - EPOCH).days % len(order)
    return order[idx], idx


def fmt_mass(g) -> str:
    if g is None:
        return ""
    g = float(g)
    if g >= 1000:
        return f"{g / 1000:,.{1 if g < 10000 else 0}f} kg"
    return f"{g:,.{1 if g < 10 else 0}f} g"


def fmt_cm(cm) -> str:
    return f"{cm:,.{1 if cm < 10 else 0}f} cm"


def info_for(s) -> dict:
    names, tax = s.get("names") or {}, s.get("taxonomy") or {}
    traits, cons = s.get("traits") or {}, s.get("conservation") or {}
    rng = s.get("range") or {}
    name = clean(names.get("en")) or clean(s.get("scientificName"))
    codes = regions(rng.get("breedingRegion"))
    region = ", ".join(REGIONS.get(c, c) for c in codes)
    habitat = traits.get("habitat") or ""
    habitat_txt = HABITAT.get(habitat, habitat.lower())
    migration = (traits.get("migration") or "").lower()
    w = traits.get("wingMm")
    w = float(w) if w is not None and float(w) >= 5 else None  # kiwis carry a 0.1 mm placeholder
    iucn = (cons.get("iucn") or "").upper()
    mass = traits.get("massG")
    facts = [x for x in [fmt_mass(mass), f"wing {fmt_cm(w / 10)}" if w else "", habitat_txt, migration, region] if x]
    return {
        "id": s["id"],
        "name": name,
        "scientific": clean(s.get("scientificName")),
        "family_latin": tax.get("family") or "",
        "family_en": clean(tax.get("familyEnglish")),
        "order": tax.get("order") or "",
        "mass": fmt_mass(mass),
        "wing": fmt_cm(w / 10) if w else "",
        "habitat": habitat_txt,
        "migration": migration,
        "region": region,
        "region_codes": codes,
        "lifestyle": traits.get("primaryLifestyle") or "",
        "iucn_code": iucn if iucn in IUCN else "",
        "iucn": IUCN.get(iucn, ""),
        "facts": facts,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "site")
    ap.add_argument("--date")
    ap.add_argument("--region", default=os.environ.get("REGION", "ALL"))
    ap.add_argument("--base-url", default=os.environ.get("PAGES_URL", ""))
    ap.add_argument("--id", help="force a species (for tests)")
    ap.add_argument("--variant", choices=VARIANTS, help="force today's picture (default: daily rotation)")
    ap.add_argument("--print-stickers", action="store_true")
    a = ap.parse_args(argv)

    day = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(TZ).date()
    data = json.loads((a.source / "data" / "species.json").read_text(encoding="utf-8"))
    species = data["species"]
    pool = eligible(species, a.region)
    if not pool:
        print(f"no species for region {a.region!r}", file=sys.stderr)
        return 2
    s, idx = (next(x for x in species if x["id"] == a.id), -1) if a.id else pick(pool, day)

    if a.print_stickers:
        print(s["sticker"]["file"])
        return 0

    sys.path.insert(0, str(Path(__file__).parent))
    import art

    info = info_for(s)
    st = art.load_sticker(a.source / s["sticker"]["file"])
    a.out.mkdir(parents=True, exist_ok=True)
    base = a.base_url.rstrip("/")

    def url(name: str) -> str:
        return f"{base + '/' if base else ''}{name}.png?v={day.isoformat()}"

    renders = {"hero": art.hero, "closeup": art.closeup, "quiet": art.quiet}
    vod = a.variant or VARIANTS[(day - VARIANT_EPOCH).days % len(VARIANTS)]
    images = {}
    for name in VARIANTS:
        art.finish(renders[name](st, info), a.out / f"{name}.png")
        images[name] = url(name)
    shutil.copyfile(a.out / f"{vod}.png", a.out / "today.png")
    images["today"] = url("today")
    image_url = url("today")

    rec = dict(info)
    rec.update({
        "date": day.isoformat(),
        "date_label": f"{day.strftime('%A')}, {day.day} {day.strftime('%B %Y')}",
        "image_url": image_url,
        "images": images,
        "variant_of_the_day": vod,
        "pool": {"region": a.region or "ALL", "size": len(pool), "index": idx},
        "source": {"taxonomy": data.get("taxonomy"), "version": data.get("version"),
                   "ref": os.environ.get("SOURCE_REF", "")},
        "credit": "Stickers: huashu-bird-sticker (PolyForm Shield 1.0.0). Data: IOC 15.2, AVONET, Wikidata.",
    })
    (a.out / "today.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{day} {a.region or 'ALL'} #{idx}/{len(pool)}: {info['name']} ({info['scientific']}) -> {vod}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
