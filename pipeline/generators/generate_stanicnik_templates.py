"""Generate vector (SVG) templates for the `stanicnik` sign category.

This is a "Kilometrická poloha" (kilometer position) marker: rounded-corner
card, white or yellow main body, bold sans numeral (matches Helvetica Neue
Bold reasonably well). No accent stripes -- an earlier version added
terracotta/rust stripes top and bottom based on a misreading of the ZT-53
sheet; real reference crops don't show them, so they were removed.

Two content layouts, both present on the ZT-53 sheet:
  - split: 2-or-3-digit whole-km number stacked over a single hectometer
    digit (e.g. "264" over "6", or "24" over "0")
  - comma: a single-digit km number shown as "N,d" on one line (e.g. "2,6")
    -- used when the whole-km part is small enough to fit next to the decimal

An earlier version of this generator (built from abstract gray-block
mockups, with no real photo reference) turned out not to match reality at
all -- a classifier trained on it confused every real stanicnik crop with a
different class. This version is built directly from real reference crops
+ the ZT-53 sheet.

The specific (top, bottom) / (km, decimal) value pairs in SPLIT_EXAMPLES /
COMMA_EXAMPLES below are a representative sample, not an exhaustive list --
edit these and re-run this script to cover different or additional values.

Usage: python generate_stanicnik_templates.py
Output: <config.TEMPLATES_DIR>/stanicnik/stanicnik_<split|comma>_<...>[_yellow].svg
"""
from ..core.config import TEMPLATES_DIR as _TEMPLATES_ROOT

TEMPLATES_DIR = _TEMPLATES_ROOT / "stanicnik"

# Proportions eyeballed from the reference crops + ZT-53 sheet -- not exact
# measurements, adjust if precise dimensions turn up.
DIGIT_COL_W = 90.0
CARD_H = 350.0
SIDE_MARGIN = 15.0
FONT_FAMILY = "Helvetica Neue"
FONT_SIZE = 140
CORNER_R = 18

TOP_ROW_Y = 172.0     # baseline y of the top (split mode) number
BOTTOM_ROW_Y = 292.0  # baseline y of the bottom (split mode) digit

# comma mode ("N,d" on one line) is its own landscape plate, not the same
# shape as the split mode's stacked plate -- confirmed against a real
# dimensioned reference sheet: wide rounded-corner card, small manufacturing
# codes top-left/bottom-right (not reproduced, not part of what the
# classifier needs to read)
COMMA_CARD_W = 460.0
COMMA_CARD_H = 320.0
# digits measured directly off a reference dimensioned sheet (pixel bbox of
# the "2,6" glyph vs. the plate's own bbox) -- digit cap-height is ~57% of
# plate height, much larger than FONT_SIZE=140 (~31%) was giving here
FONT_SIZE_COMMA = 255
COMMA_ROW_Y = 252.0   # baseline y of the single-line "N,d" text


def _body_and_frame(plate_w: float, plate_h: float, fill: str) -> tuple[str, str]:
    body = f'<rect width="{plate_w:.0f}" height="{plate_h:.0f}" rx="{CORNER_R}" fill="{fill}"/>'
    frame = f'<rect width="{plate_w:.0f}" height="{plate_h:.0f}" rx="{CORNER_R}" fill="none" stroke="black" stroke-width="4"/>'
    return body, frame


def build_svg_split(top_digits: str, bottom_digit: str, is_yellow: bool = False) -> str:
    n = len(top_digits)
    plate_w = 2 * SIDE_MARGIN + n * DIGIT_COL_W
    cx = plate_w / 2
    fill = "#F4C542" if is_yellow else "#F7F6F2"
    body, frame = _body_and_frame(plate_w, CARD_H, fill)
    return f'''<svg width="{plate_w:.0f}" height="{CARD_H:.0f}" viewBox="0 0 {plate_w:.0f} {CARD_H:.0f}" xmlns="http://www.w3.org/2000/svg">
{body}
{frame}
<text x="{cx:.1f}" y="{TOP_ROW_Y:.1f}" font-family="{FONT_FAMILY}" font-weight="bold" font-size="{FONT_SIZE}" text-anchor="middle" fill="black">{top_digits}</text>
<text x="{cx:.1f}" y="{BOTTOM_ROW_Y:.1f}" font-family="{FONT_FAMILY}" font-weight="bold" font-size="{FONT_SIZE}" text-anchor="middle" fill="black">{bottom_digit}</text>
</svg>
'''


def build_svg_comma(km_digit: str, decimal_digit: str, is_yellow: bool = False) -> str:
    cx = COMMA_CARD_W / 2
    fill = "#F4C542" if is_yellow else "#F7F6F2"
    body, frame = _body_and_frame(COMMA_CARD_W, COMMA_CARD_H, fill)
    return f'''<svg width="{COMMA_CARD_W:.0f}" height="{COMMA_CARD_H:.0f}" viewBox="0 0 {COMMA_CARD_W:.0f} {COMMA_CARD_H:.0f}" xmlns="http://www.w3.org/2000/svg">
{body}
{frame}
<text x="{cx:.1f}" y="{COMMA_ROW_Y:.1f}" font-family="{FONT_FAMILY}" font-weight="bold" font-size="{FONT_SIZE_COMMA}" text-anchor="middle" fill="black">{km_digit},{decimal_digit}</text>
</svg>
'''


# (top, bottom) -- top is 2 or 3 digits, bottom always 1 digit. Edit to
# change which specific values get a static template.
SPLIT_EXAMPLES = [
    ("388", "5"), ("386", "1"), ("346", "2"), ("349", "7"), ("341", "0"),
    ("387", "1"), ("344", "6"), ("347", "2"), ("396", "1"), ("350", "6"),
    ("65", "8"), ("12", "3"), ("47", "9"), ("90", "4"), ("23", "0"),
]
# (km digit, decimal digit) -- single-line "N,d" form. Edit to change which
# specific values get a static template.
COMMA_EXAMPLES = [("2", "6"), ("1", "0"), ("3", "4"), ("5", "9"), ("0", "2"), ("7", "8")]


def main() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for top, bottom in SPLIT_EXAMPLES:
        for yellow in (False, True):
            key = f"stanicnik_split_{top}_{bottom}" + ("_yellow" if yellow else "")
            (TEMPLATES_DIR / f"{key}.svg").write_text(build_svg_split(top, bottom, yellow))
            written.append(key)

    for km, dec in COMMA_EXAMPLES:
        for yellow in (False, True):
            key = f"stanicnik_comma_{km}_{dec}" + ("_yellow" if yellow else "")
            (TEMPLATES_DIR / f"{key}.svg").write_text(build_svg_comma(km, dec, yellow))
            written.append(key)

    print(f"Wrote {len(written)} templates to {TEMPLATES_DIR}")
    for k in written:
        print(f"  {k}.svg")


if __name__ == "__main__":
    main()
