
from math import ceil, floor
from rich.color import Color
from rich.segment import Segment, Segments
from rich.style import Style
from textual.scrollbar import ScrollBarRender


class ASCIIScrollBarRender(ScrollBarRender):
    """A scrollbar renderer that uses only ASCII space characters."""
    @classmethod
    def render_bar(
        cls,
        size: int = 25,
        virtual_size: float = 50,
        window_size: float = 20,
        position: float = 0,
        thickness: int = 1,
        vertical: bool = True,
        back_color: Color = Color.parse("#555555"),
        bar_color: Color = Color.parse("bright_magenta"),
    ) -> Segments:

        back = back_color
        bar = bar_color

        width_thickness = thickness if vertical else 1

        _Segment = Segment
        _Style = Style
        blank = " " * width_thickness

        foreground_meta = {"@mouse.up": "release", "@mouse.down": "grab"}
        if window_size and size and virtual_size and size != virtual_size:
            bar_ratio = virtual_size / size
            thumb_size = floor(max(1, window_size / bar_ratio))

            position_ratio = position / (virtual_size - window_size)
            position = (size - thumb_size) * position_ratio

            start_index = max(0, int(position))
            end_index = max(0, start_index + ceil(thumb_size))

            upper = {"@mouse.up": "scroll_up"}
            lower = {"@mouse.up": "scroll_down"}

            upper_back_segment = Segment(blank, _Style(bgcolor=back, meta=upper))
            lower_back_segment = Segment(blank, _Style(bgcolor=back, meta=lower))

            segments = [upper_back_segment] * int(size)
            segments[end_index:] = [lower_back_segment] * (size - end_index)

            segments[start_index:end_index] = [
                _Segment(blank, _Style(bgcolor=bar, meta=foreground_meta))
            ] * (end_index - start_index)

        else:
            style = _Style(bgcolor=back)
            segments = [_Segment(blank, style=style)] * int(size)
        if vertical:
            return Segments(segments, new_lines=True)
        else:
            return Segments((segments + [_Segment.line()]) * thickness, new_lines=False)
