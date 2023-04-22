from typing import Union, Optional, Callable
from textual import events
from textual.message import Message
from textual.app import ComposeResult
from textual.containers import Container
from textual.geometry import Offset, Region, Size
from textual.reactive import var, reactive
from textual.widget import Widget
from textual.widgets import Button, Static
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from localization.i18n import get as _

class WindowTitleBar(Container):
    """A title bar widget."""

    title = var("")

    def __init__(self, title: str = "", **kwargs) -> None:
        """Initialize a title bar."""
        super().__init__(**kwargs)
        self.title = title

    def compose(self) -> ComposeResult:
        """Add our widgets."""
        yield Static(self.title, classes="window_title")
        yield Button("🗙", classes="window_close")
        # yield Button("🗕", classes="window_minimize")
        # yield Button("🗖", classes="window_maximize")
        # 🗗 for restore

class Window(Container):
    """A draggable window widget."""

    class CloseRequest(Message):
        """Message when the user clicks the close button. Can be prevented."""

        def __init__(self, **kwargs) -> None:
            """Initialize a close request."""
            super().__init__(**kwargs)
            self.prevent_close = False

    class Closed(Message):
        """Message when the window is really closed."""

    title = var([])

    def __init__(self, *children, title: str = "", **kwargs) -> None:
        """Initialize a window."""
        super().__init__(*children, **kwargs)
        self.mouse_at_drag_start = None
        self.offset_at_drag_start = None
        self.title_bar = WindowTitleBar(title=title)
        self.content = Container(classes="window_content")
        # must be after title_bar is defined
        self.title = title
        self.can_focus = True

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.mount(self.title_bar)
        self.mount(self.content)
        # Set focus. (In the future, some windows will not want default focus...)
        self.focus()
        # Fix for incorrect layout that would only resolve on mouse over
        # (I peaked into mouse over handling and it calls update_styles.)
        # This can still briefly show the incorrect layout, since it relies on a timer.
        self.set_timer(0.01, lambda: self.app.update_styles(self))
    
    def on_focus(self, event: events.Focus) -> None:
        """Called when the window is focused."""
        # TODO: focus last focused widget if re-focusing
        controls = self.content.query(".submit, Input, Button")
        if controls:
            controls[0].focus()

    # def compose(self) -> ComposeResult:
    #     """Add our widgets."""
    #     self.title_bar = yield WindowTitleBar(title=self.title)
    #     self.content = yield Container(classes="window_content")

    # def compose_add_child(self, widget):
    #     """When using the context manager compose syntax, we want to attach nodes to the content container."""
    #     self.content.mount(widget)

    def watch_title(self, old_title, new_title: str) -> None:
        """Called when title is changed."""
        self.title_bar.title = new_title

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is clicked or activated with the keyboard."""

        if event.button.has_class("window_close"):
            self.request_close()
    
    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Called when the user presses the mouse button."""
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
        self.mouse_at_drag_start = event.screen_offset
        self.offset_at_drag_start = Offset(int(self.styles.offset.x.value), int(self.styles.offset.y.value))
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
        if self.mouse_at_drag_start:
            self.styles.offset = (
                self.offset_at_drag_start.x + event.screen_x - self.mouse_at_drag_start.x,
                self.offset_at_drag_start.y + event.screen_y - self.mouse_at_drag_start.y,
            )

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Called when the user releases the mouse button."""
        self.mouse_at_drag_start = None
        self.offset_at_drag_start = None
        self.release_mouse()
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

    def __init__(self, *children, handle_button, **kwargs) -> None:
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
            self.handle_button(submit_button)
        elif event.key == "escape":
            # Like the title bar close button,
            # this doesn't call handle_button...
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

    # TODO: fact check this string
    # spell-checker: disable
    code_page_437 = "☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼ !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~⌂ÇüéâäàåçêëèïîìÄÅÉæÆôöòûùÿÖÜ¢£¥₧ƒáíóúñÑªº¿⌐¬½¼¡«»░▒▓│┤╡╢╖╕╣║╗╝╜╛┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌█▄▀▌▐▀αßΓπΣσµτΦΘΩδ∞φε∩≡±≥≤⌠⌡÷≈°∙·√ⁿ²■ "
    # spell-checker: enable
    char_list = [char for char in code_page_437]

    # char_list = ["A", "b", "c"] * 4

    def __init__(self, *args, selected_character: str|None, handle_selected_character: Callable, **kwargs) -> None:
        """Initialize the dialog window."""
        super().__init__(handle_button=self.handle_button, *args, **kwargs)
        self._char_to_highlight = selected_character
        self.handle_selected_character = handle_selected_character
    
    def handle_button(self, button: Button) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        if button.id == "cancel":
            self.request_close()
        else:
            # self.post_message(self.CharacterSelected(button.char))
            # self.close()
            self.handle_selected_character(button.char)

    # def compose(self) -> ComposeResult:
    #     """Add our buttons."""
    #     with Container(classes="character_buttons"):
    #         for char in self.char_list:
    #             button = Button(char, variant="primary" if char is self._char_to_highlight else "default")
    #             button.char = char
    #             # if char is self._char_to_highlight:
    #             #     button.add_class("selected")
    #             yield button
    #     yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        container = Container(classes="character_buttons")
        for char in self.char_list:
            button = Button(char, variant="primary" if char is self._char_to_highlight else "default")
            button.char = char
            # if char is self._char_to_highlight:
            #     button.add_class("selected")
            container.mount(button)
        self.content.mount(container)
        self.content.mount(Button("Cancel", classes="cancel"))

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
get_warning_icon = lambda: Static("""
    [#000000]🭋[#ffff00 on #000000]🭯[/]🭀[/]
   [#000000]🭋[#ffff00 on #000000]🭅█🭐[/]🭀[/]
  [#000000]🭋[#ffff00 on #000000]🭅[#000000 on #ffff00] ▼ [/]🭐[/]🭀[/]
 [#000000]🭋[#ffff00 on #000000]🭅[#000000 on #ffff00]  ●  [/]🭐[/]🭀[/]
[#000000]🭋[#ffff00 on #000000]🭅███████🭐[/]🭀[/]
[#000000]🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃[/]
""", classes="warning_icon message_box_icon")

class MessageBox(DialogWindow):
    """A simple dialog window that displays a message, a group of buttons, and an optional icon."""
    def __init__(self, *args, message_widget: Union[Widget, str], button_types: str = "ok", icon_widget: Optional[Widget], handle_button: Optional[Callable] = None, **kwargs) -> None:
        """Initialize the message box."""
        super().__init__(*args, handle_button=handle_button, **kwargs)
        if isinstance(message_widget, str):
            message_widget = Static(message_widget, markup=False)
        if not icon_widget:
            icon_widget = Static("")
        self.message_widget = message_widget
        self.icon_widget = icon_widget
        self.button_types = button_types

    def on_mount(self):
        """Called when the window is mounted."""

        if self.button_types == "ok":
            buttons = [Button(_("OK"), classes="ok submit", variant="primary")]
        elif self.button_types == "yes/no":
            buttons = [
                Button(_("Yes"), classes="yes submit"), #, variant="primary"),
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
                    Horizontal(*buttons, classes="buttons"),
                    classes="main_content"
                )
            )
        )
