# Bird of the Day for TRMNL X

One bird a day on a TRMNL X (1872x1404, 16 grays), drawn six different ways.
Every picture is composed server-side at the exact pixel size of the TRMNL X
full view, pre-dithered to 16 grays, and shown 1:1, so nothing gets resampled.

Daily rotation, alternating between two pictures. The bird is the star; the type takes what is left:

| Variant | Idea |
|---|---|
| `hero` | The bird as big as it fits. The name is set in black Inter in the **largest empty corner** the bird leaves free, at whatever size fits there. Latin name and four facts in small print on the opposite side. |
| `closeup` | Head and shoulders, 1.75x bigger than the screen, the eye about a third of the way down, the bill always inside the frame. Name in a corner the bird does not reach. Aerial species (swifts, raptors, hummingbirds; AVONET `primaryLifestyle`) are often drawn in flight, so they get a body crop at 1.4x instead. |
| `poster` | The name as a pale backdrop, the bird in front of it. |
| `weight` | The mass as a big number, then what that is: "about one hen's egg", "about 3 paperclips". Wing and body length compared to a credit card, a pencil, an A4 sheet. The bird takes the right half. |
| `lifesize` | Only for birds up to 16 cm: the bird at **true size** on the glass (89 px = 1 cm) with a real centimetre ruler. Hummingbirds sit tiny and alone on the white page. |

Also built, selectable but not in the rotation: `names` (the name in up to 43
languages, each line full width), `knockout` (the bird seen through the
letters), `flock` (relatives to scale), `album` (sticker calendar),
`specimen` (museum tag), `guess` (silhouette and clues, reveal after 18:00).

## How it works

```
GitHub Action (daily, ~03:00 Europe/Berlin)
  sparse + blobless fetch of huashu-bird-sticker @ pinned commit:
    data/species.json, then only the stickers today's pictures need (about 40)
  scripts/build.py   pick the bird, write today.json
  scripts/art.py     compose the pictures, quantize to 16 grays
  deploy site/ to GitHub Pages
TRMNL private plugin, Polling on today.json, markup trmnl/full.liquid
```

**Pick:** species with `sticker.meetsQualityBar == true` (7,668). `REGION=PAL`
limits it to species breeding in the Palearctic (789, including multi-region
ones like `PAL, AF`). The pool is sorted by a hash of each species id and the
day number steps through it: same date, same bird, every species once before
any repeat. The source repo is pinned (`SOURCE_REF`) so the order never shifts.

**Life size:** the TRMNL X panel is 10.3" at 1872x1404, so 89.4 px per cm
(`PX_PER_CM` in `scripts/art.py` if yours measures differently). Body length
comes from the data where it is plausible, otherwise it is estimated from
wing length times the median length/wing ratio of the bird's order (computed
from the dataset; passerines about 2.0, owls 1.4). The caption says which.
`LIFESIZE_MAX_CM` in `scripts/build.py` sets the cut-off.

**Names:** Latin, Cyrillic and Greek are set in Inter Black. Japanese,
Chinese, Korean, Arabic, Hebrew, Thai and Malayalam use Noto Sans; the three
CJK files are 10 to 18 MB each, so the Action downloads them (cached) instead
of keeping them in the repo. Without them those languages are skipped.

**Flock:** relatives come from the same family, else the same order, limited
to a third to three times today's wing length so nobody turns into a speck.
They change daily. Placement is a seeded search that minimises overlap.

## Published files

`https://<user>.github.io/<repo>/`

- `today.json`: names, facts, clues, and `images.{hero, closeup, poster, weight, lifesize, today}` (plus the optional variants if built)
- one PNG per variant, 1836x1368, 16 grays
- `today.png`: copy of the day's rotating variant

## Setup

### GitHub

1. Settings, Pages, Source: **GitHub Actions**.
2. Optional: Settings, Secrets and variables, Actions, Variables: `REGION` = `PAL`.
3. Actions, **Bird of the Day**, **Run workflow**. Open `today.json` and the PNGs.

The schedule then runs nightly (`17 1 * * *` UTC = 02:17 winter, 03:17
summer in Berlin). Manual runs take an optional `date` and `species` id.

### TRMNL

1. **Plugins**, **Private Plugin**, **Add new**, name it `Bird of the Day`.
2. Strategy **Polling**, URL `https://<user>.github.io/<repo>/today.json`, `GET`.
3. Refresh once a day, after ~04:00 Berlin. For `guess`, refresh at least
   twice (morning and evening) so the reveal shows up.
4. **Form fields**: paste `trmnl/form_fields.yml` to get a Variant picker.
   Without it, the plugin rotates daily.
5. **Edit Markup**, **Full** tab: paste `trmnl/full.liquid`. Save.
6. **Force Refresh**, check the preview (TRMNL X, landscape), add to a playlist.

The markup reads the picker from
`trmnl.plugin_settings.custom_fields_values.variant`. The guess/reveal switch
uses `trmnl.user.utc_offset`; if TRMNL exposes these under other names in your
account, adjust those two lines.

## Local preview

```bash
pip install -r requirements-dev.txt
python scripts/build.py --source path/to/huashu-bird-sticker --out site --date 2026-11-18
python scripts/build.py --source path/to/huashu-bird-sticker --out site --id Upupa_epops --variants all
```

`tools/render_preview.py` renders the Liquid inside the TRMNL framework and
`tools/screenshot.mjs` screenshots it at 1872x1404.

## Data notes

- `species.json` has no German family names and `sticker.kind` is
  `ai-illustration` everywhere. (`data/families_de.json` is kept for a German
  edition later; the current pictures are English.)
- AVONET lists the kiwis' wing as 0.1 mm; wings under 5 mm count as missing.
- 366 of the 7,668 quality species have no traits. They get no `lifesize` or
  `weight`; the rotation just skips those days' missing variants.
- One German name has a stray trailing slash in the source; it is stripped.

## Credits and licenses

- **Stickers:** [huashu-bird-sticker](https://github.com/alchaincyf/huashu-bird-sticker)
  by Huashu (alchaincyf), [PolyForm Shield 1.0.0](https://polyformproject.org/licenses/shield/1.0.0/).
  Required Notice: Copyright (c) 2026 Huashu (alchaincyf), https://github.com/alchaincyf/huashu-bird-sticker.
  Each sticker was drawn from a reference photo whose author and license are
  listed in the source data; rights in those photos stay with the photographers.
- **Data:** compiled by huashu-bird-sticker (MIT) from the
  [IOC World Bird List v15.2](https://worldbirdnames.org/) (CC BY 3.0),
  [AVONET](https://doi.org/10.1111/ele.13898) (Tobias et al. 2022, CC BY 4.0)
  and [Wikidata](https://www.wikidata.org/) (CC0).
- **Fonts:** Instrument Serif, IBM Plex Mono, Inter and Noto Sans, all SIL
  Open Font License (`assets/fonts/`).
- **Code:** MIT, see `LICENSE`.

Personal, private plugin. Not meant to be published as a public TRMNL recipe.
