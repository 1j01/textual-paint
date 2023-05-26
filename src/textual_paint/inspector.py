"""Layout inspector development tool for Textual."""

import asyncio
from typing import NamedTuple
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.color import Color
from textual.containers import Container
from textual.dom import DOMNode
from textual.geometry import Offset
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Tree
from textual.widgets.tree import TreeNode
from textual.css._style_properties import BorderDefinition

class DOMTree(Tree[DOMNode]):
    """A widget that displays the widget hierarchy."""
    
    class Hovered(Message, bubble=True):
        """Posted when a node in the tree is hovered with the mouse or highlighted with the keyboard.

        Handled by defining a `on_domtree_hovered` method on a parent widget.
        """

        def __init__(
            self, tree: "DOMTree", tree_node: TreeNode[DOMNode], dom_node: DOMNode
        ) -> None:
            """Initialise the Hovered message.

            Args:
                tree: The `DOMTree` that had a node hovered.
                tree_node: The tree node for the file that was hovered.
                dom_node: The DOM node that was hovered.
            """
            super().__init__()
            self.tree: DOMTree = tree
            """The `DOMTree` that had a node hovered."""
            self.tree_node: TreeNode[DOMNode] = tree_node
            """The tree node that was hovered. Only _represents_ the DOM node."""
            self.dom_node: DOMNode = dom_node
            """The DOM node that was hovered."""

        # @property
        # def control(self) -> "DOMTree":
        #     """The `DOMTree` that had a node hovered.

        #     This is an alias for [`Hovered.tree`][textual_paint.inspector.DOMTree.Hovered.tree]
        #     which is used by the [`on`][textual.on] decorator.
        #     """
        #     return self.tree

    def __init__(
        self,
        root: DOMNode,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(
            root.css_identifier_styled,
            root,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self._root_dom_node = root

    def _on_tree_node_expanded(self, event: Tree.NodeExpanded[DOMNode]) -> None:
        event.stop()
        dom_node = event.node.data
        if dom_node is None:
            return
        # event.node.remove_children()
        for child in dom_node.children:
            exists = False
            for node in event.node.children:
                if node.data == child:
                    exists = True
                    break
            if exists:
                continue
            event.node.add(
                child.css_identifier_styled,
                data=child,
                allow_expand=len(child.children) > 0,
            )

    def _on_tree_node_highlighted(self, event: Tree.NodeHighlighted[DOMNode]) -> None:
        """Called when a node is highlighted with the keyboard."""
        event.stop()
        dom_node = event.node.data
        if dom_node is None:
            return
        self.post_message(self.Hovered(self, event.node, dom_node))

    def watch_hover_line(self, previous_hover_line: int, hover_line: int) -> None:
        """Extend the hover line watcher to post a message when a node is hovered."""
        super().watch_hover_line(previous_hover_line, hover_line)
        node: TreeNode[DOMNode] | None = self._get_node(hover_line)
        if node is not None:
            assert isinstance(node.data, DOMNode), "All nodes in DOMTree should have DOMNode data, got: " + repr(node.data)
            self.post_message(self.Hovered(self, node, node.data))
        # TODO: post when None? it seems to be reset anyways? but not if you move the mouse off the whole tree without moving it off a node


class OriginalStyles(NamedTuple):
    """The original styles of a widget before highlighting."""

    widget: Widget
    """The widget whose styles are stored."""
    border: BorderDefinition
    """The original border of the widget."""
    border_title: str | Text | None
    """The original border title of the widget."""
    background: Color | None
    """The original background of the widget."""
    tint: Color | None
    """The original tint of the widget."""

ALLOW_INSPECTING_INSPECTOR = False
"""Whether widgets in the inspector can be picked for inspection."""

class Inspector(Container):
    """UI for inspecting the layout of the application."""

    DEFAULT_CSS = """
    Inspector {
        dock: right;
        width: 40;
        border-left: wide $panel-darken-2;
        background: $panel;
    }
    Inspector Button {
        margin: 1;
        width: 100%;
    }
    Inspector Tree {
        margin: 1;
    }
    """

    def __init__(self):
        """Initialise the inspector."""

        super().__init__()

        self._picking: bool = False
        """Whether the user is picking a widget to inspect."""
        self._highlight: Container | None = None
        """A simple widget that highlights the widget being inspected."""
        self._highlight_styles: list[OriginalStyles] = []
        """Stores the original styles of any Hovered widgets."""

    def compose(self) -> ComposeResult:
        """Add sub-widgets."""
        inspect_icon = "⇱" # Alternatives: 🔍 🎯 🮰 🮵 ⮹ ⇱ 🢄 🡴 🡤 🡔 🢰 (↖️ arrow emoji unreliable)
        expand_icon = "+" # Alternatives: + ⨁ 🪜 🎊 🐡 🔬 (↕️ arrow emoji unreliable)
        yield Button(f"{inspect_icon} Inspect Element", classes="inspect_button")
        yield Button(f"{expand_icon} Expand All Visible", classes="expand_all_button")
        yield DOMTree(self.app)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle a button being clicked."""
        if event.button.has_class("expand_all_button"):
            self.query_one(DOMTree).root.expand_all()
        elif event.button.has_class("inspect_button"):
            self._picking = not self._picking
            self.reset_highlight()
            if self._picking:
                self.capture_mouse()
            else:
                self.release_mouse()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Handle the mouse moving."""
        if not self._picking:
            return
        self.highlight(self.get_widget_under_mouse(event.screen_offset))

    def get_widget_under_mouse(self, screen_offset: Offset) -> Widget | None:
        # This can raise NoWidget. Will it in practice?
        leaf_widget, _ = self.app.get_widget_at(*screen_offset)
        if self in leaf_widget.ancestors_with_self and not ALLOW_INSPECTING_INSPECTOR:
            return None
        return leaf_widget

    async def on_mouse_down(self, event: events.MouseDown) -> None:
        """Handle the mouse being pressed."""
        self.reset_highlight()
        if not self._picking:
            return
        leaf_widget = self.get_widget_under_mouse(event.screen_offset)
        self.release_mouse()
        self._picking = False

        if leaf_widget is None:
            return

        # Expand the tree to the selected widget.
        tree = self.query_one(DOMTree)
        tree_node = tree.root
        for dom_node in reversed(leaf_widget.ancestors_with_self):
            for node in (*tree_node.children, tree_node): # tree_node in case it's the root
                if node.data == dom_node:
                    tree_node = node
                    tree_node.expand()
                    async def wait_for_expand() -> None:
                        # while not tree_node.is_expanded: # this is set immediately
                        #     await asyncio.sleep(0.01)
                        await asyncio.sleep(0.01)
                    task = asyncio.create_task(wait_for_expand())
                    self._wait_for_expand = task
                    await task
                    del self._wait_for_expand
                    break
        # Select the widget in the tree.
        tree.select_node(tree_node)
        tree.scroll_to_node(tree_node)

    def on_domtree_hovered(self, event: DOMTree.Hovered) -> None:
        """Handle a DOM node being hovered/highlighted."""
        self.highlight(event.dom_node)

    def reset_highlight(self) -> None:
        if self._highlight is not None:
            self._highlight.remove()
        for old in self._highlight_styles:
            old.widget.styles.border = old.border
            old.widget.border_title = old.border_title
            old.widget.styles.background = old.background
            old.widget.styles.tint = old.tint

    def highlight(self, dom_node: DOMNode | None) -> None:
        """Highlight a DOM node."""
        self.reset_highlight()
        if dom_node is None:
            return
        if not isinstance(dom_node, Widget):
            # Only widgets have a region, App (the root) doesn't.
            return
        
        # Rainbow highlight of ancestors.
        """
        if dom_node and dom_node is not self.screen:
            for i, widget in enumerate(dom_node.ancestors_with_self):
                if not isinstance(widget, Widget):
                    continue
                self._highlight_styles.append(OriginalStyles(
                    widget=widget,
                    background=widget.styles.background,
                    border=widget.styles.border,
                    border_title=widget.border_title,
                    tint=widget.styles.tint,
                ))
                # widget.styles.background = Color.from_hsl(i / 10, 1, 0.3)
                # if not event.ctrl:
                # widget.styles.border = ("round", Color.from_hsl(i / 10, 1, 0.5))
                # widget.border_title = widget.css_identifier_styled
                widget.styles.tint = Color.from_hsl(i / 10, 1, 0.5).with_alpha(0.5)
        """

        # Tint highlight of hovered widget, and descendants, since the tint of a parent isn't inherited.
        widgets = dom_node.walk_children(with_self=True)
        for widget in widgets:
            assert isinstance(widget, Widget), "all descendants of a widget should be widgets, but got: " + repr(widget)
            self._highlight_styles.append(OriginalStyles(
                widget=widget,
                background=widget.styles.background,
                border=widget.styles.border,
                border_title=widget.border_title,
                tint=widget.styles.tint,
            ))
            widget.styles.tint = Color.parse("aquamarine").with_alpha(0.5)

        """
        self._highlight = Container()
        self._highlight.styles.border = ("round", "blue")
        self._highlight.border_title = dom_node.css_identifier_styled
        self._highlight.styles.width = dom_node.region.width
        self._highlight.styles.height = dom_node.region.height
        self._highlight.styles.offset = (dom_node.region.x, dom_node.region.y)
        # self._highlight.styles.layer = "inspector_highlight"
        # self._highlight.styles.dock = "top"
        """
