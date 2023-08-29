"""Workaround for misalignment. Based on the Tooltip widget from Textual."""

from __future__ import annotations
from textual.geometry import Offset

from textual.widgets import Static


class AlignmentFixer(Static):
    DEFAULT_CSS = """
    AlignmentFixer {
        layer: alignment_fixer;
        margin: 1 2;
        /*padding: 1 2;*/
        background: red;
        width: auto;
        height: auto;
        constrain: inflect;
        max-width: 40;
        /*display: none;*/
    }
    AlignmentFixer.display {
        display: none;
        /*display: block;*/
    }
    """

    def on_mount(self) -> None:
        self._absolute_offset = Offset(1, 15)
        self.set_interval(1.0, lambda: self.toggle_class("display"))
        # self.display = True
