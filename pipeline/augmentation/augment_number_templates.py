"""Photo-realistic augmentation for numeric sign categories (rychlostnik,
stanicnik, sklonovnik, radiovnik) -- reuses every helper from
augment_templates.py (background pools, warping, photo degradation passes),
but does NOT enumerate one template file per possible number. These
categories can show hundreds of distinct numbers, so one static SVG per
value (what generate_*_templates.py does) means either a huge file count or
thin coverage; instead, each individual augmented *variant* renders its own
fresh, independently-random number on the fly (see generate_variants'
`rendered` callable support in augment_templates.py).

This is currently NOT exercised by default -- augment_templates.py's static,
per-value templates are what populate the bundled dataset. Run this script
in addition if you want broader, less predictable coverage of each numeric
class's value range, at the cost of not being tied to a specific curated
list of values (see README).

Usage: python augment_number_templates.py
Output: <config.OUTPUT_DIR>/<key>/variant_NN_<condition>[_pass].png
        (same directory layout/convention as augment_templates.py, so this
        can be run before or after it and share the same output tree.)
"""
import random
import re
from typing import Callable

import numpy as np

from .augment_templates import (
    CANVAS_SCALE,
    HARD_VARIANTS_PER_TEMPLATE,
    LOWRES_VARIANTS_PER_TEMPLATE,
    LOWVIS_VARIANTS_PER_TEMPLATE,
    VARIANTS_PER_TEMPLATE,
    base_rotation_deg,
    generate_variants,
    get_render_size,
    load_background_pools,
    rotated_bbox_size,
)
from ..core.config import OUTPUT_DIR
from ..core.svg_render import render_svg_string

from ..generators import generate_radiovnik_templates as radiovnik
from ..generators import generate_rychlostnik_templates as rychlostnik
from ..generators import generate_sklonovnik_templates as sklonovnik
from ..generators import generate_stanicnik_templates as stanicnik

random.seed(0)
np.random.seed(0)

OUT_ROOT = OUTPUT_DIR

_DIM_RE = re.compile(r'width="(\d+)" height="(\d+)"')


def _svg_dims(svg_str: str) -> tuple[int, int]:
    m = _DIM_RE.search(svg_str)
    if not m:
        raise ValueError("couldn't find width/height on <svg> root")
    return int(m.group(1)), int(m.group(2))


# --- one random-instance builder per dynamic key, each returning a fresh
# SVG string for one call -- these are what actually vary per augmented
# variant, not a template file (there isn't one) --------------------------
def _rychlostnik_single_3digit_svg() -> str:
    return rychlostnik.build_svg(random.randint(100, 160))


def _rychlostnik_single_2digit_svg() -> str:
    return rychlostnik.build_svg(random.randint(40, 95))


def _rychlostnik_double_3digit_svg() -> str:
    bottom = random.randint(100, 150)
    top = min(160, bottom + random.choice([10, 20, 30]))
    return rychlostnik.build_svg_double(top, bottom)


def _rychlostnik_double_2digit_svg() -> str:
    bottom = random.randint(40, 85)
    top = min(95, bottom + random.choice([10, 20]))
    return rychlostnik.build_svg_double(top, bottom)


def _stanicnik_split_svg() -> str:
    n_digits = random.choice([2, 3])
    top = f"{random.randint(0, 10 ** n_digits - 1):0{n_digits}d}"
    bottom = str(random.randint(0, 9))
    return stanicnik.build_svg_split(top, bottom, is_yellow=random.random() < 0.15)


def _stanicnik_comma_svg() -> str:
    km = str(random.randint(0, 9))
    dec = str(random.randint(0, 9))
    return stanicnik.build_svg_comma(km, dec, is_yellow=random.random() < 0.15)


def _sklonovnik_svg() -> str:
    direction = random.choice(["increase", "decrease"])
    # second_number is genuinely optional on real signs -- omit it some of
    # the time so the classifier sees both.
    second_number = None if random.random() < 0.3 else random.randint(0, 99)
    return sklonovnik.build_svg(direction, random.randint(0, 9999), second_number)


def _radiovnik_svg() -> str:
    return radiovnik.build_svg(random.randint(0, 99))


DYNAMIC_KEYS: dict[str, Callable[[], str]] = {
    "rychlostnik_single_3digit": _rychlostnik_single_3digit_svg,
    "rychlostnik_single_2digit": _rychlostnik_single_2digit_svg,
    "rychlostnik_double_3digit": _rychlostnik_double_3digit_svg,
    "rychlostnik_double_2digit": _rychlostnik_double_2digit_svg,
    "stanicnik_split": _stanicnik_split_svg,
    "stanicnik_comma": _stanicnik_comma_svg,
    "sklonovnik": _sklonovnik_svg,
    "radiovnik": _radiovnik_svg,
}


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    print("Loading background source frames (one pool per condition)...")
    pools = load_background_pools()
    all_conditions = list(pools.keys())

    total = 0
    for key, svg_fn in DYNAMIC_KEYS.items():
        # a representative instance just to read this key's native aspect
        # ratio / canvas size -- content itself is re-rolled per variant
        sample_svg = svg_fn()
        native_w, native_h = _svg_dims(sample_svg)
        ratio = native_w / native_h
        render_w, render_h = get_render_size(ratio)

        base_angle = base_rotation_deg(ratio)
        bbox_w, bbox_h = rotated_bbox_size(render_w, render_h, base_angle)
        canvas_w = int(bbox_w * CANVAS_SCALE)
        canvas_h = int(bbox_h * CANVAS_SCALE)

        out_dir = OUT_ROOT / key
        out_dir.mkdir(parents=True, exist_ok=True)

        def make_renderer(fn=svg_fn, w=render_w, h=render_h):
            return lambda: render_svg_string(fn(), w, h)

        n_normal = generate_variants(
            make_renderer(), out_dir, VARIANTS_PER_TEMPLATE, pools, all_conditions, canvas_w, canvas_h,
            base_angle_deg=base_angle, oblique_prob=0.0,
        )
        n_hard = generate_variants(
            make_renderer(), out_dir, HARD_VARIANTS_PER_TEMPLATE, pools, ["evening_night"], canvas_w, canvas_h,
            base_angle_deg=base_angle,
            filename_suffix="hard",
            noise_sigma_range=(15, 40),
            blur_prob=0.98,
            blur_sigma_frac_range=(0.02, 0.05),
            jpeg_quality_range=(20, 55),
        )
        n_lowvis = generate_variants(
            make_renderer(), out_dir, LOWVIS_VARIANTS_PER_TEMPLATE, pools, all_conditions, canvas_w, canvas_h,
            base_angle_deg=base_angle,
            filename_suffix="lowvis",
            aspect_squash_range=(0.28, 3.6),
            contrast_range=(0.35, 0.75),
            hue_shift_range=(-12, 12),
            noise_sigma_range=(10, 30),
            blur_prob=0.95,
            blur_sigma_frac_range=(0.015, 0.04),
            jpeg_quality_range=(25, 65),
        )
        n_lowres = generate_variants(
            make_renderer(), out_dir, LOWRES_VARIANTS_PER_TEMPLATE, pools, all_conditions, canvas_w, canvas_h,
            base_angle_deg=base_angle,
            filename_suffix="lowres",
            lowres_size_range=(28, 90),
        )

        total += n_normal + n_hard + n_lowvis + n_lowres
        print(f"[{key}] {n_normal} normal + {n_hard} hard + {n_lowvis} lowvis + {n_lowres} lowres "
              f"variants written (each with its own random number)")

    print(f"\nDone. Total augmented images: {total}")
    print(f"Output root: {OUT_ROOT}")


if __name__ == "__main__":
    main()
