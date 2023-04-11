from enum import Enum

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import var, reactive
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
        # - Polygon: ▙𝗟𝙇⬣⬟△▲🔺🔻🔳🔲🔷🔶🔴🔵🟠🟡
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
        """Add our buttons."""
        with Container(id="colors_box"):
            for color in palette:
                button = Button("", id="color_well_" + color)
                button.styles.background = color
                yield button

class Canvas(Static):
    """The image document widget."""

    def __init__(self, **kwargs) -> None:
        """Initialize the canvas."""
        super().__init__(**kwargs)
        self.image_width = 80
        self.image_height = 24
        self.image_ch = [["." for _ in range(self.image_width)] for _ in range(self.image_height)]
        self.image_bg = [["#ffffff" for _ in range(self.image_width)] for _ in range(self.image_height)]
        self.image_fg = [["#000000" for _ in range(self.image_width)] for _ in range(self.image_height)]
        self.pointer_active = False

    def on_mount(self) -> None:
        self.display_canvas()

    def on_mouse_down(self, event) -> None:
        if event.x < self.image_width and event.y < self.image_height and event.x >= 0 and event.y >= 0:
            self.image_ch[event.y][event.x] = "X"
            self.image_bg[event.y][event.x] = "#ff0000"
        self.pointer_active = True
        self.capture_mouse(True)
        self.display_canvas()
    
    def on_mouse_move(self, event) -> None:
        if self.pointer_active:
            self.bresenham_walk(event.x - event.delta_x, event.y - event.delta_y, event.x, event.y, lambda x, y: self.draw_dot(x, y))
            self.display_canvas()

    def bresenham_walk(self, x0: int, y0: int, x1: int, y1: int, callback) -> None:
        """Bresenham's line algorithm"""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            callback(x0, y0)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err = err - dy
                x0 = x0 + sx
            if e2 < dx:
                err = err + dx
                y0 = y0 + sy

    def draw_dot(self, x: int, y: int) -> None:
        if x < self.image_width and y < self.image_height and x >= 0 and y >= 0:
            self.image_ch[y][x] = "O"
            self.image_bg[y][x] = "#ffff00"

    def on_mouse_up(self, event) -> None:
        self.pointer_active = False
        self.capture_mouse(False)

    def display_canvas(self) -> None:
        """Update the content area."""
        # TODO: avoid generating insane amounts of markup that then has to be parsed
        text = ""
        for y in range(self.image_height):
            for x in range(self.image_width):
                bg = self.image_bg[y][x]
                fg = self.image_fg[y][x]
                ch = self.image_ch[y][x]
                text += "["+fg+" on "+bg+"]" + ch + "[/]"
            text += "\n"
        self.update(text)

class PaintApp(App):
    """MS Paint like image editor in the terminal."""

    CSS_PATH = "paint.css"

    # show_tools_box = var(True)
    selected_tool = var(Tool.pencil)

    NAME_MAP = {
        # key to button id
    }

    # def watch_show_tools_box(self, show_tools_box: bool) -> None:
    #     """Called when show_tools_box changes."""
    #     self.query_one("#tools_box").display = not show_tools_box

    def watch_selected_tool(self, old_selected_tool: Tool, selected_tool: Tool) -> None:
        """Called when selected_tool changes."""
        self.query_one("#tool_button_" + old_selected_tool.name).classes = "tool_button"
        self.query_one("#tool_button_" + selected_tool.name).classes = "tool_button selected"

    def compose(self) -> ComposeResult:
        """Add our widgets."""
        with Container(id="paint"):
            yield Container(
                ToolsBox(),
                Canvas(),
                id="main-horizontal-split",
            )
            yield ColorsBox()

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is pressed."""

        button_id = event.button.id
        assert button_id is not None

        if button_id.startswith("tool_button_"):
            self.selected_tool = Tool[button_id[len("tool_button_") :]]


if __name__ == "__main__":
    PaintApp().run()
