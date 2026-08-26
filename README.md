# Sign Augmentation Pipeline

Generates large volumes of photo-realistic synthetic training images for a
railway-sign image classifier, from hand-built SVG vector templates —
composited onto real background footage, geometrically warped to match how
a sign actually sits in a photograph, and degraded (blur, sensor noise,
JPEG compression) to close the gap between "clean vector render" and "real
camera frame."

This project is fully self-contained and portable: every path is
configurable via environment variables (see `config.py`), and it has no
dependency on any other codebase — clone it, install the requirements, and
it runs against its own bundled SVG templates.

See `docs/Augmentation_Pipeline_Report.pdf` for a narrative overview of the
pipeline's design and results. This README is the technical reference for
every script.

---

## Project structure

```
sign-augmentation-pipeline/
├── pipeline/                            # a real Python package (has __init__.py)
│   ├── __init__.py
│   ├── core/                               # portability layer -- no external dependency
│   │   ├── __init__.py
│   │   ├── config.py                          # all configurable paths, one place
│   │   ├── svg_render.py                      # SVG loading + rasterizing
│   │   └── background_loader.py               # real-photo background loading
│   │
│   ├── generators/                         # builds the static SVG templates
│   │   ├── __init__.py
│   │   ├── digit_glyphs.py                    # procedural digit-drawing (seven-segment style)
│   │   ├── digit_glyphs_rounded.py            # procedural digit-drawing (rounded style) -- unused
│   │   ├── generate_rychlostnik_templates.py  # builds templates/rychlostnik/*.svg
│   │   ├── generate_radiovnik_templates.py    # builds templates/radiovnik/*.svg
│   │   ├── generate_stanicnik_templates.py    # builds templates/stanicnik/*.svg
│   │   └── generate_sklonovnik_templates.py   # builds templates/sklonovnik/*.svg
│   │
│   └── augmentation/                       # the augmentation pipeline itself
│       ├── __init__.py
│       ├── augment_templates.py               # the main entry point
│       └── augment_number_templates.py        # companion: randomized numeric variants
│
├── templates/                         # SVG source files (bundled, ~150 files, 628KB)
├── background_footage/                # real photos to composite onto (you supply these)
├── output/                            # generated training images land here
│
├── docs/
│   ├── Augmentation_Pipeline_Report.pdf
│   ├── report_source.html
│   └── example_images/
│
├── requirements.txt
└── .gitignore
```

`pipeline/` is a real Python package (every subfolder has an `__init__.py`),
so cross-module imports are ordinary package imports (e.g.
`from ..core.config import TEMPLATES_DIR`), not path hacks. The practical
consequence: **run every script with `python -m`, from the project root**
(e.g. `python -m pipeline.augmentation.augment_templates`) rather than
`python pipeline/augmentation/augment_templates.py` directly -- a relative
import only resolves when Python knows the file's package context, which
`-m` provides and a bare file path does not.

All paths in `pipeline/core/config.py` resolve relative to the project root
(three levels up from that file, since it now lives two levels below
`pipeline/`) — `templates/`, `background_footage/`, and `output/` stay at
the top level regardless of where the code that reads them lives.

**Two stages, run in this order:**

1. **Template generation** (`generate_*_templates.py`) — writes SVG files to
   `templates/`. Run once per class, or whenever you want to change which
   specific values/pictograms a class covers. Committed to git (they're
   small, human-authored, and the actual source of truth for what a class
   looks like).
2. **Augmentation** (`augment_templates.py`, optionally
   `augment_number_templates.py`) — reads `templates/`, writes thousands of
   photo-realistic training images to `output/`. Re-run whenever you want
   more data, or after changing `templates/`. Not committed to git (it's
   regeneratable, and large).

---

## Quick start after cloning

This walks through everything a fresh `git clone` needs before the first
real dataset generation run -- what's already in the repo, what you have
to add yourself, and the exact command that kicks off generation.

### What you get from the clone, with nothing else done

```
sign-augmentation-pipeline/
├── pipeline/            already there, ready to run
├── templates/           already there -- ~150 bundled SVG files
├── docs/                already there
├── background_footage/  EMPTY except a README.md placeholder -- see step 2
└── output/              does not exist yet -- created automatically on first run
```

`background_footage/` is the **only** thing missing before you can generate
data -- the real photos it needs are your own footage, so they're excluded
from git (`.gitignore`) and don't ship with the repo.

### Step 1 -- install dependencies

```bash
cd sign-augmentation-pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# macOS + Homebrew only: cairosvg needs cairo on the dynamic library path
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"   # Apple Silicon
# export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"    # Intel Mac
# (not needed on Linux if your distro's cairo package is installed normally)
```

### Step 2 -- add your background footage (video → frames → 4 folders)

The pipeline composites signs onto **real background photos**, not video --
if what you have is a video file (a ride-along recording, a dashcam clip,
whatever), pull frames out of it first, e.g. with `ffmpeg`:

```bash
# extracts every 5th frame -- adjust the "5" to taste; consecutive video
# frames are near-duplicates, so there's rarely a reason to keep every one
ffmpeg -i my_video.mp4 -vf "select='not(mod(n\,5))'" -vsync vfr frame_%05d.jpg
```

If you already have an exported image sequence instead of a raw video (a
frame dump some other tool produced), skip `ffmpeg` entirely and just copy
those image files in directly.

Then sort the resulting `.jpg`/`.jpeg`/`.png` files into these 4 folders
under `background_footage/`, by weather/lighting condition:

```
background_footage/
├── good_light/
├── dawn_fog_gloom/
├── evening_night/
└── rain/
```

A few things worth knowing before you do this (all covered in detail in
**`background_footage/README.md`**, which is worth reading in full):

- **Folder names are fixed** -- they come from `BACKGROUND_CONDITIONS` in
  `pipeline/augment_templates.py`. Rename/add/remove entries there if your
  own condition set is different.
- **Multiple videos can share one folder.** If you have footage from
  several different rides all shot in good daylight, extract frames from
  all of them and drop everything into `good_light/` together -- the
  pipeline doesn't care which video a frame came from.
- **File names are unrestricted** -- no naming convention is expected or
  parsed. The only rule is uniqueness *within* one folder (two different
  videos both exporting `frame_00001.jpg` into the same folder will
  silently overwrite one of them -- prefix by source if that's a risk,
  e.g. `ride1_frame_00001.jpg` / `ride2_frame_00001.jpg`).
- **Every one of the 4 folders needs to exist with at least one image in
  it**, or generation crashes the moment that condition gets sampled --
  see the Troubleshooting section in `background_footage/README.md`.
- **Optional**: add an `annotated_frames.txt` inside any condition folder
  whose footage might contain a real sign somewhere in frame, listing one
  filename per line to exclude -- keeps a real sign from ever leaking into
  a synthetic composite as background clutter.

### Step 3 -- (optional) regenerate the SVG templates

Not required -- the repo already ships a full set under `templates/`. Only
run these if you've edited a `generate_*_templates.py` script's value list
(Section "Common tasks" below) and want the templates on disk to catch up:

```bash
python -m pipeline.generators.generate_rychlostnik_templates
python -m pipeline.generators.generate_radiovnik_templates
python -m pipeline.generators.generate_stanicnik_templates
python -m pipeline.generators.generate_sklonovnik_templates
```

### Step 4 -- generate the training dataset

```bash
python -m pipeline.augmentation.augment_templates
```

This is the main run. It prints progress per template as it goes, reads
every SVG under `templates/` and every image under `background_footage/`,
and writes output to `output/augmented_templates/<template_key>/`, one PNG
per generated variant. It's safe to interrupt and re-run -- files that
already exist on disk are skipped, so re-running after adding new footage
or a new template only generates what's missing.

---

## Script reference

`pipeline/` is a real Python package, organized into three subpackages by
role: `core/` (portability layer), `generators/` (template generation),
`augmentation/` (the augmentation pipeline itself). Files below are grouped
the same way and referred to by filename alone for brevity within each
group. Remember every script needs `python -m pipeline.<subpackage>.<name>`
to run (see "Project structure" above for why).

### Core (`pipeline/core/`)

### `config.py`

The single place every path is defined. Three settings, each overridable by
an environment variable, each defaulting to a folder inside the project:

| Variable | Default | Purpose |
|---|---|---|
| `SIGN_TEMPLATES_DIR` | `./templates` | Where SVG templates are read from / written to |
| `SIGN_BACKGROUND_DIR` | `./background_footage` | Where real background photos live |
| `SIGN_AUGMENTED_OUTPUT_DIR` | `./output/augmented_templates` | Where generated training images are written |

Every other script imports its paths from here — there are no hardcoded
absolute paths anywhere else in the project. To point the pipeline at data
on a different disk or a shared drive, just export the relevant variable
before running a script.

### `svg_render.py`

A minimal SVG loader/rasterizer, built on `cairosvg`. Provides:

- **`SvgManager`** — an in-memory cache of parsed SVG files and their
  aspect ratios (parsed once from the `<svg>` tag's `width`/`height`
  attributes, or its `viewBox` as a fallback).
- **`get_svg_manager()`** — returns a fresh manager instance.
- **`load_svg_templates(dir, manager)`** — recursively loads every `.svg`
  file under `dir` into `manager`, keyed by filename stem (so
  `templates/rychlostnik/rychlostnik_100.svg` is loaded under the key
  `"rychlostnik_100"`).
- **`render_svg_template(manager, key, width, height)`** — rasterizes a
  loaded template to a `height × width × 3` BGR numpy array (OpenCV's
  native channel order) at the given pixel size.
- **`render_svg_string(svg_str, width, height)`** — same, but for an SVG
  string that was generated on the fly rather than loaded from a file
  (used by `augment_number_templates.py`).

### `background_loader.py`

A minimal real-photo loader. `list_condition_frames(dir)` lists every
`.jpg`/`.jpeg`/`.png` directly inside a condition folder, excluding any
filenames listed in that folder's optional `annotated_frames.txt` (see
`background_footage/README.md`). `load_random_frames(dir, n)` loads up to
`n` of those, decoded as BGR arrays via OpenCV.

### `digit_glyphs.py` / `digit_glyphs_rounded.py`

Two interchangeable procedural digit-drawing engines, each exposing
`make_digit_chains(digit_w, digit_h, stroke_t)` (returns a dict mapping
`"0"`–`"9"` to lists of point-chains describing that digit's strokes) and
`digit_paths(chains, digit, dx, dy_baseline)` (converts one digit's chains
into SVG `<path>` `d` strings, positioned at a given offset).

- `digit_glyphs.py` draws digits as **seven-segment-style** strokes (the
  blocky calculator-display look) — used by `generate_sklonovnik_templates.py`.
- `digit_glyphs_rounded.py` draws **rounded/oval** digits via arcs — **not
  currently used by anything**, kept in case a future sign category needs
  hand-drawn rounded digits (most current classes instead render digits as
  real system-font `<text>`, which looks better and needs neither module —
  see the note in each `generate_*` script for which approach it uses and
  why).

Neither module reads or writes any files — they're pure geometry helpers,
imported by the `generate_*_templates.py` scripts that need them.

### Generators (`pipeline/generators/`)

### `generate_<class>_templates.py` (four scripts)

Each of these builds the static SVG templates for one sign class, writing
them to `<config.TEMPLATES_DIR>/<class>/`. They're independent of each
other and of the augmentation stage — run any subset of them, in any order.

| Script | Class | Digit rendering | Notes |
|---|---|---|---|
| `generate_rychlostnik_templates.py` | speed-restriction board | Real font (`<text>`, Helvetica Neue Bold) | Single-line and stacked two-line layouts |
| `generate_radiovnik_templates.py` | radio-channel marker | Real font (`<text>`, Arial Rounded MT Bold) | Handset pictogram + 2-digit number |
| `generate_stanicnik_templates.py` | kilometer-position marker | Real font (`<text>`, Helvetica Neue Bold) | "Split" (stacked) and "comma" (inline) layouts, plus a yellow-plate variant |
| `generate_sklonovnik_templates.py` | gradient marker | Procedural (`digit_glyphs.py`) | Increase/decrease triangle direction, optional secondary number |

**Every one of these has a plain Python list of specific values near the
bottom of the file** (e.g. `VALUES` in the rychlostnik script, `COMBOS` in
the sklonovnik script) — this is a curated, representative sample, not an
exhaustive real-world list. **To change which specific values get a
template, edit that list and re-run the script** — nothing else needs to
change; the augmentation stage automatically picks up whatever templates
exist on disk.

Each script's module docstring explains its specific plate geometry, what
reference material (dimensioned standard sheets, real photographs) it was
built from, and — where relevant — the history of an earlier, wrong
approach it replaced (e.g. rychlostnik's font was originally hand-drawn in
a seven-segment style that didn't match real photographs at all; see the
docstring for the full story).

### Augmentation (`pipeline/augmentation/`)

### `augment_templates.py`

The main augmentation pipeline, and the largest file in this project. Run
directly (`python -m pipeline.augmentation.augment_templates`) to
regenerate the entire dataset from whatever's currently in `templates/`.

**What it does, end to end (see `main()`):**

1. Loads every `.svg` under `config.TEMPLATES_DIR` via `svg_render.py`.
2. Loads a pool of real background photos per weather/lighting condition
   via `background_loader.py` (`load_background_pools()`).
3. For each template, renders it once at a fixed resolution, then generates
   five separate "passes" of degraded/composited variants (see below),
   writing each to `output/<template_key>/variant_NN_<condition>[_pass].png`.

**The five passes**, each calling the shared `generate_variants()` function
with different parameters:

| Pass | What it simulates | Key parameters |
|---|---|---|
| `normal` | Ordinary daytime/night/rain capture | Default degradation ranges, all 4 conditions |
| `hard` | Night driving, amplified sensor noise | Night-only background, heavier noise/blur/compression |
| `lowvis` | Fog, off-angle capture, washed-out color | Aspect-ratio squash, low contrast, hue drift |
| `lowres` | A small/distant sign in the source frame | Downscale-then-upscale round-trip |
| `square` | Matches a classifier's inference-time crop margin exactly | Tight square canvas, minimal background margin |

**Key building blocks** (each a standalone function, independently testable
and reusable):

- `get_render_size(ratio)` — picks a render resolution matching a
  template's own aspect ratio, so elongated signs don't get squished into
  a square.
- `base_rotation_deg(ratio)` — the sign's real-world mounting angle (e.g.
  45° for square "diamond"-mounted pictograms in this project's own sign
  set — **check this assumption against your own reference photos before
  reusing it for a different sign set**).
- `load_background_pools()` / `random_background_patch()` — real-photo
  sourcing (see `background_loader.py`).
- `warp_sign_onto_background()` — composites the sign onto a background
  patch with rotation + perspective jitter (or, at low probability, a
  simulated oblique/raking viewing angle).
- `fade_sign()` / `add_directional_shading()` — material weathering and
  directional-lighting effects applied to the sign plate itself, before
  compositing.
- `photo_degrade()` — brightness/contrast/color-cast/blur/sensor-noise/
  JPEG-compression, applied after compositing (i.e. to the whole frame).
- `squash_aspect_ratio()` / `simulate_low_resolution()` — the `lowvis` and
  `lowres` passes' own specific distortions.
- `generate_variants()` — orchestrates one pass: picks a background,
  applies all the above in order, writes the result. Skips any output file
  that already exists, so re-running after adding a new pass (or a new
  template) only generates what's missing.

**Two dials you'll likely want to adjust for your own use case:**

- **`WEAK_TEMPLATE_MULTIPLIER`** (near the top of the file) — a dict
  mapping template key → a multiplier applied to all five passes' variant
  counts for that template. Use this if some of your classes are backed by
  only one template while others have several, which otherwise gives those
  classes proportionally less total training volume for no good reason —
  see the PDF report's discussion of this exact issue for a worked example.
  Ships empty (commented placeholder) in this repo — fill it in based on
  your own class list and template counts.
- **`BACKGROUND_CONDITIONS`** — the list of (folder name, needs-annotation-
  filtering) pairs. Add/remove/rename conditions here to match whatever
  background footage you actually have.

### `augment_number_templates.py`

A companion to `augment_templates.py` for sign classes whose real-world
printed value range is too large to enumerate as static files one at a
time. Instead of reading a template from disk, each augmented variant calls
one of the `_<class>_svg()` functions in this file, which builds a **fresh,
independently random** SVG string on the spot (e.g.
`rychlostnik.build_svg(random.randint(100, 160))`), rendered via
`svg_render.render_svg_string()` instead of `render_svg_template()`.

This reuses every transform in `augment_templates.py` unchanged (imports
`generate_variants`, `load_background_pools`, etc. directly) — the only
difference is *what* gets rendered each time, not how it gets degraded and
composited.

**Not run by default** — `augment_templates.py`'s static, curated templates
are what populate the bundled dataset. Run this script in addition if you
want broader, less predictable coverage of a numeric class's value range,
at the cost of not being tied to a specific curated list (see the PDF
report, "Numeric-Value Coverage and Generalization," for the trade-off this
represents).

---

## Common tasks

**Add a new pictogram class with no existing generator:** write its
`.svg` file by hand (or with any vector tool) directly under
`templates/<class_name>.svg` — `augment_templates.py` will pick it up
automatically on the next run, no code changes needed.

**Add a new numeric-value class:** write a new
`generate_<class>_templates.py` under `pipeline/generators/`, following the
pattern of the existing four — a `build_svg(...)` function, a curated list
of representative values, a `main()` that writes one `.svg` per value under
`<config.TEMPLATES_DIR>/<class_name>/`.

**Change which specific values a numeric class covers:** edit the value
list near the bottom of that class's `generate_*_templates.py` and re-run
it.

**Fix a class-balance imbalance:** add an entry to `WEAK_TEMPLATE_MULTIPLIER`
in `augment_templates.py`.

**Point the pipeline at data on another disk:** set the relevant
`SIGN_*` environment variable from `config.py` before running any script.
