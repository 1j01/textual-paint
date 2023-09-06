"""ANSI art gallery TUI"""

import argparse
import os
import re

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static
from textual.containers import HorizontalScroll, Vertical

from .paint import AnsiArtDocument
from .__init__ import __version__

parser = argparse.ArgumentParser(description='ANSI art gallery', usage='%(prog)s [folder]', prog="python -m src.textual_paint.gallery")
parser.add_argument('folder', nargs='?', default=None, help='Path to a folder containing ANSI art.')

args = parser.parse_args()

class GalleryItem(Vertical):
    """An image with a caption."""

    def __init__(self, image: AnsiArtDocument, caption: str):
        """Initialise the gallery item."""
        super().__init__()
        self.image = image
        self.caption = caption

    def compose(self) -> ComposeResult:
        """Add widgets to the layout."""
        text = self.image.get_renderable()
        text.no_wrap = True
        yield Static(text)
        yield Static(self.caption)

class Gallery(App[None]):
    """ANSI art gallery TUI"""

    TITLE = f"ANSI art gallery v{__version__}"

    def compose(self) -> ComposeResult:
        """Add widgets to the layout."""
        yield Header(show_clock=True)

        self.scroll = HorizontalScroll()
        yield self.scroll

        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted to the DOM."""
        self._load()

    def _load(self) -> None:
        """Load the folder specified on the command line."""
        folder = args.folder
        if folder is None:
            folder = os.path.join(os.path.dirname(__file__), "../../samples")
        if not os.path.isdir(folder):
            raise Exception(f"Folder not found: {folder}")
        
        for filename in os.listdir(folder):
            if not filename.endswith(".ans"):
                continue
            path = os.path.join(folder, filename)
            # with open(path, "r", encoding="cp437") as f:
            with open(path, "r", encoding="utf8") as f:
                image = AnsiArtDocument.from_ansi(f.read())
            
            self.scroll.mount(GalleryItem(image, caption=filename))


app = Gallery()

if __name__ == "__main__":
    app.run()
