from asyncio import Future
from pathlib import Path
from typing import Iterable

from rich.text import TextType
from textual.widgets import DirectoryTree
from textual.widgets._tree import TreeNode
from textual.widgets._directory_tree import DirEntry

class EnhancedDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if not (path.name.startswith(".") or path.name.endswith("~") or path.name.startswith("~"))]

    def _go_to_node(self, node: TreeNode[DirEntry], future: Future[None]) -> None:
        """Scroll to the node, and select it."""
        def _go_to_node_now():
            self.select_node(node)
            region = self._get_label_region(node._line) # type: ignore
            assert region, "Node not found in tree"
            self.scroll_to_region(region, animate=False, top=True)
            future.set_result(None)
        # Is there a way to avoid this delay?
        self.set_timer(0.01, _go_to_node_now)

    def _expand_matching_child(self, node: TreeNode[DirEntry], remaining_parts: tuple[str], future: Future[None]) -> None:
        """Hooks into DirectoryTree's add method, and expands the child node matching the next path part, recursively.
        
        Once the last part of the path is reached, it scrolls to and selects the node.
        """
        # print("_expand_matching_child", node, remaining_parts)
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
                            _expand_matching_child(node, sliced_parts, future)  # type: ignore
                            _add_to_load_queue(node)
                        # else:
                        #     print("Found a file, not as last part of path:", node.data.path, "remaining_parts:", remaining_parts)
                    else:
                        # print("scrolling", node)
                        _go_to_node(node, future)
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

    async def expand_to_path(self, target_path: str | Path) -> None:
        """Expand the directory tree to the target path, loading any directories as needed."""

        target_path = Path(target_path)

        # TODO: os.path.normcase, and maybe os.path.samefile check?
        # Is that still relevant now using pathlib.Path?
        # Also, if I'm going to make a PR for this feature,
        # - I should test it with symbolic links, and UNC paths on Windows.
        # - There should be an attribute to expand to a path initially.
        # - Maybe this method should return the node if it was found.

        future: Future[None] = Future()
        self._expand_matching_child(self.root, target_path.parts[1:], future)
        await future

