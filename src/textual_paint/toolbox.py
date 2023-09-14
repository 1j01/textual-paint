"""Container for tool buttons."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.widgets import Button

from textual_paint.tool import Tool


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
