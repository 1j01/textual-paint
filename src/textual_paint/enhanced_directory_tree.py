import os
from pathlib import Path
from typing import Iterable

from textual.widgets import DirectoryTree
from textual.widgets._tree import TreeNode
from textual.widgets._directory_tree import DirEntry

class EnhancedDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if not (path.name.startswith(".") or path.name.endswith("~") or path.name.startswith("~"))]

    def expand_to_path(self, target_path: str) -> None:
        """Expand the directory tree to the target path, loading any directories as needed."""
        # TODO: os.path.normcase, and maybe os.path.samefile check
        # Also, if I'm going to make a PR for this feature,
        # - I should test it with symbolic links, and UNC paths on Windows.
        # - There should be an attribute to expand to a path initially.
        # - Maybe this method should return the node if it was found.
        # - Could avoid some get_node_name calls by flagging if there's a match.
        # - Definitely want to figure out how to avoid the timers.
        # - Might be better to handle both / and \ regardless of platform.

        node = self.root
        def get_node_name(node: TreeNode[DirEntry]) -> str:
            assert node.data
            return os.path.basename(node.data.path)
        for path_segment in target_path.split(os.path.sep):
            # Find the child node with the right name.
            for child in node.children:
                if get_node_name(child) == path_segment:
                    node = child
                    break
            if get_node_name(node) == path_segment:
                assert isinstance(node.data, DirEntry)
                if node.data.path.is_dir():
                    if not node.is_expanded and not node.data.loaded:
                        # load_directory also calls node.expand()
                        self._load_directory(node)
                else:
                    # Found a file.
                    break
            else:
                # Directory or file not found.
                break
        # Timer is needed to wait for the new nodes to mount, I think.
        # self.select_node(node)
        self.set_timer(0.01, lambda: self.select_node(node))
        # widget.scroll_to_region supports a `top` argument,
        # but self.scroll_to_node doesn't.
        # A simple workaround is to scroll to the bottom first.
        # self.scroll_to_line(self.last_line)
        # self.scroll_to_node(node)
        # That would work if scroll_to_node and scroll_to_line didn't animate,
        # but the animations conflicts with each other and it ends up in the wrong spot.
        # They don't support widget.scroll_to_region's `animate` argument either.
        # Oh but I can use scroll_visible instead.
        # node.scroll_visible(animate=False, top=True)
        # That is, if node was a widget!
        # Ugh. OK, I'm going to use some internals, and replicate how scroll_to_node works.
        # self.scroll_to_region(self._get_label_region(node._line), animate=False, top=True)
        # Timer is needed to wait for the new nodes to mount, I think.
        def scroll_node_to_top():
            region = self._get_label_region(node._line) # type: ignore
            assert region, "Node not found in tree"
            self.scroll_to_region(region, animate=False, top=True)
        self.set_timer(0.01, scroll_node_to_top)
