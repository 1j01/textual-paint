from typing import Any, Callable
from typing_extensions import Self

from textual import events, on
from textual.dom import DOMNode, NoScreen
from textual.message import Message
from textual.app import ComposeResult
from textual.containers import Container
from textual.geometry import Offset
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import Button, Static, DataTable
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches

from .localization.i18n import get as _

class WindowTitleBar(Container):
    """A title bar widget."""

    title = var("")

    def __init__(
        self,
        title: str = "",
        allow_maximize: bool = False,
        allow_minimize: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize a title bar."""
        super().__init__(**kwargs)
        self.title = title
        self.allow_maximize = allow_maximize
        self.allow_minimize = allow_minimize

    def compose(self) -> ComposeResult:
        """Add our widgets."""
        yield Static(self.title, classes="window_title")
        if self.allow_minimize:
            yield Button("🗕", classes="window_minimize")
        if self.allow_maximize:
            yield Button("🗖", classes="window_maximize")
            restore_button = Button("🗗", classes="window_restore")
            restore_button.display = False
            yield restore_button
        yield Button("🗙", classes="window_close")

id_counter = 0
class Window(Container):
    """A draggable window widget."""

    class CloseRequest(Message):
        """Message when the user clicks the close button. Can be prevented."""

        def __init__(self, **kwargs: Any) -> None:
            """Initialize a close request."""
            super().__init__(**kwargs)
            self.prevent_close = False

    class Closed(Message):
        """Message when the window is really closed."""

    title = var("")

    BINDINGS = [
        # Binding("tab", "focus_next", "Focus Next", show=False),
        # Binding("shift+tab", "focus_previous", "Focus Previous", show=False),
        ("tab", "focus_next", "Focus Next"),
        ("shift+tab", "focus_previous", "Focus Previous"),
        ("right,down", "focus_next_button", "Focus Next Button"),
        ("left,up", "focus_previous_button", "Focus Previous Button"),
    ]

    def __init__(
        self,
        *children: Widget,
        title: str = "",
        allow_maximize: bool = False,
        allow_minimize: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize a window."""
        super().__init__(*children, **kwargs)
        self.mouse_at_drag_start: Offset | None = None
        self.offset_at_drag_start: Offset | None = None
        self.title_bar = WindowTitleBar(title=title, allow_maximize=allow_maximize, allow_minimize=allow_minimize)
        self.content = Container(classes="window_content")
        self.maximized = False
        # must be after title_bar is defined
        self.title = title
        self.can_focus = True
        self.last_focused_descendant: Widget | None = None
        if not self.id:
            # ID is needed for focus cycling
            global id_counter
            self.id = f"window_auto_id_{id_counter}"
            id_counter += 1

    def action_focus_next(self) -> None:
        """Override action to focus the next widget only within the window."""
        self.screen.focus_next(f"#{self.id} .window_content *")

    def action_focus_previous(self) -> None:
        """Override action to focus the previous widget only within the window."""
        self.screen.focus_previous(f"#{self.id} .window_content *")

    def within_buttons(self, widget: Widget | None) -> bool:
        """Returns True if widget exists and is within .buttons."""
        if not widget:
            return False
        node: DOMNode | None = widget
        while node:
            if node.has_class("buttons"):
                return True
            node = node.parent
        return False

    def within_content(self, widget: Widget | None) -> bool:
        """Returns True if widget exists and is within this window's content container."""
        # TODO: DRY using a function like JS's closest()
        if not widget:
            return False
        node = widget
        while node:
            if node is self.content:
                return True
            node = node.parent
        return False

    def action_focus_next_button(self) -> None:
        """Action to focus the next button within .buttons IF a button is focused within .buttons."""
        if self.within_buttons(self.screen.focused):
            self.screen.focus_next(f"#{self.id} .buttons *")

    def action_focus_previous_button(self) -> None:
        """Action to focus the previous button within .buttons IF a button is focused within .buttons."""
        if self.within_buttons(self.screen.focused):
            self.screen.focus_previous(f"#{self.id} .buttons *")

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.mount(self.title_bar)
        self.mount(self.content)
        with self.app.batch_update():
            # Set focus. (In the future, some windows will not want default focus...)
            self.focus()
            # Fix for incorrect layout that would only resolve on mouse over
            # (I peaked into mouse over handling and it calls update_styles.)
            self.app.update_styles(self)
        self.call_after_refresh(self.constrain_to_screen)

    def constrain_to_screen(self) -> None:
        """Constrain window to screen, so that the title bar is always visible.
        
        This method must take into account the fact that the window is centered with `align: center middle;`
        TODO: Call this on screen resize.
        """
        # print(self.region, self.virtual_region)
        x, y = map(lambda scalar: int(scalar.value), self.styles.offset)
        h_margin = 4
        border_h = self.outer_size.height - self.size.height - 1 # bottom border isn't applicable, subtract 1
        bottom_margin = self.title_bar.outer_size.height + border_h
        try:
            screen = self.screen  # type: ignore
        except NoScreen:
            # I got when hitting Ctrl+O rapidly.
            # Any old Open dialog is closed when opening the Open dialog.
            # If a dialog is closed immediately as its opening,
            # the initial `constrain_to_screen` happens after the widget is unmounted.
            return
        screen_width, screen_height = screen.region.size
        # Note: You should be able to drag the window left and right off screen most of the way.
        # Note: Order of constraints CAN matter. It's better for the window to be pushed down after being pushed up,
        # to ensure that the title bar is visible, however this may not matter since it's not pushed up unless
        # significantly off-screen at the bottom.
        # Note: self.region doesn't get updated immediately, so we need to track the modifications
        # to the offset in order for the constraints to interact properly.
        r = self.region
        if r.x < -r.width + h_margin:
            dx = -(r.x + r.width - h_margin)
            x += dx
            r = r.translate(Offset(dx, 0))
        if r.x > screen_width - h_margin:
            dx = -(r.x - screen_width + h_margin)
            x += dx
            r = r.translate(Offset(dx, 0))
        if r.y > screen_height - bottom_margin:
            dy = -(r.y - screen_height + bottom_margin)
            y += dy
            r = r.translate(Offset(0, dy))
        if r.y < 0:
            dy = -(r.y)
            y += dy
            r = r.translate(Offset(0, dy))
        self.styles.offset = (x, y)

    def on_focus(self, event: events.Focus) -> None:
        """Called when the window is focused."""
        self.focus()
    
    def focus(self, scroll_visible: bool = True) -> Self:
        """Focus the window. Note that scroll_visible may scroll a descendant into view, but never the window into view within the screen."""
        # Focus last focused widget if re-focusing
        if self.last_focused_descendant:
            if self.within_content(self.last_focused_descendant):
                self.last_focused_descendant.focus(scroll_visible=scroll_visible)
                return self
        # Otherwise the autofocus control, or submit button, or first focusable control
        for query in [".autofocus", ".submit", "Widget"]:
            controls = self.content.query(query)
            if controls:
                for control in controls:
                    if control.focusable:
                        control.focus(scroll_visible=scroll_visible)
                        return self
        # Fall back to focusing the window itself
        # Don't use scroll_visible parameter, because you probably don't want to scroll the screen to the window.
        super().focus()
        return self

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        """Called when a descendant is focused."""
        self.bring_to_front()
        self.last_focused_descendant = self.app.focused

    def bring_to_front(self) -> None:
        """Reorder the window to be last so it renders on top."""
        if not self.parent:
            # Can happen when saying Yes to "Save changes to X?" prompt during Save As
            # I got this using automation (so it might need to be fast to happen):
            # textual run --dev "src.textual_paint.paint --language en --clear-screen --inspect-layout --restart-on-changes question_icon.ans" --press ctrl+shift+s,.,_,r,i,c,h,_,c,o,n,s,o,l,e,_,m,a,r,k,u,p,enter,enter
            return
        assert isinstance(self.parent, Widget), "Window parent should be a Widget, but got: " + repr(self.parent)
        if self.parent.children[-1] is not self:
            self.parent.move_child(self, after=self.parent.children[-1])

    # def compose(self) -> ComposeResult:
    #     """Add our widgets."""
    #     self.title_bar = yield WindowTitleBar(title=self.title)
    #     self.content = yield Container(classes="window_content")

    # def compose_add_child(self, widget):
    #     """When using the context manager compose syntax, we want to attach nodes to the content container."""
    #     self.content.mount(widget)

    def watch_title(self, new_title: str) -> None:
        """Called when title is changed."""
        self.title_bar.title = new_title

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is clicked or activated with the keyboard."""

        if event.button.has_class("window_close"):
            self.request_close()
        elif event.button.has_class("window_minimize"):
            minimizing = self.content.display
            # Freeze the width, since auto width from the content won't apply.
            self.styles.width = self.outer_size.width
            # Offset by half the height of the content, because the window has a center anchor.
            border_h = self.outer_size.height - self.size.height
            if minimizing:
                y_offset = -self.content.outer_size.height / 2 - border_h
            else:
                y_offset = self._original_content_height / 2 + border_h
            self.styles.offset = (
                int(self.styles.offset.x.value),
                int(self.styles.offset.y.value + y_offset),
            )
            if minimizing:
                self._original_content_height = self.content.outer_size.height
                self._original_window_height_for_minimize = self.styles.height
            # Toggle the display of the content.
            self.content.display = not self.content.display
            # minimal_height = "auto" # doesn't work
            minimal_height = self.title_bar.outer_size.height + border_h
            self.styles.height = minimal_height if minimizing else self._original_window_height_for_minimize
            # Disable the maximize button when minimized.
            # TODO: Handle minimize for maximized windows, and maximize for minimized windows.
            try:
                self.title_bar.query_one(".window_maximize").disabled = minimizing
            except NoMatches:
                pass
        elif event.button.has_class("window_maximize"):
            self.title_bar.query_one(".window_maximize").display = False
            self.title_bar.query_one(".window_restore").display = True
            self._original_offset = self.styles.offset
            self._original_width = self.styles.width
            self._original_height = self.styles.height
            self.styles.offset = (0, 0)
            self.styles.width = "100%"
            self.styles.height = "100%"
            self.maximized = True
            # Disable the minimize button when maximized.
            try:
                self.title_bar.query_one(".window_minimize").disabled = True
            except NoMatches:
                pass
        elif event.button.has_class("window_restore"):
            self.title_bar.query_one(".window_maximize").display = True
            self.title_bar.query_one(".window_restore").display = False
            self.styles.offset = self._original_offset
            self.styles.width = self._original_width
            self.styles.height = self._original_height
            self.maximized = False
            # Enable the minimize button when restored.
            try:
                self.title_bar.query_one(".window_minimize").disabled = False
            except NoMatches:
                pass

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Called when the user presses the mouse button."""

        self.bring_to_front()
        self.focus()

        # detect if the mouse is over the title bar,
        # and not window content or title bar buttons
        if not self.parent:
            # I got NoScreen error accessing self.screen once while closing a window,
            # so I added this check.
            return
        widget, _ = self.screen.get_widget_at(*event.screen_offset)
        if widget not in [self.title_bar, self.title_bar.query_one(".window_title")]:
            return

        if event.button != 1:
            return

        if self.maximized:
            return

        self.mouse_at_drag_start = event.screen_offset
        self.offset_at_drag_start = Offset(
            int(self.styles.offset.x.value),
            int(self.styles.offset.y.value),
        )
        self.capture_mouse()
        """
        Work around a bug in textual where the MouseUp event
        is not sent to this widget if another widget gets focus,
        and thus, release_mouse() is not called,
        and you can never release the drag or click anything else.

        An excerpt from Screen._forward_event:

                if isinstance(event, events.MouseUp) and widget.focusable:
                    if self.focused is not widget:
                        self.set_focus(widget)
                        event.stop()
                        return
                event.style = self.get_style_at(event.screen_x, event.screen_y)
                if widget is self:
                    event._set_forwarded()
                    self.post_message(event)
                else:
                    widget._forward_event(event._apply_offset(-region.x, -region.y))

        Note the return statement.
        I don't know what this special case is for,
        but for this work around, I can make widget.focusable False,
        so that the special case doesn't apply.
        (`focusable` is a getter that uses can_focus and checks ancestors are enabled)
        """
        self.can_focus = False

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Called when the user moves the mouse."""
        if (
            self.mouse_at_drag_start is not None
            and self.offset_at_drag_start is not None
        ):
            self.styles.offset = (
                self.offset_at_drag_start.x + event.screen_x - self.mouse_at_drag_start.x,
                self.offset_at_drag_start.y + event.screen_y - self.mouse_at_drag_start.y,
            )

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Called when the user releases the mouse button."""
        self.mouse_at_drag_start = None
        self.offset_at_drag_start = None
        self.release_mouse()
        self.constrain_to_screen()
        # Part of the workaround for the bug mentioned in on_mouse_down
        self.can_focus = True

    def close(self) -> None:
        """Force close the window."""
        self.remove()
        self.post_message(self.Closed())

    def request_close(self) -> None:
        """Request to close the window."""
        close_request = self.CloseRequest()
        self.post_message(close_request)
        if not close_request.prevent_close:
            self.close()


class DialogWindow(Window):
    """A window that can be submitted like a form."""

    def __init__(
        self, *children: Widget, handle_button: Callable[[Button], None], **kwargs: Any
    ) -> None:
        """Initialize a dialog window."""
        super().__init__(*children, **kwargs)
        self.handle_button = handle_button

    def on_key(self, event: events.Key) -> None:
        """Called when a key is pressed."""
        # submit with enter, but not if a button has focus
        # (not even if it's a submit button, because that would double submit)
        # TODO: Use on_input_submitted instead
        if event.key == "enter" and self.app.focused not in self.query("Button").nodes:
            try:
                submit_button = self.query_one(".submit", Button)
            except NoMatches:
                return
            event.stop()
            self.handle_button(submit_button)
        elif event.key == "escape":
            event.stop()
            # Like the title bar close button,
            # this doesn't call handle_button...
            # If you want to know if the dialog is canceled by closing,
            # you can listen for the CloseRequest/Closed messages.
            self.request_close()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        # Make sure the button is in the window content
        if event.button in self.content.query("Button").nodes:
            self.handle_button(event.button)

    # def on_input_submitted(self, event: Input.Submitted) -> None:
    #     """Called when a the enter key is pressed in an Input."""


class CharacterSelectorDialogWindow(DialogWindow):
    """A dialog window that lets the user select a character."""

    # class CharacterSelected(Message):
    #     """Sent when a character is selected."""
    #     def __init__(self, character: str) -> None:
    #         """Initialize the message."""
    #         self.character = character

    # NUL at the beginning (0), SP in the middle (32), and NBSP at the end (255)
    # are all treated as space when selected. Null can cause the screen to malfunction
    # if it's inserted into the document.
    # spell-checker: disable
    code_page_437 = "\0☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼ !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~⌂ÇüéâäàåçêëèïîìÄÅÉæÆôöòûùÿÖÜ¢£¥₧ƒáíóúñÑªº¿⌐¬½¼¡«»░▒▓│┤╡╢╖╕╣║╗╝╜╛┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀αßΓπΣσµτΦΘΩδ∞φε∩≡±≥≤⌠⌡÷≈°∙·√ⁿ²■ "
    # spell-checker: enable
    char_list = [char for char in code_page_437]

    def __init__(
        self,
        *children: Widget,
        selected_character: str | None,
        handle_selected_character: Callable[[str], None],
        **kwargs: Any,
    ) -> None:
        """Initialize the dialog window."""
        super().__init__(handle_button=self.handle_button, *children, **kwargs)
        self._selected_character: str | None = selected_character
        self.handle_selected_character = handle_selected_character

    def handle_button(self, button: Button) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        if button.has_class("cancel"):
            self.request_close()
        else:
            if self._selected_character is None:
                # Probably shouldn't happen
                return
            # self.post_message(self.CharacterSelected(self._selected_character))
            # self.close()
            self.handle_selected_character(self._selected_character)

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        """Called when a cell is highlighted."""
        # assert isinstance(event.value, str), "DataTable should only contain strings, but got: " + repr(event.value)
        self._selected_character = (
            event.value if isinstance(event.value, str) and event.value != "\0" else " "
        )

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        data_table: DataTable[str] = DataTable()
        column_count = 16
        data_table.add_columns(*([" "] * column_count))
        data_table.show_header = False
        for i in range(0, len(self.char_list), column_count):
            data_table.add_row(*self.char_list[i : i + column_count])
        self.content.mount(data_table)
        self.content.mount(Button(_("OK"), classes="ok submit"))
        self.content.mount(Button(_("Cancel"), classes="cancel"))

# ASCII line art version:
# get_warning_icon = lambda: Static("""[#ffff00]
#     _
#    / \\
#   / | \\
#  /  .  \\
# /_______\\
# [/]""", classes="warning_icon message_box_icon")
# Unicode solid version 1:
# get_warning_icon = lambda: Static("""[#ffff00 on #000000]
#     _
#    ◢█◣
#   ◢[#000000 on #ffff00] ▼ [/]◣
#  ◢[#000000 on #ffff00]  ●  [/]◣
# ◢███████◣
# [/]""", classes="warning_icon message_box_icon")
# Unicode line art version (' might be a better than ╰/╯):
# get_warning_icon = lambda: Static("""[#ffff00]
#     _
#    ╱ ╲
#   ╱ │ ╲
#  ╱  .  ╲
# ╰───────╯
# """, classes="warning_icon message_box_icon")
# Unicode solid version 2:
# get_warning_icon = lambda: Static("""[#ffff00 on #000000]
#      🭯
#     🭅[#000000 on #ffff00]🭯[/]🭐
#    🭅[#000000 on #ffff00] ▼ [/]🭐
#   🭅[#000000 on #ffff00]  ●  [/]🭐
#  🭅███████🭐
# [/]""", classes="warning_icon message_box_icon")
# Unicode solid version 3, now with a border:
# VS Code's terminal seems unsure of the width of these characters (like it's rendering 2 wide but advancing by 1), and has gaps/seams.
# Ubuntu's terminal looks better, and the graphics have less gaps, but the overall shape is worse.
# I guess a lot of this comes down to the font as well.
# get_warning_icon = lambda: Static("""
#     [#000000]🭋[#ffff00 on #000000]🭯[/]🭀[/]
#    [#000000]🭋[#ffff00 on #000000]🭅█🭐[/]🭀[/]
#   [#000000]🭋[#ffff00 on #000000]🭅[#000000 on #ffff00] ▼ [/]🭐[/]🭀[/]
#  [#000000]🭋[#ffff00 on #000000]🭅[#000000 on #ffff00]  ●  [/]🭐[/]🭀[/]
# [#000000]🭋[#ffff00 on #000000]🭅███████🭐[/]🭀[/]
# [#000000]🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃[/]
# """, classes="warning_icon message_box_icon")
# Unicode solid version 4:
# This now looks great in Ubuntu's terminal.
# In VS Code's terminal, all the gaps make it look like it's under frosted glass,
# but it's acceptable. Alternatively, you may see it as looking "spiky",
# which is sensible for a warning icon, if not particularly attractive.
# get_warning_icon = lambda: Static("""
#     [#000000]◢[#ffff00 on #000000]🭯[/]◣[/]
#    [#000000]◢[#ffff00 on #000000]◢█◣[/]◣[/]
#   [#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00] ▼ [/]◣[/]◣[/]
#  [#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00]  ●  [/]◣[/]◣[/]
# [#000000]◢[#ffff00 on #000000]◢███████◣[/]◣[/]
# [#000000]🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃[/]
# """, classes="warning_icon message_box_icon")
# Unicode solid version 5, rounder exclamation mark:
# get_warning_icon = lambda: Static("""
#     [#000000]◢[#ffff00 on #000000]🭯[/]◣[/]
#    [#000000]◢[#ffff00 on #000000]◢█◣[/]◣[/]
#   [#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00] ⬮ [/]◣[/]◣[/]
#  [#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00]  •  [/]◣[/]◣[/]
# [#000000]◢[#ffff00 on #000000]◢███████◣[/]◣[/]
# [#000000]🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃[/]
# """, classes="warning_icon message_box_icon")
# Unicode solid version 6, smaller overall:
get_warning_icon = lambda: Static("""
   [#000000]◢[#ffff00 on #000000]🭯[/]◣[/]
  [#000000]◢[#ffff00 on #000000]◢█◣[/]◣[/]
 [#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00] ⬮ [/]◣[/]◣[/]
[#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00]  •  [/]◣[/]◣[/]
[#000000]🮃🮃🮃🮃🮃🮃🮃🮃🮃[/]
""", classes="warning_icon message_box_icon")

# question_icon_ansi = ""
# def get_question_icon() -> Static:
#     global question_icon_ansi
#     if not question_icon_ansi:
#         with open("question_icon.ans", "r", encoding="utf-8") as f:
#             question_icon_ansi = f.read()
#     return Static(question_icon_ansi, classes="question_icon message_box_icon")

# I added a little stopgap to save as Rich console markup by using file extension "._RICH_CONSOLE_MARKUP".
# It's very messy markup because it's generated from the ANSI art.
question_icon_console_markup = """
[rgb(255,255,255) on rgb(128,128,128)]▂[rgb(255,255,255) on rgb(128,128,128)][/rgb(255,255,255) on rgb(128,128,128)]▆[rgb(0,0,0) on rgb(255,255,255)][/rgb(255,255,255) on rgb(128,128,128)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(255,255,255) on rgb(128,128,128)][/rgb(0,0,0) on rgb(255,255,255)]▆[rgb(255,255,255) on rgb(128,128,128)][/rgb(255,255,255) on rgb(128,128,128)]▂[rgb(0,0,0) on rgb(128,128,128)][/rgb(255,255,255) on rgb(128,128,128)] [/rgb(0,0,0) on rgb(128,128,128)]
[rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,255) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]𝟔[rgb(0,0,255) on rgb(255,255,255)][/rgb(0,0,255) on rgb(255,255,255)]❩[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,255) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(255,255,255)]▌[/rgb(0,0,0) on rgb(128,128,128)]
[rgb(255,255,255) on rgb(128,128,128)]🮂[rgb(0,0,0) on rgb(255,255,255)][/rgb(255,255,255) on rgb(128,128,128)]▂[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,255) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]•[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,255) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]▁[rgb(255,255,255) on rgb(0,0,0)][/rgb(0,0,0) on rgb(255,255,255)]🮂[rgb(0,0,0) on rgb(128,128,128)][/rgb(255,255,255) on rgb(0,0,0)]▘[/rgb(0,0,0) on rgb(128,128,128)]
[rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]🮂[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]🮂[rgb(255,255,255) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]◥[rgb(0,0,0) on rgb(128,128,128)][/rgb(255,255,255) on rgb(128,128,128)]▛[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]🮂[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [/rgb(0,0,0) on rgb(128,128,128)]
"""
# make background transparent
question_icon_console_markup = question_icon_console_markup.replace(" on rgb(128,128,128)", "")
# class QuestionIcon(Static):
#     """A question mark icon."""
#
#     def __init__(self) -> None:
#         """Initialize the icon."""
#         super().__init__("", classes="question_icon message_box_icon")
#         # This assertion fails.
#         # > type(self.app)
#         # <class '<run_path>.PaintApp'>
#         # > type(PaintApp())
#         # <class 'paint.PaintApp'>
#         # from paint import PaintApp
#         # assert isinstance(self.app, PaintApp), "QuestionIcon should be used in PaintApp, but got: " + repr(self.app)
#         self.watch(self.app, "dark", self._on_dark_changed, init=False)
#         self._on_dark_changed(False, self.app.dark)
#
#     def _on_dark_changed(self, old_value: bool, dark: bool) -> None:
#         # tweak colors according to the theme
#         if dark:
#             # Never happens?
#             self.update(question_icon_console_markup.replace("rgb(0,0,0)", "rgb(255,0,255)"))
#         else:
#             self.update(question_icon_console_markup.replace("rgb(0,0,0)", "rgb(128,128,128)"))
#
# def get_question_icon() -> QuestionIcon:
#     return QuestionIcon()


# also the shadow is normally gray, I just drew it black because I was using gray as the background
question_icon_console_markup = question_icon_console_markup.replace("rgb(0,0,0)", "rgb(128,128,128)")
# Underline "❩" to make it look like the question mark has a serif. Looks bad because it's a wide character.
# question_icon_console_markup = question_icon_console_markup.replace("❩", "[u]❩[/u]")
get_question_icon = lambda: Static(question_icon_console_markup, classes="question_icon message_box_icon")

# NOTE: I had to manually replace "\" with "\\\\" in the markup below.
# One level of escaping because this is a string literal, and another level because
# Text.markup fails to escape backslashes:
# https://github.com/Textualize/rich/issues/2993
# ...although now I've replaced it with 🙽 in the text art.
paint_icon_console_markup = """
[rgb(0,0,0) on rgb(255,0,255)]⡀[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,0,255)].[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)],[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(192,192,192) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]🮈[rgb(255,255,255) on rgb(255,0,255)][/rgb(192,192,192) on rgb(255,255,255)]◣[/rgb(255,255,255) on rgb(255,0,255)]
[rgb(0,0,255) on rgb(255,0,255)]🙽[rgb(255,0,0) on rgb(255,255,255)][/rgb(0,0,255) on rgb(255,0,255)]┃[rgb(255,255,0) on rgb(255,255,255)][/rgb(255,0,0) on rgb(255,255,255)]🙼[rgb(0,0,0) on rgb(255,255,255)][/rgb(255,255,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(192,192,192) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]░[/rgb(192,192,192) on rgb(255,255,255)]
[rgb(255,255,255) on rgb(255,0,255)]🮉[rgb(128,128,128) on #e3e3e3][/rgb(255,255,255) on rgb(255,0,255)]_[rgb(128,128,128) on #e3e3e3][/rgb(128,128,128) on #e3e3e3]_[#c6c6c6 on rgb(128,128,128)][/rgb(128,128,128) on #e3e3e3]▋[rgb(255,255,255) on #e3e3e3][/#c6c6c6 on rgb(128,128,128)]🮉[rgb(0,0,0) on rgb(255,255,255)][/rgb(255,255,255) on #e3e3e3] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [/rgb(0,0,0) on rgb(255,255,255)]
[rgb(192,192,192) on rgb(255,0,255)]🮈[rgb(128,128,128) on #e3e3e3][/rgb(192,192,192) on rgb(255,0,255)]_[rgb(128,128,128) on #e3e3e3][/rgb(128,128,128) on #e3e3e3]_[rgb(128,128,128) on #e3e3e3][/rgb(128,128,128) on #e3e3e3]▍[rgb(0,0,0) on rgb(255,255,255)][/rgb(128,128,128) on #e3e3e3] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [/rgb(0,0,0) on rgb(255,255,255)]
"""
# make fuchsia transparent
paint_icon_console_markup = paint_icon_console_markup.replace(" on rgb(255,0,255)", "")
get_paint_icon = lambda: Static(paint_icon_console_markup, classes="paint_icon message_box_icon")

class MessageBox(DialogWindow):
    """A simple dialog window that displays a message, a group of buttons, and an optional icon."""

    def __init__(
        self,
        *children: Widget,
        message: Widget | str,
        button_types: str = "ok",
        icon_widget: Widget | None, # can be None but must be specified, because I'm more likely to forget to pass it than to want no icon
        handle_button: Callable[[Button], None],
        error: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the message box."""
        super().__init__(*children, handle_button=handle_button, **kwargs)
        self.message_widget: Widget
        if isinstance(message, str):
            self.message_widget = Static(message, markup=False)
        else:
            self.message_widget = message
        if error:
            # expandable error details
            import traceback
            details = "\n".join(traceback.format_exception(error))
            self.details_widget = Container(Static(details, markup=False, classes="details"))
            self.details_widget.display = False
            self.details_widget.styles.overflow_x = "auto"
            self.details_widget.styles.overflow_y = "auto"
            self.details_button = Button(_("Show Details"), classes="details_button")
            self.message_widget = Vertical(
                self.message_widget,
                self.details_button,
                self.details_widget,
            )
            self.message_widget.styles.height = "auto"
            self.message_widget.styles.max_height = "35"
            self.details_widget.styles.height = "20"

        if not icon_widget:
            icon_widget = Static("")
        self.icon_widget = icon_widget
        self.button_types = button_types

    @on(Button.Pressed, ".details_button")
    def toggle_details(self, event: Button.Pressed) -> None:
        """Toggle the visibility of the error details."""
        self.details_widget.display = not self.details_widget.display
        button_text = _("Hide Details") if self.details_widget.display else _("Show Details")
        self.details_button.update(button_text)

    def on_mount(self):
        """Called when the window is mounted."""

        if self.button_types == "ok":
            buttons = [Button(_("OK"), classes="ok submit", variant="primary")]
        elif self.button_types == "yes/no":
            buttons = [
                Button(_("Yes"), classes="yes submit"),  # , variant="primary"),
                Button(_("No"), classes="no"),
            ]
        elif self.button_types == "yes/no/cancel":
            buttons = [
                Button(_("Yes"), classes="yes submit", variant="primary"),
                Button(_("No"), classes="no"),
                Button(_("Cancel"), classes="cancel"),
            ]
        else:
            raise ValueError("Invalid button_types: " + repr(self.button_types))

        self.content.mount(
            Horizontal(
                self.icon_widget,
                Vertical(
                    self.message_widget,
                    # Window class provides arrow key navigation within .buttons
                    Horizontal(*buttons, classes="buttons"),
                    classes="main_content",
                ),
            )
        )
