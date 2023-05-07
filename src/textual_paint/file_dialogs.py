import os
from typing import Any, Callable
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import Button, Input, Tree
from textual.widgets._directory_tree import DirEntry
from textual.containers import Container
from localization.i18n import get as _
from windows import DialogWindow
from enhanced_directory_tree import EnhancedDirectoryTree

class FileDialogWindow(DialogWindow):
    """A dialog window that lets the user select a file."""
    
    def __init__(
        self,
        *children: Widget,
        file_name: str = "",
        selected_file_path: str | None,
        handle_selected_file_path: Callable[[str], None],
        **kwargs: Any,
    ) -> None:
        """Initialize the dialog window."""
        super().__init__(handle_button=self.handle_button, *children, **kwargs)
        self._starting_file_name: str = file_name
        self._selected_file_path: str | None = selected_file_path
        self.handle_selected_file_path = handle_selected_file_path
        self._directory_tree_selected_path: str | None = None
        """Last highlighted item in the directory tree"""
        self._expanding_directory_tree: bool = False
        """Flag to prevent setting the filename input when initially expanding the directory tree"""

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        self._expand_directory_tree()
        # This MIGHT be more reliable even though it's hacky.
        # I don't know what the exact preconditions are for the expansion to work.
        # self.call_after_refresh(self._expand_directory_tree)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[DirEntry]) -> None:
        """
        Called when a file/folder is selected in the DirectoryTree.
        
        This message comes from Tree.
        DirectoryTree gives FileSelected, but only for files, not folders.
        """
        assert event.node.data
        if event.node.data.is_dir:
            self._directory_tree_selected_path = event.node.data.path
        elif event.node.parent:
            assert event.node.parent.data
            self._directory_tree_selected_path = event.node.parent.data.path
            name = os.path.basename(event.node.data.path)
            if not self._expanding_directory_tree:
                self.query_one("FileDialogWindow .filename_input", Input).value = name
        else:
            self._directory_tree_selected_path = None

    def _expand_directory_tree(self) -> None:
        """Expand the directory tree to the target directory, either the folder of the open file or the current working directory."""
        tree = self.content.query_one(EnhancedDirectoryTree)
        self._expanding_directory_tree = True
        target_dir = (self._selected_file_path or os.getcwd()).rstrip(os.path.sep)
        tree.expand_to_path(target_dir)
        # There are currently some timers in expand_to_path.
        # In particular, it waits before selecting the target node,
        # and this flag is for avoiding responding to that.
        def done_expanding():
            self._expanding_directory_tree = False
        self.set_timer(0.1, done_expanding)

class OpenDialogWindow(FileDialogWindow):
    """A dialog window that lets the user select a file to open.
    
    `handle_selected_file_path` is called when the user clicks the Open button,
    and the window is NOT closed in that case.
    """

    def __init__(
        self,
        *children: Widget,
        selected_file_path: str | None,
        handle_selected_file_path: Callable[[str], None],
        **kwargs: Any,
    ) -> None:
        """Initialize the dialog window."""
        super().__init__(*children, file_name="", selected_file_path=selected_file_path, handle_selected_file_path=handle_selected_file_path, **kwargs)

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        self.content.mount(
            EnhancedDirectoryTree(path="/"),
            Input(classes="filename_input", placeholder=_("Filename")),
            Container(
                Button(_("Open"), classes="open submit", variant="primary"),
                Button(_("Cancel"), classes="cancel"),
                classes="buttons",
            ),
        )

    def handle_button(self, button: Button) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        # TODO: DRY with Save As
        if not button.has_class("open"):
            self.close()
            return
        filename = self.content.query_one(".filename_input", Input).value
        if not filename:
            return
        # TODO: allow entering an absolute or relative path, not just a filename
        if self._directory_tree_selected_path:
            file_path = os.path.join(self._directory_tree_selected_path, filename)
        else:
            file_path = filename
        self.handle_selected_file_path(file_path)


class SaveAsDialogWindow(FileDialogWindow):
    """A dialog window that lets the user select a file to save to.
    
    `handle_selected_file_path` is called when the user clicks the Save button,
    and the window is NOT closed in that case.
    """

    def __init__(
        self,
        *children: Widget,
        file_name: str = "",
        selected_file_path: str | None,
        handle_selected_file_path: Callable[[str], None],
        **kwargs: Any,
    ) -> None:
        """Initialize the dialog window."""
        super().__init__(*children, file_name=file_name, selected_file_path=selected_file_path, handle_selected_file_path=handle_selected_file_path, **kwargs)

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        self.content.mount(
            EnhancedDirectoryTree(path="/"),
            Input(classes="filename_input", placeholder=_("Filename"), value=self._starting_file_name),
            Container(
                Button(_("Save"), classes="save submit", variant="primary"),
                Button(_("Cancel"), classes="cancel"),
                classes="buttons",
            ),
        )
    
    def handle_button(self, button: Button) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        # TODO: DRY with Open
        if button.has_class("cancel"):
            self.request_close()
        elif button.has_class("save"):
            name = self.query_one(".filename_input", Input).value
            if not name:
                return
            # TODO: allow entering an absolute or relative path, not just a filename
            if self._directory_tree_selected_path:
                file_path = os.path.join(self._directory_tree_selected_path, name)
            else:
                file_path = name
            self.handle_selected_file_path(file_path)
