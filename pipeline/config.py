"""Central, portable configuration for the sign-augmentation pipeline.

Every path used anywhere in this project is defined here, and every one of
them can be overridden with an environment variable. If left unset, each
defaults to a folder inside this project, so a fresh clone works
immediately -- against the bundled `templates/`, writing output inside the
project -- with no device-specific setup at all.

Environment variables:
  SIGN_TEMPLATES_DIR
      Where SVG sign templates are read from (by augment_templates.py) and
      written to (by the generate_*_templates.py scripts).
      Default: <project root>/templates

  SIGN_BACKGROUND_DIR
      Where real background photographs live, one subfolder per lighting/
      weather condition (good_light/, dawn_fog_gloom/, evening_night/,
      rain/ -- see background_loader.py for the exact expected layout).
      Default: <project root>/background_footage

  SIGN_AUGMENTED_OUTPUT_DIR
      Where generated training images are written, one subfolder per
      template key.
      Default: <project root>/output/augmented_templates

To point the pipeline at data that lives somewhere else entirely (a shared
drive, a different disk), just export the relevant variable before running
any script, e.g.:

    export SIGN_BACKGROUND_DIR=/mnt/shared/rail_footage
    python augment_templates.py
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # this file lives in pipeline/, one level below the project root

TEMPLATES_DIR = Path(os.environ.get("SIGN_TEMPLATES_DIR", PROJECT_ROOT / "templates"))
BACKGROUND_DIR = Path(os.environ.get("SIGN_BACKGROUND_DIR", PROJECT_ROOT / "background_footage"))
OUTPUT_DIR = Path(os.environ.get("SIGN_AUGMENTED_OUTPUT_DIR", PROJECT_ROOT / "output" / "augmented_templates"))
