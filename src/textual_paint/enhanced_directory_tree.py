"""Enhances Textual's DirectoryTree with auto-expansion, filtering of hidden files, and ASCII icon replacements."""

from pathlib import Path
from typing import Callable, Iterable

from rich.style import Style
from rich.text import Text, TextType
from textual.reactive import var
from textual.widgets import DirectoryTree, Tree
from textual.widgets._directory_tree import DirEntry
from textual.widgets._tree import TOGGLE_STYLE, TreeNode

# from textual_paint.args import args
from textual_paint.__init__ import PYTEST
from textual_paint.ascii_mode import replace

# Vague skeuomorphism
# FILE_ICON = Text.from_markup("[#aaaaaa on #ffffff]=[/] " if args.ascii_only else "📄 ")
# FOLDER_OPEN_ICON = Text.from_markup("[rgb(128,128,64)]L[/] " if args.ascii_only else "📂 ")
# FOLDER_CLOSED_ICON = Text.from_markup("[rgb(128,128,64)]V[/] " if args.ascii_only else "📁 ")
# Simple generic tree style
# FILE_ICON = Text.from_markup("" if args.ascii_only else "📄 ")
# FOLDER_OPEN_ICON = Text.from_markup("[blue]-[/] " if args.ascii_only else "📂 ")
# FOLDER_CLOSED_ICON = Text.from_markup("[blue]+[/] " if args.ascii_only else "📁 ")

# Simple generic tree style + new way of handling --ascii-only mode
FILE_ICON = Text("📄 ")
FOLDER_OPEN_ICON = Text("📂 ")
FOLDER_CLOSED_ICON = Text("📁 ")
icons = locals()
replace(icons, "FILE_ICON", Text.from_markup(""))
replace(icons, "FOLDER_OPEN_ICON", Text.from_markup("[blue]-[/] "))
replace(icons, "FOLDER_CLOSED_ICON", Text.from_markup("[blue]+[/] "))

class EnhancedDirectoryTree(DirectoryTree):
    """A DirectoryTree with auto-expansion, filtering of hidden files, and ASCII icon replacements."""

    node_highlighted_by_expand_to_path = var(False)
    """Whether a NodeHighlighted event was triggered by expand_to_path.

    (An alternative would be to create a new message type wrapping `NodeHighlighted`,
    which includes a flag.)
    (Also, this could be a simple attribute, but I didn't want to make an `__init__`
    method for this one thing.)
    """

    _id = "some fake shit"
    _name = "some more fake shit"

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if not (path.name.startswith(".") or path.name.endswith("~") or path.name.startswith("~"))]

    def _go_to_node(self, node: TreeNode[DirEntry], callback: Callable[[], None]) -> None:
        """Scroll to the node, and select it."""
        def _go_to_node_now():

            # print("set flag")
            self.node_highlighted_by_expand_to_path = True
            self.select_node(node)
            # def clear_flag() -> None:
            #     print("clear flag")
            #     self.node_highlighted_by_expand_to_path = False
            # self.call_later(clear_flag) # too early!
            # self.set_timer(0.01, clear_flag) # unreliable
            # self.call_after_refresh(clear_flag) # unreliable
            # The above is unreliable because NodeHighlighted is
            # sent by watch_cursor_line, so it may go:
            # * set flag
            # * (add clear_flag callback to queue)
            # * watch_cursor_line
            # * (adds NodeHighlighted to queue)
            # * clear flag
            # * on_tree_node_highlighted
            #
            # So instead, listen for NodeHighlighted,
            # and then clear the flag.

            region = self._get_label_region(node._line)  # pyright: ignore[reportPrivateUsage]
            assert region, "Node not found in tree"
            self.scroll_to_region(region, animate=False, top=True)

            callback()
        # Is there a way to avoid this delay?
        self.set_timer(0.01, _go_to_node_now)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[DirEntry]) -> None:
        """Called when a node is highlighted in the DirectoryTree.

        This handler is used to clear the flag set by expand_to_path.
        See _go_to_node for more details.
        """
        # print("EnhancedDirectoryTree.on_tree_node_highlighted (queue clearing flag)")
        def clear_flag() -> None:
            # print("clear flag")
            self.node_highlighted_by_expand_to_path = False
        # Now that we've received the NodeHighlighted event,
        # we just need to wait for subclasses/parent widgets to handle it,
        # so this can be tighter the earliest-calling method I tried above.
        # self.call_next(clear_flag) # too early!
        # Even though it's the same event, bubbling, the `call_next`
        # callback actually comes before the event finishes bubbling.
        # self.call_later(clear_flag) # too early!
        self.call_after_refresh(clear_flag) # finally reliable

    def _expand_matching_child(self, node: TreeNode[DirEntry], remaining_parts: tuple[str, ...], callback: Callable[[], None]) -> None:
        """Hooks into DirectoryTree's add method, and expands the child node matching the next path part, recursively.

        Once the last part of the path is reached, it scrolls to and selects the node.
        """
        # print("_expand_matching_child", node, remaining_parts)
        if not remaining_parts:
            # I noticed this happening when testing with pyfakefs.
            # os.cwd() is faked to return "/" by default, leading to this edge case
            # where the EnhancedDirectoryTree is "expanded" to the root.
            return
        orig_add = node.add
        _expand_matching_child = self._expand_matching_child
        _add_to_load_queue = self._add_to_load_queue
        _go_to_node = self._go_to_node
        def expand_if_match(node: TreeNode[DirEntry]) -> None:
            if node.data:
                # print(f"comparing node.data.path.parts[-1] {node.data.path.parts[-1]!r} with remaining_parts[0] {remaining_parts[0]!r}")
                if node.data.path.parts[-1] == remaining_parts[0]:
                    if len(remaining_parts) > 1:
                        if node.data.path.is_dir():
                            sliced_parts = remaining_parts[1:]
                            # print("recursing with sliced_parts", sliced_parts)
                            _expand_matching_child(node, sliced_parts, callback)
                            _add_to_load_queue(node)
                        # else:
                        #     print("Found a file, not as last part of path:", node.data.path, "remaining_parts:", remaining_parts)
                    else:
                        # print("scrolling", node)
                        _go_to_node(node, callback)
                        # If the target path is a directory, expand it.
                        # This might not always be desired, for a general API,
                        # but for File > New, File > Open, it should expand the current directory.
                        if node.data.path.is_dir():
                            _add_to_load_queue(node)
        def add(
            self: TreeNode[DirEntry],
            label: TextType,
            data: DirEntry | None = None,
            *,
            expand: bool = False,
            allow_expand: bool = True,
        ) -> TreeNode[DirEntry]:
            node = orig_add(label, data, expand=expand, allow_expand=allow_expand)
            # print("add", node, node.data)
            expand_if_match(node)
            # Note: The hook is left indefinitely.
            # It may be worth some consideration as to whether this could pose any problems.
            # However, we can't just reset to orig_add here since that would make this only handle the first added node.
            return node
        # Hook the add method to handle new nodes.
        node.add = add.__get__(node, type(node))
        # Also expand children of the node already loaded.
        for child in node.children:
            expand_if_match(child)

    def expand_to_path(self, target_path: str | Path, callback: Callable[[], None] | None = None) -> None:
        """Expand the directory tree to the target path, loading any directories as needed."""

        target_path = Path(target_path)

        # TODO: os.path.normcase, and maybe os.path.samefile check?
        # Is that still relevant now using pathlib.Path?
        # Also, if I'm going to make a PR for this feature,
        # - I should test it with symbolic links, and UNC paths on Windows.
        # - There should be an attribute to expand to a path initially.
        # - Maybe this method should return the node if it was found.

        if callback is None:
            callback = lambda: None

        self._expand_matching_child(self.root, target_path.parts[1:], callback)

    def render_label(
        self, node: TreeNode[DirEntry], base_style: Style, style: Style
    ) -> Text:
        """Override label rendering to make icons dynamic for --ascii-only mode.

        Args:
            node: A tree node.
            base_style: The base style of the widget.
            style: The additional style for the label.

        Returns:
            A Rich Text object containing the label.
        """
        node_label = node._label.copy()  # pyright: ignore[reportPrivateUsage]

        if PYTEST and node_label.plain == "\\":
            # Normalize root node display for cross-platform snapshot testing.
            # (Setting pyfakefs's fs.os = OSType.LINUX caused bigger problems.)
            node_label.plain = "/"

        node_label.stylize(style)

        if node._allow_expand:  # pyright: ignore[reportPrivateUsage]
            prefix = (FOLDER_OPEN_ICON if node.is_expanded else FOLDER_CLOSED_ICON).copy()
            prefix.stylize_before(base_style + TOGGLE_STYLE)
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--folder", partial=True)
            )
        else:
            prefix = FILE_ICON.copy()
            prefix.stylize_before(base_style)
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--file", partial=True),
            )
            node_label.highlight_regex(
                r"\..+$",
                self.get_component_rich_style(
                    "directory-tree--extension", partial=True
                ),
            )

        if node_label.plain.startswith("."):
            node_label.stylize_before(
                self.get_component_rich_style("directory-tree--hidden")
            )

        return prefix + node_label
