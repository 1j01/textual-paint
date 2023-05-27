"""Layout inspector development tool for Textual."""

import asyncio
from typing import Any, Iterable, NamedTuple, Optional, TypeGuard
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.color import Color
from textual.containers import Container
from textual.dom import DOMNode
from textual.errors import NoWidget
from textual.geometry import Offset
from textual.message import Message
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import Button, Label, Static, Tree
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

    class Selected(Message, bubble=True):
        """Posted when a node in the tree is selected.

        Handled by defining a `on_domtree_selected` method on a parent widget.
        """

        def __init__(
            self, tree: "DOMTree", tree_node: TreeNode[DOMNode], dom_node: DOMNode
        ) -> None:
            """Initialise the Selected message.

            Args:
                tree: The `DOMTree` that had a node selected.
                tree_node: The tree node for the file that was selected.
                dom_node: The DOM node that was selected.
            """
            super().__init__()
            self.tree: DOMTree = tree
            """The `DOMTree` that had a node selected."""
            self.tree_node: TreeNode[DOMNode] = tree_node
            """The tree node that was selected. Only _represents_ the DOM node."""
            self.dom_node: DOMNode = dom_node
            """The DOM node that was selected."""

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

    def _on_tree_node_selected(self, event: Tree.NodeSelected[DOMNode]) -> None:
        """Called when a node is selected with the mouse or keyboard."""
        event.stop()
        dom_node = event.node.data
        if dom_node is None:
            return
        self.post_message(self.Selected(self, event.node, dom_node))

    def watch_hover_line(self, previous_hover_line: int, hover_line: int) -> None:
        """Extend the hover line watcher to post a message when a node is hovered."""
        super().watch_hover_line(previous_hover_line, hover_line)
        node: TreeNode[DOMNode] | None = self._get_node(hover_line)
        if node is not None:
            assert isinstance(node.data, DOMNode), "All nodes in DOMTree should have DOMNode data, got: " + repr(node.data)
            self.post_message(self.Hovered(self, node, node.data))
        # TODO: post when None? it seems to be reset anyways? but not if you move the mouse off the whole tree without moving it off a node


class NodeInfo(Container):

    dom_node: var[DOMNode | None] = var[Optional[DOMNode]](None)
    """The DOM node being inspected."""

    def compose(self) -> ComposeResult:
        """Add sub-widgets."""
        yield Label("[b]Properties[/b]")
        yield Tree("", classes="properties")
        yield Label("[b]Styles[/b]")
        yield Static(classes="styles")
        yield Label("[b]Key Bindings[/b]")
        yield Static(classes="key_bindings")
        yield Label("[b]Events[/b]")
        yield Static(classes="events")

    def watch_dom_node(self, dom_node: DOMNode | None) -> None:
        """Update the info displayed when the DOM node changes."""
        print("watch_dom_node", dom_node)
        properties_tree = self.query_one(".properties", Tree)
        styles_static = self.query_one(".styles", Static)
        key_bindings_static = self.query_one(".key_bindings", Static)
        events_static = self.query_one(".events", Static)

        if dom_node is None:
            properties_tree.reset("Nothing selected", None)
            styles_static.update("Nothing selected")
            key_bindings_static.update("Nothing selected")
            events_static.update("Nothing selected")
            return

        properties_tree.reset("", dom_node)
        self.add_data(properties_tree.root, dom_node)

        # styles_static.update(dom_node.styles.css)
        # styles_static.update(dom_node._css_styles.css)
        styles_static.update(dom_node.css_tree)

        key_bindings_static.update("\n".join(map(repr, dom_node.BINDINGS)) or "(None defined with BINDINGS)")

        # For events, look for class properties that are subclasses of Message
        # to determine what events are available.
        available_events = []
        for cls in type(dom_node).__mro__:
            for name, value in cls.__dict__.items():
                if isinstance(value, type) and issubclass(value, Message):
                    available_events.append(value)
        events_static.update("\n".join(map(str, available_events)) or f"(No message types exported by {type(dom_node).__name__!r} or its superclasses)")

    @classmethod
    def add_data(cls, node: TreeNode, data: object) -> None:
        """Adds data to a node.

        Based on https://github.com/Textualize/textual/blob/65b0c34f2ed6a69795946a0735a51a463602545c/examples/json_tree.py

        Args:
            node (TreeNode): A Tree node.
            data (object): Any object ideally should work.
        """

        from rich.highlighter import ReprHighlighter

        highlighter = ReprHighlighter()

        # uses equality, not (just) identity; is that a problem?
        # visited: set[object] = set()
        # well lists aren't hashable so we can't use a set
        visited: list[object] = []
        # but the in operator still uses equality, right? so the question stands
        # P.S. might want both a set and a list, for performance (for hashable and non-hashable types)

        max_depth = 3

        def add_node(name: str, node: TreeNode, data: object, depth: int = 0) -> None:
            """Adds a node to the tree.

            Args:
                name (str): Name of the node.
                node (TreeNode): Parent node.
                data (object): Data associated with the node.
            """

            def with_name(text: Text) -> Text:
                return Text.assemble(
                    Text.from_markup(f"[b]{name}[/b]="), text
                )

            if depth > max_depth:
                node.allow_expand = False
                node.set_label(with_name(Text.from_markup("[i]max depth[/i]")))
                return
            # TODO: max_keys as well
            # TODO: distinguish between cycles and repeated references
            if data in visited:
                node.allow_expand = False
                node.set_label(with_name(Text.from_markup("[i]cyclic reference[/i]")))
                return
            visited.append(data)
            if isinstance(data, list):
                node.set_label(Text(f"[] {name}"))
                for index, value in enumerate(data):
                    new_node = node.add("")
                    add_node(str(index), new_node, value, depth + 1)
            elif isinstance(data, str) or isinstance(data, int) or isinstance(data, float) or isinstance(data, bool):
                node.allow_expand = False
                if name:
                    label = with_name(highlighter(repr(data)))
                else:
                    label = Text(repr(data))
                node.set_label(label)
            elif hasattr(data, "__dict__"):
                node.set_label(Text(f"{{}} {name}"))
                for key, value in data.__dict__.items():
                    new_node = node.add("")
                    add_node(str(key), new_node, value, depth + 1)
            else:
                node.allow_expand = False
                node.set_label(with_name(Text(repr(data))))

        add_node("Properties", node, data)


class OriginalStyles(NamedTuple):
    """The original styles of a widget before highlighting."""

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
        min-height: 10;
    }
    """

    def __init__(self):
        """Initialise the inspector."""

        super().__init__()

        self._picking: bool = False
        """Whether the user is picking a widget to inspect."""
        self._highlight: Container | None = None
        """A simple widget that highlights the widget being inspected."""
        self._highlight_styles: dict[Widget, OriginalStyles] = {}
        """Stores the original styles of any Hovered widgets."""

    def compose(self) -> ComposeResult:
        """Add sub-widgets."""
        inspect_icon = "⇱" # Alternatives: 🔍 🎯 🮰 🮵 ⮹ ⇱ 🢄 🡴 🡤 🡔 🢰 (↖️ arrow emoji unreliable)
        expand_icon = "+" # Alternatives: + ⨁ 🪜 🎊 🐡 🔬 (↕️ arrow emoji unreliable)
        yield Button(f"{inspect_icon} Inspect Element", classes="inspect_button")
        yield Button(f"{expand_icon} Expand All Visible", classes="expand_all_button")
        yield DOMTree(self.app)
        yield NodeInfo()

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
        try:
            leaf_widget, _ = self.app.get_widget_at(*screen_offset)
        except NoWidget:
            return None
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
        tree.action_select_cursor()

    def on_domtree_selected(self, event: DOMTree.Selected) -> None:
        """Handle a node being selected in the DOM tree."""
        print("Inspecting DOM node:", event.dom_node)
        self.query_one(NodeInfo).dom_node = event.dom_node

    def on_domtree_hovered(self, event: DOMTree.Hovered) -> None:
        """Handle a DOM node being hovered/highlighted."""
        self.highlight(event.dom_node)

    def reset_highlight(self, except_widgets: Iterable[Widget] = ()) -> None:
        """Reset the highlight."""
        if self._highlight is not None:
            self._highlight.remove()
        for widget, old in list(self._highlight_styles.items()):
            if widget in except_widgets:
                continue
            widget.styles.border = old.border
            widget.border_title = old.border_title
            widget.styles.background = old.background
            widget.styles.tint = old.tint
            del self._highlight_styles[widget]

    def is_list_of_widgets(self, value: Any) -> TypeGuard[list[Widget]]:
        """Test whether a value is a list of widgets. The TypeGuard tells the type checker that this function ensures the type."""
        if not isinstance(value, list):
            return False
        for item in value:  # type: ignore
            if not isinstance(item, Widget):
                return False
        return True

    def highlight(self, dom_node: DOMNode | None) -> None:
        """Highlight a DOM node."""

        if not isinstance(dom_node, Widget):
            # Only widgets have a region, App (the root) doesn't.
            self.reset_highlight()
            return
        
        # Rainbow highlight of ancestors.
        """
        if dom_node and dom_node is not self.screen:
            for i, widget in enumerate(dom_node.ancestors_with_self):
                if not isinstance(widget, Widget):
                    continue
                self._highlight_styles[widget] = OriginalStyles(
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
        assert self.is_list_of_widgets(widgets), "walk_children should return a list of widgets, but got: " + repr(widgets)
        self.reset_highlight(except_widgets=widgets)
        for widget in widgets:
            if widget in self._highlight_styles:
                continue
            self._highlight_styles[widget] = OriginalStyles(
                background=widget.styles.background,
                border=widget.styles.border,
                border_title=widget.border_title,
                tint=widget.styles.tint,
            )
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
