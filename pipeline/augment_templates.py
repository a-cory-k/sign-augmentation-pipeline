"""Synthesize photo-realistic training/eval variants from SVG sign templates.

Renders each SVG in config.TEMPLATES_DIR and composites it onto real
background patches (sampled from config.BACKGROUND_DIR -- see
background_loader.py for the exact expected folder layout), with a small
rotation/perspective jitter and photo-realistic degradation (brightness/
contrast/color cast, blur, sensor noise, JPEG re-compression). Purpose:
templates are clean vector renders with no real-world context, which hurts
a classifier trained on them without this step -- this closes that gap
without needing any new manually-labeled data.

Five passes per template:
  1. "normal"  -- VARIANTS_PER_TEMPLATE, split evenly across all 4
     conditions, mild degradation (see photo_degrade).
  2. "hard"    -- HARD_VARIANTS_PER_TEMPLATE, evening_night background only,
     amplified noise/blur/compression -- for harder evaluation cases (dark,
     grainy frames), on top of (not replacing) the normal pass.
  3. "lowvis"  -- LOWVIS_VARIANTS_PER_TEMPLATE, squashed aspect ratio + heavy
     low-contrast/hue-drift/blur -- reproduces low-contrast stripes barely
     visible against their background, extreme aspect-ratio squashing when
     a very wide/narrow real crop gets forced into a square model input,
     and occasional off-color paint variants.
  4. "lowres"  -- LOWRES_VARIANTS_PER_TEMPLATE, downscale-then-upscale to a
     size matching real small/distant crops (see simulate_low_resolution) --
     a small crop never had the detail a blurred full-resolution render
     still carries, so blur degradation alone doesn't reproduce this.
  5. "square"  -- SQUARE_VARIANTS_PER_TEMPLATE, square canvas just barely
     bigger than the sign's own tight bbox (SQUARE_CANVAS_SCALE_RANGE) --
     a sliver of real background at the corners when rotated, nothing more.
     Matches the margin convention used when cropping a detected sign for
     classification at inference time -- keeping both sides of that
     convention in agreement matters (see README).

Usage: python augment_templates.py
Output: <config.OUTPUT_DIR>/<template_key>/variant_NN_<condition>[_pass].png
        (hard/lowvis/lowres/square-pass files get a matching filename
        suffix so they never collide with the normal pass. Re-running is
        safe and incremental -- generate_variants skips any variant file
        that already exists, so adding a new pass to an already-populated
        output directory only writes the new files.)
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cv2
import numpy as np

from background_loader import load_random_frames
from config import BACKGROUND_DIR, OUTPUT_DIR, TEMPLATES_DIR
from svg_render import get_svg_manager, load_svg_templates, render_svg_template

random.seed(0)
np.random.seed(0)

OUT_ROOT = OUTPUT_DIR
RENDER_SIZE = 320          # long-side render size; short side follows the
                           # template's own aspect ratio (see get_render_size)

# Real crops are cropped tight to their annotated bbox (aspect ratios
# ~0.8-1.0) -- barely any margin. A small canvas margin (just enough to
# reveal corner slivers when rotated) matches that far better than a big
# scenic border around the sign.
CANVAS_SCALE = 1.12
N_BACKGROUND_FRAMES_PER_CONDITION = 20

VARIANTS_PER_TEMPLATE = 60       # normal pass, split evenly across all conditions
HARD_VARIANTS_PER_TEMPLATE = 20  # extra pass: evening_night + heavier noise
LOWVIS_VARIANTS_PER_TEMPLATE = 20  # extra pass: squashed aspect ratio + heavy
                                    # low-contrast/hue-drift/blur
LOWRES_VARIANTS_PER_TEMPLATE = 20  # extra pass: simulated small-crop resolution loss
SQUARE_VARIANTS_PER_TEMPLATE = 40  # extra pass: square canvas, minimal real-
                                    # background margin (see module docstring)

# canvas_scale is relative to the sign's own tight rotated bbox side (not
# CANVAS_SCALE, which stays reserved for the tight normal/hard/lowvis
# canvas) -- kept deliberately close to 1.0: training should see the same
# margin distribution the real inference-time crops get, not just "some
# square with a bit of background". A mismatch here is a common, easy-to-
# introduce bug -- whatever margin convention your own inference/cropping
# code uses, keep SQUARE_CANVAS_SCALE_RANGE in agreement with it.
SQUARE_CANVAS_SCALE_RANGE = (1.05, 1.15)
MAX_MARGIN_CANVAS_SIDE = 420  # hard cap in pixels, see generate_variants --
                               # everything gets resized down to a small
                               # fixed size at training time regardless, so
                               # an uncapped canvas is wasted decode/resize
                               # cost for zero quality benefit

# Templates that are the *only* SVG for their class (no sibling variants to
# pool with, unlike e.g. a class with several pictogram variants) end up
# with far less effective visual diversity per class even at the same
# VARIANTS_PER_TEMPLATE. This is an explicit, per-key multiplier table
# rather than an automatic rule, since "is this template its class's only
# representative" isn't a geometric property that can be derived from the
# SVG itself -- edit this dict directly for your own class list and
# whatever imbalance you find between them (see README for how to diagnose
# this: compare per-class image counts, and precision/recall on any
# confused pairs of classes).
WEAK_TEMPLATE_MULTIPLIER: dict[str, float] = {
    # "some_template_key": 3.0,
}

# (condition folder name, needs annotation filtering). Set the second
# element to True for any condition whose footage might contain real signs
# somewhere in frame -- see background_loader.py's annotated_frames.txt
# convention. Conditions known to contain zero signed frames can skip the
# check entirely.
BACKGROUND_CONDITIONS = [
    ("good_light", True),
    ("dawn_fog_gloom", False),
    ("evening_night", False),
    ("rain", False),
]


def get_render_size(ratio: float) -> tuple[int, int]:
    """(width, height) for rendering a template with aspect ratio `ratio`
    (width/height), with the longer side fixed at RENDER_SIZE. Templates
    can be far from square (e.g. a wide board sign vs. a tall narrow one) --
    rendering everything to a fixed square would stretch them badly.
    """
    if ratio >= 1:
        return RENDER_SIZE, round(RENDER_SIZE / ratio)
    return round(RENDER_SIZE * ratio), RENDER_SIZE


def base_rotation_deg(ratio: float) -> float:
    """In-plane rotation (degrees) the physical sign is mounted at, before
    per-variant jitter. Exactly-square pictogram templates (aspect ratio
    1.0) are often physically mounted "diamond"-style, rotated 45deg --
    check this against your own real photographed crops per class before
    trusting it blindly; it's driven by aspect ratio (not a class name
    list) so it generalizes to any template, present or future, but the
    45deg-for-square assumption is specific to this project's own sign
    set and mounting conventions.
    """
    return 45.0 if 0.98 <= ratio <= 1.02 else 0.0


def rotated_bbox_size(w: float, h: float, angle_deg: float) -> tuple[float, float]:
    """Axis-aligned bounding box of a w x h rectangle rotated by angle_deg."""
    angle = np.deg2rad(angle_deg)
    cos_a, sin_a = abs(np.cos(angle)), abs(np.sin(angle))
    return w * cos_a + h * sin_a, w * sin_a + h * cos_a


def load_background_pools() -> dict[str, list[np.ndarray]]:
    """One real-photo pool per weather/lighting condition, read from
    config.BACKGROUND_DIR (see background_loader.py for the expected
    per-condition folder layout and optional annotation-filtering
    convention)."""
    pools: dict[str, list[np.ndarray]] = {}
    for seq_name, _needs_filter in BACKGROUND_CONDITIONS:
        # _needs_filter isn't branched on here -- list_condition_frames
        # (inside load_random_frames) always checks for an optional
        # annotated_frames.txt and only excludes files if that list exists,
        # so a condition with no such file is already equivalent to
        # "no filtering needed" with no extra code path required.
        images = load_random_frames(BACKGROUND_DIR / seq_name, N_BACKGROUND_FRAMES_PER_CONDITION)
        pools[seq_name] = images
        print(f"  [{seq_name}] {len(images)} background frames loaded")
    return pools


def random_background_patch(images: list[np.ndarray], w: int, h: int) -> np.ndarray:
    bg = random.choice(images)
    bh, bw = bg.shape[:2]
    if bw < w or bh < h:
        scale = max(w / bw, h / bh) * 1.05
        bg = cv2.resize(bg, (int(bw * scale) + 1, int(bh * scale) + 1))
        bh, bw = bg.shape[:2]
    x0 = random.randint(0, bw - w)
    y0 = random.randint(0, bh - h)
    return bg[y0:y0 + h, x0:x0 + w].copy()


def warp_sign_onto_background(
    sign_bgr: np.ndarray,
    background: np.ndarray,
    base_angle_deg: float = 0.0,
    oblique_prob: float = 0.0,
    oblique_strength_range: tuple[float, float] = (0.15, 0.4),
) -> np.ndarray:
    """Place `sign_bgr` (fills its own frame entirely -- no transparency) at
    `base_angle_deg` (the sign's real-world mounting angle, e.g. 45 for a
    diamond-mounted pictogram) plus a random small rotation/perspective
    jitter inside `background`, revealing real background at the corners
    where the rotated sign no longer covers the canvas.

    With probability `oblique_prob`, instead of the normal mild independent
    per-corner jitter, simulates a genuine raking viewing angle: one whole
    edge of the sign is pushed toward its opposite edge (like a card tilted
    away from the camera), rather than 4 independently-jittered corners --
    a visually distinct distortion pattern from ordinary keystoning, worth
    it only if your own real photos actually show this (steep near-edge-on
    viewing angles); defaults to disabled (oblique_prob=0.0) since it made
    this project's own results net worse when tried project-wide.
    """
    sh, sw = sign_bgr.shape[:2]
    ch, cw = background.shape[:2]

    margin_x = (cw - sw) / 2.0
    margin_y = (ch - sh) / 2.0
    src = np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]])  # TL, TR, BR, BL

    max_rot_deg = 14.0
    max_persp = 0.05
    # Negated: in image coords (y grows downward) this rotation formula is
    # visually clockwise for positive angle, opposite of the counterclockwise
    # convention a "diamond mounting" (base_angle_deg=45) needs -- verify
    # against your own real crops if you change base_rotation_deg's logic.
    angle = np.deg2rad(-(base_angle_deg + random.uniform(-max_rot_deg, max_rot_deg)))
    cos_a, sin_a = np.cos(angle), np.sin(angle)
    cx, cy = sw / 2.0, sh / 2.0

    # Guarded behind oblique_prob > 0 so that oblique_prob=0.0 consumes
    # exactly zero extra random() calls -- otherwise every subsequent draw
    # (background choice, jitter, degradation) would silently shift out of
    # sync with a fixed random.seed(0) even when this feature is "disabled".
    apply_oblique = oblique_prob > 0 and random.random() < oblique_prob
    if apply_oblique:
        axis = random.choice(["horizontal", "vertical"])  # which edge pair compresses
        strength = random.uniform(*oblique_strength_range)
        squeeze_first_pair = random.random() < 0.5

    dst = []
    for i, (x, y) in enumerate(src):
        # rotate around center
        rx = cx + (x - cx) * cos_a - (y - cy) * sin_a
        ry = cy + (x - cx) * sin_a + (y - cy) * cos_a

        if apply_oblique:
            if axis == "horizontal":
                # compress the top edge (0,1) or bottom edge (2,3) toward
                # the vertical centerline -- simulates looking up/down at
                # an angle at a rectangular board.
                in_far_pair = i in (0, 1) if squeeze_first_pair else i in (2, 3)
                if in_far_pair:
                    rx = cx + (rx - cx) * (1 - strength)
            else:
                # compress the left edge (0,3) or right edge (1,2) toward
                # the horizontal centerline -- simulates a steep sideways
                # (near edge-on) viewing angle.
                in_far_pair = i in (0, 3) if squeeze_first_pair else i in (1, 2)
                if in_far_pair:
                    ry = cy + (ry - cy) * (1 - strength)
        else:
            # perspective jitter per corner
            rx += random.uniform(-max_persp, max_persp) * sw
            ry += random.uniform(-max_persp, max_persp) * sh

        # place within the bigger canvas (centered, with margin)
        dst.append([rx + margin_x, ry + margin_y])
    dst = np.float32(dst)

    M = cv2.getPerspectiveTransform(src, dst)
    warped_sign = cv2.warpPerspective(sign_bgr, M, (cw, ch))
    mask = cv2.warpPerspective(
        np.full((sh, sw), 255, dtype=np.uint8), M, (cw, ch))
    # feather the mask edge slightly so the composite seam isn't razor-sharp
    mask = cv2.GaussianBlur(mask, (5, 5), 0)

    mask_f = (mask.astype(np.float32) / 255.0)[:, :, None]
    composite = background.astype(np.float32) * \
        (1 - mask_f) + warped_sign.astype(np.float32) * mask_f
    return np.clip(composite, 0, 255).astype(np.uint8)


def fade_sign(
    sign_bgr: np.ndarray,
    prob: float = 0.35,
    desaturate_range: tuple[float, float] = (0.3, 0.75),
    lighten_range: tuple[float, float] = (0, 25),
) -> np.ndarray:
    """Randomly simulate sun/weather-bleached paint on the sign plate itself
    (applied before compositing onto the background, so it reads as material
    weathering, not a lighting/scene effect). Desaturating in HSV naturally
    affects colored fills far more than near-neutral (white/black) strokes
    and borders, which already have near-zero saturation -- matching how
    real weathered signs stay legible even as their color washes out.
    """
    if random.random() >= prob:
        return sign_bgr
    hsv = cv2.cvtColor(sign_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] *= (1 - random.uniform(*desaturate_range))
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] + random.uniform(*lighten_range), 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def add_directional_shading(
    sign_bgr: np.ndarray,
    prob: float = 0.45,
    strength_range: tuple[float, float] = (0.06, 0.22),
) -> np.ndarray:
    """Randomly simulate directional sunlight raking across the sign plate,
    brightening one edge and darkening the opposite -- distinct from the
    uniform per-image brightness shift in photo_degrade, which shifts the
    whole frame's exposure rather than creating a gradient across the sign
    itself. Applied to the sign only, before compositing, as a linear
    gradient along a random direction.
    """
    if random.random() >= prob:
        return sign_bgr
    h, w = sign_bgr.shape[:2]
    angle = random.uniform(0, 2 * np.pi)
    yy, xx = np.mgrid[0:h, 0:w]
    direction = (xx / w - 0.5) * np.cos(angle) + (yy / h - 0.5) * np.sin(angle)
    direction /= np.abs(direction).max() + 1e-6
    gradient = 1.0 + direction * random.uniform(*strength_range)
    out = sign_bgr.astype(np.float32) * gradient[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def photo_degrade(
    img: np.ndarray,
    noise_sigma_range: tuple[float, float] = (2, 14),
    blur_prob: float = 0.92,
    blur_sigma_frac_range: tuple[float, float] = (0.005, 0.02),
    jpeg_quality_range: tuple[int, int] = (35, 90),
    contrast_range: tuple[float, float] = (0.75, 1.25),
    hue_shift_range: tuple[float, float] = (0.0, 0.0),
) -> np.ndarray:
    """Photo-realistic degradation. Params are tunable per call so a "hard"
    pass can just widen the ranges / lower jpeg_quality_range instead of
    duplicating this whole function.

    Blur sigma is a fraction of the image's longer side rather than a fixed
    pixel kernel, so it scales automatically with RENDER_SIZE/CANVAS_SCALE.
    Tune the default ranges against your own real crops' measured sharpness
    (e.g. Laplacian variance at a common scale) before trusting them --
    synthetic renders default to much sharper than a real photo from a
    moving camera unless blur is deliberately calibrated against real data.

    contrast_range / hue_shift_range default to no-op-ish values so existing
    callers are unaffected by default; a "lowvis" pass widens contrast_range
    toward heavily washed-out and sets a nonzero hue_shift_range, to match
    low-contrast/off-color real crops.
    """
    out = img.astype(np.float32)

    # brightness / contrast jitter
    brightness = random.uniform(-25, 25)
    contrast = random.uniform(*contrast_range)
    out = (out - 127.5) * contrast + 127.5 + brightness

    # mild color cast (simulates lighting / white balance variation)
    for c in range(3):
        out[:, :, c] *= random.uniform(0.92, 1.08)

    out = np.clip(out, 0, 255).astype(np.uint8)

    # optional hue rotation (odd off-color paint/lighting variants)
    if hue_shift_range != (0.0, 0.0):
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.int16)
        hsv[:, :, 0] = (hsv[:, :, 0] + int(random.uniform(*hue_shift_range))) % 180
        out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # blur (focus softness / slight motion blur), sigma relative to image
    # size -- geometric mean of h/w, not max, so very elongated signs don't
    # get over-blurred relative to their short dimension just because their
    # long dimension is big.
    if random.random() < blur_prob:
        scale = (out.shape[0] * out.shape[1]) ** 0.5
        sigma = random.uniform(*blur_sigma_frac_range) * scale
        k = max(3, int(sigma * 3) | 1)  # odd kernel, ~3 sigma radius
        out = cv2.GaussianBlur(out, (k, k), sigma)

    # gaussian noise (sensor noise)
    noise_sigma = random.uniform(*noise_sigma_range)
    noise = np.random.normal(0, noise_sigma, out.shape).astype(np.float32)
    out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # JPEG re-encode artifact
    quality = random.randint(*jpeg_quality_range)
    ok, encoded = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if ok:
        out = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    return out


def squash_aspect_ratio(img: np.ndarray, ratio_range: tuple[float, float] = (0.28, 3.6)) -> np.ndarray:
    """Stretches the image to a random new aspect ratio (area roughly
    preserved) and back to its original size. Reproduces the distortion a
    real narrow/wide sign crop suffers when forced through a classifier's
    fixed square input.
    """
    h, w = img.shape[:2]
    target_ratio = random.uniform(*ratio_range)
    area = w * h
    new_w = max(4, int((area * target_ratio) ** 0.5))
    new_h = max(4, int((area / target_ratio) ** 0.5))
    stretched = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    return cv2.resize(stretched, (w, h), interpolation=cv2.INTER_LINEAR)


def simulate_low_resolution(
    img: np.ndarray,
    min_size_range: tuple[int, int] = (28, 90),
) -> np.ndarray:
    """Downscale to a size matching real small/distant crops, then back up
    to the canvas size with bilinear interpolation. The normal/hard/lowvis
    passes all degrade a full-resolution render with blur/noise/jpeg, but a
    genuinely small real crop isn't just a blurred full-resolution photo --
    it never had those pixels to begin with. Calibrate min_size_range
    against your own real crops' measured pixel widths (both correctly- and
    incorrectly-classified) before trusting the default range. Bilinear
    (not e.g. Lanczos) on the way back up should match whatever resize
    method your classifier itself uses at inference time.
    """
    h, w = img.shape[:2]
    target_long = random.randint(*min_size_range)
    scale = target_long / max(h, w)
    small_w, small_h = max(1, round(w * scale)), max(1, round(h * scale))
    small = cv2.resize(img, (small_w, small_h), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def generate_variants(
    rendered,
    out_dir: Path,
    count: int,
    condition_pools: dict[str, list[np.ndarray]],
    condition_names: list[str],
    canvas_w: int,
    canvas_h: int,
    base_angle_deg: float = 0.0,
    fade_prob: float = 0.35,
    shading_prob: float = 0.0,
    oblique_prob: float = 0.0,
    filename_suffix: str = "",
    aspect_squash_range: tuple[float, float] | None = None,
    lowres_size_range: tuple[int, int] | None = None,
    canvas_scale_range: tuple[float, float] | None = None,
    base_square_side: float | None = None,
    sign_scale_range: tuple[float, float] | None = None,
    skip_existing: bool = True,
    **degrade_kwargs,
) -> int:
    """Generate `count` variants split as evenly as possible across
    `condition_names`, writing to out_dir. Returns number of files actually
    written (skip_existing=True skips any variant whose output file is
    already on disk, so re-running to add a new pass doesn't waste time
    regenerating earlier passes).

    `rendered` is normally a fixed BGR array (every variant is the same base
    render, just degraded/warped differently). It may also be a zero-arg
    callable, invoked fresh for *each* variant -- used by
    augment_number_templates.py for sign categories where the point isn't
    to enumerate every possible printed value as its own template file, but
    to have each augmented variant show a different random value.
    """
    assignments = [condition_names[i % len(condition_names)] for i in range(count)]
    random.shuffle(assignments)

    written = 0
    for v, condition in enumerate(assignments):
        suffix = f"_{filename_suffix}" if filename_suffix else ""
        out_path = out_dir / f"variant_{v:02d}_{condition}{suffix}.png"
        if skip_existing and out_path.exists():
            continue

        variant_canvas_w, variant_canvas_h = canvas_w, canvas_h
        if canvas_scale_range is not None:
            # square canvas, sized off the sign's own tight bbox side (not
            # canvas_w/canvas_h, which already carry the small CANVAS_SCALE
            # margin from the normal/hard/lowvis passes) -- randomized per
            # variant for margin diversity. Capped at MAX_MARGIN_CANVAS_SIDE
            # since training resizes everything down to a small fixed size
            # regardless, so anything past a few multiples of that is
            # wasted decode/resize cost.
            side = min(round(base_square_side * random.uniform(*canvas_scale_range)), MAX_MARGIN_CANVAS_SIDE)
            variant_canvas_w = variant_canvas_h = side

        background = random_background_patch(condition_pools[condition], variant_canvas_w, variant_canvas_h)
        frame = rendered() if callable(rendered) else rendered
        if sign_scale_range is not None:
            # shrink the sign itself before compositing -- reveals more real
            # background around a physically smaller-looking sign, instead
            # of just blurring/downsampling a full-frame one (see lowres)
            shrink = random.uniform(*sign_scale_range)
            fh, fw = frame.shape[:2]
            frame = cv2.resize(
                frame, (max(1, round(fw * shrink)), max(1, round(fh * shrink))),
                interpolation=cv2.INTER_AREA,
            )
        sign = fade_sign(frame, prob=fade_prob)
        sign = add_directional_shading(sign, prob=shading_prob)
        composed = warp_sign_onto_background(
            sign, background, base_angle_deg=base_angle_deg, oblique_prob=oblique_prob,
        )
        final = photo_degrade(composed, **degrade_kwargs)
        if aspect_squash_range is not None:
            final = squash_aspect_ratio(final, aspect_squash_range)
        if lowres_size_range is not None:
            final = simulate_low_resolution(final, lowres_size_range)
        cv2.imwrite(str(out_path), final)
        written += 1
    return written


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    manager = get_svg_manager()
    load_svg_templates(TEMPLATES_DIR, manager)
    # recursive: templates may sit in a per-sign-type subfolder (e.g.
    # templates/rychlostnik/*.svg) as well as flat under templates/
    template_keys = sorted(p.stem for p in Path(TEMPLATES_DIR).glob("**/*.svg"))
    print(f"{len(template_keys)} templates found")

    print("Loading background source frames (one pool per condition)...")
    pools = load_background_pools()
    all_conditions = list(pools.keys())

    total = 0
    for key in template_keys:
        ratio = manager.get_ratio(key)
        render_w, render_h = get_render_size(ratio)
        rendered = render_svg_template(manager, key, render_w, render_h)  # BGR

        base_angle = base_rotation_deg(ratio)
        bbox_w, bbox_h = rotated_bbox_size(render_w, render_h, base_angle)
        # square canvas for every pass, not just "square" -- CANVAS_SCALE
        # already sits inside SQUARE_CANVAS_SCALE_RANGE, so this is the same
        # margin as the real crops, applied uniformly instead of leaving
        # normal/hard/lowvis/lowres non-square. Train and inference-time
        # cropping need to agree on this from the same convention, not
        # converge on it through two different mechanisms.
        canvas_side = int(max(bbox_w, bbox_h) * CANVAS_SCALE)
        canvas_w = canvas_h = canvas_side

        out_dir = OUT_ROOT / key
        out_dir.mkdir(parents=True, exist_ok=True)

        multiplier = WEAK_TEMPLATE_MULTIPLIER.get(key, 1.0)
        variants_n = round(VARIANTS_PER_TEMPLATE * multiplier)
        hard_variants_n = round(HARD_VARIANTS_PER_TEMPLATE * multiplier)
        lowvis_variants_n = round(LOWVIS_VARIANTS_PER_TEMPLATE * multiplier)
        lowres_variants_n = round(LOWRES_VARIANTS_PER_TEMPLATE * multiplier)
        square_variants_n = round(SQUARE_VARIANTS_PER_TEMPLATE * multiplier)

        n_normal = generate_variants(
            rendered, out_dir, variants_n, pools, all_conditions, canvas_w, canvas_h,
            base_angle_deg=base_angle, oblique_prob=0.0,
        )

        # Hard pass: evening_night only + amplified noise/blur/compression --
        # additive on top of the normal pass (different filename suffix, so
        # nothing gets overwritten and both passes coexist).
        n_hard = generate_variants(
            rendered, out_dir, hard_variants_n, pools, ["evening_night"], canvas_w, canvas_h,
            base_angle_deg=base_angle,
            filename_suffix="hard",
            noise_sigma_range=(15, 40),
            blur_prob=0.98,
            blur_sigma_frac_range=(0.02, 0.05),
            jpeg_quality_range=(20, 55),
        )

        # Low-visibility pass: squashed aspect ratio + heavily reduced
        # contrast + off-color hue drift + strong blur -- additive on top of
        # the normal/hard passes.
        n_lowvis = generate_variants(
            rendered, out_dir, lowvis_variants_n, pools, all_conditions, canvas_w, canvas_h,
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

        # Low-resolution pass: simulates a genuinely small real crop (see
        # simulate_low_resolution).
        n_lowres = generate_variants(
            rendered, out_dir, lowres_variants_n, pools, all_conditions, canvas_w, canvas_h,
            base_angle_deg=base_angle,
            filename_suffix="lowres",
            lowres_size_range=(28, 90),
        )

        # tight rotated-bbox side, decoupled from CANVAS_SCALE -- the base
        # unit the square pass's own canvas scale multiplies
        base_side = max(bbox_w, bbox_h)

        # Square pass: square canvas just barely bigger than the sign's own
        # bbox -- see module docstring.
        n_square = generate_variants(
            rendered, out_dir, square_variants_n, pools, all_conditions, canvas_w, canvas_h,
            base_angle_deg=base_angle,
            filename_suffix="square",
            canvas_scale_range=SQUARE_CANVAS_SCALE_RANGE,
            base_square_side=base_side,
        )

        total += n_normal + n_hard + n_lowvis + n_lowres + n_square
        angle_note = f", base_angle={base_angle:.0f}deg" if base_angle else ""
        weak_note = f", {multiplier:.0f}x (weak class)" if multiplier != 1.0 else ""
        print(f"[{key}] {n_normal} normal + {n_hard} hard + {n_lowvis} lowvis + {n_lowres} lowres + "
              f"{n_square} square variants written{angle_note}{weak_note}")

    print(f"\nDone. Total augmented images: {total}")
    print(f"Output root: {OUT_ROOT}")


if __name__ == "__main__":
    main()
