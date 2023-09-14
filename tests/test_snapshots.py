"""Visual regression tests, using pytest-textual-snapshot. Run with `pytest`."""

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


def test_paint_app(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, terminal_size=LARGER)

def test_paint_stretch_skew_dialog(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, press=["ctrl+w"])

def test_paint_flip_rotate_dialog(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, press=["ctrl+r"])

def test_paint_image_attributes_dialog(snap_compare: SnapCompareType, each_theme: None):
    assert snap_compare(PAINT, press=["ctrl+e"])

def test_paint_open_dialog(snap_compare: SnapCompareType, each_theme: None, my_fs: None):
    assert snap_compare(PAINT, press=["ctrl+o"], terminal_size=LARGER)

def test_paint_save_dialog(snap_compare: SnapCompareType, each_theme: None, my_fs: None):
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

# TODO: test changing color of in-progress polygon when selecting a color from the palette
# TODO: test dragging to define polygon; in particular, dragging can define the first two points at once
def test_paint_polygon_tool(snap_compare: SnapCompareType):
    async def draw_polygon(pilot: Pilot[None]):
        # TODO: fix polygon closing prematurely, interpreting clicks as double clicks despite the distance,
        # and then remove as many of these pause() calls as possible
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
        await drag(pilot, '#canvas', [Offset(5, 8), Offset(24, 16)])
        for key in ('T', 'e', 'x', 't', 'space', 'T', 'o', 'o', 'l', 'space', 'T', 'e', 's', 't', 'space', 'left_parenthesis', 'T', 'T', 'T', 'right_parenthesis', 'n', 'e', 'w', 'space', 'l', 'i', 'n', 'e', 'space', 's', 't', 'a', 'r', 't', 's', 'space', 'h', 'e', 'r', 'e', 'a', 'n', 'd', 'space', 'h', 'e', 'r', 'e', 'space', 'a', 'u', 't', 'o', 'm', 'a', 't', 'i', 'c', 'a', 'l', 'hyphen', 'l', 'y'):
            await pilot.press(key)

    assert snap_compare(PAINT, run_before=automate_app, terminal_size=LARGER)

def test_text_tool_cursor_keys_and_color(snap_compare: SnapCompareType):
    async def automate_app(pilot: Pilot[None]):
        await click_by_attr(pilot, "ToolsBox Button", "tooltip", "Text")
        await drag(pilot, '#canvas', [Offset(8, 5), Offset(21, 10)])
        for key in ('s', 'end', 'pagedown', '1', 'home', '2', 'pageup', '3', 'end', '4', 'pageup', 'home', 'right', 'right', 'c', 'r', 'e', 't', 'backspace', 'backspace', 'backspace', 'backspace', 'v', '3', 'n'):
            await pilot.press(key)
        await pilot.click('#canvas', offset=Offset(9, 10))
        for key in ('e', 'r', 'o'):
            await pilot.press(key)
        await click_by_index(pilot, '#available_colors Button', 9)
        await click_by_index(pilot, '#available_colors Button', 18, control=True)

    assert snap_compare(PAINT, run_before=automate_app, terminal_size=LARGER)

def test_free_form_select(snap_compare: SnapCompareType):
    async def automate_app(pilot: Pilot[None]):
        await click_by_attr(pilot, "ToolsBox Button", "tooltip", "Free-Form Select")
        await drag(pilot, '#canvas', [Offset(8, 3), Offset(9, 4), Offset(10, 4), Offset(13, 5), Offset(17, 7), Offset(21, 8), Offset(26, 10), Offset(30, 12), Offset(35, 13), Offset(39, 14), Offset(40, 14), Offset(40, 15), Offset(39, 15), Offset(37, 15), Offset(33, 16), Offset(30, 16), Offset(25, 16), Offset(21, 16), Offset(16, 15), Offset(11, 14), Offset(4, 13), Offset(0, 13), Offset(2, 0), Offset(3, 0), Offset(4, 0), Offset(0, 9), Offset(7, 8), Offset(13, 7), Offset(20, 5), Offset(27, 4), Offset(28, 4), Offset(27, 4), Offset(27, 5), Offset(25, 6), Offset(20, 10), Offset(15, 13), Offset(12, 16), Offset(11, 17), Offset(10, 18), Offset(10, 17), Offset(10, 17)])
        await pilot.press('ctrl+i')
        await drag(pilot, '#canvas', [Offset(21, 14), Offset(21, 14), Offset(22, 14), Offset(23, 14), Offset(24, 14), Offset(25, 14), Offset(26, 14), Offset(27, 14), Offset(28, 14), Offset(29, 14), Offset(30, 14), Offset(31, 14), Offset(32, 14), Offset(33, 14), Offset(34, 14), Offset(34, 14)])
        await drag(pilot, '#canvas', [Offset(9, 10), Offset(9, 10), Offset(8, 10), Offset(7, 10), Offset(6, 10), Offset(5, 11), Offset(4, 11), Offset(3, 11), Offset(4, 11), Offset(5, 11), Offset(6, 11), Offset(7, 11), Offset(8, 11), Offset(8, 12), Offset(9, 12), Offset(10, 12), Offset(11, 12), Offset(12, 12), Offset(13, 12), Offset(13, 11), Offset(13, 10), Offset(14, 10), Offset(14, 9), Offset(13, 9), Offset(12, 9), Offset(11, 9), Offset(11, 10), Offset(10, 10), Offset(10, 10)])
        await pilot.press('ctrl+i')
        await drag(pilot, '#canvas', [Offset(12, 6), Offset(12, 6), Offset(13, 6), Offset(14, 6), Offset(14, 5), Offset(15, 5), Offset(16, 5), Offset(16, 4), Offset(17, 4), Offset(18, 4), Offset(18, 3), Offset(19, 3), Offset(19, 2), Offset(20, 2), Offset(20, 1), Offset(19, 0), Offset(18, 0), Offset(17, 0), Offset(16, 0), Offset(15, 0), Offset(14, 0), Offset(13, 0), Offset(12, 0), Offset(12, 1), Offset(11, 1), Offset(10, 1), Offset(9, 2), Offset(8, 2), Offset(7, 3), Offset(6, 3), Offset(6, 3)])
        await pilot.press('delete')
        await drag(pilot, '#canvas', [Offset(47, 10), Offset(47, 10), Offset(46, 10), Offset(46, 11), Offset(45, 12), Offset(45, 13), Offset(45, 14), Offset(45, 15), Offset(45, 16), Offset(46, 17), Offset(47, 18), Offset(48, 18), Offset(49, 18), Offset(50, 18), Offset(50, 19), Offset(51, 19), Offset(52, 19), Offset(53, 19), Offset(54, 19), Offset(55, 19), Offset(56, 19), Offset(57, 18), Offset(58, 18), Offset(59, 17), Offset(60, 17), Offset(60, 16), Offset(61, 16), Offset(61, 15), Offset(61, 14), Offset(60, 14), Offset(60, 13), Offset(59, 12), Offset(58, 11), Offset(57, 11), Offset(57, 10), Offset(56, 10), Offset(55, 10), Offset(55, 10)])

    assert snap_compare(PAINT, run_before=automate_app, terminal_size=LARGER)

def test_free_form_select_meld_negative_coords(snap_compare: SnapCompareType):
    async def automate_app(pilot: Pilot[None]):
        await click_by_attr(pilot, "ToolsBox Button", "tooltip", "Fill With Color")
        await click_by_index(pilot, '#available_colors Button', 17) # yellow
        await pilot.click('#canvas', offset=Offset(19, 8))
        await click_by_attr(pilot, "ToolsBox Button", "tooltip", "Free-Form Select")
        await drag(pilot, '#editing_area', [Offset(19, 1), Offset(19, 1), Offset(18, 2), Offset(17, 2), Offset(15, 3), Offset(13, 4), Offset(6, 6), Offset(2, 8), Offset(0, 10), Offset(3, 2), Offset(2, 0), Offset(2, 1), Offset(2, 2), Offset(3, 2), Offset(5, 2), Offset(14, 14), Offset(1, 14), Offset(1, 13), Offset(4, 13), Offset(8, 12), Offset(12, 11), Offset(16, 11), Offset(20, 10), Offset(22, 10), Offset(23, 9), Offset(24, 9), Offset(25, 9), Offset(26, 9), Offset(26, 8), Offset(25, 8), Offset(23, 7), Offset(19, 6), Offset(15, 6), Offset(11, 5), Offset(6, 3), Offset(3, 2), Offset(2, 1), Offset(2, 0), Offset(3, 0), Offset(3, 0)])
        await drag(pilot, '#canvas', [Offset(13, 8), Offset(13, 8), Offset(12, 8), Offset(12, 7), Offset(12, 6), Offset(11, 6), Offset(11, 5), Offset(10, 5), Offset(10, 4), Offset(9, 4), Offset(8, 3), Offset(8, 3)])
        await pilot.press('ctrl+i')
        await pilot.pause(0.5)
        await pilot.click('#editing_area', offset=Offset(0, 20)) # deselect
        await pilot.pause(0.5)

    assert snap_compare(PAINT, run_before=automate_app, terminal_size=LARGER)

def test_select(snap_compare: SnapCompareType):
    async def automate_app(pilot: Pilot[None]):
        await click_by_attr(pilot, "ToolsBox Button", "tooltip", "Select")
        await drag(pilot, '#canvas', [Offset(5, 3), Offset(5, 3), Offset(6, 4), Offset(8, 5), Offset(9, 6), Offset(11, 7), Offset(13, 8), Offset(14, 10), Offset(15, 10), Offset(16, 11), Offset(17, 11), Offset(18, 12), Offset(19, 12), Offset(19, 13), Offset(20, 13), Offset(21, 13), Offset(21, 14), Offset(22, 14), Offset(22, 14)])
        await pilot.press('ctrl+i')
        await drag(pilot, '#canvas', [Offset(12, 8), Offset(13, 8), Offset(13, 9), Offset(14, 10), Offset(15, 12), Offset(16, 13), Offset(18, 14), Offset(19, 15), Offset(20, 15), Offset(20, 16), Offset(21, 16), Offset(22, 17), Offset(23, 17), Offset(24, 17), Offset(24, 16), Offset(24, 15), Offset(24, 14), Offset(25, 13), Offset(25, 13)])
        await drag(pilot, '#canvas', [Offset(7, 13), Offset(7, 13), Offset(8, 13), Offset(9, 14), Offset(10, 15), Offset(11, 15), Offset(12, 16), Offset(13, 17), Offset(15, 17), Offset(16, 18), Offset(17, 19), Offset(18, 19), Offset(19, 19), Offset(19, 20), Offset(20, 20), Offset(21, 20), Offset(22, 21), Offset(23, 21), Offset(24, 21), Offset(24, 22), Offset(25, 22), Offset(25, 22)])
        await pilot.press('ctrl+i')
        await drag(pilot, '#canvas', [Offset(12, 3), Offset(12, 3), Offset(13, 4), Offset(14, 5), Offset(14, 6), Offset(15, 7), Offset(16, 7), Offset(17, 8), Offset(18, 9), Offset(19, 9), Offset(20, 10), Offset(21, 10), Offset(22, 10), Offset(23, 11), Offset(24, 12), Offset(25, 12), Offset(26, 12), Offset(26, 13), Offset(27, 13), Offset(28, 14), Offset(29, 14), Offset(30, 14), Offset(30, 15), Offset(31, 15), Offset(32, 15), Offset(32, 16), Offset(33, 16), Offset(34, 16), Offset(35, 16), Offset(36, 16), Offset(37, 16), Offset(38, 16), Offset(38, 15), Offset(39, 15), Offset(40, 15), Offset(41, 15), Offset(42, 16), Offset(41, 16), Offset(41, 16)])
        await drag(pilot, '#canvas', [Offset(34, 13), Offset(34, 13), Offset(34, 12), Offset(35, 12), Offset(35, 11), Offset(35, 10), Offset(35, 9), Offset(36, 9), Offset(37, 9), Offset(38, 9), Offset(39, 9), Offset(40, 9), Offset(39, 9), Offset(38, 9), Offset(38, 9)],
                   control=True) # duplicate selection with Ctrl
        await drag(pilot, '#canvas', [Offset(2, 6), Offset(2, 6), Offset(3, 6), Offset(4, 6), Offset(4, 7), Offset(5, 7), Offset(6, 7), Offset(7, 8), Offset(8, 8), Offset(8, 9), Offset(10, 9), Offset(11, 10), Offset(12, 11), Offset(13, 11), Offset(13, 12), Offset(15, 12), Offset(16, 13), Offset(17, 13), Offset(18, 14), Offset(19, 14), Offset(20, 15), Offset(21, 16), Offset(23, 16), Offset(24, 17), Offset(25, 17), Offset(25, 18), Offset(26, 18), Offset(27, 18), Offset(28, 18), Offset(29, 18), Offset(30, 18), Offset(31, 18), Offset(32, 18), Offset(33, 18), Offset(33, 18)])

    assert snap_compare(PAINT, run_before=automate_app, terminal_size=LARGER)

def test_gallery_app(snap_compare: SnapCompareType):
    assert snap_compare(GALLERY)

