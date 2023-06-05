from functools import lru_cache
from random import random

from rich.color import Color as RichColor
from rich.region import Region
from rich.segment import Segment
from rich.style import Style
from textual.color import Color
from textual.filter import LineFilter

blend_color = Color(255, 0, 0)

# @lru_cache(1024)
def colorize_style(style: Style, blend_factor: float = 0.5) -> Style:
    """Tint colors."""
    style_color = style.color
    style_background = style.bgcolor
    color = (
        None
        if style_color is None
        else Color.from_rich_color(style_color).blend(blend_color, blend_factor).rich_color
    )
    background = (
        None
        if style_background is None
        else Color.from_rich_color(style_background).blend(blend_color, blend_factor).rich_color
    )
    return style + Style.from_color(color, background)


class Colorize(LineFilter):
    """Tint all colors."""

    def __init__(self, blend_factor: float = 0.5):
        super().__init__()
        self.blend_factor = blend_factor

    def apply(self, segments: list[Segment], background: Color) -> list[Segment]:
        """Transform a list of segments.

        Args:
            segments: A list of segments.
            background: The background color.

        Returns:
            A new list of segments.
        """
        _colorize_style = colorize_style
        _Segment = Segment
        # _blend_factor = self.blend_factor
        _blend_factor = random() # visualize updates
        return [
            _Segment(text, _colorize_style(style, _blend_factor), None)
            for text, style, _ in segments
        ]

# class ColorizeRegion(LineFilter):
#     """Convert all colors to red."""

#     def __init__(self, region: Region, blend_factor: float = 0.5):
#         super().__init__()
#         self.region = region
#         self.blend_factor = blend_factor

#     def apply(self, segments: list[Segment], background: Color) -> list[Segment]:
#         """Transform a list of segments.

#         Args:
#             segments: A list of segments.
#             background: The background color.

#         Returns:
#             A new list of segments.
#         """
#         _colorize_style = colorize_style
#         _Segment = Segment
#         _blend_factor = self.blend_factor
#         # _blend_factor = random() # visualize updates
#         return [
#             _Segment(text, _colorize_style(style, _blend_factor), None)
#             for text, style, _ in segments
#         ]
