import os
from typing import Any, Callable

from textual.containers import Container
from textual.widget import Widget
from textual.widgets import Button, Input, Tree, Label
from textual.containers import Horizontal
from textual.widgets._directory_tree import DirEntry
from textual.containers import Container

from .localization.i18n import get as _
from .windows import DialogWindow
from .enhanced_directory_tree import EnhancedDirectoryTree

class FileDialogWindow(DialogWindow):
    """A dialog window that lets the user select a file."""
    
    def __init__(
        self,
        *children: Widget,
        file_name: str = "",
        selected_file_path: str | None,
        handle_selected_file_path: Callable[[str], None],
        auto_add_default_extension: str = "",
        submit_label: str,
        **kwargs: Any,
    ) -> None:
        """Initialize the dialog window."""

        super().__init__(handle_button=self.handle_button, *children, **kwargs)

        self._starting_file_name: str = file_name
        self._selected_file_path: str | None = selected_file_path
        self._submit_label: str = submit_label

        self.handle_selected_file_path = handle_selected_file_path
        """Callback called when the user selects a file."""

        self._directory_tree_selected_path: str | None = None
        """Last highlighted item in the directory tree"""

        self._auto_add_default_extension: str = auto_add_default_extension
        """The default extension to add to the filename if it doesn't have one"""

    def handle_button(self, button: Button) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        if button.has_class("cancel"):
            self.request_close()
        elif button.has_class("submit"):
            filename = self.content.query_one(".filename_input", Input).value
            if not filename:
                return

            file_path = filename
            # This comes before os.path.join so that "~" (which gives an absolute path)
            # overrides the currently selected directory (as absolute paths do in general)
            # >>> import os
            # >>> os.path.join("foo", os.path.expanduser("~/bar"))
            # '/home/<user>/bar'
            # >>> os.path.expanduser(os.path.join("foo", "~/bar"))
            # 'foo/~/bar'
            file_path = os.path.expanduser(file_path) # ~ or ~<user>
            file_path = os.path.expandvars(file_path) # e.g. $HOME, ${HOME}, or on Windows, %USERPROFILE%

            if self._directory_tree_selected_path:
                file_path = os.path.join(self._directory_tree_selected_path, file_path)

            if os.path.splitext(file_path)[1] == "":
                file_path += self._auto_add_default_extension

            # if it's a directory, just navigate to it in the directory tree
            if os.path.isdir(file_path):
                # self._directory_tree_selected_path = file_path
                # self._selected_file_path = file_path
                # self._expand_directory_tree()
                tree = self.content.query_one(EnhancedDirectoryTree)
                tree.expand_to_path(file_path)
                return

            self.handle_selected_file_path(file_path)

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        self.content.mount(
            EnhancedDirectoryTree(path="/"),
            Horizontal(
                Label(_("File name:")),
                Input(classes="filename_input autofocus", value=self._starting_file_name),
            ),
            Container(
                Button(self._submit_label, classes="submit", variant="primary"),
                Button(_("Cancel"), classes="cancel"),
                classes="buttons",
            ),
        )

        self._expand_directory_tree()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[DirEntry]) -> None:
        """
        Called when a file/folder is selected in the DirectoryTree.
        
        This message comes from Tree.
        DirectoryTree gives FileSelected, but only for files, not folders.
        """
        assert event.node.data
        
        if event.node.data.path.is_dir():
            self._directory_tree_selected_path = str(event.node.data.path)
        elif event.node.parent:
            assert event.node.parent.data
            self._directory_tree_selected_path = str(event.node.parent.data.path)
            name = os.path.basename(event.node.data.path)
            assert isinstance(event.control, EnhancedDirectoryTree)
            # print("node_highlighted_by_expand_to_path", event.control.node_highlighted_by_expand_to_path)
            if not event.control.node_highlighted_by_expand_to_path:
                # TODO: handle NoMatches if dialog is opened and closed immediately
                # such as by spamming Ctrl+O
                self.query_one("FileDialogWindow .filename_input", Input).value = name
        else:
            self._directory_tree_selected_path = None

    def _expand_directory_tree(self) -> None:
        """Expand the directory tree to the target directory, either the folder of the open file or the current working directory."""
        tree = self.content.query_one(EnhancedDirectoryTree)
        target_dir = (self._selected_file_path or os.getcwd()).rstrip(os.path.sep)
        tree.expand_to_path(target_dir)

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
        super().__init__(
            *children,
            submit_label=_("Open"),
            file_name="",
            selected_file_path=selected_file_path,
            handle_selected_file_path=handle_selected_file_path,
            **kwargs
        )

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
        auto_add_default_extension: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize the dialog window."""
        super().__init__(
            *children,
            submit_label=_("Save"),
            file_name=file_name,
            selected_file_path=selected_file_path,
            handle_selected_file_path=handle_selected_file_path,
            auto_add_default_extension=auto_add_default_extension,
            **kwargs
        )
