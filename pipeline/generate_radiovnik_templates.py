"""Generate vector (SVG) templates for the `radiovnik` sign category.

Horizontal layout only (plate 760x480, pictogram + 2 side-by-side digits,
slot 147.5 x 220 at x=[200, 412.5], y=210, 50mm bottom margin) -- confirmed
against a real dimensioned reference sheet (147.5 = (760-200-200-65)/2, 65
gap, 220 slot height, 50 bottom margin all check out exactly). A vertical
mounting variant was tried and dropped -- not worth the uncertainty of an
approximately-reconstructed layout; horizontal only.

Digits are rendered as real SVG <text> using "Arial Rounded MT Bold" (a
common system font -- confirmed present and rendering correctly through
cairosvg on macOS; substitute any other rounded sans-serif font available
on your system if it isn't), NOT hand-drawn paths. Two earlier attempts at
hand-drawing the digits (blocky seven-segment, then hand-tuned bezier/arc
curves -- see digit_glyphs_rounded.py, now unused) both looked wrong
compared to the reference, which clearly shows genuinely rounded numerals
(oval "0", curved-tail "9") -- using a real font's actual glyphs sidesteps
that entirely instead of re-approximating curves by hand a third time.

The specific channel numbers in VALUES below are a representative sample,
not sourced from an authoritative real-network list -- edit this list (and
re-run this script) if an authoritative list of real values becomes
available, or to cover additional values.

Usage: python generate_radiovnik_templates.py
Output: <config.TEMPLATES_DIR>/radiovnik/radiovnik_<nn>.svg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import TEMPLATES_DIR as _TEMPLATES_ROOT

TEMPLATES_DIR = _TEMPLATES_ROOT / "radiovnik"

PICTOGRAM_D = (
    'M239.861 54.3672C293.115 43.4393 356.307 39.0672 399.141 40.9072V40.9082H399.143'
    'C482.946 44.1304 537.854 55.407 571.914 68.7324C588.944 75.3952 600.741 82.5622 608.331 89.4727'
    'C615.689 96.1718 619.056 102.592 619.47 108.053L619.5 108.579V138.887C617.636 146.395 611.675 149.048 608.466 149.5'
    'H501.251C494.335 148.15 491.158 142.392 491.158 138.949V120.53C491.158 113.551 488.204 109.067 484.488 106.325'
    'C481.027 103.771 476.929 102.741 473.997 102.558L473.427 102.532H280.838'
    'C276.102 102.532 273.081 104.279 271.254 106.515C269.444 108.729 268.842 111.38 268.842 113.162V139.816'
    'C267.445 146.868 261.484 149.5 257.845 149.5H150.539'
    'C146.497 149.5 144.012 147.747 142.52 145.573C141.009 143.373 140.5 140.715 140.5 138.948V106.751'
    'C141.267 100.804 144.484 95.2413 149.757 90.0586C155.04 84.866 162.366 80.0768 171.283 75.6943'
    'C189.117 66.9293 213.232 59.8316 239.861 54.3672Z'
)
PICTOGRAM = f'<path d="{PICTOGRAM_D}" fill="black" stroke="black"/>'

PLATE_W, PLATE_H = 760.0, 480.0
SLOT_W, SLOT_H = 147.5, 220.0
SLOT_X = [200.0, 412.5]
SLOT_Y = 210.0
FONT_FAMILY = "Arial Rounded MT Bold"
FONT_SIZE = 205
BASELINE_Y = SLOT_Y + SLOT_H - 22  # empirically fits the digit within the slot


def build_svg(number: int) -> str:
    s = f"{number:02d}"
    digits_markup = "\n".join(
        f'<text x="{SLOT_X[i] + SLOT_W / 2:.1f}" y="{BASELINE_Y:.1f}" font-family="{FONT_FAMILY}" '
        f'font-size="{FONT_SIZE}" text-anchor="middle" fill="black">{ch}</text>'
        for i, ch in enumerate(s)
    )
    return f'''<svg width="{PLATE_W:.0f}" height="{PLATE_H:.0f}" viewBox="0 0 {PLATE_W:.0f} {PLATE_H:.0f}" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="{PLATE_W:.0f}" height="{PLATE_H:.0f}" rx="10" fill="white"/>
{digits_markup}
{PICTOGRAM}
<rect x="2" y="2" width="{PLATE_W - 4:.0f}" height="{PLATE_H - 4:.0f}" rx="8" stroke="black" stroke-width="4"/>
</svg>
'''


# Representative channel numbers, not sourced from a real-network spec --
# edit to cover different/additional values.
VALUES = [1, 3, 5, 7, 9, 12, 15, 18, 22, 27, 33, 41, 45, 50, 56, 62, 68, 74, 80, 89, 90, 95, 99]


def main() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    written = []

    for v in VALUES:
        key = f"radiovnik_{v:02d}"
        (TEMPLATES_DIR / f"{key}.svg").write_text(build_svg(v))
        written.append(key)

    print(f"Wrote {len(written)} templates to {TEMPLATES_DIR}")
    for k in written:
        print(f"  {k}.svg")


if __name__ == "__main__":
    main()
