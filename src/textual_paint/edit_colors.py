from typing import Any, Callable
from textual import events, on
from textual.containers import Container
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Button
from textual.containers import Container
from localization.i18n import get as _
from windows import DialogWindow


# https://github.com/kouzhudong/win2k/blob/ce6323f76d5cd7d136b74427dad8f94ee4c389d2/trunk/private/shell/win16/comdlg/color.c#L38-L43
# These are a fallback in case colors are not received from some driver.
# const default_basic_colors = [
# 	"#8080FF", "#80FFFF", "#80FF80", "#80FF00", "#FFFF80", "#FF8000", "#C080FF", "#FF80FF",
# 	"#0000FF", "#00FFFF", "#00FF80", "#40FF00", "#FFFF00", "#C08000", "#C08080", "#FF00FF",
# 	"#404080", "#4080FF", "#00FF00", "#808000", "#804000", "#FF8080", "#400080", "#8000FF",
# 	"#000080", "#0080FF", "#008000", "#408000", "#FF0000", "#A00000", "#800080", "#FF0080",
# 	"#000040", "#004080", "#004000", "#404000", "#800000", "#400000", "#400040", "#800040",
# 	"#000000", "#008080", "#408080", "#808080", "#808040", "#C0C0C0", "#400040", "#FFFFFF",
# ];
# Grabbed with Color Cop from the screen with Windows 98 SE running in VMWare
basic_colors = [
	"#FF8080", "#FFFF80", "#80FF80", "#00FF80", "#80FFFF", "#0080FF", "#FF80C0", "#FF80FF",
	"#FF0000", "#FFFF00", "#80FF00", "#00FF40", "#00FFFF", "#0080C0", "#8080C0", "#FF00FF",
	"#804040", "#FF8040", "#00FF00", "#008080", "#004080", "#8080FF", "#800040", "#FF0080",
	"#800000", "#FF8000", "#008000", "#008040", "#0000FF", "#0000A0", "#800080", "#8000FF",
	"#400000", "#804000", "#004000", "#004040", "#000080", "#000040", "#400040", "#400080",
	"#000000", "#808000", "#808040", "#808080", "#408080", "#C0C0C0", "#400040", "#FFFFFF",
]
custom_colors = [
	"#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF",
	"#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF",
]

num_colors_per_row = 8

class ColorGrid(Container):
    """A grid of colors."""

    def __init__(self, colors: list[str], **kwargs: Any) -> None:
        """Initialize the ColorGrid."""
        super().__init__(**kwargs)
        self.selected_color: str = colors[0]
        self._color_by_button: dict[Button, str] = {}
        self._colors = colors
        self.can_focus = True

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        for color in self._colors:
            button = Button("", classes="color_button color_well")
            button.styles.background = color
            button.can_focus = False
            self._color_by_button[button] = color
            # if color is self._selected_color:
            #     button.focus()
            self.mount(button)
        self.focus_ring = Container(classes="focus_ring ring")
        self.selection_ring = Container(classes="selection_ring ring")
        self.mount(self.focus_ring)
        self.mount(self.selection_ring)

    def on_key(self, event: events.Key) -> None:
        """Called when a key is pressed."""
        if event.key == "up":
            self._navigate_relative(-num_colors_per_row)
        elif event.key == "down":
            self._navigate_relative(+num_colors_per_row)
        elif event.key == "left":
            self._navigate_relative(-1)
        elif event.key == "right":
            self._navigate_relative(+1)
        elif event.key == "home":
            self._navigate_absolute(0)
        elif event.key == "end":
            self._navigate_absolute(len(self._colors) - 1)
        elif event.key in ("space", "enter"):
            self._select_focused_color()
    
    def _select_focused_color(self) -> None:
        try:
            focused = self.query_one(".focused", Button)
        except NoMatches:
            return
        # for selected in self.query(".selected"):
        #     selected.remove_class("selected")
        # focused.add_class("selected")

        self.selection_ring.styles.offset = (focused.virtual_region.x - 1, focused.virtual_region.y - 1)
        self.selection_ring.styles.width = focused.region.width + 2
        self.selection_ring.styles.height = focused.region.height + 2

        self.selected_color = self._color_by_button[focused]
    
    def _navigate_relative(self, delta: int) -> None:
        """Navigate to a color relative to the currently focused color."""
        try:
            focused = self.query_one(".focused", Button)
        except NoMatches:
            return
        # index = self._colors.index(self._color_by_button[focused]) # doesn't work because there can be duplicates
        index = list(self._color_by_button.keys()).index(focused)
        print(delta, (index % num_colors_per_row), num_colors_per_row)
        if delta == -1 and (index % num_colors_per_row) == 0:
            return
        if delta == +1 and (index % num_colors_per_row) == num_colors_per_row - 1:
            return
        self._navigate_absolute(index + delta)

    def _navigate_absolute(self, index: int) -> None:
        """Navigate to the color at the given index."""
        if index < 0 or index >= len(self._colors):
            return
        target_button = list(self._color_by_button.keys())[index]
        # for button in self._color_by_button:
        #     button.remove_class("focused")
        # target_button.add_class("focused")
        
        self.focus_ring.styles.offset = (target_button.virtual_region.x - 1, target_button.virtual_region.y - 1)
        self.focus_ring.styles.width = target_button.region.width + 2
        self.focus_ring.styles.height = target_button.region.height + 2

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        self.selected_color = self._color_by_button[event.button]
        # for button in self._color_by_button:
        #     button.remove_class("focused")
        # event.button.add_class("focused")
        self._navigate_absolute(list(self._color_by_button.keys()).index(event.button))
        self._select_focused_color()
        self.focus()

    # I want MouseDown rather than Pressed in order to implement double-clicking.
    # However, event.control is None for mouse events, so this doesn't work:
    # def on_mouse_down(self, event: events.MouseDown) -> None:
    #     """Called when the mouse is pressed down."""
    #     if event.button == 1:
    #         self.selected_color = self._color_by_button[event.control]
    #         self.refresh()
    # @on(events.MouseDown, ".color_button")
    # def handle_color_button(self, event: events.MouseDown) -> None:
    #     """Called when a color button is clicked."""
    #     self.selected_color = self._color_by_button[event.control]

class EditColorsDialogWindow(DialogWindow):
    """A dialog window that lets the user select a color."""

    def __init__(self, *children: Widget, title: str = _("Edit Colors"), selected_color: str|None, handle_selected_color: Callable[[str], None], **kwargs: Any) -> None:
        """Initialize the Edit Colors dialog."""
        super().__init__(handle_button=self.handle_button, *children, title=title, **kwargs)
        self._color_to_highlight = selected_color
        self._color_by_button: dict[Button, str] = {}
        self.handle_selected_color = handle_selected_color
    
    def handle_button(self, button: Button) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        if button.has_class("cancel"):
            self.request_close()
        elif button.has_class("ok"):
            self.handle_selected_color(self.color_grid.selected_color)

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        self.color_grid = ColorGrid(basic_colors)
        self.content.mount(self.color_grid)
        self.content.mount(
            Container(
                Button(_("OK"), classes="ok submit", variant="primary"),
                Button(_("Cancel"), classes="cancel"),
                classes="buttons",
            )
        )
