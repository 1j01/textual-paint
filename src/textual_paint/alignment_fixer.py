"""Workaround for misalignment."""

from __future__ import annotations
from textual.geometry import Region, Size

from textual.widgets import Static


class AlignmentFixer(Static):
    DEFAULT_CSS = """
    AlignmentFixer {
        display: none;
    }
    """

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_hax)

    def refresh_hax(self) -> None:
        # self.screen.refresh(Region.from_offset(self.app.mouse_position, Size(1, 1)))
        # self.query(".tool_button").refresh()
        self.query(".tool_button").set_styles("background: #ff0000;")
        self.query(".tool_button").set_styles("width: 10;")
        # self.query(".tool_button").set_styles("background:")
