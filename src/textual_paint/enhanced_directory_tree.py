from pathlib import Path
from typing import Iterable

from rich.text import TextType
from textual.widgets import DirectoryTree
from textual.widgets._tree import TreeNode
from textual.widgets._directory_tree import DirEntry

class EnhancedDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if not (path.name.startswith(".") or path.name.endswith("~") or path.name.startswith("~"))]

    def _go_to_node(self, node: TreeNode[DirEntry]) -> None:
        """Scroll to the node, and select it."""
        self.set_timer(0.01, lambda: self.select_node(node))
        def scroll_node_to_top():
            region = self._get_label_region(node._line) # type: ignore
            assert region, "Node not found in tree"
            self.scroll_to_region(region, animate=False, top=True)
        self.set_timer(0.01, scroll_node_to_top)

    def _hook_node_add(self, node: TreeNode[DirEntry], remaining_parts: tuple[str]) -> None:
        # print("_hook_node_add", node, remaining_parts)
        orig_add = node.add
        _hook_node_add = self._hook_node_add
        _add_to_load_queue = self._add_to_load_queue
        _go_to_node = self._go_to_node
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
            if node.data:
                # print(f"comparing node.data.path.parts[-1] {node.data.path.parts[-1]!r} with remaining_parts[0] {remaining_parts[0]!r}")
                if node.data.path.parts[-1] == remaining_parts[0]:
                    if len(remaining_parts) > 1:
                        if node.data.path.is_dir():
                            sliced_parts = remaining_parts[1:]
                            # print("recursing with sliced_parts", sliced_parts)
                            _hook_node_add(node, sliced_parts)  # type: ignore
                            _add_to_load_queue(node)
                        # else:
                        #     print("Found a file, not as last part of path:", node.data.path, "remaining_parts:", remaining_parts)
                    else:
                        # print("scrolling", node)
                        _go_to_node(node)
            return node
        node.add = add.__get__(node, type(node))

    def expand_to_path(self, target_path: str | Path) -> None:
        """Expand the directory tree to the target path, loading any directories as needed."""

        target_path = Path(target_path)

        # TODO: os.path.normcase, and maybe os.path.samefile check?
        # Is that still relevant now using pathlib.Path?
        # Also, if I'm going to make a PR for this feature,
        # - I should test it with symbolic links, and UNC paths on Windows.
        # - There should be an attribute to expand to a path initially.
        # - Maybe this method should return the node if it was found.
        # - Definitely want to figure out how to avoid the timers.

        self._hook_node_add(self.root, target_path.parts[1:])

