"""The ColorsBox widget for selecting colors."""

from typing import TYPE_CHECKING
from textual import events
from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.reactive import var
from textual.widgets import Button
from textual_paint.char_input import DOUBLE_CLICK_TIME, CharInput

class ColorsBox(Container):
    """Color palette widget."""

    palette: var[tuple[str, ...]] = var(tuple())
    """A tuple of colors to display.
    
    A tuple is used because list mutations can't be watched.
    """

    class ColorSelected(Message):
        """Message sent when a color is selected."""
        def __init__(self, color: str, as_foreground: bool) -> None:
            self.color = color
            self.as_foreground = as_foreground
            super().__init__()

    class EditColor(Message):
        """Message sent when a color is selected."""
        def __init__(self, color_index: int, as_foreground: bool) -> None:
            self.color_index = color_index
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
        yield Container(id="available_colors")

    def watch_palette(self, palette: tuple[str, ...]) -> None:
        """Called when the palette is changed."""
        container = self.query_one("#available_colors")
        buttons = self.query(".color_button").nodes
        for extra_button in buttons[len(palette):]:
            extra_button.remove()
            del self.color_by_button[extra_button]  # type: ignore
        for _new_color in palette[len(buttons):]:
            button = Button("", classes="color_button color_well")
            button.can_focus = False
            container.mount(button)
            buttons.append(button)
        for button, color in zip(buttons, palette):
            button.styles.background = color
            self.color_by_button[button] = color  # type: ignore

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
                self.post_message(self.EditColor(self.query(".color_button").nodes.index(button), secondary))
            self.last_click_time = event.time
            self.last_click_button = button