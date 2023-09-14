"""The ColorsBox widget for selecting colors."""

from typing import TYPE_CHECKING
from textual import events
from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.widgets import Button
from textual_paint.char_input import DOUBLE_CLICK_TIME, CharInput

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
            from textual_paint.paint import palette # TODO: restructure data flow
            for color in palette:
                button = Button("", classes="color_button color_well")
                button.styles.background = color
                button.can_focus = False
                self.color_by_button[button] = color
                yield button

    def update_palette(self) -> None:  # , palette: list[str]) -> None:
        """Update the palette with new colors."""
        from textual_paint.paint import palette # TODO: restructure data flow
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
            secondary = event.ctrl or event.button == 3
            self.post_message(self.ColorSelected(self.color_by_button[button], secondary))
            # Detect double click and open Edit Colors dialog.
            if event.time - self.last_click_time < DOUBLE_CLICK_TIME and button == self.last_click_button:
                if TYPE_CHECKING:
                    from textual_paint.paint import PaintApp
                    assert isinstance(self.app, PaintApp)
                    # TODO: decouple from PaintApp
                self.app.action_edit_colors(self.query(".color_button").nodes.index(button), secondary)
            self.last_click_time = event.time
            self.last_click_button = button