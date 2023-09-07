"""ANSI art gallery TUI"""

import argparse
import locale
import os
import re
from pathlib import Path
from rich.text import Text

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, ScrollableContainer
from textual.reactive import Reactive, var
from textual.widgets import Footer, Header, Static

from .__init__ import __version__
from .ansi_art_document import AnsiArtDocument
from .auto_restart import restart_on_changes, restart_program

parser = argparse.ArgumentParser(description='ANSI art gallery', usage='%(prog)s [path]', prog="python -m src.textual_paint.gallery")
parser.add_argument('path', nargs='?', default=None, help='Path to a folder containing ANSI art, or an ANSI file.')
parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
parser.add_argument('--no-animation', action='store_true', help='Disable transition effects')

dev_options = parser.add_argument_group('development options')
dev_options.add_argument('--inspect-layout', action='store_true', help='Enables DOM inspector (F12) and middle click highlight')
dev_options.add_argument('--restart-on-changes', action='store_true', help='Restart the app when the source code is changed')

args = parser.parse_args()

def _(text: str) -> str:
    """Placeholder for localization function."""
    return text

class GalleryItem(Container):
    """An image with a caption."""

    position: Reactive[float] = var(0)

    def __init__(self, image: AnsiArtDocument, caption: str):
        """Initialise the gallery item."""
        super().__init__()
        self.image = image
        self.caption = caption

    def compose(self) -> ComposeResult:
        """Add widgets to the layout."""
        text = self.image.get_renderable()
        text.no_wrap = True
        yield ScrollableContainer(Static(text, classes="image"), classes="image_container")
        yield Static(self.caption, classes="caption")

    def watch_position(self, value: float) -> None:
        """Called when `position` is changed."""
        self.styles.offset = (round(self.app.size.width * value), 0)

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

    path_index: Reactive[int] = var(0)

    def __init__(self) -> None:
        """Initialise the app."""
        super().__init__()
        self.paths: list[Path] = []
        self.gallery_item_by_path: dict[Path, GalleryItem] = {}

    def compose(self) -> ComposeResult:
        """Add widgets to the layout."""
        yield Header(show_clock=True)

        self.container = Container()
        yield self.container

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
        if args.path is None:
            gallery_folder = Path(os.path.dirname(__file__), "../../samples").resolve()
            hide_old_versions = True
        else:
            gallery_folder = Path(args.path)

        if not gallery_folder.exists():
            self.exit(None, Text(f"Folder or file not found: {gallery_folder}"))
            return

        file_to_show = None
        if gallery_folder.is_file():
            # allow showing a specific file, and load whatever folder it's in
            file_to_show = gallery_folder
            gallery_folder = gallery_folder.parent

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

        exts_str = ', '.join(f'*{ext}' for ext in exts)
        if file_to_show:
            try:
                index_to_show = [*map(str, paths)].index(str(file_to_show))
            except ValueError:
                self.exit(None, Text(f"Not an ANSI art file ({exts_str}): {file_to_show}"))
                return
        else:
            index_to_show = 0

        if len(paths) == 0:
            self.exit(None, Text(f"No ANSI art ({exts_str}) found in folder: {gallery_folder}"))
            return

        # Debugging
        # self.exit(None, Text("\n".join(str(path) for path in paths) + f"\n\nindex_to_show: {index_to_show}\ntotal: {len(paths)}"))
        # return

        self.paths = paths
        self.gallery_item_by_path = {}
        self.path_index = index_to_show
        self._load_upcoming_images()

    def _load_upcoming_images(self) -> None:
        """Load current and upcoming images."""
        range_start = max(self.path_index - 2, 0)
        range_end = min(self.path_index + 2, len(self.paths))

        for path in self.paths[range_start:range_end]:
            if path not in self.gallery_item_by_path:
                self._load_image(path)

    def _load_image(self, path: Path) -> None:
        """Load a file and create a gallery item for it."""
        # with open(path, "r", encoding="cp437") as f:
        with open(path, "r", encoding="utf8") as f:
            image = AnsiArtDocument.from_ansi(f.read())

        gallery_item = GalleryItem(image, caption=path.name)
        self.container.mount(gallery_item)
        item_index = self.paths.index(path)
        # gallery_item.styles.opacity = 1.0 if item_index == self.path_index else 0.0
        gallery_item.position = 0 if item_index == self.path_index else (-1 if item_index < self.path_index else 1)
        self.gallery_item_by_path[path] = gallery_item

    def validate_path_index(self, path_index: int) -> int:
        """Ensure the index is within range."""
        return max(0, min(path_index, len(self.paths) - 1))

    def watch_path_index(self, current_index: int) -> None:
        """Called when the path index is changed."""
        self._load_upcoming_images()
        for path, gallery_item in self.gallery_item_by_path.items():
            item_index = self.paths.index(path)
            # opacity = 1.0 if item_index == current_index else 0.0
            # gallery_item.styles.animate("opacity", value=opacity, final_value=opacity, duration=0.5)
            position = 0 if item_index == current_index else (-1 if item_index < current_index else 1)
            if args.no_animation:
                gallery_item.position = position
            else:
                gallery_item.animate("position", value=position, final_value=position, duration=0.3)

        self.sub_title = f"{current_index + 1}/{len(self.paths)}"

    def action_next(self) -> None:
        """Scroll to the next item."""
        self.path_index += 1

    def action_previous(self) -> None:
        """Scroll to the previous item."""
        self.path_index -= 1

    def action_scroll_to_start(self) -> None:
        """Scroll to the first item."""
        self.path_index = 0

    def action_scroll_to_end(self) -> None:
        """Scroll to the last item."""
        self.path_index = len(self.paths) - 1

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
