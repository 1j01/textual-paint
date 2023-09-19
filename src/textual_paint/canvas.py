"""The Canvas widget."""

from typing import TYPE_CHECKING, Any, Optional
from rich.color import Color

from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.geometry import Offset, Region, Size
from textual.message import Message
from textual.reactive import reactive
from textual.strip import Strip
from textual.widget import Widget

from textual_paint.ansi_art_document import AnsiArtDocument, Selection
from textual_paint.args import args
from textual_paint.meta_glyph_font import largest_font_that_fits


def scale_region(region: Region, scale: int) -> Region:
    """Returns the region scaled by the given factor."""
    return Region(region.x * scale, region.y * scale, region.width * scale, region.height * scale)


class Canvas(Widget):
    """The drawing surface widget. Displays an AnsiArtDocument and Selection, and handles mouse events."""

    magnification = reactive(1, layout=True)
    show_grid = reactive(False)

    # Is it kosher to include an event in a message?
    # Is it better (and possible) to bubble up the event, even though I'm capturing the mouse?
    # Or would it be better to just have Canvas own duplicate state for all tool parameters?
    # That's what I was refactoring to avoid. So far I've made things more complicated,
    # but I'm betting it will be good when implementing different tools.
    # Maybe the PaintApp widget can capture the mouse events instead?
    # Not sure if that would work as nicely when implementing selections.
    # I'd have to think about it.
    # But it would make the Canvas just be a widget for rendering, which seems good.
    class ToolStart(Message):
        """Message when starting drawing."""

        def __init__(self, mouse_down_event: events.MouseDown) -> None:
            self.x = mouse_down_event.x
            self.y = mouse_down_event.y
            self.button = mouse_down_event.button
            self.ctrl = mouse_down_event.ctrl
            super().__init__()

    class ToolUpdate(Message):
        """Message when dragging on the canvas."""

        def __init__(self, mouse_move_event: events.MouseMove) -> None:
            self.x = mouse_move_event.x
            self.y = mouse_move_event.y
            super().__init__()

    class ToolStop(Message):
        """Message when releasing the mouse."""

        def __init__(self, mouse_up_event: events.MouseUp) -> None:
            self.x = mouse_up_event.x
            self.y = mouse_up_event.y
            super().__init__()

    class ToolPreviewUpdate(Message):
        """Message when moving the mouse while the mouse is up."""

        def __init__(self, mouse_move_event: events.MouseMove) -> None:
            self.x = mouse_move_event.x
            self.y = mouse_move_event.y
            super().__init__()

    class ToolPreviewStop(Message):
        """Message when the mouse leaves the canvas while previewing (not while drawing)."""

        def __init__(self) -> None:
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the canvas."""
        super().__init__(**kwargs)
        self.image: AnsiArtDocument|None = None
        self.pointer_active: bool = False
        self.magnifier_preview_region: Optional[Region] = None
        self.select_preview_region: Optional[Region] = None
        self.which_button: Optional[int] = None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Called when a mouse button is pressed.

        This either starts drawing, or if both mouse buttons are pressed, cancels the current action.
        """
        if self.app.has_class("view_bitmap"):
            # Exiting is handled by the PaintApp.
            return

        self.fix_mouse_event(event)  # not needed, pointer isn't captured yet.
        event.x //= self.magnification
        event.y //= self.magnification

        if self.pointer_active and self.which_button != event.button:
            if TYPE_CHECKING:
                from textual_paint.paint import PaintApp
                assert isinstance(self.app, PaintApp)
                # TODO: Pyright is marking this as Never... maybe use cast instead?
                # Not sure why it would be Never though, might be a bug.
            self.app.stop_action_in_progress()
            return

        self.post_message(self.ToolStart(event))
        self.pointer_active = True
        self.which_button = event.button
        self.capture_mouse(True)

    def fix_mouse_event(self, event: events.MouseEvent) -> None:
        """Work around inconsistent widget-relative mouse coordinates by calculating from screen coordinates."""
        # Hack to fix mouse coordinates, not needed for mouse down,
        # or while the mouse is up.
        # This seems like a bug.
        # I think it's due to coordinates being calculated differently during mouse capture.
        # if self.pointer_active:
        #     assert isinstance(self.parent, Widget)
        #     event.x += int(self.parent.scroll_x)
        #     event.y += int(self.parent.scroll_y)
        # The above fix sometimes works but maybe sometimes shouldn't apply or isn't right.
        # In order to make this robust without knowing the exact cause,
        # I'm going to always calculate straight from the screen coordinates.
        # This should also make it robust against the bugs in the library being fixed.
        # node: DOMNode|None = self
        offset = event.screen_offset
        # while node:
        #     offset = offset - node.offset
        #     node = node.parent
        # assert isinstance(self.parent, Widget)
        offset = offset - self.region.offset  #+ Offset(int(self.parent.scroll_x), int(self.parent.scroll_y))
        event.x = offset.x
        event.y = offset.y


    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Called when the mouse is moved. Update the tool action or preview."""
        self.fix_mouse_event(event)
        event.x //= self.magnification
        event.y //= self.magnification

        if self.pointer_active:
            self.post_message(self.ToolUpdate(event))
        else:
            # I put this in the else block just for performance.
            # Hopefully it wouldn't matter much, but
            # the pointer should never be active in View Bitmap mode.
            if self.app.has_class("view_bitmap"):
                return
            self.post_message(self.ToolPreviewUpdate(event))

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Called when a mouse button is released. Stop the current tool."""
        self.fix_mouse_event(event)
        event.x //= self.magnification
        event.y //= self.magnification

        if self.pointer_active:
            self.post_message(self.ToolStop(event))
        self.pointer_active = False
        self.capture_mouse(False)

    def on_leave(self, event: events.Leave) -> None:
        """Called when the mouse leaves the canvas. Stop preview if applicable."""
        if not self.pointer_active:
            self.post_message(self.ToolPreviewStop())

    def get_content_width(self, container: Size, viewport: Size) -> int:
        """Defines the intrinsic width of the widget."""
        if self.image is None:
            return 0 # shouldn't really happen
        return self.image.width * self.magnification

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        """Defines the intrinsic height of the widget."""
        if self.image is None:
            return 0 # shouldn't really happen
        return self.image.height * self.magnification

    def render_line(self, y: int) -> Strip:
        """Render a line of the widget. y is relative to the top of the widget."""
        assert self.image is not None
        # self.size.width/height already is multiplied by self.magnification.
        if y >= self.size.height:
            return Strip.blank(self.size.width)
        segments: list[Segment] = []
        sel = self.image.selection
        magnification = self.magnification  # reactive.__get__ is a performance bottleneck

        # Avoiding "possibly unbound" errors.
        magnifier_preview_region = None
        inner_magnifier_preview_region = None
        select_preview_region = None
        inner_select_preview_region = None
        selection_region = None
        inner_selection_region = None

        if self.magnifier_preview_region:
            magnifier_preview_region = scale_region(self.magnifier_preview_region, magnification)
            inner_magnifier_preview_region = magnifier_preview_region.shrink((1, 1, 1, 1))
        if self.select_preview_region:
            select_preview_region = scale_region(self.select_preview_region, magnification)
            inner_select_preview_region = select_preview_region.shrink((1, 1, 1, 1))
        if sel:
            selection_region = scale_region(sel.region, magnification)
            inner_selection_region = selection_region.shrink((1, 1, 1, 1))
        show_grid = magnification >= 4 and self.show_grid  # avoiding reactive.__get__ in loop, not as much of a bottleneck though
        for x in range(self.size.width):
            cell_x = x // magnification
            cell_y = y // magnification
            try:
                if sel and sel.contained_image and sel.region.contains(cell_x, cell_y) and (sel.mask is None or sel.mask[cell_y - sel.region.y][cell_x - sel.region.x]):
                    bg = sel.contained_image.bg[cell_y - sel.region.y][cell_x - sel.region.x]
                    fg = sel.contained_image.fg[cell_y - sel.region.y][cell_x - sel.region.x]
                    ch = sel.contained_image.ch[cell_y - sel.region.y][cell_x - sel.region.x]
                else:
                    bg = self.image.bg[cell_y][cell_x]
                    fg = self.image.fg[cell_y][cell_x]
                    ch = self.image.ch[cell_y][cell_x]
            except IndexError:
                # This should be easier to debug visually.
                bg = "#555555"
                fg = "#cccccc"
                ch = "?"
            if magnification > 1:
                ch = self.big_ch(ch, x % magnification, y % magnification, magnification)
                if show_grid:
                    if x % magnification == 0 or y % magnification == 0:
                        # Not setting `bg` here, because:
                        # Its actually useful to see the background color of the cell,
                        # as it lets you distinguish between a space " " and a full block "█".
                        # Plus this lets the grid be more subtle, visually taking up less than a cell.
                        fg = "#c0c0c0" if (x + y) % 2 == 0 else "#808080"
                        if x % magnification == 0 and y % magnification == 0:
                            ch = "+" if args.ascii_only else "▛" # "┼" # (🭽 may render as wide)
                        elif x % magnification == 0:
                            ch = "|" if args.ascii_only else "▌" # "┆" # (▏, not 🭰)
                        elif y % magnification == 0:
                            ch = "-" if args.ascii_only else "▀" # "┄" # (▔, not 🭶)
            style = Style.from_color(color=Color.parse(fg), bgcolor=Color.parse(bg))
            assert style.color is not None
            assert style.bgcolor is not None
            def within_text_selection_highlight(textbox: Selection) -> int:
                if cell_x >= textbox.region.right or cell_x < textbox.region.x:
                    # Prevent inverting outside the textbox.
                    return False
                def offset_to_text_index(offset: Offset) -> int:
                    return offset.y * textbox.region.width + offset.x
                start_index = offset_to_text_index(textbox.text_selection_start)
                end_index = offset_to_text_index(textbox.text_selection_end)
                min_index = min(start_index, end_index)
                max_index = max(start_index, end_index)
                cell_index = offset_to_text_index(Offset(cell_x, cell_y) - textbox.region.offset)
                return min_index <= cell_index <= max_index
            if TYPE_CHECKING:
                from textual_paint.paint import PaintApp
                assert isinstance(self.app, PaintApp)
            if (
                (self.magnifier_preview_region and magnifier_preview_region.contains(x, y) and (not inner_magnifier_preview_region.contains(x, y))) or  # type: ignore
                (self.select_preview_region and select_preview_region.contains(x, y) and (not inner_select_preview_region.contains(x, y))) or  # type: ignore
                (sel and (not sel.textbox_mode) and (self.app.selection_drag_offset is None) and selection_region.contains(x, y) and (not inner_selection_region.contains(x, y))) or  # type: ignore
                (sel and sel.textbox_mode and within_text_selection_highlight(sel))
            ):
                # invert the colors
                if TYPE_CHECKING:
                    assert style.color.triplet is not None
                    assert style.bgcolor.triplet is not None
                style = Style.from_color(
                    color=Color.from_rgb(255 - style.color.triplet.red, 255 - style.color.triplet.green, 255 - style.color.triplet.blue),
                    bgcolor=Color.from_rgb(255 - style.bgcolor.triplet.red, 255 - style.bgcolor.triplet.green, 255 - style.bgcolor.triplet.blue)
                )
            segments.append(Segment(ch, style))
        return Strip(segments, self.size.width)

    def refresh_scaled_region(self, region: Region) -> None:
        """Refresh a region of the widget, scaled by the magnification."""
        if self.magnification == 1:
            self.refresh(region)
            return
        # TODO: are these offsets needed? I added them because of a problem which I've fixed
        self.refresh(Region(
            (region.x - 1) * self.magnification,
            (region.y - 1) * self.magnification,
            (region.width + 2) * self.magnification,
            (region.height + 2) * self.magnification,
        ))

    def watch_magnification(self) -> None:
        """Called when magnification changes."""
        self.active_meta_glyph_font = largest_font_that_fits(self.magnification, self.magnification)

    def big_ch(self, ch: str, x: int, y: int, magnification: int) -> str:
        """Return a character part of a meta-glyph."""
        if self.active_meta_glyph_font and ch in self.active_meta_glyph_font.glyphs:
            glyph_lines = self.active_meta_glyph_font.glyphs[ch]
            x -= (magnification - self.active_meta_glyph_font.width) // 2
            y -= (magnification - self.active_meta_glyph_font.height) // 2
            if y >= len(glyph_lines) or y < 0:
                return " "
            glyph_line = glyph_lines[y]
            if x >= len(glyph_line) or x < 0:
                return " "
            return glyph_line[x]
        match ch:
            case " ":
                return " "
            case "░":
                return "░"
            case "▒":
                return "▒"
            case "▓":
                return "▓"
            case "█":
                return "█"
            # These are now obsolete special cases of below fractional block character handling.
            # case "▄":
            #     return "█" if y >= magnification // 2 else " "
            # case "▀":
            #     return "█" if y < magnification // 2 else " "
            # case "▌":
            #     return "█" if x < magnification // 2 else " "
            # case "▐":
            #     return "█" if x >= magnification // 2 else " "
            # Corner triangles
            case "◣":
                diagonal = x - y
                return "█" if diagonal < 0 else " " if diagonal > 0 else "◣"
            case "◥":
                diagonal = x - y
                return "█" if diagonal > 0 else " " if diagonal < 0 else "◥"
            case "◢":
                diagonal = x + y + 1 - magnification
                return "█" if diagonal > 0 else " " if diagonal < 0 else "◢"
            case "◤":
                diagonal = x + y + 1 - magnification
                return "█" if diagonal < 0 else " " if diagonal > 0 else "◤"
            case "╱":
                diagonal = x + y + 1 - magnification
                return "╱" if diagonal == 0 else " "
            case "╲":
                diagonal = x - y
                return "╲" if diagonal == 0 else " "
            case "╳":
                diagonal_1 = x + y + 1 - magnification
                diagonal_2 = x - y
                return "╲" if diagonal_2 == 0 else "╱" if diagonal_1 == 0 else " "
            case "/":
                diagonal = x + y + 1 - magnification
                return "/" if diagonal == 0 else " "
            case "\\":
                diagonal = x - y
                return "\\" if diagonal == 0 else " "
            # Fractional blocks
            # These are at the end because `in` may be slow.
            # Note: the order of the gradient strings is chosen so that
            # the dividing line is at the top/left at index 0.
            case ch if ch in "█▇▆▅▄▃▂▁":
                gradient = "█▇▆▅▄▃▂▁ "
                index = gradient.index(ch)
                threshold_y = int(index / 8 * magnification)
                if y == threshold_y:
                    # Within the threshold cell, which is at y here,
                    # use one of the fractional characters.
                    # If you look at a 3/8ths character, to scale it up 2x,
                    # you need a 6/8ths character. It simply scales with the magnification.
                    # If you look at a 6/8ths character, to scale it up 2x,
                    # you need a full block and a 4/8ths character, 4/8ths being the threshold cell here,
                    # so it needs to wrap around, taking the remainder.
                    return gradient[index * magnification % 8]
                elif y > threshold_y:
                    return "█"
                else:
                    return " "
            case ch if ch in "▏▎▍▌▋▊▉█":
                gradient = " ▏▎▍▌▋▊▉█"
                index = gradient.index(ch)
                threshold_x = int(index / 8 * magnification)
                if x == threshold_x:
                    return gradient[index * magnification % 8]
                elif x < threshold_x:
                    return "█"
                else:
                    return " "
            case ch if ch in "▔🮂🮃▀🮄🮅🮆█":
                gradient = " ▔🮂🮃▀🮄🮅🮆█"
                index = gradient.index(ch)
                threshold_y = int(index / 8 * magnification)
                if y == threshold_y:
                    return gradient[index * magnification % 8]
                elif y < threshold_y:
                    return "█"
                else:
                    return " "
            case ch if ch in "█🮋🮊🮉▐🮈🮇▕":
                gradient = "█🮋🮊🮉▐🮈🮇▕ "
                index = gradient.index(ch)
                threshold_x = int(index / 8 * magnification)
                if x == threshold_x:
                    return gradient[index * magnification % 8]
                elif x > threshold_x:
                    return "█"
                else:
                    return " "
            case _: pass
        # Fall back to showing the character in a single cell, approximately centered.
        if x == magnification // 2 and y == magnification // 2:
            return ch
        else:
            return " "

