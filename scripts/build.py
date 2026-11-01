#!/usr/bin/env python3
"""Bird of the Day: pick today's species and render every variant for TRMNL X.

  python scripts/build.py --source SRC --out site [--date YYYY-MM-DD] [--region PAL] [--id Genus_species]
  python scripts/build.py --source SRC --print-stickers   # sticker paths the build will need

SRC is a (sparse) checkout of github.com/alchaincyf/huashu-bird-sticker.
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import hashlib
import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SEED = "trmnl-bird-of-the-day"
TZ = ZoneInfo("Europe/Berlin")
EPOCH = dt.date(2026, 1, 1)

VARIANTS = ["lifesize", "flock", "album", "poster", "specimen", "guess"]

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
DIET = {
    "Invertivore": "insects and other invertebrates", "Omnivore": "almost anything",
    "Frugivore": "fruit", "Granivore": "seeds", "Nectarivore": "nectar",
    "Aquatic predator": "fish and other aquatic animals", "Vertivore": "small vertebrates",
    "Herbivore terrestrial": "plants", "Herbivore aquatic": "water plants", "Scavenger": "carrion",
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


def quality(species):
    return [s for s in species if (s.get("sticker") or {}).get("meetsQualityBar") is True
            and (s.get("sticker") or {}).get("file")]


def eligible(species, region: str):
    out = quality(species)
    if region and region.upper() != "ALL":
        want = {r.strip() for r in region.split(",")}
        out = [s for s in out if want & set(regions((s.get("range") or {}).get("breedingRegion")))]
    return out


def hkey(*parts) -> str:
    return hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()


def ordered(pool):
    return sorted(pool, key=lambda s: hkey(SEED, s["id"]))


def pick(order, day: dt.date):
    """Fixed hash-shuffle of the pool, one step per day: no repeats within a cycle."""
    idx = (day - EPOCH).days % len(order)
    return order[idx], idx


# ---------------------------------------------------------------- numbers

def num(x: float, decimals: int) -> str:
    return f"{x:,.{decimals}f}"


def fmt_mass(g) -> str:
    if g is None:
        return ""
    g = float(g)
    if g >= 1000:
        return f"{num(g / 1000, 1 if g < 10000 else 0)} kg"
    return f"{num(g, 1 if g < 10 else 0)} g"


def fmt_cm(cm) -> str:
    if cm is None:
        return ""
    return f"{num(cm, 1 if cm < 10 else 0)} cm"


def wing_mm(s):
    w = (s.get("traits") or {}).get("wingMm")
    return float(w) if w is not None and float(w) >= 5 else None  # kiwis: 0.1 mm placeholder


def length_ratios(species) -> dict:
    """Median body length / wing length per order, from species that have both."""
    r = defaultdict(list)
    for s in species:
        z, w = (s.get("size") or {}).get("bodyLengthCm"), wing_mm(s)
        if z and w:
            r[s["taxonomy"]["order"]].append((sum(z) / 2) / (w / 10))
    allr = [x for v in r.values() for x in v]
    out = {o: statistics.median(v) for o, v in r.items() if len(v) >= 8}
    out["_all"] = statistics.median(allr) if allr else 2.0
    return out


def body_length(s, ratios) -> tuple[float | None, str]:
    """Body length in cm and how we know it."""
    w = wing_mm(s)
    ratio = ratios.get(s["taxonomy"]["order"], ratios["_all"])
    z = (s.get("size") or {}).get("bodyLengthCm")
    if z:
        L = sum(z) / 2
        if not w or 0.6 * ratio <= L / (w / 10) <= 1.6 * ratio:
            return L, "measured"
    if w:
        return w / 10 * ratio, "estimated from wing length"
    return None, ""


# ---------------------------------------------------------------- record

def info_for(s, ratios) -> dict:
    names, tax = s.get("names") or {}, s.get("taxonomy") or {}
    traits, cons = s.get("traits") or {}, s.get("conservation") or {}
    rng = s.get("range") or {}
    name = clean(names.get("en")) or clean(s.get("scientificName"))
    codes = regions(rng.get("breedingRegion"))
    region = ", ".join(REGIONS.get(c, c) for c in codes)
    habitat = traits.get("habitat") or ""
    habitat_txt = HABITAT.get(habitat, habitat.lower())
    migration = (traits.get("migration") or "").lower()
    w = wing_mm(s)
    L, how = body_length(s, ratios)
    iucn = (cons.get("iucn") or "").upper()
    mass = traits.get("massG")
    facts = [x for x in [
        fmt_mass(mass),
        f"wing {fmt_cm(w / 10)}" if w else "",
        habitat_txt,
        migration,
        region,
    ] if x]
    clues = [x for x in [
        f"I weigh about {fmt_mass(mass)}." if mass else "",
        f"My wings are {fmt_cm(w / 10)} long." if w else "",
        f"I breed in: {region}." if region else "",
        f"You will find me in {habitat_txt}." if habitat_txt else "",
        {"sedentary": "I stay put all year.", "migratory": "I migrate.",
         "partially migratory": "Some of us migrate, some stay."}.get(migration, ""),
        f"My family: {clean(tax.get('familyEnglish'))}." if tax.get("familyEnglish") else "",
        f"My name starts with {name[0]} and has {len(name.replace(' ', '').replace('-', ''))} letters.",
    ] if x]
    tag_rows = [
        ("mass", fmt_mass(mass)),
        ("wing", fmt_cm(w / 10) if w else ""),
        ("length", f"{fmt_cm(L)}" if L else ""),
        ("habitat", habitat_txt),
        ("moves", migration),
        ("breeds", region),
        ("status", f"{IUCN[iucn]} ({iucn})" if iucn in IUCN else ""),
    ]
    return {
        "id": s["id"],
        "name": name,
        "scientific": clean(s.get("scientificName")),
        "authority": clean(s.get("authority")),
        "family_latin": tax.get("family") or "",
        "family_en": clean(tax.get("familyEnglish")),
        "order": tax.get("order") or "",
        "seq": tax.get("seq") or 0,
        "mass": fmt_mass(mass),
        "wing_mm": w,
        "wing": fmt_cm(w / 10) if w else "",
        "length_cm": L,
        "length_label": f"About {fmt_cm(L)}" + (f" ({how})" if how != "measured" else ""),
        "length_how": how,
        "habitat": habitat_txt,
        "migration": migration,
        "diet": DIET.get(traits.get("trophicNiche") or "", ""),
        "region": region,
        "region_codes": codes,
        "iucn_code": iucn if iucn in IUCN else "",
        "iucn": IUCN.get(iucn, ""),
        "facts": facts,
        "clues": clues,
        "tag_rows": tag_rows,
        "sticker": s["sticker"]["file"],
    }


def relatives(s, species, day, limit=11):
    """Same family first, then same order; similar size so the scale stays readable."""
    q = quality(species)
    w0 = wing_mm(s) or 100.0
    def ok(x):
        w = wing_mm(x)
        return x["id"] != s["id"] and w and 0.33 <= w / w0 <= 3.0
    fam = [x for x in q if x["taxonomy"]["family"] == s["taxonomy"]["family"] and ok(x)]
    out = sorted(fam, key=lambda x: hkey(SEED, day, x["id"]))[:limit]
    if len(out) < 7:
        rest = [x for x in q if x["taxonomy"]["order"] == s["taxonomy"]["order"] and ok(x) and x not in out]
        out += sorted(rest, key=lambda x: hkey(SEED, day, x["id"]))[: limit - len(out)]
    return out


def month_days(order, day):
    first = day.replace(day=1)
    n = calendar.monthrange(day.year, day.month)[1]
    return [pick(order, first + dt.timedelta(i))[0] for i in range(n)]


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "site")
    ap.add_argument("--date")
    ap.add_argument("--region", default=os.environ.get("REGION", "ALL"))
    ap.add_argument("--base-url", default=os.environ.get("PAGES_URL", ""))
    ap.add_argument("--id", help="force today's species (for layout tests)")
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--print-stickers", action="store_true")
    a = ap.parse_args(argv)

    day = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(TZ).date()
    data = json.loads((a.source / "data" / "species.json").read_text(encoding="utf-8"))
    species = data["species"]
    by_id = {s["id"]: s for s in species}
    pool = eligible(species, a.region)
    if not pool:
        print(f"no species for region {a.region!r}", file=sys.stderr)
        return 2
    order = ordered(pool)
    s, idx = (by_id[a.id], -1) if a.id else pick(order, day)
    rel = relatives(s, species, day)
    month = month_days(order, day)
    if a.id:
        month[day.day - 1] = s
    variants = [v for v in a.variants.split(",") if v]

    if a.print_stickers:
        need = {s["sticker"]["file"]}
        if "flock" in variants:
            need |= {x["sticker"]["file"] for x in rel}
        if "album" in variants:
            need |= {x["sticker"]["file"] for x in month}
        print("\n".join(sorted(need)))
        return 0

    sys.path.insert(0, str(Path(__file__).parent))
    import art

    ratios = length_ratios(species)
    info = info_for(s, ratios)
    src = lambda x: a.source / x["sticker"]["file"]
    st = art.load_sticker(src(s))
    out = a.out
    base = a.base_url.rstrip("/")
    v = day.isoformat()
    url = lambda name: f"{base + '/' if base else ''}{name}.png?v={v}"
    images = {}

    def save(name, canvas):
        art.finish(canvas, out / f"{name}.png")
        images[name] = url(name)

    if "lifesize" in variants and info["length_cm"]:
        save("lifesize", art.life_size(st, info))
    if "flock" in variants:
        others = [(art.load_sticker(src(x)), info_for(x, ratios)) for x in rel]
        me = dict(info)
        if not me["wing_mm"]:
            me["wing_mm"] = statistics.median([o[1]["wing_mm"] for o in others]) if others else 100.0
        fam = info["family_en"] or info["family_latin"]
        caption = {
            "title": info["name"],
            "subtitle": (f"and {len(others)} relative{'s' if len(others) != 1 else ''}, "
                         f"drawn to scale by wing length") if others else "alone today, no close relatives",
            "footer": f"{fam}  /  {info['scientific']}",
        }
        save("flock", art.flock((st, me), others, f"{SEED}:{v}", caption))
    if "album" in variants:
        first_wd = day.replace(day=1).weekday()
        cache = {}
        days = []
        for i, x in enumerate(month):
            if x["id"] not in cache:
                cache[x["id"]] = art.load_sticker(src(x))
            days.append({"st": cache[x["id"]], "day": i + 1})
        tagline = f"Day {day.day}: {info['name']}"
        save("album", art.album(days, day.day - 1, day.strftime("%B"), str(day.year), first_wd, tagline))
    if "poster" in variants:
        save("poster", art.poster(st, info))
    if "specimen" in variants:
        save("specimen", art.specimen(st, info, f"{SEED}:{v}"))
    if "guess" in variants:
        save("guess", art.guess(st, info, reveal=False))
        save("reveal", art.guess(st, info, reveal=True))

    vod = VARIANTS[(day - EPOCH).days % len(VARIANTS)]
    if vod not in images:
        vod = "poster" if "poster" in images else next(iter(images))
    import shutil
    shutil.copyfile(out / f"{vod}.png", out / "today.png")
    images["today"] = url("today")

    rec = {k: v for k, v in info.items() if k not in ("tag_rows", "wing_mm", "sticker")}
    rec.update({
        "date": day.isoformat(),
        "date_label": f"{day.strftime('%A')}, {day.day} {day.strftime('%B %Y')}",
        "images": images,
        "variant_of_the_day": vod,
        "relatives": [x["id"] for x in rel],
        "pool": {"region": a.region or "ALL", "size": len(pool), "index": idx},
        "source": {"taxonomy": data.get("taxonomy"), "version": data.get("version"),
                   "ref": os.environ.get("SOURCE_REF", "")},
        "credit": "Stickers: huashu-bird-sticker (PolyForm Shield 1.0.0). Data: IOC 15.2, AVONET, Wikidata.",
    })
    out.mkdir(parents=True, exist_ok=True)
    (out / "today.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{day} {a.region or 'ALL'} #{idx}/{len(pool)}: {info['name']} ({info['scientific']}) -> {', '.join(images)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
