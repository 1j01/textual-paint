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
from localization.i18n import markup_hotkey, get_direction

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
            if self.parent_menu:
                self.parent_menu.focus()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is clicked or activated with the keyboard."""

        if isinstance(event.button, MenuItem):
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
                    event.button.submenu.open(self, event.button)

    def open(self, parent_menu, parent_menu_item):
        self.display = True
        if len(self.items) > 0:
            self.items[0].focus()
        self.parent_menu = parent_menu
        self.parent_menu_item = parent_menu_item
        self.add_class("menu_popup")

        if parent_menu.has_class("menu_bar"):
            self.styles.offset = (parent_menu_item.region.x, parent_menu_item.region.y + parent_menu_item.region.height)
        else:
            # JS code for reference
            # https://github.com/1j01/os-gui/blob/bb4df0f0c26969c089858118130975cd137cdac8/MenuBar.js#L618-L644
            # submenu_popup_el corresponds to self
            # submenu_popup_rect corresponds to self.region
            # rect corresponds to parent_menu_item.region
            # scroll offset doesn't apply here

            # const rect = item_el.getBoundingClientRect();
            # let submenu_popup_rect = submenu_popup_el.getBoundingClientRect();
            # submenu_popup_el.style.left = `${(get_direction() === "rtl" ? rect.left - submenu_popup_rect.width : rect.right) + window.scrollX}px`;
            # submenu_popup_el.style.top = `${rect.top + window.scrollY}px`;
            # submenu_popup_rect = submenu_popup_el.getBoundingClientRect();
            # if (get_direction() === "rtl") {
            #     if (submenu_popup_rect.left < 0) {
            #         submenu_popup_el.style.left = `${rect.right}px`;
            #         submenu_popup_rect = submenu_popup_el.getBoundingClientRect();
            #         if (submenu_popup_rect.right > innerWidth) {
            #             submenu_popup_el.style.left = `${innerWidth - submenu_popup_rect.width}px`;
            #         }
            #     }
            # } else {
            #     if (submenu_popup_rect.right > innerWidth) {
            #         submenu_popup_el.style.left = `${rect.left - submenu_popup_rect.width}px`;
            #         submenu_popup_rect = submenu_popup_el.getBoundingClientRect();
            #         if (submenu_popup_rect.left < 0) {
            #             submenu_popup_el.style.left = "0";
            #         }
            #     }
            # }

            rect = parent_menu_item.region
            self.styles.offset = (
                rect.x - self.region.width if get_direction() == "rtl" else rect.x + rect.width,
                rect.y
            )
            if get_direction() == "rtl":
                if self.region.x < 0:
                    self.styles.offset = (rect.x + rect.width, rect.y)
                    if self.region.x + self.region.width > self.screen.size.width:
                        self.styles.offset = (self.screen.size.width - self.region.width, rect.y)
            else:
                if self.region.x + self.region.width > self.screen.size.width:
                    self.styles.offset = (rect.x - self.region.width, rect.y)
                    if self.region.x < 0:
                        self.styles.offset = (0, rect.y)

        # Find the widest label
        max_width = 0
        for item in self.items:
            if isinstance(item, MenuItem):
                if len(item.label.plain) > max_width:
                    max_width = len(item.label.plain)
        # Split on tab character and align the shortcuts
        for item in self.items:
            if isinstance(item, MenuItem):
                markup_parts = item.label.markup.split("\t")
                plain_parts = item.label.plain.split("\t")
                if len(markup_parts) > 1:
                    item.label = markup_parts[0] + " " * (max_width - len(plain_parts[0])) + markup_parts[1]
    
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

    def __init__(self, name: str, action = None, id: str = None, submenu = None, grayed = False, **kwargs) -> None:
        """Initialize a menu item."""
        super().__init__(markup_hotkey(name), **kwargs)
        self.add_class("menu_item")
        self.disabled = grayed
        self.action = action
        self.submenu = submenu
        if isinstance(id, str):
            self.id = id
        elif id:
            self.id = "rc_" + str(id)
        else:
            self.id = "menu_item_" + to_snake_case(name)


mid_line = "─" * 100
class Separator(Static):
    """A menu separator widget."""


    def __init__(self, **kwargs) -> None:
        """Initialize a separator."""
        super().__init__(mid_line, **kwargs)
        self.add_class("separator")
        # self.disabled = True # This breaks scroll wheel over the separator, as of Textual 0.20.1
        self.disabled = False
        self.action = None
        self.submenu = None
