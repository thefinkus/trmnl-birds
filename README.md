# Bird of the Day for TRMNL X

A private TRMNL plugin that shows one bird per day as a field card: a sticker
illustration on the left, German name, Latin name, English name, family, weight,
wing length, habitat, migration, Red List status and breeding region on the right.

Built for the **TRMNL X** (1872x1404, 4-bit, 16 grays, landscape). The markup uses
TRMNL Framework classes only, with `lg:` and `4bit:` prefixes, so it also degrades
on the smaller devices.

```
GitHub Action (daily, ~03:00 Europe/Berlin)
  ├─ sparse + blobless fetch of huashu-bird-sticker @ pinned commit
  │    data/species.json, then only today's sticker
  ├─ scripts/build.py
  │    pick species from the date  ->  today.json
  │    sticker -> white, grayscale, contrast, 16 grays, Floyd-Steinberg  ->  today.png
  └─ deploy to GitHub Pages
TRMNL private plugin (Polling) -> today.json -> trmnl/full.liquid
```

## How the bird is picked

- Pool: species with `sticker.meetsQualityBar == true` (7,668 of 11,064).
- `REGION=PAL` limits the pool to species whose `range.breedingRegion` includes
  `PAL` (789, including multi-region species such as `PAL, AF`).
- Order: the pool is sorted by `sha256("trmnl-bird-of-the-day:" + id)` and the
  day number since 2026-01-01 steps through it. Same date, same bird, on any
  machine. Every species comes up once before any repeats.
- The source repo is pinned to a commit (`SOURCE_REF` in the workflow) so the
  order cannot shift under you. Bumping it may reshuffle the sequence.

## Files

| Path | What |
|---|---|
| `.github/workflows/bird-of-the-day.yml` | Daily build and Pages deploy, plus manual runs |
| `scripts/build.py` | Pick, image processing, `today.json` |
| `data/families_de.json` | German family names (Wikidata, CC0, plus hand-checked additions) |
| `trmnl/full.liquid` | Markup for the TRMNL full view, paste this into TRMNL |
| `trmnl/samples.txt` | Fixed test birds, published under `samples/` |
| `tools/` | Local preview: render the Liquid and screenshot it at TRMNL X size |

## Published files

After a run, GitHub Pages serves:

- `https://<user>.github.io/<repo>/today.json`
- `https://<user>.github.io/<repo>/today.png` (1064x1278, 16 grays, pre-dithered)
- `https://<user>.github.io/<repo>/samples/{normal,longname,notraits}/today.json`

`today.json` fields used by the markup: `name`, `name_size`, `scientific_name`,
`name_en`, `family`, `weight`, `wing`, `habitat`, `migration`, `has_facts`,
`region`, `iucn`, `iucn_code`, `iucn_alert`, `date_de`, `image_url`. Empty fields
are empty strings and the markup hides them. Extra fields (`region_en`,
`family_latin`, `diet`, `tail`, `order`, `pool`, `source`, ...) are there for
later use.

## Setup

### 1. GitHub

1. Settings, Pages, Source: **GitHub Actions**.
2. Optional: Settings, Secrets and variables, Actions, Variables: add `REGION`
   with `PAL` for Palearctic birds only. Default is `ALL`.
3. Actions, **Bird of the Day**, **Run workflow**. Check that
   `https://<user>.github.io/<repo>/today.json` and `today.png` open.

After that the schedule runs it every night. The cron is `17 1 * * *` UTC,
which is 02:17 in winter and 03:17 in summer in Berlin. GitHub can start
scheduled runs late under load, and disables schedules in repos with no
activity for 60 days (a manual run re-enables them).

### 2. TRMNL

1. In TRMNL go to **Plugins**, search **Private Plugin**, **Add new**.
2. Name: `Vogel des Tages`.
3. Strategy: **Polling**.
4. Polling URL: `https://<user>.github.io/<repo>/today.json`, verb `GET`,
   no headers.
5. Refresh: once a day (set it so the poll lands after ~04:00 Berlin, after
   the Action has run).
6. **Save**, then **Edit Markup**. In the **Full** tab paste the contents of
   `trmnl/full.liquid`. Save.
7. Click **Force Refresh** and check the preview with the device set to
   TRMNL X, landscape.
8. Add the plugin to your device playlist.

### 3. Test the edge cases in the TRMNL previewer

Change the Polling URL temporarily, Force Refresh, look at the preview, then
set it back to `today.json`:

| Case | Polling URL |
|---|---|
| Normal bird (Wiedehopf) | `.../samples/normal/today.json` |
| Very long name (Maskarenenparadiesschnäpper) | `.../samples/longname/today.json` |
| No traits, no German name, no IUCN (Red Grouse) | `.../samples/notraits/today.json` |

You can also run the workflow manually with a `species` id
(e.g. `Apteryx_mantelli`) to publish any bird as `today.json`.

## Layout rules

- Sticker column `w--[58cqw]`, image `image--contain`. Everything else is
  framework classes; no inline styles, no pixel values.
- The headline steps down through four title sizes by `name_size`, chosen from
  the longest single word (German compounds cannot wrap) and the total length.
  Checked against all 7,668 names: the longest word is 27 letters.
- Every text block has `data-clamp`, every optional field is wrapped in
  `{% if field != blank %}`, the facts grid is skipped when no trait exists.
- The Latin name uses `<i>` (the framework has no italic utility). It sits on
  the clamped element itself, because the clamp engine rewrites inner HTML.
- Red List: outline label for LC/NT/DD, filled label for VU, EN, CR, EW, EX.
- Breeding regions are written out in German: PAL Paläarktis, AF Afrika,
  OR Süd- und Südostasien, AU Australasien, NA Nordamerika, MA Mittelamerika,
  SA Südamerika, PO Pazifik, IO Indischer Ozean, AO Atlantik, SO Südpolarmeer,
  TrO Tropische Ozeane, AN Antarktis. English versions are in `region_en`.

## Local preview

```bash
pip install -r requirements-dev.txt
python scripts/build.py --source path/to/huashu-bird-sticker --out site --id Upupa_epops --base-url http://localhost:8765
python tools/render_preview.py site/today.json site/index.html --assets https://trmnl.com
node tools/screenshot.mjs http://localhost:8765/index.html shot.png
```

`tools/screenshot.mjs` renders at 1872x1404 with the framework's `screen--v2
screen--lg screen--4bit` classes and fails if any text leaves the layout. The
real check is still the TRMNL previewer.

## Data notes

Differences from what one might expect from the source description:

- `taxonomy` has no German family names, only `family` (Latin) and
  `familyEnglish`. `data/families_de.json` adds German names for 213 of 250
  families; the rest fall back to English.
- `sticker.kind` is `ai-illustration` for every species.
- `breedingRegion` is often a list (`PAL, AF`); the `REGION` filter matches any
  entry. Exactly `PAL` alone would be 578 species.
- One German name has a trailing slash in the source
  (`Kinabaludschungelschnäpper/`); it is stripped.
- AVONET lists the kiwis' wing length as 0.1 mm; wing values under 5 mm are
  treated as missing.
- 366 of the 7,668 quality species have no `traits`; 174 have no German name
  (the English name becomes the headline).

## Credits and licenses

- **Stickers:** [huashu-bird-sticker](https://github.com/alchaincyf/huashu-bird-sticker)
  by Huashu (alchaincyf), licensed under
  [PolyForm Shield 1.0.0](https://polyformproject.org/licenses/shield/1.0.0/).
  Required Notice: Copyright (c) 2026 Huashu (alchaincyf),
  https://github.com/alchaincyf/huashu-bird-sticker.
  Each sticker was drawn from a reference photo whose author and license are
  listed in the source data; rights in those photos stay with the photographers.
- **Data:** compiled by huashu-bird-sticker under MIT, from the
  [IOC World Bird List v15.2](https://worldbirdnames.org/) (Gill, Donsker &
  Rasmussen, CC BY 3.0), [AVONET](https://doi.org/10.1111/ele.13898)
  (Tobias et al. 2022, CC BY 4.0) and [Wikidata](https://www.wikidata.org/) (CC0).
- **German family names:** Wikidata labels (CC0) plus hand additions.
- **This repo's code:** MIT, see `LICENSE`.

This is a personal, private plugin. It is not meant to be published as a public
TRMNL recipe.
