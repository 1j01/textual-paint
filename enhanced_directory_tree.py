import os
from textual.widgets import DirectoryTree

class EnhancedDirectoryTree(DirectoryTree):
    def expand_to_path(self, target_path: str) -> None:
        """Expand the directory tree to the target path, loading any directories as needed."""
        # TODO: os.path.normcase, and maybe os.path.samefile check
        
        node = self.root
        def get_node_name(node):
            return os.path.basename(node.data.path.rstrip(os.path.sep))
        for path_segment in target_path.split(os.path.sep):
            # Find the child node with the right name.
            for child in node.children:
                if get_node_name(child) == path_segment:
                    node = child
                    break
            if get_node_name(node) == path_segment:
                if node.data.is_dir:
                    if not node.is_expanded and not node.data.loaded:
                        # load_directory also calls node.expand()
                        self.load_directory(node)
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
        self.set_timer(0.01, lambda: self.scroll_to_region(self._get_label_region(node._line), animate=False, top=True))
