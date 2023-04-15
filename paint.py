import os
import re
import sys
import argparse
from enum import Enum
from random import randint, random
from typing import List, Optional
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
from textual.widgets import Button, Static, Input, DirectoryTree
from menus import MenuBar, Menu, MenuItem, Separator
from windows import Window

ascii_only_icons = False

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
        # - Rectangular Select: ⬚▧🔲 ⣏⣹
        # - Eraser/Color Eraser: 🧼🧽🧹🚫👋🗑️
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
            Tool.free_form_select: "Free-Form Select",
            Tool.select: "Rectangular Select",
            Tool.eraser: "Eraser/Color Eraser",
            Tool.fill: "Fill With Color",
            Tool.pick_color: "Pick Color",
            Tool.magnifier: "Magnifier",
            Tool.pencil: "Pencil",
            Tool.brush: "Brush",
            Tool.airbrush: "Airbrush",
            Tool.text: "Text",
            Tool.line: "Line",
            Tool.curve: "Curve",
            Tool.rectangle: "Rectangle",
            Tool.polygon: "Polygon",
            Tool.ellipse: "Ellipse",
            Tool.rounded_rectangle: "Rounded Rectangle",
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
        """Get the ANSI representation of the document. Untested. This is a freebie from the AI."""
        
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
        # Hack to fix mouse coordinates, not needed for mouse down.
        # This seems like a bug.
        event.x += int(self.parent.scroll_x)
        event.y += int(self.parent.scroll_y)

        if self.pointer_active:
            self.post_message(self.ToolUpdate(event))
        else:
            self.post_message(self.ToolPreviewUpdate(event))

    def on_mouse_up(self, event) -> None:
        self.pointer_active = False
        self.capture_mouse(False)

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
    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("meta+q", "quit", "Quit"),
        ("ctrl+s", "save", "Save"),
        ("ctrl+shift+s", "save_as", "Save As"),
        # ("ctrl+o", "open", "Open"),
        ("ctrl+n", "new", "New"),
        # ("ctrl+shift+n", "clear_image", "Clear Image"),
        ("ctrl+t", "toggle_tools_box", "Toggle Tools Box"),
        ("ctrl+w", "toggle_colors_box", "Toggle Colors Box"),
        ("ctrl+z", "undo", "Undo"),
        # Ctrl+Shift+Z doesn't seem to work on Ubuntu or VS Code terminal
        ("ctrl+shift+z", "redo", "Redo"),
        ("shift+ctrl+z", "redo", "Redo"),
        ("ctrl+y", "redo", "Redo"),
        ("f4", "redo", "Redo"),
        # action_toggle_dark is built in to App
        ("ctrl+d", "toggle_dark", "Toggle Dark Mode"),
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
    preview_action: Optional[Action] = None

    NAME_MAP = {
        # key to button id
    }

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
        self.query_one("#tool_button_" + old_selected_tool.name).classes = "tool_button"
        self.query_one("#tool_button_" + selected_tool.name).classes = "tool_button selected"

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
            redo_action = Action("Undo " + action.name, self.image, action.region)
            action.undo(self.image)
            self.redos.append(redo_action)
            self.canvas.refresh()

    def action_redo(self) -> None:
        if len(self.redos) > 0:
            self.cancel_preview()
            action = self.redos.pop()
            undo_action = Action("Undo " + action.name, self.image, action.region)
            action.undo(self.image)
            self.undos.append(undo_action)
            self.canvas.refresh()

    def action_save(self) -> None:
        """Save the image to a file."""
        if self.filename:
            ansi = self.image.get_ansi()
            with open(self.filename, "w") as f:
                f.write(ansi)
        else:
            self.action_save_as()
    
    def action_save_as(self) -> None:
        """Save the image as a new file."""
        for old_window in self.query("#save_as_dialog").nodes:
            old_window.close()
        window = Window(
            classes="dialog",
            id="save_as_dialog",
            title="Save As",
        )
        window.content.mount(
            DirectoryTree(id="save_as_directory_tree", path="/"),
            Input(id="save_as_filename_input", placeholder="Filename"),
            Button("Save", id="save_as_save_button", variant="primary"),
            Button("Cancel", id="save_as_cancel_button"),
        )
        self.mount(window)
        def expand_directory_tree():
            """Expand the directory tree to the target directory, either the folder of the open file or the current working directory."""
            target_dirs = (self.filename or os.getcwd()).split(os.path.sep)
            tree = window.content.query_one("#save_as_directory_tree")
            node = tree.root
            def get_node_name(node):
                return os.path.basename(node.data.path.rstrip(os.path.sep))
            for dir_name in target_dirs:
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
                        # Found file.
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

        expand_directory_tree()
    
    def confirm_overwrite(self, filename: str, callback) -> None:
        for old_window in self.query("#overwrite_dialog").nodes:
            old_window.close()

        class OverwriteWindow(Window):
            """
            A window that asks the user if they want to overwrite a file.
            
            This subclass only exists to listen for the button presses.
            Is there a better way to do this?
            Dynamically assigning on_button_pressed to the instance didn't work.
            """
            def on_button_pressed(self, event):
                if event.button.id == "overwrite_yes_button":
                    callback()
                window.close()

        window = OverwriteWindow(
            classes="dialog",
            id="overwrite_dialog",
            title="Save As",
        )
        window.content.mount(
            Horizontal(
                Static("""[#ffff00]
    _
   / \\
  / | \\
 /  .  \\
/_______\\
[/]""", classes="warning_icon"),
                Vertical(
                    Static(filename + " already exists.", markup=False),
                    Static("Do you want to replace it?"),
                    Horizontal(
                        Button("Yes", id="overwrite_yes_button"),
                        Button("No", id="overwrite_no_button"),
                    ),
                    classes="main_content"
                )
            )
        )
        self.mount(window)
            

    # def action_open(self) -> None:
    #     """Open an image from a file."""
    #     filename = self.query_one("#file_open").value
    #     if filename:
    #         with open(filename, "r") as f:
    #             self.image = AnsiArtDocument.from_ansi(f.read())
    #             self.canvas.image = self.image

    def action_new(self) -> None:
        """Create a new image."""
        # TODO: prompt to save if there are unsaved changes
        self.image = AnsiArtDocument(80, 24)
        self.canvas.image = self.image
        self.canvas.refresh()
        self.filename = None
        self.undos = []
        self.redos = []
        self.preview_action = None
        # Following MS Paint's lead and resetting the color (but not the tool.)
        # It probably has to do with color modes.
        self.selected_color = palette[0]
        self.selected_char = " "

    def compose(self) -> ComposeResult:
        """Add our widgets."""
        with Container(id="paint"):
            yield MenuBar([
                MenuItem("File", submenu=Menu([
                    MenuItem("New", self.action_new),
                    # MenuItem("Open", self.action_open),
                    MenuItem("Save", self.action_save),
                    MenuItem("Save As", self.action_save_as),
                    # MenuItem("Quit", self.action_quit),
                ])),
                MenuItem("Edit", submenu=Menu([
                    MenuItem("Undo", self.action_undo),
                    MenuItem("Redo", self.action_redo),
                ])),
                MenuItem("View", submenu=Menu([
                    MenuItem("Tool Box", self.action_toggle_tools_box),
                    MenuItem("Color Box", self.action_toggle_colors_box),
                ])),
                MenuItem("Image"),
                MenuItem("Colors"),
                MenuItem("Help"),
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

        if button_id.startswith("tool_button_"):
            self.selected_tool = Tool[button_id[len("tool_button_") :]]
        elif button_id.startswith("color_button_"):
            self.selected_color = button_id[len("color_button_") :]
        elif button_id == "save_as_save_button":
            name = self.query_one("#save_as_filename_input", Input).value
            if name:
                if self.directory_tree_selected_path:
                    name = os.path.join(self.directory_tree_selected_path, name)
                def on_save_confirmed():
                    self.query_one("#save_as_dialog", Window).close()
                    self.filename = name
                    self.action_save()
                if os.path.exists(name):
                    self.confirm_overwrite(name, on_save_confirmed)
                else:
                    on_save_confirmed()
                    
        elif button_id == "save_as_cancel_button":
            self.query_one("#save_as_dialog", Window).close()

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
            self.query_one("#save_as_filename_input", Input).value = name
        else:
            self.directory_tree_selected_path = None

if __name__ == "__main__":
    app = PaintApp()

    parser = argparse.ArgumentParser(description='Paint in the terminal.')
    parser.add_argument('--ascii-only-icons', action='store_true', help='Use only ASCII characters for tool icons')
    parser.add_argument('filename', nargs='?', default=None, help='File to open')
    args = parser.parse_args()
    if args.ascii_only_icons:
        ascii_only_icons = True
    if args.filename:
        # if args.filename == "-" and not sys.stdin.isatty():
        #     app.image = AnsiArtDocument.from_text(sys.stdin.read())
        #     app.filename = "<stdin>"
        # else:
        with open(args.filename, 'r') as my_file:
            app.image = AnsiArtDocument.from_text(my_file.read())
            app.filename = args.filename

    app.run()
