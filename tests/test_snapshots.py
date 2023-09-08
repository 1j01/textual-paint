from pathlib import Path

import pytest

# These paths are treated as relative to this file.
APPS_DIR = Path("../src/textual_paint")
PAINT = APPS_DIR / "paint.py"
GALLERY = APPS_DIR / "gallery.py"

LARGER = (81, 38)
"""Large enough to show the entire paint app."""


@pytest.fixture(params=[
    {"theme": "light", "ascii_only": False},
    {"theme": "dark", "ascii_only": False},
    {"theme": "light", "ascii_only": True},
    {"theme": "dark", "ascii_only": True},
], ids=lambda param: f"{param['theme']}_{'ascii' if param['ascii_only'] else 'unicode'}")
def each_theme(request):
    """Fixture to set the PYTEST_TEXTUAL_PAINT_ARGS environment variable."""
    theme = request.param.get("theme")
    ascii_only = request.param.get("ascii_only")
    # os.environ["PYTEST_TEXTUAL_PAINT_ARGS"] = f"--theme {theme}" + (" --ascii-only" if ascii_only else "")
    from textual_paint.args import args
    args.theme = theme
    args.ascii_only = ascii_only
    yield
    # del os.environ["PYTEST_TEXTUAL_PAINT_ARGS"]
    args.theme = "light"
    args.ascii_only = False


def test_paint_app(snap_compare, each_theme):
    assert snap_compare(PAINT, terminal_size=LARGER)

def test_paint_stretch_skew_dialog(snap_compare, each_theme):
    assert snap_compare(PAINT, press=["ctrl+w"])

def test_paint_flip_rotate_dialog(snap_compare, each_theme):
    assert snap_compare(PAINT, press=["ctrl+r"])

def test_paint_image_attributes_dialog(snap_compare, each_theme):
    assert snap_compare(PAINT, press=["ctrl+e"])

def test_paint_open_dialog(snap_compare, each_theme):
    assert snap_compare(PAINT, press=["ctrl+o"], terminal_size=LARGER)

def test_paint_save_dialog(snap_compare, each_theme):
    assert snap_compare(PAINT, press=["ctrl+s"], terminal_size=LARGER)

def test_paint_help_dialog(snap_compare, each_theme):
    assert snap_compare(PAINT, press=["f1"], terminal_size=LARGER)

def test_paint_view_bitmap(snap_compare):
    assert snap_compare(PAINT, press=["ctrl+f"])

def test_paint_invert_and_exit(snap_compare, each_theme):
    assert snap_compare(PAINT, press=["ctrl+i", "ctrl+q"])

def test_gallery_app(snap_compare):
    assert snap_compare(GALLERY)

