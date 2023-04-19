import os
import re
import sys
import psutil
import argparse
import asyncio
from enum import Enum
from random import randint, random
from typing import List, Optional
from watchdog.events import PatternMatchingEventHandler, FileSystemEvent, EVENT_TYPE_CLOSED, EVENT_TYPE_OPENED
from watchdog.observers import Observer
import stransi
from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.message import Message, MessageTarget
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.geometry import Offset, Region, Size
from textual.css.query import NoMatches
from textual.reactive import var, reactive
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Button, Static, Input, DirectoryTree, Header
from textual.color import Color
from menus import MenuBar, Menu, MenuItem, Separator
from windows import Window, DialogWindow
from localization.i18n import get as _, load_language


observer = None

def restart_program():
    """Restarts the current program, after file objects and descriptors cleanup"""

    try:
        app.exit()
        # It's meant to eventually call this, but we need it immediately (unless we delay with asyncio perhaps)
        # Otherwise the terminal will be left in a state where you can't (visibly) type anything
        # if you exit the app after reloading, since the new process will pick up the old terminal state.
        app._driver.stop_application_mode()
    except Exception as e:
        print("Error stopping application mode. The command line may not work as expected.", e)

    try:
        observer.stop()
        observer.join(timeout=1)
        if observer.is_alive:
            print("Timed out waiting for file change observer thread to stop.")
    except Exception as e:
        print("Error stopping file change observer:", e)

    try:
        p = psutil.Process(os.getpid())
        for handler in p.open_files() + p.connections():
            try:
                os.close(handler.fd)
            except Exception as e:
                print("Error closing file descriptor", handler.fd, e)
    except Exception as e:
        print("Error closing file descriptors", e)

    # python = sys.executable
    # os.execl(python, python, *sys.argv)
    os.execl(sys.executable, *sys.orig_argv)

class RestartHandler(PatternMatchingEventHandler):
    """A handler for file changes"""
    def on_any_event(self, event: FileSystemEvent):
        if event.event_type in (EVENT_TYPE_CLOSED, EVENT_TYPE_OPENED):
            # These seem like they'd just cause trouble... they're not changes, are they?
            return
        restart_program()

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
        """Get the name of this tool."""
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

    def compose(self) -> ComposeResult:
        """Add our buttons."""
        with Container(id="tools_box"):
            # tool buttons
            for tool in Tool:
                yield Button(tool.get_icon(), id="tool_button_" + tool.name)

class ColorsBox(Container):
    """Color palette widget."""

    def compose(self) -> ComposeResult:
        """Add our selected color and color well buttons."""
        with Container(id="colors_box"):
            with Container(id="selected_colors"):
                yield Static(id="selected_color", classes="color_well")
            with Container(id="available_colors"):
                for color in palette:
                    button = Button("", id="color_button_" + color, classes="color_well")
                    button.styles.background = color
                    yield button


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

    def copy_region(self, source, source_region: Region = None, target_region: Region = None):
        if source_region is None:
            source_region = Region(0, 0, source.width, source.height)
        if target_region is None:
            target_region = Region(0, 0, source_region.width, source_region.height)
        source_offset = source_region.offset
        target_offset = target_region.offset
        if debug_region_updates:
            random_color = "rgb(" + str(randint(0, 255)) + "," + str(randint(0, 255)) + "," + str(randint(0, 255)) + ")"
        for y in range(target_region.height):
            for x in range(target_region.width):
                if source_region.contains(x + source_offset.x, y + source_offset.y):
                    self.ch[y + target_offset.y][x + target_offset.x] = source.ch[y + source_offset.y][x + source_offset.x]
                    self.bg[y + target_offset.y][x + target_offset.x] = source.bg[y + source_offset.y][x + source_offset.x]
                    self.fg[y + target_offset.y][x + target_offset.x] = source.fg[y + source_offset.y][x + source_offset.x]
                    if debug_region_updates:
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
        document = AnsiArtDocument(1, 1)
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
            elif isinstance(instruction, stransi.SetColor):
                # Color
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

    def __init__(self, name, document: AnsiArtDocument, region: Region = None) -> None:
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

def bresenham_walk(x0: int, y0: int, x1: int, y1: int) -> None:
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

def midpoint_ellipse(xc: int, yc: int, rx: int, ry: int) -> None:
    """Midpoint ellipse drawing algorithm. Yields points out of order."""
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

def flood_fill(document: AnsiArtDocument, x: int, y: int, fill_ch: str, fill_fg: str, fill_bg: str) -> None:
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
            (original_ch == " " or document.fg[y][x] == original_fg)
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
    stack = [(x, x, y, 1), (x, x, y - 1, -1)]
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

class Canvas(Widget):
    """The image document widget."""

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

    class ToolPreviewUpdate(Message):
        """Message when moving the mouse while the mouse is up."""

        def __init__(self, mouse_move_event: events.MouseMove) -> None:
            self.mouse_move_event = mouse_move_event
            super().__init__()

    class ToolPreviewStop(Message):
        """Message when the mouse leaves the canvas while previewing (not while drawing)."""

        def __init__(self) -> None:
            super().__init__()

    def __init__(self, **kwargs) -> None:
        """Initialize the canvas."""
        super().__init__(**kwargs)
        self.image = None
        self.pointer_active = False

    def on_mouse_down(self, event) -> None:
        self.post_message(self.ToolStart(event))
        self.pointer_active = True
        self.capture_mouse(True)
    
    def on_mouse_move(self, event) -> None:
        # Hack to fix mouse coordinates, not needed for mouse down,
        # or while the mouse is up.
        # This seems like a bug.
        if self.pointer_active:
            event.x += int(self.parent.scroll_x)
            event.y += int(self.parent.scroll_y)

        if self.pointer_active:
            self.post_message(self.ToolUpdate(event))
        else:
            self.post_message(self.ToolPreviewUpdate(event))

    def on_mouse_up(self, event) -> None:
        self.pointer_active = False
        self.capture_mouse(False)

    def on_leave(self, event) -> None:
        if not self.pointer_active:
            self.post_message(self.ToolPreviewStop())

    def get_content_width(self, container: Size, viewport: Size) -> int:
        return self.image.width

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return self.image.height

    def render_line(self, y: int) -> Strip:
        """Render a line of the widget. y is relative to the top of the widget."""
        if y >= self.image.height:
            return Strip.blank(self.size.width)
        segments = []
        for x in range(self.image.width):
            bg = self.image.bg[y][x]
            fg = self.image.fg[y][x]
            ch = self.image.ch[y][x]
            segments.append(Segment(ch, Style.parse(fg+" on "+bg)))
        return Strip(segments, self.size.width)


class PaintApp(App):
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
        ("ctrl+q", "exit", _("Quit")),
        ("meta+q", "exit", _("Quit")),
        ("ctrl+c", "exit", _("Quit")),
        ("ctrl+s", "save", _("Save")),
        ("ctrl+shift+s", "save_as", _("Save As")),
        ("ctrl+o", "open", _("Open")),
        ("ctrl+n", "new", _("New")),
        # ("ctrl+shift+n", "clear_image", _("Clear Image")),
        ("ctrl+t", "toggle_tools_box", _("Toggle Tools Box")),
        ("ctrl+w", "toggle_colors_box", _("Toggle Colors Box")),
        ("ctrl+z", "undo", _("Undo")),
        # Ctrl+Shift+Z doesn't seem to work on Ubuntu or VS Code terminal
        ("ctrl+shift+z", "redo", _("Repeat")),
        ("shift+ctrl+z", "redo", _("Repeat")),
        ("ctrl+y", "redo", _("Repeat")),
        ("f4", "redo", _("Repeat")),
        # action_toggle_dark is built in to App
        ("ctrl+d", "toggle_dark", _("Toggle Dark Mode")),
        # dev helper
        # f5 would be more traditional, but I need something not bound to anything
        # in the context of the terminal in VS Code, and not used by this app, like Ctrl+R, and detectable in the terminal.
        ("f2", "reload", _("Reload")),
    ]

    show_tools_box = var(True)
    show_colors_box = var(True)
    selected_tool = var(Tool.pencil)
    selected_color = var(palette[0])
    selected_char = var(" ")
    filename = var(None)
    image = var(None)

    undos: List[Action] = []
    redos: List[Action] = []
    # temporary undo state for brush previews
    preview_action: Optional[Action] = None
    # file modification tracking
    saved_undo_count = 0

    NAME_MAP = {
        # key to button id
    }

    TITLE = _("Paint")

    def watch_filename(self, filename: Optional[str]) -> None:
        """Called when filename changes."""
        if filename is None:
            self.sub_title = _("Untitled")
        else:
            self.sub_title = os.path.basename(filename)

    def watch_show_tools_box(self, show_tools_box: bool) -> None:
        """Called when show_tools_box changes."""
        self.query_one("#tools_box").display = show_tools_box
        if self.has_class("show_tools_box"):
            self.remove_class("show_tools_box")
        else:
            self.add_class("show_tools_box")
    
    def watch_show_colors_box(self, show_colors_box: bool) -> None:
        """Called when show_colors_box changes."""
        self.query_one("#colors_box").display = show_colors_box
        if self.has_class("show_colors_box"):
            self.remove_class("show_colors_box")
        else:
            self.add_class("show_colors_box")

    def watch_selected_tool(self, old_selected_tool: Tool, selected_tool: Tool) -> None:
        """Called when selected_tool changes."""
        self.query_one("#tool_button_" + old_selected_tool.name).remove_class("selected")
        self.query_one("#tool_button_" + selected_tool.name).add_class("selected")

    def watch_selected_color(self, old_selected_color: str, selected_color: str) -> None:
        """Called when selected_color changes."""
        self.query_one("#selected_color").styles.background = selected_color

    def stamp_brush(self, x: int, y: int, affected_region_base: Region = None) -> Region:
        brush_diameter = 1
        if self.selected_tool == Tool.brush or self.selected_tool == Tool.airbrush or self.selected_tool == Tool.eraser:
            brush_diameter = 3
        if brush_diameter == 1:
            self.stamp_char(x, y)
        else:
            # plot points within a circle
            for i in range(brush_diameter):
                for j in range(brush_diameter):
                    if (i - brush_diameter // 2) ** 2 + (j - brush_diameter // 2) ** 2 <= (brush_diameter // 2) ** 2:
                        self.stamp_char(x + i - brush_diameter // 2, y + j - brush_diameter // 2)
        # expand the affected region to include the brush
        brush_diameter += 2 # safety margin
        affected_region = Region(x - brush_diameter // 2, y - brush_diameter // 2, brush_diameter, brush_diameter)
        if affected_region_base:
            return affected_region_base.union(affected_region)
        else:
            return affected_region
    
    def stamp_char(self, x: int, y: int) -> None:
        char = self.selected_char
        color = self.selected_color
        if self.selected_tool == Tool.eraser:
            char = " "
            color = "#ffffff"
        if self.selected_tool == Tool.airbrush:
            if random() < 0.7:
                return
        if x < self.image.width and y < self.image.height and x >= 0 and y >= 0:
            self.image.ch[y][x] = char
            self.image.bg[y][x] = color
    
    def action_undo(self) -> None:
        if len(self.undos) > 0:
            self.cancel_preview()
            action = self.undos.pop()
            redo_action = Action(_("Undo") + " " + action.name, self.image, action.region)
            action.undo(self.image)
            self.redos.append(redo_action)
            self.canvas.refresh()

    def action_redo(self) -> None:
        if len(self.redos) > 0:
            self.cancel_preview()
            action = self.redos.pop()
            undo_action = Action(_("Undo") + " " + action.name, self.image, action.region)
            action.undo(self.image)
            self.undos.append(undo_action)
            self.canvas.refresh()

    def action_save(self) -> None:
        """Start the save action, but don't wait for the Save As dialog to close if it's a new file."""
        self._not_garbage1 = asyncio.create_task(self.save())

    async def save(self, from_save_as=False) -> None:
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
                self.warning_message_box(dialog_title, _("%1 contains an invalid path.").replace("%1", self.filename), "ok")
            except OSError as e:
                self.warning_message_box(dialog_title, _("Failed to save document.") + "\n\n" + str(e), "ok")
            except Exception as e:
                self.warning_message_box(dialog_title, _("An unexpected error occurred while writing %1.").replace("%1", self.filename) + "\n\n" + str(e), "ok")
        else:
            await self.save_as()
    
    def action_save_as(self) -> None:
        """Show the save as dialog, without waiting for it to close."""
        # Action must not await the dialog closing,
        # or else you'll never see the dialog in the first place!
        self._not_garbage2 = asyncio.create_task(self.save_as())

    async def save_as(self) -> None:
        """Save the image as a new file."""
        for old_window in self.query("#save_as_dialog, #open_dialog").nodes:
            old_window.close()
        
        saved_future = asyncio.Future()

        def handle_button(button):
            if not button.has_class("save"):
                window.close()
                return
            name = self.query_one("#save_as_dialog_filename_input", Input).value
            if name:
                if self.directory_tree_selected_path:
                    name = os.path.join(self.directory_tree_selected_path, name)
                def on_save_confirmed():
                    async def async_on_save_confirmed():
                        self.filename = name
                        await self.save(from_save_as=True)
                        window.close()
                        saved_future.set_result(None)
                    # asyncio.run() cannot be called from a running event loop
                    # asyncio.create_task() result must be saved to a variable to avoid garbage collection.
                    # https://textual.textualize.io/blog/2023/02/11/the-heisenbug-lurking-in-your-async-code/
                    self._not_garbage_to_collect123 = asyncio.create_task(async_on_save_confirmed())
                if os.path.exists(name):
                    self.confirm_overwrite(name, on_save_confirmed)
                else:
                    on_save_confirmed()

        window = DialogWindow(
            classes="dialog",
            id="save_as_dialog",
            title=_("Save As"),
            handle_button=handle_button,
        )
        window.content.mount(
            DirectoryTree(id="save_as_dialog_directory_tree", path="/"),
            Input(id="save_as_dialog_filename_input", placeholder=_("Filename")),
            Button(_("Save"), classes="save submit", variant="primary"),
            Button(_("Cancel"), classes="cancel"),
        )
        self.mount(window)
        self.expand_directory_tree(window.content.query_one("#save_as_dialog_directory_tree"))
        await saved_future

    def expand_directory_tree(self, tree: DirectoryTree) -> None:
        """Expand the directory tree to the target directory, either the folder of the open file or the current working directory."""
        # TODO: os.path.normcase, and maybe os.path.samefile check
        target_dir = (self.filename or os.getcwd()).rstrip(os.path.sep)
        node = tree.root
        def get_node_name(node):
            return os.path.basename(node.data.path.rstrip(os.path.sep))
        for dir_name in target_dir.split(os.path.sep):
            # Find the child node with the right name.
            for child in node.children:
                if get_node_name(child) == dir_name:
                    node = child
                    break
            if get_node_name(node) == dir_name:
                if node.data.is_dir:
                    if not node.is_expanded and not node.data.loaded:
                        # load_directory also calls node.expand()
                        tree.load_directory(node)
                else:
                    # Found a file.
                    break
            else:
                # Directory or file not found.
                break
        # Timer is needed to wait for the new nodes to mount, I think.
        # tree.select_node(node)
        self.set_timer(0.01, lambda: tree.select_node(node))
        # widget.scroll_to_region supports a `top` argument,
        # but tree.scroll_to_node doesn't.
        # A simple workaround is to scroll to the bottom first.
        # tree.scroll_to_line(tree.last_line)
        # tree.scroll_to_node(node)
        # That would work if scroll_to_node and scroll_to_line didn't animate,
        # but the animations conflicts with each other and it ends up in the wrong spot.
        # They don't support widget.scroll_to_region's `animate` argument either.
        # Oh but I can use scroll_visible instead.
        # node.scroll_visible(animate=False, top=True)
        # That is, if node was a widget!
        # Ugh. OK, I'm going to use some internals, and replicate how scroll_to_node works.
        # tree.scroll_to_region(tree._get_label_region(node._line), animate=False, top=True)
        # Timer is needed to wait for the new nodes to mount, I think.
        self.set_timer(0.01, lambda: tree.scroll_to_region(tree._get_label_region(node._line), animate=False, top=True))
    
    def confirm_overwrite(self, filename: str, callback) -> None:
        message = _("%1 already exists.\nDo you want to replace it?").replace("%1", filename)
        def handle_button(button):
            if not button.has_class("yes"):
                return
            callback()
        self.warning_message_box(_("Save As"), Static(message, markup=False), "yes/no", handle_button)

    def prompt_save_changes(self, filename: str, callback) -> None:
        filename = os.path.basename(filename)
        message = "Save changes to " + filename + "?"
        def handle_button(button):
            if not button.has_class("yes") and not button.has_class("no"):
                return
            async def async_handle_button(button):
                if button.has_class("yes"):
                    await self.save()
                callback()
            # asyncio.run() cannot be called from a running event loop
            # asyncio.create_task() result must be saved to a variable to avoid garbage collection.
            # https://textual.textualize.io/blog/2023/02/11/the-heisenbug-lurking-in-your-async-code/
            self._not_garbage_to_collect = asyncio.create_task(async_handle_button(button))
        self.warning_message_box(_("Paint"), Static(message, markup=False), "yes/no/cancel", handle_button)

    def is_document_modified(self) -> bool:
        return len(self.undos) != self.saved_undo_count

    def action_exit(self) -> None:
        if self.is_document_modified():
            self.prompt_save_changes(self.filename or _("Untitled"), self.exit)
        else:
            self.exit()
    
    def action_reload(self) -> None:
        if self.is_document_modified():
            self.prompt_save_changes(self.filename or _("Untitled"), restart_program)
        else:
            restart_program()

    def warning_message_box(self, title: str, message_widget: Widget, button_types: str = "ok", callback = None) -> None:

        if isinstance(message_widget, str):
            message_widget = Static(message_widget, markup=False)

        for old_window in self.query("#message_box").nodes:
            old_window.close()
        
        self.bell()

        def handle_button(button):
            if callback:
                callback(button)
            window.close()

        window = DialogWindow(
            classes="dialog",
            id="message_box",
            title=title,
            handle_button=handle_button,
        )

        if button_types == "ok":
            buttons = [Button(_("OK"), classes="ok submit", variant="primary")]
        elif button_types == "yes/no":
            buttons = [
                Button(_("Yes"), classes="yes submit"), #, variant="primary"),
                Button(_("No"), classes="no"),
            ]
        elif button_types == "yes/no/cancel":
            buttons = [
                Button(_("Yes"), classes="yes submit", variant="primary"),
                Button(_("No"), classes="no"),
                Button(_("Cancel"), classes="cancel"),
            ]
        else:
            raise ValueError("Invalid button_types: " + repr(button_types))
        
        # ASCII line art version:
#         warning_icon = Static("""[#ffff00]
#     _
#    / \\
#   / | \\
#  /  .  \\
# /_______\\
# [/]""", classes="warning_icon")
        # Unicode solid version 1:
#         warning_icon = Static("""[#ffff00 on #000000]
#     _
#    ◢█◣
#   ◢[#000000 on #ffff00] ▼ [/]◣
#  ◢[#000000 on #ffff00]  ●  [/]◣
# ◢███████◣
# [/]""", classes="warning_icon")
        # Unicode line art version (' might be a better than ╰/╯):
#         warning_icon = Static("""[#ffff00]
#     _
#    ╱ ╲
#   ╱ │ ╲
#  ╱  .  ╲
# ╰───────╯
# """, classes="warning_icon")
        # Unicode solid version 2:
#         warning_icon = Static("""[#ffff00 on #000000]
#      🭯
#     🭅[#000000 on #ffff00]🭯[/]🭐
#    🭅[#000000 on #ffff00] ▼ [/]🭐
#   🭅[#000000 on #ffff00]  ●  [/]🭐
#  🭅███████🭐
# [/]""", classes="warning_icon")
        # Unicode solid version 3, now with a border:
        # VS Code's terminal seems unsure of the width of these characters (like it's rendering 2 wide but advancing by 1), and has gaps/seams.
        # Ubuntu's terminal looks better, and the graphics have less gaps, but the overall shape is worse.
        # I guess a lot of this comes down to the font as well.
        warning_icon = Static("""
    [#000000]🭋[#ffff00 on #000000]🭯[/]🭀[/]
   [#000000]🭋[#ffff00 on #000000]🭅█🭐[/]🭀[/]
  [#000000]🭋[#ffff00 on #000000]🭅[#000000 on #ffff00] ▼ [/]🭐[/]🭀[/]
 [#000000]🭋[#ffff00 on #000000]🭅[#000000 on #ffff00]  ●  [/]🭐[/]🭀[/]
[#000000]🭋[#ffff00 on #000000]🭅███████🭐[/]🭀[/]
[#000000]🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃[/]
""", classes="warning_icon")
        window.content.mount(
            Horizontal(
                warning_icon,
                Vertical(
                    message_widget,
                    Horizontal(*buttons, classes="buttons"),
                    classes="main_content"
                )
            )
        )
        self.mount(window)

    def action_open(self) -> None:
        """Show dialog to open an image from a file."""

        def handle_button(button):
            if not button.has_class("open"):
                window.close()
                return
            filename = window.content.query_one("#open_dialog_filename_input").value
            if self.directory_tree_selected_path:
                filename = os.path.join(self.directory_tree_selected_path, filename)
            if filename:
                if self.filename and os.path.samefile(filename, self.filename):
                    window.close()
                    return
                try:
                    with open(filename, "r") as f:
                        content = f.read() # f is out of scope in go_ahead()
                        def go_ahead():
                            try:
                                new_image = AnsiArtDocument.from_ansi(content)
                            except Exception as e:
                                # "This is not a valid bitmap file, or its format is not currently supported."
                                # string from MS Paint doesn't apply well here,
                                # at least not until we support bitmap files.
                                self.warning_message_box(_("Open"), Static(_("Paint cannot open this file.") + "\n\n" + str(e)), "ok")
                                return
                            self.action_new(force=True)
                            self.canvas.image = self.image = new_image
                            self.canvas.refresh()
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
                    self.warning_message_box(_("Open"), Static(_("An unexpected error occurred while reading %1.").replace("%1", filename) + "\n\n" + str(e)), "ok")

        for old_window in self.query("#save_as_dialog, #open_dialog").nodes:
            old_window.close()
        window = DialogWindow(
            classes="dialog",
            id="open_dialog",
            title=_("Open"),
            handle_button=handle_button,
        )
        window.content.mount(
            DirectoryTree(id="open_dialog_directory_tree", path="/"),
            Input(id="open_dialog_filename_input", placeholder=_("Filename")),
            Button(_("Open"), classes="open submit", variant="primary"),
            Button(_("Cancel"), classes="cancel"),
        )
        self.mount(window)
        self.expand_directory_tree(window.content.query_one("#open_dialog_directory_tree"))

    def action_new(self, *, force=False) -> None:
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
        self.canvas.refresh()
        self.filename = None
        self.saved_undo_count = 0
        self.undos = []
        self.redos = []
        self.preview_action = None
        # Following MS Paint's lead and resetting the color (but not the tool.)
        # It probably has to do with color modes.
        self.selected_color = palette[0]
        self.selected_char = " "
    
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
    def action_cut(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_copy(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_paste(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_clear_selection(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_select_all(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_copy_to(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_paste_from(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_toggle_status_bar(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_text_toolbar(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_normal_size(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_large_size(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_custom_zoom(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
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
    def action_edit_colors(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_help_topics(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")
    def action_about_paint(self) -> None:
        self.warning_message_box(_("Paint"), "Not implemented.", "ok")

    def compose(self) -> ComposeResult:
        """Add our widgets."""
        yield Header()
        with Container(id="paint"):
            yield MenuBar([
                MenuItem(_("&File"), submenu=Menu([
                    MenuItem(_("&New\tCtrl+N"), self.action_new, 57600),
                    MenuItem(_("&Open...\tCtrl+O"), self.action_open, 57601),
                    MenuItem(_("&Save\tCtrl+S"), self.action_save, 57603),
                    MenuItem(_("Save &As..."), self.action_save_as, 57604),
                    Separator(),
                    MenuItem(_("Print Pre&view"), self.action_print_preview, 57609),
                    MenuItem(_("Page Se&tup..."), self.action_page_setup, 57605),
                    MenuItem(_("&Print...\tCtrl+P"), self.action_print, 57607),
                    Separator(),
                    MenuItem(_("S&end..."), self.action_send, 37662),
                    Separator(),
                    MenuItem(_("Set As &Wallpaper (Tiled)"), self.action_set_as_wallpaper_tiled, 57677),
                    MenuItem(_("Set As Wa&llpaper (Centered)"), self.action_set_as_wallpaper_centered, 57675),
                    Separator(),
                    MenuItem(_("Recent File"), self.action_recent_file, 57616, grayed=True),
                    Separator(),
                    # MenuItem(_("E&xit\tAlt+F4"), self.action_exit, 57665),
                    MenuItem(_("E&xit\tCtrl+Q"), self.action_exit, 57665),
                ])),
                MenuItem(_("&Edit"), submenu=Menu([
                    MenuItem(_("&Undo\tCtrl+Z"), self.action_undo, 57643),
                    MenuItem(_("&Repeat\tF4"), self.action_redo, 57644),
                    Separator(),
                    MenuItem(_("Cu&t\tCtrl+X"), self.action_cut, 57635),
                    MenuItem(_("&Copy\tCtrl+C"), self.action_copy, 57634),
                    MenuItem(_("&Paste\tCtrl+V"), self.action_paste, 57637),
                    MenuItem(_("C&lear Selection\tDel"), self.action_clear_selection, 57632),
                    MenuItem(_("Select &All\tCtrl+A"), self.action_select_all, 57642),
                    Separator(),
                    MenuItem(_("C&opy To..."), self.action_copy_to, 37663),
                    MenuItem(_("Paste &From..."), self.action_paste_from, 37664),
                ])),
                MenuItem(_("&View"), submenu=Menu([
                    MenuItem(_("&Tool Box\tCtrl+T"), self.action_toggle_tools_box, 59415),
                    MenuItem(_("&Color Box\tCtrl+L"), self.action_toggle_colors_box, 59416),
                    MenuItem(_("&Status Bar"), self.action_toggle_status_bar, 59393),
                    MenuItem(_("T&ext Toolbar"), self.action_text_toolbar, 37678),
                    Separator(),
                    MenuItem(_("&Zoom"), submenu=Menu([
                        MenuItem(_("&Normal Size\tCtrl+PgUp"), self.action_normal_size, 37670),
                        MenuItem(_("&Large Size\tCtrl+PgDn"), self.action_large_size, 37671),
                        MenuItem(_("C&ustom..."), self.action_custom_zoom, 37672),
                        Separator(),
                        MenuItem(_("Show &Grid\tCtrl+G"), self.action_show_grid, 37677),
                        MenuItem(_("Show T&humbnail"), self.action_show_thumbnail, 37676),
                    ])),
                    MenuItem(_("&View Bitmap\tCtrl+F"), self.action_view_bitmap, 37673),
                ])),
                MenuItem(_("&Image"), submenu=Menu([
                    MenuItem(_("&Flip/Rotate...\tCtrl+R"), self.action_flip_rotate, 37680),
                    MenuItem(_("&Stretch/Skew...\tCtrl+W"), self.action_stretch_skew, 37681),
                    MenuItem(_("&Invert Colors\tCtrl+I"), self.action_invert_colors, 37682),
                    MenuItem(_("&Attributes...\tCtrl+E"), self.action_attributes, 37683),
                    MenuItem(_("&Clear Image\tCtrl+Shft+N"), self.action_clear_image, 37684),
                    MenuItem(_("&Draw Opaque"), self.action_draw_opaque, 6868),
                ])),
                MenuItem(_("&Colors"), submenu=Menu([
                    MenuItem(_("&Edit Colors..."), self.action_edit_colors, 6869),
                ])),
                MenuItem(_("&Help"), submenu=Menu([
                    MenuItem(_("&Help Topics"), self.action_help_topics, 57670),
                    Separator(),
                    MenuItem(_("&About Paint"), self.action_about_paint, 57664),
                ])),
            ])
            yield Container(
                ToolsBox(),
                Container(
                    Canvas(id="canvas"),
                    id="editing-area",
                ),
                id="main-horizontal-split",
            )
            yield ColorsBox()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        # Image can be set from the outside, via CLI
        if self.image is None:
            self.image = AnsiArtDocument(80, 24)
        self.canvas = self.query_one("#canvas")
        self.canvas.image = self.image

    def pick_color(self, x: int, y: int) -> None:
        """Select a color from the image."""
        self.selected_color = self.image.bg[y][x]
        self.selected_char = self.image.ch[y][x]

    def on_canvas_tool_start(self, event: Canvas.ToolStart) -> None:
        """Called when the user starts drawing on the canvas."""
        event.stop()
        self.cancel_preview()

        if self.selected_tool == Tool.pick_color:
            self.pick_color(event.mouse_down_event.x, event.mouse_down_event.y)
            return

        if self.selected_tool in [Tool.free_form_select, Tool.select, Tool.magnifier, Tool.text, Tool.curve, Tool.polygon]:
            self.selected_tool = Tool.pencil
            # TODO: support other tools
        self.image_at_start = AnsiArtDocument(self.image.width, self.image.height)
        self.image_at_start.copy_region(self.image)
        self.mouse_at_start = (event.mouse_down_event.x, event.mouse_down_event.y)
        if len(self.redos) > 0:
            self.redos = []
        action = Action(self.selected_tool.get_name(), self.image)
        self.undos.append(action)
        
        affected_region = None
        if self.selected_tool == Tool.pencil or self.selected_tool == Tool.brush:
            affected_region = self.stamp_brush(event.mouse_down_event.x, event.mouse_down_event.y)
        elif self.selected_tool == Tool.fill:
            affected_region = flood_fill(self.image, event.mouse_down_event.x, event.mouse_down_event.y, self.selected_char, "#ffffff", self.selected_color)

        if affected_region:
            action.region = affected_region
            action.region = action.region.intersection(Region(0, 0, self.image.width, self.image.height))
            action.update(self.image_at_start)
            self.canvas.refresh(affected_region)

    def cancel_preview(self) -> None:
        """Revert the currently previewed action."""
        if self.preview_action:
            self.preview_action.undo(self.image)
            self.canvas.refresh(self.preview_action.region)
            self.preview_action = None

    def on_canvas_tool_preview_update(self, event: Canvas.ToolPreviewUpdate) -> None:
        """Called when the user is hovering over the canvas but not drawing yet."""
        event.stop()
        self.cancel_preview()

        if self.selected_tool in [Tool.brush, Tool.pencil, Tool.eraser]:
            image_before = AnsiArtDocument(self.image.width, self.image.height)
            image_before.copy_region(self.image)
            affected_region = self.stamp_brush(event.mouse_move_event.x, event.mouse_move_event.y)
            if affected_region:
                self.preview_action = Action(self.selected_tool.get_name(), self.image)
                self.preview_action.region = affected_region.intersection(Region(0, 0, self.image.width, self.image.height))
                self.preview_action.update(image_before)
                self.canvas.refresh(affected_region)

    def on_canvas_tool_preview_stop(self, event: Canvas.ToolPreviewStop) -> None:
        """Called when the user stops hovering over the canvas (while previewing, not drawing)."""
        event.stop()
        self.cancel_preview()

    def on_canvas_tool_update(self, event: Canvas.ToolUpdate) -> None:
        """Called when the user is drawing on the canvas."""
        event.stop()
        self.cancel_preview()

        if self.selected_tool == Tool.pick_color:
            self.pick_color(event.mouse_move_event.x, event.mouse_move_event.y)
            return

        if self.selected_tool in [Tool.fill, Tool.magnifier]:
            return
        
        if len(self.undos) == 0:
            # This can happen if you undo while drawing.
            # Ideally we'd stop getting events in this case.
            # This might be buggy if there were multiple undos.
            # It might replace the action instead of doing nothing.
            return

        mm = event.mouse_move_event
        action = self.undos[-1]
        affected_region = None

        replace_action = self.selected_tool in [Tool.ellipse, Tool.rectangle, Tool.line, Tool.rounded_rectangle]
        if replace_action:
            old_action = self.undos.pop()
            old_action.undo(self.image)
            action = Action(self.selected_tool.get_name(), self.image, affected_region)
            self.undos.append(action)
        
        if self.selected_tool == Tool.pencil or self.selected_tool == Tool.brush or self.selected_tool == Tool.eraser or self.selected_tool == Tool.airbrush:
            for x, y in bresenham_walk(mm.x - mm.delta_x, mm.y - mm.delta_y, mm.x, mm.y):
                affected_region = self.stamp_brush(x, y, affected_region)
        elif self.selected_tool == Tool.line:
            for x, y in bresenham_walk(self.mouse_at_start[0], self.mouse_at_start[1], mm.x, mm.y):
                affected_region = self.stamp_brush(x, y, affected_region)
        elif self.selected_tool == Tool.rectangle:
            for x in range(min(self.mouse_at_start[0], mm.x), max(self.mouse_at_start[0], mm.x) + 1):
                for y in range(min(self.mouse_at_start[1], mm.y), max(self.mouse_at_start[1], mm.y) + 1):
                    if x in range(min(self.mouse_at_start[0], mm.x) + 1, max(self.mouse_at_start[0], mm.x)) and y in range(min(self.mouse_at_start[1], mm.y) + 1, max(self.mouse_at_start[1], mm.y)):
                        continue
                    affected_region = self.stamp_brush(x, y, affected_region)
        elif self.selected_tool == Tool.rounded_rectangle:
            arc_radius = min(2, abs(self.mouse_at_start[0] - mm.x) // 2, abs(self.mouse_at_start[1] - mm.y) // 2)
            min_x = min(self.mouse_at_start[0], mm.x)
            max_x = max(self.mouse_at_start[0], mm.x)
            min_y = min(self.mouse_at_start[1], mm.y)
            max_y = max(self.mouse_at_start[1], mm.y)
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
            center_x = (self.mouse_at_start[0] + mm.x) // 2
            center_y = (self.mouse_at_start[1] + mm.y) // 2
            radius_x = abs(self.mouse_at_start[0] - mm.x) // 2
            radius_y = abs(self.mouse_at_start[1] - mm.y) // 2
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
            self.canvas.refresh(affected_region)

    def on_key(self, event: events.Key) -> None:
        """Called when the user presses a key."""

        def press(button_id: str) -> None:
            try:
                self.query_one(f"#{button_id}", Button).press()
            except NoMatches:
                pass

        key = event.key
        
        button_id = self.NAME_MAP.get(key)
        if button_id is not None:
            press(self.NAME_MAP.get(key, key))

    def action_toggle_tools_box(self) -> None:
        self.show_tools_box = not self.show_tools_box

    def action_toggle_colors_box(self) -> None:
        self.show_colors_box = not self.show_colors_box

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is clicked or activated with the keyboard."""

        button_id = event.button.id
        # button_classes = event.button.classes

        if button_id:
            if button_id.startswith("tool_button_"):
                self.selected_tool = Tool[button_id[len("tool_button_") :]]
            elif button_id.startswith("color_button_"):
                self.selected_color = button_id[len("color_button_") :]

    def on_tree_node_highlighted(self, event: DirectoryTree.FileSelected) -> None:
        """
        Called when a file/folder is selected in the DirectoryTree.
        
        This message comes from Tree.
        DirectoryTree gives FileSelected but only for files.
        """
        if event.node.data.is_dir:
            self.directory_tree_selected_path = event.node.data.path
        elif event.node.parent:
            self.directory_tree_selected_path = event.node.parent.data.path
            name = os.path.basename(event.node.data.path)
            self.query_one("#save_as_dialog_filename_input, #open_dialog_filename_input", Input).value = name
        else:
            self.directory_tree_selected_path = None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Called when the mouse button gets pressed."""
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
        self.debug_highlight = []
        leaf_widget, _ = self.get_widget_at(*event.screen_offset)
        if leaf_widget and leaf_widget is not self.screen:
            for i, widget in enumerate(leaf_widget.ancestors_with_self):
                self.debug_highlight.append((widget, widget.styles.background, widget.styles.border, widget.border_title if hasattr(widget, "border_title") else None))
                widget.styles.background = Color.from_hsl(i / 10, 1, 0.3)
                if not event.ctrl:
                    widget.styles.border = ("round", Color.from_hsl(i / 10, 1, 0.5))
                    title = widget.__class__.__name__
                    if widget.id:
                        title += "#" + widget.id
                    if widget.classes:
                        title += "." + ".".join(widget.classes)
                    widget.border_title = title

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
        app.filename = os.path.abspath(args.filename)
if args.clear_screen:
    os.system("cls||clear")

app.dark = args.theme == "dark"

if __name__ == "__main__":
    app.run()
