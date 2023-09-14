"""Specialized Input for entering a single character, used in the ColorsBox widget. Also shows the selected colors."""

from typing import TYPE_CHECKING

from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.color import Color
from textual.filter import LineFilter
from textual.message import Message
from textual.strip import Strip
from textual.widgets import Input

DOUBLE_CLICK_TIME = 0.8 # seconds

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
        if TYPE_CHECKING:
            from textual_paint.paint import PaintApp
            assert isinstance(self.app, PaintApp)
            # TODO: decouple from PaintApp
        self.app.on_paste(event)

    def validate_cursor_position(self, cursor_position: int) -> int:
        """Force the cursor position to 0 so that it's over the character."""
        return 0

    def insert_text_at_cursor(self, text: str) -> None:
        """Override to limit the value to a single character."""
        self.value = text[-1] if text else " "

    def render_line(self, y: int) -> Strip:
        """Overrides rendering to color the character, since Input doesn't seem to support the color style."""
        if TYPE_CHECKING:
            from textual_paint.paint import PaintApp
            assert isinstance(self.app, PaintApp)
            # TODO: decouple from PaintApp
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
    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Detect double click and open character selector dialog, or swap colors on right click or Ctrl+click."""
        if TYPE_CHECKING:
            from textual_paint.paint import PaintApp
            assert isinstance(self.app, PaintApp)
            # TODO: decouple from PaintApp
        if event.ctrl or event.button == 3: # right click
            self.app.action_swap_colors()
            return
        if event.time - self.last_click_time < DOUBLE_CLICK_TIME:
            self.app.action_open_character_selector()
        self.last_click_time = event.time
