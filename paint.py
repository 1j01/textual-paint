from enum import Enum
from random import randint
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
from textual.widgets import Button, Static

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
        # - Free-Form Select:  ✂️📐🆓🕸✨⚝🫥🇫/🇸◌
        # - Rectangular Select: ⬚▧🔲
        # - Eraser: 🧼🧽🧹🚫👋🗑️
        # - Fill Bucket (Flood Fill): 🌊💦💧🌈🎉🎊🪣🫗
        # - Pick Color: 🎨💉
        # - Magnifier: 🔍🔎👀🔬🔭🧐🕵️‍♂️🕵️‍♀️
        # - Pencil: ✏️✍️🖎🖊️🖋️✒️🖆📝🖍️
        # - Brush: 🖌️🖌👨‍🎨🧑‍🎨💅
        # - Airbrush: 💨ᖜ╔🧴🥤🫠
        # - Text: 🆎📝📄📃🔤📜A
        # - Line: 📏📉📈⟍𝈏⧹
        # - Curve: ↪️🪝🌙〰️◡◠~∼≈∽∿〜〰﹋﹏≈≋～
        # - Rectangle: ▭▬▮▯◼️◻️⬜⬛🟧🟩
        # - Polygon: ▙𝗟𝙇⬣⬟△▲🔺🔻🔷🔶
        # - Ellipse: ⬭🔴🔵🔶🔷🔸🔹🟠🟡🟢🟣🫧
        # - Rounded Rectangle: ▢⬜⬛
        
        return {
            Tool.free_form_select: "⚝",
            Tool.select: "⬚",
            Tool.eraser: "🧼",
            Tool.fill: "🫗",
            Tool.pick_color: "💉",
            Tool.magnifier: "🔍",
            Tool.pencil: "✏️",
            Tool.brush: "🖌️",
            Tool.airbrush: "💨",
            Tool.text: "A",
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
            Tool.eraser: "Eraser",
            Tool.fill: "Fill Bucket",
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
                yield Static(id="selected_color")
            with Container(id="available_colors"):
                for color in palette:
                    button = Button("", id="color_well_" + color)
                    button.styles.background = color
                    yield button


debug_region_updates = True

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
        ansi = ""
        for y in range(self.height):
            for x in range(self.width):
                if x == 0:
                    ansi += "\033[0m"
                ansi += "\033[48;2;" + self.bg[y][x] + ";38;2;" + self.fg[y][x] + "m" + self.ch[y][x]
            ansi += "\033[0m\r"
        return ansi

class Action:
    """An action that can be undone efficiently using a region update."""

    def __init__(self, name, document: AnsiArtDocument, region: Region = None) -> None:
        """Initialize the action using the document state before modification."""
        if region is None:
            region = Region(0, 0, document.width, document.height)
        self.name = name
        self.live_document = document # only for undoing; TODO: move to parameter of undo()
        self.region = region
        self.update(document)

    def update(self, document: AnsiArtDocument) -> None:
        """Grabs the image data from the current region of the document."""
        self.sub_image_before = AnsiArtDocument(self.region.width, self.region.height)
        self.sub_image_before.copy_region(document, self.region)

    def undo(self) -> None:
        """Undo this action. Note that a canvas refresh is not performed here."""
        self.live_document.copy_region(self.sub_image_before, target_region=self.region)

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

    show_tools_box = var(True)
    show_colors_box = var(True)
    selected_tool = var(Tool.pencil)
    selected_color = var(palette[0])
    selected_char = var("#")

    undos = []
    redos = []

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

    def stamp_brush(self, x: int, y: int, affected_region: Region) -> Region:
        brush_diameter = 1
        if self.selected_tool == Tool.brush:
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
        return affected_region.union(Region(x - brush_diameter // 2, y - brush_diameter // 2, brush_diameter, brush_diameter))
    
    def stamp_char(self, x: int, y: int) -> None:
        if x < self.image.width and y < self.image.height and x >= 0 and y >= 0:
            self.image.ch[y][x] = self.selected_char
            self.image.bg[y][x] = self.selected_color
    
    def undo(self) -> None:
        if len(self.undos) > 0:
            action = self.undos.pop()
            redo_action = Action("Undo " + action.name, self.image, action.region)
            action.undo()
            self.redos.append(redo_action)
            self.canvas.refresh()

    def redo(self) -> None:
        if len(self.redos) > 0:
            action = self.redos.pop()
            undo_action = Action("Undo " + action.name, self.image, action.region)
            action.undo()
            self.undos.append(undo_action)
            self.canvas.refresh()

    def compose(self) -> ComposeResult:
        """Add our widgets."""
        with Container(id="paint"):
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
        self.image = AnsiArtDocument(80, 24)
        self.canvas = self.query_one("#canvas")
        self.canvas.image = self.image

    def on_canvas_tool_start(self, event: Canvas.ToolStart) -> None:
        """Called when the user starts drawing on the canvas."""
        if self.selected_tool != Tool.pencil and self.selected_tool != Tool.brush:
            self.selected_tool = Tool.pencil
            # TODO: support other tools
        self.image_at_start = AnsiArtDocument(self.image.width, self.image.height)
        self.image_at_start.copy_region(self.image)
        region = Region(event.mouse_down_event.x, event.mouse_down_event.y, 1, 1)
        if len(self.redos) > 0:
            self.redos = []
        action = Action(self.selected_tool.get_name(), self.image)
        self.undos.append(action)
        region = self.stamp_brush(event.mouse_down_event.x, event.mouse_down_event.y, region)
        action.region = region
        action.update(self.image_at_start)
        self.canvas.refresh(region)
        event.stop()

    def on_canvas_tool_update(self, event: Canvas.ToolUpdate) -> None:
        """Called when the user is drawing on the canvas."""
        mm = event.mouse_move_event
        action = self.undos[-1]
        affected_region = Region(mm.x, mm.y, 1, 1)
        for x, y in bresenham_walk(mm.x - mm.delta_x, mm.y - mm.delta_y, mm.x, mm.y):
            affected_region = self.stamp_brush(x, y, affected_region)
        
        # Update action region and image data
        action.region = action.region.union(affected_region)
        action.update(self.image_at_start)

        self.canvas.refresh(affected_region)
        event.stop()

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
        elif key == "ctrl+q" or key == "meta+q":
            self.exit()
        elif key == "ctrl+t":
            self.show_tools_box = not self.show_tools_box
        elif key == "ctrl+w":
            self.show_colors_box = not self.show_colors_box
        elif key == "ctrl+z":
            self.undo()
        # Ctrl+Shift+Z doesn't seem to work on Ubuntu or VS Code terminal
        elif key == "ctrl+shift+z" or key == "shift+ctrl+z" or key == "ctrl+y" or key == "f4":
            self.redo()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is clicked or activated with the keyboard."""

        button_id = event.button.id
        assert button_id is not None

        if button_id.startswith("tool_button_"):
            self.selected_tool = Tool[button_id[len("tool_button_") :]]
        elif button_id.startswith("color_well_"):
            self.selected_color = button_id[len("color_well_") :]


if __name__ == "__main__":
    PaintApp().run()
