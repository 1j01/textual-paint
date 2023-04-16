from textual import events
from textual.message import Message
from textual.app import ComposeResult
from textual.containers import Container
from textual.geometry import Offset, Region, Size
from textual.reactive import var, reactive
from textual.widgets import Button, Static

class WindowTitleBar(Container):
    """A title bar widget."""

    title = var([])

    def __init__(self, title: str = "", **kwargs) -> None:
        """Initialize a title bar."""
        super().__init__(**kwargs)
        self.add_class("window_title_bar")
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
        self.add_class("window")
        self.mouse_at_drag_start = None
        self.offset_at_drag_start = None
        self.title_bar = WindowTitleBar(title=title)
        self.content = Container(classes="window_content")
        # must be after title_bar is defined
        self.title = title

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.mount(self.title_bar)
        self.mount(self.content)
        # Fix for incorrect layout that would only resolve on mouse over
        # (I peaked into mouse over handling and it calls update_styles.)
        # This can still briefly show the incorrect layout, since it relies on a timer.
        self.set_timer(0.01, lambda: self.app.update_styles(self))

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
            close_request = self.CloseRequest()
            self.post_message(close_request)
            if not close_request.prevent_close:
                self.close()
    
    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Called when the user presses the mouse button."""
        # detect if the mouse is over the title bar,
        # and not window content or title bar buttons
        widget, _ = self.screen.get_widget_at(*event.screen_offset)
        if widget not in [self.title_bar, self.title_bar.query_one(".window_title")]:
            return

        if event.button != 1:
            return
        self.mouse_at_drag_start = event.screen_offset
        self.offset_at_drag_start = Offset(self.styles.offset.x.value, self.styles.offset.y.value)
        self.capture_mouse()

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

    def close(self) -> None:
        self.remove()
        self.post_message(self.Closed())


class DialogWindow(Window):
    """A window that can be submitted like a form."""

    def __init__(self, *children, on_submit, **kwargs) -> None:
        """Initialize a dialog window."""
        super().__init__(*children, **kwargs)
        self.add_class("dialog_window")
        self.on_submit = on_submit

    def on_key(self, event: events.Key) -> None:
        """Called when a key is pressed."""
        # TODO: submit with enter, but not if a button has focus
        # if event.key == "enter":
        #     self.on_submit()
        if event.key == "escape":
            self.close()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        if event.button.has_class("dialog_window_submit"):
            self.on_submit()
        elif event.button.has_class("dialog_window_cancel"):
            self.close()
