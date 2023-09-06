"""ANSI art gallery TUI"""

import argparse
import locale
import os
import re
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalScroll, ScrollableContainer
from textual.widgets import Footer, Header, Static

from .__init__ import __version__
from .ansi_art_document import AnsiArtDocument
from .auto_restart import restart_on_changes, restart_program

parser = argparse.ArgumentParser(description='ANSI art gallery', usage='%(prog)s [folder]', prog="python -m src.textual_paint.gallery")
parser.add_argument('folder', nargs='?', default=None, help='Path to a folder containing ANSI art.')

dev_options = parser.add_argument_group('development options')
dev_options.add_argument('--inspect-layout', action='store_true', help='Enables DOM inspector (F12) and middle click highlight')
dev_options.add_argument('--restart-on-changes', action='store_true', help='Restart the app when the source code is changed')

args = parser.parse_args()

def _(text: str) -> str:
    """Placeholder for localization function."""
    return text

class GalleryItem(ScrollableContainer):
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
        yield Static(text, classes="image")
        yield Static(self.caption, classes="caption")

class GalleryApp(App[None]):
    """ANSI art gallery TUI"""

    TITLE = "ANSI art gallery"

    CSS_PATH = "gallery.css"

    BINDINGS = [
        Binding("ctrl+q", "quit", _("Quit"), priority=True),
        Binding("ctrl+d", "toggle_dark", _("Toggle Dark Mode")),
        Binding("left,pageup", "previous", _("Previous"), priority=True),
        Binding("right,pagedown", "next", _("Next"), priority=True),
        Binding("home", "scroll_to_start", _("First"), priority=True, show=False),
        Binding("end", "scroll_to_end", _("Last"), priority=True, show=False),
        # dev helper
        # f5 would be more traditional, but I need something not bound to anything
        # in the context of the terminal in VS Code, and not used by this app, like Ctrl+R, and detectable in the terminal.
        # This isn't that important since I have automatic reloading,
        # but it still comes in handy sometimes.
        Binding("f2", "reload", _("Reload"), show=False),
        # Dev tool to inspect the widget tree.
        Binding("f12", "toggle_inspector", _("Toggle Inspector"), show=False),
    ]

    def compose(self) -> ComposeResult:
        """Add widgets to the layout."""
        yield Header(show_clock=True)

        self.scroll = HorizontalScroll()
        yield self.scroll

        yield Footer()

        if not args.inspect_layout:
            return
        # importing the inspector adds instrumentation which can slow down startup
        from .inspector import Inspector
        inspector = Inspector()
        inspector.display = False
        yield inspector


    def on_mount(self) -> None:
        """Called when the app is mounted to the DOM."""
        self._load()

    def _load(self) -> None:
        """Load the folder specified on the command line."""
        hide_old_versions = False
        if args.folder is None:
            gallery_folder = Path(os.path.dirname(__file__), "../../samples").resolve()
            hide_old_versions = True
        else:
            gallery_folder = Path(args.folder)

        if not gallery_folder.exists():
            self.exit(None, f"Folder not found: {gallery_folder}")
            return

        if not gallery_folder.is_dir():
            # TODO: allow showing a specific file, and load whatever folder it's in
            self.exit(None, f"Not a folder: {gallery_folder}")
            return

        exts = (".ans", ".txt")

        paths = gallery_folder.rglob("**/*")
        paths = [path for path in paths if path.is_file() and path.suffix in exts]

        # First sort by whole path
        paths = sorted(paths, key=lambda path: locale.strxfrm(str(path)))
        # Then (higher priority) sort by version number (vX.Y) numerically where present
        # Actually, it might be simpler to handle any numbers in the filename, using Decorate-Sort-Undecorate.
        # Well, I can do it mostly, but for comparing "v1" and "v1.1", I need to consider the version number as a group.
        # For two-number version strings, I could consider it as a float, but for three-number version strings, a tuple should work.
        # I don't have any three-number version strings in the filenames of my ANSI art samples, but TODO: generalize this.
        matches_and_paths = [(re.findall(r"(\d*(?:\.\d+)?)(\D*)", str(path)), path) for path in paths]
        sorted_parts_and_paths = sorted(matches_and_paths, key=lambda matches_and_path: [
            [
                # If ints or strings are conditionally omitted, it leads to int vs str comparison errors.
                # *([float(match[0])] if match[0] else []),
                # *([locale.strxfrm(match[1])] if match[1] else []),
                # So just keep it as an alternating list of floats and strings. Simpler, and safer.
                float(match[0]) if match[0] else float("inf"),
                locale.strxfrm(match[1]),
            ]
            for match in matches_and_path[0]
        ])
        paths = [path for _, path in sorted_parts_and_paths]

        if hide_old_versions:
            # Hide any paths that are not the latest version of a file,
            # for files matching some_identifier_vX.Y_optional_comment.ext
            latest_versions: dict[str, tuple[float, Path]] = {}
            for path in paths:
                version_match = re.match(r"(.+)_v(\d+(?:\.\d+)?)", path.stem)
                if version_match:
                    id = version_match.group(1)
                    version = float(version_match.group(2))
                    if id in latest_versions:
                        if version > latest_versions[id][0]:
                            latest_versions[id] = version, path
                    else:
                        latest_versions[id] = version, path
                else:
                    latest_versions[str(path)] = -1, path
            paths = [path for _, path in latest_versions.values()]

            # Hide some uninteresting files
            paths = [path for path in paths if not re.match("0x0|1x1|2x2|4x4_font_template|gradient_test|pipe_strip_mega|cp437_as_utf8|galaxies_v1", path.name)]

        if len(paths) == 0:
            self.exit(None, f"No ANSI art ({', '.join(f'*{ext}' for ext in exts)}) found in folder: {gallery_folder}")
            return

        # Debugging
        # self.exit(None, "\n".join(str(path) for path in paths))
        # return

        for path in paths:
            # with open(path, "r", encoding="cp437") as f:
            with open(path, "r", encoding="utf8") as f:
                image = AnsiArtDocument.from_ansi(f.read())
            
            self.scroll.mount(GalleryItem(image, caption=path.name))
        
    def _scroll_to_adjacent_item(self, delta_index: int = 0) -> None:
        """Scroll to the next/previous item."""
        # try:
        #     index = self.scroll.children.index(self.app.focused)
        # except ValueError:
        #     return
        widget, _ = self.app.get_widget_at(self.screen.region.width // 2, self.screen.region.height // 2)
        while widget is not None and not isinstance(widget, GalleryItem):
            widget = widget.parent
        if widget is None:
            index = 0
        else:
            index = self.scroll.children.index(widget)
        index += delta_index
        index = max(0, min(index, len(self.scroll.children) - 1))
        target = self.scroll.children[index]
        target.focus()
        self.scroll.scroll_to_widget(target)

    def action_next(self) -> None:
        """Scroll to the next item."""
        self._scroll_to_adjacent_item(1)

    def action_previous(self) -> None:
        """Scroll to the previous item."""
        self._scroll_to_adjacent_item(-1)

    def action_scroll_to_start(self) -> None:
        """Scroll to the first item."""
        self.scroll.scroll_to_widget(self.scroll.children[0])

    def action_scroll_to_end(self) -> None:
        """Scroll to the last item."""
        self.scroll.scroll_to_widget(self.scroll.children[-1])

    def action_reload(self) -> None:
        """Reload the program."""
        restart_program()

    def action_toggle_inspector(self) -> None:
        """Toggle the DOM inspector."""
        if not args.inspect_layout:
            return
        # importing the inspector adds instrumentation which can slow down startup
        from .inspector import Inspector
        inspector = self.query_one(Inspector)
        inspector.display = not inspector.display
        if not inspector.display:
            inspector.picking = False


app = GalleryApp()

if args.restart_on_changes:
    restart_on_changes(app)

if __name__ == "__main__":
    app.run()
