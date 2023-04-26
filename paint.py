#!/usr/bin/env python3
import os
import re
import sys
import psutil
import argparse
import asyncio
from enum import Enum
from random import randint, random
from typing import Any, List, Optional, Callable, Iterator, Tuple
from watchdog.events import PatternMatchingEventHandler, FileSystemEvent, EVENT_TYPE_CLOSED, EVENT_TYPE_OPENED
from watchdog.observers import Observer
import stransi
from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.message import Message
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.geometry import Offset, Region, Size
from textual.css._style_properties import BorderDefinition
from textual.reactive import var, reactive
from textual.strip import Strip
from textual.dom import DOMNode
from textual.widget import Widget
from textual.widgets import Button, Static, Input, Tree, Header
from textual.widgets._directory_tree import DirEntry
from textual.binding import Binding
from textual.color import Color
from menus import MenuBar, Menu, MenuItem, Separator
from windows import Window, DialogWindow, CharacterSelectorDialogWindow, MessageBox, get_warning_icon
from edit_colors import EditColorsDialogWindow
from localization.i18n import get as _, load_language, remove_hotkey
from enhanced_directory_tree import EnhancedDirectoryTree

observer = None

def restart_program():
    """Restarts the current program, after file objects and descriptors cleanup"""

    try:
        app.exit()
        # It's meant to eventually call this, but we need it immediately (unless we delay with asyncio perhaps)
        # Otherwise the terminal will be left in a state where you can't (visibly) type anything
        # if you exit the app after reloading, since the new process will pick up the old terminal state.
        app._driver.stop_application_mode() # type: ignore
    except Exception as e:
        print("Error stopping application mode. The command line may not work as expected. The `reset` command should restore it on Linux.", e)

    try:
        try:
            observer.stop()
            observer.join(timeout=1)
            if observer.is_alive:
                print("Timed out waiting for file change observer thread to stop.")
        except RuntimeError as e:
            # Ignore "cannot join current thread" error
            # join() might be redundant, but I'm keeping it just in case something with threading changes in the future
            if str(e) != "cannot join current thread":
                raise
    except Exception as e:
        print("Error stopping file change observer:", e)

    try:
        p = psutil.Process(os.getpid())
        for handler in p.open_files() + p.connections():
            try:
                os.close(handler.fd)
            except Exception as e:
                print(f"Error closing file descriptor ({handler.fd}):", e)
    except Exception as e:
        print("Error closing file descriptors:", e)

    # python = sys.executable
    # os.execl(python, python, *sys.argv)
    os.execl(sys.executable, *sys.orig_argv)

class RestartHandler(PatternMatchingEventHandler):
    """A handler for file changes"""
    def on_any_event(self, event: FileSystemEvent):
        if event.event_type in (EVENT_TYPE_CLOSED, EVENT_TYPE_OPENED):
            # These seem like they'd just cause trouble... they're not changes, are they?
            return
        print("Reloading due to FS change:", event.event_type, event.src_path)
        app.screen.styles.background = "red"
        # The unsaved changes prompt seems to need call_from_thread,
        # or else it gets "no running event loop",
        # whereas restart_program() needs to not use it,
        # or else nothing happens.
        # However, when app.action_reload is called from the key binding,
        # it seems to work fine with or without unsaved changes.
        if app.is_document_modified():
            app.call_from_thread(app.action_reload)
        else:
            restart_program()
        app.screen.styles.background = "yellow"

def restart_on_changes():
    """Restarts the current program when a file is changed"""
    global observer
    observer = Observer()
    observer.schedule(RestartHandler(
        # Don't need to restart on changes to .css, since Textual will reload them in --dev mode
        # Could include localization files, but I'm not actively localizing this app at this point.
        # WET: WatchDog doesn't match zero directories for **, so we have to split up any patterns that use it.
        patterns=[
            "**/*.py", "*.py"
        ],
        ignore_patterns=[
            ".history/**/*", ".history/*",
            ".vscode/**/*", ".vscode/*",
            ".git/**/*", ".git/*",
            "node_modules/**/*", "node_modules/*",
            "__pycache__/**/*", "__pycache__/*",
            "venv/**/*", "venv/*",
        ],
        ignore_directories=True,
    ), path='.', recursive=True)
    observer.start()


# These can go away now that args are parsed up top
ascii_only_icons = False
inspect_layout = False

# Command line arguments
# Please keep in sync with the README
parser = argparse.ArgumentParser(description='Paint in the terminal.')
parser.add_argument('--theme', default='light', help='Theme to use, either "light" or "dark"', choices=['light', 'dark'])
parser.add_argument('--language', default='en', help='Language to use', choices=['ar', 'cs', 'da', 'de', 'el', 'en', 'es', 'fi', 'fr', 'he', 'hu', 'it', 'ja', 'ko', 'nl', 'no', 'pl', 'pt', 'pt-br', 'ru', 'sk', 'sl', 'sv', 'tr', 'zh', 'zh-simplified'])
parser.add_argument('--ascii-only-icons', action='store_true', help='Use only ASCII characters for tool icons')
parser.add_argument('--inspect-layout', action='store_true', help='Inspect the layout with middle click, for development')
# This flag is for development, because it's very confusing
# to see the error message from the previous run,
# when a problem is actually solved.
# There are enough ACTUAL "that should have worked!!" moments to deal with.
# I really don't want false ones mixed in. You want to reward your brain for finding good solutions, after all.
parser.add_argument('--clear-screen', action='store_true', help='Clear the screen before starting; useful for development, to avoid seeing fixed errors')
parser.add_argument('--restart-on-changes', action='store_true', help='Restart the app when the source code is changed, for development')
parser.add_argument('filename', nargs='?', default=None, help='File to open')

if __name__ == "<run_path>":
    # Arguments have to be passed like `textual run --dev "paint.py LICENSE.txt"`
    # so we need to look for an argument starting with "paint.py",
    # and parse the rest of the string as arguments.
    args = None
    for arg in sys.argv:
        if arg.startswith("paint.py"):
            args = parser.parse_args(arg[len("paint.py") :].split())
            break
    assert args is not None, "Couldn't find paint.py in command line arguments"
else:
    args = parser.parse_args()

load_language(args.language)

if args.restart_on_changes:
    restart_on_changes()

# Most arguments are handled at the end of the file.

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
        # - Free-Form Select:  ✂️📐🆓🕸✨⚝🫥🇫/🇸◌⁛⁘ ⢼⠮
        # - Select: ⬚▧🔲 ⣏⣹
        # - Eraser/Color Eraser: 🧼🧽🧹🚫👋🗑️▰▱
        # - Fill With Color: 🌊💦💧🌈🎉🎊🪣🫗
        # - Pick Color: 🎨💉💅💧📌📍⤤𝀃🝯🍶
        # - Magnifier: 🔍🔎👀🔬🔭🧐🕵️‍♂️🕵️‍♀️
        # - Pencil: ✏️✎✍️🖎🖊️🖋️✒️🖆📝🖍️
        # - Brush: 🖌️🖌👨‍🎨🧑‍🎨💅
        # - Airbrush: 💨ᖜ╔🧴🥤🫠
        # - Text: 🆎📝📄📃🔤📜AＡ
        # - Line: 📏📉📈⟍𝈏╲⧹\⧵∖
        # - Curve: ↪️🪝🌙〰️◡◠~∼≈∽∿〜〰﹋﹏≈≋～⁓
        # - Rectangle: ▭▬▮▯🟥🟧🟨🟩🟦🟪🟫⬛⬜◼️◻️◾◽▪️▫️
        # - Polygon: ▙𝗟𝙇﹄』⬣⬟🔶🔷🔸🔹🔺🔻△▲
        # - Ellipse: ⬭⭕🔴🟠🟡🟢🔵🟣🟤⚫⚪🫧
        # - Rounded Rectangle: ▢⬜⬛
        if ascii_only_icons:
            return {
                Tool.free_form_select: "<[u]^[/]7", # "*" "<^>" "<[u]^[/]7"
                Tool.select: "::", # "#" "::" ":_:" ":[u]:[/]:" ":[u]'[/]:"
                Tool.eraser: "[u]/[/]7", # "47" "27" "/_/" "[u]/[/]7"
                Tool.fill: "[u i]H[/]?", # "#?" "H?" "[u i]F[/]?"
                Tool.pick_color: "[u i] P[/]", # "[u].[/]" "[u i]\\P[/]"
                Tool.magnifier: ",O", # ",O" "o-" "O-" "o=" "O=" "Q"
                Tool.pencil: "-==", # "c==>" "==-"
                Tool.brush: "E)=", # "[u],h.[/u]" "[u],|.[/u]" "[u]h[/u]"
                Tool.airbrush: "[u i]H[/]`<", # "H`" "H`<" "[u i]H[/]`<" "[u i]6[/]<"
                Tool.text: "A", # "Abc"
                Tool.line: "\\",
                Tool.curve: "~", # "~" "S" "s"
                Tool.rectangle: "[_]", # "[]"
                Tool.polygon: "[b]L[/b]", # "L"
                Tool.ellipse: "O", # "()"
                Tool.rounded_rectangle: "(_)",
            }[self]
        return {
            Tool.free_form_select: "⚝",
            Tool.select: "⬚",
            Tool.eraser: "🧼",
            Tool.fill: "🌊", # "🫗" causes jutting out in Ubuntu terminal, "🪣" causes the opposite in VS Code terminal
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
        
        Not to be confused with tool.name, which is an identifier."""
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
    "rgb(0,0,0)", # Black
    "rgb(128,128,128)", # Dark Gray
    "rgb(128,0,0)", # Dark Red
    "rgb(128,128,0)", # Pea Green
    "rgb(0,128,0)", # Dark Green
    "rgb(0,128,128)", # Slate
    "rgb(0,0,128)", # Dark Blue
    "rgb(128,0,128)", # Lavender
    "rgb(128,128,64)",
    "rgb(0,64,64)",
    "rgb(0,128,255)",
    "rgb(0,64,128)",
    "rgb(64,0,255)",
    "rgb(128,64,0)",

    "rgb(255,255,255)", # White
    "rgb(192,192,192)", # Light Gray
    "rgb(255,0,0)", # Bright Red
    "rgb(255,255,0)", # Yellow
    "rgb(0,255,0)", # Bright Green
    "rgb(0,255,255)", # Cyan
    "rgb(0,0,255)", # Bright Blue
    "rgb(255,0,255)", # Magenta
    "rgb(255,255,128)",
    "rgb(0,255,128)",
    "rgb(128,255,255)",
    "rgb(128,128,255)",
    "rgb(255,0,128)",
    "rgb(255,128,64)",
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
            # TODO: tooltip with tool.get_name()
            button = Button(tool.get_icon(), classes="tool_button")
            button.can_focus = False
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

    def validate_value(self, value: str) -> str:
        """Limit the value to a single character."""
        return value[-1] if value else " "
    
    # This caused a bug where the character would oscillate between multiple values
    # due to the events queuing up.
    # watch_value would send CharSelected, and then on_char_input_char_selected would
    # set the value to an old value, which would cause watch_value to queue up another
    # CharSelected event, and it would cycle through values.
    # (Usually it wasn't a problem because the key events would be processed in time.)
    # async def watch_value(self, value: str) -> None:
    #     """Called when value changes."""
    #     self.post_message(self.CharSelected(value))
    # Instead, we override on_key to send the message.
    async def on_key(self, event: events.Key) -> None:
        """Called when a key is pressed."""
        # await super().on_key(event)
        if event.is_printable and event.character: # redundance for type checker
            self.value = event.character
            self.post_message(self.CharSelected(self.value))

    def validate_cursor_position(self, cursor_position: int) -> int:
        """Force the cursor position to 0 so that it's over the character."""
        return 0
    
    def insert_text_at_cursor(self, text: str) -> None:
        """Override to limit the value to a single character."""
        self.value = text[-1] if text else " "

    def render_line(self, y: int) -> Strip:
        """Overrides rendering to color the character, since Input doesn't seem to support the color style."""
        assert isinstance(self.app, PaintApp)
        # return Strip([Segment(self.value * self.size.width, Style(color=self.app.selected_fg_color, bgcolor=self.app.selected_bg_color))])
        # There's a LineFilter class that can be subclassed to do stuff like this, but I'm not sure why you'd want a class for it.
        # Is it a typechecking thing? Does python not have good interfaces support?
        # Anyways, this code is based on how that works, 
        super_class_strip = super().render_line(y)
        new_segments: list[Segment] = []
        style_mod: Style = Style(color=self.app.selected_fg_color, bgcolor=self.app.selected_bg_color)
        for text, style, _ in super_class_strip._segments:
            assert isinstance(style, Style)
            new_segments.append(Segment(text, style + style_mod, None))
        return Strip(new_segments)

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

    def update_palette(self) -> None: # , palette: list[str]) -> None:
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
        target_region = self.region.intersection(Region(0, 0, document.width, document.height))
        document.copy_region(source=self.contained_image, target_region=target_region, mask=self.mask)


debug_region_updates = False

ansi_escape_pattern = re.compile(r"(\N{ESC}\[[\d;]*[a-zA-Z])")

class AnsiArtDocument:
    """A document that can be rendered as ANSI."""

    def __init__(self, width: int, height: int) -> None:
        """Initialize the document."""
        self.width = width
        self.height = height
        self.ch = [[" " for _ in range(width)] for _ in range(height)]
        self.bg = [["#ffffff" for _ in range(width)] for _ in range(height)]
        self.fg = [["#000000" for _ in range(width)] for _ in range(height)]
        self.selection: Optional[Selection] = None

    def copy_region(self, source: 'AnsiArtDocument', source_region: Region|None = None, target_region: Region|None = None, mask: list[list[bool]]|None = None) -> None:
        """Copy a region from another document into this document."""
        if source_region is None:
            source_region = Region(0, 0, source.width, source.height)
        if target_region is None:
            target_region = Region(0, 0, source_region.width, source_region.height)
        source_offset = source_region.offset
        target_offset = target_region.offset
        random_color: Optional[str] = None # avoid "possibly unbound"
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

    def get_ansi(self) -> str:
        """Get the ANSI representation of the document."""
        # TODO: try using Rich API to generate ANSI, like how the Canvas renders to the screen
        # TODO: generate more efficient ANSI, e.g. don't repeat the same color codes
        def color_to_rgb(color_code: str) -> str:
            """Convert a color code to the RGB values format used for ANSI escape codes."""
            if color_code.startswith('#'):
                # Convert hex code to RGB values
                color_code = color_code.lstrip('#')
                rgb = tuple(int(color_code[i:i+2], 16) for i in (0, 2, 4))
            elif color_code.startswith('rgb(') and color_code.endswith(')'):
                # Convert "rgb(r,g,b)" style to RGB values
                rgb_str = color_code[4:-1]
                rgb = tuple(int(x.strip()) for x in rgb_str.split(','))
            else:
                raise ValueError("Invalid color code")
            return f"{rgb[0]};{rgb[1]};{rgb[2]}"

        ansi = ""
        for y in range(self.height):
            for x in range(self.width):
                if x == 0:
                    ansi += "\033[0m"
                ansi += "\033[48;2;" + color_to_rgb(self.bg[y][x]) + ";38;2;" + color_to_rgb(self.fg[y][x]) + "m" + self.ch[y][x]
            ansi += "\033[0m\r\n"
        return ansi

    def get_html(self) -> str:
        """Get the HTML representation of the document."""
        html = ""
        for y in range(self.height):
            for x in range(self.width):
                html += "<span style='background-color:" + self.bg[y][x] + ";color:" + self.fg[y][x] + "'>" + self.ch[y][x] + "</span>"
            html += "<br>"
        return html
    
    @staticmethod
    def from_ascii(text: str) -> 'AnsiArtDocument':
        """Creates a document from the given ASCII plain text."""
        lines = text.splitlines()
        width = 0
        for line in lines:
            width = max(len(line), width)
        height = len(lines)
        document = AnsiArtDocument(width, height)
        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                document.ch[y][x] = char
        return document
    
    @staticmethod
    def from_ansi(text: str) -> 'AnsiArtDocument':
        """Creates a document from the given ANSI text."""
        # TODO: use Rich API to render ANSI to a virtual screen,
        # and remove dependency on stransi
        ansi = stransi.Ansi(text)

        # Initial document is zero wide to avoid an extraneous character at (0,0),
        # but needs one row to avoid IndexError.
        document = AnsiArtDocument(0, 1)
        # Ultimately, the minimum size is 1x1.
        width = 1
        height = 1

        x = 0
        y = 0
        bg_color = "#000000"
        fg_color = "#ffffff"
        for instruction in ansi.instructions():
            if isinstance(instruction, str):
                # Text
                for char in instruction:
                    if char == '\r':
                        x = 0
                    elif char == '\n':
                        x = 0
                        y += 1
                        height = max(y, height)
                        if len(document.ch) <= y:
                            document.ch.append([])
                            document.bg.append([])
                            document.fg.append([])
                    else:
                        x += 1
                        width = max(x, width)
                        document.ch[y].append(char)
                        document.bg[y].append(bg_color)
                        document.fg[y].append(fg_color)
            elif isinstance(instruction, stransi.SetColor) and instruction.color is not None:
                # Color (I'm not sure why instruction.color would be None, but it's typed as Optional[Color])
                # (maybe just for initial state?)
                if instruction.role == stransi.color.ColorRole.FOREGROUND:
                    rgb = instruction.color.rgb
                    fg_color = "rgb(" + str(int(rgb.red * 255)) + "," + str(int(rgb.green * 255)) + "," + str(int(rgb.blue * 255)) + ")"
                elif instruction.role == stransi.color.ColorRole.BACKGROUND:
                    rgb = instruction.color.rgb
                    bg_color = "rgb(" + str(int(rgb.red * 255)) + "," + str(int(rgb.green * 255)) + "," + str(int(rgb.blue * 255)) + ")"
            elif isinstance(instruction, stransi.SetAttribute):
                # Attribute
                pass
            else:
                raise ValueError("Unknown instruction type")
        document.width = width
        document.height = height
        # Fill in the rest of the lines
        # just using the last color, not sure if that's correct...
        for y in range(document.height):
            for x in range(document.width - len(document.ch[y])):
                document.ch[y].append(' ')
                document.bg[y].append(bg_color)
                document.fg[y].append(fg_color)
        return document
    
    @staticmethod
    def from_text(text: str) -> 'AnsiArtDocument':
        """Creates a document from the given text, detecting if uses ANSI or not."""
        if ansi_escape_pattern.search(text):
            return AnsiArtDocument.from_ansi(text)
        else:
            return AnsiArtDocument.from_ascii(text)

class Action:
    """An action that can be undone efficiently using a region update."""

    def __init__(self, name: str, document: AnsiArtDocument, region: Region|None = None) -> None:
        """Initialize the action using the document state before modification."""
        if region is None:
            region = Region(0, 0, document.width, document.height)
        self.name = name
        self.region = region
        self.update(document)

    def update(self, document: AnsiArtDocument) -> None:
        """Grabs the image data from the current region of the document."""
        if self.region:
            self.sub_image_before = AnsiArtDocument(self.region.width, self.region.height)
            self.sub_image_before.copy_region(document, self.region)

    def undo(self, target_document: AnsiArtDocument) -> None:
        """Undo this action. Note that a canvas refresh is not performed here."""
        target_document.copy_region(self.sub_image_before, target_region=self.region)

def bresenham_walk(x0: int, y0: int, x1: int, y1: int) -> Iterator[Tuple[int, int]]:
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


def polygon_walk(points: List[Offset]) -> Iterator[Tuple[int, int]]:
    """Yields points along the perimeter of a polygon."""
    for i in range(len(points)):
        yield from bresenham_walk(
            points[i][0],
            points[i][1],
            points[(i + 1) % len(points)][0],
            points[(i + 1) % len(points)][1]
        )

def polyline_walk(points: List[Offset]) -> Iterator[Tuple[int, int]]:
    """Yields points along a polyline (unclosed polygon)."""
    for i in range(len(points) - 1):
        yield from bresenham_walk(
            points[i][0],
            points[i][1],
            points[i + 1][0],
            points[i + 1][1]
        )

def is_inside_polygon(x: int, y: int, points: List[Offset]) -> bool:
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
                    if p1y != p2y:
                        x_intersection = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= x_intersection:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

# def polygon_fill(points: List[Offset]) -> Iterator[Tuple[int, int]]:
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
def compute_bezier(t: float, start_x: float, start_y: float, control_1_x: float, control_1_y: float, control_2_x: float, control_2_y: float, end_x: float, end_y: float):
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
def bezier_curve_walk(start_x: float, start_y: float, control_1_x: float, control_1_y: float, control_2_x: float, control_2_y: float, end_x: float, end_y: float):
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

def quadratic_curve_walk(start_x: float, start_y: float, control_x: float, control_y: float, end_x: float, end_y: float):
    """Yields points along a quadratic curve."""
    return bezier_curve_walk(start_x, start_y, control_x, control_y, control_x, control_y, end_x, end_y)

def midpoint_ellipse(xc: int, yc: int, rx: int, ry: int) -> Iterator[Tuple[int, int]]:
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
        return
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
            self.mouse_down_event = mouse_down_event
            super().__init__()
    
    class ToolUpdate(Message):
        """Message when dragging on the canvas."""

        def __init__(self, mouse_move_event: events.MouseMove) -> None:
            self.mouse_move_event = mouse_move_event
            super().__init__()

    class ToolStop(Message):
        """Message when releasing the mouse."""

        def __init__(self, mouse_up_event: events.MouseUp) -> None:
            self.mouse_up_event = mouse_up_event
            super().__init__()

    class ToolPreviewUpdate(Message):
        """Message when moving the mouse while the mouse is up."""

        def __init__(self, mouse_move_event: events.MouseMove) -> None:
            self.mouse_move_event = mouse_move_event
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
        Start drawing, or if both mouse buttons are pressed, cancel the current action."""
        self.fix_mouse_event(event) # not needed, pointer isn't captured yet.
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
        offset = offset - self.region.offset #+ Offset(int(self.parent.scroll_x), int(self.parent.scroll_y))
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
            self.post_message(self.ToolPreviewUpdate(event))

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Called when a mouse button is released. Stop the current tool."""
        self.fix_mouse_event(event)
        event.x //= self.magnification
        event.y //= self.magnification

        self.pointer_active = False
        self.capture_mouse(False)
        self.post_message(self.ToolStop(event))

    def on_leave(self, event: events.Leave) -> None:
        """Called when the mouse leaves the canvas. Stop preview if applicable."""
        if not self.pointer_active:
            self.post_message(self.ToolPreviewStop())

    def get_content_width(self, container: Size, viewport: Size) -> int:
        """Defines the intrinsic width of the widget."""
        return self.image.width * self.magnification

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        """Defines the intrinsic height of the widget."""
        return self.image.height * self.magnification

    def render_line(self, y: int) -> Strip:
        """Render a line of the widget. y is relative to the top of the widget."""
        assert self.image is not None
        # self.size.width/height already is multiplied by self.magnification.
        if y >= self.size.height:
            return Strip.blank(self.size.width)
        segments: List[Segment] = []
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
            style = Style.parse(fg+" on "+bg)
            assert style.color is not None
            assert style.bgcolor is not None
            # def offset_to_text_index(offset) -> int:
            #     # return offset.y * sel.region.width + offset.x
            #     # return offset.y * self.image.width + offset.x
            assert isinstance(self.app, PaintApp)
            if (
                (self.magnifier_preview_region and magnifier_preview_region.contains(x, y) and (not inner_magnifier_preview_region.contains(x, y))) or
                (self.select_preview_region and select_preview_region.contains(x, y) and (not inner_select_preview_region.contains(x, y))) or
                (sel and (not sel.textbox_mode) and (self.app.selection_drag_offset is None) and selection_region.contains(x, y) and (not inner_selection_region.contains(x, y))) or
                (sel and sel.textbox_mode and (
                    # offset_to_text_index(sel.text_selection_start) <=
                    # offset_to_text_index(Offset(x, y))
                    # < offset_to_text_index(sel.text_selection_end)
                    # sel.text_selection_start.x <= cell_x - sel.region.x < sel.text_selection_end.x and
                    # sel.text_selection_start.y <= cell_y - sel.region.y < sel.text_selection_end.y
                    sel.text_selection_start.x == cell_x - sel.region.x and
                    sel.text_selection_start.y == cell_y - sel.region.y
                ))
            ):
                # invert the colors
                style = Style.parse(f"rgb({255 - style.color.triplet.red},{255 - style.color.triplet.green},{255 - style.color.triplet.blue}) on rgb({255 - style.bgcolor.triplet.red},{255 - style.bgcolor.triplet.green},{255 - style.bgcolor.triplet.blue})")
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
    
    def big_ch(self, ch: str, x: int, y: int) -> str:
        """Return a character part of a meta-glyph."""
        match ch:
            case " ":
                return " "
            case "█":
                return "█"
            case "▄":
                return "█" if y >= self.magnification // 2 else " "
            case "▀":
                return "█" if y < self.magnification // 2 else " "
            case "▌":
                return "█" if x < self.magnification // 2 else " "
            case "▐":
                return "█" if x >= self.magnification // 2 else " "
            case _: pass
        # Fall back to showing the character for a single cell.
        # if x == 0 and y == 0:
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
        # It's also bound to Ctrl+C by default, so for now I'll rebind it,
        # but eventually Ctrl+C will become Edit > Copy.
        Binding("ctrl+q", "exit", _("Quit")),
        Binding("ctrl+s", "save", _("Save")),
        Binding("ctrl+shift+s", "save_as", _("Save As")),
        Binding("ctrl+p", "print", _("Print")),
        Binding("ctrl+o", "open", _("Open")),
        Binding("ctrl+n", "new", _("New")),
        Binding("ctrl+shift+n", "clear_image", _("Clear Image")),
        Binding("ctrl+t", "toggle_tools_box", _("Toggle Tools Box")),
        Binding("ctrl+w", "toggle_colors_box", _("Toggle Colors Box")),
        Binding("ctrl+z", "undo", _("Undo")),
        # Ctrl+Shift+<key> doesn't seem to work on Ubuntu or VS Code terminal,
        # it ignores the Shift.
        Binding("ctrl+shift+z,shift+ctrl+z,ctrl+y,f4", "redo", _("Repeat")),
        Binding("ctrl+x", "cut", _("Cut")),
        Binding("ctrl+c", "copy", _("Copy")), # Quit, for now
        Binding("ctrl+v", "paste", _("Paste")),
        Binding("ctrl+g", "toggle_grid", _("Show Grid")),
        Binding("ctrl+f", "view_bitmap", _("View Bitmap")),
        Binding("ctrl+r", "flip_rotate", _("Flip/Rotate")),
        Binding("ctrl+w", "stretch_skew", _("Stretch/Skew")),
        Binding("ctrl+i", "invert_colors", _("Invert Colors")),
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
        Binding("f2", "reload", _("Reload")),
        # 
        Binding("f3", "custom_zoom", _("Custom Zoom"))
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
    filename = var(None)
    """The path to the file being edited. TODO: rename to indicate it's a path."""

    directory_tree_selected_path: str|None = None
    """Last highlighted item in Open/Save As dialogs"""
    expanding_directory_tree = False
    """Flag to prevent setting the filename input when initially expanding the directory tree"""

    image = var(AnsiArtDocument.from_text("Not Loaded"))
    """The document being edited. Contains the selection, if any."""
    image_initialized = False
    """Whether the image is ready. This flag exists to avoid type checking woes if I were to allow image to be None."""
    
    magnification = var(1)
    """Current magnification level."""
    return_to_magnification = var(4)
    """Saved zoomed-in magnification level."""

    undos: List[Action] = []
    """Past actions that can be undone"""
    redos: List[Action] = []
    """Future actions that can be redone"""
    preview_action: Optional[Action] = None
    """A temporary undo state for tool previews"""
    saved_undo_count = 0
    """Used to determine if the document has been modified since the last save, in is_document_modified()"""

    mouse_gesture_cancelled = False
    """For Undo/Redo, to interrupt the current action"""
    mouse_at_start: Offset = Offset(0, 0)
    """Mouse position at mouse down.
    Used for shape tools that draw between the mouse down and up points (Line, Rectangle, Ellipse, Rounded Rectangle),
    the Select tool (similarly to Rectangle), and used to detect double-click, for the Polygon tool."""
    mouse_previous: Offset = Offset(0, 0)
    """Previous mouse position, for brush tools (Pencil, Brush, Eraser, Airbrush)"""
    selection_drag_offset: Offset|None = None
    """For Select tool, indicates that the selection is being moved
    and defines the offset of the selection from the mouse"""
    selecting_text: bool = False
    """Used for Text tool"""
    tool_points: List[Offset] = []
    """Used for Curve, Polygon, or Free-Form Select tools"""
    polygon_last_click_time: float = 0
    """Used for Polygon tool to detect double-click"""
    color_eraser_mode: bool = False
    """Used for Eraser/Color Eraser tool, when using the right mouse button"""
    
    background_tasks: set[asyncio.Task[None]] = set()
    """Stores references to Task objects so they don't get garbage collected."""

    TITLE = _("Paint")

    def watch_filename(self, filename: Optional[str]) -> None:
        """Called when filename changes."""
        if filename is None:
            self.sub_title = _("Untitled")
        else:
            self.sub_title = os.path.basename(filename)

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
            if selected_tool == self.query_one("ToolsBox", ToolsBox).tool_by_button[button]:
                button.add_class("selected")
            else:
                button.remove_class("selected")

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
        # TODO: keep the top left corner of the viewport in the same place
        # https://github.com/1j01/jspaint/blob/12a90c6bb9d36f495dc6a07114f9667c82ee5228/src/functions.js#L326-L351
        # This will matter more when large documents don't freeze up the program...

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
        brush_diameter += 2 # safety margin
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
                style = Style.parse(self.image.fg[y][x]+" on "+self.image.bg[y][x])
                selected_fg_style = Style.parse(self.selected_fg_color)
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
            style = Style.parse(self.image.fg[y][x]+" on "+self.image.bg[y][x])
            assert style.color is not None
            assert style.bgcolor is not None
            # Why do I need these extra asserts here and not in the other place I do color inversion,
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
            gen = points
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
        action = Action(self.selected_tool.get_name(), self.image)
        if len(self.redos) > 0:
            self.redos = []
        self.undos.append(action)

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
        self.stop_action_in_progress()
        if len(self.undos) > 0:
            action = self.undos.pop()
            redo_action = Action(_("Undo") + " " + action.name, self.image, action.region)
            action.undo(self.image)
            self.redos.append(redo_action)
            self.canvas.refresh(layout=True)

    def action_redo(self) -> None:
        """Redoes the last undone action."""
        self.stop_action_in_progress()
        if len(self.redos) > 0:
            action = self.redos.pop()
            undo_action = Action(_("Undo") + " " + action.name, self.image, action.region)
            action.undo(self.image)
            self.undos.append(undo_action)
            self.canvas.refresh(layout=True)

    def close_windows(self, selector: str) -> None:
        """Close all windows matching the CSS selector."""
        for window in self.query(selector).nodes:
            assert isinstance(window, Window), f"Expected a Window for query '{selector}', but got {window.css_identifier}"
            window.close()

    def action_save(self) -> None:
        """Start the save action, but don't wait for the Save As dialog to close if it's a new file."""
        task = asyncio.create_task(self.save())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def save(self, from_save_as: bool = False) -> None:
        """Save the image to a file."""
        self.cancel_preview()
        dialog_title = _("Save As") if from_save_as else _("Save")
        if self.filename:
            try:
                ansi = self.image.get_ansi()
                with open(self.filename, "w") as f:
                    f.write(ansi)
                self.saved_undo_count = len(self.undos)
            except PermissionError:
                self.warning_message_box(dialog_title, _("Access denied."), "ok")
            except FileNotFoundError: 
                self.warning_message_box(dialog_title, _("%1 contains an invalid path.", self.filename), "ok")
            except OSError as e:
                self.warning_message_box(dialog_title, _("Failed to save document.") + "\n\n" + repr(e), "ok")
            except Exception as e:
                self.warning_message_box(dialog_title, _("An unexpected error occurred while writing %1.", self.filename) + "\n\n" + repr(e), "ok")
        else:
            await self.save_as()
    
    def action_save_as(self) -> None:
        """Show the save as dialog, without waiting for it to close."""
        # Action must not await the dialog closing,
        # or else you'll never see the dialog in the first place!
        task = asyncio.create_task(self.save_as())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def save_as(self) -> None:
        """Save the image as a new file."""
        self.close_windows("#save_as_dialog, #open_dialog")
        
        saved_future: asyncio.Future[None] = asyncio.Future()

        def handle_button(button: Button) -> None:
            if not button.has_class("save"):
                window.close()
                return
            name = self.query_one("#save_as_dialog .filename_input", Input).value
            if not name:
                return
            if self.directory_tree_selected_path:
                name = os.path.join(self.directory_tree_selected_path, name)
            def on_save_confirmed():
                async def async_on_save_confirmed():
                    self.filename = name
                    await self.save(from_save_as=True)
                    window.close()
                    saved_future.set_result(None)
                # https://textual.textualize.io/blog/2023/02/11/the-heisenbug-lurking-in-your-async-code/
                task = asyncio.create_task(async_on_save_confirmed())
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)
            if os.path.exists(name):
                self.confirm_overwrite(name, on_save_confirmed)
            else:
                on_save_confirmed()

        window = DialogWindow(
            id="save_as_dialog",
            classes="file_dialog_window",
            title=_("Save As"),
            handle_button=handle_button,
        )
        filename: str = os.path.basename(self.filename) if self.filename else _("Untitled")
        window.content.mount(
            EnhancedDirectoryTree(id="save_as_dialog_directory_tree", path="/"),
            Input(classes="filename_input", placeholder=_("Filename"), value=filename),
            Button(_("Save"), classes="save submit", variant="primary"),
            Button(_("Cancel"), classes="cancel"),
        )
        self.mount(window)
        self.expand_directory_tree(window.content.query_one("#save_as_dialog_directory_tree", EnhancedDirectoryTree))
        await saved_future

    def expand_directory_tree(self, tree: EnhancedDirectoryTree) -> None:
        """Expand the directory tree to the target directory, either the folder of the open file or the current working directory."""
        self.expanding_directory_tree = True
        target_dir = (self.filename or os.getcwd()).rstrip(os.path.sep)
        tree.expand_to_path(target_dir)
        # There are currently some timers in expand_to_path.
        # In particular, it waits before selecting the target node,
        # and this flag is for avoiding responding to that.
        def done_expanding():
            self.expanding_directory_tree = False
        self.set_timer(0.1, done_expanding)

    def confirm_overwrite(self, filename: str, callback: Callable[[], None]) -> None:
        """Asks the user if they want to overwrite a file."""
        message = _("%1 already exists.\nDo you want to replace it?", filename)
        def handle_button(button: Button) -> None:
            if not button.has_class("yes"):
                return
            callback()
        self.warning_message_box(_("Save As"), Static(message, markup=False), "yes/no", handle_button)

    def prompt_save_changes(self, filename: str, callback: Callable[[], None]) -> None:
        """Asks the user if they want to save changes to a file."""
        filename = os.path.basename(filename)
        message = _("Save changes to %1?", filename)
        def handle_button(button: Button) -> None:
            if not button.has_class("yes") and not button.has_class("no"):
                return
            async def async_handle_button(button: Button):
                if button.has_class("yes"):
                    await self.save()
                callback()
            # https://textual.textualize.io/blog/2023/02/11/the-heisenbug-lurking-in-your-async-code/
            task = asyncio.create_task(async_handle_button(button))
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

        self.warning_message_box(_("Paint"), Static(message, markup=False), "yes/no/cancel", handle_button)

    def is_document_modified(self) -> bool:
        """Returns whether the document has been modified since the last save."""
        return len(self.undos) != self.saved_undo_count

    def action_exit(self) -> None:
        """Exit the program, prompting to save changes if necessary."""
        if self.is_document_modified():
            self.prompt_save_changes(self.filename or _("Untitled"), self.exit)
        else:
            self.exit()
    
    def action_reload(self) -> None:
        """Reload the program, prompting to save changes if necessary."""
        if self.is_document_modified():
            self.prompt_save_changes(self.filename or _("Untitled"), restart_program)
        else:
            restart_program()

    def warning_message_box(self,
        title: str,
        message_widget: Widget|str,
        button_types: str = "ok",
        callback: Callable[[Button], None]|None = None,
    ) -> None:
        """Show a warning message box with the given title, message, and buttons."""
        self.close_windows("#message_box")
        
        self.bell()

        def handle_button(button: Button) -> None:
            # TODO: this is not different or useful enough from DialogWindow's
            # handle_button to justify
            # It's a difference in name, and an automatic close
            if callback:
                callback(button)
            window.close()
        window = MessageBox(
            id="message_box",
            title=title,
            icon_widget=get_warning_icon(),
            message_widget=message_widget,
            button_types=button_types,
            handle_button=handle_button,
        )
        self.mount(window)

    def action_open(self) -> None:
        """Show dialog to open an image from a file."""

        def handle_button(button: Button) -> None:
            if not button.has_class("open"):
                window.close()
                return
            filename = window.content.query_one("#open_dialog .filename_input", Input).value
            if not filename:
                return
            if self.directory_tree_selected_path:
                filename = os.path.join(self.directory_tree_selected_path, filename)
            try:
                # Note that os.path.
                # samefile can raise FileNotFoundError
                if self.filename and os.path.samefile(filename, self.filename):
                    window.close()
                    return
                with open(filename, "r") as f:
                    content = f.read() # f is out of scope in go_ahead()
                    def go_ahead():
                        try:
                            new_image = AnsiArtDocument.from_text(content)
                        except Exception as e:
                            # "This is not a valid bitmap file, or its format is not currently supported."
                            # string from MS Paint doesn't apply well here,
                            # at least not until we support bitmap files.
                            self.warning_message_box(_("Open"), Static(_("Paint cannot open this file.") + "\n\n" + repr(e)), "ok")
                            return
                        self.action_new(force=True)
                        self.canvas.image = self.image = new_image
                        self.canvas.refresh(layout=True)
                        self.filename = filename
                        window.close()
                    if self.is_document_modified():
                        self.prompt_save_changes(self.filename or _("Untitled"), go_ahead)
                    else:
                        go_ahead()
            except FileNotFoundError:
                self.warning_message_box(_("Open"), Static(_("File not found.") + "\n" + _("Please verify that the correct path and file name are given.")), "ok")
            except IsADirectoryError:
                self.warning_message_box(_("Open"), Static(_("Invalid file.")), "ok")
            except PermissionError:
                self.warning_message_box(_("Open"), Static(_("Access denied.")), "ok")
            except Exception as e:
                self.warning_message_box(_("Open"), Static(_("An unexpected error occurred while reading %1.", filename) + "\n\n" + repr(e)), "ok")

        self.close_windows("#save_as_dialog, #open_dialog")
        window = DialogWindow(
            id="open_dialog",
            classes="file_dialog_window",
            title=_("Open"),
            handle_button=handle_button,
        )
        window.content.mount(
            EnhancedDirectoryTree(id="open_dialog_directory_tree", path="/"),
            Input(classes="filename_input", placeholder=_("Filename")),
            Button(_("Open"), classes="open submit", variant="primary"),
            Button(_("Cancel"), classes="cancel"),
        )
        self.mount(window)
        self.expand_directory_tree(window.content.query_one("#open_dialog_directory_tree", EnhancedDirectoryTree))

    def action_new(self, *, force: bool = False) -> None:
        """Create a new image."""
        if self.is_document_modified() and not force:
            def go_ahead():
                # Cancel doesn't call this callback.
                # Yes or No has been selected.
                # If Yes, a save dialog should already have been shown,
                # or the open file saved.
                # Go ahead and create a new image.
                self.action_new(force=True)
            self.prompt_save_changes(self.filename or _("Untitled"), go_ahead)
            return
        self.image = AnsiArtDocument(80, 24)
        self.canvas.image = self.image
        self.canvas.refresh(layout=True)
        self.filename = None
        self.saved_undo_count = 0
        self.undos = []
        self.redos = []
        self.preview_action = None
        # Following MS Paint's lead and resetting the color (but not the tool.)
        # It probably has to do with color modes.
        self.selected_bg_color = palette[0]
        self.selected_fg_color = palette[len(palette) // 2]
        self.selected_char = " "
    
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

    def action_print_preview(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_page_setup(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_print(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_send(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_set_as_wallpaper_tiled(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_set_as_wallpaper_centered(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_recent_file(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")

    # def use_clipboard(self, text_to_write: str|None = None):
    #     import tkinter # Apparently while this is a built-in module, it's not always available.
    #     tk = tkinter.Tk()
    #     tk.withdraw()
    #     if type(text_to_write) == str: # Set clipboard text.
    #         tk.clipboard_clear()
    #         tk.clipboard_append(text_to_write)
    #     try:
    #         clipboard_text = tk.clipboard_get()
    #     except tkinter.TclError:
    #         clipboard_text = ''
    #     r.update() # Stops a few errors (clipboard text unchanged, command line program unresponsive, window not destroyed).
    #     tk.destroy()
    #     return clipboard_text

    def action_cut(self) -> None:
        """Cut the selection to the clipboard."""
        if self.action_copy():
            self.action_clear_selection()

    def action_copy(self) -> bool:
        """Copy the selection to the clipboard."""
        sel = self.image.selection
        if sel is None:
            return False
        had_contained_image = sel.contained_image is not None
        try:
            if sel.contained_image is None:
                # Copy underlying image.
                # Don't want to make an undo state, unlike when cutting out a selection when you drag it.
                sel.copy_from_document(self.image)
            # TODO: copy selected text in textbox, if any
            import pyperclip
            # if not pyperclip.is_available():
            #     # Why is this so unreliable? Ugh, this function actually checks if implementation functions are loaded.
            #     # It shouldn't be used.
            #     self.warning_message_box(_("Paint"), _("Clipboard is not available."), "ok")
            #     return False
            pyperclip.copy(sel.contained_image.get_ansi())
            # self.use_clipboard(sel.contained_image.get_ansi())
        except Exception as e:
            self.warning_message_box(_("Paint"), _("Failed to copy to the clipboard.") + "\n\n" + repr(e), "ok")
            return False
        finally:
            if not had_contained_image:
                sel.contained_image = None
        return True

    def action_paste(self) -> None:
        """Paste the clipboard as a selection."""
        import pyperclip
        text = pyperclip.paste()
        # text = self.use_clipboard()
        if not text:
            return
        if self.image.selection and self.image.selection.textbox_mode:
            # TODO: paste into textbox
            return
        pasted_image = AnsiArtDocument.from_text(text)
        self.stop_action_in_progress()
        # TODO: paste at top left corner of viewport
        self.image.selection = Selection(Region(0, 0, pasted_image.width, pasted_image.height))
        self.image.selection.contained_image = pasted_image
        self.image.selection.pasted = True # create undo state when finalizing selection
        self.canvas.refresh_scaled_region(self.image.selection.region)
        self.selected_tool = Tool.select
    
    def action_select_all(self) -> None:
        """Select the entire image."""
        self.stop_action_in_progress()
        self.image.selection = Selection(Region(0, 0, self.image.width, self.image.height))
        self.canvas.refresh()
        self.selected_tool = Tool.select
    def action_copy_to(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_paste_from(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_text_toolbar(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
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
                min_zoom = 1
                max_zoom = 16
                try:
                    n = int(window.content.query_one("#zoom_input", Input).value)
                    if n < min_zoom or n > max_zoom:
                        raise ValueError
                    self.magnification = n
                    window.close()
                except ValueError:
                    self.warning_message_box(_("Zoom"), _("Please enter an integer between %1 and %2.", str(min_zoom), str(max_zoom)), "ok")
            else:
                window.close()
        window = DialogWindow(
            id="zoom_dialog",
            title=_("Custom Zoom"),
            handle_button=handle_button,
        )
        window.content.mount(
            Input(id="zoom_input", value=str(self.magnification), placeholder=_("Zoom")),
            # Vertical(
            #     Horizontal(
            #         Static(_("Zoom to")),
            #         Input(id="zoom_input", value=str(self.magnification)),
            #     ),
            #     Horizontal(
            #         Static(_("Current zoom:")),
            #         Static(str(self.magnification)),
            #     ),
            # ),
            Container(
                Button(_("OK"), classes="ok submit", variant="primary"),
                Button(_("Cancel"), classes="cancel"),
                classes="buttons",
            )
        )
        self.mount(window)
    def action_show_grid(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_show_thumbnail(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_view_bitmap(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_flip_rotate(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_stretch_skew(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_invert_colors(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_attributes(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_clear_image(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_draw_opaque(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    
    def action_help_topics(self) -> None:
        """Show the Help Topics dialog."""
        self.close_windows("#help_dialog")
        window = DialogWindow(
            id="help_dialog",
            title=_("Help"), # _("Help Topics"),
            handle_button=lambda button: window.close(),
        )
        help_text = parser.format_usage()
        window.content.mount(Static(help_text,  classes="help_text"))
        window.content.mount(Button(_("OK"), classes="ok submit"))
        self.mount(window)
    
    def action_about_paint(self) -> None:
        """Show the About Paint dialog."""
        self.close_windows("#about_paint_dialog")
        window = DialogWindow(
            id="about_paint_dialog",
            title=_("About Paint"),
            handle_button=lambda button: window.close(),
        )
        window.content.mount(Static("""🎨 [b]Textual Paint[/b]

[i]MS Paint in your terminal.[/i]

[b]Version:[/b] 0.1.0
[b]Author:[/b] [link=https://isaiahodhner.io/]Isaiah Odhner[/link]
[b]License:[/b] [link=https://github.com/1j01/textual-paint/blob/main/LICENSE.txt]MIT[/link]
[b]Source Code:[/b] [link=https://github.com/1j01/textual-paint]github.com/1j01/textual-paint[/link]
"""))
        window.content.mount(Button(_("OK"), classes="ok submit"))
        self.mount(window)

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
                    MenuItem(_("Set As &Wallpaper (Tiled)"), self.action_set_as_wallpaper_tiled, 57677, grayed=True, description=_("Tiles this bitmap as the desktop wallpaper.")),
                    MenuItem(_("Set As Wa&llpaper (Centered)"), self.action_set_as_wallpaper_centered, 57675, grayed=True, description=_("Centers this bitmap as the desktop wallpaper.")),
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
                    MenuItem(_("C&opy To..."), self.action_copy_to, 37663, grayed=True, description=_("Copies the selection to a file.")),
                    MenuItem(_("Paste &From..."), self.action_paste_from, 37664, grayed=True, description=_("Pastes a file into the selection.")),
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
                        MenuItem(_("Show &Grid\tCtrl+G"), self.action_show_grid, 37677, grayed=True, description=_("Shows or hides the grid.")),
                        MenuItem(_("Show T&humbnail"), self.action_show_thumbnail, 37676, grayed=True, description=_("Shows or hides the thumbnail view of the picture.")),
                    ])),
                    MenuItem(_("&View Bitmap\tCtrl+F"), self.action_view_bitmap, 37673, grayed=True, description=_("Displays the entire picture.")),
                ])),
                MenuItem(remove_hotkey(_("&Image")), submenu=Menu([
                    MenuItem(_("&Flip/Rotate...\tCtrl+R"), self.action_flip_rotate, 37680, grayed=True, description=_("Flips or rotates the picture or a selection.")),
                    MenuItem(_("&Stretch/Skew...\tCtrl+W"), self.action_stretch_skew, 37681, grayed=True, description=_("Stretches or skews the picture or a selection.")),
                    MenuItem(_("&Invert Colors\tCtrl+I"), self.action_invert_colors, 37682, grayed=True, description=_("Inverts the colors of the picture or a selection.")),
                    MenuItem(_("&Attributes...\tCtrl+E"), self.action_attributes, 37683, grayed=True, description=_("Changes the attributes of the picture.")),
                    MenuItem(_("&Clear Image\tCtrl+Shft+N"), self.action_clear_image, 37684, grayed=True, description=_("Clears the picture or selection.")),
                    MenuItem(_("&Draw Opaque"), self.action_draw_opaque, 6868, grayed=True, description=_("Makes the current selection either opaque or transparent.")),
                ])),
                MenuItem(remove_hotkey(_("&Colors")), submenu=Menu([
                    MenuItem(_("&Edit Colors..."), self.action_edit_colors, 6869, description=_("Creates a new color.")),
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
        

    def on_canvas_tool_start(self, event: Canvas.ToolStart) -> None:
        """Called when the user starts drawing on the canvas."""
        event.stop()
        self.cancel_preview()

        self.mouse_gesture_cancelled = False

        if self.selected_tool == Tool.pick_color:
            self.pick_color(event.mouse_down_event.x, event.mouse_down_event.y)
            return

        if self.selected_tool == Tool.magnifier:
            self.magnifier_click(event.mouse_down_event.x, event.mouse_down_event.y)
            return

        self.mouse_at_start = Offset(event.mouse_down_event.x, event.mouse_down_event.y)
        self.mouse_previous = self.mouse_at_start
        self.color_eraser_mode = self.selected_tool == Tool.eraser and event.mouse_down_event.button == 3

        if self.selected_tool in [Tool.curve, Tool.polygon]:
            self.tool_points.append(Offset(event.mouse_down_event.x, event.mouse_down_event.y))
            if self.selected_tool == Tool.curve:
                self.make_preview(self.draw_current_curve)
            else:
                self.make_preview(self.draw_current_polyline, show_dimensions_in_status_bar=True) # polyline until finished
            return

        if self.selected_tool == Tool.free_form_select:
            self.tool_points = [Offset(event.mouse_down_event.x, event.mouse_down_event.y)]

        if self.selected_tool in [Tool.select, Tool.free_form_select, Tool.text]:
            sel = self.image.selection
            if sel and sel.region.contains_point(self.mouse_at_start):
                if self.selected_tool == Tool.text:
                    # Place cursor at mouse position
                    sel.text_selection_start = Offset(*self.mouse_at_start) - sel.region.offset
                    sel.text_selection_end = Offset(*self.mouse_at_start) - sel.region.offset
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
                    if event.mouse_down_event.ctrl:
                        sel.copy_to_document(self.image)
                    return
                # Cut out the selected part of the image from the document to use as the selection's image data.
                # TODO: DRY with the below action handling
                self.image_at_start = AnsiArtDocument(self.image.width, self.image.height)
                self.image_at_start.copy_region(self.image)
                action = Action(self.selected_tool.get_name(), self.image)
                if len(self.redos) > 0:
                    self.redos = []
                self.undos.append(action)
                sel.copy_from_document(self.image)
                if not event.mouse_down_event.ctrl:
                    self.erase_region(sel.region, sel.mask)
 
                # TODO: Optimize the region storage. Right now I'm copying the whole image,
                # for the case of selection, because later, when the selection is melded into the canvas,
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
                
                # TODO: DRY with the below action handling
                action.region = affected_region
                action.region = action.region.intersection(Region(0, 0, self.image.width, self.image.height))
                action.update(self.image_at_start)
                self.canvas.refresh_scaled_region(affected_region)
                return
            self.meld_selection()
            return

        self.image_at_start = AnsiArtDocument(self.image.width, self.image.height)
        self.image_at_start.copy_region(self.image)
        if len(self.redos) > 0:
            self.redos = []
        action = Action(self.selected_tool.get_name(), self.image)
        self.undos.append(action)
        
        affected_region = None
        if self.selected_tool == Tool.pencil or self.selected_tool == Tool.brush:
            affected_region = self.stamp_brush(event.mouse_down_event.x, event.mouse_down_event.y)
        elif self.selected_tool == Tool.fill:
            affected_region = flood_fill(self.image, event.mouse_down_event.x, event.mouse_down_event.y, self.selected_char, self.selected_fg_color, self.selected_bg_color)

        if affected_region:
            action.region = affected_region
            action.region = action.region.intersection(Region(0, 0, self.image.width, self.image.height))
            action.update(self.image_at_start)
            self.canvas.refresh_scaled_region(affected_region)

    def cancel_preview(self) -> None:
        """Revert the currently previewed action."""
        if self.preview_action:
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

    def make_preview(self, draw_proc: Callable[[], Region], show_dimensions_in_status_bar: bool = False) -> None:
        """Preview the result of a draw operation, using a temporary action. Optionally preview dimensions in status bar."""
        self.cancel_preview()
        image_before = AnsiArtDocument(self.image.width, self.image.height)
        image_before.copy_region(self.image)
        affected_region = draw_proc()
        if affected_region:
            self.preview_action = Action(self.selected_tool.get_name(), self.image)
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

        self.get_widget_by_id("status_coords", Static).update(f"{event.mouse_move_event.x},{event.mouse_move_event.y}")

        if self.selected_tool in [Tool.brush, Tool.pencil, Tool.eraser, Tool.curve, Tool.polygon]:
            if self.selected_tool == Tool.curve:
                self.make_preview(self.draw_current_curve)
            elif self.selected_tool == Tool.polygon:
                self.make_preview(self.draw_current_polyline, show_dimensions_in_status_bar=True) # polyline until finished
            else:
                self.make_preview(lambda: self.stamp_brush(event.mouse_move_event.x, event.mouse_move_event.y))
        elif self.selected_tool == Tool.magnifier:
            prospective_magnification = self.get_prospective_magnification()

            if prospective_magnification < self.magnification:
                return # hide if clicking would zoom out

            # prospective viewport size in document coords
            w = self.editing_area.size.width // prospective_magnification
            h = self.editing_area.size.height // prospective_magnification

            rect_x1 = (event.mouse_move_event.x - w // 2)
            rect_y1 = (event.mouse_move_event.y - h // 2)

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
            action = Action(self.selected_tool.get_name(), self.image)
            if len(self.redos) > 0:
                self.redos = []
            self.undos.append(action)

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
            action = action # type: ignore
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
            if self.selected_tool in [Tool.line, Tool.rectangle, Tool.ellipse, Tool.rounded_rectangle]: # , Tool.curve
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
                self.get_widget_by_id("status_dimensions", Static).update(f"{event.mouse_move_event.x - self.mouse_at_start.x}x{event.mouse_move_event.y - self.mouse_at_start.y}")
            else:
                self.get_widget_by_id("status_coords", Static).update(f"{event.mouse_move_event.x},{event.mouse_move_event.y}")

        if self.selected_tool == Tool.pick_color:
            self.pick_color(event.mouse_move_event.x, event.mouse_move_event.y)
            return

        if self.selected_tool in [Tool.fill, Tool.magnifier]:
            return
        
        if self.selected_tool in [Tool.select, Tool.free_form_select, Tool.text]:
            sel = self.image.selection
            if self.selecting_text:
                assert sel is not None, "selecting_text should only be set if there's a selection"
                sel.text_selection_end = Offset(event.mouse_move_event.x, event.mouse_move_event.y) - sel.region.offset
                self.canvas.refresh_scaled_region(sel.region)
            elif self.selection_drag_offset is not None:
                assert sel is not None, "selection_drag_offset should only be set if there's a selection"
                offset = (
                    self.selection_drag_offset.x + event.mouse_move_event.x,
                    self.selection_drag_offset.y + event.mouse_move_event.y,
                )
                # Handles constraints and canvas refresh.
                self.move_selection_absolute(*offset)
            elif self.selected_tool == Tool.free_form_select:
                self.tool_points.append(Offset(event.mouse_move_event.x, event.mouse_move_event.y))
                self.make_preview(self.draw_current_free_form_select_polyline, show_dimensions_in_status_bar=True)
            else:
                self.canvas.select_preview_region = self.get_select_region(self.mouse_at_start, event.mouse_move_event.offset)
                self.canvas.refresh_scaled_region(self.canvas.select_preview_region)
                self.get_widget_by_id("status_dimensions", Static).update(
                    f"{self.canvas.select_preview_region.width}x{self.canvas.select_preview_region.height}"
                )
            return

        if self.selected_tool in [Tool.curve, Tool.polygon]:
            if len(self.tool_points) < 2:
                self.tool_points.append(Offset(event.mouse_move_event.x, event.mouse_move_event.y))
            self.tool_points[-1] = Offset(event.mouse_move_event.x, event.mouse_move_event.y)

            if self.selected_tool == Tool.curve:
                self.make_preview(self.draw_current_curve)
            elif self.selected_tool == Tool.polygon:
                self.make_preview(self.draw_current_polyline, show_dimensions_in_status_bar=True) # polyline until finished
            return

        if len(self.undos) == 0:
            # Code below wants to update the last action.
            # However, if you you undo while drawing,
            # there may be no last action.
            # FIXME: Ideally we'd stop getting events in this case.
            # This might be buggy if there were multiple undos.
            # It might replace the action instead of doing nothing.
            return

        mm = event.mouse_move_event
        action = self.undos[-1]
        affected_region = None

        replace_action = self.selected_tool in [Tool.ellipse, Tool.rectangle, Tool.line, Tool.rounded_rectangle]
        old_action: Optional[Action] = None # avoid "possibly unbound"
        if replace_action:
            old_action = self.undos.pop()
            old_action.undo(self.image)
            action = Action(self.selected_tool.get_name(), self.image, affected_region)
            self.undos.append(action)
        
        if self.selected_tool in [Tool.pencil, Tool.brush, Tool.eraser, Tool.airbrush]:
            for x, y in bresenham_walk(self.mouse_previous.x, self.mouse_previous.y, mm.x, mm.y):
                affected_region = self.stamp_brush(x, y, affected_region)
        elif self.selected_tool == Tool.line:
            for x, y in bresenham_walk(self.mouse_at_start.x, self.mouse_at_start.y, mm.x, mm.y):
                affected_region = self.stamp_brush(x, y, affected_region)
        elif self.selected_tool == Tool.rectangle:
            for x in range(min(self.mouse_at_start.x, mm.x), max(self.mouse_at_start.x, mm.x) + 1):
                for y in range(min(self.mouse_at_start.y, mm.y), max(self.mouse_at_start.y, mm.y) + 1):
                    if x in range(min(self.mouse_at_start.x, mm.x) + 1, max(self.mouse_at_start.x, mm.x)) and y in range(min(self.mouse_at_start.y, mm.y) + 1, max(self.mouse_at_start.y, mm.y)):
                        continue
                    affected_region = self.stamp_brush(x, y, affected_region)
        elif self.selected_tool == Tool.rounded_rectangle:
            arc_radius = min(2, abs(self.mouse_at_start.x - mm.x) // 2, abs(self.mouse_at_start.y - mm.y) // 2)
            min_x = min(self.mouse_at_start.x, mm.x)
            max_x = max(self.mouse_at_start.x, mm.x)
            min_y = min(self.mouse_at_start.y, mm.y)
            max_y = max(self.mouse_at_start.y, mm.y)
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
            center_x = (self.mouse_at_start.x + mm.x) // 2
            center_y = (self.mouse_at_start.y + mm.y) // 2
            radius_x = abs(self.mouse_at_start.x - mm.x) // 2
            radius_y = abs(self.mouse_at_start.y - mm.y) // 2
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
                affected_region = affected_region.union(old_action.region)
            self.canvas.refresh_scaled_region(affected_region)
        
        self.mouse_previous = mm.offset

    def on_canvas_tool_stop(self, event: Canvas.ToolStop) -> None:
        """Called when releasing the mouse button after drawing/dragging on the canvas."""
        # Clear the selection preview in case the mouse has moved.
        # (I don't know of any guarantee that it won't.)
        self.cancel_preview()

        self.get_widget_by_id("status_dimensions", Static).update("")

        self.color_eraser_mode = False # reset for preview

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
        if self.selected_tool in [Tool.select, Tool.free_form_select, Tool.text] and self.mouse_at_start:
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
                select_region = self.get_select_region(self.mouse_at_start, event.mouse_up_event.offset)
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
                abs(self.tool_points[0].x - event.mouse_up_event.x) <= close_gap_threshold_cells and
                abs(self.tool_points[0].y - event.mouse_up_event.y) <= close_gap_threshold_cells
            )
            double_clicked = (
                time_since_last_click < double_click_threshold_seconds and
                abs(self.mouse_at_start.x - event.mouse_up_event.x) <= double_click_threshold_cells and
                abs(self.mouse_at_start.y - event.mouse_up_event.y) <= double_click_threshold_cells
            )
            if enough_points and (closed_gap or double_clicked):
                self.finalize_polygon_or_curve()
            else:
                # Most likely just drawing the preview we just cancelled.
                self.make_preview(self.draw_current_polyline, show_dimensions_in_status_bar=True) # polyline until finished

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
        if self.image.selection and not self.image.selection.textbox_mode:
            if key == "left":
                self.move_selection_relative(-1, 0)
            elif key == "right":
                self.move_selection_relative(1, 0)
            elif key == "up":
                self.move_selection_relative(0, -1)
            elif key == "down":
                self.move_selection_relative(0, 1)
        if self.image.selection and self.image.selection.textbox_mode:
            assert self.image.selection.contained_image is not None, "Textbox mode should always have contained_image, to edit as text."
            # TODO: delete selected text if any, when typing
            # Note: Don't forget to set self.image.selection.textbox_edited = True
            #       for any new actions that actually affect the text content.
            x, y = self.image.selection.text_selection_start
            if key == "enter":
                x = 0
                y += 1
                if y >= self.image.selection.contained_image.height:
                    y = self.image.selection.contained_image.height - 1
                # self.image.selection.textbox_edited = True
            elif key == "left":
               x = max(0, x - 1)
            elif key == "right":
                x = min(self.image.selection.contained_image.width - 1, x + 1)
            elif key == "up":
                y = max(0, y - 1)
            elif key == "down":
                y = min(self.image.selection.contained_image.height - 1, y + 1)
            elif key == "backspace":
                x = max(0, x - 1)
                self.image.selection.contained_image.ch[y][x] = " "
                self.image.selection.textbox_edited = True
            elif key == "delete":
                self.image.selection.contained_image.ch[y][x] = " "
                x = min(self.image.selection.contained_image.width - 1, x + 1)
                self.image.selection.textbox_edited = True
            elif key == "home":
                x = 0
            elif key == "end":
                x = self.image.selection.contained_image.width - 1
            elif key == "pageup":
                y = 0
            elif key == "pagedown":
                y = self.image.selection.contained_image.height - 1
            elif event.is_printable and event.character: # Redundance for type checker
                # Type a character into the textbox
                self.image.selection.contained_image.ch[y][x] = event.character
                # x = min(self.image.selection.contained_image.width - 1, x + 1)
                x += 1
                if x >= self.image.selection.contained_image.width:
                    x = 0
                    # y = min(self.image.selection.contained_image.height - 1, y + 1)
                    y += 1
                    if y >= self.image.selection.contained_image.height:
                        y = self.image.selection.contained_image.height - 1
                        x = self.image.selection.contained_image.width - 1
                self.image.selection.textbox_edited = True
            self.image.selection.text_selection_start = Offset(x, y)
            self.image.selection.text_selection_end = Offset(x, y)
            self.canvas.refresh_scaled_region(self.image.selection.region)


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
        self.finalize_polygon_or_curve() # must come before setting selected_tool
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

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[DirEntry]) -> None:
        """
        Called when a file/folder is selected in the DirectoryTree.
        
        This message comes from Tree.
        DirectoryTree gives FileSelected but only for files.
        """
        assert event.node.data
        if event.node.data.is_dir:
            self.directory_tree_selected_path = event.node.data.path
        elif event.node.parent:
            assert event.node.parent.data
            self.directory_tree_selected_path = event.node.parent.data.path
            name = os.path.basename(event.node.data.path)
            if not self.expanding_directory_tree:
                self.query_one(".file_dialog_window .filename_input", Input).value = name
        else:
            self.directory_tree_selected_path = None

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
        self.debug_highlight: List[Tuple[Widget, Color, BorderDefinition, Optional[str]]] = []
        # leaf_widget, _ = self.get_widget_at(*event.screen_offset)
        if leaf_widget and leaf_widget is not self.screen:
            for i, widget in enumerate(leaf_widget.ancestors_with_self):
                self.debug_highlight.append((widget, widget.styles.background, widget.styles.border, widget.border_title if hasattr(widget, "border_title") else None))  # type: ignore
                widget.styles.background = Color.from_hsl(i / 10, 1, 0.3)
                if not event.ctrl:
                    widget.styles.border = ("round", Color.from_hsl(i / 10, 1, 0.5))
                    widget.border_title = widget.css_identifier_styled  # type: ignore

# `textual run --dev paint.py` will search for a 
# global variable named `app`, and fallback to
# anything that is an instance of `App`, or
# a subclass of `App`.
# Creating the app and parsing arguments must not be within an if __name__ == "__main__" block,
# since __name__ will be "<run_path>" when running with the textual CLI,
# and it would create a new app instance, and all arguments would be ignored.
app = PaintApp()

if args.ascii_only_icons:
    ascii_only_icons = True
if args.inspect_layout:
    inspect_layout = True
if args.filename:
    # if args.filename == "-" and not sys.stdin.isatty():
    #     app.image = AnsiArtDocument.from_text(sys.stdin.read())
    #     app.filename = "<stdin>"
    # else:
    with open(args.filename, 'r') as my_file:
        app.image = AnsiArtDocument.from_text(my_file.read())
        app.image_initialized = True
        app.filename = os.path.abspath(args.filename)
if args.clear_screen:
    os.system("cls||clear")

app.dark = args.theme == "dark"

if __name__ == "__main__":
    app.run()
