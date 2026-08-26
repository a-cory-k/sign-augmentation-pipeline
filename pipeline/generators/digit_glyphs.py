"""Shared procedural digit-glyph engine used by the various
generate_<sign>_templates.py scripts under scripts/ (rychlostnik, stanicnik,
...). Not a standalone tool -- import `make_digit_chains` + `digit_paths`.

Digits are seven-segment-style stroke chains inside a `digit_w` x `digit_h`
unit box (y=0 at bottom, y=digit_h at top), rendered as thick round-capped/
round-joined SVG strokes (cairosvg/Cairo rounds corners natively via
stroke-linejoin, no manual corner math needed). This is a font approximation,
not a traced/certified reproduction of any specific standard's true numeral
curves -- re-derive per-sign proportions from real measurements if exact
conformance to a standard ever matters.
"""


def make_digit_chains(digit_w: float, digit_h: float, stroke_t: float) -> dict[str, list[list[tuple[float, float]]]]:
    xL, xR = stroke_t / 2, digit_w - stroke_t / 2
    yB, yT, yM = stroke_t / 2, digit_h - stroke_t / 2, digit_h / 2
    TLt, TRt = (xL, yT), (xR, yT)
    TLm, TRm = (xL, yM), (xR, yM)
    BLb, BRb = (xL, yB), (xR, yB)
    cx = digit_w / 2

    return {
        "0": [[TLt, TRt, TRm, BRb, BLb, TLm, TLt]],
        "1": [[(cx, yB), (cx, yT)]],
        "2": [[TLt, TRt, TRm, TLm, BLb, BRb]],
        "3": [[TLt, TRt, TRm, BRb, BLb], [TRm, TLm]],
        "4": [[TLt, TLm, TRm, TRt], [TRm, BRb]],
        "5": [[TRt, TLt, TLm, TRm, BRb, BLb]],
        "6": [[TRt, TLt, TLm, BLb, BRb, TRm, TLm]],
        "7": [[TLt, TRt, TRm, BRb]],
        "8": [[TLt, TRt, TRm, TLm, TLt], [TRm, BRb, BLb, TLm]],
        "9": [[TLm, TLt, TRt, TRm, BRb, BLb], [TLm, TRm]],
    }


def digit_paths(
    chains: dict[str, list[list[tuple[float, float]]]],
    digit: str,
    dx: float,
    dy_baseline: float,
) -> list[str]:
    """SVG path 'd' strings for one glyph's chains, x offset by dx, with
    dy_baseline = the SVG y-coordinate of the digit's own bottom edge (font
    y=0). Font y grows upward but SVG y grows downward, so each point's y
    must be *subtracted* from dy_baseline, not added -- adding it renders
    every glyph upside down (verified: that bug made "2" and "5" swap into
    looking like each other, since flipping a seven-segment digit vertically
    silently produces a different valid digit's topology, not an obviously
    broken shape).
    """
    paths = []
    for chain in chains[digit]:
        x0, y0 = chain[0]
        cmds = [f"M {dx + x0:.1f} {dy_baseline - y0:.1f}"] + \
            [f"L {dx + x:.1f} {dy_baseline - y:.1f}" for x, y in chain[1:]]
        paths.append(" ".join(cmds))
    return paths
