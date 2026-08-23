"""Rounded/oval digit font -- originally built for radiovnik, on the theory
that its real reference showed proper rounded numerals (a true oval "0", a
"9" with a round bowl and curved tail) rather than the blocky seven-segment
DIGIT_CHAINS in digit_glyphs.py.

NOT CURRENTLY USED: generate_radiovnik_templates.py ended up rendering
digits as real SVG <text> (a system font) instead of hand-drawn paths, since
that matched the reference better than either hand-drawn attempt (blocky or
rounded). Nothing in this project currently imports this module. Kept for
reference / in case a future sign category needs hand-drawn rounded digits
and a real font isn't a viable option for it.
"""

import math


def arc_points(cx: float, cy: float, rx: float, ry: float, start_deg: float, end_deg: float, n: int = 20):
    pts = []
    for i in range(n + 1):
        t = math.radians(start_deg + (end_deg - start_deg) * i / n)
        pts.append((cx + rx * math.cos(t), cy + ry * math.sin(t)))
    return pts


def make_round_digit_chains(w: float, h: float, t: float) -> dict[str, list[list[tuple[float, float]]]]:
    cx = w / 2
    rx = (w - t) / 2
    # two-bowl digits (8) and single-bowl digits (0) use the full height;
    # 6/9's bowl occupies roughly the top/bottom 58% of the height
    ry_full = (h - t) / 2
    cy_full = h / 2

    bowl_ry = h * 0.30
    bowl_h_center_top = h - t / 2 - bowl_ry       # 9's bowl center (near top)
    bowl_h_center_bot = t / 2 + bowl_ry           # 6's bowl center (near bottom)

    x0, x1 = t / 2, w - t / 2
    y0, y1 = t / 2, h - t / 2
    ym = h / 2

    chains: dict[str, list[list[tuple[float, float]]]] = {}

    # 0: full oval
    chains["0"] = [arc_points(cx, cy_full, rx, ry_full, 90, 90 - 360)]

    # 1: simple vertical stroke
    chains["1"] = [[(cx, y0), (cx, y1)]]

    # 2: top arc (open bottom-left) sweeping into a diagonal down to a flat
    # bottom bar
    top2 = arc_points(cx, y1 - h * 0.16, rx, h * 0.16, 160, -20, n=14)
    chains["2"] = [top2 + [(x0, y0), (x1, y0)]]

    # 3: two stacked right-opening arcs (open to the left), joined at the
    # waist
    arc3_top = arc_points(cx - w * 0.06, y1 - h * 0.22, rx * 0.9, h * 0.22, 120, -120, n=14)
    arc3_bot = arc_points(cx - w * 0.06, y0 + h * 0.22, rx * 0.9, h * 0.22, 120, -120, n=14)
    chains["3"] = [arc3_top, arc3_bot]

    # 4: straight (fine as a geometric shape even in a rounded font)
    chains["4"] = [[(x0, y1), (x0, ym), (x1, ym)], [(x1, y1), (x1, y0)]]

    # 5: flat top bar + short left vertical + bottom arc (opens up-left)
    bottom5 = arc_points(cx, y0 + h * 0.16, rx, h * 0.16, 160, -140, n=14)
    chains["5"] = [[(x1, y1), (x0, y1), (x0, ym)] + bottom5]

    # 6: tail from top curving down the left side into a bowl near the
    # bottom -- (x0, ym) keeps the descent following the left edge; bowl6's
    # own first point is already close to it, so the join stays smooth
    bowl6 = arc_points(cx, bowl_h_center_bot, rx, bowl_ry, 200, 200 - 340, n=20)
    chains["6"] = [[(x1, y1), (x0, ym)] + bowl6]

    # 7: straight
    chains["7"] = [[(x0, y1), (x1, y1), (x1, y0)]]

    # 8: two stacked ovals
    chains["8"] = [
        arc_points(cx, y1 - h * 0.24, rx, h * 0.24, 90, 90 - 360, n=18),
        arc_points(cx, y0 + h * 0.24, rx, h * 0.24, 90, 90 - 360, n=18),
    ]

    # 9: round bowl near the top, tail curving down and slightly left at the
    # bottom -- the tail is a plain 3-point polyline starting exactly at the
    # bowl's own last point (not an independently-parameterized arc), since
    # an arc with its own separately-guessed center/radius didn't line up
    # with the bowl and produced a stray loop/jump instead of a clean tail
    bowl9 = arc_points(cx, bowl_h_center_top, rx, bowl_ry, 340, 340 - 340, n=20)
    tail_start = bowl9[-1]
    chains["9"] = [bowl9, [tail_start, (x1, h * 0.30), (cx * 0.55, y0)]]

    return chains


def digit_paths(chains, digit: str, dx: float, dy_baseline: float) -> list[str]:
    """Same convention as _digit_glyphs.digit_paths: dy_baseline is the SVG
    y-coordinate of the digit's own bottom edge; font y grows up, SVG y
    grows down.
    """
    paths = []
    for chain in chains[digit]:
        x0, y0 = chain[0]
        cmds = [f"M {dx + x0:.1f} {dy_baseline - y0:.1f}"] + \
            [f"L {dx + x:.1f} {dy_baseline - y:.1f}" for x, y in chain[1:]]
        paths.append(" ".join(cmds))
    return paths
