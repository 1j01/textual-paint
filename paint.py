from enum import Enum

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container
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


class ToolsBox(Container):
    """Widget containing tool buttons"""

    def compose(self) -> ComposeResult:
        """Add our buttons."""
        with Container(id="tools_box"):
            # tool buttons
            for tool in Tool:
                yield Button(tool.get_icon(), id="tool_button_" + tool.name)

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
        self.image_ch[event.y][event.x] = "X"
        self.image_bg[event.y][event.x] = "#ff0000"
        self.pointer_active = True
        self.display_canvas()
    
    def on_mouse_move(self, event) -> None:
        if self.pointer_active:
            self.image_ch[event.y][event.x] = "O"
            self.image_bg[event.y][event.x] = "#ffff00"
            self.display_canvas()

    def on_mouse_up(self, event) -> None:
        self.pointer_active = False

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
            yield ToolsBox()
            yield Canvas()

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
