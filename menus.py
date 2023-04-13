import re
from enum import Enum
from typing import List
from textual import events
from textual.message import Message, MessageTarget
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.geometry import Offset, Region, Size
from textual.reactive import var, reactive
from textual.widget import Widget
from textual.widgets import Button, Static

def to_snake_case(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    name = re.sub('__([A-Z])', r'_\1', name)
    name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)
    return name.lower()

class Menu(Container):
    """A menu widget."""

    items = var([])
    focus_index = var(0)

    def __init__(self, items: List[str], **kwargs) -> None:
        """Initialize a menu."""
        super().__init__(**kwargs)
        self.add_class("menu")
        self.items = items
        for item in items:
            if not hasattr(item, "id"):
                item.id = "menu_item_" + to_snake_case(item.name)

    def compose(self) -> ComposeResult:
        """Define widget structure."""
        for item in self.items:
            if item.type == "separator":
                yield Static("─" * 20, classes="menu_separator")
            else:
                yield Button(item.name, id=item.id, classes="menu_item")

    def on_key(self, event: events.Key) -> None:
        """Called when the user presses a key."""

        if event.key == "up":
            self.focus_index -= 1
            if self.focus_index < 0:
                self.focus_index = len(self.items) - 1
        elif event.key == "down":
            self.focus_index += 1
            if self.focus_index >= len(self.items):
                self.focus_index = 0
        elif event.key == "enter":
            if self.items[self.focus_index].action:
                self.items[self.focus_index].action()
            # elif self.items[self.focus_index].submenu:
            #     self.items[self.focus_index].submenu.open()

class MenuBar(Menu):
    """A menu bar widget."""

    def __init__(self, items: List[str], **kwargs) -> None:
        """Initialize a menu bar."""
        super().__init__(items, **kwargs)
        self.add_class("menu_bar")


class MenuItem:
    """A menu item."""

    def __init__(self, name: str, action = None, type: str = "item", submenu = None) -> None:
        """Initialize a menu item."""
        self.name = name
        self.action = action
        self.type = type
        self.submenu = submenu

class Separator(MenuItem):
    """A menu separator."""

    def __init__(self) -> None:
        """Initialize a menu separator."""
        super().__init__("", None, "separator")
