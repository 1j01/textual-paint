"""Workaround for misalignment. Based on the Tooltip widget from Textual."""

from __future__ import annotations

from textual.widgets import Static


class AlignmentFixer(Static):
    DEFAULT_CSS = """
    AlignmentFixer {
        layer: _tooltips;
        margin: 1 2;
        /*padding: 1 2;*/
        background: red;
        width: auto;
        height: auto;
        constrain: inflect;
        max-width: 40;
        /* display: none; */
    }
    """
