"""Portable SVG template loader/renderer.

Loads every .svg file under a directory (recursively) into memory, keyed by
filename stem, and renders any of them to a BGR numpy array (OpenCV's native
channel order) via cairosvg.

This is a minimal, dependency-free replacement for the SvgManager class this
pipeline originally used (from the parent sodik repo's polygon_recognition
package) -- that version pulled in the project's full detection/annotation
codebase for no benefit here, since all this pipeline actually needs is
"parse an SVG, know its aspect ratio, rasterize it to a bitmap."

Requires the system cairo library (via the cairosvg/cairocffi Python
packages). On macOS with Homebrew, cairo is usually not on the default
dynamic-library search path -- if you see an import error mentioning
"cairo"/"libcairo", run:

    export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"   # Apple Silicon
    export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"      # Intel Mac

before running any script. On Linux, installing your distro's `cairo`
package (e.g. `apt install libcairo2`) is normally sufficient with no
environment variable needed.
"""
import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import cairosvg
import cv2
import numpy as np
from PIL import Image as PILImage


class SvgManager:
    """In-memory cache of parsed SVG files and their aspect ratios."""

    def __init__(self) -> None:
        self._svgs: dict[str, ET.ElementTree] = {}
        self._ratios: dict[str, float] = {}

    def load_svg(self, path: str, key: Optional[str] = None) -> ET.ElementTree:
        resolved = Path(path).resolve()
        if key is None:
            key = resolved.stem
        if key in self._svgs:
            return self._svgs[key]
        tree = ET.parse(str(resolved))
        self._svgs[key] = tree
        self._ratios[key] = self._extract_ratio(tree)
        return tree

    @staticmethod
    def _extract_ratio(tree: ET.ElementTree) -> float:
        """width / height, preferring the root <svg> width/height attributes,
        falling back to the viewBox, falling back to 1.0 (square)."""
        root = tree.getroot()

        def _parse_unit(value: str) -> Optional[float]:
            m = re.match(r"^([0-9]*\.?[0-9]+)", value.strip())
            return float(m.group(1)) if m else None

        w, h = root.get("width"), root.get("height")
        if w and h:
            pw, ph = _parse_unit(w), _parse_unit(h)
            if pw and ph and ph > 0:
                return pw / ph

        vb = root.get("viewBox")
        if vb:
            parts = vb.strip().replace(",", " ").split()
            if len(parts) == 4:
                try:
                    vw, vh = float(parts[2]), float(parts[3])
                    if vh > 0:
                        return vw / vh
                except ValueError:
                    pass

        return 1.0

    def get_ratio(self, key: str, default: float = 1.0) -> float:
        return self._ratios.get(key, default)

    def get_svg(self, key: str) -> Optional[ET.ElementTree]:
        return self._svgs.get(key)


def get_svg_manager() -> SvgManager:
    """Returns a fresh manager. Unlike the original this was ported from,
    this is intentionally NOT a process-wide singleton -- a standalone
    script has no need to share one global instance across modules, and a
    plain instance is easier to reason about."""
    return SvgManager()


def load_svg_templates(templates_dir, manager: SvgManager) -> SvgManager:
    """Loads every .svg file under templates_dir (recursively -- templates
    may sit in a per-class subfolder, e.g. templates/rychlostnik/*.svg, or
    flat directly under templates_dir) into `manager`, keyed by filename
    stem."""
    templates_path = Path(templates_dir)
    if not templates_path.exists():
        raise FileNotFoundError(f"SVG templates directory not found: {templates_path}")
    for svg_path in sorted(templates_path.glob("**/*.svg")):
        manager.load_svg(str(svg_path), key=svg_path.stem)
    return manager


def render_svg_template(manager: SvgManager, svg_key: str, width: int, height: int) -> np.ndarray:
    """Rasterizes a previously loaded template to a `height x width x 3`
    BGR array, stretched to exactly (width, height) regardless of its own
    aspect ratio (the caller is expected to have already picked (width,
    height) to match the template's real aspect ratio if that matters --
    see get_render_size in augment_templates.py)."""
    tree = manager.get_svg(svg_key)
    if tree is None:
        raise KeyError(f"SVG template not loaded: {svg_key}")

    root = ET.fromstring(ET.tostring(tree.getroot(), encoding="unicode"))
    root.set("preserveAspectRatio", "none")
    svg_bytes = cairosvg.svg2png(
        bytestring=ET.tostring(root, encoding="unicode").encode(),
        output_width=width,
        output_height=height,
    )
    rgb = np.array(PILImage.open(io.BytesIO(svg_bytes)).convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def render_svg_string(svg_str: str, width: int, height: int) -> np.ndarray:
    """Same as render_svg_template, but for an SVG that was generated
    on-the-fly as a string rather than loaded from a file -- used by
    augment_number_templates.py, whose whole point is that its SVG content
    is never written to disk as a template."""
    png_bytes = cairosvg.svg2png(bytestring=svg_str.encode(), output_width=width, output_height=height)
    im = PILImage.open(io.BytesIO(png_bytes)).convert("RGB")
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
