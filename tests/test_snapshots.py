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

def test_paint_flip_rotate_dialog(snap_compare):
    assert snap_compare(PAINT, press=["ctrl+r"])

def test_paint_image_attributes_dialog(snap_compare):
    assert snap_compare(PAINT, press=["ctrl+e"])

def test_paint_open_dialog(snap_compare):
    assert snap_compare(PAINT, press=["ctrl+o"])

def test_paint_save_dialog(snap_compare):
    assert snap_compare(PAINT, press=["ctrl+s"])

def test_paint_help_dialog(snap_compare):
    assert snap_compare(PAINT, press=["f1"])

def test_paint_view_bitmap(snap_compare):
    assert snap_compare(PAINT, press=["ctrl+f"])

def test_paint_invert_and_exit(snap_compare):
    assert snap_compare(PAINT, press=["ctrl+i", "ctrl+q"])

def test_gallery_app(snap_compare):
    assert snap_compare(GALLERY)

