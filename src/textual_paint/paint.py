#!/usr/bin/env python3

"""Textual Paint is a detailed MS Paint clone that runs in the terminal."""

import asyncio
import math
import os
import re
import shlex
import sys
from random import random
from typing import Any, Callable, Iterator, Optional
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from rich.style import Style
from rich.text import Text
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Color
from textual.containers import Container, Horizontal, Vertical
from textual.css._style_properties import BorderDefinition
from textual.dom import DOMNode
from textual.geometry import Offset, Region, Size
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import (Button, Header, Input, RadioButton, RadioSet,
                             Static)
from textual.widgets._header import HeaderIcon
from textual.worker import get_current_worker  # type: ignore

from textual_paint.__init__ import PYTEST, __version__
from textual_paint.action import Action
from textual_paint.ansi_art_document import (SAVE_DISABLED_FORMATS,
                                             AnsiArtDocument,
                                             FormatReadNotSupported,
                                             FormatWriteNotSupported,
                                             Selection)
from textual_paint.args import args, get_help_text
from textual_paint.ascii_mode import set_ascii_only_mode
from textual_paint.auto_restart import restart_on_changes, restart_program
from textual_paint.canvas import Canvas
from textual_paint.char_input import CharInput
from textual_paint.character_picker import CharacterSelectorDialogWindow
from textual_paint.colors_box import ColorsBox
from textual_paint.edit_colors import EditColorsDialogWindow
from textual_paint.file_dialogs import OpenDialogWindow, SaveAsDialogWindow
from textual_paint.graphics_primitives import (bezier_curve_walk,
                                               bresenham_walk, flood_fill,
                                               is_inside_polygon,
                                               midpoint_ellipse, polygon_walk,
                                               polyline_walk,
                                               quadratic_curve_walk)
from textual_paint.icons import (get_help_icon_markup, get_paint_icon,
                                 get_question_icon, get_warning_icon,
                                 get_windows_icon_markup, header_icon_text)
from textual_paint.localization.i18n import get as _
from textual_paint.localization.i18n import load_language, remove_hotkey
from textual_paint.menus import Menu, MenuBar, MenuItem, Separator
from textual_paint.palette_data import DEFAULT_PALETTE, IRC_PALETTE
from textual_paint.rasterize_ansi_art import rasterize
from textual_paint.tool import Tool
from textual_paint.toolbox import ToolsBox
from textual_paint.wallpaper import get_config_dir, set_wallpaper
from textual_paint.windows import DialogWindow, MessageBox, Window

MAX_FILE_SIZE = 500000 # 500 KB

# Most arguments are handled at the end of the file,
# but it may be important to do this one early.
load_language(args.language)


def offset_to_text_index(textbox: Selection, offset: Offset) -> int:
    """Converts an offset in the textbox to an index in the text."""
    assert textbox.textbox_mode, "offset_to_text_index called on non-textbox selection"
    return offset.y * textbox.region.width + offset.x

def text_index_to_offset(textbox: Selection, index: int) -> Offset:
    """Converts an index in the text to an offset in the textbox."""
    assert textbox.textbox_mode, "text_index_to_offset called on non-textbox selection"
    return Offset(index % textbox.region.width, index // textbox.region.width)

def selected_text_range(textbox: Selection) -> Iterator[Offset]:
    """Yields all offsets within the text selection."""
    assert textbox.textbox_mode, "selected_text_range called on non-textbox selection"
    start = offset_to_text_index(textbox, textbox.text_selection_start)
    end = offset_to_text_index(textbox, textbox.text_selection_end)
    for i in range(min(start, end), max(start, end) + 1):
        yield text_index_to_offset(textbox, i)

def selected_text(textbox: Selection) -> str:
    """Returns the text within the text selection."""
    assert textbox.textbox_mode, "selected_text called on non-textbox selection"
    assert textbox.contained_image, "textbox has no image data"
    # return "".join(textbox.contained_image.ch[y][x] for x, y in selected_text_range(textbox))
    text = ""
    last_y = -1
    for x, y in selected_text_range(textbox):
        text += textbox.contained_image.ch[y][x]
        if y != last_y:
            text += "\n"
            last_y = y
    return text



class PaintApp(App[None]):
    """MS Paint like image editor in the terminal."""

    CSS_PATH = "paint.css"

    # These call action_* methods on the widget.
    # They can have parameters, if need be.
    # https://textual.textualize.io/guide/actions/
    #
    # KEEP IN SYNC with the README.md Usage section, please.
    BINDINGS = [
        # There is a built-in "quit" action, but it will quit without asking to save.
        # It's also bound to Ctrl+C by default, so it needs to be rebound, either to
        # action_exit, which prompts to save, or to action_copy, like a desktop app.
        Binding("ctrl+q", "exit", _("Quit")),
        Binding("ctrl+s", "save", _("Save")),
        Binding("ctrl+shift+s", "save_as", _("Save As")),
        Binding("ctrl+p", "print", _("Print")),
        Binding("ctrl+o", "open", _("Open")),
        Binding("ctrl+n", "new", _("New")),
        Binding("ctrl+shift+n", "clear_image", _("Clear Image")),
        Binding("ctrl+t", "toggle_tools_box", _("Toggle Tools Box")),
        Binding("ctrl+l", "toggle_colors_box", _("Toggle Colors Box")),
        Binding("ctrl+z", "undo", _("Undo")),
        # Ctrl+Shift+<key> doesn't seem to work on Ubuntu or VS Code terminal,
        # it ignores the Shift.
        Binding("ctrl+shift+z,shift+ctrl+z,ctrl+y,f4", "redo", _("Repeat")),
        Binding("ctrl+x", "cut", _("Cut")),
        Binding("ctrl+c", "copy(True)", _("Copy")),
        Binding("ctrl+v", "paste", _("Paste")),
        Binding("ctrl+g", "toggle_grid", _("Show Grid")),
        Binding("ctrl+f", "view_bitmap", _("View Bitmap")),
        Binding("ctrl+r", "flip_rotate", _("Flip/Rotate")),
        Binding("ctrl+w", "stretch_skew", _("Stretch/Skew")),
        # Unfortunately, Ctrl+I is indistinguishable from Tab, which is used for focus switching.
        # To support Ctrl+I, we have to use a priority binding, and ignore it in
        # cases where focus switching is desired.
        Binding("ctrl+i,tab", "invert_colors_unless_should_switch_focus", _("Invert Colors"), priority=True),
        Binding("ctrl+e", "attributes", _("Attributes")),
        Binding("delete", "clear_selection(True)", _("Clear Selection")),
        Binding("ctrl+a", "select_all", _("Select All")),
        Binding("ctrl+pageup", "normal_size", _("Normal Size")),
        Binding("ctrl+pagedown", "large_size", _("Large Size")),
        # action_toggle_dark is built in to App
        Binding("ctrl+d", "toggle_dark", _("Toggle Dark Mode")),
        Binding("escape", "cancel", _("Cancel")),
        Binding("f1", "help_topics", _("Help Topics")),
        # dev helper
        # f5 would be more traditional, but I need something not bound to anything
        # in the context of the terminal in VS Code, and not used by this app, like Ctrl+R, and detectable in the terminal.
        # This isn't as important now that I have automatic reloading,
        # but I still use it regularly.
        Binding("f2", "reload", _("Reload")),
        # Temporary quick access to work on a specific dialog.
        # Can be used together with `--press f3` when using `textual run` to open the dialog at startup.
        # Would be better if all dialogs were accessible from the keyboard.
        # Binding("f3", "custom_zoom", _("Custom Zoom")),
        # Dev tool to inspect the widget tree.
        Binding("f12", "toggle_inspector", _("Toggle Inspector")),
        # Update screenshot on readme.
        # Binding("ctrl+j", "update_screenshot", _("Update Screenshot")),
    ]

    show_tools_box = var(True)
    """Whether to show the tools box."""
    show_colors_box = var(True)
    """Whether to show the tools box."""
    show_status_bar = var(True)
    """Whether to show the status bar."""

    palette = var(DEFAULT_PALETTE)
    """The colors to show in the colors box. This is a tuple for immutability, since mutations would not trigger watch_palette."""
    selected_tool = var(Tool.pencil)
    """The currently selected tool."""
    return_to_tool = var(Tool.pencil)
    """Tool to switch to after using the Magnifier or Pick Color tools."""
    selected_bg_color = var(DEFAULT_PALETTE[0])
    """The currently selected background color. Unlike MS Paint, this acts as the primary color."""
    selected_fg_color = var(DEFAULT_PALETTE[len(DEFAULT_PALETTE) // 2])
    """The currently selected foreground (text) color."""
    selected_char = var(" ")
    """The character to draw with."""
    file_path = var(None)
    """The path to the file being edited."""

    image = var(AnsiArtDocument.from_text("Not Loaded"))
    """The document being edited. Contains the selection, if any."""
    image_initialized = False
    """Whether the image is ready. This flag exists to avoid type checking woes if I were to allow image to be None."""

    magnification = var(1)
    """Current magnification level."""
    return_to_magnification = var(4)
    """Saved zoomed-in magnification level."""
    show_grid = var(False)
    """Whether to show the grid. Only applies when zoomed in to 400% or more."""
    old_scroll_offset = var(Offset(0, 0))
    """The scroll offset before View Bitmap mode was entered."""

    undos: list[Action] = []
    """Past actions that can be undone"""
    redos: list[Action] = []
    """Future actions that can be redone"""
    preview_action: Optional[Action] = None
    """A temporary undo state for tool previews"""
    saved_undo_count = 0
    """Used to determine if the document has been modified since the last save, in is_document_modified()"""
    backup_saved_undo_count = 0
    """Used to determine if the document has been modified since the last backup save"""
    save_backup_after_cancel_preview = False
    """Flag to postpone saving the backup until a tool preview action is reverted, so as not to save it into the backup file"""
    backup_folder: Optional[str] = None
    """The folder to save a temporary backup file to. If None, will save alongside the file being edited."""
    backup_checked_for: Optional[str] = None
    """The file path last checked for a backup save.

    This is tracked to prevent discarding Untitled.ans~ when loading a document on startup.
    Indicates that the file path either was loaded (recovered) or was not found.
    Not set when failing to load a backup, since the file maybe shouldn't be discarded in that case.
    """

    mouse_gesture_cancelled = False
    """For Undo/Redo, to interrupt the current action"""
    mouse_at_start: Offset = Offset(0, 0)
    """Mouse position at mouse down.

    Used for shape tools that draw between the mouse down and up points (Line, Rectangle, Ellipse, Rounded Rectangle),
    the Select tool (defining a box similarly to Rectangle), and also used to detect double-click, for the Polygon tool.
    """
    mouse_previous: Offset = Offset(0, 0)
    """Previous mouse position, for brush tools (Pencil, Brush, Eraser, Airbrush)"""
    selection_drag_offset: Offset|None = None
    """For Select tool, indicates that the selection is being moved, and defines the offset of the selection from the mouse"""
    selecting_text: bool = False
    """Used for Text tool"""
    tool_points: list[Offset] = []
    """Used for Curve, Polygon, or Free-Form Select tools"""
    polygon_last_click_time: float = 0
    """Used for Polygon tool to detect double-click"""
    color_eraser_mode: bool = False
    """Used for Eraser/Color Eraser tool, when using the right mouse button"""

    background_tasks: set[asyncio.Task[None]] = set()
    """Stores references to Task objects so they don't get garbage collected."""

    TITLE = _("Paint")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        set_ascii_only_mode(args.ascii_only)

    def watch_file_path(self, file_path: Optional[str]) -> None:
        """Called when file_path changes."""
        if file_path is None:
            self.sub_title = _("Untitled")
        else:
            self.sub_title = os.path.basename(file_path)

    def watch_show_tools_box(self, show_tools_box: bool) -> None:
        """Called when show_tools_box changes."""
        self.query_one("#tools_box", ToolsBox).display = show_tools_box

    def watch_show_colors_box(self, show_colors_box: bool) -> None:
        """Called when show_colors_box changes."""
        self.query_one("#colors_box", ColorsBox).display = show_colors_box

    def watch_show_status_bar(self, show_status_bar: bool) -> None:
        """Called when show_status_bar changes."""
        self.query_one("#status_bar").display = show_status_bar

    def watch_selected_tool(self, selected_tool: Tool) -> None:
        """Called when selected_tool changes."""
        self.query_one("ToolsBox", ToolsBox).show_selected_tool(selected_tool)

    def watch_palette(self, palette: tuple[str, ...]) -> None:
        """Called when palette changes."""
        self.query_one("ColorsBox", ColorsBox).palette = palette

    def watch_selected_bg_color(self, selected_bg_color: str) -> None:
        """Called when selected_bg_color changes."""
        self.query_one("#selected_color_char_input", CharInput).styles.background = selected_bg_color
        # CharInput now handles the background style itself PARTIALLY; it doesn't affect the whole area.

        # update Text tool textbox immediately
        if self.image.selection and self.image.selection.textbox_mode:
            assert self.image.selection.contained_image is not None, "textbox_mode without contained_image"
            for y in range(self.image.selection.region.height):
                for x in range(self.image.selection.region.width):
                    self.image.selection.contained_image.bg[y][x] = self.selected_bg_color
            self.canvas.refresh_scaled_region(self.image.selection.region)

        # update Polygon/Curve tool preview immediately
        self.draw_tool_preview_on_canvas()

    def watch_selected_fg_color(self, selected_fg_color: str) -> None:
        """Called when selected_fg_color changes."""
        # self.query_one("#selected_color_char_input", CharInput).styles.color = selected_fg_color
        # CharInput now handles this itself, because styles.color never worked to color the Input's text.
        # Well, it still needs to be updated.
        self.query_one("#selected_color_char_input", CharInput).refresh()

        # update Text tool textbox immediately
        if self.image.selection and self.image.selection.textbox_mode:
            assert self.image.selection.contained_image is not None, "textbox_mode without contained_image"
            for y in range(self.image.selection.region.height):
                for x in range(self.image.selection.region.width):
                    self.image.selection.contained_image.fg[y][x] = self.selected_fg_color
            self.canvas.refresh_scaled_region(self.image.selection.region)

        # update Polygon/Curve tool preview immediately
        self.draw_tool_preview_on_canvas()

    def watch_selected_char(self, selected_char: str) -> None:
        """Called when selected_char changes."""
        self.query_one("#selected_color_char_input", CharInput).value = selected_char

    def watch_magnification(self, old_magnification: int, magnification: int) -> None:
        """Called when magnification changes."""
        self.canvas.magnification = magnification
        if old_magnification != 1:
            self.return_to_magnification = old_magnification

        # TODO: keep the top left corner of the viewport in the same place
        # https://github.com/1j01/jspaint/blob/12a90c6bb9d36f495dc6a07114f9667c82ee5228/src/functions.js#L326-L351
        # This will matter more when large documents don't freeze up the program...

    def watch_show_grid(self, show_grid: bool) -> None:
        """Called when show_grid changes."""
        self.canvas.show_grid = show_grid

    def stamp_brush(self, x: int, y: int, affected_region_base: Optional[Region] = None) -> Region:
        """Draws the current brush at the given coordinates, with special handling for different tools."""
        brush_diameter = 1
        square = self.selected_tool == Tool.eraser
        if self.selected_tool == Tool.brush or self.selected_tool == Tool.airbrush or self.selected_tool == Tool.eraser:
            brush_diameter = 3
        if brush_diameter == 1:
            self.stamp_char(x, y)
        else:
            # plot points within a circle (or square)
            for i in range(brush_diameter):
                for j in range(brush_diameter):
                    if square or (i - brush_diameter // 2) ** 2 + (j - brush_diameter // 2) ** 2 <= (brush_diameter // 2) ** 2:
                        self.stamp_char(x + i - brush_diameter // 2, y + j - brush_diameter // 2)
        # expand the affected region to include the brush
        brush_diameter += 2  # safety margin
        affected_region = Region(x - brush_diameter // 2, y - brush_diameter // 2, brush_diameter, brush_diameter)
        if affected_region_base:
            return affected_region_base.union(affected_region)
        else:
            return affected_region

    def stamp_char(self, x: int, y: int) -> None:
        """Modifies the cell at the given coordinates, with special handling for different tools."""
        if x >= self.image.width or y >= self.image.height or x < 0 or y < 0:
            return

        char = self.selected_char
        bg_color = self.selected_bg_color
        fg_color = self.selected_fg_color
        if self.selected_tool == Tool.eraser:
            char = " "
            bg_color = "#ffffff"
            fg_color = "#000000"
            if self.color_eraser_mode:
                char = self.image.ch[y][x]
                # fg_color = self.selected_bg_color if self.image.fg[y][x] == self.selected_fg_color else self.image.fg[y][x]
                # bg_color = self.selected_bg_color if self.image.bg[y][x] == self.selected_fg_color else self.image.bg[y][x]

                # Use color comparison instead of string comparison because "#000000" != "rgb(0,0,0)"
                # This stuff might be simpler and more efficient if we used Color objects in the document model
                style = Style(color=self.image.fg[y][x], bgcolor=self.image.bg[y][x])
                selected_fg_style = Style(color=self.selected_fg_color)
                assert style.color is not None
                assert style.bgcolor is not None
                assert selected_fg_style.color is not None
                # fg_matches = style.color.triplet == selected_fg_style.color.triplet
                # bg_matches = style.bgcolor.triplet == selected_fg_style.color.triplet
                threshold = 5
                assert style.color.triplet is not None
                assert style.bgcolor.triplet is not None
                assert selected_fg_style.color.triplet is not None
                fg_matches = abs(style.color.triplet[0] - selected_fg_style.color.triplet[0]) < threshold and abs(style.color.triplet[1] - selected_fg_style.color.triplet[1]) < threshold and abs(style.color.triplet[2] - selected_fg_style.color.triplet[2]) < threshold
                bg_matches = abs(style.bgcolor.triplet[0] - selected_fg_style.color.triplet[0]) < threshold and abs(style.bgcolor.triplet[1] - selected_fg_style.color.triplet[1]) < threshold and abs(style.bgcolor.triplet[2] - selected_fg_style.color.triplet[2]) < threshold
                fg_color = self.selected_bg_color if fg_matches else self.image.fg[y][x]
                bg_color = self.selected_bg_color if bg_matches else self.image.bg[y][x]
        if self.selected_tool == Tool.airbrush:
            if random() < 0.7:
                return
        if self.selected_tool == Tool.free_form_select:
            # Invert the underlying colors
            # TODO: DRY color inversion, and/or simplify it. It shouldn't need a Style object.
            style = Style(color=self.image.fg[y][x], bgcolor=self.image.bg[y][x])
            assert style.color is not None
            assert style.bgcolor is not None
            # Why do I need these extra asserts here and not in Canvas.render_line
            # using pyright, even though hovering over the other place shows that it also considers
            # triplet to be ColorTriplet|None?
            assert style.color.triplet is not None
            assert style.bgcolor.triplet is not None
            # self.image.bg[y][x] = f"rgb({255 - style.bgcolor.triplet.red},{255 - style.bgcolor.triplet.green},{255 - style.bgcolor.triplet.blue})"
            # self.image.fg[y][x] = f"rgb({255 - style.color.triplet.red},{255 - style.color.triplet.green},{255 - style.color.triplet.blue})"
            # Use hex instead, for less memory usage, theoretically
            self.image.bg[y][x] = f"#{(255 - style.bgcolor.triplet.red):02x}{(255 - style.bgcolor.triplet.green):02x}{(255 - style.bgcolor.triplet.blue):02x}"
            self.image.fg[y][x] = f"#{(255 - style.color.triplet.red):02x}{(255 - style.color.triplet.green):02x}{(255 - style.color.triplet.blue):02x}"
        else:
            self.image.ch[y][x] = char
            self.image.bg[y][x] = bg_color
            self.image.fg[y][x] = fg_color

    def erase_region(self, region: Region, mask: Optional[list[list[bool]]] = None) -> None:
        """Clears the given region."""
        # Time to go undercover as an eraser. 🥸
        # TODO: just add a parameter to stamp_char.
        # Momentarily masquerading makes me mildly mad.
        original_tool = self.selected_tool
        self.selected_tool = Tool.eraser
        for x in range(region.width):
            for y in range(region.height):
                if mask is None or mask[y][x]:
                    self.stamp_char(x + region.x, y + region.y)
        self.selected_tool = original_tool

    def draw_current_free_form_select_polyline(self) -> Region:
        """Inverts the colors along a polyline defined by tool_points, for Free-Form Select tool preview."""
        # TODO: DRY with draw_current_curve/draw_current_polygon/draw_current_polyline
        # Also (although this may be counter to DRYING (Deduplicating Repetitive Yet Individually Nimble Generators)),
        # could optimize to not use stamp_brush, since it's always a single character here.
        gen = polyline_walk(self.tool_points)
        affected_region = Region()
        already_inverted: set[tuple[int, int]] = set()
        for x, y in gen:
            if (x, y) not in already_inverted:
                affected_region = affected_region.union(self.stamp_brush(x, y, affected_region))
                already_inverted.add((x, y))
        return affected_region

    def draw_current_polyline(self) -> Region:
        """Draws a polyline from tool_points, for Polygon tool preview."""
        # TODO: DRY with draw_current_curve/draw_current_polygon
        gen = polyline_walk(self.tool_points)
        affected_region = Region()
        for x, y in gen:
            affected_region = affected_region.union(self.stamp_brush(x, y, affected_region))
        return affected_region

    def draw_current_polygon(self) -> Region:
        """Draws a polygon from tool_points, for Polygon tool."""
        # TODO: DRY with draw_current_curve/draw_current_polyline
        gen = polygon_walk(self.tool_points)
        affected_region = Region()
        for x, y in gen:
            affected_region = affected_region.union(self.stamp_brush(x, y, affected_region))
        return affected_region

    def draw_current_curve(self) -> Region:
        """Draws a curve (or line) from tool_points, for Curve tool."""
        points = self.tool_points
        if len(points) == 4:
            gen = bezier_curve_walk(
                points[0].x, points[0].y,
                points[2].x, points[2].y,
                points[3].x, points[3].y,
                points[1].x, points[1].y,
            )
        elif len(points) == 3:
            gen = quadratic_curve_walk(
                points[0].x, points[0].y,
                points[2].x, points[2].y,
                points[1].x, points[1].y,
            )
        elif len(points) == 2:
            gen = bresenham_walk(
                points[0].x, points[0].y,
                points[1].x, points[1].y,
            )
        else:
            gen = iter(points)
        affected_region = Region()
        for x, y in gen:
            affected_region = affected_region.union(self.stamp_brush(x, y, affected_region))
        return affected_region

    def finalize_polygon_or_curve(self) -> None:
        """Finalizes the polygon or curve shape, creating an undo state."""
        # TODO: DRY with other undo state creation
        self.cancel_preview()

        if self.selected_tool not in [Tool.polygon, Tool.curve]:
            return

        if self.selected_tool == Tool.polygon and len(self.tool_points) < 3:
            return
        if self.selected_tool == Tool.curve and len(self.tool_points) < 2:
            return

        self.image_at_start = AnsiArtDocument(self.image.width, self.image.height)
        self.image_at_start.copy_region(self.image)
        action = Action(self.selected_tool.get_name())
        self.add_action(action)

        if self.selected_tool == Tool.polygon:
            affected_region = self.draw_current_polygon()
        else:
            affected_region = self.draw_current_curve()

        action.region = affected_region
        action.region = action.region.intersection(Region(0, 0, self.image.width, self.image.height))
        action.update(self.image_at_start)
        self.canvas.refresh_scaled_region(affected_region)

        self.tool_points = []

    def action_cancel(self) -> None:
        """Action to end the current tool activity, via Escape key."""
        self.stop_action_in_progress()

    def stop_action_in_progress(self) -> None:
        """Finalizes the selection, or cancels other tools."""
        self.cancel_preview()
        self.meld_selection()
        self.tool_points = []
        self.mouse_gesture_cancelled = True
        self.get_widget_by_id("status_coords", Static).update("")
        self.get_widget_by_id("status_dimensions", Static).update("")
        if self.selected_tool in [Tool.pick_color, Tool.magnifier]:
            self.selected_tool = self.return_to_tool

    def action_undo(self) -> None:
        """Undoes the last action."""
        # print("Before undo, undos:", ", ".join(map(lambda action: f"{action.name} {action.region}", self.undos)))
        # print("redos:", ", ".join(map(lambda action: f"{action.name} {action.region}", self.redos)))
        self.stop_action_in_progress()
        if len(self.undos) > 0:
            action = self.undos.pop()
            redo_region = Region(0, 0, self.image.width, self.image.height) if action.is_full_update else action.region
            redo_action = Action(_("Undo") + " " + action.name, redo_region)
            redo_action.is_full_update = action.is_full_update
            redo_action.update(self.image)
            action.undo(self.image)
            self.redos.append(redo_action)
            self.canvas.refresh(layout=True)

    def action_redo(self) -> None:
        """Redoes the last undone action."""
        # print("Before redo, undos:", ", ".join(map(lambda action: f"{action.name} {action.region}", self.undos)))
        # print("redos:", ", ".join(map(lambda action: f"{action.name} {action.region}", self.redos)))
        self.stop_action_in_progress()
        if len(self.redos) > 0:
            action = self.redos.pop()
            undo_region = Region(0, 0, self.image.width, self.image.height) if action.is_full_update else action.region
            undo_action = Action(_("Undo") + " " + action.name, undo_region)
            undo_action.is_full_update = action.is_full_update
            undo_action.update(self.image)
            action.undo(self.image)
            self.undos.append(undo_action)
            self.canvas.refresh(layout=True)

    def add_action(self, action: Action) -> None:
        """Adds an action to the undo stack, clearing redos."""
        if len(self.redos) > 0:
            self.redos = []
        self.undos.append(action)

    def close_windows(self, selector: str) -> None:
        """Close all windows matching the CSS selector."""
        for window in self.query(selector).nodes:
            assert isinstance(window, Window), f"Expected a Window for query '{selector}', but got {window.css_identifier}"
            window.close()

    def start_backup_interval(self) -> None:
        """Auto-save a backup file periodically."""
        self.backup_interval = 10
        self.set_interval(self.backup_interval, self.save_backup)

    def get_backup_file_path(self) -> str:
        """Returns the path to the backup file."""
        backup_file_path = self.file_path or _("Untitled")
        if self.backup_folder:
            backup_file_path = os.path.join(self.backup_folder, os.path.basename(backup_file_path))
        # FOO.ANS -> FOO.ans~; FOO.TXT -> FOO.TXT.ans~; Untitled -> Untitled.ans~
        backup_file_path = re.sub(r"\.ans$", "", backup_file_path, re.IGNORECASE) + ".ans~"
        return os.path.abspath(backup_file_path)

    def save_backup(self) -> None:
        """Save to the backup file if there have been changes since it was saved."""
        if self.backup_saved_undo_count != len(self.undos):
            if self.image_has_preview():
                # Postpone saving the backup until the preview is reverted, so it's not saved into the backup file.
                # Since the preview exists as long as you're hovering over the canvas,
                # we don't want to just delay and hope to be able to save at some point.
                # Instead, set a flag to save the backup exactly as soon as the preview action is reverted.
                self.save_backup_after_cancel_preview = True
                return
            ansi = self.image.get_ansi()
            # This maybe shouldn't use UTF-8...
            ansi_bytes = ansi.encode("utf-8")
            self.write_file_path(self.get_backup_file_path(), ansi_bytes, _("Backup Save Failed"))
            self.backup_saved_undo_count = len(self.undos)

    def recover_from_backup(self) -> None:
        """Recover from the backup file, if it exists."""
        if PYTEST:
            # It might be nice to test the backup system,
            # but for now it's interfering with snapshot tests.
            # I could also do something fancier, like set the --backup-folder flag in tests,
            # and empty the folder after each test.
            print("Skipping recover_from_backup in pytest")
            return
        backup_file_path = self.get_backup_file_path()
        print("Checking for backup at:", backup_file_path, "...it exists" if os.path.exists(backup_file_path) else "...it does not exist")
        if os.path.exists(backup_file_path):
            try:
                if os.path.getsize(backup_file_path) > MAX_FILE_SIZE:
                    self.message_box(_("Open"), _("A backup file was found, but was not recovered.") + "\n" + _("The file is too large to open."), "ok")
                    return
                with open(backup_file_path, "r", encoding="utf-8") as f:
                    backup_content = f.read()
                    backup_image = AnsiArtDocument.from_text(backup_content)
                    self.backup_checked_for = backup_file_path
                    # TODO: make backup use image format when appropriate
            except Exception as e:
                self.message_box(_("Paint"), _("A backup file was found, but was not recovered.") + "\n" + _("An unexpected error occurred while reading %1.", backup_file_path), "ok", error=e)
                # Don't set self.backup_checked_for, so the backup won't be discarded,
                # to allow for manual recovery.
                # Actually, it will be overwritten when saving a new backup...
                # TODO: numbered session files; I had some plans for this in a commit message
                # See: 74ffc34de4b789ec1da2ae2e08bf99f1bb4670c9
                # I could make backup_checked_for into owned_backup_file_path (or a dict if needed)
                return
            # This creates an undo
            self.resize_document(backup_image.width, backup_image.height)
            self.undos[-1].name = _("Recover from backup")
            self.canvas.image = self.image = backup_image
            self.canvas.refresh(layout=True)
            # No point in saving the backup file as-is, so mark it as up-to-date
            self.backup_saved_undo_count = len(self.undos)
            # Don't set self.saved_undo_count, since the recovered contents are not saved to the main file
            # Don't delete the backup file, since it's not saved to the main file yet

            def handle_button(button: Button) -> None:
                if button.has_class("no"):
                    self.action_undo()
            # This message may be ambiguous if the main file has been changed since the backup was made.
            # TODO: UX design; maybe compare file modification times
            self.message_box(_("Paint"), _("Recovered document from backup.\nKeep changes?"), "yes/no", handle_button)
        else:
            self.backup_checked_for = backup_file_path

    def action_save(self) -> None:
        """Start the save action, but don't wait for the Save As dialog to close if it's a new file."""
        async def save_ignoring_result() -> None:
            await self.save()
        task = asyncio.create_task(save_ignoring_result())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    def write_file_path(self, file_path: str, content: bytes, dialog_title: str) -> bool:
        """Write a file, showing an error message and returning False if it fails."""
        try:
            with open(file_path, "wb") as f:
                f.write(content)
            return True
        except PermissionError:
            self.message_box(dialog_title, _("Access denied."), "ok")
        except FileNotFoundError:
            self.message_box(dialog_title, _("%1 contains an invalid path.", file_path), "ok")
        except OSError as e:
            self.message_box(dialog_title, _("Failed to save document."), "ok", error=e)
        except Exception as e:
            self.message_box(dialog_title, _("An unexpected error occurred while writing %1.", file_path), "ok", error=e)
        return False

    def reload_after_save(self, content: bytes, file_path: str) -> bool:
        """Reload the document from saved content, to show information loss from the file format.

        Unlike `open_from_file_path`, this method:
        - doesn't short circuit when the file path matches the current file path, crucially
        - skips backup management (discarding or checking for a backup)
        - skips the file system, which is more efficient
        - is undoable
        """
        # TODO: DRY error handling with open_from_file_path and action_paste_from
        try:
            self.resize_document(self.image.width, self.image.height) # (hackily) make this undoable
            new_image = AnsiArtDocument.decode_based_on_file_extension(content, file_path)
            self.canvas.image = self.image = new_image
            self.canvas.refresh(layout=True)
            # awkward to do this in here as well as externally, but this should be updated with the new undo count
            self.saved_undo_count = len(self.undos)
            self.update_palette_from_format_id(AnsiArtDocument.format_from_extension(file_path))
            return True
        except UnicodeDecodeError:
            self.message_box(_("Open"), file_path + "\n" + _("Paint cannot read this file.") + "\n" + _("Unexpected file format."), "ok")
        except UnidentifiedImageError as e:
            self.message_box(_("Open"), _("This is not a valid bitmap file, or its format is not currently supported."), "ok", error=e)
        except FormatReadNotSupported as e:
            self.message_box(_("Open"), e.localized_message, "ok")
        except Exception as e:
            self.message_box(_("Open"), _("An unexpected error occurred while reading %1.", file_path), "ok", error=e)
        return False

    def update_palette_from_format_id(self, format_id: str | None) -> None:
        """Update the palette based on the file format.

        In the future, this should update from attributes set when loading the file,
        such as whether it supports color, and if not, it could show pattern fills,
        such as ░▒▓█... that's not a lot of patterns, and you could get those from the
        character picker, but it might be nice to have them more accessible,
        that or to make the character picker a dockable window.
        """
        if format_id == "IRC":
            self.palette = IRC_PALETTE + (IRC_PALETTE[0],) * (len(self.palette) - len(IRC_PALETTE))
        elif format_id == "PLAINTEXT":
            self.palette = ("#000000", "#ffffff") + ("#ffffff",) * (len(self.palette) - 2)

    async def save(self) -> bool:
        """Save the image to a file.

        Note that this method will never return if the user cancels the Save As dialog.
        """
        self.stop_action_in_progress()
        dialog_title = _("Save")
        if self.file_path:
            format_id = AnsiArtDocument.format_from_extension(self.file_path)
            # Note: `should_reload` implies information loss, but information loss doesn't imply `should_reload`.
            # In the case of write-only formats, this function should return False.
            should_reload = await self.confirm_information_loss_async(format_id)
            try:
                content = self.image.encode_to_format(format_id)
            except FormatWriteNotSupported as e:
                self.message_box(_("Save"), e.localized_message, "ok")
                return False
            if self.write_file_path(self.file_path, content, dialog_title):
                self.saved_undo_count = len(self.undos) # also set in reload_after_save
                if should_reload:
                    # Note: this fails to preview the lost information in the case
                    # of saving the old file in prompt_save_changes,
                    # because the document will be unloaded.
                    return self.reload_after_save(content, self.file_path)
                return True
            else:
                return False
        else:
            await self.save_as()
            # If the user cancels the Save As dialog, we'll never get here.
            return True

    def action_save_as(self) -> None:
        """Show the save as dialog, without waiting for it to close."""
        # Action must not await the dialog closing,
        # or else you'll never see the dialog in the first place!
        task = asyncio.create_task(self.save_as())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def save_as(self) -> None:
        """Save the image as a new file."""
        # stop_action_in_progress() will also be called once the dialog is closed,
        # which is more important than here, since the dialog isn't (currently) modal.
        # You could make a selection while the dialog is open, for example.
        self.stop_action_in_progress()
        self.close_windows("SaveAsDialogWindow, OpenDialogWindow")

        saved_future: asyncio.Future[None] = asyncio.Future()

        def handle_selected_file_path(file_path: str) -> None:
            format_id = AnsiArtDocument.format_from_extension(file_path)
            reload_after_save = False # in case of information loss on save, show it immediately
            def on_save_confirmed() -> None:
                async def async_on_save_confirmed() -> None:
                    self.stop_action_in_progress()
                    try:
                        content = self.image.encode_to_format(format_id)
                    except FormatWriteNotSupported as e:
                        self.message_box(_("Save As"), e.localized_message, "ok")
                        return

                    success = self.write_file_path(file_path, content, _("Save As"))
                    if success:
                        self.discard_backup() # for OLD file_path (must be done before changing self.file_path)
                        self.file_path = file_path
                        self.saved_undo_count = len(self.undos) # also set in reload_after_save
                        window.close()
                        if reload_after_save:
                            if not self.reload_after_save(content, file_path):
                                # I'm unsure about this.
                                # Also, if backup recovery is to happen below,
                                # it should happen in this case too I think.
                                return
                        saved_future.set_result(None)

                    # It's important to look for a backup file even for Save As, so that
                    # self.backup_checked_for is set; otherwise the backup will get left behind when closing,
                    # since it avoids deleting a backup file without first trying to recover from it (if it exists).
                    # TODO: Give a special message for clarity, or create numbered backup files to avoid conflict.
                    # See: commit message 74ffc34de4b789ec1da2ae2e08bf99f1bb4670c9 regarding numbered backup files.
                    self.recover_from_backup()
                # https://textual.textualize.io/blog/2023/02/11/the-heisenbug-lurking-in-your-async-code/
                task = asyncio.create_task(async_on_save_confirmed())
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)
            def after_confirming_any_information_loss(should_reload: bool) -> None:
                # Note: `should_reload` implies information loss, but information loss doesn't imply `should_reload`.
                # In the case of write-only formats, this callback should be passed False.
                nonlocal reload_after_save
                reload_after_save = should_reload
                if os.path.exists(file_path):
                    self.confirm_overwrite(file_path, on_save_confirmed)
                else:
                    on_save_confirmed()
            self.confirm_information_loss(format_id, after_confirming_any_information_loss)

        window = SaveAsDialogWindow(
            title=_("Save As"),
            handle_selected_file_path=handle_selected_file_path,
            selected_file_path=self.file_path,
            file_name=os.path.basename(self.file_path or _("Untitled")),
            auto_add_default_extension=".ans",
        )
        await self.mount(window)
        await saved_future

    def action_copy_to(self) -> None:
        """Save the selection to a file."""
        # DON'T stop_action_in_progress() here, because we want to keep the selection.
        self.close_windows("SaveAsDialogWindow, OpenDialogWindow")

        if self.get_selected_content() is None:
            # TODO: disable the menu item instead
            self.message_box(_("Copy To"), _("No selection."), "ok")
            return

        def handle_selected_file_path(file_path: str) -> None:

            def on_save_confirmed():
                async def async_on_save_confirmed():
                    try:
                        content = self.get_selected_content(file_path)
                    except FormatWriteNotSupported as e:
                        self.message_box(_("Copy To"), e.localized_message, "ok")
                        return
                    if content is None:
                        # confirm_overwrite dialog isn't modal, so we need to check again
                        self.message_box(_("Copy To"), _("No selection."), "ok")
                        return
                    if self.write_file_path(file_path, content, _("Copy To")):
                        window.close()
                # https://textual.textualize.io/blog/2023/02/11/the-heisenbug-lurking-in-your-async-code/
                task = asyncio.create_task(async_on_save_confirmed())
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)
            if os.path.exists(file_path):
                self.confirm_overwrite(file_path, on_save_confirmed)
            else:
                on_save_confirmed()

        window = SaveAsDialogWindow(
            title=_("Copy To"),
            handle_selected_file_path=handle_selected_file_path,
            selected_file_path=os.path.dirname(self.file_path or ""),
            auto_add_default_extension=".ans",
        )
        self.mount(window)

    def confirm_overwrite(self, file_path: str, callback: Callable[[], None]) -> None:
        """Asks the user if they want to overwrite a file."""
        message = _("%1 already exists.\nDo you want to replace it?", file_path)
        def handle_button(button: Button) -> None:
            if not button.has_class("yes"):
                return
            callback()
        self.message_box(_("Save As"), message, "yes/no", handle_button)

    def confirm_no_undo(self, callback: Callable[[], None]) -> None:
        """Asks the user to confirm that they want to continue with a permanent action."""
        # We have translations for "Do you want to continue?" via MS Paint,
        # but not for the rest of the message.
        message = _("This cannot be undone.") + "\n\n" + _("Do you want to continue?")
        def handle_button(button: Button) -> None:
            if not button.has_class("yes"):
                return
            callback()
        self.message_box(_("Paint"), message, "yes/no", handle_button)

    def prompt_save_changes(self, file_path: str, callback: Callable[[], None]) -> None:
        """Asks the user if they want to save changes to a file."""
        filename = os.path.basename(file_path)
        message = _("Save changes to %1?", filename)
        def handle_button(button: Button) -> None:
            if not button.has_class("yes") and not button.has_class("no"):
                return
            async def async_handle_button(button: Button):
                if button.has_class("yes"):
                    # If save fails, such as due to an unknown file extension,
                    # doing nothing (after the error message) is fine for New, but confusing for Open.
                    # It might be better to show Save As, but note that currently any file dialog is closed when opening one,
                    # regardless of type, with `self.close_windows("SaveAsDialogWindow, OpenDialogWindow")`
                    # It's at least better to return in case of an error, so that it doesn't
                    # tell you to save with a different filename whilst also permanently unloading the document.
                    # (For testing, open e.g. pyproject.toml, edit it, then hit New, Open, or Save.)
                    if not await self.save():
                        return
                callback()
            # https://textual.textualize.io/blog/2023/02/11/the-heisenbug-lurking-in-your-async-code/
            task = asyncio.create_task(async_handle_button(button))
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

        self.message_box(_("Paint"), message, "yes/no/cancel", handle_button)

    def confirm_lose_color_information(self, callback: Callable[[], None]) -> None:
        """Confirms discarding color information when saving as a plain text file."""
        message = _("Saving into this format may cause some loss of color information.") + "\n" + _("Do you want to continue?")
        def handle_button(button: Button) -> None:
            if button.has_class("yes"):
                callback()

        self.message_box(_("Paint"), message, "yes/no", handle_button)

    def confirm_lose_text_information(self, callback: Callable[[], None]) -> None:
        """Confirms discarding text information when saving as a plain text file."""
        message = _("Saving into this format will cause loss of any text information (letters, numbers, or symbols.)") + "\n" + _("Do you want to continue?")
        def handle_button(button: Button) -> None:
            if button.has_class("yes"):
                callback()

        self.message_box(_("Paint"), message, "yes/no", handle_button)

    def confirm_save_non_openable_file(self, callback: Callable[[], None]) -> None:
        """Confirms saving into a format that can only be saved, not opened."""
        message = _("This format can only be saved, not opened.") + "\n" + _("Do you want to continue?")
        def handle_button(button: Button) -> None:
            if button.has_class("yes"):
                callback()

        self.message_box(_("Paint"), message, "yes/no", handle_button)

    def confirm_information_loss(self, format_id: str | None, callback: Callable[[bool], None]) -> None:
        """Confirms discarding information when saving as a particular format. Callback variant. Never calls back if unconfirmed.

        The callback argument is whether there's information loss AND the file is openable.
        This is used to determine whether the file should be reloaded to show the information loss.
        It can't be reloaded if it's not openable.
        Some formats like PDF (currently) are color-only and can't be opened.
        """
        # TODO: don't warn if the information is not present
        # Note: image formats will lose any FOREGROUND color information.
        # This could be considered part of the text information, but could be mentioned.
        # Also, it could be confusing if a file uses a lot of full block characters (█).
        non_openable = format_id in ("HTML", "RICH_CONSOLE_MARKUP") or (format_id in Image.SAVE and not format_id in Image.OPEN)
        supports_text_and_color = format_id in ("ANSI", "SVG", "HTML", "RICH_CONSOLE_MARKUP", "IRC")
        # Note: "IRC" format supports text and color, but only limited colors,
        # so it still needs a warning.
        if format_id in ["PLAINTEXT", "IRC"]:
            self.confirm_lose_color_information(lambda: callback(True))
        elif format_id in SAVE_DISABLED_FORMATS:
            # We will show an error when attempting to encode.
            # Any warning here would just be annoying preamble to the error.
            callback(False)
        elif supports_text_and_color:
            # This is handled before Pillow's image formats, so that bespoke format support overrides Pillow.
            if non_openable:
                self.confirm_save_non_openable_file(lambda: callback(False))
            else:
                callback(False)
        elif format_id in Image.SAVE:
            # Image formats Pillow supports for writing
            if non_openable:
                self.confirm_save_non_openable_file(lambda: self.confirm_lose_text_information(lambda: callback(False)))
            else:
                self.confirm_lose_text_information(lambda: callback(True))
        else:
            # Read-only format or unknown format
            # An error message will be shown when attempting to encode.
            callback(False)

    async def confirm_information_loss_async(self, format_id: str | None) -> bool:
        """Confirms discarding information when saving as a particular format. Awaitable variant, which uses the callback variant."""
        future = asyncio.get_running_loop().create_future()
        self.confirm_information_loss(format_id, lambda result: future.set_result(result))
        return await future

    def is_document_modified(self) -> bool:
        """Returns whether the document has been modified since the last save."""
        return len(self.undos) != self.saved_undo_count

    def discard_backup(self) -> None:
        """Deletes the backup file, if it exists."""
        backup_file_path = self.get_backup_file_path()
        if self.backup_checked_for != backup_file_path:
            # Avoids discarding Untitled.ans~ on startup.
            print(f"Not discarding backup {backup_file_path!r} because it doesn't match the backup file checked for: {self.backup_checked_for!r}")
            return
        print("Discarding backup (if it exists):", backup_file_path)
        # import traceback
        # traceback.print_stack()
        try:
            os.remove(backup_file_path)
        except FileNotFoundError:
            pass
        except PermissionError:
            # This can happen when running with
            # `python -m src.textual_paint.paint /root/some_file_which_can_be_nonexistent`
            # (and then exiting)
            # If we don't have permission to delete the backup file,
            # then we probably didn't have permission to create it,
            # so it's not a big deal if we can't delete it.
            pass
        except Exception as e:
            self.message_box(_("Paint"), _("An unexpected error occurred while deleting the backup file %1.", backup_file_path), "ok", error=e)

    def discard_backup_and_exit(self) -> None:
        """Exit the program immediately, deleting the backup file."""
        self.discard_backup()
        self.exit()

    def action_exit(self) -> None:
        """Exit the program, prompting to save changes if necessary."""
        if self.is_document_modified():
            self.prompt_save_changes(self.file_path or _("Untitled"), self.discard_backup_and_exit)
        else:
            self.discard_backup_and_exit()

    def action_reload(self) -> None:
        """Reload the program, prompting to save changes if necessary."""
        # restart_program() calls discard_backup()
        if self.is_document_modified():
            self.prompt_save_changes(self.file_path or _("Untitled"), restart_program)
        else:
            restart_program()

    def action_update_screenshot(self) -> None:
        """Update the screenshot on the readme."""
        folder = os.path.join(os.path.dirname(__file__), "..", "..")
        self.save_screenshot(filename="screenshot.svg", path=folder)

    def message_box(self,
        title: str,
        message: Widget|str,
        button_types: str = "ok",
        callback: Callable[[Button], None]|None = None,
        icon_widget: Widget|None = None,
        error: Exception|None = None,
    ) -> None:
        """Show a warning message box with the given title, message, and buttons."""

        # Must not be a default argument, because it needs a fresh copy each time,
        # or it won't show up.
        if icon_widget is None:
            icon_widget = get_warning_icon()

        # self.close_windows("#message_box")

        self.bell()

        def handle_button(button: Button) -> None:
            # TODO: this is not different or useful enough from DialogWindow's
            # handle_button to justify
            # It's a difference in name, and an automatic close
            if callback:
                callback(button)
            window.close()
        window = MessageBox(
            # id="message_box",
            title=title,
            icon_widget=icon_widget,
            message=message,
            error=error,
            button_types=button_types,
            handle_button=handle_button,
        )
        self.mount(window)

    def open_from_file_path(self, file_path: str, opened_callback: Callable[[], None]) -> None:
        """Opens the given file for editing, prompting to save changes if necessary."""

        # First, check if the file is already open.
        # We can't use os.path.samefile because it doesn't provide
        # enough granularity to distinguish which file got an error.
        # It shouldn't error if the current file was deleted.
        # - It may be deleted in a file manager, which should be fine.
        # - This also used to happen when opening the backup file corresponding to the current file;
        #   it got discarded immediately after opening it, since it "belonged" to the now-closed file;
        #   now that's prevented by checking if the backup file is being opened before discarding it,
        #   and also backup files are now hidden in the file dialogs (though you can type the name manually).
        # But if the file to be opened was deleted,
        # then it should show an error message (although it would anyways when trying to read the file).
        if self.file_path:
            current_file_stat = None
            opened = False
            try:
                current_file_stat = os.stat(self.file_path)
                try:
                    file_to_be_opened_stat = os.stat(file_path)
                    if os.path.samestat(current_file_stat, file_to_be_opened_stat):
                        opened = True
                        return
                except FileNotFoundError:
                    self.message_box(_("Open"), file_path + "\n" + _("File not found.") + "\n" + _("Please verify that the correct path and file name are given."), "ok")
                    return
                except Exception as e:
                    self.message_box(_("Open"), _("An unknown error occurred while accessing %1.", file_path), "ok", error=e)
                    return
            except FileNotFoundError:
                pass
            except Exception as e:
                self.message_box(_("Open"), _("An unknown error occurred while accessing %1.", self.file_path), "ok", error=e)
                return
            # It's generally bad practice to invoke a callback within a try block,
            # because it can lead to unexpected behavior if the callback throws an exception,
            # such as the exception being silently swallowed, especially if some cases `pass`.
            if opened:
                opened_callback()
        try:
            if os.path.getsize(file_path) > MAX_FILE_SIZE:
                self.message_box(_("Open"), _("The file is too large to open."), "ok")
                return
            with open(file_path, "rb") as f:
                content = f.read()  # f is out of scope in go_ahead()
                def go_ahead():
                    # Note: exceptions handled outside of this function (UnicodeDecodeError, UnidentifiedImageError, FormatReadNotSupported)
                    new_image = AnsiArtDocument.decode_based_on_file_extension(content, file_path)

                    # action_new handles discarding the backup, and recovering from Untitled.ans~, by default
                    # but we need to 1. handle the case where the backup is the file to be opened,
                    # and 2. recover from <file to be opened>.ans~ instead of Untitled.ans~
                    # so manage_backup=False prevents these behaviors.
                    opening_backup = False
                    try:
                        backup_file_path = self.get_backup_file_path()
                        # print("Comparing files:", file_path, backup_file_path)
                        if os.path.samefile(file_path, backup_file_path):
                            print("Not discarding backup because it is now open in the editor:", backup_file_path)
                            opening_backup = True
                    except FileNotFoundError:
                        pass
                    except OSError as e:
                        print("Error comparing files:", e)
                    if not opening_backup:
                        self.discard_backup()

                    self.action_new(force=True, manage_backup=False)
                    self.canvas.image = self.image = new_image
                    self.canvas.refresh(layout=True)
                    self.file_path = file_path
                    self.update_palette_from_format_id(AnsiArtDocument.format_from_extension(file_path))
                    # Should this set self.saved_undo_count?
                    # I guess it's probably always 0 at this point, right?
                    opened_callback()
                    self.recover_from_backup()
                if self.is_document_modified():
                    self.prompt_save_changes(self.file_path or _("Untitled"), go_ahead)
                else:
                    go_ahead()
        except FileNotFoundError:
            self.message_box(_("Open"), file_path + "\n" + _("File not found.") + "\n" + _("Please verify that the correct path and file name are given."), "ok")
        except IsADirectoryError:
            self.message_box(_("Open"), file_path + "\n" + _("Invalid file."), "ok")
        except PermissionError:
            self.message_box(_("Open"), file_path + "\n" + _("Access denied."), "ok")
        except UnicodeDecodeError:
            self.message_box(_("Open"), file_path + "\n" + _("Paint cannot read this file.") + "\n" + _("Unexpected file format."), "ok")
        except UnidentifiedImageError as e:
            self.message_box(_("Open"), _("This is not a valid bitmap file, or its format is not currently supported."), "ok", error=e)
        except FormatReadNotSupported as e:
            self.message_box(_("Open"), e.localized_message, "ok")
        except Exception as e:
            self.message_box(_("Open"), _("An unexpected error occurred while reading %1.", file_path), "ok", error=e)

    def action_open(self) -> None:
        """Show dialog to open an image from a file."""

        def handle_selected_file_path(file_path: str) -> None:
            self.open_from_file_path(file_path, window.close)

        self.close_windows("SaveAsDialogWindow, OpenDialogWindow")
        window = OpenDialogWindow(
            title=_("Open"),
            handle_selected_file_path=handle_selected_file_path,
            selected_file_path=self.file_path,
        )
        self.mount(window)

    def action_paste_from(self) -> None:
        """Paste a file as a selection."""
        def handle_selected_file_path(file_path: str) -> None:
            # TODO: DRY error handling with open_from_file_path and reload_after_save
            try:
                if os.path.getsize(file_path) > MAX_FILE_SIZE:
                    self.message_box(_("Paste"), _("The file is too large to open."), "ok")
                    return
                with open(file_path, "r", encoding="utf-8") as f:
                    # TODO: handle pasting image files
                    self.paste(f.read())
                window.close()
            except UnicodeDecodeError:
                self.message_box(_("Open"), file_path + "\n" + _("Paint cannot read this file.") + "\n" + _("Unexpected file format."), "ok")
            except UnidentifiedImageError as e:
                self.message_box(_("Open"), _("This is not a valid bitmap file, or its format is not currently supported."), "ok", error=e)
            except FormatReadNotSupported as e:
                self.message_box(_("Open"), e.localized_message, "ok")
            except FileNotFoundError:
                self.message_box(_("Paint"), file_path + "\n" + _("File not found.") + "\n" + _("Please verify that the correct path and file name are given."), "ok")
            except IsADirectoryError:
                self.message_box(_("Paint"), file_path + "\n" + _("Invalid file."), "ok")
            except PermissionError:
                self.message_box(_("Paint"), file_path + "\n" + _("Access denied."), "ok")
            except Exception as e:
                self.message_box(_("Paint"), _("An unexpected error occurred while reading %1.", file_path), "ok", error=e)

        self.close_windows("SaveAsDialogWindow, OpenDialogWindow")
        window = OpenDialogWindow(
            title=_("Paste From"),
            handle_selected_file_path=handle_selected_file_path,
            selected_file_path=os.path.dirname(self.file_path or ""),
        )
        self.mount(window)

    def action_new(self, *, force: bool = False, manage_backup: bool = True) -> None:
        """Create a new image, discarding the backup file for the old file path, and undos/redos.

        This method is used as part of opening files as well,
        in which case force=True and recover=False,
        because prompting and recovering are handled outside.
        """
        if self.is_document_modified() and not force:
            def go_ahead():
                # Note: I doubt anything should use (force=False, manage_backup=False) but I'm passing it along.
                # TODO: would this be cleaner as an inner and outer function? what would I call the inner function?
                self.action_new(force=True, manage_backup=manage_backup)
            self.prompt_save_changes(self.file_path or _("Untitled"), go_ahead)
            return

        if manage_backup:
            self.discard_backup() # for OLD file_path (must be done before changing self.file_path)

        self.image = AnsiArtDocument(80, 24)
        self.canvas.image = self.image
        self.canvas.refresh(layout=True)
        self.file_path = None
        self.saved_undo_count = 0
        self.backup_saved_undo_count = 0
        self.undos = []
        self.redos = []
        self.preview_action = None
        # Following MS Paint's lead and resetting the color (but not the tool.)
        # It probably has to do with color modes.
        # TODO: Should this reset the palette?
        self.selected_bg_color = self.palette[0]
        self.selected_fg_color = self.palette[len(self.palette) // 2]
        self.selected_char = " "

        if manage_backup:
            self.recover_from_backup()

    def action_open_character_selector(self) -> None:
        """Show dialog to select a character."""
        self.close_windows("#character_selector_dialog")
        def handle_selected_character(character: str) -> None:
            self.selected_char = character
            window.close()
        window = CharacterSelectorDialogWindow(
            id="character_selector_dialog",
            handle_selected_character=handle_selected_character,
            selected_character=self.selected_char,
            title=_("Choose Character"),
        )
        self.mount(window)

    def action_swap_colors(self) -> None:
        """Swap the foreground and background colors."""
        self.selected_bg_color, self.selected_fg_color = self.selected_fg_color, self.selected_bg_color

    def action_edit_colors(self, color_palette_index: int|None = None, as_foreground: bool = False) -> None:
        """Show dialog to edit colors."""
        self.close_windows("#edit_colors_dialog")
        def handle_selected_color(color: str) -> None:
            if as_foreground:
                self.selected_fg_color = color
            else:
                self.selected_bg_color = color
            if color_palette_index is not None:
                # Effectively:
                # self.palette[color_palette_index] = color
                # But I made it a tuple for immutability guarantees.
                self.palette = self.palette[:color_palette_index] + (color,) + self.palette[color_palette_index + 1:]
            window.close()
        window = EditColorsDialogWindow(
            id="edit_colors_dialog",
            handle_selected_color=handle_selected_color,
            selected_color=self.selected_bg_color,
            title=_("Edit Colors"),
        )
        self.mount(window)

    def read_palette(self, file_content: str) -> tuple[str, ...]:
        """Read a GIMP Palette file."""
        format_name = "GIMP Palette"
        lines = file_content.splitlines()
        if lines[0] != format_name:
            raise ValueError(f"Not a {format_name}.")

        colors: list[str] = []
        line_index = 0
        while line_index + 1 < len(lines):
            line_index += 1
            line = lines[line_index]

            if line[0] == "#" or line == "":
                continue

            if line.startswith("Name:"):
                # palette.name = line.split(":", 1)[1].strip()
                continue

            if line.startswith("Columns:"):
                # palette.number_of_columns = int(line.split(":", 1)[1])
                continue

            r_g_b_name = re.match(
                r"^\s*([0-9]+)\s+([0-9]+)\s+([0-9]+)(?:\s+(.*))?$", line
            )
            if not r_g_b_name:
                raise ValueError(
                    f"Line {line_index + 1} doesn't match pattern of red green blue name."
                )

            red = int(r_g_b_name[1])
            green = int(r_g_b_name[2])
            blue = int(r_g_b_name[3])
            # name = r_g_b_name[4]
            colors.append(f"#{red:02x}{green:02x}{blue:02x}")

        return tuple(colors)

    def load_palette(self, file_content: str) -> None:
        """Load a palette from a GIMP palette file."""
        try:
            new_colors = self.read_palette(file_content)
        except ValueError as e:
            self.message_box(_("Paint"), _("Unexpected file format.") + "\n" + str(e), "ok")
            return
        except Exception as e:
            self.message_box(_("Paint"), _("Failed to read palette file."), "ok", error=e)
            return
        self.palette = new_colors[:len(self.palette)] + (new_colors[0],) * (len(self.palette) - len(new_colors))

    def action_get_colors(self) -> None:
        """Show a dialog to select a palette file to load."""

        def handle_selected_file_path(file_path: str) -> None:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.load_palette(f.read())
            except UnicodeDecodeError:
                # Extra detail because PAL files are not yet supported,
                # and would trigger this error if you try to open them.
                self.message_box(
                    _("Open"),
                    file_path + "\n" +
                        _("Paint cannot read this file.") + "\n" +
                        _("Unexpected file format.") + "\n" +
                        _("Only GIMP Palette files (*.gpl) are supported for now."),
                    "ok"
                )
            except FileNotFoundError:
                self.message_box(_("Open"), file_path + "\n" + _("File not found.") + "\n" + _("Please verify that the correct path and file name are given."), "ok")
            except IsADirectoryError:
                self.message_box(_("Open"), file_path + "\n" + _("Invalid file."), "ok")
            except PermissionError:
                self.message_box(_("Open"), file_path + "\n" + _("Access denied."), "ok")
            except Exception as e:
                self.message_box(_("Open"), _("An unexpected error occurred while reading %1.", file_path), "ok", error=e)
            else:
                window.close()

        self.close_windows("SaveAsDialogWindow, OpenDialogWindow")
        window = OpenDialogWindow(
            title=_("Get Colors"),
            handle_selected_file_path=handle_selected_file_path,
            selected_file_path=self.file_path,
        )
        self.mount(window)

    def action_save_colors(self) -> None:
        """Show a dialog to save the current palette to a file."""

        def handle_selected_file_path(file_path: str) -> None:
            color_lines: list[str] = []
            for color_str in self.palette:
                red, green, blue = Color.parse(color_str).rgb
                red = str(red).ljust(3, " ")
                green = str(green).ljust(3, " ")
                blue = str(blue).ljust(3, " ")
                name = ""
                color_line = f"{red} {green} {blue}   {name}"
                color_lines.append(color_line)

            newline = "\n" # f-strings are stupid, at least until Python 3.12
            # https://docs.python.org/3.12/whatsnew/3.12.html#pep-701-syntactic-formalization-of-f-strings
            palette_str = f"""GIMP Palette
Name: Saved Colors
Columns: {len(self.palette) // 2}
#
{newline.join(color_lines)}
"""

            palette_bytes = palette_str.encode("utf-8")
            # ensure .gpl extension
            if file_path[-4:].lower() != ".gpl":
                file_path += ".gpl"
            success = self.write_file_path(file_path, palette_bytes, _("Save Colors"))
            if success:
                window.close()

        self.close_windows("SaveAsDialogWindow, OpenDialogWindow")
        window = SaveAsDialogWindow(
            title=_("Save Colors"),
            handle_selected_file_path=handle_selected_file_path,
            selected_file_path=self.file_path,
        )
        self.mount(window)

    def action_print_preview(self) -> None:
        self.message_box(_("Paint"), "Not implemented.", "ok")
    def action_page_setup(self) -> None:
        self.message_box(_("Paint"), "Not implemented.", "ok")
    def action_print(self) -> None:
        self.message_box(_("Paint"), "Not implemented.", "ok")
    def action_send(self) -> None:
        self.message_box(_("Paint"), "Not implemented.", "ok")

    def action_set_as_wallpaper_tiled(self) -> None:
        """Tile the image as the wallpaper."""
        self.set_as_wallpaper(tiled=True)
    def action_set_as_wallpaper_centered(self) -> None:
        """Center the image as the wallpaper."""
        self.set_as_wallpaper(tiled=False)
    # worker thread helps keep the UI responsive
    @work(exclusive=True, thread=True)
    def set_as_wallpaper(self, tiled: bool) -> None:
        """Set the image as the wallpaper."""
        try:
            dir = os.path.join(get_config_dir("textual-paint"), "wallpaper")
            os.makedirs(dir, exist_ok=True)
            # svg = self.image.get_svg()
            # image_path = os.path.join(dir, "wallpaper.svg")
            # with open(image_path, "w", encoding="utf-8") as f:
            #     f.write(svg)

            # In order to reliably update the wallpaper,
            # change to a unique file path each time.
            # Simply alternating between two file paths
            # leads to re-using a cached image on Ubuntu 22.
            image_path = os.path.join(dir, f"wallpaper_{uuid4()}.png")
            # Clean up old files
            keep_files = 5
            files = os.listdir(dir)
            files.sort(key=lambda f: os.path.getmtime(os.path.join(dir, f)))
            for file in files[:-keep_files]:
                os.remove(os.path.join(dir, file))

            screen_size = self.get_screen_size()
            im = rasterize(self.image)
            im_w, im_h = im.size
            if tiled:
                new_im = Image.new('RGBA', screen_size)
                w, h = new_im.size
                for i in range(0, w, im_w):
                    for j in range(0, h, im_h):
                        new_im.paste(im, (i, j))
            else:
                new_im = Image.new('RGBA', screen_size)
                w, h = new_im.size
                new_im.paste(im, (w//2 - im_w//2, h//2 - im_h//2))
            new_im.save(image_path)
            if get_current_worker().is_cancelled:
                return # You'd have to be really fast with the menus to cancel it...
            set_wallpaper(image_path)
        except Exception as e:
            # self.message_box(_("Paint"), _("Failed to set the wallpaper."), "ok", error=e)
            # Because this is running in a thread, we can't directly access the UI.
            self.call_from_thread(self.message_box, _("Paint"), _("Failed to set the wallpaper."), "ok", error=e)
    def get_screen_size(self) -> Size:
        """Get the screen size."""
        # TODO: test DPI scaling
        try:
            # special macOS handling to avoid a Python rocket icon bouncing in the dock
            # (with screeninfo module it bounced; with tkinter it didn't, but still it stayed there indefinitely)
            if sys.platform == "darwin":
                # from AppKit import NSScreen
                # screen = NSScreen.mainScreen() # Shows rocket icon in dock...
                # size = screen.frame().size.width, screen.frame().size.height
                # return size

                from Quartz import CGDisplayBounds, CGMainDisplayID
                main_monitor = CGDisplayBounds(CGMainDisplayID())
                return Size(int(main_monitor.size.width), int(main_monitor.size.height))

            # from screeninfo import get_monitors
            # largest_area = 0
            # largest_monitor = None
            # for m in get_monitors():
            #     area = m.width * m.height
            #     if area > largest_area:
            #         largest_area = area
            #         largest_monitor = m
            # assert largest_monitor is not None, "No monitors found."
            # return largest_monitor.width, largest_monitor.height

            import tkinter
            root = tkinter.Tk()
            root.withdraw()
            size = Size(root.winfo_screenwidth(), root.winfo_screenheight())
            root.destroy()
            return size
        except Exception as e:
            print("Failed to get screen size:", e)
            return Size(1920, 1080)

    def action_recent_file(self) -> None:
        self.message_box(_("Paint"), "Not implemented.", "ok")

    def action_cut(self) -> None:
        """Cut the selection to the clipboard."""
        if self.action_copy():
            self.action_clear_selection()

    def get_selected_content(self, file_path: str|None = None) -> bytes | None:
        """Returns the content of the selection, or underlying the selection if it hasn't been cut out yet.

        For a textbox, returns the selected text within the textbox. May include ANSI escape sequences, either way.

        Raises FormatWriteNotSupported if the file_path implies a format that can't be encoded.
        Defaults to ANSI if `file_path` is None (or empty string).
        """
        sel = self.image.selection
        if sel is None:
            return None
        had_contained_image = sel.contained_image is not None
        try:
            if sel.contained_image is None:
                # Temporarily copy underlying image.
                # Don't want to make an undo state, unlike when cutting out a selection when you drag it.
                sel.copy_from_document(self.image)
                assert sel.contained_image is not None
            if sel.textbox_mode:
                text = selected_text(sel).encode("utf-8")
            else:
                format_id = AnsiArtDocument.format_from_extension(file_path) if file_path else "ANSI"
                text = sel.contained_image.encode_to_format(format_id)
        finally:
            if not had_contained_image:
                sel.contained_image = None
        return text

    def action_copy(self, from_ctrl_c: bool = False) -> bool:
        """Copy the selection to the clipboard."""
        try:
            content = self.get_selected_content()
            if content is None:
                if from_ctrl_c:
                    message = "Press Ctrl+Q to quit."
                    self.get_widget_by_id("status_text", Static).update(message)
                return False
            # TODO: avoid redundant encoding/decoding, if it's not too much trouble to make things bytes|str.
            text = content.decode("utf-8")
            # TODO: Copy as other formats. No Python libraries support this well yet.
            import pyperclip  # type: ignore
            pyperclip.copy(text)
        except Exception as e:
            self.message_box(_("Paint"), _("Failed to copy to the clipboard."), "ok", error=e)
            return False
        return True

    def action_paste(self) -> None:
        """Paste the clipboard (ANSI art allowed), either as a selection, or into a textbox."""
        try:
            # TODO: paste other formats. No Python libraries support this well yet.
            import pyperclip  # type: ignore
            text: str = pyperclip.paste()
        except Exception as e:
            self.message_box(_("Paint"), _("Error getting the Clipboard Data!"), "ok", error=e)
            return
        if not text:
            return
        self.paste(text)

    def paste(self, text: str) -> None:
        """Paste the given text (ANSI art allowed), either as a selection, or into a textbox."""
        if self.image.selection and self.image.selection.textbox_mode:
            # paste into textbox
            pasted_image = AnsiArtDocument.from_text(text, default_bg=self.selected_bg_color, default_fg=self.selected_fg_color)
            textbox = self.image.selection
            assert textbox.contained_image is not None
            paste_region = Region(*textbox.text_selection_start, pasted_image.width, pasted_image.height)
            if paste_region.right > textbox.region.width or paste_region.bottom > textbox.region.height:
                self.message_box(_("Paint"), _("Not enough room to paste text.") + "\n\n" + _("Enlarge the text area and try again."), "ok")
                return
            textbox.contained_image.copy_region(source=pasted_image, target_region=paste_region)
            textbox.textbox_edited = True
            self.canvas.refresh_scaled_region(textbox.region)
            return
        # paste as selection
        pasted_image = AnsiArtDocument.from_text(text)
        def do_the_paste() -> None:
            self.stop_action_in_progress()
            # paste at top left corner of viewport
            x: int = max(0, min(self.image.width - 1, int(self.editing_area.scroll_x // self.magnification)))
            y: int = max(0, min(self.image.height - 1, int(self.editing_area.scroll_y // self.magnification)))
            self.image.selection = Selection(Region(x, y, pasted_image.width, pasted_image.height))
            self.image.selection.contained_image = pasted_image
            self.image.selection.pasted = True  # create undo state when finalizing selection
            self.canvas.refresh_scaled_region(self.image.selection.region)
            self.selected_tool = Tool.select
        if pasted_image.width > self.image.width or pasted_image.height > self.image.height:
            # "bitmap" is inaccurate for ANSI art, but it's what MS Paint says, so we have translation coverage.
            message = _("The image in the clipboard is larger than the bitmap.") + "\n" + _("Would you like the bitmap enlarged?")
            def handle_button(button: Button) -> None:
                if button.has_class("yes"):
                    self.resize_document(max(pasted_image.width, self.image.width), max(pasted_image.height, self.image.height))
                    do_the_paste()
                elif button.has_class("no"):
                    do_the_paste()

            title = get_windows_icon_markup() + " " + _("Paint")
            self.message_box(title, message, "yes/no/cancel", handle_button, icon_widget=get_question_icon())
        else:
            do_the_paste()

    def action_select_all(self) -> None:
        """Select the entire image, or in a textbox, all the text."""
        if self.image.selection and self.image.selection.textbox_mode:
            assert self.image.selection.contained_image is not None
            self.image.selection.text_selection_start = Offset(0, 0)
            self.image.selection.text_selection_end = Offset(self.image.selection.contained_image.width - 1, self.image.selection.contained_image.height - 1)
            self.canvas.refresh_scaled_region(self.image.selection.region)
        else:
            self.stop_action_in_progress()
            self.image.selection = Selection(Region(0, 0, self.image.width, self.image.height))
            self.canvas.refresh()
            self.selected_tool = Tool.select

    def action_text_toolbar(self) -> None:
        self.message_box(_("Paint"), "Not implemented.", "ok")

    def action_normal_size(self) -> None:
        """Zoom to 1x."""
        self.magnification = 1

    def action_large_size(self) -> None:
        """Zoom to 4x."""
        self.magnification = 4

    def action_custom_zoom(self) -> None:
        """Show dialog to set zoom level."""
        self.close_windows("#zoom_dialog")
        def handle_button(button: Button) -> None:
            if button.has_class("ok"):
                radio_button = window.content.query_one(RadioSet).pressed_button
                assert radio_button is not None
                assert radio_button.id is not None
                self.magnification = int(radio_button.id.split("_")[1])
                window.close()
            else:
                window.close()
        window = DialogWindow(
            id="zoom_dialog",
            title=_("Custom Zoom"),
            handle_button=handle_button,
        )
        window.content.mount(
            Vertical(
                Horizontal(
                    Static(_("Current zoom:")),
                    Static(str(self.magnification * 100) + "%"),
                ),
                RadioSet(
                    RadioButton(_("100%"), id="value_1"),
                    RadioButton(_("200%"), id="value_2"),
                    RadioButton(_("400%"), id="value_4"),
                    RadioButton(_("600%"), id="value_6"),
                    RadioButton(_("800%"), id="value_8"),
                    classes="autofocus",
                )
            ),
            Container(
                Button(_("OK"), classes="ok submit", variant="primary"),
                Button(_("Cancel"), classes="cancel"),
                classes="buttons",
            )
        )
        window.content.query_one("#value_" + str(self.magnification), RadioButton).value = True
        window.content.query_one(RadioSet).border_title = _("Zoom to")
        def reorder_radio_buttons() -> None:
            """Visually reorder the radio buttons to top-down, left-right.

            (If I reorder them in the DOM, the navigation order won't be right.)

            This needs to be run after the buttons are mounted so that their positions are known.
            """
            radio_buttons = window.content.query(RadioButton)
            radio_button_absolute_positions = [radio_button.region.offset for radio_button in radio_buttons]
            # print("radio_button_absolute_positions", radio_button_absolute_positions)
            order = [0, 3, 1, 4, 2]
            radio_button_absolute_target_positions = [radio_button_absolute_positions[order[i]] for i in range(len(radio_buttons))]
            for radio_button, radio_button_absolute_position, radio_button_absolute_target_position in zip(radio_buttons, radio_button_absolute_positions, radio_button_absolute_target_positions):
                relative_position = radio_button_absolute_target_position - radio_button_absolute_position
                # print(radio_button, relative_position)
                radio_button.styles.offset = relative_position
        self.mount(window)
        # TODO: avoid flash of incorrect ordering by doing this before rendering but after layout
        self.call_after_refresh(reorder_radio_buttons)

    def action_toggle_grid(self) -> None:
        """Toggle the grid setting. Note that it's only shown at 4x zoom or higher."""
        self.show_grid = not self.show_grid

    def action_toggle_thumbnail(self) -> None:
        self.message_box(_("Paint"), "Not implemented.", "ok")

    def action_view_bitmap(self) -> None:
        """Shows the image in full-screen, without the UI."""
        self.cancel_preview()
        self.toggle_class("view_bitmap")
        if self.has_class("view_bitmap"):
            # entering View Bitmap mode
            self.old_scroll_offset = self.editing_area.scroll_offset
            self.canvas.magnification = 1 # without setting self.magnification, so we can restore the canvas to the current setting
            # Keep the left/top of the image in place in the viewport, when the image is larger than the viewport.
            adjusted_x = self.editing_area.scroll_x // self.magnification
            adjusted_y = self.editing_area.scroll_y // self.magnification
            self.editing_area.scroll_to(adjusted_x, adjusted_y, animate=False)
        else:
            # exiting View Bitmap mode
            self.canvas.magnification = self.magnification
            # This relies on the call_after_refresh in this method, for the magnification to affect the scrollable region.
            # I doubt this is considered part of the API contract, so it may break in the future.
            # Also, ideally we would update the screen in one go, without a flash of the wrong scroll position.
            self.editing_area.scroll_to(*self.old_scroll_offset, animate=False)

    def action_flip_rotate(self) -> None:
        """Show dialog to flip or rotate the image."""
        self.close_windows("#flip_rotate_dialog")
        def handle_button(button: Button) -> None:
            if button.has_class("ok"):
                if window.content.query_one("#flip_horizontal", RadioButton).value:
                    self.action_flip_horizontal()
                elif window.content.query_one("#flip_vertical", RadioButton).value:
                    self.action_flip_vertical()
                elif window.content.query_one("#rotate_by_angle", RadioButton).value:
                    radio_button = window.content.query_one("#angle", RadioSet).pressed_button
                    assert radio_button is not None, "There should always be a pressed button; one should've been selected initially."
                    assert radio_button.id is not None, "Each radio button should have been given an ID."
                    angle = int(radio_button.id.split("_")[-1])
                    self.action_rotate_by_angle(angle)
            window.close()
        window = DialogWindow(
            id="flip_rotate_dialog",
            title=_("Flip/Rotate"),
            handle_button=handle_button,
        )
        window.content.mount(
            Container(
                RadioSet(
                    RadioButton(_("Flip horizontal"), id="flip_horizontal", classes="autofocus"),
                    RadioButton(_("Flip vertical"), id="flip_vertical"),
                    RadioButton(_("Rotate by angle"), id="rotate_by_angle"),
                    classes="autofocus",
                    id="flip_rotate_radio_set",
                ),
                RadioSet(
                    RadioButton(_("90°"), id="angle_90"),
                    RadioButton(_("180°"), id="angle_180"),
                    RadioButton(_("270°"), id="angle_270"),
                    classes="autofocus",
                    id="angle",
                ),
                id="flip_rotate_fieldset",
                classes="fieldset",
            ),
            Container(
                Button(_("OK"), classes="ok submit", variant="primary"),
                Button(_("Cancel"), classes="cancel"),
                classes="buttons",
            )
        )
        window.content.query_one("#flip_rotate_fieldset", Container).border_title = _("Flip or rotate")
        window.content.query_one("#flip_horizontal", RadioButton).value = True
        window.content.query_one("#angle_90", RadioButton).value = True
        self.mount(window)

    @on(RadioSet.Changed, "#flip_rotate_radio_set")
    def conditionally_enable_angle_radio_buttons(self, event: RadioSet.Changed) -> None:
        """Enable/disable the angle radio buttons based on the logically-outer radio selection."""
        self.query_one("#angle", RadioSet).disabled = event.pressed.id != "rotate_by_angle"

    def action_flip_horizontal(self) -> None:
        """Flip the image horizontally."""

        action = Action(_("Flip horizontal"), Region(0, 0, self.image.width, self.image.height))
        action.is_full_update = True
        action.update(self.image)
        self.add_action(action)

        source = AnsiArtDocument(self.image.width, self.image.height)
        source.copy(self.image)
        for y in range(self.image.height):
            for x in range(self.image.width):
                self.image.ch[y][self.image.width - x - 1] = source.ch[y][x]
                self.image.fg[y][self.image.width - x - 1] = source.fg[y][x]
                self.image.bg[y][self.image.width - x - 1] = source.bg[y][x]
        self.canvas.refresh()

    def action_flip_vertical(self) -> None:
        """Flip the image vertically."""

        action = Action(_("Flip vertical"), Region(0, 0, self.image.width, self.image.height))
        action.is_full_update = True
        action.update(self.image)
        self.add_action(action)

        source = AnsiArtDocument(self.image.width, self.image.height)
        source.copy(self.image)
        for y in range(self.image.height):
            for x in range(self.image.width):
                self.image.ch[self.image.height - y - 1][x] = source.ch[y][x]
                self.image.fg[self.image.height - y - 1][x] = source.fg[y][x]
                self.image.bg[self.image.height - y - 1][x] = source.bg[y][x]
        self.canvas.refresh()

    def action_rotate_by_angle(self, angle: int) -> None:
        """Rotate the image by the given angle, one of 90, 180, or 270."""
        action = Action(_("Rotate by angle"), Region(0, 0, self.image.width, self.image.height))
        action.is_full_update = True
        action.update(self.image)
        self.add_action(action)

        source = AnsiArtDocument(self.image.width, self.image.height)
        source.copy(self.image)

        if angle != 180:
            self.image.resize(self.image.height, self.image.width)

        for y in range(self.image.height):
            for x in range(self.image.width):
                if angle == 90:
                    self.image.ch[y][x] = source.ch[self.image.width - x - 1][y]
                    self.image.fg[y][x] = source.fg[self.image.width - x - 1][y]
                    self.image.bg[y][x] = source.bg[self.image.width - x - 1][y]
                elif angle == 180:
                    self.image.ch[y][x] = source.ch[self.image.height - y - 1][self.image.width - x - 1]
                    self.image.fg[y][x] = source.fg[self.image.height - y - 1][self.image.width - x - 1]
                    self.image.bg[y][x] = source.bg[self.image.height - y - 1][self.image.width - x - 1]
                elif angle == 270:
                    self.image.ch[y][x] = source.ch[x][self.image.height - y - 1]
                    self.image.fg[y][x] = source.fg[x][self.image.height - y - 1]
                    self.image.bg[y][x] = source.bg[x][self.image.height - y - 1]
        self.canvas.refresh(layout=True)

    def action_stretch_skew(self) -> None:
        """Open the stretch/skew dialog."""
        self.close_windows("#stretch_skew_dialog")
        def handle_button(button: Button) -> None:
            if button.has_class("ok"):
                horizontal_stretch = float(window.content.query_one("#horizontal_stretch", Input).value)
                vertical_stretch = float(window.content.query_one("#vertical_stretch", Input).value)
                horizontal_skew = float(window.content.query_one("#horizontal_skew", Input).value)
                vertical_skew = float(window.content.query_one("#vertical_skew", Input).value)
                self.action_stretch_skew_by(horizontal_stretch, vertical_stretch, horizontal_skew, vertical_skew)
            window.close()
        window = DialogWindow(
            id="stretch_skew_dialog",
            title=_("Stretch/Skew"),
            handle_button=handle_button,
        )
        try:
            file_name = "stretch_skew_icons_full_ascii.ans" if args.ascii_only else "stretch_skew_icons.ans"
            with open(os.path.join(os.path.dirname(__file__), file_name), encoding="utf-8") as f:
                icons_ansi = f.read()
                icons_doc = AnsiArtDocument.from_ansi(icons_ansi)
                icons_rich_markup = icons_doc.get_rich_console_markup()
                icons_rich_markup = icons_rich_markup.replace("on #004040", "").replace("on rgb(0,64,64)", "")
                icon_height = icons_doc.height // 4
                lines = icons_rich_markup.split("\n")
                icons: list[Text | str] = []
                for i in range(4):
                    icon_markup = "\n".join(lines[i * icon_height : (i + 1) * icon_height])
                    icons.append(Text.from_markup(icon_markup))
        except Exception as e:
            print("Failed to load icons for Stretch/Skew dialog:", repr(e))
            icons = [""] * 4
        window.content.mount(
            Container(
                Horizontal(
                    Static(icons[0], classes="stretch_skew_icon"),
                    Static(_("Horizontal:"), classes="left-label"),
                    Input(value="100", id="horizontal_stretch", classes="autofocus"),
                    Static(_("%"), classes="right-label"),
                ),
                Horizontal(
                    Static(icons[1], classes="stretch_skew_icon"),
                    Static(_("Vertical:"), classes="left-label"),
                    Input(value="100", id="vertical_stretch"),
                    Static(_("%"), classes="right-label"),
                ),
                id="stretch_fieldset",
                classes="fieldset",
            ),
            Container(
                Horizontal(
                    Static(icons[2], classes="stretch_skew_icon"),
                    Static(_("Horizontal:"), classes="left-label"),
                    Input(value="0", id="horizontal_skew"),
                    Static(_("Degrees"), classes="right-label"),
                ),
                Horizontal(
                    Static(icons[3], classes="stretch_skew_icon"),
                    Static(_("Vertical:"), classes="left-label"),
                    Input(value="0", id="vertical_skew"),
                    Static(_("Degrees"), classes="right-label"),
                ),
                id="skew_fieldset",
                classes="fieldset",
            ),
            Container(
                Button(_("OK"), classes="ok submit", variant="primary"),
                Button(_("Cancel"), classes="cancel"),
                classes="buttons",
            )
        )
        window.content.query_one("#stretch_fieldset", Container).border_title = _("Stretch")
        window.content.query_one("#skew_fieldset", Container).border_title = _("Skew")
        window.content.query_one("#horizontal_stretch", Input).value = "100"
        window.content.query_one("#vertical_stretch", Input).value = "100"
        window.content.query_one("#horizontal_skew", Input).value = "0"
        window.content.query_one("#vertical_skew", Input).value = "0"
        self.mount(window)

    def action_stretch_skew_by(self, horizontal_stretch: float, vertical_stretch: float, horizontal_skew: float, vertical_skew: float) -> None:
        """Stretch/skew the image by the given amounts."""

        # Convert units
        horizontal_stretch = horizontal_stretch / 100
        vertical_stretch = vertical_stretch / 100
        horizontal_skew = math.radians(horizontal_skew)
        vertical_skew = math.radians(vertical_skew)

        # Record original state for undo
        action = Action(_("Stretch/skew"), Region(0, 0, self.image.width, self.image.height))
        action.is_full_update = True
        action.update(self.image)
        self.add_action(action)

        # Record original state for the transform (yes this is a bit inefficient)
        # (technically we could use action.sub_image_before)
        source = AnsiArtDocument(self.image.width, self.image.height)
        source.copy(self.image)

        w = source.width * horizontal_stretch
        h = source.height * vertical_stretch

        # Find bounds of transformed image, from each corner
        bb_min_x = float("inf")
        bb_max_x = float("-inf")
        bb_min_y = float("inf")
        bb_max_y = float("-inf")
        for x01, y01 in ((0, 0), (0, 1), (1, 0), (1, 1)):
            x = math.tan(-horizontal_skew) * h * x01 + w * y01
            y = math.tan(-vertical_skew) * w * y01 + h * x01
            bb_min_x = min(bb_min_x, x)
            bb_max_x = max(bb_max_x, x)
            bb_min_y = min(bb_min_y, y)
            bb_max_y = max(bb_max_y, y)

        bb_x = bb_min_x
        bb_y = bb_min_y
        bb_w = bb_max_x - bb_min_x
        bb_h = bb_max_y - bb_min_y

        # self.image.resize(0, 0) # clear the image
        self.image.resize(max(1, int(bb_w)), max(1, int(bb_h)))

        # Reverse transformation matrix values
        x_scale = 1 / horizontal_stretch
        v_skew = -vertical_skew
        h_skew = -horizontal_skew
        y_scale = 1 / vertical_stretch

        for y in range(self.image.height):
            for x in range(self.image.width):
                # Apply inverse transformation
                sample_x = x_scale * x - math.tan(h_skew) * y + bb_x
                sample_y = -math.tan(v_skew) * x + y_scale * y + bb_y

                # Convert to integer coordinates
                # round() causes artifacts where for instance a 200% stretch will result in a 3-1-3-1 pattern instead of 2-2-2-2
                sample_x = int(sample_x)
                sample_y = int(sample_y)

                if 0 <= sample_x < source.width and 0 <= sample_y < source.height:
                    self.image.ch[y][x] = source.ch[sample_y][sample_x]
                    self.image.fg[y][x] = source.fg[sample_y][sample_x]
                    self.image.bg[y][x] = source.bg[sample_y][sample_x]
                else:
                    self.image.ch[y][x] = " "
                    self.image.fg[y][x] = "#000000" # default_fg — if this was a variable, would it allocate less strings?
                    self.image.bg[y][x] = "#ffffff" # default_bg
        self.canvas.refresh(layout=True)

    def action_invert_colors_unless_should_switch_focus(self) -> None:
        """Try to distinguish between Tab and Ctrl+I scenarios."""
        # pretty simple heuristic, but seems effective
        # I didn't make the dialogs modal, but it's OK if this
        # assumes you'll be interacting with the modal rather than the canvas
        # (even though you can, for instance, draw on the canvas while the dialog is open)
        if self.query(DialogWindow):
            # self.action_focus_next()
            # DialogWindow has a special focus_next action that wraps within the dialog.
            # await self.run_action("focus_next", self.query_one(DialogWindow))
            # There may be multiple dialogs open, so we need to find the one that's focused.
            node: DOMNode | None = self.focused
            while node is not None:
                if isinstance(node, DialogWindow):
                    # await self.run_action("focus_next", node)
                    node.action_focus_next()
                    return
                node = node.parent
            self.action_focus_next()
        else:
            self.action_invert_colors()

    def action_invert_colors(self) -> None:
        """Invert the colors of the image or selection."""
        self.cancel_preview()
        sel = self.image.selection
        if sel:
            if sel.textbox_mode:
                return
            if sel.contained_image is None:
                self.extract_to_selection()
                assert sel.contained_image is not None
            # Note: no undo state will be created if the selection is already extracted
            sel.contained_image.invert()
            self.canvas.refresh_scaled_region(sel.region)
        else:
            # TODO: DRY undo state creation
            action = Action(_("Invert Colors"), Region(0, 0, self.image.width, self.image.height))
            action.update(self.image)
            self.add_action(action)

            self.image.invert()
            self.canvas.refresh()

    def resize_document(self, width: int, height: int) -> None:
        """Resize the document, creating an undo state, and refresh the canvas."""
        self.cancel_preview()

        # NOTE: This function is relied on to create an undo even if the size doesn't change,
        # when recovering from a backup, and when reloading file content when losing information during Save As.
        # TODO: DRY undo state creation
        action = Action(_("Attributes"), Region(0, 0, self.image.width, self.image.height))
        action.is_full_update = True
        action.update(self.image)
        self.add_action(action)

        self.image.resize(width, height, default_bg=self.selected_bg_color, default_fg=self.selected_fg_color)

        self.canvas.refresh(layout=True)

    def action_attributes(self) -> None:
        """Show dialog to set the image attributes."""
        self.close_windows("#attributes_dialog")
        def handle_button(button: Button) -> None:
            if button.has_class("ok"):
                try:
                    width = int(window.content.query_one("#width_input", Input).value)
                    height = int(window.content.query_one("#height_input", Input).value)
                    if width < 1 or height < 1:
                        raise ValueError

                    self.resize_document(width, height)
                    window.close()

                except ValueError:
                    self.message_box(_("Attributes"), _("Please enter a positive integer."), "ok")
            else:
                window.close()
        window = DialogWindow(
            id="attributes_dialog",
            title=_("Attributes"),
            handle_button=handle_button,
        )
        window.content.mount(
            Vertical(
                Horizontal(
                    Static(_("Width:")),
                    Input(id="width_input", value=str(self.image.width), classes="autofocus"),
                ),
                Horizontal(
                    Static(_("Height:")),
                    Input(id="height_input", value=str(self.image.height)),
                ),
            ),
            Container(
                Button(_("OK"), classes="ok submit", variant="primary"),
                Button(_("Cancel"), classes="cancel"),
                classes="buttons",
            )
        )
        self.mount(window)

    def action_clear_image(self) -> None:
        """Clear the image, creating an undo state."""
        # This could be simplified to use erase_region, but that would be marginally slower.
        # It could also be simplified to action_select_all+action_clear_selection,
        # but it's better to keep a meaningful name for the undo state.
        # TODO: DRY undo state creation
        self.cancel_preview()
        action = Action(_("Clear Image"), Region(0, 0, self.image.width, self.image.height))
        action.is_full_update = True
        action.update(self.image)
        self.add_action(action)

        for y in range(self.image.height):
            for x in range(self.image.width):
                self.image.ch[y][x] = " "
                self.image.fg[y][x] = "#000000"
                self.image.bg[y][x] = "#ffffff"

        self.canvas.refresh()

    def action_draw_opaque(self) -> None:
        """Toggles opaque/transparent selection mode."""
        self.message_box(_("Paint"), "Not implemented.", "ok")

    def action_help_topics(self) -> None:
        """Show the Help Topics dialog."""
        self.close_windows("#help_dialog")
        # "Paint Help" is the title in MS Paint,
        # but we don't have translations for that.
        # This works in English, but probably sounds weird in other languages.
        title = _("Paint") + " " + _("Help")
  
        title = get_help_icon_markup() + " " + title
        def handle_button(button: Button) -> None:
            window.close()
        window = DialogWindow(
            id="help_dialog",
            title=title,
            handle_button=handle_button,
            allow_maximize=True,
            allow_minimize=True,
        )
        help_text = get_help_text()
        window.content.mount(Container(Static(help_text, markup=False),  classes="help_text_container"))
        window.content.mount(Button(_("OK"), classes="ok submit"))
        self.mount(window)

    def action_about_paint(self) -> None:
        """Show the About Paint dialog."""
        self.close_windows("#about_paint_dialog")
        message = Static(f"""[b]Textual Paint[/b]

[i]MS Paint in your terminal.[/i]

[b]Version:[/b] {__version__}
[b]Author:[/b] [link=https://isaiahodhner.io/]Isaiah Odhner[/link]
[b]License:[/b] [link=https://github.com/1j01/textual-paint/blob/main/LICENSE.txt]MIT[/link]
[b]Source Code:[/b] [link=https://github.com/1j01/textual-paint]github.com/1j01/textual-paint[/link]
""")
        def handle_button(button: Button) -> None:
            window.close()
        window = MessageBox(
            id="about_paint_dialog",
            title=_("About Paint"),
            handle_button=handle_button,
            icon_widget=get_paint_icon(),
            message=message,
        )
        self.mount(window)

    def action_toggle_inspector(self) -> None:
        """Toggle the DOM inspector."""
        if not args.inspect_layout:
            return
        # importing the inspector adds instrumentation which can slow down startup
        from textual_paint.inspector import Inspector
        inspector = self.query_one(Inspector)
        inspector.display = not inspector.display
        if not inspector.display:
            inspector.picking = False

    def compose(self) -> ComposeResult:
        """Add our widgets."""
        yield Header()
        with Container(id="paint"):
            # I'm not supporting hotkeys for the top level menus, because I can't detect Alt.
            yield MenuBar([
                MenuItem(remove_hotkey(_("&File")), submenu=Menu([
                    MenuItem(_("&New\tCtrl+N"), self.action_new, 57600, description=_("Creates a new document.")),
                    MenuItem(_("&Open...\tCtrl+O"), self.action_open, 57601, description=_("Opens an existing document.")),
                    MenuItem(_("&Save\tCtrl+S"), self.action_save, 57603, description=_("Saves the active document.")),
                    MenuItem(_("Save &As..."), self.action_save_as, 57604, description=_("Saves the active document with a new name.")),
                    Separator(),
                    MenuItem(_("Print Pre&view"), self.action_print_preview, 57609, grayed=True, description=_("Displays full pages.")),
                    MenuItem(_("Page Se&tup..."), self.action_page_setup, 57605, grayed=True, description=_("Changes the page layout.")),
                    MenuItem(_("&Print...\tCtrl+P"), self.action_print, 57607, grayed=True, description=_("Prints the active document and sets printing options.")),
                    Separator(),
                    MenuItem(_("S&end..."), self.action_send, 37662, grayed=True, description=_("Sends a picture by using mail or fax.")),
                    Separator(),
                    MenuItem(_("Set As &Wallpaper (Tiled)"), self.action_set_as_wallpaper_tiled, 57677, description=_("Tiles this bitmap as the desktop wallpaper.")),
                    MenuItem(_("Set As Wa&llpaper (Centered)"), self.action_set_as_wallpaper_centered, 57675, description=_("Centers this bitmap as the desktop wallpaper.")),
                    Separator(),
                    MenuItem(_("Recent File"), self.action_recent_file, 57616, grayed=True, description=_("Opens this document.")),
                    Separator(),
                    # MenuItem(_("E&xit\tAlt+F4"), self.action_exit, 57665, description=_("Quits Paint.")),
                    MenuItem(_("E&xit\tCtrl+Q"), self.action_exit, 57665, description=_("Quits Paint.")),
                ])),
                MenuItem(remove_hotkey(_("&Edit")), submenu=Menu([
                    MenuItem(_("&Undo\tCtrl+Z"), self.action_undo, 57643, description=_("Undoes the last action.")),
                    MenuItem(_("&Repeat\tF4"), self.action_redo, 57644, description=_("Redoes the previously undone action.")),
                    Separator(),
                    MenuItem(_("Cu&t\tCtrl+X"), self.action_cut, 57635, description=_("Cuts the selection and puts it on the Clipboard.")),
                    MenuItem(_("&Copy\tCtrl+C"), self.action_copy, 57634, description=_("Copies the selection and puts it on the Clipboard.")),
                    MenuItem(_("&Paste\tCtrl+V"), self.action_paste, 57637, description=_("Inserts the contents of the Clipboard.")),
                    MenuItem(_("C&lear Selection\tDel"), self.action_clear_selection, 57632, description=_("Deletes the selection.")),
                    MenuItem(_("Select &All\tCtrl+A"), self.action_select_all, 57642, description=_("Selects everything.")),
                    Separator(),
                    MenuItem(_("C&opy To..."), self.action_copy_to, 37663, description=_("Copies the selection to a file.")),
                    MenuItem(_("Paste &From..."), self.action_paste_from, 37664, description=_("Pastes a file into the selection.")),
                ])),
                MenuItem(remove_hotkey(_("&View")), submenu=Menu([
                    MenuItem(_("&Tool Box\tCtrl+T"), self.action_toggle_tools_box, 59415, description=_("Shows or hides the tool box.")),
                    MenuItem(_("&Color Box\tCtrl+L"), self.action_toggle_colors_box, 59416, description=_("Shows or hides the color box.")),
                    MenuItem(_("&Status Bar"), self.action_toggle_status_bar, 59393, description=_("Shows or hides the status bar.")),
                    MenuItem(_("T&ext Toolbar"), self.action_text_toolbar, 37678, grayed=True, description=_("Shows or hides the text toolbar.")),
                    Separator(),
                    MenuItem(_("&Zoom"), submenu=Menu([
                        MenuItem(_("&Normal Size\tCtrl+PgUp"), self.action_normal_size, 37670, description=_("Zooms the picture to 100%.")),
                        MenuItem(_("&Large Size\tCtrl+PgDn"), self.action_large_size, 37671, description=_("Zooms the picture to 400%.")),
                        MenuItem(_("C&ustom..."), self.action_custom_zoom, 37672, description=_("Zooms the picture.")),
                        Separator(),
                        MenuItem(_("Show &Grid\tCtrl+G"), self.action_toggle_grid, 37677, description=_("Shows or hides the grid.")),
                        MenuItem(_("Show T&humbnail"), self.action_toggle_thumbnail, 37676, grayed=True, description=_("Shows or hides the thumbnail view of the picture.")),
                    ])),
                    MenuItem(_("&View Bitmap\tCtrl+F"), self.action_view_bitmap, 37673, description=_("Displays the entire picture.")),
                ])),
                MenuItem(remove_hotkey(_("&Image")), submenu=Menu([
                    MenuItem(_("&Flip/Rotate...\tCtrl+R"), self.action_flip_rotate, 37680, description=_("Flips or rotates the picture or a selection.")),
                    MenuItem(_("&Stretch/Skew...\tCtrl+W"), self.action_stretch_skew, 37681, description=_("Stretches or skews the picture or a selection.")),
                    MenuItem(_("&Invert Colors\tCtrl+I"), self.action_invert_colors, 37682, description=_("Inverts the colors of the picture or a selection.")),
                    MenuItem(_("&Attributes...\tCtrl+E"), self.action_attributes, 37683, description=_("Changes the attributes of the picture.")),
                    MenuItem(_("&Clear Image\tCtrl+Shft+N"), self.action_clear_image, 37684, description=_("Clears the picture or selection.")),
                    MenuItem(_("&Draw Opaque"), self.action_draw_opaque, 6868, grayed=True, description=_("Makes the current selection either opaque or transparent.")),
                ])),
                MenuItem(remove_hotkey(_("&Colors")), submenu=Menu([
                    MenuItem(_("&Get Colors..."), self.action_get_colors, 41749, description=_("Uses a previously saved palette of colors.")),
                    MenuItem(_("&Save Colors..."), self.action_save_colors, 41750, description=_("Saves the current palette of colors to a file.")),
                    MenuItem(_("&Edit Colors..."), self.action_edit_colors, 41751, description=_("Creates a new color.")),
                    # MenuItem(_("&Edit Colors..."), self.action_edit_colors, 6869, description=_("Creates a new color.")),
                ])),
                MenuItem(remove_hotkey(_("&Help")), submenu=Menu([
                    MenuItem(_("&Help Topics"), self.action_help_topics, 57670, description=_("Displays Help for the current task or command.")),
                    Separator(),
                    MenuItem(_("&About Paint"), self.action_about_paint, 57664, description=_("Displays program information, version number, and copyright.")),
                ])),
            ])
            yield Container(
                ToolsBox(id="tools_box"),
                Container(
                    Canvas(id="canvas"),
                    id="editing_area",
                ),
                id="main_horizontal_split",
            )
            yield ColorsBox(id="colors_box")
            yield Container(
                Static(_("For Help, click Help Topics on the Help Menu."), id="status_text"),
                Static(id="status_coords"),
                Static(id="status_dimensions"),
                id="status_bar",
            )
        if not args.inspect_layout:
            return
        # importing the inspector adds instrumentation which can slow down startup
        from textual_paint.inspector import Inspector
        inspector = Inspector()
        inspector.display = False
        yield inspector

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        # Image can be set from the outside, via CLI
        if not self.image_initialized:
            self.image = AnsiArtDocument(80, 24)
            self.image_initialized = True
        self.canvas = self.query_one("#canvas", Canvas)
        self.canvas.image = self.image
        self.editing_area = self.query_one("#editing_area", Container)
        self.query_one(HeaderIcon).icon = header_icon_text  # type: ignore

    def pick_color(self, x: int, y: int) -> None:
        """Select a color from the image."""
        if x < 0 or y < 0 or x >= self.image.width or y >= self.image.height:
            return
        self.selected_bg_color = self.image.bg[y][x]
        self.selected_fg_color = self.image.fg[y][x]
        self.selected_char = self.image.ch[y][x]

    def get_prospective_magnification(self) -> int:
        """Returns the magnification result on click with the Magnifier tool."""
        return self.return_to_magnification if self.magnification == 1 else 1

    def magnifier_click(self, x: int, y: int) -> None:
        """Zooms in or out on the image."""

        prev_magnification = self.magnification
        prospective_magnification = self.get_prospective_magnification()

        # TODO: fix flickering.
        # The canvas resize and scroll each cause a repaint.
        # I tried using a batch_update, but it prevented the layout recalculation
        # needed for the scroll to work correctly.
        # with self.batch_update():
        self.magnification = prospective_magnification
        self.canvas.magnification = self.magnification

        if self.magnification > prev_magnification:
            w = self.editing_area.size.width / self.magnification
            h = self.editing_area.size.height / self.magnification
            self.editing_area.scroll_to(
                (x - w / 2) * self.magnification / prev_magnification,
                (y - h / 2) * self.magnification / prev_magnification,
                animate=False,
            )
            # `scroll_to` uses `call_after_refresh`.
            # `_scroll_to` is the same thing but without call_after_refresh.
            # But it doesn't work correctly, because the layout isn't updated yet.
            # And if I call:
            # self.screen._refresh_layout()
            # beforehand, it's back to the flickering.
            # I also tried calling:
            # self.editing_area.refresh(layout=True, repaint=False)
            # But it's back to the incorrect scroll position.
            # self.editing_area._scroll_to(
            #     (x - w / 2) * self.magnification / prev_magnification,
            #     (y - h / 2) * self.magnification / prev_magnification,
            #     animate=False,
            # )

    def extract_to_selection(self, erase_underlying: bool = True) -> None:
        """Extracts image data underlying the selection from the document into the selection.

        This creates an undo state with the current tool's name, which should be Select or Free-Form Select.
        """
        sel = self.image.selection
        assert sel is not None, "extract_to_selection called without a selection"
        assert sel.contained_image is None, "extract_to_selection called after a selection was already extracted"
        # TODO: DRY action handling
        self.image_at_start = AnsiArtDocument(self.image.width, self.image.height)
        self.image_at_start.copy_region(self.image)
        action = Action(self.selected_tool.get_name())
        self.add_action(action)
        sel.copy_from_document(self.image)
        if erase_underlying:
            self.erase_region(sel.region, sel.mask)

        # TODO: Optimize the region storage for Text, Select, and Free-Form Select tools.
        # Right now I'm copying the whole image here, because later, when the selection is melded into the canvas,
        # it _implicitly updates_ the undo action, by changing the document without creating a new Action.
        # This is the intended behavior, in that it allows the user to undo the
        # selection and any changes to it as one action. But it's not efficient for large images.
        # I could:
        # - Update the region when melding to be the union of the two rectangles.
        # - Make Action support a list of regions, and add the new region on meld.
        # - Make Action support a list of sub-actions (or just one), and make meld a sub-action.
        # - Add a new Action on meld, but mark it for skipping when undoing, and skipping ahead to when redoing.

        # `affected_region = sel.region` doesn't encompass the new region when melding
        affected_region = Region(0, 0, self.image.width, self.image.height)

        action.region = affected_region
        action.region = action.region.intersection(Region(0, 0, self.image.width, self.image.height))
        action.update(self.image_at_start)
        self.canvas.refresh_scaled_region(affected_region)

    def on_canvas_tool_start(self, event: Canvas.ToolStart) -> None:
        """Called when the user starts drawing on the canvas."""
        event.stop()
        self.cancel_preview()

        self.mouse_gesture_cancelled = False

        if self.selected_tool == Tool.pick_color:
            self.pick_color(event.x, event.y)
            return

        if self.selected_tool == Tool.magnifier:
            self.magnifier_click(event.x, event.y)
            return

        self.mouse_at_start = Offset(event.x, event.y)
        self.mouse_previous = self.mouse_at_start
        self.color_eraser_mode = self.selected_tool == Tool.eraser and event.button == 3

        if self.selected_tool in [Tool.curve, Tool.polygon]:
            self.tool_points.append(Offset(event.x, event.y))
            if self.selected_tool == Tool.curve:
                self.make_preview(self.draw_current_curve)
            else:
                # polyline until finished
                self.make_preview(self.draw_current_polyline, show_dimensions_in_status_bar=True)
            return

        if self.selected_tool == Tool.free_form_select:
            self.tool_points = [Offset(event.x, event.y)]

        if self.selected_tool in [Tool.select, Tool.free_form_select, Tool.text]:
            sel = self.image.selection
            if sel and sel.region.contains_point(self.mouse_at_start):
                if self.selected_tool == Tool.text:
                    # Place cursor at mouse position
                    offset_in_textbox = Offset(*self.mouse_at_start) - sel.region.offset
                    # clamping isn't needed here, unlike while dragging
                    sel.text_selection_start = offset_in_textbox
                    sel.text_selection_end = offset_in_textbox
                    self.canvas.refresh_scaled_region(sel.region)
                    self.selecting_text = True
                    return
                # Start dragging the selection.
                self.selection_drag_offset = Offset(
                    sel.region.x - self.mouse_at_start.x,
                    sel.region.y - self.mouse_at_start.y,
                )
                if sel.contained_image:
                    # Already cut out, don't replace the image data.
                    # But if you hold Ctrl, stamp the selection.
                    if event.ctrl:
                        # If pasted, it needs an undo state.
                        # Otherwise, one should have been already created.
                        if sel.pasted:
                            sel.pasted = False # don't create undo when melding (TODO: rename flag or refactor)

                            action = Action("Paste")
                            self.add_action(action)
                            # The region must be the whole canvas, because when the selection
                            # is melded with the canvas, it could be anywhere.
                            # This could be optimized, see extract_to_selection.
                            action.region = Region(0, 0, self.image.width, self.image.height)
                            action.update(self.image)
                        sel.copy_to_document(self.image)
                        # Don't need to refresh canvas since selection occludes the affected region,
                        # and has the same content anyway, being a stamp.
                    return
                self.extract_to_selection(not event.ctrl)
                return
            self.meld_selection()
            return

        self.image_at_start = AnsiArtDocument(self.image.width, self.image.height)
        self.image_at_start.copy_region(self.image)
        action = Action(self.selected_tool.get_name())
        self.add_action(action)

        affected_region = None
        if self.selected_tool == Tool.pencil or self.selected_tool == Tool.brush:
            affected_region = self.stamp_brush(event.x, event.y)
        elif self.selected_tool == Tool.fill:
            affected_region = flood_fill(self.image, event.x, event.y, self.selected_char, self.selected_fg_color, self.selected_bg_color)

        if affected_region:
            action.region = affected_region
            action.region = action.region.intersection(Region(0, 0, self.image.width, self.image.height))
            action.update(self.image_at_start)
            self.canvas.refresh_scaled_region(affected_region)
        else:
            # Flood fill didn't affect anything.
            # Following MS Paint, we still created an undo action.
            # We need a region to avoid an error/warning when undoing.
            # But we don't need to refresh the canvas.
            action.region = Region(0, 0, 0, 0)

    def cancel_preview(self) -> None:
        """Revert the currently previewed action."""
        if self.preview_action:
            assert self.preview_action.region is not None, "region should have been initialized for preview_action"
            self.preview_action.undo(self.image)
            self.canvas.refresh_scaled_region(self.preview_action.region)
            self.preview_action = None
        if self.canvas.magnifier_preview_region:
            region = self.canvas.magnifier_preview_region
            self.canvas.magnifier_preview_region = None
            self.canvas.refresh_scaled_region(region)
        if self.canvas.select_preview_region:
            region = self.canvas.select_preview_region
            self.canvas.select_preview_region = None
            self.canvas.refresh_scaled_region(region)

        # To avoid saving with a tool preview as part of the image data,
        # or interrupting the user's flow by canceling the preview occasionally to auto-save a backup,
        # we postpone auto-saving the backup until the image is clean of any previews.
        if self.save_backup_after_cancel_preview:
            self.save_backup()
            self.save_backup_after_cancel_preview = False

    def image_has_preview(self) -> bool:
        """Return whether the image data contains a tool preview. The document should not be saved in this state."""
        return self.preview_action is not None
        # Regarding self.canvas.magnifier_preview_region, self.canvas.select_preview_region:
        # These previews are not stored in the image data, so they don't count.

    def make_preview(self, draw_proc: Callable[[], Region], show_dimensions_in_status_bar: bool = False) -> None:
        """Preview the result of a draw operation, using a temporary action. Optionally preview dimensions in status bar."""
        self.cancel_preview()
        image_before = AnsiArtDocument(self.image.width, self.image.height)
        image_before.copy_region(self.image)
        affected_region = draw_proc()
        if affected_region:
            self.preview_action = Action(self.selected_tool.get_name())
            self.preview_action.region = affected_region.intersection(Region(0, 0, self.image.width, self.image.height))
            self.preview_action.update(image_before)
            self.canvas.refresh_scaled_region(affected_region)
            if show_dimensions_in_status_bar:
                self.get_widget_by_id("status_dimensions", Static).update(
                    f"{self.preview_action.region.width}x{self.preview_action.region.height}"
                )

    def on_canvas_tool_preview_update(self, event: Canvas.ToolPreviewUpdate) -> None:
        """Called when the user is hovering over the canvas but not drawing yet."""
        event.stop()

        self.get_widget_by_id("status_coords", Static).update(f"{event.x},{event.y}")

        self.draw_tool_preview_on_canvas(Offset(event.x, event.y))

    def draw_tool_preview_on_canvas(self, mouse: Offset|None = None) -> None:
        """Update the tool preview on the canvas, if applicable."""
        self.cancel_preview()

        if self.selected_tool in [Tool.brush, Tool.pencil, Tool.eraser, Tool.curve, Tool.polygon]:
            if self.selected_tool == Tool.curve:
                self.make_preview(self.draw_current_curve)
            elif self.selected_tool == Tool.polygon:
                # polyline until finished
                self.make_preview(self.draw_current_polyline, show_dimensions_in_status_bar=True)
            elif mouse is not None:
                self.make_preview(lambda: self.stamp_brush(mouse.x, mouse.y))
        elif self.selected_tool == Tool.magnifier and mouse is not None:
            prospective_magnification = self.get_prospective_magnification()

            if prospective_magnification < self.magnification:
                return  # hide if clicking would zoom out

            # prospective viewport size in document coords
            w = self.editing_area.size.width // prospective_magnification
            h = self.editing_area.size.height // prospective_magnification

            rect_x1 = (mouse.x - w // 2)
            rect_y1 = (mouse.y - h // 2)

            # try to move rect into bounds without squishing
            rect_x1 = max(0, rect_x1)
            rect_y1 = max(0, rect_y1)
            rect_x1 = min(self.image.width - w, rect_x1)
            rect_y1 = min(self.image.height - h, rect_y1)

            rect_x2 = rect_x1 + w
            rect_y2 = rect_y1 + h

            # clamp rect to bounds (with squishing)
            rect_x1 = max(0, rect_x1)
            rect_y1 = max(0, rect_y1)
            rect_x2 = min(self.image.width, rect_x2)
            rect_y2 = min(self.image.height, rect_y2)

            rect_w = rect_x2 - rect_x1
            rect_h = rect_y2 - rect_y1
            rect_x = rect_x1
            rect_y = rect_y1

            self.canvas.magnifier_preview_region = Region(rect_x, rect_y, rect_w, rect_h)
            self.canvas.refresh_scaled_region(self.canvas.magnifier_preview_region)

    def on_canvas_tool_preview_stop(self, event: Canvas.ToolPreviewStop) -> None:
        """Called when the user stops hovering over the canvas (while previewing, not drawing)."""
        event.stop()
        # Curve and Polygon persist when the mouse leaves the canvas,
        # since they're more stateful in their UI. It's confusing if
        # what you started drawing disappears.
        # Other tools should hide their preview, since they only preview
        # what will happen if you click on the canvas.
        if self.selected_tool not in [Tool.curve, Tool.polygon]:
            self.cancel_preview()
        self.get_widget_by_id("status_coords", Static).update("")

    def get_select_region(self, start: Offset, end: Offset) -> Region:
        """Returns the minimum region that contains the cells at the start and end offsets."""
        # Region.from_corners requires the first point to be the top left,
        # and it doesn't ensure the width and height are non-zero, so it doesn't work here.
        # We want to treat the inputs as cells, not points,
        # so we need to add 1 to the bottom/right.
        x1, y1 = start
        x2, y2 = end
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        region = Region(x1, y1, x2 - x1 + 1, y2 - y1 + 1)
        # Clamp to the document bounds.
        return region.intersection(Region(0, 0, self.image.width, self.image.height))

    def meld_or_clear_selection(self, meld: bool) -> None:
        """Merges the selection into the image, or deletes it if meld is False."""
        if not self.image.selection:
            return

        if self.image.selection.textbox_mode:
            # The Text tool creates an undo state only when you switch tools
            # or click outside the textbox, melding the textbox into the image.
            # If you're deleting the textbox, an undo state doesn't need to be created.

            # If you haven't typed anything into the textbox yet, it should be deleted
            # to make it easier to start over in positioning the textbox.
            # If you have typed something, it should be melded into the image,
            # even if you backspaced it all, to match MS Paint.
            if not self.image.selection.textbox_edited:
                meld = False

            make_undo_state = meld
        else:
            # The Select tool creates an undo state when you drag a selection,
            # so we only need to create one if you haven't dragged it, unless it was pasted.
            # Once it's dragged, it cuts out the image data, and contained_image is not None.
            # TODO: refactor to a flag that says whether an undo state was already created
            make_undo_state = (self.image.selection.contained_image is None and not meld) or self.image.selection.pasted

        if make_undo_state:
            # TODO: DRY with other undo state creation
            self.image_at_start = AnsiArtDocument(self.image.width, self.image.height)
            self.image_at_start.copy_region(self.image)
            action = Action(self.selected_tool.get_name())
            self.add_action(action)

        region = self.image.selection.region
        if meld:
            self.image.selection.copy_to_document(self.image)
        else:
            if self.image.selection.contained_image is None:
                # It hasn't been cut out yet, so we need to erase it.
                self.erase_region(region, self.image.selection.mask)
        self.image.selection = None
        self.canvas.refresh_scaled_region(region)
        self.selection_drag_offset = None
        self.selecting_text = False

        if make_undo_state:
            action = action  # type: ignore
            affected_region = region
            # TODO: DRY with other undo state creation
            action.region = affected_region
            action.region = action.region.intersection(Region(0, 0, self.image.width, self.image.height))
            action.update(self.image_at_start)
            self.canvas.refresh_scaled_region(affected_region)

    def meld_selection(self) -> None:
        """Draw the selection onto the image and dissolve the selection."""
        self.meld_or_clear_selection(meld=True)

    def action_clear_selection(self, from_key_binding: bool = False) -> None:
        """Delete the selection and its contents, or if using the Text tool, delete text."""
        sel = self.image.selection
        if sel is None:
            return
        if sel.textbox_mode:
            if not from_key_binding:
                self.on_key(events.Key("delete", None))
        else:
            self.meld_or_clear_selection(meld=False)

    def on_canvas_tool_update(self, event: Canvas.ToolUpdate) -> None:
        """Called when the user is drawing on the canvas.

        Several tools do a preview of sorts here, even though it's not the ToolPreviewUpdate event.
        TODO: rename these events to describe when they occur, ascribe less semantics to them.
        """
        event.stop()
        self.cancel_preview()

        if self.mouse_gesture_cancelled:
            return

        if self.selected_tool != Tool.select:
            if self.selected_tool in [Tool.line, Tool.rectangle, Tool.ellipse, Tool.rounded_rectangle]:  # , Tool.curve
                # Display is allowed to go negative, unlike for the Select tool, handled below.
                # Also, Polygon gets both coords and dimensions.
                # Unlike MS Paint, Free-Form Select displays the dimensions of the resulting selection,
                # (rather than the difference between the mouse position and the starting point,)
                # which seems better to me.
                # Also, unlike MS Paint, Curve displays mouse coords rather than dimensions,
                # where "dimensions" are the difference between the mouse position and the starting point.
                # I don't know that this is better, but my mouse_at_start currently is set on mouse down for in-progress curves,
                # so it wouldn't match MS Paint unless I changed that or used the tool_points list.
                # I don't know that anyone looks at the status bar while drawing a curve.
                # If they do, they should probably be using a graphing calculator instead or something.
                self.get_widget_by_id("status_dimensions", Static).update(f"{event.x - self.mouse_at_start.x}x{event.y - self.mouse_at_start.y}")
            else:
                self.get_widget_by_id("status_coords", Static).update(f"{event.x},{event.y}")

        if self.selected_tool == Tool.pick_color:
            self.pick_color(event.x, event.y)
            return

        if self.selected_tool in [Tool.fill, Tool.magnifier]:
            return

        if self.selected_tool in [Tool.select, Tool.free_form_select, Tool.text]:
            sel = self.image.selection
            if self.selecting_text:
                assert sel is not None, "selecting_text should only be set if there's a selection"
                offset_in_textbox = Offset(event.x, event.y) - sel.region.offset
                offset_in_textbox = Offset(
                    min(max(0, offset_in_textbox.x), sel.region.width - 1),
                    min(max(0, offset_in_textbox.y), sel.region.height - 1),
                )
                sel.text_selection_end = offset_in_textbox
                self.canvas.refresh_scaled_region(sel.region)
            elif self.selection_drag_offset is not None:
                assert sel is not None, "selection_drag_offset should only be set if there's a selection"
                offset = (
                    self.selection_drag_offset.x + event.x,
                    self.selection_drag_offset.y + event.y,
                )
                # Handles constraints and canvas refresh.
                self.move_selection_absolute(*offset)
            elif self.selected_tool == Tool.free_form_select:
                self.tool_points.append(Offset(event.x, event.y))
                self.make_preview(self.draw_current_free_form_select_polyline, show_dimensions_in_status_bar=True)
            else:
                self.canvas.select_preview_region = self.get_select_region(self.mouse_at_start, Offset(event.x, event.y))
                self.canvas.refresh_scaled_region(self.canvas.select_preview_region)
                self.get_widget_by_id("status_dimensions", Static).update(
                    f"{self.canvas.select_preview_region.width}x{self.canvas.select_preview_region.height}"
                )
            return

        if self.selected_tool in [Tool.curve, Tool.polygon]:
            if len(self.tool_points) < 2:
                self.tool_points.append(Offset(event.x, event.y))
            self.tool_points[-1] = Offset(event.x, event.y)

            if self.selected_tool == Tool.curve:
                self.make_preview(self.draw_current_curve)
            elif self.selected_tool == Tool.polygon:
                # polyline until finished
                self.make_preview(self.draw_current_polyline, show_dimensions_in_status_bar=True)
            return

        # The remaining tools work by updating an undo state created on mouse down.
        assert len(self.undos) > 0, "No undo state to update. The undo state should have been created in on_canvas_tool_start, or if the gesture was canceled, execution shouldn't reach here."

        action = self.undos[-1]
        affected_region = None

        replace_action = self.selected_tool in [Tool.ellipse, Tool.rectangle, Tool.line, Tool.rounded_rectangle]
        old_action: Optional[Action] = None  # avoid "possibly unbound"
        if replace_action:
            old_action = self.undos.pop()
            old_action.undo(self.image)
            action = Action(self.selected_tool.get_name(), affected_region)
            self.undos.append(action)

        if self.selected_tool in [Tool.pencil, Tool.brush, Tool.eraser, Tool.airbrush]:
            for x, y in bresenham_walk(self.mouse_previous.x, self.mouse_previous.y, event.x, event.y):
                affected_region = self.stamp_brush(x, y, affected_region)
        elif self.selected_tool == Tool.line:
            for x, y in bresenham_walk(self.mouse_at_start.x, self.mouse_at_start.y, event.x, event.y):
                affected_region = self.stamp_brush(x, y, affected_region)
        elif self.selected_tool == Tool.rectangle:
            for x in range(min(self.mouse_at_start.x, event.x), max(self.mouse_at_start.x, event.x) + 1):
                for y in range(min(self.mouse_at_start.y, event.y), max(self.mouse_at_start.y, event.y) + 1):
                    if x in range(min(self.mouse_at_start.x, event.x) + 1, max(self.mouse_at_start.x, event.x)) and y in range(min(self.mouse_at_start.y, event.y) + 1, max(self.mouse_at_start.y, event.y)):
                        continue
                    affected_region = self.stamp_brush(x, y, affected_region)
        elif self.selected_tool == Tool.rounded_rectangle:
            arc_radius = min(2, abs(self.mouse_at_start.x - event.x) // 2, abs(self.mouse_at_start.y - event.y) // 2)
            min_x = min(self.mouse_at_start.x, event.x)
            max_x = max(self.mouse_at_start.x, event.x)
            min_y = min(self.mouse_at_start.y, event.y)
            max_y = max(self.mouse_at_start.y, event.y)
            for x, y in midpoint_ellipse(0, 0, arc_radius, arc_radius):
                if x < 0:
                    x = min_x + x + arc_radius
                else:
                    x = max_x + x - arc_radius
                if y < 0:
                    y = min_y + y + arc_radius
                else:
                    y = max_y + y - arc_radius
                affected_region = self.stamp_brush(x, y, affected_region)
            for x in range(min_x + arc_radius, max_x - arc_radius + 1):
                affected_region = self.stamp_brush(x, min_y, affected_region)
                affected_region = self.stamp_brush(x, max_y, affected_region)
            for y in range(min_y + arc_radius, max_y - arc_radius + 1):
                affected_region = self.stamp_brush(min_x, y, affected_region)
                affected_region = self.stamp_brush(max_x, y, affected_region)
        elif self.selected_tool == Tool.ellipse:
            center_x = (self.mouse_at_start.x + event.x) // 2
            center_y = (self.mouse_at_start.y + event.y) // 2
            radius_x = abs(self.mouse_at_start.x - event.x) // 2
            radius_y = abs(self.mouse_at_start.y - event.y) // 2
            for x, y in midpoint_ellipse(center_x, center_y, radius_x, radius_y):
                affected_region = self.stamp_brush(x, y, affected_region)
        else:
            raise NotImplementedError

        # Update action region and image data
        if action.region and affected_region:
            action.region = action.region.union(affected_region)
        elif affected_region:
            action.region = affected_region
        if action.region:
            action.region = action.region.intersection(Region(0, 0, self.image.width, self.image.height))
            action.update(self.image_at_start)

        # Only for refreshing, include replaced action region
        # (The new action is allowed to shrink the region compared to the old one)
        if affected_region:
            if replace_action:
                assert old_action is not None, "old_action should have been set if replace_action is True"
                affected_region = affected_region.union(old_action.region)
            self.canvas.refresh_scaled_region(affected_region)

        self.mouse_previous = Offset(event.x, event.y)

    def on_canvas_tool_stop(self, event: Canvas.ToolStop) -> None:
        """Called when releasing the mouse button after drawing/dragging on the canvas."""
        # Clear the selection preview in case the mouse has moved.
        # (I don't know of any guarantee that it won't.)
        self.cancel_preview()

        self.get_widget_by_id("status_dimensions", Static).update("")

        self.color_eraser_mode = False  # reset for preview

        if self.mouse_gesture_cancelled:
            return

        if self.selection_drag_offset is not None:
            # Done dragging selection
            self.selection_drag_offset = None
            # Refresh to show border, which is hidden while dragging
            assert self.image.selection is not None, "Dragging selection without selection"
            self.canvas.refresh_scaled_region(self.image.selection.region)
            return
        if self.selecting_text:
            # Done selecting text
            self.selecting_text = False
            return

        assert self.mouse_at_start is not None, "mouse_at_start should be set on mouse down"
        # Note that self.mouse_at_start is not set to None on mouse up,
        # so it can't be used to check if the mouse is down.
        # But ToolStop should only happen if the mouse is down.
        if self.selected_tool in [Tool.select, Tool.free_form_select, Tool.text]:
            # Finish making a selection
            if self.selected_tool == Tool.free_form_select:
                # Find bounds of the polygon
                min_x = min(p.x for p in self.tool_points)
                max_x = max(p.x for p in self.tool_points)
                min_y = min(p.y for p in self.tool_points)
                max_y = max(p.y for p in self.tool_points)
                select_region = Region(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
                select_region = select_region.intersection(Region(0, 0, self.image.width, self.image.height))
            else:
                select_region = self.get_select_region(self.mouse_at_start, Offset(event.x, event.y))
            if self.image.selection:
                # This shouldn't happen, because it should meld
                # the selection on mouse down.
                self.meld_selection()
            self.image.selection = Selection(select_region)
            self.image.selection.textbox_mode = self.selected_tool == Tool.text
            if self.image.selection.textbox_mode:
                self.image.selection.contained_image = AnsiArtDocument(self.image.selection.region.width, self.image.selection.region.height)
                for y in range(self.image.selection.region.height):
                    for x in range(self.image.selection.region.width):
                        self.image.selection.contained_image.fg[y][x] = self.selected_fg_color
                        self.image.selection.contained_image.bg[y][x] = self.selected_bg_color
            if self.selected_tool == Tool.free_form_select:
                # Define the mask for the selection using the polygon
                self.image.selection.mask = [[is_inside_polygon(x + select_region.x, y + select_region.y, self.tool_points) for x in range(select_region.width)] for y in range(select_region.height)]
            self.canvas.refresh_scaled_region(select_region)
        elif self.selected_tool == Tool.curve:
            # Maybe finish drawing a curve
            if len(self.tool_points) >= 4:
                self.finalize_polygon_or_curve()
            else:
                # Most likely just drawing the preview we just cancelled.
                self.make_preview(self.draw_current_curve)
        elif self.selected_tool == Tool.polygon:
            # Maybe finish drawing a polygon

            # Check if the distance between the first and last point is small enough,
            # or if the user double-clicked.
            close_gap_threshold_cells = 2
            double_click_threshold_seconds = 0.5
            double_click_threshold_cells = 2
            time_since_last_click = event.time - self.polygon_last_click_time
            enough_points = len(self.tool_points) >= 3
            closed_gap = (
                abs(self.tool_points[0].x - event.x) <= close_gap_threshold_cells and
                abs(self.tool_points[0].y - event.y) <= close_gap_threshold_cells
            )

            # print("self.mouse_at_start.x - event.x", self.mouse_at_start.x - event.x)
            # print("self.tool_points[-2].x - event.x if len(self.tool_points) >= 2 else None", self.tool_points[-2].x - event.x if len(self.tool_points) >= 2 else None)
            double_clicked = (
                time_since_last_click < double_click_threshold_seconds and
                # Distance during second click (from press to release)
                abs(self.mouse_at_start.x - event.x) <= double_click_threshold_cells and
                abs(self.mouse_at_start.y - event.y) <= double_click_threshold_cells and
                # Distance between first and second clicks
                # I guess if the tool points are updated on mouse move,
                # this is the distance between the two mouse up events.
                # TODO: use distance between first mouse down and second mouse up (or maybe second mouse down?)
                len(self.tool_points) >= 2 and
                abs(self.tool_points[-2].x - event.x) <= double_click_threshold_cells and
                abs(self.tool_points[-2].y - event.y) <= double_click_threshold_cells
            )
            if enough_points and (closed_gap or double_clicked):
                self.finalize_polygon_or_curve()
            else:
                # Most likely just drawing the preview we just cancelled.
                self.make_preview(self.draw_current_polyline, show_dimensions_in_status_bar=True)  # polyline until finished

            self.polygon_last_click_time = event.time
        elif self.selected_tool in [Tool.pick_color, Tool.magnifier]:
            self.selected_tool = self.return_to_tool


        # Not reliably unset, so might as well not rely on it. (See early returns above.)
        # self.mouse_at_start = None

    def move_selection_absolute(self, x: int, y: int) -> None:
        """Positions the selection relative to the document."""
        # Constrain to have at least one row/column within the bounds of the document.
        # This ensures you can always drag the selection back into the document,
        # but doesn't limit you from positioning it partially outside.
        # (It is useless to position it _completely_ outside, since you could just delete it.)
        sel = self.image.selection
        assert sel is not None, "move_selection_absolute called without a selection"
        if sel.contained_image is None:
            self.extract_to_selection()
        offset = Offset(
            max(1-sel.region.width, min(self.image.width - 1, x)),
            max(1-sel.region.height, min(self.image.height - 1, y)),
        )
        old_region = sel.region
        sel.region = Region.from_offset(offset, sel.region.size)
        combined_region = old_region.union(sel.region)
        self.canvas.refresh_scaled_region(combined_region)

    def move_selection_relative(self, delta_x: int, delta_y: int) -> None:
        """Moves the selection relative to its current position."""
        sel = self.image.selection
        assert sel is not None, "move_selection_relative called without a selection"
        self.move_selection_absolute(sel.region.offset.x + delta_x, sel.region.offset.y + delta_y)

    def on_key(self, event: events.Key) -> None:
        """Called when the user presses a key."""
        key = event.key
        shift = key.startswith("shift+")
        if shift:
            key = key[len("shift+"):]
        if "ctrl" in key:
            # Don't interfere with Ctrl+C, Ctrl+V, etc.
            # and don't double-handle Ctrl+F (View Bitmap)
            return

        if self.has_class("view_bitmap"):
            self.call_later(self.action_view_bitmap)
            return

        if self.image.selection and not self.image.selection.textbox_mode:
            # TODO: smear selection if shift is held
            if key == "left":
                self.move_selection_relative(-1, 0)
            elif key == "right":
                self.move_selection_relative(1, 0)
            elif key == "up":
                self.move_selection_relative(0, -1)
            elif key == "down":
                self.move_selection_relative(0, 1)
        if self.image.selection and self.image.selection.textbox_mode:
            textbox = self.image.selection
            assert textbox.contained_image is not None, "Textbox mode should always have contained_image, to edit as text."

            def delete_selected_text() -> None:
                """Deletes the selected text, if any."""
                # This was JUST checked above, but Pyright doesn't know that.
                assert textbox.contained_image is not None, "Textbox mode should always have contained_image, to edit as text."
                # Delete the selected text.
                for offset in selected_text_range(textbox):
                    textbox.contained_image.ch[offset.y][offset.x] = " "
                textbox.textbox_edited = True
                # Move the cursor to the start of the selection.
                textbox.text_selection_end = textbox.text_selection_start = min(
                    textbox.text_selection_start,
                    textbox.text_selection_end,
                )

            # TODO: delete selected text if any, when typing

            # Note: Don't forget to set textbox.textbox_edited = True
            #       for any new actions that actually affect the text content.

            # Whether or not shift is held, we start with the end point.
            # Then once we've moved this point, we update the end point,
            # and we update the start point unless shift is held.
            # This way, the cursor jumps to (near) the end point if you
            # hit an arrow key without shift, but with shift it will extend
            # the selection.
            x, y = textbox.text_selection_end

            if key == "enter":
                x = 0
                y += 1
                if y >= textbox.contained_image.height:
                    y = textbox.contained_image.height - 1
                # textbox.textbox_edited = True
            elif key == "left":
                x = max(0, x - 1)
            elif key == "right":
                x = min(textbox.contained_image.width - 1, x + 1)
            elif key == "up":
                y = max(0, y - 1)
            elif key == "down":
                y = min(textbox.contained_image.height - 1, y + 1)
            elif key == "backspace":
                if textbox.text_selection_end == textbox.text_selection_start:
                    x = max(0, x - 1)
                    textbox.contained_image.ch[y][x] = " "
                else:
                    delete_selected_text()
                    x, y = textbox.text_selection_end
                textbox.textbox_edited = True
            elif key == "delete":
                if textbox.text_selection_end == textbox.text_selection_start:
                    textbox.contained_image.ch[y][x] = " "
                    x = min(textbox.contained_image.width - 1, x + 1)
                else:
                    delete_selected_text()
                    x, y = textbox.text_selection_end
                textbox.textbox_edited = True
            elif key == "home":
                x = 0
            elif key == "end":
                x = textbox.contained_image.width - 1
            elif key == "pageup":
                y = 0
            elif key == "pagedown":
                y = textbox.contained_image.height - 1
            elif event.is_printable:
                assert event.character is not None, "is_printable should imply character is not None"
                # Type a character into the textbox
                textbox.contained_image.ch[y][x] = event.character
                # x = min(textbox.contained_image.width - 1, x + 1)
                x += 1
                if x >= textbox.contained_image.width:
                    x = 0
                    # y = min(textbox.contained_image.height - 1, y + 1)
                    y += 1
                    if y >= textbox.contained_image.height:
                        y = textbox.contained_image.height - 1
                        x = textbox.contained_image.width - 1
                textbox.textbox_edited = True
            if shift:
                textbox.text_selection_end = Offset(x, y)
            else:
                textbox.text_selection_start = Offset(x, y)
                textbox.text_selection_end = Offset(x, y)
            self.canvas.refresh_scaled_region(textbox.region)

    def on_paste(self, event: events.Paste) -> None:
        """Called when a file is dropped into the terminal, or when text is pasted with middle click."""
        # Note: this method is called directly by CharInput,
        # to work around Input stopping propagation of Paste events.

        # Detect file drop
        def _extract_filepaths(text: str) -> list[str]:
            """Extracts escaped filepaths from text.

            Taken from https://github.com/agmmnn/textual-filedrop/blob/55a288df65d1397b959d55ef429e5282a0bb21ff/textual_filedrop/_filedrop.py#L17-L36
            """
            split_filepaths = []
            if os.name == "nt":
                pattern = r'(?:[^\s"]|"(?:\\"|[^"])*")+'
                split_filepaths = re.findall(pattern, text)
            else:
                split_filepaths = shlex.split(text)

            split_filepaths = shlex.split(text)
            # print(split_filepaths)
            filepaths: list[str] = []
            for i in split_filepaths:
                item = i.replace("\x00", "").replace('"', "")
                if os.path.isfile(item):
                    filepaths.append(i)
                # elif os.path.isdir(item):
                #     for root, _, files in os.walk(item):
                #         for file in files:
                #             filepaths.append(os.path.join(root, file))
            return filepaths

        try:
            filepaths = _extract_filepaths(event.text)
            if filepaths:
                file_path = filepaths[0]
                self.open_from_file_path(file_path, lambda: None)
                return
        except ValueError:
            pass

        # Text pasting is only supported with Ctrl+V or Edit > Paste, handled separately.
        return

    def action_toggle_tools_box(self) -> None:
        """Toggles the visibility of the tools box."""
        self.show_tools_box = not self.show_tools_box

    def action_toggle_colors_box(self) -> None:
        """Toggles the visibility of the colors box."""
        self.show_colors_box = not self.show_colors_box

    def action_toggle_status_bar(self) -> None:
        """Toggles the visibility of the status bar."""
        self.show_status_bar = not self.show_status_bar

    def on_tools_box_tool_selected(self, event: ToolsBox.ToolSelected) -> None:
        """Called when a tool is selected in the tools box."""
        self.finalize_polygon_or_curve()  # must come before setting selected_tool
        self.meld_selection()
        self.tool_points = []

        self.selected_tool = event.tool
        if self.selected_tool not in [Tool.magnifier, Tool.pick_color]:
            self.return_to_tool = self.selected_tool

    def on_char_input_char_selected(self, event: CharInput.CharSelected) -> None:
        """Called when a character is entered in the character input."""
        self.selected_char = event.char

    def on_colors_box_color_selected(self, event: ColorsBox.ColorSelected) -> None:
        """Called when a color well is clicked in the palette."""
        if event.as_foreground:
            self.selected_fg_color = event.color
        else:
            self.selected_bg_color = event.color

    def on_colors_box_edit_color(self, event: ColorsBox.EditColor) -> None:
        """Called when a color is double-clicked in the palette."""
        self.action_edit_colors(color_palette_index=event.color_index, as_foreground=event.as_foreground)

    def on_menu_status_info(self, event: Menu.StatusInfo) -> None:
        """Called when a menu item is hovered."""
        text: str = event.description or ""
        if event.closed:
            text = _("For Help, click Help Topics on the Help Menu.")
        self.get_widget_by_id("status_text", Static).update(text)

    def within_menus(self, node: DOMNode) -> bool:
        """Returns True if the node is within the menus."""
        # root node will never be a menu, so it doesn't need to be `while node:`
        # and this makes the type checker happy, since parent can be None
        while node.parent:
            if isinstance(node, Menu):
                return True
            node = node.parent
        return False

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Called when the mouse button gets pressed."""

        leaf_widget, _ = self.get_widget_at(*event.screen_offset)

        # Close menus if clicking outside the menus
        if not self.within_menus(leaf_widget):
            if self.query_one(MenuBar).any_menus_open():
                self.query_one(MenuBar).close()
                return

        # Exit View Bitmap mode if clicking anywhere
        if self.has_class("view_bitmap"):
            # Call later to avoid drawing on the canvas when exiting
            self.call_later(self.action_view_bitmap)

        # Deselect if clicking outside the canvas
        if leaf_widget is self.editing_area:
            self.meld_selection()
        # Unfocus if clicking on or outside the canvas,
        # so that you can type in the Text tool.
        # Otherwise the CharInput gets in the way.
        if leaf_widget is self.editing_area or leaf_widget is self.canvas:
            self.app.set_focus(None)

        # This is a dev helper to inspect the layout
        # by highlighting the elements under the mouse in different colors, and labeling them on their borders.
        # debug_highlight is a list of tuples of (element, original_color, original_border, original_border_title)
        if not args.inspect_layout:
            return
        # Trigger only with middle mouse button.
        # This is before the reset, so you have to middle click on the root element to reset.
        # I didn't like it resetting on every click.
        if event.button != 2:
            return
        if hasattr(self, "debug_highlight"):
            for element, original_color, original_border, original_border_title in self.debug_highlight:
                element.styles.background = original_color
                element.styles.border = original_border
                element.border_title = original_border_title
        self.debug_highlight: list[tuple[Widget, Color, BorderDefinition, Optional[str]]] = []
        # leaf_widget, _ = self.get_widget_at(*event.screen_offset)
        if leaf_widget and leaf_widget is not self.screen:
            for i, widget in enumerate(leaf_widget.ancestors_with_self):
                self.debug_highlight.append((widget, widget.styles.background, widget.styles.border, widget.border_title if hasattr(widget, "border_title") else None))  # type: ignore
                widget.styles.background = Color.from_hsl(i / 10, 1, 0.3)
                if not event.ctrl:
                    widget.styles.border = ("round", Color.from_hsl(i / 10, 1, 0.5))
                    widget.border_title = widget.css_identifier_styled  # type: ignore


# `textual run --dev src.textual_paint.paint` will search for a
# global variable named `app`, and fallback to
# anything that is an instance of `App`, or
# a subclass of `App`.
app = PaintApp()

# Passive arguments
# (with the exception of making directories)

app.dark = args.theme == "dark"

if args.backup_folder:
    backup_folder = os.path.abspath(args.backup_folder)
    # I could move this elsewhere, but it's kind of good to fail early
    # if you don't have permissions to create the backup folder.
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)
    app.backup_folder = backup_folder

# Active arguments
# The backup_folder must be set before recover_from_backup() is called below.

if args.restart_on_changes:
    restart_on_changes(app)

if args.filename:
    # if args.filename == "-" and not sys.stdin.isatty():
    #     app.image = AnsiArtDocument.from_text(sys.stdin.read())
    #     app.filename = "<stdin>"
    # else:
    if os.path.exists(args.filename):
        # This calls recover_from_backup().
        # This requires the canvas to exist, hence call_later().
        def open_file_from_cli_arg() -> None:
            app.open_from_file_path(os.path.abspath(args.filename), lambda: None)
        app.call_later(open_file_from_cli_arg)
    else:
        # Sometimes you just want to name a new file from the command line.
        # Hopefully this won't be too confusing since it will be blank.
        app.file_path = os.path.abspath(args.filename)
        # Also, it's good to recover the backup in case the file was deleted.
        # This requires the canvas to exist, hence call_later().
        app.call_later(app.recover_from_backup)
else:
    # This is done inside action_new() but we're not using that for the initial blank state.
    # This requires the canvas to exist, hence call_later().
    app.call_later(app.recover_from_backup)

if args.clear_screen:
    os.system("cls||clear")

app.call_later(app.start_backup_interval)

def main() -> None:
    """Entry point for the textual-paint CLI."""
    app.run()

if __name__ == "__main__":
    main()
