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
        self.parent_menu = None

    def watch_items(self, old_items, new_items: List[str]) -> None:
        """Update the menu items."""
        for item in old_items:
            self.unmount(item)
        for item in new_items:
            self.mount(item)
            if item.submenu:
                self.app.mount(item.submenu)
                item.submenu.close()

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
        elif event.key == "escape":
            self.close()
            self.parent_menu.focus()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is clicked or activated with the keyboard."""

        button_id = event.button.id
        assert button_id is not None

        if button_id.startswith("menu_item_"):
            if event.button.action:
                event.button.action()
                root_menu = self
                while root_menu.parent_menu:
                    root_menu = root_menu.parent_menu
                root_menu.close()
            elif event.button.submenu:
                was_open = event.button.submenu.display
                for item in self.items:
                    if item.submenu:
                        item.submenu.close()
                if not was_open:
                    event.button.submenu.open(self)

    def open(self, parent_menu):
        self.display = True
        if len(self.items) > 0:
            self.items[0].focus()
        self.parent_menu = parent_menu
        self.add_class("menu_popup")
    
    def close(self):
        for item in self.items:
            if item.submenu:
                item.submenu.close()
        if not isinstance(self, MenuBar):
            self.display = False

class MenuBar(Menu):
    """A menu bar widget."""

    def __init__(self, items: List[str], **kwargs) -> None:
        """Initialize a menu bar."""
        super().__init__(items, **kwargs)
        self.add_class("menu_bar")


class MenuItem(Button):
    """A menu item widget."""

    def __init__(self, name: str, action = None, id: str = None, submenu = None, **kwargs) -> None:
        """Initialize a menu item."""
        super().__init__(name, **kwargs)
        self.add_class("menu_item")
        self.action = action
        self.submenu = submenu
        if id:
            self.id = id
        else:
            self.id = "menu_item_" + to_snake_case(name)

class Separator(Static):
    """A menu separator widget."""

    def __init__(self, **kwargs) -> None:
        """Initialize a separator."""
        super().__init__("", **kwargs)
        self.add_class("separator")