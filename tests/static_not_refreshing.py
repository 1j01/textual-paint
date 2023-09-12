import uuid
from typing import Any, Callable

from textual.app import App, ComposeResult
from textual.events import Event, Key, MouseMove
from textual.widgets import Static

original_on_event = App.on_event  # type: ignore

class Repro():
    def __init__(self, app_class: Callable[[], App[Any]]) -> None:
        """Initialize the repro.
        
        app_class: A function that returns an App instance.
        """
        self.app_class = app_class

        self.app: App[Any] | None = None
        self.next_after_exit: Callable[[], None] | None = None

        # repro = self
        # async def on_event(self: App[Any], event: Event) -> None:
        #     # Every event seems to be received twice, once with _forwarded set and once without.
        #     # I don't claim to understand the forwarding scheme, but ignoring either
        #     # the forwarded or the un-forwarded events seems workable.
        #     if not event._forwarded:
        #         repro.handle_event(event)
        #     await original_on_event(self, event)
        # self.app_on_event = on_event

    def handle_event(self, event: Event) -> None:
        """Record the mouse position and restart on Ctrl+R."""
        assert self.app is not None, "app should be set when receiving an event from it"
        if isinstance(event, Key):
            if event.key == "ctrl+r":
                self.run()  # restart the app

    def run(self) -> None:
        """Start or restart the app."""
        def startup_and_hook() -> None:
            """Start the app, and hook its events."""
            self.next_after_exit = None  # important to allowing you to exit; don't keep launching the app
            self.app = self.app_class()
            # self.app.on_event = self.app_on_event.__get__(self.app)
            self.app.run()
            # run is blocking, so this will happen after the app exits
            if self.next_after_exit:
                self.next_after_exit()
        if self.app is not None:
            # exit can't be awaited, because it stops the whole event loop (eventually)
            # but we need to wait for the event loop to stop before we can start a new app
            self.next_after_exit = startup_and_hook
            self.app.exit()
        else:
            startup_and_hook()

class ReproApp(App[None]):
    """App shows the mouse position, has instructions and a tooltip."""
    def compose(self) -> ComposeResult:
        yield Static("Move the mouse to show and update the Static on the right.\n\nThen press Ctrl+R to restart, and note how it no longer updates most of the time.\n\n\n\n")
        tipper = Static("[Hover me for a tooltip.]")
        tipper.tooltip = "A tooltip magically causes a repaint when it appears."
        yield tipper
        self.static = Static("This will show the mouse position...")
        yield self.static
        self.static.styles.dock = "right"
        self.static.styles.width = 46
        self.static.styles.height = "100%"
        # self.set_interval(0.1, self.update_static)
    
    def on_mouse_move(self, event: MouseMove) -> None:
        """Show the mouse position in the title."""
        # self.mouse_position = event.screen_offset
        self.update_static()
    
    def update_static(self) -> None:
        text = f"mouse_position = {self.mouse_position!r}\nrandom_id = {uuid.uuid4().hex!r}"
        self.static.update(text)
    

if __name__ == "__main__":
    # Repro(ReproApp).run()
    ReproApp().run()
