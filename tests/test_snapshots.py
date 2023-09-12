from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Awaitable, Callable, Iterable, Protocol

import pytest
from textual.geometry import Offset
from textual.pilot import Pilot
from textual.widgets import Input

from tests.pilot_helpers import click_by_attr, click_by_index, drag

if TYPE_CHECKING:
    # When tests are run, paint.py is re-evaluated,
    # leading to a different class of the same name at runtime.
    from textual_paint.paint import PaintApp


class SnapCompareType(Protocol):
    """Type of the function returned by the snap_compare fixture."""
    def __call__(
        self,
        app_path: str | PurePath,
        press: Iterable[str] = (),
        terminal_size: tuple[int, int] = (80, 24),
        run_before: Callable[[Pilot], Awaitable[None] | None] | None = None,  # type: ignore
    ) -> bool:
        ...

# These paths are treated as relative to this file.
APPS_DIR = Path("../src/textual_paint")
PAINT = APPS_DIR / "paint.py"
GALLERY = APPS_DIR / "gallery.py"

LARGER = (81, 38)
"""Large enough to show the Textual Paint app's main UI and most dialogs comfortably."""
LARGEST = (107, 42)
"""Large enough to show the Edit Colors dialog, which is a bit oversized."""

# Prevent flaky tests due to timing issues.
Input.cursor_blink = False  # type: ignore
# paint.DOUBLE_CLICK_TIME = 20.0  # seconds; ridiculously high; probably ineffective since paint.py is re-evaluated for each test

@pytest.fixture(params=[
    {"theme": "light", "ascii_only": False},
    {"theme": "dark", "ascii_only": False},
    {"theme": "light", "ascii_only": True},
    {"theme": "dark", "ascii_only": True},
], ids=lambda param: f"{param['theme']}_{'ascii' if param['ascii_only'] else 'unicode'}")
def each_theme(request: pytest.FixtureRequest):
    """Fixture to test each combination of UI styles."""
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


def test_paint_app(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, terminal_size=LARGER)

def test_paint_stretch_skew_dialog(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, press=["ctrl+w"])

def test_paint_flip_rotate_dialog(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, press=["ctrl+r"])

def test_paint_image_attributes_dialog(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, press=["ctrl+e"])

def test_paint_open_dialog(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, press=["ctrl+o"], terminal_size=LARGER)

def test_paint_save_dialog(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, press=["ctrl+s"], terminal_size=LARGER)

def test_paint_help_dialog(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, press=["f1"], terminal_size=LARGER)

def test_paint_view_bitmap(snap_compare: SnapCompareType):
    assert snap_compare(PAINT, press=["ctrl+f"])

def test_paint_invert_and_exit(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, press=["ctrl+i", "ctrl+q"])

def test_swap_selected_colors(snap_compare: SnapCompareType):
    async def swap_selected_colors(pilot: Pilot[None]):
        await pilot.click("CharInput", control=True)

    assert snap_compare(PAINT, run_before=swap_selected_colors)

def test_paint_character_picker_dialog(snap_compare: SnapCompareType, each_theme: None):
    async def open_character_picker(pilot: Pilot[None]):
        # app.dark = True caused it to fail to open the dialog in the dark theme,
        # due to `self.call_later(self.refresh_css)` in `watch_dark` in `App`
        # (verified by replacing `app.dark = args.theme == "dark"` with `app.call_later(app.refresh_css)`)
        # Adding a delay works around this.
        await pilot.pause(1.0)
        await pilot.click("CharInput")
        await pilot.click("CharInput")
        assert pilot.app.query_one("CharacterSelectorDialogWindow")

    assert snap_compare(PAINT, run_before=open_character_picker, terminal_size=LARGER)

def test_paint_edit_colors_dialog(snap_compare: SnapCompareType, each_theme: None):
    async def open_edit_colors(pilot: Pilot[None]):
        await pilot.pause(1.0) # see comment in test_paint_character_picker_dialog
        pilot.app.query("ColorsBox Button")[0].id = "a_color_button"
        await pilot.click("#a_color_button")
        await pilot.click("#a_color_button")
        assert pilot.app.query_one("EditColorsDialogWindow")

    assert snap_compare(PAINT, run_before=open_edit_colors, terminal_size=LARGEST)

def test_paint_expand_canvas_dialog(snap_compare: SnapCompareType, each_theme: None):
    async def paste_large_content(pilot: Pilot[None]):
        if TYPE_CHECKING:
            # Will be a different class at runtime, per test, due to re-evaluating the module.
            assert isinstance(pilot.app, PaintApp)
        pilot.app.paste("a" * 1000)

    assert snap_compare(PAINT, run_before=paste_large_content, terminal_size=LARGER)

def test_paint_error_dialog(snap_compare: SnapCompareType, each_theme: None):
    async def show_error(pilot: Pilot[None]):
        if TYPE_CHECKING:
            # Will be a different class at runtime, per test, due to re-evaluating the module.
            assert isinstance(pilot.app, PaintApp)
        pilot.app.message_box("EMIT", "Error Message Itself Test", "ok", error=Exception("Error Message Itself Test"))
        assert pilot.app.query_one("MessageBox")
        await pilot.pause(1.0)
        assert pilot.app.query_one("MessageBox .details_button")
        # pilot.app.query_one("MessageBox .details_button", Button).press()
        await pilot.click("MessageBox .details_button")
        await pilot.pause(0.5) # avoid pressed state

    assert snap_compare(PAINT, run_before=show_error)

def test_paint_custom_zoom_dialog(snap_compare: SnapCompareType, each_theme: None):
    async def show_custom_zoom(pilot: Pilot[None]):
        if TYPE_CHECKING:
            # Will be a different class at runtime, per test, due to re-evaluating the module.
            assert isinstance(pilot.app, PaintApp)
        pilot.app.action_custom_zoom()

    assert snap_compare(PAINT, run_before=show_custom_zoom)

def test_paint_about_paint_dialog(snap_compare: SnapCompareType, each_theme: None):
    async def show_about_paint(pilot: Pilot[None]):
        if TYPE_CHECKING:
            # Will be a different class at runtime, per test, due to re-evaluating the module.
            assert isinstance(pilot.app, PaintApp)
        pilot.app.action_about_paint()

    assert snap_compare(PAINT, run_before=show_about_paint)

# TODO: test polygon color changing while in-progress when you select a color from the palette
# TODO: test dragging to define polygon first — especially, the first two with one drag
def test_paint_polygon_tool(snap_compare: SnapCompareType):
    async def draw_polygon(pilot: Pilot[None]):
        # TODO: fix polygon closing prematurely
        # (interpreting clicks as double clicks despite the distance)
        # and then remove the pause() calls (as many as possible)
        await click_by_attr(pilot, "ToolsBox Button", "tooltip", "Polygon")
        await pilot.click('#canvas', offset=Offset(3, 2))
        await pilot.pause(0.3)
        await pilot.click('#canvas', offset=Offset(19, 2))
        await pilot.pause(0.3)
        await pilot.click('#canvas', offset=Offset(29, 7))
        await pilot.pause(0.3)
        await pilot.click('#canvas', offset=Offset(11, 7))
        await pilot.pause(0.3)
        await pilot.click('#canvas', offset=Offset(3, 2))
        await pilot.pause(0.3)
        # first shape (defined above) should be closed by returning to start point

        await click_by_index(pilot, '#available_colors Button', 16) # red
        await pilot.click('#canvas', offset=Offset(17, 10))
        await pilot.pause(0.3)
        await pilot.click('#canvas', offset=Offset(30, 16))
        await pilot.pause(0.3)
        await pilot.click('#canvas', offset=Offset(49, 16))
        await pilot.pause(0.3)
        await pilot.click('#canvas', offset=Offset(35, 10))
        # no pause — double click on purpose
        await pilot.click('#canvas', offset=Offset(35, 10))
        await pilot.pause(0.3)
        # second shape (defined above) should be closed by double clicking

        await click_by_index(pilot, '#available_colors Button', 17) # yellow
        await pilot.click('#canvas', offset=Offset(33, 2))
        await pilot.pause(0.3)
        await pilot.click('#canvas', offset=Offset(58, 16))
        await pilot.pause(0.3)
        await pilot.click('#canvas', offset=Offset(58, 2))
        await pilot.pause(0.3)
        await pilot.click('#canvas', offset=Offset(44, 2))
        await pilot.pause(0.3)
        await pilot.click('#canvas', offset=Offset(52, 7))
        # third shape (defined above) should be left open as a polyline

    assert snap_compare(PAINT, run_before=draw_polygon, terminal_size=LARGER)

def test_text_tool_wrapping(snap_compare: SnapCompareType):
    async def automate_app(pilot: Pilot[None]):
        await click_by_attr(pilot, "ToolsBox Button", "tooltip", "Text")
        await drag(pilot, '#canvas', [Offset(x=5, y=8), Offset(x=24, y=16)])
        for key in ('T', 'e', 'x', 't', 'space', 'T', 'o', 'o', 'l', 'space', 'T', 'e', 's', 't', 'space', 'left_parenthesis', 'T', 'T', 'T', 'right_parenthesis', 'n', 'e', 'w', 'space', 'l', 'i', 'n', 'e', 'space', 's', 't', 'a', 'r', 't', 's', 'space', 'h', 'e', 'r', 'e', 'a', 'n', 'd', 'space', 'h', 'e', 'r', 'e', 'space', 'a', 'u', 't', 'o', 'm', 'a', 't', 'i', 'c', 'a', 'l', 'hyphen', 'l', 'y'):
            await pilot.press(key)

    assert snap_compare(PAINT, run_before=automate_app, terminal_size=LARGER)

def test_text_tool_cursor_keys_and_color(snap_compare: SnapCompareType):
    async def automate_app(pilot: Pilot[None]):
        await click_by_attr(pilot, "ToolsBox Button", "tooltip", "Text")
        await drag(pilot, '#canvas', [Offset(x=8, y=5), Offset(x=21, y=10)])
        for key in ('s', 'end', 'pagedown', '1', 'home', '2', 'pageup', '3', 'end', '4', 'pageup', 'home', 'right', 'right', 'c', 'r', 'e', 't', 'backspace', 'backspace', 'backspace', 'backspace', 'v', '3', 'n'):
            await pilot.press(key)
        await pilot.click('#canvas', offset=Offset(9, 10))
        for key in ('e', 'r', 'o'):
            await pilot.press(key)
        await click_by_index(pilot, '#available_colors Button', 9)
        await click_by_index(pilot, '#available_colors Button', 18, control=True)

    assert snap_compare(PAINT, run_before=automate_app, terminal_size=LARGER)

def test_gallery_app(snap_compare: SnapCompareType):
    assert snap_compare(GALLERY)

