"""Generate vector (SVG) templates for the `rychlostnik` sign category.

Reconstructs the ZT-4a "Rychlostník" standard sheet (railway speed-restriction
board): rounded-corner white plate, side/top-bottom margins and inter-digit
gap taken from the ZT-4a/ZT-60 sheets (in the sheets' own mm units, kept here
purely as relative proportions -- this generator doesn't target exact
mm-for-mm reproduction, see below).

Digits are rendered as real font text (Helvetica Neue Bold, matching
generate_stanicnik_templates.py's approach), NOT hand-drawn stroke paths.
An earlier version drew digits as seven-segment-style stroke chains (a
blocky, calculator-display digit shape, including a plain rectangle outline
for "0") -- checked against real photographed rychlostnik crops across
several independent sources, which consistently show an ordinary
sans-serif print numeral font (rounded "0", curved "3"/"6"/"8"/"9"), nothing
resembling a seven-segment digit. Training a classifier on the
seven-segment shapes taught it a digit font that doesn't exist on the real
signs, and it ended up systematically confusing this class with another
numeric class whose digits WERE rendered in a real font. Real system-font
glyphs sidestep that failure mode entirely.

Rychlostnik values are usually 3 digits but real crops confirm 2-digit
values happen too (e.g. "65", "50" as a single-line value) -- both digit
counts are covered, single-line (`first_number` only) OR stacked two-line
(`first_number` over `second_number`, e.g. tilting-train speed over normal
speed, per the ZT-4a/ZT-60 sheets' Obr.2 double-line variant), including a
2-digit-over-2-digit stacked pair, not just 3-over-3.

The specific values in VALUES/DOUBLE_PAIRS below are a curated,
representative sample of real Czech rail speed-board values, not an
exhaustive list -- edit these lists (and re-run this script) to cover
different or additional values; every downstream stage picks up the new
templates automatically.

Usage: python generate_rychlostnik_templates.py
Output: <config.TEMPLATES_DIR>/rychlostnik/rychlostnik_<n>.svg (single-line)
        <config.TEMPLATES_DIR>/rychlostnik/rychlostnik_<a>_<b>.svg (stacked two-line)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import TEMPLATES_DIR as _TEMPLATES_ROOT

TEMPLATES_DIR = _TEMPLATES_ROOT / "rychlostnik"

# Proportions carried over from the ZT-4a/ZT-60-derived layout (relative
# scale only, not mm-exact -- see module docstring). FONT_SIZE/DIGIT_COL_W
# use the same ratio generate_stanicnik_templates.py's font already
# validated (DIGIT_COL_W = FONT_SIZE * ~0.643) rather than re-deriving font
# metrics from scratch.
DIGIT_H = 392.0
SIDE_MARGIN = 72.0
TOP_BOTTOM_MARGIN = 54.0
ROW_GAP = 108.0
PLATE_CORNER_R = 32.0

FONT_FAMILY = "Helvetica Neue"
FONT_SIZE = 460.0          # cap-height of Helvetica Neue Bold digits ~= 0.85 * font-size
DIGIT_COL_W = FONT_SIZE * 0.643


def _row_width(n_digits: int) -> float:
    return n_digits * DIGIT_COL_W


def _text_row(s: str, cx: float, baseline_y: float) -> str:
    return (f'<text x="{cx:.1f}" y="{baseline_y:.1f}" font-family="{FONT_FAMILY}" '
            f'font-weight="bold" font-size="{FONT_SIZE:.0f}" text-anchor="middle" '
            f'fill="black">{s}</text>')


def _wrap_svg(plate_w: float, plate_h: float, text_elems: list[str]) -> str:
    texts = "\n".join(text_elems)
    return f'''<svg width="{plate_w:.0f}" height="{plate_h:.0f}" viewBox="0 0 {plate_w:.0f} {plate_h:.0f}" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="2" y="2" width="{plate_w - 4:.0f}" height="{plate_h - 4:.0f}" rx="{PLATE_CORNER_R:.0f}" fill="white" stroke="black" stroke-width="4"/>
{texts}
</svg>
'''


def build_svg(number: int) -> str:
    """Single-line -- natural digit count (2 or 3 digits, both confirmed
    real), no forced zero-padding."""
    s = str(number)
    plate_w = 2 * SIDE_MARGIN + _row_width(len(s))
    plate_h = 2 * TOP_BOTTOM_MARGIN + DIGIT_H
    cx = plate_w / 2
    baseline_y = plate_h - TOP_BOTTOM_MARGIN
    return _wrap_svg(plate_w, plate_h, [_text_row(s, cx, baseline_y)])


def build_svg_double(top_number: int, bottom_number: int) -> str:
    """Stacked two-line -- first_number over second_number, each independently
    2 or 3 digits (natural length, no zero-padding); the plate width follows
    the wider of the two rows, both rows centered on the plate."""
    top_s, bottom_s = str(top_number), str(bottom_number)
    n_digits = max(len(top_s), len(bottom_s))
    plate_w = 2 * SIDE_MARGIN + _row_width(n_digits)
    plate_h = 2 * TOP_BOTTOM_MARGIN + 2 * DIGIT_H + ROW_GAP
    cx = plate_w / 2

    top_baseline = TOP_BOTTOM_MARGIN + DIGIT_H
    bottom_baseline = plate_h - TOP_BOTTOM_MARGIN
    return _wrap_svg(plate_w, plate_h, [
        _text_row(top_s, cx, top_baseline),
        _text_row(bottom_s, cx, bottom_baseline),
    ])


# Curated, representative real speed-board values -- mostly 3-digit, but
# 2-digit values (e.g. 65, 50) confirmed present in real crops too. Edit this
# list to change which specific values get a static template.
VALUES = list(range(100, 161, 5)) + [40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95]

# (top=tilting-train speed, bottom=normal speed) -- top usually 10-30 km/h
# above bottom, per real ZT-4a two-line boards (Obr.2). Both 3-over-3 and
# 2-over-2 confirmed real. Edit this list to change which pairs get a
# static template.
DOUBLE_PAIRS = [
    (110, 100), (120, 100), (130, 110), (140, 120), (150, 130), (160, 140),
    (60, 40), (70, 50), (80, 60), (85, 75), (90, 80), (95, 85),
]


def main() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    written = []

    for v in VALUES:
        key = f"rychlostnik_{v}"
        (TEMPLATES_DIR / f"{key}.svg").write_text(build_svg(v))
        written.append(key)

    for top, bottom in DOUBLE_PAIRS:
        key = f"rychlostnik_{top}_{bottom}"
        (TEMPLATES_DIR / f"{key}.svg").write_text(build_svg_double(top, bottom))
        written.append(key)

    print(f"Wrote {len(written)} templates to {TEMPLATES_DIR}")
    for k in written:
        print(f"  {k}.svg")


if __name__ == "__main__":
    main()
