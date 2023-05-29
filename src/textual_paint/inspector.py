"""Layout inspector development tool for Textual."""

import asyncio
import inspect
import pathlib
from types import EllipsisType
from typing import Any, Iterable, NamedTuple, Optional, Type, TypeGuard
from rich.markup import escape
from rich.text import Text
from rich.highlighter import ReprHighlighter
# from rich.syntax import Syntax
from textual import events
from textual.app import ComposeResult
from textual.case import camel_to_snake
from textual.color import Color
from textual.containers import Container, VerticalScroll
from textual.dom import DOMNode
from textual.errors import NoWidget
from textual.geometry import Offset
from textual.message import Message
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import Button, Static, TabPane, TabbedContent, Tree
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

class _ShowMoreSentinelType: pass
_ShowMoreSentinel = _ShowMoreSentinelType()
"""A sentinel that represents an ellipsis that can be clicked to load more properties."""
del _ShowMoreSentinelType

class PropertiesTree(Tree[object]):
    """A widget for exploring the attributes/properties of an object."""

    highlighter = ReprHighlighter()

    def __init__(
        self,
        label: str,
        root: object = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(
            label,
            root,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self._root_dom_node = root
        self._already_loaded: dict[TreeNode[object], set[str]] = {}
        """A mapping of tree nodes to the keys that have already been loaded.
        
        This allows the tree to be collapsed and expanded without duplicating nodes.
        It's also used for lazy-loading nodes when clicking the ellipsis in long lists.
        """

    def _on_tree_node_expanded(self, event: Tree.NodeExpanded[object]) -> None:
        event.stop()
        self._populate_node(event.node)

    def _on_tree_node_selected(self, event: Tree.NodeSelected[object]) -> None:
        event.stop()
        if event.node.data is _ShowMoreSentinel:
            event.node.remove()
            assert event.node.parent is not None, "Show more node should have a parent"
            self._populate_node(event.node.parent, load_more=True)

    @property
    def AAA_deal_with_it(self) -> dict[str, Any]:
        """This property gives a grab bag of different types to test the tree."""
        from enum import Enum
        from typing import NamedTuple
        import traceback
        return {
            "a_string": "DEAL WITH IT 😎",
            "an_int": 42,
            "a_float": 3.14,
            "a_bool": True,
            "none": None,
            "a_list": ["a", "b", "c"],
            "a_tuple": ("a", "b", "c"),
            "a_named_tuple": NamedTuple("a_named_tuple", [("a", int), ("b", str), ("c", float)])(1, "2", 3.0),
            "a_set": {"a", "b", "c"},
            "a_frozenset": frozenset({"a", "b", "c"}),
            "a_dict": {"a": "A", "b": "B", "c": "C"},
            "a_dict_with_mixed_keys": {1: "A", "b": "B", Enum("an_enum", "a b c"): "C", frozenset(): "D"},
            "a_parameterized_generic": dict[str, int],
            "a_module": inspect,
            "a_function": lambda x: x,  # type: ignore
            "a_generator": (x for x in "abc"),
            "an_iterator": iter("abc"),
            "a_range": range(10),
            "a_slice": slice(1, 2, 3),
            "a_complex": 1 + 2j,
            "a_bytes": b"abc",
            "a_bytearray": bytearray(b"abc"),
            "an_enum": Enum("an_enum", "a b c"),
            "an_ellipsis": ...,
            "a_memoryview": memoryview(b"abc"),
            "not_implemented": NotImplemented,
            "an_exception": Exception("hello"),
            "a_type": type,
            "a_code": compile("print('hello')", "<string>", "exec"),
            "a_frame": inspect.currentframe(),
            "a_traceback": traceback.extract_stack(),
        }
    
    @property
    def AAA_test_property_that_raises_exception(self) -> str:
        raise Exception("EMIT: Error Message Itself Test; uncomment and navigate to this node to see the error message")

    def _populate_node(self, node: TreeNode[object], load_more: bool = False) -> None:
        data: object = node.data
        if data is None:
            return

        if node not in self._already_loaded:
            self._already_loaded[node] = set()

        max_keys = 100
        if load_more:
            max_keys += len(self._already_loaded[node])

        def key_filter(key: str) -> bool:
            # TODO: allow toggling filtering of private properties
            # (or show in a collapsed node)
            return not key.startswith("_")

        index = 0
        def add_node_with_limit(key: str, value: object, exception: Exception | None = None) -> bool:
            """Add a node to the tree, or return True if the max number of nodes has been reached."""
            PropertiesTree._add_property_node(node, str(key), value, exception)
            self._already_loaded[node].add(str(key))
            nonlocal index
            index += 1
            if index >= max_keys:
                node.add("...", _ShowMoreSentinel).allow_expand = False
                return True
            return False
        
        def safe_dir_items(obj: object) -> Iterable[tuple[str, object, Exception | None]]:
            """Yields tuples of (key, value, error) for each key in dir(obj)."""
            # for key, value in obj.__dict__.items():
            # inspect.getmembers is better than __dict__ because it includes getters
            # except it can raise errors from any of the getters, and I need more granularity
            # for key, value in inspect.getmembers(obj):
            # TODO: handle DynamicClassAttributes like inspect.getmembers does
            for key in dir(obj):
                try:
                    yield (key, getattr(obj, key), None)
                except Exception as e:
                    yield (key, None, e)

        def with_no_error(key_val: tuple[str, object]) -> tuple[str, object, None]:
            return (key_val[0], key_val[1], None)

        iterator: Iterable[tuple[str, object, Exception | None]]

        # Dictionaries are iterable, but we want key-value pairs, not index-key pairs
        if isinstance(data, dict):
            iterator = map(with_no_error, data.items())  # type: ignore
        # Prefer dir() for NamedTuple, but enumerate() for lists (and tentatively all other iterables)
        elif isinstance(data, Iterable) and not hasattr(data, "_fields"):  # type: ignore
            iterator = map(with_no_error, enumerate(data))  # type: ignore
        else:
            iterator = safe_dir_items(data)  # type: ignore
        
        for key, value, error in iterator:
            if not key_filter(str(key)):
                continue
            if str(key) in self._already_loaded[node]:
                continue
            if add_node_with_limit(key, value, error):
                break

    @classmethod
    def _add_property_node(cls, parent_node: TreeNode[object], name: str, data: object, exception: Exception | None = None) -> None:
        """Adds data to a node.

        Based on https://github.com/Textualize/textual/blob/65b0c34f2ed6a69795946a0735a51a463602545c/examples/json_tree.py

        Args:
            parent_node (TreeNode): A Tree node to add a child to.
            name (str): The key that the data is associated with.
            data (object): Any object ideally should work.
        """

        node = parent_node.add(name, data)

        def with_name(text: Text) -> Text:
            return Text.assemble(
                Text.from_markup(f"[b]{escape(name)}[/b]="), text
            )

        if exception is not None:
            node.allow_expand = False
            node.set_label(with_name(Text.from_markup(f"[i][#808080](getter error: [red]{escape(repr(exception))}[/red])[/#808080][/i]")))
        elif isinstance(data, (list, set, frozenset, tuple)):
            length = len(data)  # type: ignore
            # node.set_label(Text(f"{name} ({length})"))
            # node.set_label(with_name(PropertiesTree.highlighter(repr(data))))
            # node.set_label(Text.assemble(
            #     Text.from_markup(f"[#808080]({length})[/#808080] "),
            #     with_name(PropertiesTree.highlighter(repr(data))),
            # ))
            # node.set_label(Text.assemble(
            #     with_name(PropertiesTree.highlighter(repr(data))),
            #     Text.from_markup(f" [#808080]({length})[/#808080]"),
            # ))
            # In the middle I think is best, although it's the most complicated:
            node.set_label(Text.assemble(
                Text.from_markup(f"[b]{escape(name)}[/b]"),
                Text.from_markup(f"[#808080]({length})[/#808080]"),
                Text("="),
                PropertiesTree.highlighter(repr(data))
            ))
            # Can I perhaps DRY with with_name() with with_name taking a length parameter? In other words:
            # Can I perhaps DRY with with_name() with with_name() with with_name(text, length) as the parameters?
        elif isinstance(data, (str, bytes, int, float, bool, type(None))):
            node.allow_expand = False
            node.set_label(with_name(PropertiesTree.highlighter(repr(data))))
        elif callable(data):
            # node.set_label(Text(f"{type(data).__name__} {name}"))
            node.remove()
        elif hasattr(data, "__dict__") or hasattr(data, "__slots__") or isinstance(data, dict):
            node.set_label(with_name(PropertiesTree.highlighter(repr(data))))
        else:
            node.allow_expand = False
            node.set_label(with_name(PropertiesTree.highlighter(repr(data))))



class NodeInfo(Container):

    dom_node: var[DOMNode | None] = var[Optional[DOMNode]](None)
    """The DOM node being inspected."""

    def compose(self) -> ComposeResult:
        """Add sub-widgets."""
        with TabbedContent(initial="properties"):
            with TabPane("Props", id="properties"):
                yield PropertiesTree("", classes="properties")
                yield Static("", classes="properties_nothing_selected")
            with TabPane("CSS", id="styles"):
                yield VerticalScroll(Static(classes="styles"))
            with TabPane("Keys", id="key_bindings"):
                yield VerticalScroll(Static(classes="key_bindings"))
            with TabPane("Events", id="events"):
                yield VerticalScroll(Static(classes="events"))

    def watch_dom_node(self, dom_node: DOMNode | None) -> None:
        """Update the info displayed when the DOM node changes."""
        print("watch_dom_node", dom_node)
        properties_tree = self.query_one(PropertiesTree)
        properties_static = self.query_one(".properties_nothing_selected", Static)
        styles_static = self.query_one(".styles", Static)
        key_bindings_static = self.query_one(".key_bindings", Static)
        events_static = self.query_one(".events", Static)

        if dom_node is None:
            nothing_selected_message = "Nothing selected"
            properties_tree.display = False
            properties_static.display = True
            properties_tree.reset("", None)
            properties_static.update(nothing_selected_message)
            styles_static.update(nothing_selected_message)
            key_bindings_static.update(nothing_selected_message)
            events_static.update(nothing_selected_message)
            return

        properties_tree.display = True
        properties_static.display = False
        properties_tree.reset(dom_node.css_identifier_styled, dom_node)
        # trigger _on_tree_node_expanded to load the first level of properties
        properties_tree.root.collapse()
        properties_tree.root.expand()

        # styles_static.update(dom_node.css_tree)
        # styles_static.update(dom_node._css_styles.css)
        styles_static.update(dom_node.styles.css)
        # styles_static.update(Syntax(f"all styles {{\n{dom_node.styles.css}\n}}", "css"))

        # key_bindings_static.update("\n".join(map(repr, dom_node.BINDINGS)) or "(None defined with BINDINGS)")
        highlighter = ReprHighlighter()
        key_bindings_static.update(Text("\n").join(map(lambda binding: highlighter(repr(binding)), dom_node.BINDINGS)) or "(None defined with BINDINGS)")

        # For events, look for class properties that are subclasses of Message
        # to determine what events are available.
        # TODO: also include built-in events not defined on a widget class
        # Also, there's plenty of UI work to do here.
        # Should it separate posted vs handled events?
        # Documentation strings could go in tooltips or otherwise be abbreviated.
        # Source code links could go in tooltips, which might help to prevent line-
        # breaks, which break automatic <file>:<line> linking (Ctrl+Click support) in VS Code.
        available_events: list[Type[Message]] = []
        for cls in type(dom_node).__mro__:
            for value in cls.__dict__.values():
                if isinstance(value, type) and issubclass(value, Message):
                    available_events.append(value)
        def message_info(message_class: Type[Message]) -> str:
            """Return a description of a message class, listing any handlers."""
            # A. Ideally Message would have a static method that returns the handler name.
            # B. I tried constructing a message instance and getting the handler name from that,
            #    with `message_class()._handler_name`, but:
            #    1. this could have side effects,
            #    2. this uses a private property, and
            #    3. __init__ needs parameters, different for different message types.
            #       (Constructing the base class and finagling it to use the subclass's namespace/name
            #        might be possible, but seems like a lot of work for a fragile hack.)
            # C. Duplicate the code from `Message.__init__`. It's not much code, since we can import camel_to_snake,
            #    although I'm not sure the module is meant to be public, it's sort of just a helper.)
            name = camel_to_snake(message_class.__name__)
            handler_name = f"on_{message_class.namespace}_{name}" if message_class.namespace else f"on_{name}"
            # Find any listeners for this event
            # TODO: only look upwards if the event bubbles
            usages: list[str] = []
            for ancestor in dom_node.ancestors_with_self:
                if hasattr(ancestor, handler_name):
                    # Record which class the handler is defined on
                    # Not sure which order would be needed here
                    # for cls in type(ancestor).__mro__:
                    #     if hasattr(cls, handler_name):
                    #         ...
                    #         break
                    # But there's a simpler way: method.__self__.__class__
                    handler = getattr(ancestor, handler_name)
                    defining_class = handler.__self__.__class__
                    try:
                        line_number = inspect.getsourcelines(handler)[1]
                        file = inspect.getsourcefile(handler)
                        if file is None:
                            def_location = f"(unknown location)"
                        else:
                            # def_location = f"{file}:{line_number}"
                            # def_location = f"[link=file://{file}]{file}:{line_number}[/link]"
                            # def_location = f"{file}:{line_number} [link=file://{file}](open)[/link]"
                            # I'm including the line number here hoping that SOME editor will use it.
                            # TODO: button to execute a command to open the file in an editor
                            # (configurable? magical? or with a button for each known editor?)
                            file_uri = pathlib.Path(file).as_uri() + "#" + str(line_number)
                            def_location = f"{file}:{line_number} [link={file_uri}](open file)[/link]"
                    except OSError as e:
                        def_location = f"(error getting location: {e})"
                    # TODO: link to the DOM node in the tree that has the listener
                    # Also, what should I name the variables here?
                    # I've invented a term "grand ancestor" to distinguish from "ancestor",
                    # which is kind of fun, but... maybe not the clearest.
                    # (meta_ancestor? super_ancestor? ancestor_ancestor? ancestor_for_path?)
                    dom_path = " > ".join([grand_ancestor.css_identifier for grand_ancestor in ancestor.ancestors_with_self])
                    handler_qualname = f"{defining_class.__qualname__}.{handler_name}"
                    usages.append(f"Listener on DOM node: {dom_path}\n\n{handler_qualname}\n{def_location}")
            if usages:
                usage_info = "\n\n".join(usages)
            else:
                usage_info = f"No listeners found for {handler_name}"
            
            # TODO: link to source code for the message class
            return f"[b]{message_class.__qualname__}[/b]\n[#808080]{message_class.__doc__ or '(No docstring)'}[/#808080]\n{usage_info}\n"

        if available_events:
            events_static.update("\n".join(map(message_info, available_events)))
            # events_static.update("\n".join(map(repr, available_events)))
        else:
            events_static.update(f"(No message types exported by {type(dom_node).__name__!r} or its superclasses)")


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

ALLOW_INSPECTING_INSPECTOR = True
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
    Inspector Button.inspect_button {
        margin: 1;
        width: 1fr;
    }
    Inspector Button.inspect_button.picking {
        color: $accent;
    }
    Inspector DOMTree {
        height: 1fr;
        scrollbar-gutter: stable;
    }
    Inspector NodeInfo,
    Inspector TabbedContent,
    Inspector ContentSwitcher,
    Inspector TabPane,
    Inspector TabPane > VerticalScroll {
        width: 1fr !important;
        height: 1fr !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    Inspector Static {
        margin-bottom: 1;
    }
    """

    picking = var(False)
    """Whether the user is picking a widget to inspect."""

    def __init__(self):
        """Initialise the inspector."""

        super().__init__()

        self._highlight: Container | None = None
        """A simple widget that highlights the widget being inspected."""
        self._highlight_styles: dict[Widget, OriginalStyles] = {}
        """Stores the original styles of any Hovered widgets."""

    def compose(self) -> ComposeResult:
        """Add sub-widgets."""
        inspect_icon = "⇱" # Alternatives: 🔍 🎯 🮰 🮵 ⮹ ⇱ 🢄 🡴 🡤 🡔 🢰 (↖️ arrow emoji unreliable)
        # expand_icon = "+" # Alternatives: + ⨁ 🪜 🎊 🐡 🔬 (↕️ arrow emoji unreliable)
        yield Button(f"{inspect_icon} Inspect Element", classes="inspect_button")
        # yield Button(f"{expand_icon} Expand All Visible", classes="expand_all_button")
        yield DOMTree(self.app)  # type: ignore
        yield NodeInfo()

    def watch_picking(self, picking: bool) -> None:
        """Watch the picking variable."""
        self.reset_highlight()
        if picking:
            self.capture_mouse()
        else:
            self.release_mouse()
        self.query_one(".inspect_button", Button).set_class(picking, "picking")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle a button being clicked."""
        if event.button.has_class("expand_all_button"):
            self.query_one(DOMTree).root.expand_all()
        elif event.button.has_class("inspect_button"):
            self.picking = not self.picking

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Handle the mouse moving."""
        if not self.picking:
            return
        self.highlight(self.get_widget_under_mouse(event.screen_offset))

    def get_widget_under_mouse(self, screen_offset: Offset) -> Widget | None:
        try:
            leaf_widget, _ = self.app.get_widget_at(*screen_offset)  # type: ignore
        except NoWidget:
            return None
        if self in leaf_widget.ancestors_with_self and not ALLOW_INSPECTING_INSPECTOR:
            return None
        return leaf_widget

    async def on_mouse_down(self, event: events.MouseDown) -> None:
        """Handle the mouse being pressed."""
        self.reset_highlight()
        if not self.picking:
            return
        leaf_widget = self.get_widget_under_mouse(event.screen_offset)
        self.picking = False

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
