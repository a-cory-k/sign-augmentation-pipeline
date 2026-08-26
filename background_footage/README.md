# Background footage

This folder is where the pipeline looks for real background photographs,
one subfolder per weather/lighting condition. It's empty in a fresh clone
(the actual photos are excluded via `.gitignore` -- they're your own
footage, not part of this codebase) -- you need to populate it before
running `pipeline.augmentation.augment_templates` or `pipeline.augmentation.augment_number_templates`.

## 1. Video (or an image sequence) needs to become plain image files first

The pipeline never opens a video file directly -- `background_loader.py`
only reads `.jpg`/`.jpeg`/`.png` files that already sit directly inside a
condition folder. If what you have is:

- **a video file** (a recording from a cab-ride camera, a dashcam, a phone,
  etc.) -- extract frames from it yourself first, e.g. with `ffmpeg`:

  ```bash
  # every frame (fine for a short clip)
  ffmpeg -i my_ride.mp4 frame_%05d.jpg

  # every 5th frame (recommended for anything more than a couple of
  # minutes -- consecutive video frames are near-duplicates, so this gives
  # more effective visual variety per file saved, and keeps the folder a
  # manageable size)
  ffmpeg -i my_ride.mp4 -vf "select='not(mod(n\,5))'" -vsync vfr frame_%05d.jpg
  ```

- **an already-extracted image sequence** (frames some other tool -- an
  annotation tool, a different pipeline -- already exported for you as
  individual files) -- no extraction step needed, just copy those files
  in directly.

Either way, what ends up inside each condition folder below must be plain
image files, not a video container.

## 2. Where the files go: exactly 4 folders, one per condition

```
background_footage/
  good_light/
    frame_00001.jpg
    frame_00002.jpg
    ...
    annotated_frames.txt   <- optional, see below
  dawn_fog_gloom/
    ...
  evening_night/
    ...
  rain/
    ...
```

- The four condition folder names (`good_light`, `dawn_fog_gloom`,
  `evening_night`, `rain`) are read from `pipeline/augmentation/augment_templates.py`'s
  `BACKGROUND_CONDITIONS` list -- rename/add/remove conditions there to
  match whatever footage you actually have. If you only have footage for
  2 conditions, either delete the other two entries from that list, or
  make sure every folder in the list exists with at least one image in it
  (see "Troubleshooting" below for what happens if you don't).
- Any `.jpg`/`.jpeg`/`.png` file directly inside a condition folder is
  treated as a candidate background frame. Subfolders inside a condition
  folder are not scanned -- keep the image files flat, directly inside
  `good_light/` etc.

## 3. Multiple videos/sequences can land in the same condition folder

A condition folder doesn't have to come from one single video. If you have
footage from three different rides that were all shot in good daylight,
extract frames from all three and drop them into `good_light/` together --
the loader just globs every image file directly inside the folder, with no
concept of "which video did this frame come from."

File names are read as opaque paths only -- there is no naming convention
to follow, no fixed pattern, no requirement that they match anything. The
only two rules are: the extension has to be `.jpg`/`.jpeg`/`.png`, and
names have to be **unique within that one folder** (if two different videos
both happen to export a `frame_00001.jpg`, the second copy silently
overwrites the first -- rename before copying, or extract straight into
separate temp folders and copy in with a per-source prefix, e.g.
`ride1_frame_00001.jpg` / `ride2_frame_00001.jpg`). For example, a
`good_light/` folder fed from two different source videos might look like:

```
background_footage/good_light/
  ride1_frame_00120.jpg
  ride1_frame_00125.jpg
  ride1_frame_00130.jpg
  ride2_2026-04-02_003201.jpg
  ride2_2026-04-02_003211.jpg
  annotated_frames.txt
```

## 4. Optional safety filter: excluding frames that might show a real sign

If a condition's footage might contain real signs somewhere in frame, add a
file named `annotated_frames.txt` inside that condition's folder, listing
(one filename per line, matching files in that same folder) the frames to
exclude from the background pool -- this guarantees a real sign never
accidentally ends up composited in as "background clutter" behind a
synthetic one:

```
# background_footage/good_light/annotated_frames.txt
ride1_frame_00125.jpg
ride2_2026-04-02_003211.jpg
```

Skip this file entirely for footage you're sure has no signs in it at all
-- every image in the folder is then used as-is.

## 5. How many frames do you need

The pipeline defaults to sampling up to 20 frames per condition per run
(`N_BACKGROUND_FRAMES_PER_CONDITION` in `pipeline/augmentation/augment_templates.py`).
It'll happily run with fewer -- but **every condition folder listed in
`BACKGROUND_CONDITIONS` needs to exist and contain at least one image**,
or generation will crash the first time that condition gets sampled (see
"Troubleshooting"). A handful of frames per condition works; more gives
more visual variety in the generated backgrounds, with diminishing returns
well before you'd need "every frame from every video."

## Troubleshooting

- **`FileNotFoundError: Background condition folder not found`** -- one of
  the folders listed in `BACKGROUND_CONDITIONS` doesn't exist on disk yet.
  Create it (even with just one image inside), or remove that condition
  from the list in `pipeline/augmentation/augment_templates.py` if you don't have that
  kind of footage.
- **`IndexError: Cannot choose from an empty sequence`** (or similar,
  during generation) -- a condition folder exists but has zero valid image
  files in it. Add at least one image, or remove that condition from
  `BACKGROUND_CONDITIONS`.

## Pointing this at footage stored elsewhere

Override this default location entirely with the `SIGN_BACKGROUND_DIR`
environment variable if your footage lives elsewhere (a different disk, a
shared drive) -- see `pipeline/core/config.py`:

```bash
export SIGN_BACKGROUND_DIR=/mnt/shared/rail_footage
python -m pipeline.augmentation.augment_templates
```
