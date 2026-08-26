"""Portable background-footage loader.

This is a minimal, dependency-free replacement for the SequenceDataset class
this pipeline originally used (from the parent sodik repo's `dataset`
module) -- that version understands this project's full annotation/COCO
schema, which is unnecessary machinery for what this pipeline actually
needs: "give me N real, unannotated photographs from folder X."

Expected layout, one subfolder per weather/lighting condition, under
config.BACKGROUND_DIR:

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

Any .jpg/.jpeg/.png file directly inside a condition folder is treated as a
candidate background frame.

Optional per-condition filtering: if a condition folder contains a file
named `annotated_frames.txt` (one filename per line, matching files in that
same folder), those specific files are excluded from the pool -- use this
for any condition whose footage might contain real signs somewhere in the
frame, so a real sign never accidentally ends up composited in as
"background clutter" behind a synthetic one. Conditions with no such file
use every image in the folder as-is (appropriate when you know that
footage was never annotated / never shows a sign at all).
"""
import random
from pathlib import Path

import cv2
import numpy as np

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ANNOTATED_LIST_FILENAME = "annotated_frames.txt"


def list_condition_frames(condition_dir: Path) -> list[Path]:
    """All eligible background image paths for one condition folder,
    excluding any listed in that folder's optional annotated_frames.txt."""
    condition_dir = Path(condition_dir)
    if not condition_dir.is_dir():
        raise FileNotFoundError(f"Background condition folder not found: {condition_dir}")

    excluded: set[str] = set()
    annotated_list = condition_dir / ANNOTATED_LIST_FILENAME
    if annotated_list.exists():
        excluded = {line.strip() for line in annotated_list.read_text().splitlines() if line.strip()}

    return [
        p for p in sorted(condition_dir.iterdir())
        if p.suffix.lower() in IMAGE_EXTENSIONS and p.name not in excluded
    ]


def load_random_frames(condition_dir: Path, n: int) -> list[np.ndarray]:
    """Loads up to n randomly chosen, decoded BGR images from one condition
    folder (fewer if the folder has fewer eligible files)."""
    paths = list_condition_frames(condition_dir)
    random.shuffle(paths)

    images = []
    for path in paths[:n]:
        img = cv2.imread(str(path))
        if img is not None:
            images.append(img)
    return images
