"""Generate vector (SVG) templates for the `sklonovnik` sign category.

Unlike rychlostnik/stanicnik, this doesn't design new geometry from scratch --
it reuses an existing hand-authored plate/triangle/digit-slot layout (a
black square plate, a white triangle pointing up for "increase" / down for
"decrease", a 4-digit slot region for first_number, and a 2-digit slot
region in RED inside the triangle for second_number), rendering real digit
strokes at those same coordinates via the procedural digit-glyph engine in
digit_glyphs.py.

first_number is the gradient marker's main (4-digit) value, black, outside
the triangle. second_number is a 2-digit value in red inside the triangle
(presumably the slope/gradient value itself) -- confirmed genuinely
optional on real signs (some real crops show only first_number, no second
number at all), so build_svg accepts None for it.

The specific (direction, first_number, second_number) combinations in
COMBOS/SINGLE_COMBOS below are a representative sample (digit-count-
consistent examples, not sourced from a real-network spec) -- edit these
and re-run this script to cover different or additional values.

Usage: python generate_sklonovnik_templates.py
Output: <config.TEMPLATES_DIR>/sklonovnik/sklonovnik_<increase|decrease>_<first>_<second>.svg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import TEMPLATES_DIR as _TEMPLATES_ROOT
from digit_glyphs import digit_paths, make_digit_chains

TEMPLATES_DIR = _TEMPLATES_ROOT / "sklonovnik"

# --- fixed geometry, taken verbatim from an existing hand-authored
# reference SVG -----------------------------------------------------------
PLATE = '<rect width="450" height="500" transform="matrix(-1 0 0 -1 450 500)" fill="white"/>\n' \
        '<rect width="450" height="500" transform="matrix(-1 0 0 -1 450 500)" fill="black"/>'

# first_number slot: 4 digits, each occupying a 57 x 90 box, 15 gap
FIRST_SLOT_W, FIRST_SLOT_H, FIRST_SLOT_GAP = 57.0, 90.0, 15.0
FIRST_SLOT_X0 = 88.5
FIRST_STROKE_T = 12.0

# second_number slot: 2 digits, each 56.5 x 120, in red, inside the triangle
SECOND_SLOT_W, SECOND_SLOT_H, SECOND_SLOT_GAP = 56.5, 120.0, 19.5
SECOND_SLOT_X0 = 159.0
SECOND_STROKE_T = 16.0

VARIANTS = {
    "increase": {
        "triangle": '<path d="M25 285H425L225 25L25 285Z" fill="white"/>',
        "white_bg_rect": '<rect width="400" height="190" transform="translate(25 285)" fill="white"/>',
        "first_y": 335.0,
        "second_y": 165.0,
    },
    "decrease": {
        "triangle": '<path d="M425 215L25 215L225 475L425 215Z" fill="white"/>',
        "white_bg_rect": '<rect width="400" height="190" transform="translate(25 25)" fill="white"/>',
        "first_y": 75.0,
        "second_y": 215.0,
    },
}

FIRST_CHAINS = make_digit_chains(FIRST_SLOT_W, FIRST_SLOT_H, FIRST_STROKE_T)
SECOND_CHAINS = make_digit_chains(SECOND_SLOT_W, SECOND_SLOT_H, SECOND_STROKE_T)


def build_svg(direction: str, first_number: int, second_number: int | None) -> str:
    v = VARIANTS[direction]
    first_s = f"{first_number:04d}"

    first_paths = []
    dy_first = v["first_y"] + FIRST_SLOT_H
    for i, ch in enumerate(first_s):
        dx = FIRST_SLOT_X0 + i * (FIRST_SLOT_W + FIRST_SLOT_GAP)
        first_paths.extend(digit_paths(FIRST_CHAINS, ch, dx, dy_first))

    first_strokes = "\n".join(
        f'<path d="{d}" fill="none" stroke="black" stroke-width="{FIRST_STROKE_T:.0f}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        for d in first_paths
    )

    second_strokes = ""
    if second_number is not None:
        second_s = f"{second_number:02d}"
        second_paths = []
        dy_second = v["second_y"] + SECOND_SLOT_H
        for i, ch in enumerate(second_s):
            dx = SECOND_SLOT_X0 + i * (SECOND_SLOT_W + SECOND_SLOT_GAP)
            second_paths.extend(digit_paths(SECOND_CHAINS, ch, dx, dy_second))
        second_strokes = "\n".join(
            f'<path d="{d}" fill="none" stroke="#FF0000" stroke-width="{SECOND_STROKE_T:.0f}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            for d in second_paths
        )

    return f'''<svg width="450" height="500" viewBox="0 0 450 500" fill="none" xmlns="http://www.w3.org/2000/svg">
{PLATE}
{v["white_bg_rect"]}
{first_strokes}
{v["triangle"]}
{second_strokes}
</svg>
'''


# (first_number, second_number) -- e.g. (position marker, gradient value).
# Edit to change which specific values get a static template.
COMBOS = [
    (1250, 12), (2005, 8), (3140, 25), (450, 6),
    (1875, 18), (2630, 3), (990, 15), (3305, 22),
]
# first_number-only examples -- second_number omitted entirely, a confirmed
# real variant (see build_svg's docstring note). Edit to change which
# specific values get a static template.
SINGLE_COMBOS = [1600, 1200, 800, 2450]


def main() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for direction in ("increase", "decrease"):
        for first, second in COMBOS:
            key = f"sklonovnik_{direction}_{first}_{second}"
            (TEMPLATES_DIR / f"{key}.svg").write_text(build_svg(direction, first, second))
            written.append(key)
        for first in SINGLE_COMBOS:
            key = f"sklonovnik_{direction}_{first}_single"
            (TEMPLATES_DIR / f"{key}.svg").write_text(build_svg(direction, first, None))
            written.append(key)

    print(f"Wrote {len(written)} templates to {TEMPLATES_DIR}")
    for k in written:
        print(f"  {k}.svg")


if __name__ == "__main__":
    main()
