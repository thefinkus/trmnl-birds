# Bird of the Day for TRMNL

One bird a day on a TRMNL panel (X at 1872x1404 in 16 grays, OG at 800x480 in
1-bit, landscape or portrait), in one of three framings
that rotate day by day: `hero` (the whole bird as big as it fits, its name in
the largest free corner, Latin name and four facts in small print), `closeup`
(head and shoulders at 1.75x, the bill always in frame) and `quiet` (the bird
alone, one small line with both names). Composed server-side at the exact
pixel size of each panel's full view, pre-dithered to the panel's grays, shown 1:1.

```
GitHub Action (nightly, three slots from 02:17 Europe/Berlin, and on every push to main)
  sparse + blobless fetch of huashu-bird-sticker @ pinned commit:
    data/species.json, then only today's sticker
  scripts/build.py   pick the bird, write today.json
  scripts/art.py     compose hero, closeup and quiet for TRMNL X and OG, landscape
                     and portrait (12 PNGs), copy the day's framing to today*.png
  deploy site/ to GitHub Pages, then make TRMNL poll and render
TRMNL plugin (recipe), Polling on today.json, trmnl/settings.yml + four layouts;
  the markup shows the picture for the panel and orientation it runs on,
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

**Panels:** every framing is composed four times, for the X (1836x1368 inside
the 18 px frame) and the OG (780x460 inside the 10 px frame), each in landscape
and portrait. Lengths tuned on the X are halved on the OG; there the facts line
is dropped, the Latin name is set in Inter Italic (Instrument Serif's hairlines
break up in 1-bit) and goes right under the name, and all type is pure black,
since any gray would dither to speckle. The name keeps its margin on both
sides, which matters in the narrow portrait views.

**Rotation:** `VARIANTS` in `scripts/build.py`, one step per day from
`VARIANT_EPOCH` (2026-11-02 shows `hero`). `--variant` forces one for a run.

## Published files

- `https://<user>.github.io/<repo>/today.json`: name, Latin name, family,
  mass, wing, habitat, migration, range, IUCN status, `image_url`,
  `variant_of_the_day`, and four sets of picture URLs, each with `hero`,
  `closeup`, `quiet` and `today`: `images` (TRMNL X landscape, 1836x1368,
  16 grays), `images_portrait` (1368x1836), `images_og` (TRMNL OG landscape,
  780x460, 1-bit) and `images_og_portrait` (460x780); `targets` spells the
  sizes out
- `today.png`, `today_portrait.png`, `today_og.png`, `today_og_portrait.png`:
  the day's picture for each panel and orientation
- `hero*.png`, `closeup*.png`, `quiet*.png`: all three framings, same suffixes

## Setup

### GitHub

1. Settings, Pages, Source: **GitHub Actions**.
2. Optional: repository variable `REGION` = `PAL`.
3. Optional, so your own instance shows the new bird right after the nightly
   build instead of at its next 6-hour poll: variable `TRMNL_PLUGIN_SETTING_ID`
   (the id in the private plugin's URL on trmnl.com) and secret `TRMNL_API_KEY`
   (trmnl.com, Account, API key). The `refresh` job then changes the instance's
   refresh interval for a moment, which makes TRMNL poll `today.json` and render
   at once, and puts the interval back. (TRMNL's `POST .../refreshes` only
   refetches the data, it does not render.)
4. Push to `main`, or Actions, **Bird of the Day**, **Run workflow**.

The schedule has three slots, `17 1`, `17 3` and `17 5` UTC (02:17, 04:17 and 06:17 in
Berlin winter time), because GitHub sometimes starts a scheduled run hours late; a repeat
run builds the same bird. Manual runs take an optional `date` and `species` id.

### TRMNL

The plugin is meant to be installed as a recipe from the TRMNL catalog. To run
your own copy from a fork:

1. **Plugins**, **Private Plugin**, **Add new**, name it `Bird of the Day`.
2. Strategy **Polling**, URL `https://<user>.github.io/<repo>/today.json`, `GET`,
   refresh every 6 hours.
3. Zip the contents of `trmnl/` (settings.yml and the four layouts) and upload it to
   `POST /api/plugin_settings/<id>/archive` with your account API key; that sets the
   layouts and both form fields in one go. Or paste the layouts in **Edit Markup**
   and build the fields from `trmnl/settings.yml` in the **Form Builder**.
4. **Force Refresh**, check the previews, add to a playlist.

**Framing** on the plugin's settings page picks the picture: daily rotation
(default), hero, close-up or quiet. The markup reads
`trmnl.plugin_settings.custom_fields_values.framing` and takes the matching URL
from `images`; unset or unknown falls back to `image_url`, the day's picture.
The full layout holds four `<img>` tags and shows one: the framework's `lg:`
classes tell a TRMNL X from an OG, `portrait:` tells the orientation, so each
panel gets a picture composed for exactly its view and shown 1:1. Half and
quadrant layouts show the quiet picture fitted into the cell.

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
