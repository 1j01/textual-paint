import uuid

from textual.app import App, ComposeResult
from textual.events import MouseMove
from textual.widgets import Static

class MouseMoveApp(App[None]):
    """App shows the mouse position."""
    def compose(self) -> ComposeResult:
        self.static = Static("This should show the mouse position...")
        yield self.static
        # self.set_interval(0.1, self.update_static) # works fine
    
    def on_mouse_move(self, event: MouseMove) -> None:
        """Show the mouse position in the title."""
        # Never called...
        self.update_static()
    
    def update_static(self) -> None:
        text = f"mouse_position = {self.mouse_position!r}\nrandom_id = {uuid.uuid4().hex!r}"
        self.static.update(text)
    

if __name__ == "__main__":
    MouseMoveApp().run()
