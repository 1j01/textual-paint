#!/usr/bin/env python3

import base64
import io
import math
import os
from pathlib import Path
import re
import shlex
import argparse
import asyncio
from enum import Enum
from random import randint, random
import sys
from typing import Any, Coroutine, NamedTuple, Optional, Callable, Iterator
from uuid import uuid4

import stransi
from stransi.instruction import Instruction
from rich.segment import Segment
from rich.style import Style
from rich.console import Console
from rich.text import Text
from textual import events, on, work
from textual.filter import LineFilter
from textual.message import Message
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.geometry import Offset, Region, Size
from textual.css._style_properties import BorderDefinition
from textual.reactive import var, reactive
from textual.strip import Strip
from textual.dom import DOMNode
from textual.widget import Widget
from textual.widgets import Button, Static, Input, Header, RadioSet, RadioButton
from textual.binding import Binding
from textual.color import Color, ColorParseError
from PIL import Image, UnidentifiedImageError
from textual.worker import get_current_worker  # type: ignore
from pyfiglet import Figlet, FigletFont  # type: ignore

from .menus import MenuBar, Menu, MenuItem, Separator
from .windows import Window, DialogWindow, CharacterSelectorDialogWindow, MessageBox, get_warning_icon, get_question_icon, get_paint_icon
from .file_dialogs import SaveAsDialogWindow, OpenDialogWindow
from .edit_colors import EditColorsDialogWindow
from .localization.i18n import get as _, load_language, remove_hotkey
from .rasterize_ansi_art import rasterize
from .wallpaper import get_config_dir, set_wallpaper
from .auto_restart import restart_on_changes, restart_program

from .__init__ import __version__

MAX_FILE_SIZE = 500000 # 500 KB
DEBUG_SVG_LOADING = False # writes debug.svg when flexible character grid loader is used

# JPEG is disabled because of low quality.
# On the scale of images you're able to (performantly) edit in this app (currently),
# JPEG is not a good choice.
# ICNS is disabled because it only supports a limited set of sizes.
SAVE_DISABLED_FORMATS = ["JPEG", "ICNS"]

# These can go away now that args are parsed up top
ascii_only_icons = False
inspect_layout = False

# Command line arguments
parser = argparse.ArgumentParser(description='Paint in the terminal.', usage='%(prog)s [options] [filename]', prog="textual-paint")
parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
parser.add_argument('--theme', default='light', help='Theme to use, either "light" or "dark"', choices=['light', 'dark'])
parser.add_argument('--language', default='en', help='Language to use', choices=['ar', 'cs', 'da', 'de', 'el', 'en', 'es', 'fi', 'fr', 'he', 'hu', 'it', 'ja', 'ko', 'nl', 'no', 'pl', 'pt', 'pt-br', 'ru', 'sk', 'sl', 'sv', 'tr', 'zh', 'zh-simplified'])
parser.add_argument('--ascii-only-icons', action='store_true', help='Use only ASCII characters for tool icons, no emoji or other Unicode symbols')
parser.add_argument('--backup-folder', default=None, metavar="FOLDER", help='Folder to save backups to. By default a backup is saved alongside the edited file.')

# TODO: hide development options from help? there's quite a few of them now
parser.add_argument('--inspect-layout', action='store_true', help='Enables DOM inspector (F12) and middle click highlight, for development')
# This flag is for development, because it's very confusing
# to see the error message from the previous run,
# when a problem is actually solved.
# There are enough ACTUAL "that should have worked!!" moments to deal with.
# I really don't want false ones mixed in. You want to reward your brain for finding good solutions, after all.
parser.add_argument('--clear-screen', action='store_true', help='Clear the screen before starting; useful for development, to avoid seeing outdated errors')
parser.add_argument('--restart-on-changes', action='store_true', help='Restart the app when the source code is changed, for development')
parser.add_argument('--recode-samples', action='store_true', help='Open and save each file in samples/, for testing')

parser.add_argument('filename', nargs='?', default=None, help='Path to a file to open. File will be created if it doesn\'t exist.')

def update_cli_help_on_readme():
    """Update the readme with the current CLI usage info"""
    readme_help_start = re.compile(r"```\n.*--help\n")
    readme_help_end = re.compile(r"```")
    readme_file_path = os.path.join(os.path.dirname(__file__), "../../README.md")
    with open(readme_file_path, "r+", encoding="utf-8") as f:
        # By default, argparse uses the terminal width for formatting help text,
        # even when using format_help() to get a string.
        # The only way to override that is to override the formatter_class.
        # This is hacky, but it seems like the simplest way to fix the width
        # without creating a separate ArgumentParser, and without breaking the wrapping for --help.
        # This lambda works because python uses the same syntax for construction and function calls,
        # so formatter_class doesn't need to be an actual class.
        # See: https://stackoverflow.com/questions/44333577/explain-lambda-argparse-helpformatterprog-width
        width = 80
        old_formatter_class = parser.formatter_class
        parser.formatter_class = lambda prog: argparse.HelpFormatter(prog, width=width)
        help_text = parser.format_help()
        parser.formatter_class = old_formatter_class
        
        md = f.read()
        start_match = readme_help_start.search(md)
        if start_match is None:
            raise Exception("Couldn't find help section in readme")
        start = start_match.end()
        end_match = readme_help_end.search(md, start)
        if end_match is None:
            raise Exception("Couldn't find end of help section in readme")
        end = end_match.start()
        md = md[:start] + help_text + md[end:]
        f.seek(0)
        f.write(md)
        f.truncate()
# Manually disabled for release.
# TODO: disable for release builds, while keeping it automatic during development.
# (I could make this another dev flag, but I like the idea of it being automatic.)
# (Maybe a pre-commit hook would be ideal, if it's worth the complexity.)
# update_cli_help_on_readme()

args = parser.parse_args()

load_language(args.language)

# Most arguments are handled at the end of the file.

class MetaGlyphFont:
    def __init__(self, file_path: str, width: int, height: int, covered_characters: str):
        self.file_path = file_path
        """The path to the font file."""
        self.glyphs: dict[str, list[str]] = {}
        """Maps characters to meta-glyphs, where each meta-glyph is a list of rows of characters."""
        self.width = width
        """The width in characters of a meta-glyph."""
        self.height = height
        """The height in characters of a meta-glyph."""
        self.covered_characters = covered_characters
        """The characters supported by this font."""
        self.load()
    
    def load(self):
        """Load the font from the .flf FIGlet font file."""
        # fig = Figlet(font=self.file_path) # gives FontNotFound error!
        # Figlet constructor only supports looking for installed fonts.
        # I could install the font, with FigletFont.installFonts,
        # maybe with some prefixed name, but I don't want to do that.

        with open(self.file_path, encoding="utf-8") as f:
            flf = f.read()
            fig_font = FigletFont()
            fig_font.data = flf
            fig_font.loadFont()
            fig = Figlet()
            # fig.setFont(font=fig_font) # nope, that's also looking for a font name
            fig.font = self.file_path  # may not be used
            fig.Font = fig_font  # this feels so wrong
            for char in self.covered_characters:
                meta_glyph = fig.renderText(char)
                self.glyphs[char] = meta_glyph.split("\n")

covered_characters = R""" !"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~"""
meta_glyph_fonts: dict[int, MetaGlyphFont] = {
    2: MetaGlyphFont(os.path.join(os.path.dirname(__file__), "fonts/NanoTiny/NanoTiny_v14_2x2.flf"), 2, 2, covered_characters),
    # 4: MetaGlyphFont(os.path.join(os.path.dirname(__file__), "fonts/NanoTiny/NanoTiny_v14_4x4.flf"), 4, 4, covered_characters),
    # TODO: less specialized (more practical) fonts for larger sizes
}

def largest_font_that_fits(max_width: int, max_height: int) -> MetaGlyphFont | None:
    """Get the largest font with glyphs that can all fit in the given dimensions."""
    for font_size in sorted(meta_glyph_fonts.keys(), reverse=True):
        font = meta_glyph_fonts[font_size]
        if font.width <= max_width and font.height <= max_height:
            return font
    return None


class Tool(Enum):
    """The tools available in the Paint app."""
    free_form_select = 1
    select = 2
    eraser = 3
    fill = 4
    pick_color = 5
    magnifier = 6
    pencil = 7
    brush = 8
    airbrush = 9
    text = 10
    line = 11
    curve = 12
    rectangle = 13
    polygon = 14
    ellipse = 15
    rounded_rectangle = 16

    def get_icon(self) -> str:
        """Get the icon for this tool."""
        # Alternatives considered:
        # - Free-Form Select:  ✂️📐🆓🕸✨⚝⛤⛥⛦⛧🫥🇫/🇸◌⁛⁘ ⢼⠮
        # - Select: ⬚▧🔲 ⣏⣹ ⛶
        # - Eraser/Color Eraser: 🧼🧽🧹🚫👋🗑️▰▱
        # - Fill With Color: 🌊💦💧🌈🎉🎊🪣🫗
        # - Pick Color: 🎨💉💅💧📌📍⤤𝀃🝯🍶
        # - Magnifier: 🔍🔎👀🔬🔭🧐🕵️‍♂️🕵️‍♀️
        # - Pencil: ✏️✎✍️🖎🖊️🖋️✒️🖆📝🖍️
        # - Brush: 🖌👨‍🎨🧑‍🎨💅🧹🪮🪥🪒🪠ⵄ⑃ሐ⋔⋲ ▭/𝈸/⊏/⸦/⊂+⋹
        # - Airbrush: ⛫💨дᖜ╔🧴🥤🫠
        # - Text: 🆎📝📄📃🔤📜AＡ
        # - Line: 📏📉📈⟍𝈏╲⧹\⧵∖
        # - Curve: ↪️🪝🌙〰️◡◠~∼≈∽∿〜〰﹋﹏≈≋～⁓
        # - Rectangle: ▭▬▮▯🟥🟧🟨🟩🟦🟪🟫⬛⬜◼️◻️◾◽▪️▫️
        # - Polygon: ▙𝗟𝙇﹄』𓊋⬣⬟🔶🔷🔸🔹🔺🔻△▲
        # - Ellipse: ⬭⭕🔴🟠🟡🟢🔵🟣🟤⚫⚪🫧
        # - Rounded Rectangle: ▢⬜⬛

        if ascii_only_icons:
            enum_to_icon = {
                Tool.free_form_select: "<[u]^[/]7",  # "*" "<^>" "<[u]^[/]7"
                Tool.select: "::",  # "#" "::" ":_:" ":[u]:[/]:" ":[u]'[/]:"
                Tool.eraser: "[u]/[/]7",  # "47" "27" "/_/" "[u]/[/]7"
                Tool.fill: "[u i]H[/]?",  # "#?" "H?" "[u i]F[/]?"
                Tool.pick_color: "[u i] P[/]",  # "[u].[/]" "[u i]\\P[/]"
                Tool.magnifier: ",O",  # ",O" "o-" "O-" "o=" "O=" "Q"
                Tool.pencil: "-==",  # "c==>" "==-"
                Tool.brush: "E)=",  # "[u],h.[/u]" "[u],|.[/u]" "[u]h[/u]"
                Tool.airbrush: "[u i]H[/]`<",  # "H`" "H`<" "[u i]H[/]`<" "[u i]6[/]<"
                Tool.text: "A",  # "Abc"
                Tool.line: "\\",
                Tool.curve: "~",  # "~" "S" "s"
                Tool.rectangle: "[_]",  # "[]" "[_]" ("[\x1B[53m_\x1B[55m]" doesn't work right, is there no overline tag?)
                Tool.polygon: "[b]L[/b]",  # "L"
                Tool.ellipse: "O",  # "()"
                Tool.rounded_rectangle: "(_)", # "(_)" ("(\x1B[53m_\x1B[55m)" doesn't work right, is there no overline tag?)
            }
            return enum_to_icon[self]
        # Some glyphs cause misalignment of everything to the right of them, including the canvas,
        # so alternative characters need to be chosen carefully for each platform.
        # "🫗" causes jutting out in Ubuntu terminal, "🪣" causes the opposite in VS Code terminal
        # VS Code sets TERM_PROGRAM to "vscode", so we can use that to detect it
        TERM_PROGRAM = os.environ.get("TERM_PROGRAM")
        if TERM_PROGRAM == "vscode":
            if self == Tool.fill:
                # return "🫗" # is also hard to see in the light theme
                return "🌊" # is a safe alternative
                # return "[on black]🫗 [/]" # no way to make this not look like a selection highlight
            if self == Tool.pencil:
                # "✏️" doesn't display in color in VS Code
                return "🖍️" # or "🖊️", "🖋️"
        elif TERM_PROGRAM == "iTerm.app":
            # 🪣 (Fill With Color) and ⚝ (Free-Form Select) defaults are missing in iTerm2 on macOS 10.14 (Mojave)
            # They show as a question mark in a box, and cause the rest of the row to be misaligned.
            if self == Tool.fill:
                return "🌊"
            if self == Tool.free_form_select:
                return "⢼⠮"
        elif os.environ.get("WT_SESSION"):
            # The new Windows Terminal app sets WT_SESSION to a GUID.
            # Caveats:
            # - If you run `cmd` inside WT, this env var will be inherited.
            # - If you run a GUI program that launches another terminal emulator, this env var will be inherited.
            # - If you run via ssh, using Microsoft's official openssh server, WT_SESSION will not be set.
            # - If you hold alt and right click in Windows Explorer, and say Open Powershell Here, WT_SESSION will not be set,
            #   because powershell.exe is launched outside of the Terminal app, then later attached to it.
            # Source: https://github.com/microsoft/terminal/issues/11057

            # Windows Terminal has alignment problems with the default Pencil symbol "✏️"
            # as well as alternatives "🖍️", "🖊️", "🖋️", "✍️", "✒️"
            # "🖎" and "🖆" don't cause alignment issues, but don't show in color and are illegibly small.
            if self == Tool.pencil:
                # This looks more like it would represent the Text tool than the Pencil,
                # so it's far from ideal, especially when there IS an actual pencil emoji...
                return "📝"
            # "🖌️" is causes misalignment (and is hard to distinguish from "✏️" at a glance)
            # "🪮" shows as tofu
            if self == Tool.brush:
                return "🧹"
            # "🪣" shows as tofu
            if self == Tool.fill:
                return "🌊"
        return {
            Tool.free_form_select: "⚝",
            Tool.select: "⬚",
            Tool.eraser: "🧼",
            Tool.fill: "🪣",
            Tool.pick_color: "💉",
            Tool.magnifier: "🔍",
            Tool.pencil: "✏️",
            Tool.brush: "🖌️",
            Tool.airbrush: "💨",
            Tool.text: "Ａ",
            Tool.line: "⟍",
            Tool.curve: "～",
            Tool.rectangle: "▭",
            Tool.polygon: "𝙇",
            Tool.ellipse: "⬭",
            Tool.rounded_rectangle: "▢",
        }[self]

    def get_name(self) -> str:
        """Get the localized name for this tool.
        
        Not to be confused with tool.name, which is an identifier.
        """
        return {
            Tool.free_form_select: _("Free-Form Select"),
            Tool.select: _("Select"),
            Tool.eraser: _("Eraser/Color Eraser"),
            Tool.fill: _("Fill With Color"),
            Tool.pick_color: _("Pick Color"),
            Tool.magnifier: _("Magnifier"),
            Tool.pencil: _("Pencil"),
            Tool.brush: _("Brush"),
            Tool.airbrush: _("Airbrush"),
            Tool.text: _("Text"),
            Tool.line: _("Line"),
            Tool.curve: _("Curve"),
            Tool.rectangle: _("Rectangle"),
            Tool.polygon: _("Polygon"),
            Tool.ellipse: _("Ellipse"),
            Tool.rounded_rectangle: _("Rounded Rectangle"),
        }[self]


palette = [
    "rgb(0,0,0)",  # Black
    "rgb(128,128,128)",  # Dark Gray
    "rgb(128,0,0)",  # Dark Red
    "rgb(128,128,0)",  # Pea Green
    "rgb(0,128,0)",  # Dark Green
    "rgb(0,128,128)",  # Slate
    "rgb(0,0,128)",  # Dark Blue
    "rgb(128,0,128)",  # Lavender
    "rgb(128,128,64)",
    "rgb(0,64,64)",
    "rgb(0,128,255)",
    "rgb(0,64,128)",
    "rgb(64,0,255)",
    "rgb(128,64,0)",

    "rgb(255,255,255)",  # White
    "rgb(192,192,192)",  # Light Gray
    "rgb(255,0,0)",  # Bright Red
    "rgb(255,255,0)",  # Yellow
    "rgb(0,255,0)",  # Bright Green
    "rgb(0,255,255)",  # Cyan
    "rgb(0,0,255)",  # Bright Blue
    "rgb(255,0,255)",  # Magenta
    "rgb(255,255,128)",
    "rgb(0,255,128)",
    "rgb(128,255,255)",
    "rgb(128,128,255)",
    "rgb(255,0,128)",
    "rgb(255,128,64)",
]

irc_palette = [
    "rgb(255,255,255)", # 0 White
    "rgb(0,0,0)", # 1 Black
    "rgb(0,0,127)", # 2 Navy
    "rgb(0,147,0)", # 3 Green
    "rgb(255,0,0)", # 4 Red
    "rgb(127,0,0)", # 5 Maroon
    "rgb(156,0,156)", # 6 Purple
    "rgb(252,127,0)", # 7 Orange
    "rgb(255,255,0)", # 8 Yellow
    "rgb(0,252,0)", # 9 Light Green
    "rgb(0,147,147)", # 10 Teal
    "rgb(0,255,255)", # 11 Cyan
    "rgb(0,0,252)", # 12 Royal blue
    "rgb(255,0,255)", # 13 Magenta
    "rgb(127,127,127)", # 14 Gray
    "rgb(210,210,210)", # 15 Light Gray
]

class ToolsBox(Container):
    """Widget containing tool buttons"""

    class ToolSelected(Message):
        """Message sent when a tool is selected."""
        def __init__(self, tool: Tool) -> None:
            self.tool = tool
            super().__init__()

    def compose(self) -> ComposeResult:
        """Add our buttons."""
        self.tool_by_button: dict[Button, Tool] = {}
        for tool in Tool:
            button = Button(tool.get_icon(), classes="tool_button")
            button.can_focus = False
            # TODO: ideally, position tooltip centered under the tool button,
            # so that it never obscures the tool icon you're hovering over,
            # and make it appear immediately if a tooltip was already visible
            # (tooltip should hide and delay should return if moving to a button below,
            # to allow for easy scanning of the buttons, but not if moving above or to the side)
            button.tooltip = tool.get_name()
            self.tool_by_button[button] = tool
            yield button
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is clicked."""

        if "tool_button" in event.button.classes:
            self.post_message(self.ToolSelected(self.tool_by_button[event.button]))

class CharInput(Input, inherit_bindings=False):
    """Widget for entering a single character."""
    
    class CharSelected(Message):
        """Message sent when a character is selected."""
        def __init__(self, char: str) -> None:
            self.char = char
            super().__init__()

    class Recolor(LineFilter):
        """Replaces foreground and background colors."""

        def __init__(self, fg_color: Color, bg_color: Color) -> None:
            self.style = Style(color=fg_color.rich_color, bgcolor=bg_color.rich_color)
            super().__init__()

        def apply(self, segments: list[Segment], background: Color) -> list[Segment]:
            """Transform a list of segments."""
            return list(Segment.apply_style(segments, post_style=self.style))

    def validate_value(self, value: str) -> str:
        """Limit the value to a single character."""
        return value[-1] if value else " "
    
    # Previously this used watch_value,
    # and had a bug where the character would oscillate between multiple values
    # due to a feedback loop between watch_value and on_char_input_char_selected.
    # watch_value would queue up a CharSelected message, and then on_char_input_char_selected would
    # receive an older CharSelected message and set the value to the old value,
    # which would cause watch_value to queue up another CharSelected event, and it would cycle through values.
    # (Usually it wasn't a problem because the key events would be processed in time.)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Called when value changes."""
        with self.prevent(Input.Changed):
            self.post_message(self.CharSelected(event.value))

    def on_paste(self, event: events.Paste) -> None:
        """Called when text is pasted, OR a file is dropped on the terminal."""
        # _on_paste in Input stops the event from propagating,
        # but this breaks file drag and drop.
        # This can't be overridden since the event system calls
        # methods of each class in the MRO.
        # So instead, I'll call the app's on_paste method directly.
        assert isinstance(self.app, PaintApp)
        self.app.on_paste(event)

    def validate_cursor_position(self, cursor_position: int) -> int:
        """Force the cursor position to 0 so that it's over the character."""
        return 0
    
    def insert_text_at_cursor(self, text: str) -> None:
        """Override to limit the value to a single character."""
        self.value = text[-1] if text else " "

    def render_line(self, y: int) -> Strip:
        """Overrides rendering to color the character, since Input doesn't seem to support the color style."""
        assert isinstance(self.app, PaintApp)
        # Textural style, repeating the character:
        # This doesn't support a blinking cursor, and it can't extend all the way
        # to the edges, even when removing padding, due to the border, which takes up a cell on each side.
        # return Strip([Segment(self.value * self.size.width, Style(color=self.app.selected_fg_color, bgcolor=self.app.selected_bg_color))])

        # Single-character style, by filtering the Input's rendering:
        original_strip = super().render_line(y)
        fg_color = Color.parse(self.app.selected_fg_color)
        bg_color = Color.parse(self.app.selected_bg_color)
        return original_strip.apply_filter(self.Recolor(fg_color, bg_color), background=bg_color)

    last_click_time = 0
    def on_click(self, event: events.Click) -> None:
        """Detect double click and open character selector dialog."""
        if event.time - self.last_click_time < 0.8:
            assert isinstance(self.app, PaintApp)
            self.app.action_open_character_selector()
        self.last_click_time = event.time

class ColorsBox(Container):
    """Color palette widget."""

    class ColorSelected(Message):
        """Message sent when a color is selected."""
        def __init__(self, color: str, as_foreground: bool) -> None:
            self.color = color
            self.as_foreground = as_foreground
            super().__init__()

    def compose(self) -> ComposeResult:
        """Add our selected color and color well buttons."""
        self.color_by_button: dict[Button, str] = {}
        with Container(id="palette_selection_box"):
            # This widget is doing double duty, showing the current color
            # and showing/editing the current character.
            # I haven't settled on naming for this yet.
            yield CharInput(id="selected_color_char_input", classes="color_well")
        with Container(id="available_colors"):
            for color in palette:
                button = Button("", classes="color_button color_well")
                button.styles.background = color
                button.can_focus = False
                self.color_by_button[button] = color
                yield button

    def update_palette(self) -> None:  # , palette: list[str]) -> None:
        """Update the palette with new colors."""
        for button, color in zip(self.query(".color_button").nodes, palette):
            assert isinstance(button, Button)
            button.styles.background = color
            self.color_by_button[button] = color

    last_click_time = 0
    last_click_button: Button | None = None
    # def on_button_pressed(self, event: Button.Pressed) -> None:
        # """Called when a button is clicked."""
    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Called when a mouse button is pressed."""
        button, _ = self.app.get_widget_at(*event.screen_offset)
        if "color_button" in button.classes:
            assert isinstance(button, Button)
            self.post_message(self.ColorSelected(self.color_by_button[button], event.ctrl))
            # Detect double click and open Edit Colors dialog.
            if event.time - self.last_click_time < 0.8 and button == self.last_click_button:
                assert isinstance(self.app, PaintApp)
                self.app.action_edit_colors(self.query(".color_button").nodes.index(button), event.ctrl)
            self.last_click_time = event.time
            self.last_click_button = button

class Selection:
    """
    A selection within an AnsiArtDocument.

    AnsiArtDocument can contain a Selection, and Selection can contain an AnsiArtDocument.
    However, the selection's AnsiArtDocument should never itself contain a Selection.

    When a selection is created, it has no image data, but once it's dragged,
    it gets a copy of the image data from the document.
    The image data is stored as an AnsiArtDocument, since it's made up of characters and colors.
    """
    def __init__(self, region: Region) -> None:
        """Initialize a selection."""
        self.region: Region = region
        """The region of the selection within the outer document."""
        self.contained_image: Optional[AnsiArtDocument] = None
        """The image data contained in the selection, None until dragged, except for text boxes."""
        self.pasted: bool = False
        """Whether the selection was pasted from the clipboard, and thus needs an undo state created for it when melding."""
        self.textbox_mode = False
        """Whether the selection is a text box. Either way it's text, but it's a different editing mode."""
        self.textbox_edited = False
        """Whether text has been typed into the text box, ever. If not, the textbox can be deleted when clicking off."""
        self.text_selection_start = Offset(0, 0)
        """The start position of the text selection within the text box. This may be before or after the end."""""
        self.text_selection_end = Offset(0, 0)
        """The end position of the text selection within the text box. This may be before or after the start."""""
        self.mask: Optional[list[list[bool]]] = None
        """A mask of the selection to cut out, used for Free-Form Select tool. Coordinates are relative to the selection region."""

    def copy_from_document(self, document: 'AnsiArtDocument') -> None:
        """Copy the image data from the document into the selection."""
        self.contained_image = AnsiArtDocument(self.region.width, self.region.height)
        self.contained_image.copy_region(source=document, source_region=self.region)
    
    def copy_to_document(self, document: 'AnsiArtDocument') -> None:
        """Draw the selection onto the document."""
        if not self.contained_image:
            # raise ValueError("Selection has no image data.")
            return

        # Prevent out of bounds errors (IndexError: list assignment index out of range)
        # by clipping the target region to the document, and adjusting the source region accordingly.
        target_region = self.region.intersection(Region(0, 0, document.width, document.height))
        source_region = Region(target_region.x - self.region.x, target_region.y - self.region.y, self.contained_image.width, self.contained_image.height)

        document.copy_region(source=self.contained_image, source_region=source_region, target_region=target_region, mask=self.mask)


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


debug_region_updates = False


# Detects ANSI escape sequences.
# ansi_escape_pattern = re.compile(r"(\N{ESC}\[[\d;]*[a-zA-Z])")

# Detects all control codes, including newlines and tabs.
# ansi_control_code_pattern = re.compile(r'[\x00-\x1F\x7F]')

# Detects all control codes, including tabs and carriage return (CR) if used alone, but excluding line feed (LF) and CR+LF.
ansi_detector_pattern = re.compile(r'[\x00-\x09\x0B\x0C\x0E-\x1F\x7F]|\r(?!\n)')
# Explanation:
# [\x00-\x09\x0B\x0C\x0E-\x1F\x7F]: Matches any control character except CR (\x0D) or LF (\x0A).
# \r(?<!\r\n): Matches CR (\x0D) if it's not part of CRLF (\x0D\x0A).
#   (?<!\r\n): Negative lookbehind assertion to ensure that the matched CR (if any) is not part of CRLF.
# Tabs are included because they need to be expanded to spaces or they'll mess up the layout, currently,
# and if the text isn't detected as ANSI, it won't currently be expanded.
# Development strategy:
# I used https://www.debuggex.com/ to develop a simpler regex that operates on letters as stand-ins for control codes,
# since I don't know that I could input isolated control codes into the site.
# e|r(?!n)
# using test data:
# ---e--- (e representing any control code except CR or LF)
# ---r---
# ---n--- <- shouldn't match
# ---rn-- <- shouldn't match
# ---nr--

assert ansi_detector_pattern.search("\x0A") is None, "LF should not be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x0D") is not None, "CR by itself (not part of CRLF) should be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x0D\x0A") is None, "CRLF should not be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x09") is not None, "TAB should be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x1B") is not None, "ESC should be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x7F") is not None, "DEL should be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x00") is not None, "NUL should be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x80") is None, "Ç (in CP 437) or € (U+0080) should not be matched by ansi_detector_pattern"

# This SVG template is based on the template in rich/_export_format.py
# It removes the simulated window frame, and crops the SVG to just the terminal content.
# It also adds a placeholder for ANSI data to be stored in the SVG,
# in order to support opening the file after saving it, in a perfectly lossless way.
# (I have also implemented a more general SVG loading mechanism, but it's now a fallback.)
# It was very nice during development to automate saving a file as SVG:
# textual run --dev "src.textual_paint.paint --restart-on-changes samples/ship.ans" --press ctrl+shift+s,.,s,v,g,enter
# (The Ctrl+Shift+S shortcut doesn't work when actually trying it as a user, but it works to simulate it.)
CUSTOM_CONSOLE_SVG_FORMAT = """\
<svg
    class="rich-terminal"
    viewBox="0 0 {terminal_width} {terminal_height}"
    xmlns="http://www.w3.org/2000/svg"
    xmlns:txtpnt="http://github.com/1j01/textual-paint"
>
    <!-- Generated with Rich https://www.textualize.io and Textual Paint https://github.com/1j01/textual-paint -->
    <style>

    @font-face {{
        font-family: "Fira Code";
        src: local("FiraCode-Regular"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff2/FiraCode-Regular.woff2") format("woff2"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff/FiraCode-Regular.woff") format("woff");
        font-style: normal;
        font-weight: 400;
    }}
    @font-face {{
        font-family: "Fira Code";
        src: local("FiraCode-Bold"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff2/FiraCode-Bold.woff2") format("woff2"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff/FiraCode-Bold.woff") format("woff");
        font-style: bold;
        font-weight: 700;
    }}

    .{unique_id}-matrix {{
        font-family: Fira Code, monospace;
        font-size: {char_height}px;
        line-height: {line_height}px;
        font-variant-east-asian: full-width;
    }}

    {styles}
    </style>

    <defs>
    <clipPath id="{unique_id}-clip-terminal">
      <rect x="0" y="0" width="{terminal_width}" height="{terminal_height}" />
    </clipPath>
    {lines}
    <txtpnt:ansi>%ANSI_GOES_HERE%</txtpnt:ansi>
    </defs>

    <g clip-path="url(#{unique_id}-clip-terminal)">
    {backgrounds}
    <g class="{unique_id}-matrix">
    {matrix}
    </g>
    </g>
</svg>
"""

CUSTOM_CONSOLE_HTML_FORMAT = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
{stylesheet}
body {{
    color: {foreground};
    background-color: {background};
}}
</style>
</head>
<body>
    <pre style="font-family:monospace;line-height:1"><code>{code}</code></pre>
</body>
</html>
"""


class FormatWriteNotSupported(Exception):
    """The format doesn't support writing."""
    def __init__(self, localized_message: str):
        self.localized_message = localized_message
        super().__init__(localized_message)

class FormatReadNotSupported(Exception):
    """The format doesn't support reading."""
    def __init__(self, localized_message: str):
        self.localized_message = localized_message
        super().__init__(localized_message)

class AnsiArtDocument:
    """A document that can be rendered as ANSI."""

    def __init__(self, width: int, height: int, default_bg: str = "#ffffff", default_fg: str = "#000000") -> None:
        """Initialize the document."""
        # Pyright is really confused by height for some reason, doesn't have a problem with width.
        # I narrowed it down to the resize method, lines with new_bg/new_fg, but
        # I have no idea why that would be a problem.
        # Ideally I would try to pare this down to a minimal reproducible example,
        # and file a bug report (or learn something about my code),
        # but for now, I just want to silence 100+ errors.
        # I'm leaving width unannotated to highlight the fragility of programming.
        self.width = width
        self.height: int = height
        self.ch = [[" " for _ in range(width)] for _ in range(height)]
        self.bg = [[default_bg for _ in range(width)] for _ in range(height)]
        self.fg = [[default_fg for _ in range(width)] for _ in range(height)]
        self.selection: Optional[Selection] = None

    def copy(self, source: 'AnsiArtDocument') -> None:
        """Copy the image size and data from another document. Does not copy the selection."""
        self.width = source.width
        self.height = source.height
        self.ch = [row[:] for row in source.ch]
        self.bg = [row[:] for row in source.bg]
        self.fg = [row[:] for row in source.fg]
        self.selection = None

    def copy_region(self, source: 'AnsiArtDocument', source_region: Region|None = None, target_region: Region|None = None, mask: list[list[bool]]|None = None) -> None:
        """Copy a region from another document into this document."""
        if source_region is None:
            source_region = Region(0, 0, source.width, source.height)
        if target_region is None:
            target_region = Region(0, 0, source_region.width, source_region.height)
        source_offset = source_region.offset
        target_offset = target_region.offset
        random_color: Optional[str] = None  # avoid "possibly unbound"
        if debug_region_updates:
            random_color = "rgb(" + str(randint(0, 255)) + "," + str(randint(0, 255)) + "," + str(randint(0, 255)) + ")"
        for y in range(target_region.height):
            for x in range(target_region.width):
                if source_region.contains(x + source_offset.x, y + source_offset.y) and (mask is None or mask[y][x]):
                    self.ch[y + target_offset.y][x + target_offset.x] = source.ch[y + source_offset.y][x + source_offset.x]
                    self.bg[y + target_offset.y][x + target_offset.x] = source.bg[y + source_offset.y][x + source_offset.x]
                    self.fg[y + target_offset.y][x + target_offset.x] = source.fg[y + source_offset.y][x + source_offset.x]
                    if debug_region_updates:
                        assert random_color is not None
                        # self.bg[y + target_offset.y][x + target_offset.x] = "rgb(" + str((x + source_offset.x) * 255 // self.width) + "," + str((y + source_offset.y) * 255 // self.height) + ",0)"
                        self.bg[y + target_offset.y][x + target_offset.x] = random_color
                else:
                    if debug_region_updates:
                        self.ch[y + target_offset.y][x + target_offset.x] = "?"
                        self.bg[y + target_offset.y][x + target_offset.x] = "#ff00ff"
                        self.fg[y + target_offset.y][x + target_offset.x] = "#000000"

    def resize(self, width: int, height: int, default_bg: str = "#ffffff", default_fg: str = "#000000") -> None:
        """Resize the document."""
        if width == self.width and height == self.height:
            return
        new_ch = [[" " for _ in range(width)] for _ in range(height)]
        new_bg = [[default_bg for _ in range(width)] for _ in range(height)]
        new_fg = [[default_fg for _ in range(width)] for _ in range(height)]
        for y in range(min(height, self.height)):
            for x in range(min(width, self.width)):
                new_ch[y][x] = self.ch[y][x]
                new_bg[y][x] = self.bg[y][x]
                new_fg[y][x] = self.fg[y][x]
        self.width = width
        self.height = height
        self.ch = new_ch
        self.bg = new_bg
        self.fg = new_fg

    def invert(self) -> None:
        """Invert the foreground and background colors."""
        self.invert_region(Region(0, 0, self.width, self.height))

    def invert_region(self, region: Region) -> None:
        """Invert the foreground and background colors in the given region."""
        # TODO: DRY color inversion, and/or simplify it. It shouldn't need a Style object.
        for y in range(region.y, region.y + region.height):
            for x in range(region.x, region.x + region.width):
                style = Style(color=self.fg[y][x], bgcolor=self.bg[y][x])
                assert style.color is not None
                assert style.bgcolor is not None
                assert style.color.triplet is not None
                assert style.bgcolor.triplet is not None
                self.bg[y][x] = f"#{(255 - style.bgcolor.triplet.red):02x}{(255 - style.bgcolor.triplet.green):02x}{(255 - style.bgcolor.triplet.blue):02x}"
                self.fg[y][x] = f"#{(255 - style.color.triplet.red):02x}{(255 - style.color.triplet.green):02x}{(255 - style.color.triplet.blue):02x}"

    @staticmethod
    def format_from_extension(file_path: str) -> str | None:
        """Get the format ID from the file extension of the given path.
        
        Most format IDs are similar to the extension, e.g. 'PNG' for '.png',
        but some are different, e.g. 'JPEG2000' for '.jp2'.
        """
        # Ignore case and trailing '~' (indicating a backup file)
        # Alternative: pathlib.Path.suffix
        file_ext_with_dot = os.path.splitext(file_path)[1].lower().rstrip("~")
        # print("File extension:", file_ext_with_dot)
        ext_to_id = Image.registered_extensions() # maps extension to format ID, e.g. '.jp2': 'JPEG2000'
        # print("Supported image formats by extension:", Image.EXTENSION)
        if file_ext_with_dot in ext_to_id:
            return ext_to_id[file_ext_with_dot]
        ext_to_id = {
            ".svg": "SVG",
            ".html": "HTML",
            ".htm": "HTML",
            ".txt": "PLAINTEXT",
            ".asc": "PLAINTEXT",
            ".diz": "PLAINTEXT",
            ".ans": "ANSI",
            ".irc": "IRC",
            ".mirc": "IRC",
            "._rich_console_markup": "RICH_CONSOLE_MARKUP",
        }
        if file_ext_with_dot in ext_to_id:
            return ext_to_id[file_ext_with_dot]
        return None

    def encode_based_on_file_extension(self, file_path: str) -> bytes:
        """Encode the image according to the file extension."""
        return self.encode_to_format(self.format_from_extension(file_path))

    def encode_to_format(self, format_id: str | None) -> bytes:
        """Encode the image into the given file format."""
        # print("Supported image formats for writing:", Image.SAVE.keys())
        if format_id is None:
            raise FormatWriteNotSupported(localized_message=_("Unknown file extension.") + "\n\n" + _("To save your changes, use a different filename."))
        elif format_id == "ANSI":
            # This maybe shouldn't use UTF-8... but there's not a singular encoding for "ANSI art".
            return self.get_ansi().encode("utf-8")
        elif format_id == "IRC":
            # Also not sure about UTF-8 here.
            return self.get_irc().encode("utf-8")
        elif format_id == "SVG":
            return self.get_svg().encode("utf-8")
        elif format_id == "HTML":
            return self.get_html().encode("utf-8")
        elif format_id == "PLAINTEXT":
            return self.get_plain().encode("utf-8")
        elif format_id == "RICH_CONSOLE_MARKUP":
            return self.get_rich_console_markup().encode("utf-8")
        elif format_id in Image.SAVE and format_id not in SAVE_DISABLED_FORMATS:
            return self.encode_image_format(format_id)
        else:
            raise FormatWriteNotSupported(localized_message=_("Cannot write files in %1 format.", format_id) + "\n\n" + _("To save your changes, use a different filename."))
 
    def encode_image_format(self, pil_format_id: str) -> bytes:
        """Encode the document as an image file."""
        size = (self.width, self.height)
        image = Image.new("RGB", size, color="#000000")
        pixels = image.load()
        assert pixels is not None, "failed to load pixels for new image"
        for y in range(self.height):
            for x in range(self.width):
                color = Color.parse(self.bg[y][x])
                pixels[x, y] = (color.r, color.g, color.b)
        buffer = io.BytesIO()
        # `lossless` is for WebP
        # `sizes` is for ICO, since it defaults to a list of square sizes, blurring/distorting the image.
        # `bitmap_format` is also for ICO. I get "Compressed icons are not supported" in Ubuntu's image viewer,
        # and thumbnails don't render when it uses the default PNG sub-format.
        image.save(buffer, pil_format_id, lossless=True, sizes=[size], bitmap_format="bmp")
        return buffer.getvalue()

    def get_ansi(self) -> str:
        """Get the ANSI representation of the document."""
        renderable = self.get_renderable()
        console = self.get_console(render_contents=False)
        segments = renderable.render(console=console)
        ansi = ""
        for text, style, _ in Segment.filter_control(
            Segment.simplify(segments)
        ):
            if style:
                ansi += style.render(text)
            else:
                ansi += text
        return ansi

    def get_irc(self) -> str:
        """Get the mIRC code representation of the document."""
        renderable = self.get_renderable()
        console = self.get_console(render_contents=False)
        segments = renderable.render(console=console)

        def color_distance(a: Color, b: Color) -> float:
            """Perceptual color distance between two colors."""
            # https://www.compuphase.com/cmetric.htm
            red_mean = (a.r + b.r) // 2
            red = a.r - b.r
            green = a.g - b.g
            blue = a.b - b.b
            return math.sqrt((((512 + red_mean) * red * red) >> 8) + 4 * green * green + (((767 - red_mean) * blue * blue) >> 8))

        def closest_color(color: Color) -> int:
            """Get the closest color in the palette to the given color."""
            closest_color = 0
            closest_distance = float("inf")
            for index, hex in enumerate(irc_palette):
                distance = color_distance(color, Color.parse(hex))
                if distance < closest_distance:
                    closest_color = index
                    closest_distance = distance
            return closest_color

        # TODO: simplify after converting to IRC colors, to remove unnecessary color codes
        irc_text = ""
        for text, style, _ in Segment.filter_control(
            Segment.simplify(segments)
        ):
            if style and style.color is not None and style.bgcolor is not None:
                irc_text += "\x03"
                irc_text += str(closest_color(Color.from_rich_color(style.color)))
                irc_text += ","
                irc_text += str(closest_color(Color.from_rich_color(style.bgcolor)))
                if text[0] in "0123456789,":
                    # separate the color code from the text with an ending escape character
                    irc_text += "\x03"
                irc_text += text
            else:
                irc_text += text
        # ^O is the mIRC code for "reset to default colors"
        return irc_text + "\x0F"

    def get_plain(self) -> str:
        """Get the plain text representation of the document."""
        text = ""
        for y in range(self.height):
            for x in range(self.width):
                text += self.ch[y][x]
            text += "\n"
        return text

    def get_rich_console_markup(self) -> str:
        """Get the Rich API markup representation of the document."""
        return self.get_renderable().markup
    
    def get_html(self) -> str:
        """Get the HTML representation of the document."""
        console = self.get_console()
        return console.export_html(inline_styles=True, code_format=CUSTOM_CONSOLE_HTML_FORMAT)
    
    def get_svg(self) -> str:
        """Get the SVG representation of the document."""
        console = self.get_console()
        svg = console.export_svg(code_format=CUSTOM_CONSOLE_SVG_FORMAT)
        # Include ANSI in the SVG so it can be loaded perfectly when re-opened.
        # This can't use the .format() template since e.g. "{anything}" in the document would case a KeyError.
        # (And I can't do it beforehand on the template because the template uses .format() itself...
        # unless I escaped all the braces, but that would be ugly! So I'm just using a different syntax.)
        # `html.escape` leaves control codes, which blows up ET.fromstring, so use base64 instead.
        return svg.replace("%ANSI_GOES_HERE%", base64.b64encode(self.get_ansi().encode("utf-8")).decode("utf-8"))
    
    def get_renderable(self) -> Text:
        """Get a Rich renderable for the document."""
        joiner = Text("\n")
        lines: list[Text] = []
        for y in range(self.height):
            line = Text()
            for x in range(self.width):
                line.append(self.ch[y][x], style=Style(bgcolor=self.bg[y][x], color=self.fg[y][x]))
            lines.append(line)
        result = joiner.join(lines)
        return result

    def get_console(self, render_contents: bool = True) -> Console:
        """Get a Rich Console with the document rendered in it."""
        console = Console(
            width=self.width,
            height=self.height,
            file=io.StringIO(),
            force_terminal=True,
            color_system="truecolor",
            record=True,
            legacy_windows=False,
        )
        if render_contents:
            console.print(self.get_renderable())
        return console

    @staticmethod
    def from_plain(text: str, default_bg: str = "#ffffff", default_fg: str = "#000000") -> 'AnsiArtDocument':
        """Creates a document from the given plain text."""
        lines = text.splitlines()
        width = 1
        for line in lines:
            width = max(len(line), width)
        height = max(len(lines), 1)
        document = AnsiArtDocument(width, height, default_bg, default_fg)
        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                document.ch[y][x] = char
        return document

    @staticmethod
    def from_irc(text: str, default_bg: str = "#ffffff", default_fg: str = "#000000") -> 'AnsiArtDocument':
        """Creates a document from text with mIRC codes."""

        document = AnsiArtDocument(0, 0, default_bg, default_fg)
        # Minimum size of 1x1, so that the document is never empty.
        width = 1
        height = 1

        x = 0
        y = 0
        bg_color = default_bg
        fg_color = default_fg

        color_escape = "\x03"
        # an optional escape code at the end disambiguates a digit from part of the color code
        color_escape_re = re.compile(r"\x03(\d{1,2})?(?:,(\d{1,2}))?\x03?")
        reset_escape = "\x0F"

        index = 0
        while index < len(text):
            char = text[index]
            if char == color_escape:
                match = color_escape_re.match(text[index:])
                if match:
                    index += len(match.group(0))
                    # TODO: should a one-value syntax reset the background?
                    bg_color = default_bg
                    fg_color = default_fg
                    if match.group(1):
                        fg_color = irc_palette[int(match.group(1))]
                    if match.group(2):
                        bg_color = irc_palette[int(match.group(2))]
                    continue
            if char == reset_escape:
                index += 1
                bg_color = default_bg
                fg_color = default_fg
                continue
            if char == "\n":
                width = max(width, x)
                x = 0
                y += 1
                height = max(height, y)
                index += 1
                continue
            # Handle a single character, adding rows/columns as needed.
            while len(document.ch) <= y:
                document.ch.append([])
                document.bg.append([])
                document.fg.append([])
            while len(document.ch[y]) <= x:
                document.ch[y].append(' ')
                document.bg[y].append(default_bg)
                document.fg[y].append(default_fg)
            document.ch[y][x] = char
            document.bg[y][x] = bg_color
            document.fg[y][x] = fg_color
            width = max(x + 1, width)
            height = max(y + 1, height)
            x += 1
            index += 1

        document.width = width
        document.height = height
        # Handle minimum height.
        while len(document.ch) <= document.height:
            document.ch.append([])
            document.bg.append([])
            document.fg.append([])
        # Pad rows to a consistent width.
        for y in range(document.height):
            for x in range(len(document.ch[y]), document.width):
                document.ch[y].append(' ')
                document.bg[y].append(default_bg)
                document.fg[y].append(default_fg)

        return document

    @staticmethod
    def from_ansi(text: str, default_bg: str = "#ffffff", default_fg: str = "#000000", max_width: int = 100000) -> 'AnsiArtDocument':
        """Creates a document from the given ANSI text."""

        # TODO: use Rich API to render ANSI to a virtual screen,
        # and remove dependency on stransi
        # or improve ANSI handling based on Playscii's code
        # It kind of looks like Rich's API isn't designed to handle absolute positioning,
        # since it parses a line at a time, but I only looked at it briefly.

        # rich_text = Text.from_ansi(text, style=Style(bgcolor=default_bg, color=default_fg))
        # # This takes a console and options, but I want the width of the console to come from the text...
        # # Do I need to create a console huge and then resize it (or make a new one)?
        # measurement = Measurement.get(console, options, rich_text)
        # document = AnsiArtDocument(measurement.width, measurement.height, default_bg, default_fg)
        # console = document.get_console(rich_text)
        # # then see export_html et. al. for how to get the data out? or just use the rich_text?


        # Workaround for unwanted color rounding
        # RGB.__post_init__ rounds the color components, in decimal, causing 128 to become 127.
        from ochre.spaces import RGB
        RGB.__post_init__ = lambda self: None


        ansi = stransi.Ansi(text)

        document = AnsiArtDocument(0, 0, default_bg, default_fg)
        # Minimum size of 1x1, so that the document is never empty.
        width = 1
        height = 1

        x = 0
        y = 0
        bg_color = default_bg
        fg_color = default_fg
        instruction: Instruction[Any] | str
        for instruction in ansi.instructions():
            if isinstance(instruction, str):
                # Text and control characters other than escape sequences
                for char in instruction:
                    if char == '\r':
                        x = 0
                    elif char == '\n':
                        x = 0
                        y += 1
                        # Don't increase height until there's a character to put in the new row.
                        # This avoids an extra row if the file ends with a newline.
                    elif char == '\t':
                        x += 8 - (x % 8)
                        if x > max_width - 1:
                            x = max_width - 1  # I'm not sure if this is the right behavior; should it wrap?
                    elif char == '\b':
                        x -= 1
                        if x < 0:
                            x = 0
                            # on some terminals, backspace at the start of a line moves the cursor up,
                            # but we're not defining a width for the document up front, so we can't do that
                            # (could use max_width, but since there will be some incompatibility anyway,
                            # better to go with the simpler, more understandable behavior)
                    elif char == '\x07':
                        # ignore bell
                        # TODO: ignore other unhandled control characters
                        pass
                    else:
                        while len(document.ch) <= y:
                            document.ch.append([])
                            document.bg.append([])
                            document.fg.append([])
                        while len(document.ch[y]) <= x:
                            document.ch[y].append(' ')
                            document.bg[y].append(default_bg)
                            document.fg[y].append(default_fg)
                        document.ch[y][x] = char
                        document.bg[y][x] = bg_color
                        document.fg[y][x] = fg_color
                        width = max(x + 1, width)
                        height = max(y + 1, height)
                        x += 1
                        if x > max_width - 1:
                            x = 0
                            y += 1
            elif isinstance(instruction, stransi.SetColor) and instruction.color is not None:
                # Color (I'm not sure why instruction.color would be None, but it's typed as Optional[Color])
                # (maybe just for initial state?)
                if instruction.role == stransi.color.ColorRole.FOREGROUND:
                    rgb = instruction.color.rgb
                    fg_color = "rgb(" + str(int(rgb.red * 255)) + "," + str(int(rgb.green * 255)) + "," + str(int(rgb.blue * 255)) + ")"
                elif instruction.role == stransi.color.ColorRole.BACKGROUND:
                    rgb = instruction.color.rgb
                    bg_color = "rgb(" + str(int(rgb.red * 255)) + "," + str(int(rgb.green * 255)) + "," + str(int(rgb.blue * 255)) + ")"
            elif isinstance(instruction, stransi.SetCursor):
                # Cursor position is encoded as y;x, so stransi understandably gets this backwards.
                # TODO: fix stransi to interpret ESC[<y>;<x>H correctly
                # (or update it if it gets fixed)
                # Note that stransi gives 0-based coordinates; the underlying ANSI is 1-based.
                if instruction.move.relative:
                    x += instruction.move.y
                    y += instruction.move.x
                else:
                    x = instruction.move.y
                    y = instruction.move.x
                x = max(0, x)
                y = max(0, y)
                x = min(max_width - 1, x)
                width = max(x + 1, width)
                height = max(y + 1, height)
                while len(document.ch) <= y:
                    document.ch.append([])
                    document.bg.append([])
                    document.fg.append([])
            elif isinstance(instruction, stransi.SetClear):
                def clear_line(row_to_clear: int, before: bool, after: bool):
                    cols_to_clear: list[int] = []
                    if before:
                        cols_to_clear += range(0, len(document.ch[row_to_clear]))
                    if after:
                        cols_to_clear += range(x, len(document.ch[row_to_clear]))
                    for col_to_clear in cols_to_clear:
                        document.ch[row_to_clear][col_to_clear] = ' '
                        document.bg[row_to_clear][col_to_clear] = default_bg
                        document.fg[row_to_clear][col_to_clear] = default_fg
                match instruction.region:
                    case stransi.clear.Clear.LINE:
                        # Clear the current line
                        clear_line(y, True, True)
                    case stransi.clear.Clear.LINE_AFTER:
                        # Clear the current line after the cursor
                        clear_line(y, False, True)
                    case stransi.clear.Clear.LINE_BEFORE:
                        # Clear the current line before the cursor
                        clear_line(y, True, False)
                    case stransi.clear.Clear.SCREEN:
                        # Clear the entire screen
                        for row_to_clear in range(len(document.ch)):
                            clear_line(row_to_clear, True, True)
                        # and reset the cursor to home
                        x, y = 0, 0
                    case stransi.clear.Clear.SCREEN_AFTER:
                        # Clear the screen after the cursor
                        for row_to_clear in range(y, len(document.ch)):
                            clear_line(row_to_clear, row_to_clear > y, True)
                    case stransi.clear.Clear.SCREEN_BEFORE:
                        # Clear the screen before the cursor
                        for row_to_clear in range(y):
                            clear_line(row_to_clear, True, row_to_clear < y)
            elif isinstance(instruction, stransi.SetAttribute):
                # Attribute
                pass
            elif isinstance(instruction, stransi.Unsupported):
                raise ValueError("Unknown instruction " + repr(instruction.token))
            else:
                raise ValueError("Unknown instruction type " + str(type(instruction)))
        document.width = width
        document.height = height
        # Handle minimum height.
        while len(document.ch) <= document.height:
            document.ch.append([])
            document.bg.append([])
            document.fg.append([])
        # Pad rows to a consistent width.
        for y in range(document.height):
            for x in range(len(document.ch[y]), document.width):
                document.ch[y].append(' ')
                document.bg[y].append(default_bg)
                document.fg[y].append(default_fg)
        return document
    
    @staticmethod
    def from_text(text: str, default_bg: str = "#ffffff", default_fg: str = "#000000") -> 'AnsiArtDocument':
        """Creates a document from the given text, detecting if it uses ANSI control codes or not."""
        if ansi_detector_pattern.search(text):
            return AnsiArtDocument.from_ansi(text, default_bg, default_fg)
        else:
            return AnsiArtDocument.from_plain(text, default_bg, default_fg)

    @staticmethod
    def from_image_format(content: bytes) -> 'AnsiArtDocument':
        """Creates a document from the given bytes, detecting the file format.
        
        Raises UnidentifiedImageError if the format is not detected.
        """
        image = Image.open(io.BytesIO(content))
        rgb_image = image.convert('RGB') # handles indexed images, etc.
        width, height = rgb_image.size
        document = AnsiArtDocument(width, height)
        for y in range(height):
            for x in range(width):
                r, g, b = rgb_image.getpixel((x, y))  # type: ignore
                document.bg[y][x] = "#" + hex(r)[2:].zfill(2) + hex(g)[2:].zfill(2) + hex(b)[2:].zfill(2)  # type: ignore
        return document

    @staticmethod
    def from_svg(svg: str, default_bg: str = "#ffffff", default_fg: str = "#000000") -> 'AnsiArtDocument':
        """Creates a document from an SVG containing a character grid with rects for cell backgrounds.
        
        - If the SVG contains a special <ansi> element, this is used instead of anything else.
        Otherwise it falls back to flexible grid detection:
        - rect elements can be in any order.
        - rect elements can even be in different groups, however transforms are not considered.
        - rect elements can vary in size, spanning different numbers of cells, and the grid can be wonky.
        - rect elements can be missing, in which case the default background is used.
        - rect elements that frame the entire grid are ignored. (maybe should be used for background color?)
        - if there are any rect elements outside the grid, they will extend the grid; they're not distinguished.
        - fill OR style attributes (of rect/text elements) are used to determine the background/foreground colors.
        - text elements are assumed to be belonging to the cell according to their x/y,
          without regard to their size (textLength) or alignment (text-anchor).
        - stylesheets are partially supported.
        - not all CSS/SVG color formats are supported.

        To test the flexibility of this loader, I created pathological_character_grid.svg
        It contains out-of-order unevenly sized rects, missing rects, a background rect, and an emoji.
        It doesn't currently contain varying color formats, font sizes, alignments, or transforms,
        and it only uses style rather than fill, and text with tspan rather than text without.
        It also doesn't have spanned rects, because I didn't realize that was a thing until afterward.
        (Fun fact: I got the pathological SVG working before the rigid grid SVG as saved by the app.)

        To test it, run the following command:
        textual run --dev "src.textual_paint.paint --language en --clear-screen --inspect-layout --restart-on-changes 'samples/pathological_character_grid.svg'" --press ctrl+shift+s,left,left,left,left,.,s,a,v,e,d,enter,enter
        and check samples/pathological_character_grid.saved.svg
        There's also useful debug visuals saved in debug.svg (if enabled).
        Then add ".saved" to that command and run it to check the saved file.
        """
        import xml.etree.ElementTree as ET
        root = ET.fromstring(svg)

        ansi_el = root.find(".//{http://github.com/1j01/textual-paint}ansi")
        if ansi_el is not None:
            if ansi_el.text is None:
                return AnsiArtDocument(1, 1, default_bg, default_fg)
            ansi_text = base64.b64decode(ansi_el.text).decode("utf-8")
            return AnsiArtDocument.from_ansi(ansi_text, default_bg, default_fg)

        def add_debug_marker(x: float, y: float, color: str) -> None:
            """Adds a circle to the SVG at the given position, for debugging."""
            if not DEBUG_SVG_LOADING:
                return
            # without the namespace, it won't show up!
            marker = ET.Element("{http://www.w3.org/2000/svg}circle")
            marker.attrib["cx"] = str(x)
            marker.attrib["cy"] = str(y)
            marker.attrib["r"] = "1"
            marker.attrib["fill"] = color
            marker.attrib["stroke"] = "black"
            marker.attrib["stroke-width"] = "0.1"
            root.append(marker)

        # Parse stylesheets.
        # Textual's CSS parser can't handle at-rules like the @font-face in the SVG,
        # as of textual 0.24.1, so we either need to parse it manually or remove it.
        from textual.css.parse import parse
        from textual.css.model import RuleSet
        rule_sets: list[RuleSet] = []
        # OK this is seriously hacky. It doesn't support browser CSS really at all,
        # so I'm rewriting properties as different properties that it does support.
        property_map = {
            "fill": "color",
        }
        reverse_property_map = {v: k for k, v in property_map.items()}
        def rewrite_property(match: re.Match[str]) -> str:
            property_name = match.group(1)
            property_value = match.group(2)
            
            if property_name in property_map:
                rewritten_name = property_map[property_name]
                return f"{rewritten_name}: {property_value}"
            
            return match.group(0)  # Return the original match if no rewrite is needed

        for style_element in root.findall(".//{http://www.w3.org/2000/svg}style"):
            assert style_element.text is not None, "style element has no text"
            css = style_element.text
            at_rule_pattern = r"\s*@[\w-]+\s*{[^}]+}"  # doesn't handle nested braces
            css = re.sub(at_rule_pattern, "", css)
            property_pattern = r"([\w-]+)\s*:\s*([^;}]+)"

            css = re.sub(property_pattern, rewrite_property, css)

            for rule_set in parse(css, "inline <style> (modified)"):
                rule_sets.append(rule_set)
        # Apply stylesheets as inline styles.
        for rule_set in rule_sets:
            # list[tuple[str, Specificity6, Any]]
            rules = rule_set.styles.extract_rules((0, 0, 0))
            for css_selector in rule_set.selector_names:
                # Just need to handle class and id selectors.
                if css_selector.startswith("."):
                    class_name = css_selector[1:]
                    # xpath = f".//*[contains(@class, '{class_name}')]" # not supported
                    xpath = f".//*[@class='{class_name}']"
                elif css_selector.startswith("#"):
                    id = css_selector[1:]
                    xpath = f".//*[@id='{id}']"
                else:
                    # xpath = "./.." # root's parent never matches
                    # (absolute xpath is not allowed here, but we're querying from root)
                    # Alternatively, we could do this:
                    xpath = ".//*[id='never-match-me-please']"
                for element in root.findall(xpath):
                    for rule in rules:
                        prop, _, value = rule
                        prop = reverse_property_map.get(prop, prop)
                        # it adds auto_color: False when setting a color; hacks on top of hacks
                        if isinstance(value, str):
                            element.attrib[prop] = value
                        elif isinstance(value, Color):
                            element.attrib[prop] = value.hex

        # Search for rect elements to define the background, and the cell locations.
        rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
        if len(rects) == 0:
            raise ValueError("No rect elements found in SVG.")
        # Remove any rects that contain other rects.
        # This targets any background/border rects framing the grid.
        # TODO: fix combinatorial explosion (maybe sort by size and do something fancier with that?)
        # Collision bucketization could apply here, but seems like overkill.
        # And what would be the bucket size? 1/10th of the smallest rect?
        # We haven't determined the cell size yet.
        def rect_contains(outer_rect: ET.Element, inner_rect: ET.Element) -> bool:
            return (
                float(outer_rect.attrib["x"]) <= float(inner_rect.attrib["x"]) and
                float(outer_rect.attrib["y"]) <= float(inner_rect.attrib["y"]) and
                float(outer_rect.attrib["x"]) + float(outer_rect.attrib["width"]) >= float(inner_rect.attrib["x"]) + float(inner_rect.attrib["width"]) and
                float(outer_rect.attrib["y"]) + float(outer_rect.attrib["height"]) >= float(inner_rect.attrib["y"]) + float(inner_rect.attrib["height"])
            )
        rects_to_ignore: set[ET.Element] = set()
        for i, outer_rect in enumerate(rects):
            for inner_rect in rects[i + 1:]:
                if outer_rect != inner_rect and rect_contains(outer_rect, inner_rect):
                    rects_to_ignore.add(outer_rect)
                    # Combinatorial explosion is much worse with logging enabled.
                    # print("Ignoring outer_rect: " + ET.tostring(outer_rect, encoding="unicode"))
                    # For debugging, outline the ignored rect.
                    if DEBUG_SVG_LOADING:
                        outer_rect.attrib["style"] = "stroke:#ff0000;stroke-width:1;stroke-dasharray:1,1;fill:none"

        rects = [rect for rect in rects if rect not in rects_to_ignore]

        # This could technically happen if there are two rects of the same size and position.
        assert len(rects) > 0, "No rect elements after removing rects containing other rects."

        # Find the cell size.
        # (This starts with a guess, and then is refined after guessing the document bounds.)
        # Strategy 1: average the rect sizes.
        # cell_width = sum(float(rect.attrib["width"]) for rect in rects) / len(rects)
        # cell_height = sum(float(rect.attrib["height"]) for rect in rects) / len(rects)
        # Rects can span multiple cells, so this doesn't turn out well.
        # Strategy 2: find the smallest rect.
        # cell_width = min(float(rect.attrib["width"]) for rect in rects)
        # cell_height = min(float(rect.attrib["height"]) for rect in rects)
        # That way there's at least a decent chance of it being a single cell.
        # But this doesn't contend with varying cell sizes of the pathological test case.
        # Strategy 3: find the smallest rect, then sort rects into rows and columns,
        # using the smallest rect as a baseline to decide what constitutes a row/column gap,
        # then use the average spacing between rects in adjacent rows/columns,
        # also using the smallest rect to avoid averaging in gaps that are more than one cell.
        # TODO: handle case that there's no 1x1 cell rect.
        min_width = min(float(rect.attrib["width"]) for rect in rects)
        min_height = min(float(rect.attrib["height"]) for rect in rects)
        # Start with each rect in its own track, then join tracks that are close enough.
        measures: dict[str, float] = {}
        Track = NamedTuple("Track", [("rects", list[ET.Element]), ("min_center", float), ("max_center", float)])
        def join_tracks(track1: Track, track2: Track) -> Track:
            return Track(track1.rects + track2.rects, min(track1.min_center, track2.min_center), max(track1.max_center, track2.max_center))
        def rect_center(rect: ET.Element, coord_attrib: str, size_attrib: str) -> float:
            return float(rect.attrib[coord_attrib]) + float(rect.attrib[size_attrib]) / 2
        axes: list[tuple[str, str, float]] = [("x", "width", min_width), ("y", "height", min_height)]
        for (coord_attrib, size_attrib, min_rect_size) in axes:
            # Can't have too many rects or this will be slow.
            # Note: this optimization invalidates most of the grid estimation strategy here,
            # without the second sort in the opposite axis.
            # (But it still worked without it, for the few cases I tested,
            # but probably more through luck of the first rect being the right size or something like that.
            # Um, not that, because it's using the spacing between rects, right? but something like that.)
            # (At any rate, just look at the debug.svg output to see what I mean.)
            # TODO: is the first sort even necessary?
            rects.sort(key=lambda rect: float(rect.attrib[coord_attrib]))
            rects.sort(key=lambda rect: float(rect.attrib["x" if coord_attrib == "y" else "y"]))
            max_rects = 30
            # Have to ignore rects that span multiple cells, since their centers can be half-off the grid
            # of cell-sized rect centers (which is normally half-off from the grid of cell corners).
            max_rect_size = min_rect_size * 1.5
            tracks = [
                Track(
                    [rect],
                    rect_center(rect, coord_attrib, size_attrib),
                    rect_center(rect, coord_attrib, size_attrib),
                )
                for rect in rects[:max_rects] if float(rect.attrib[size_attrib]) <= max_rect_size
            ]
            joined = True
            while joined and len(tracks) > 1:
                joined = False
                for i in range(len(tracks)):
                    for j in range(i + 1, len(tracks)):
                        # The cell spacing will be at least min_rect_size, probably.
                        # However, if we join columns that are one cell apart, we'll
                        # fail to measure the cell spacing, it'll be too big.
                        # We only want to join rects within a single column.
                        max_offset = min_rect_size * 0.9
                        """
                        # i_min--j_min--i_max--j_max
                        # (always join)
                        # or
                        # j_min--i_min--j_max--i_max
                        # (always join)
                        # or
                        # i_min----------------i_max j_min----------------j_max
                        # (join if abs(i_max - j_min) <= max_offset)
                        # or
                        # j_min----------------j_max i_min----------------i_max
                        # (join if abs(j_max - i_min) <= max_offset)

                        i_min = tracks[i].min_center
                        i_max = tracks[i].max_center
                        j_min = tracks[j].min_center
                        j_max = tracks[j].max_center

                        ranges_overlap = (i_min <= j_min <= i_max) or (j_min <= i_min <= j_max)
                        ends_near = min(abs(i_max - j_min), abs(j_max - i_min)) <= max_offset
                        if ranges_overlap or ends_near:
                        """
                        i_center = (tracks[i].min_center + tracks[i].max_center) / 2
                        j_center = (tracks[j].min_center + tracks[j].max_center) / 2
                        if abs(i_center - j_center) <= max_offset:
                            tracks[i] = join_tracks(tracks[i], tracks[j])
                            del tracks[j]
                            joined = True
                            break
                    if joined:
                        break
            # Sort tracks
            tracks.sort(key=lambda track: (track.min_center + track.max_center) / 2)
            # Visualize the tracks for debug
            if DEBUG_SVG_LOADING:
                for track in tracks:
                    ET.SubElement(root, "{http://www.w3.org/2000/svg}rect", {
                        "x": str(track.min_center) if coord_attrib == "x" else "0",
                        "y": str(track.min_center) if coord_attrib == "y" else "0",
                        "width": str(track.max_center - track.min_center + 0.001) if coord_attrib == "x" else "100%",
                        "height": str(track.max_center - track.min_center + 0.001) if coord_attrib == "y" else "100%",
                        # "style": "stroke:#0000ff;stroke-width:0.1;stroke-dasharray:1,1;fill:none"
                        "style": "fill:#0000ff;fill-opacity:0.1;stroke:#0000ff;stroke-width:0.1"
                    })

            # Find the average spacing between tracks, ignoring gaps that are likely to be more than one cell.
            # I'm calling this gap because I'm lazy.
            max_gap = min_rect_size * 2
            all_gaps: list[float] = []
            gaps: list[float] = []
            for i in range(len(tracks) - 1):
                i_center = (tracks[i].max_center + tracks[i].min_center) / 2
                j_center = (tracks[i + 1].max_center + tracks[i + 1].min_center) / 2
                gap = abs(j_center - i_center) # abs shouldn't be necessary, but just in case I guess
                if DEBUG_SVG_LOADING:
                    ET.SubElement(root, "{http://www.w3.org/2000/svg}line", {
                        "x1": str(i_center) if coord_attrib == "x" else ("5%" if i % 2 == 0 else "2%"),
                        "y1": str(i_center) if coord_attrib == "y" else ("5%" if i % 2 == 0 else "2%"),
                        "x2": str(j_center) if coord_attrib == "x" else ("5%" if i % 2 == 0 else "2%"),
                        "y2": str(j_center) if coord_attrib == "y" else ("5%" if i % 2 == 0 else "2%"),
                        "stroke": "#ff0000" if gap > max_gap else "#0051ff",
                    })
                all_gaps.append(gap)
                if gap <= max_gap:
                    gaps.append(gap)
            if len(gaps) == 0:
                measures[coord_attrib] = min_rect_size
            else:
                measures[coord_attrib] = sum(gaps) / len(gaps)

        cell_width = measures["x"]
        cell_height = measures["y"]

        print("Initial cell size guess: " + str(cell_width) + " x " + str(cell_height))
        # Find the document bounds.
        min_x = min(float(rect.attrib["x"]) for rect in rects)
        min_y = min(float(rect.attrib["y"]) for rect in rects)
        max_x = max(float(rect.attrib["x"]) + float(rect.attrib["width"]) for rect in rects)
        max_y = max(float(rect.attrib["y"]) + float(rect.attrib["height"]) for rect in rects)
        add_debug_marker(min_x, min_y, "blue")
        add_debug_marker(max_x, max_y, "blue")
        width = int((max_x - min_x) / cell_width + 1/9)
        height = int((max_y - min_y) / cell_height + 1/9)
        # Adjust cell width/height based on document bounds.
        cell_width = (max_x - min_x) / width
        cell_height = (max_y - min_y) / height
        print("Refined cell size estimate: " + str(cell_width) + " x " + str(cell_height))
        # Create the document.
        document = AnsiArtDocument(width, height, default_bg, default_fg)
        # Fill the document with the background colors.
        def get_fill(el: ET.Element) -> Optional[str]:
            fill = None
            try:
                fill = el.attrib["fill"]
            except KeyError:
                try:
                    style = el.attrib["style"]
                except KeyError:
                    print("Warning: element has no fill or style attribute: " + ET.tostring(el, encoding="unicode"))
                else:
                    for style_part in style.split(";"):
                        if style_part.startswith("fill:"):
                            fill = style_part[len("fill:"):]
                            break
            if fill is None or fill == "none" or fill == "":
                print("Warning: element has no fill defined: " + ET.tostring(el, encoding="unicode"))
                return None
            try:
                r, g, b = Color.parse(fill).rgb
                return "#" + hex(r)[2:].zfill(2) + hex(g)[2:].zfill(2) + hex(b)[2:].zfill(2)
            except ColorParseError:
                print("Warning: element has invalid fill: " + ET.tostring(el, encoding="unicode"))
                return None

        for rect in rects:
            fill = get_fill(rect)
            for x_offset in range(int(float(rect.attrib["width"]) / cell_width + 1/2)):
                for y_offset in range(int(float(rect.attrib["height"]) / cell_height + 1/2)):
                    x = float(rect.attrib["x"]) + cell_width * (x_offset + 1/2)
                    y = float(rect.attrib["y"]) + cell_height * (y_offset + 1/2)
                    add_debug_marker(x, y, "red")
                    x = int((x - min_x) / cell_width)
                    y = int((y - min_y) / cell_height)
                    if fill is not None:
                        try:
                            document.bg[y][x] = fill
                        except IndexError:
                            print("Warning: rect out of bounds: " + ET.tostring(rect, encoding="unicode"))

        # Find text elements to define the foreground.
        texts = root.findall(".//{http://www.w3.org/2000/svg}text")
        if len(texts) == 0:
            raise ValueError("No text elements found in SVG.")
        for text in texts:
            # approximate center of text
            # y position really depends on font size, as well as the baseline y position.
            x = (float(text.attrib["x"]) + cell_width/2)
            y = (float(text.attrib["y"]) - cell_height/4)
            add_debug_marker(x, y, "yellow")
            x = int((x - min_x) / cell_width)
            y = int((y - min_y) / cell_height)

            ch = text.text
            if ch is None:
                tspans = text.findall(".//{http://www.w3.org/2000/svg}tspan")
                if len(tspans) == 0:
                    print("Warning: text element has no text or tspan: " + ET.tostring(text, encoding="unicode"))
                    continue
                ch = ""
                for tspan in tspans:
                    if tspan.text is not None:
                        ch += tspan.text
                    else:
                        print("Warning: tspan element has no text: " + ET.tostring(tspan, encoding="unicode"))
            # This is likely to cause problems with multi-character emojis, like flags,
            # although such characters are unlikely to work in the terminal anyway.
            # if len(ch) > 1:
            #     print("Warning: text element has more than one character: " + ET.tostring(text, encoding="unicode"))
            #     ch = ch[0]
            fill = get_fill(text)
            try:
                document.ch[y][x] = ch
                if fill is not None:
                    document.fg[y][x] = fill
            except IndexError:
                print("Warning: text element is out of bounds: " + ET.tostring(text, encoding="unicode"))
                continue
        
        # For debugging, write the SVG with the ignored rects outlined, and coordinate markers added.
        if DEBUG_SVG_LOADING:
            ET.ElementTree(root).write("debug.svg", encoding="unicode")

        return document

    @staticmethod
    def decode_based_on_file_extension(content: bytes, file_path: str, default_bg: str = "#ffffff", default_fg: str = "#000000") -> 'AnsiArtDocument':
        """Creates a document from the given bytes, detecting the file format.
        
        Raises FormatReadNotSupported if the file format is not supported for reading. Some are write-only.
        Raises UnicodeDecodeError, which can be a very long message, so make sure to handle it!
        Raises UnidentifiedImageError if the format is not detected.
        """
        format_id = AnsiArtDocument.format_from_extension(file_path)
        # print("Supported image formats for reading:", Image.OPEN.keys())
        # TODO: try loading as image first, then as text if that fails with UnidentifiedImageError
        # That way it can handle images without file extensions.
        if format_id in Image.OPEN:
            return AnsiArtDocument.from_image_format(content)
        elif format_id == "ANSI":
            return AnsiArtDocument.from_ansi(content.decode('utf-8'), default_bg, default_fg)
        elif format_id == "IRC":
            return AnsiArtDocument.from_irc(content.decode('utf-8'), default_bg, default_fg)
        elif format_id == "PLAINTEXT":
            return AnsiArtDocument.from_plain(content.decode('utf-8'), default_bg, default_fg)
        elif format_id == "SVG":
            return AnsiArtDocument.from_svg(content.decode('utf-8'), default_bg, default_fg)
        elif format_id in Image.SAVE or format_id in ["HTML", "RICH_CONSOLE_MARKUP"]:
            # This is a write-only format.
            raise FormatReadNotSupported(localized_message=_("Cannot read files saved as %1 format.", format_id))
        else:
            # This is an unknown format.
            # For now at least, I'm preserving the behavior of loading as ANSI/PLAINTEXT.
            return AnsiArtDocument.from_text(content.decode('utf-8'), default_bg, default_fg)

class Action:
    """An action that can be undone efficiently using a region update.

    This uses an image patch to undo the action, except for resizes, which store the entire document state.
    In either case, the action stores image data in sub_image_before.
    The image data from _after_ the action is not stored, because the Action exists only for undoing.

    TODO: In the future it would be more efficient to use a mask for the region update,
    to store only modified pixels, and use RLE compression on the mask and image data.
    
    NOTE: Not to be confused with Textual's `class Action(Event)`, or the type of law suit.
    Indeed, Textual's actions are used significantly in this application, with action_* methods,
    but this class is not related. Perhaps I should rename this class to UndoOp, or HistoryOperation.
    """

    def __init__(self, name: str, region: Region|None = None) -> None:
        """Initialize the action using the document state before modification."""
        self.name = name
        """The name of the action, for future display."""
        self.region = region
        """The region of the document that was modified."""
        self.is_full_update = False
        """Indicates that this action resizes the document, and thus should not be undone with a region update.
        
        That is, unless in the future region updates support a mask and work in tandem with resizes.
        """
        self.sub_image_before: AnsiArtDocument|None = None
        """The image data from the region of the document before modification."""

    def update(self, document: AnsiArtDocument) -> None:
        """Grabs the image data from the current region of the document."""
        assert self.region is not None, "Action.update called without a defined region"
        self.sub_image_before = AnsiArtDocument(self.region.width, self.region.height)
        self.sub_image_before.copy_region(document, self.region)

    def undo(self, target_document: AnsiArtDocument) -> None:
        """Undo this action. Note that a canvas refresh is not performed here."""
        # Warning: these warnings are hard to see in the terminal, since the terminal is being redrawn.
        # You have to use `textual console` to see them.
        if not self.sub_image_before:
            print("Warning: No undo data for Action. (Action.undo was called before any Action.update)")
            return
        if self.region is None:
            print("Warning: Action.undo called without a defined region")
            return
        if self.is_full_update:
            target_document.copy(self.sub_image_before)
        else:
            target_document.copy_region(self.sub_image_before, target_region=self.region)

def bresenham_walk(x0: int, y0: int, x1: int, y1: int) -> Iterator[tuple[int, int]]:
    """Bresenham's line algorithm"""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err = err - dy
            x0 = x0 + sx
        if e2 < dx:
            err = err + dx
            y0 = y0 + sy


def polygon_walk(points: list[Offset]) -> Iterator[tuple[int, int]]:
    """Yields points along the perimeter of a polygon."""
    for i in range(len(points)):
        yield from bresenham_walk(
            points[i][0],
            points[i][1],
            points[(i + 1) % len(points)][0],
            points[(i + 1) % len(points)][1]
        )

def polyline_walk(points: list[Offset]) -> Iterator[tuple[int, int]]:
    """Yields points along a polyline (unclosed polygon)."""
    for i in range(len(points) - 1):
        yield from bresenham_walk(
            points[i][0],
            points[i][1],
            points[i + 1][0],
            points[i + 1][1]
        )

def is_inside_polygon(x: int, y: int, points: list[Offset]) -> bool:
    """Returns True if the point is inside the polygon."""
    # https://stackoverflow.com/a/217578
    # Actually I just got this from Copilot, and don't know the source
    n = len(points)
    inside = False
    p1x, p1y = points[0]
    for i in range(n + 1):
        p2x, p2y = points[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    x_intersection: float = x  # Avoid "possibly unbound" type checker error
                    # I don't know if this is right; should it flip `inside` in this case?
                    # Is this an actual case that can occur, where p1y == p2y AND p1x != p2x?
                    if p1y != p2y:
                        x_intersection = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= x_intersection:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

# def polygon_fill(points: list[Offset]) -> Iterator[tuple[int, int]]:
#     """Yields points inside a polygon."""

#     # Find the bounding box
#     min_x = min(points, key=lambda p: p[0])[0]
#     min_y = min(points, key=lambda p: p[1])[1]
#     max_x = max(points, key=lambda p: p[0])[0]
#     max_y = max(points, key=lambda p: p[1])[1]

#     # Check each point in the bounding box, and yield any points that are inside the polygon
#     for x in range(min_x, max_x + 1):
#         for y in range(min_y, max_y + 1):
#             if is_inside_polygon(x, y, points):
#                 yield x, y

# adapted from https://github.com/Pomax/bezierjs
def compute_bezier(t: float, start_x: float, start_y: float, control_1_x: float, control_1_y: float, control_2_x: float, control_2_y: float, end_x: float, end_y: float) -> tuple[float, float]:
    """Returns a point along a bezier curve."""
    mt = 1 - t
    mt2 = mt * mt
    t2 = t * t

    a = mt2 * mt
    b = mt2 * t * 3
    c = mt * t2 * 3
    d = t * t2

    return (
        a * start_x + b * control_1_x + c * control_2_x + d * end_x,
        a * start_y + b * control_1_y + c * control_2_y + d * end_y,
    )

# It's possible to walk a bezier curve more correctly,
# but is it possible to tell the difference?
def bezier_curve_walk(start_x: float, start_y: float, control_1_x: float, control_1_y: float, control_2_x: float, control_2_y: float, end_x: float, end_y: float) -> Iterator[tuple[int, int]]:
    """Yields points along a bezier curve."""
    steps = 100
    point_a = (start_x, start_y)
    # TypeError: 'float' object cannot be interpreted as an integer
    # for t in range(0, 1, 1 / steps):
    for i in range(steps):
        t = i / steps
        point_b = compute_bezier(t, start_x, start_y, control_1_x, control_1_y, control_2_x, control_2_y, end_x, end_y)
        yield from bresenham_walk(int(point_a[0]), int(point_a[1]), int(point_b[0]), int(point_b[1]))
        point_a = point_b

def quadratic_curve_walk(start_x: float, start_y: float, control_x: float, control_y: float, end_x: float, end_y: float) -> Iterator[tuple[int, int]]:
    """Yields points along a quadratic curve."""
    return bezier_curve_walk(start_x, start_y, control_x, control_y, control_x, control_y, end_x, end_y)

def midpoint_ellipse(xc: int, yc: int, rx: int, ry: int) -> Iterator[tuple[int, int]]:
    """Midpoint ellipse drawing algorithm. Yields points out of order, and thus can't legally be called a "walk", except in Britain."""
    # Source: https://www.geeksforgeeks.org/midpoint-ellipse-drawing-algorithm/

    x = 0
    y = ry
 
    # Initial decision parameter of region 1
    d1 = ((ry * ry) - (rx * rx * ry) +
                      (0.25 * rx * rx))
    dx = 2 * ry * ry * x
    dy = 2 * rx * rx * y
 
    # For region 1
    while (dx < dy):
        # Yield points based on 4-way symmetry
        yield x + xc, y + yc
        yield -x + xc, y + yc
        yield x + xc, -y + yc
        yield -x + xc, -y + yc
 
        # Checking and updating value of
        # decision parameter based on algorithm
        if (d1 < 0):
            x += 1
            dx = dx + (2 * ry * ry)
            d1 = d1 + dx + (ry * ry)
        else:
            x += 1
            y -= 1
            dx = dx + (2 * ry * ry)
            dy = dy - (2 * rx * rx)
            d1 = d1 + dx - dy + (ry * ry)
 
    # Decision parameter of region 2
    d2 = (((ry * ry) * ((x + 0.5) * (x + 0.5))) +
          ((rx * rx) * ((y - 1) * (y - 1))) -
           (rx * rx * ry * ry))
 
    # Plotting points of region 2
    while (y >= 0):
        # Yielding points based on 4-way symmetry
        yield x + xc, y + yc
        yield -x + xc, y + yc
        yield x + xc, -y + yc
        yield -x + xc, -y + yc
 
        # Checking and updating parameter
        # value based on algorithm
        if (d2 > 0):
            y -= 1
            dy = dy - (2 * rx * rx)
            d2 = d2 + (rx * rx) - dy
        else:
            y -= 1
            x += 1
            dx = dx + (2 * ry * ry)
            dy = dy - (2 * rx * rx)
            d2 = d2 + dx - dy + (rx * rx)

def flood_fill(document: AnsiArtDocument, x: int, y: int, fill_ch: str, fill_fg: str, fill_bg: str) -> Region|None:
    """Flood fill algorithm."""

    # Get the original value of the cell.
    # This is the color to be replaced.
    original_fg = document.fg[y][x]
    original_bg = document.bg[y][x]
    original_ch = document.ch[y][x]

    # Track the region affected by the fill.
    min_x = x
    min_y = y
    max_x = x
    max_y = y

    def inside(x: int, y: int) -> bool:
        """Returns true if the cell at the given coordinates matches the color to be replaced. Treats foreground color as equal if character is a space."""
        if x < 0 or x >= document.width or y < 0 or y >= document.height:
            return False
        return (
            document.ch[y][x] == original_ch and
            document.bg[y][x] == original_bg and
            (original_ch == " " or document.fg[y][x] == original_fg) and
            (document.ch[y][x] != fill_ch or document.bg[y][x] != fill_bg or document.fg[y][x] != fill_fg)
        )

    def set_cell(x: int, y: int) -> None:
        """Sets the cell at the given coordinates to the fill color, and updates the region bounds."""
        document.ch[y][x] = fill_ch
        document.fg[y][x] = fill_fg
        document.bg[y][x] = fill_bg
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    # Simple translation of the "final, combined-scan-and-fill span filler"
    # pseudo-code from https://en.wikipedia.org/wiki/Flood_fill
    if not inside(x, y):
        return None
    stack: list[tuple[int, int, int, int]] = [(x, x, y, 1), (x, x, y - 1, -1)]
    while stack:
        x1, x2, y, dy = stack.pop()
        x = x1
        if inside(x, y):
            while inside(x - 1, y):
                set_cell(x - 1, y)
                x = x - 1
        if x < x1:
            stack.append((x, x1-1, y-dy, -dy))
        while x1 <= x2:
            while inside(x1, y):
                set_cell(x1, y)
                x1 = x1 + 1
                stack.append((x, x1 - 1, y+dy, dy))
                if x1 - 1 > x2:
                    stack.append((x2 + 1, x1 - 1, y-dy, -dy))
            x1 = x1 + 1
            while x1 < x2 and not inside(x1, y):
                x1 = x1 + 1
            x = x1

    # Return the affected region.
    return Region(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)

def scale_region(region: Region, scale: int) -> Region:
    """Returns the region scaled by the given factor."""
    return Region(region.x * scale, region.y * scale, region.width * scale, region.height * scale)

class Canvas(Widget):
    """The image document widget."""

    magnification = reactive(1, layout=True)
    show_grid = reactive(False)

    # Is it kosher to include an event in a message?
    # Is it better (and possible) to bubble up the event, even though I'm capturing the mouse?
    # Or would it be better to just have Canvas own duplicate state for all tool parameters?
    # That's what I was refactoring to avoid. So far I've made things more complicated,
    # but I'm betting it will be good when implementing different tools.
    # Maybe the PaintApp widget can capture the mouse events instead?
    # Not sure if that would work as nicely when implementing selections.
    # I'd have to think about it.
    # But it would make the Canvas just be a widget for rendering, which seems good.
    class ToolStart(Message):
        """Message when starting drawing."""

        def __init__(self, mouse_down_event: events.MouseDown) -> None:
            self.x = mouse_down_event.x
            self.y = mouse_down_event.y
            self.button = mouse_down_event.button
            self.ctrl = mouse_down_event.ctrl
            super().__init__()
    
    class ToolUpdate(Message):
        """Message when dragging on the canvas."""

        def __init__(self, mouse_move_event: events.MouseMove) -> None:
            self.x = mouse_move_event.x
            self.y = mouse_move_event.y
            super().__init__()

    class ToolStop(Message):
        """Message when releasing the mouse."""

        def __init__(self, mouse_up_event: events.MouseUp) -> None:
            self.x = mouse_up_event.x
            self.y = mouse_up_event.y
            super().__init__()

    class ToolPreviewUpdate(Message):
        """Message when moving the mouse while the mouse is up."""

        def __init__(self, mouse_move_event: events.MouseMove) -> None:
            self.x = mouse_move_event.x
            self.y = mouse_move_event.y
            super().__init__()

    class ToolPreviewStop(Message):
        """Message when the mouse leaves the canvas while previewing (not while drawing)."""

        def __init__(self) -> None:
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the canvas."""
        super().__init__(**kwargs)
        self.image: AnsiArtDocument|None = None
        self.pointer_active: bool = False
        self.magnifier_preview_region: Optional[Region] = None
        self.select_preview_region: Optional[Region] = None
        self.which_button: Optional[int] = None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Called when a mouse button is pressed.

        This either starts drawing, or if both mouse buttons are pressed, cancels the current action.
        """
        if self.app.has_class("view_bitmap"):
            # Exiting is handled by the PaintApp.
            return

        self.fix_mouse_event(event)  # not needed, pointer isn't captured yet.
        event.x //= self.magnification
        event.y //= self.magnification

        if self.pointer_active and self.which_button != event.button:
            assert isinstance(self.app, PaintApp)
            self.app.stop_action_in_progress()
            return

        self.post_message(self.ToolStart(event))
        self.pointer_active = True
        self.which_button = event.button
        self.capture_mouse(True)
    
    def fix_mouse_event(self, event: events.MouseEvent) -> None:
        """Work around inconsistent widget-relative mouse coordinates by calculating from screen coordinates."""
        # Hack to fix mouse coordinates, not needed for mouse down,
        # or while the mouse is up.
        # This seems like a bug.
        # I think it's due to coordinates being calculated differently during mouse capture.
        # if self.pointer_active:
        #     assert isinstance(self.parent, Widget)
        #     event.x += int(self.parent.scroll_x)
        #     event.y += int(self.parent.scroll_y)
        # The above fix sometimes works but maybe sometimes shouldn't apply or isn't right.
        # In order to make this robust without knowing the exact cause,
        # I'm going to always calculate straight from the screen coordinates.
        # This should also make it robust against the bugs in the library being fixed.
        # node: DOMNode|None = self
        offset = event.screen_offset
        # while node:
        #     offset = offset - node.offset
        #     node = node.parent
        # assert isinstance(self.parent, Widget)
        offset = offset - self.region.offset  #+ Offset(int(self.parent.scroll_x), int(self.parent.scroll_y))
        event.x = offset.x
        event.y = offset.y


    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Called when the mouse is moved. Update the tool action or preview."""
        self.fix_mouse_event(event)
        event.x //= self.magnification
        event.y //= self.magnification

        if self.pointer_active:
            self.post_message(self.ToolUpdate(event))
        else:
            # I put this in the else block just for performance.
            # Hopefully it wouldn't matter much, but
            # the pointer should never be active in View Bitmap mode.
            if self.app.has_class("view_bitmap"):
                return
            self.post_message(self.ToolPreviewUpdate(event))

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Called when a mouse button is released. Stop the current tool."""
        self.fix_mouse_event(event)
        event.x //= self.magnification
        event.y //= self.magnification
        
        if self.pointer_active:
            self.post_message(self.ToolStop(event))
        self.pointer_active = False
        self.capture_mouse(False)

    def on_leave(self, event: events.Leave) -> None:
        """Called when the mouse leaves the canvas. Stop preview if applicable."""
        if not self.pointer_active:
            self.post_message(self.ToolPreviewStop())

    def get_content_width(self, container: Size, viewport: Size) -> int:
        """Defines the intrinsic width of the widget."""
        if self.image is None:
            return 0 # shouldn't really happen
        return self.image.width * self.magnification

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        """Defines the intrinsic height of the widget."""
        if self.image is None:
            return 0 # shouldn't really happen
        return self.image.height * self.magnification

    def render_line(self, y: int) -> Strip:
        """Render a line of the widget. y is relative to the top of the widget."""
        assert self.image is not None
        # self.size.width/height already is multiplied by self.magnification.
        if y >= self.size.height:
            return Strip.blank(self.size.width)
        segments: list[Segment] = []
        sel = self.image.selection

        # Avoiding "possibly unbound" errors.
        magnifier_preview_region = None
        inner_magnifier_preview_region = None
        select_preview_region = None
        inner_select_preview_region = None
        selection_region = None
        inner_selection_region = None

        if self.magnifier_preview_region:
            magnifier_preview_region = scale_region(self.magnifier_preview_region, self.magnification)
            inner_magnifier_preview_region = magnifier_preview_region.shrink((1, 1, 1, 1))
        if self.select_preview_region:
            select_preview_region = scale_region(self.select_preview_region, self.magnification)
            inner_select_preview_region = select_preview_region.shrink((1, 1, 1, 1))
        if sel:
            selection_region = scale_region(sel.region, self.magnification)
            inner_selection_region = selection_region.shrink((1, 1, 1, 1))
        for x in range(self.size.width):
            cell_x = x // self.magnification
            cell_y = y // self.magnification
            try:
                if sel and sel.contained_image and sel.region.contains(cell_x, cell_y) and (sel.mask is None or sel.mask[cell_y - sel.region.y][cell_x - sel.region.x]):
                    bg = sel.contained_image.bg[cell_y - sel.region.y][cell_x - sel.region.x]
                    fg = sel.contained_image.fg[cell_y - sel.region.y][cell_x - sel.region.x]
                    ch = sel.contained_image.ch[cell_y - sel.region.y][cell_x - sel.region.x]
                else:
                    bg = self.image.bg[cell_y][cell_x]
                    fg = self.image.fg[cell_y][cell_x]
                    ch = self.image.ch[cell_y][cell_x]
            except IndexError:
                # This should be easier to debug visually.
                bg = "#555555"
                fg = "#cccccc"
                ch = "?"
            if self.magnification > 1:
                ch = self.big_ch(ch, x % self.magnification, y % self.magnification)
                if self.show_grid and self.magnification >= 4:
                    if x % self.magnification == 0 or y % self.magnification == 0:
                        # Not setting `bg` here, because:
                        # Its actually useful to see the background color of the cell,
                        # as it lets you distinguish between a space " " and a full block "█".
                        # Plus this lets the grid be more subtle, visually taking up less than a cell.
                        fg = "#c0c0c0" if (x + y) % 2 == 0 else "#808080"
                        if x % self.magnification == 0 and y % self.magnification == 0:
                            ch = "▛" # "┼" # (🭽 may render as wide)
                        elif x % self.magnification == 0:
                            ch = "▌" # "┆" # (▏, not 🭰)
                        elif y % self.magnification == 0:
                            ch = "▀" # "┄" # (▔, not 🭶)
            style = Style(color=fg, bgcolor=bg)
            assert style.color is not None
            assert style.bgcolor is not None
            def within_text_selection_highlight(textbox: Selection) -> int:
                if cell_x >= textbox.region.right or cell_x < textbox.region.x:
                    # Prevent inverting outside the textbox.
                    return False
                def offset_to_text_index(offset: Offset) -> int:
                    return offset.y * textbox.region.width + offset.x
                start_index = offset_to_text_index(textbox.text_selection_start)
                end_index = offset_to_text_index(textbox.text_selection_end)
                min_index = min(start_index, end_index)
                max_index = max(start_index, end_index)
                cell_index = offset_to_text_index(Offset(cell_x, cell_y) - textbox.region.offset)
                return min_index <= cell_index <= max_index
            assert isinstance(self.app, PaintApp)
            if (
                (self.magnifier_preview_region and magnifier_preview_region.contains(x, y) and (not inner_magnifier_preview_region.contains(x, y))) or  # type: ignore
                (self.select_preview_region and select_preview_region.contains(x, y) and (not inner_select_preview_region.contains(x, y))) or  # type: ignore
                (sel and (not sel.textbox_mode) and (self.app.selection_drag_offset is None) and selection_region.contains(x, y) and (not inner_selection_region.contains(x, y))) or  # type: ignore
                (sel and sel.textbox_mode and within_text_selection_highlight(sel))
            ):
                # invert the colors
                inverse_color = f"rgb({255 - style.color.triplet.red},{255 - style.color.triplet.green},{255 - style.color.triplet.blue})"
                inverse_bgcolor = f"rgb({255 - style.bgcolor.triplet.red},{255 - style.bgcolor.triplet.green},{255 - style.bgcolor.triplet.blue})"
                style = Style(color=inverse_color, bgcolor=inverse_bgcolor)
            segments.append(Segment(ch, style))
        return Strip(segments, self.size.width)
    
    def refresh_scaled_region(self, region: Region) -> None:
        """Refresh a region of the widget, scaled by the magnification."""
        if self.magnification == 1:
            self.refresh(region)
            return
        # TODO: are these offsets needed? I added them because of a problem which I've fixed
        self.refresh(Region(
            (region.x - 1) * self.magnification,
            (region.y - 1) * self.magnification,
            (region.width + 2) * self.magnification,
            (region.height + 2) * self.magnification,
        ))
    
    def watch_magnification(self) -> None:
        """Called when magnification changes."""
        self.active_meta_glyph_font = largest_font_that_fits(self.magnification, self.magnification)

    def big_ch(self, ch: str, x: int, y: int) -> str:
        """Return a character part of a meta-glyph."""
        if self.active_meta_glyph_font and ch in self.active_meta_glyph_font.glyphs:
            glyph_lines = self.active_meta_glyph_font.glyphs[ch]
            x -= (self.magnification - self.active_meta_glyph_font.width) // 2
            y -= (self.magnification - self.active_meta_glyph_font.height) // 2
            if y >= len(glyph_lines) or y < 0:
                return " "
            glyph_line = glyph_lines[y]
            if x >= len(glyph_line) or x < 0:
                return " "
            return glyph_line[x]
        if ch in " ░▒▓█":
            return ch
        match ch:
            # These are now obsolete special cases of below fractional block character handling.
            # case "▄":
            #     return "█" if y >= self.magnification // 2 else " "
            # case "▀":
            #     return "█" if y < self.magnification // 2 else " "
            # case "▌":
            #     return "█" if x < self.magnification // 2 else " "
            # case "▐":
            #     return "█" if x >= self.magnification // 2 else " "
            # Corner triangles
            case "◣":
                diagonal = x - y
                return "█" if diagonal < 0 else " " if diagonal > 0 else "◣"
            case "◥":
                diagonal = x - y
                return "█" if diagonal > 0 else " " if diagonal < 0 else "◥"
            case "◢":
                diagonal = x + y + 1 - self.magnification
                return "█" if diagonal > 0 else " " if diagonal < 0 else "◢"
            case "◤":
                diagonal = x + y + 1 - self.magnification
                return "█" if diagonal < 0 else " " if diagonal > 0 else "◤"
            case "╱":
                diagonal = x + y + 1 - self.magnification
                return "╱" if diagonal == 0 else " "
            case "╲":
                diagonal = x - y
                return "╲" if diagonal == 0 else " "
            case "╳":
                diagonal_1 = x + y + 1 - self.magnification
                diagonal_2 = x - y
                return "╲" if diagonal_2 == 0 else "╱" if diagonal_1 == 0 else " "
            case "/":
                diagonal = x + y + 1 - self.magnification
                return "/" if diagonal == 0 else " "
            case "\\":
                diagonal = x - y
                return "\\" if diagonal == 0 else " "
            # Fractional blocks
            # These are at the end because `in` may be slow.
            # Note: the order of the gradient strings is chosen so that
            # the dividing line is at the top/left at index 0.
            case ch if ch in "█▇▆▅▄▃▂▁":
                gradient = "█▇▆▅▄▃▂▁ "
                index = gradient.index(ch)
                threshold_y = int(index / 8 * self.magnification)
                if y == threshold_y:
                    # Within the threshold cell, which is at y here,
                    # use one of the fractional characters.
                    # If you look at a 3/8ths character, to scale it up 2x,
                    # you need a 6/8ths character. It simply scales with the magnification.
                    # If you look at a 6/8ths character, to scale it up 2x,
                    # you need a full block and a 4/8ths character, 4/8ths being the threshold cell here,
                    # so it needs to wrap around, taking the remainder.
                    return gradient[index * self.magnification % 8]
                elif y > threshold_y:
                    return "█"
                else:
                    return " "
            case ch if ch in "▏▎▍▌▋▊▉█":
                gradient = " ▏▎▍▌▋▊▉█"
                index = gradient.index(ch)
                threshold_x = int(index / 8 * self.magnification)
                if x == threshold_x:
                    return gradient[index * self.magnification % 8]
                elif x < threshold_x:
                    return "█"
                else:
                    return " "
            case ch if ch in "▔🮂🮃▀🮄🮅🮆█":
                gradient = " ▔🮂🮃▀🮄🮅🮆█"
                index = gradient.index(ch)
                threshold_y = int(index / 8 * self.magnification)
                if y == threshold_y:
                    return gradient[index * self.magnification % 8]
                elif y < threshold_y:
                    return "█"
                else:
                    return " "
            case ch if ch in "█🮋🮊🮉▐🮈🮇▕":
                gradient = "█🮋🮊🮉▐🮈🮇▕ "
                index = gradient.index(ch)
                threshold_x = int(index / 8 * self.magnification)
                if x == threshold_x:
                    return gradient[index * self.magnification % 8]
                elif x > threshold_x:
                    return "█"
                else:
                    return " "
            case _: pass
        # Fall back to showing the character in a single cell, approximately centered.
        if x == self.magnification // 2 and y == self.magnification // 2:
            return ch
        else:
            return " "


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

    selected_tool = var(Tool.pencil)
    """The currently selected tool."""
    return_to_tool = var(Tool.pencil)
    """Tool to switch to after using the Magnifier or Pick Color tools."""
    selected_bg_color = var(palette[0])
    """The currently selected background color. Unlike MS Paint, this acts as the primary color."""
    selected_fg_color = var(palette[len(palette) // 2])
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

    def watch_selected_tool(self, old_selected_tool: Tool, selected_tool: Tool) -> None:
        """Called when selected_tool changes."""
        for button in self.query(".tool_button"):
            assert isinstance(button, Button)
            button_tool = self.query_one("ToolsBox", ToolsBox).tool_by_button[button]
            button.set_class(selected_tool == button_tool, "selected")

    def watch_selected_bg_color(self, selected_bg_color: str) -> None:
        """Called when selected_bg_color changes."""
        self.query_one("#selected_color_char_input", CharInput).styles.background = selected_bg_color
        # CharInput now handles the background style itself PARTIALLY; it doesn't affect the whole area.

        if self.image.selection and self.image.selection.textbox_mode:
            assert self.image.selection.contained_image is not None, "textbox_mode without contained_image"
            for y in range(self.image.selection.region.height):
                for x in range(self.image.selection.region.width):
                    self.image.selection.contained_image.bg[y][x] = self.selected_bg_color
            self.canvas.refresh_scaled_region(self.image.selection.region)

    def watch_selected_fg_color(self, selected_fg_color: str) -> None:
        """Called when selected_fg_color changes."""
        # self.query_one("#selected_color_char_input", CharInput).styles.color = selected_fg_color
        # CharInput now handles this itself, because styles.color never worked to color the Input's text.
        # Well, it still needs to be updated.
        self.query_one("#selected_color_char_input", CharInput).refresh()

        if self.image.selection and self.image.selection.textbox_mode:
            assert self.image.selection.contained_image is not None, "textbox_mode without contained_image"
            for y in range(self.image.selection.region.height):
                for x in range(self.image.selection.region.width):
                    self.image.selection.contained_image.fg[y][x] = self.selected_fg_color
            self.canvas.refresh_scaled_region(self.image.selection.region)

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
        global palette
        if format_id == "IRC":
            palette = irc_palette + [irc_palette[0]] * (len(palette) - len(irc_palette))
            self.query_one(ColorsBox).update_palette()
        elif format_id == "PLAINTEXT":
            palette = ["#000000", "#ffffff"] + ["#ffffff"] * (len(palette) - 2)
            self.query_one(ColorsBox).update_palette()

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

    async def confirm_information_loss_async(self, format_id: str | None) -> Coroutine[None, None, bool]:
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
            if not button.has_class("details_button"):
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
        self.selected_bg_color = palette[0]
        self.selected_fg_color = palette[len(palette) // 2]
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

    def action_edit_colors(self, color_palette_index: int|None = None, as_foreground: bool = False) -> None:
        """Show dialog to edit colors."""
        self.close_windows("#edit_colors_dialog")
        def handle_selected_color(color: str) -> None:
            if as_foreground:
                self.selected_fg_color = color
            else:
                self.selected_bg_color = color
            if color_palette_index is not None:
                palette[color_palette_index] = color
                # TODO: Update the palette in a reactive way.
                # I'll need to move the palette state to the app.
                self.query_one(ColorsBox).update_palette()
            window.close()
        window = EditColorsDialogWindow(
            id="edit_colors_dialog",
            handle_selected_color=handle_selected_color,
            selected_color=self.selected_bg_color,
            title=_("Edit Colors"),
        )
        self.mount(window)

    def read_palette(self, file_content: str) -> list[str]:
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

        return colors

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
        global palette
        palette[:len(new_colors)] = new_colors
        palette[len(new_colors):] = [new_colors[0]] * (len(palette) - len(new_colors))
        self.query_one(ColorsBox).update_palette()

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
            for color_str in palette:
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
Columns: {len(palette) // 2}
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
    @work(exclusive=True)
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

            # logo_icon = "🌈🪟"
            # logo_icon = "🏳️‍🌈🪟"  # this would be closer, but I can't do the rainbow flag in the terminal, it uses ZWJ
            # logo_icon = "[blue on red]▀[/][green on yellow]▀[/]" # this gives dim colors
            # logo_icon = "[#0000ff on #ff0000]▀[/][#00aa00 on #ffff00]▀[/]" # good
            # logo_icon = "[#000000][b]≈[/][/][#0000ff on #ff0000]▀[/][#00aa00 on #ffff00]▀[/]" # trying to add the trailing flag effect
            logo_icon = "[#000000]⣿[/][#0000ff on #ff0000]▀[/][#00aa00 on #ffff00]▀[/]" # ah, that's brilliant! that worked way better than I expected

            title = logo_icon + " " + _("Paint")
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
            with open(os.path.join(os.path.dirname(__file__), "stretch_skew_icons.ans"), encoding="utf-8") as f:
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
        # The icon is a document with a yellow question mark.
        # I can almost represent that with emoji, but this causes issues
        # where the emoji and the first letter of the title
        # can disappear depending on the x position of the window.
        # icon = "📄❓"
        # This icon can disappear too, but it doesn't seem
        # to cause the title to get cut off.
        # icon = "📄"
        # Actually, I can make a yellow question mark!
        # Just don't use emoji for it.
        icon = "📄[#ffff00]?[/]"
        title = icon + " " + title
        def handle_button(button: Button) -> None:
            window.close()
        window = DialogWindow(
            id="help_dialog",
            title=title,
            handle_button=handle_button,
            allow_maximize=True,
            allow_minimize=True,
        )
        help_text = parser.format_help()
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
        if not inspect_layout:
            return
        # importing the inspector adds instrumentation which can slow down startup
        from .inspector import Inspector
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
        if not inspect_layout:
            return
        # importing the inspector adds instrumentation which can slow down startup
        from .inspector import Inspector
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
        self.cancel_preview()

        self.get_widget_by_id("status_coords", Static).update(f"{event.x},{event.y}")

        if self.selected_tool in [Tool.brush, Tool.pencil, Tool.eraser, Tool.curve, Tool.polygon]:
            if self.selected_tool == Tool.curve:
                self.make_preview(self.draw_current_curve)
            elif self.selected_tool == Tool.polygon:
                # polyline until finished
                self.make_preview(self.draw_current_polyline, show_dimensions_in_status_bar=True)
            else:
                self.make_preview(lambda: self.stamp_brush(event.x, event.y))
        elif self.selected_tool == Tool.magnifier:
            prospective_magnification = self.get_prospective_magnification()

            if prospective_magnification < self.magnification:
                return  # hide if clicking would zoom out

            # prospective viewport size in document coords
            w = self.editing_area.size.width // prospective_magnification
            h = self.editing_area.size.height // prospective_magnification

            rect_x1 = (event.x - w // 2)
            rect_y1 = (event.y - h // 2)

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
            double_clicked = (
                time_since_last_click < double_click_threshold_seconds and
                abs(self.mouse_at_start.x - event.x) <= double_click_threshold_cells and
                abs(self.mouse_at_start.y - event.y) <= double_click_threshold_cells
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
        """Called when a tool is selected in the palette."""
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
        if not inspect_layout:
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
if args.ascii_only_icons:
    ascii_only_icons = True
if args.inspect_layout:
    inspect_layout = True

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

if args.recode_samples:
    # Re-encode the sample files to test for changes/inconsistency in encoding.

    async def recode_sample(file_path: str|Path) -> None:
        """Re-encodes a single sample file."""
        print(f"Re-encoding {file_path}")
        with open(file_path, "rb") as f:
            image = AnsiArtDocument.decode_based_on_file_extension(f.read(), str(file_path))
        with open(file_path, "wb") as f:
            f.write(image.encode_based_on_file_extension(str(file_path)))
        print(f"Saved {file_path}")

    async def recode_samples() -> None:
        """Re-encodes all sample files in parallel."""
        samples_folder = os.path.join(os.path.dirname(__file__), "../../samples")
        tasks: list[Coroutine[Any, Any, None]] = []
        for file_path in Path(samples_folder).glob("**/*"):
            # Skip backup files in case some sample file is being edited.
            if file_path.name.endswith("~"):
                continue
            # Skip GIMP Palette files.
            if file_path.name.endswith(".gpl"):
                continue
            # Skip folders.
            if file_path.is_dir():
                continue
            tasks.append(recode_sample(file_path))

        await asyncio.gather(*tasks)

    # have to wait for the app to be initialized
    async def once_running() -> None:
        await recode_samples()
        app.exit()
    app.call_later(once_running)

if args.clear_screen:
    os.system("cls||clear")

app.call_later(app.start_backup_interval)

def main() -> None:
    """Entry point for the textual-paint CLI."""
    app.run()

if __name__ == "__main__":
    main()
