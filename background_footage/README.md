# Background footage

This folder is where the pipeline looks for real background photographs,
one subfolder per weather/lighting condition. It's empty in a fresh clone
(the actual photos are excluded via `.gitignore` -- they're your own
footage, not part of this codebase) -- you need to populate it before
running `augment_templates.py` or `augment_number_templates.py`.

Expected layout:

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
  `evening_night`, `rain`) are read from `augment_templates.py`'s
  `BACKGROUND_CONDITIONS` list -- rename/add/remove conditions there to
  match whatever footage you actually have.
- Any `.jpg`/`.jpeg`/`.png` file directly inside a condition folder is
  treated as a candidate background frame.
- **Optional safety filter**: if a condition's footage might contain real
  signs somewhere in frame, add a file named `annotated_frames.txt` inside
  that condition's folder, listing (one per line) the filenames to exclude
  from the background pool -- this guarantees a real sign never
  accidentally ends up composited in as "background clutter" behind a
  synthetic one. Skip this file entirely for footage you're sure has no
  signs in it at all.
- You need at least a handful of images per condition (the pipeline defaults
  to sampling 20 per condition, see `N_BACKGROUND_FRAMES_PER_CONDITION` in
  `augment_templates.py` -- it'll happily use fewer if that's all you have,
  just with less variety).

Override this default location entirely with the `SIGN_BACKGROUND_DIR`
environment variable if your footage lives elsewhere -- see `config.py`.
