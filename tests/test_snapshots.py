from pathlib import Path

import pytest

# These paths are treated as relative to this file.
APPS_DIR = Path("../src/textual_paint")
PAINT = APPS_DIR / "paint.py"
GALLERY = APPS_DIR / "gallery.py"

def test_paint_app(snap_compare):
    assert snap_compare(PAINT)

def test_paint_stretch_skew(snap_compare):
    assert snap_compare(PAINT, press=["ctrl+w"])

def test_gallery_app(snap_compare):
    assert snap_compare(GALLERY)

