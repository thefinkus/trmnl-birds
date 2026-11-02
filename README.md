# Bird of the Day for TRMNL X

One bird a day on a TRMNL X (1872x1404, 16 grays), in one of three framings
that rotate day by day: `hero` (the whole bird as big as it fits, its name in
the largest free corner, Latin name and four facts in small print), `closeup`
(head and shoulders at 1.75x, the bill always in frame) and `quiet` (the bird
alone, one small line with both names). Composed server-side at the exact
pixel size of the TRMNL X full view, pre-dithered to 16 grays, shown 1:1.

```
GitHub Action (daily, ~03:00 Europe/Berlin, and on every push to main)
  sparse + blobless fetch of huashu-bird-sticker @ pinned commit:
    data/species.json, then only today's sticker
  scripts/build.py   pick the bird, write today.json
  scripts/art.py     compose hero/closeup/quiet.png, copy the day's to today.png
  deploy site/ to GitHub Pages, then ask TRMNL to refresh
TRMNL private plugin, Polling on today.json, trmnl/settings.yml + full.liquid;
  the Framing field picks today / hero / closeup / quiet
```

**Pick:** species with `sticker.meetsQualityBar == true` (7,668). `REGION=PAL`
(repository variable) limits it to species breeding in the Palearctic (789,
including multi-region ones like `PAL, AF`). The pool is sorted by a hash of
each species id and the day number steps through it: same date, same bird,
every species once before any repeat. The source repo is pinned
(`SOURCE_REF` in the workflow) so the order never shifts.

**Layout:** the bird is scaled to fill the view; a coarse occupancy grid finds
the biggest empty corner, and the name is set there in Inter Black at the
largest size that fits (up to three lines). The small print goes to another
free corner, else under the name with a gap of a seventh of the name size.
The closeup caps the name at 170 px and keeps the Latin name under it. Aerial
species (AVONET `primaryLifestyle`), often drawn in flight, get a body crop at
1.4x instead of the head crop. The quiet caption sits bottom left, or top left
when the bird reaches into that corner; the bird shrinks a step if neither is
free.

**Rotation:** `VARIANTS` in `scripts/build.py`, one step per day from
`VARIANT_EPOCH` (2026-11-02 shows `hero`). `--variant` forces one for a run.

## Published files

- `https://<user>.github.io/<repo>/today.json`: name, Latin name, family,
  mass, wing, habitat, migration, range, IUCN status, `image_url`,
  `variant_of_the_day`, `images.{hero, closeup, quiet, today}`
- `https://<user>.github.io/<repo>/today.png`: the day's picture, 1836x1368, 16 grays
- `hero.png`, `closeup.png`, `quiet.png`: all three framings of the day's bird

## Setup

### GitHub

1. Settings, Pages, Source: **GitHub Actions**.
2. Optional: repository variable `REGION` = `PAL`.
3. Optional, so the panel updates right after the nightly build instead of
   on TRMNL's own 24 h cycle: variable `TRMNL_PLUGIN_SETTING_ID` (the id in
   the private plugin's URL on trmnl.com) and secret `TRMNL_API_KEY`
   (trmnl.com, Account, API key).
4. Push to `main`, or Actions, **Bird of the Day**, **Run workflow**.

The schedule is `17 1 * * *` UTC (02:17 winter, 03:17 summer in Berlin).
Manual runs take an optional `date` and `species` id.

### TRMNL

1. **Plugins**, **Private Plugin**, **Add new**, name it `Bird of the Day`.
2. Strategy **Polling**, URL `https://<user>.github.io/<repo>/today.json`, `GET`.
3. Refresh once a day.
4. **Edit Markup**, **Full** tab: paste `trmnl/full.liquid`. **Form Builder**: add the
   `framing` select from `trmnl/settings.yml`. Or upload both files as one zip to
   `POST /api/plugin_settings/<id>/archive` (account API key), which sets markup and
   field in one go. Save.
5. **Force Refresh**, check the preview (TRMNL X), add to a playlist.

**Framing** on the plugin's settings page picks the picture: daily rotation
(default), hero, close-up or quiet. The markup reads
`trmnl.plugin_settings.custom_fields_values.framing` and takes the matching URL
from `images`; unset or unknown falls back to `image_url`, the day's picture.

## Local preview

```bash
pip install -r requirements-dev.txt
python scripts/build.py --source path/to/huashu-bird-sticker --out site --id Upupa_epops
python tools/render_preview.py site/today.json site/index.html --assets https://trmnl.com
node tools/screenshot.mjs http://localhost:8765/index.html shot.png
```

## Data notes

- One German name in the source has a stray trailing slash; it is stripped.
- AVONET lists the kiwis' wing as 0.1 mm; wings under 5 mm count as missing.
- 366 of the 7,668 quality species have no traits; the small print is shorter.

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
- **Fonts:** Inter, Instrument Serif, IBM Plex Mono (SIL Open Font License, `assets/fonts/`).
- **Code:** MIT, see `LICENSE`.

Personal, private plugin. Not meant to be published as a public TRMNL recipe.
