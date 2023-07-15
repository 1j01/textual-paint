from typing import Any, Callable

from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.geometry import Offset
from textual.message import Message
from textual.reactive import reactive, var
from textual.strip import Strip
from textual.color import Color as Color
from textual.widget import Widget
from textual.widgets import Button, Input, Label
from textual.containers import Container

from .localization.i18n import get as _
from .windows import DialogWindow


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

    class Changed(Message):
        """A message that is sent when the selected color changes."""
        
        def __init__(self, color: str, color_grid: "ColorGrid", index: int) -> None:
            """Initialize the message."""
            super().__init__()
            self.color = color
            self.color_grid = color_grid
            self.index = index

    color_list: var[list[str]] = var(list[str], init=False)
    """The list of colors to display. NOT TO BE CONFUSED WITH `colors` defined by `Widget`."""

    def __init__(self, color_list: list[str], selected_color: str, **kwargs: Any) -> None:
        """Initialize the ColorGrid."""
        super().__init__(**kwargs)
        self.selected_color: str = selected_color
        self._color_by_button: dict[Button, str] = {}
        self.color_list = color_list  # This immediately calls `watch_color_list`.
        self.can_focus = True
    
    def on_mount(self) -> None:
        """Called when the window is mounted."""
        found_match = False
        for button, color in self._color_by_button.items():
            matches = Color.parse(color) == Color.parse(self.selected_color)
            if matches and not found_match:
                button.add_class("focused")
                found_match = True
        self._select_focused_color()

    def watch_color_list(self, color_list: list[str]) -> None:
        """Called when the color list changes."""
        self._color_by_button = {}
        for button in self.query(Button):
            button.remove()
        for color in self.color_list:
            button = Button("", classes="color_button color_well")
            button.styles.background = color
            button.can_focus = False  # using fake focus for now
            self._color_by_button[button] = color
            self.mount(button)

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
            self._navigate_absolute(len(self.color_list) - 1)
        elif event.key in ("space", "enter"):
            self._select_focused_color()
    
    def _select_focused_color(self) -> None:
        try:
            focused = self.query_one(".focused", Button)
        except NoMatches:
            return
        for selected in self.query(".selected"):
            selected.remove_class("selected")
        focused.add_class("selected")
        self.selected_color = self._color_by_button[focused]
        index = list(self._color_by_button.keys()).index(focused)
        self.post_message(self.Changed(self.selected_color, self, index))
    
    def _navigate_relative(self, delta: int) -> None:
        """Navigate to a color relative to the currently focused color."""
        try:
            focused = self.query_one(".focused", Button)
        except NoMatches:
            return
        # index = self._colors.index(self._color_by_button[focused]) # doesn't work because there can be duplicates
        index = list(self._color_by_button.keys()).index(focused)
        # print(delta, (index % num_colors_per_row), num_colors_per_row)
        if delta == -1 and (index % num_colors_per_row) == 0:
            return
        if delta == +1 and (index % num_colors_per_row) == num_colors_per_row - 1:
            return
        self._navigate_absolute(index + delta)

    def _navigate_absolute(self, index: int) -> None:
        """Navigate to the color at the given index."""
        if index < 0 or index >= len(self.color_list):
            return
        target_button = list(self._color_by_button.keys())[index]
        target_button.add_class("focused")
        for button in self._color_by_button:
            button.remove_class("focused")
        target_button.add_class("focused")
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        self.selected_color = self._color_by_button[event.button]
        for button in self._color_by_button:
            button.remove_class("focused")
        event.button.add_class("focused")
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

class LuminosityRamp(Widget):
    """A vertical slider to select a luminosity, previewing the color at each luminosity with a gradient."""

    class Changed(Message):
        """A message that is sent when the luminosity changes."""

        def __init__(self, luminosity: float) -> None:
            """Initialize the Changed message."""
            super().__init__()
            self.luminosity = luminosity


    hue = reactive(0.0)
    saturation = reactive(0.0)
    luminosity = reactive(0.0)

    def __init__(self, hue: float, saturation: float, luminosity: float, **kwargs: Any) -> None:
        """Initialize the LuminosityRamp."""
        super().__init__(**kwargs)
        self.luminosity = luminosity
        self.hue = hue
        self.saturation = saturation
        self._mouse_down = False

    def render_line(self, y: int) -> Strip:
        """Render a line of the widget."""
        marker = "◀" # ◀ (bigger/clearer) or 🢐 (closer shape but smaller)
        # lum = y / self.size.height # bottom isn't quite white
        lum = 1 - y / (self.size.height - 1)
        color = Color.from_hsl(self.hue, self.saturation, lum)
        style = Style(bgcolor=color.rich_color)
        segments = [Segment(" " * (self.size.width - 1), style, None)]
        if y == round((self.size.height - 1) * (1 - self.luminosity)):
            segments.append(Segment(marker, Style(color="black"), None))
        return Strip(segments)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Called when the mouse is pressed down."""
        self._update_color(event.y)
        self._mouse_down = True
        self.capture_mouse()
    
    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Called when the mouse is released."""
        self.release_mouse()
        self._mouse_down = False

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Called when the mouse is moved."""
        if self._mouse_down:
            self._update_color(event.y)
    
    def _update_color(self, y: int) -> None:
        """Update the color based on the given y coordinate."""
        self.luminosity = max(0, min(1, 1 - y / (self.size.height - 1)))
        self.post_message(self.Changed(luminosity=self.luminosity))
        # self.refresh()

class ColorField(Widget):
    """A field of hue and saturation, where you can pick a color by clicking."""

    class Changed(Message):
        """A message that is sent when the color changes."""

        def __init__(self, hue: float, saturation: float) -> None:
            """Initialize the Changed message."""
            super().__init__()
            self.hue = hue
            self.saturation = saturation

    hue = reactive(0.0)
    saturation = reactive(0.0)

    def __init__(self, hue: float, saturation: float, **kwargs: Any) -> None:
        """Initialize the ColorField."""
        super().__init__(**kwargs)
        self.hue = hue
        self.saturation = saturation
        self._mouse_down = False

    def render_line(self, y: int) -> Strip:
        """Render a line of the widget."""
        segments: list[Segment] = []
        crosshair = "✜" # Options: ┼+✜✛⊹✚╋╬⁘⁛⌖⯐ or
        #  ╻
        # ╺ ╸
        #  ╹
        for x in range(self.size.width):
            crosshair_here = (
                x == round(self.hue * (self.size.width - 1)) and
                y == round((self.size.height - 1) * (1 - self.saturation))
            )
            color = Color.from_hsl(x / (self.size.width - 1), 1 - y / (self.size.height - 1), 0.5)
            char = crosshair if crosshair_here else " "
            segments.append(Segment(char, Style(color="black", bgcolor=color.rich_color), None))
        return Strip(segments)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Called when the mouse is pressed down."""
        self._update_color(event.offset)
        self._mouse_down = True
        self.capture_mouse()
    
    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Called when the mouse is released."""
        self.release_mouse()
        self._mouse_down = False

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Called when the mouse is moved."""
        if self._mouse_down:
            self._update_color(event.offset)
    
    def _update_color(self, offset: Offset) -> None:
        """Update the color based on the given offset."""
        x, y = offset
        self.hue = max(0, min(1, x / (self.size.width - 1)))
        self.saturation = max(0, min(1, 1 - y / (self.size.height - 1)))
        self.post_message(self.Changed(hue=self.hue, saturation=self.saturation))
        # self.refresh()

class ColorPreview(Widget):
    """A preview of the selected color. This doesn't really need to be a special widget..."""

    color: reactive[str] = reactive("black")

    def __init__(self, color: str, **kwargs: Any) -> None:
        """Initialize the ColorPreview."""
        super().__init__(**kwargs)
        self.color = color

    def render_line(self, y: int) -> Strip:
        """Render a line of the widget."""
        return Strip([Segment(" " * self.size.width, Style(bgcolor=self.color), None)])

class IntegerInput(Input):
    """An input that only accepts integers."""

    def __init__(self, min: int, max: int, **kwargs: Any) -> None:
        """Initialize the IntegerInput."""
        super().__init__(**kwargs)
        self.min = min
        self.max = max
        self.last_valid_int = 0
    
    def _track_valid_int(self, value: str) -> int:
        try:
            value_as_int = int(value)
        except ValueError:
            return self.last_valid_int
        value_as_int = max(self.min, min(self.max, value_as_int))
        self.last_valid_int = value_as_int
        return value_as_int

    def validate_value(self, value: str) -> str:
        """Validate the given value."""
        if not value:
            # Allow empty string
            return value
        return str(self._track_valid_int(value))

    def on_blur(self, event: events.Blur) -> None:
        """Called when the input loses focus. Resets the input if empty."""
        if not self.value:
            self.value = str(self.last_valid_int)

class EditColorsDialogWindow(DialogWindow):
    """A dialog window that lets the user select a color."""

    def __init__(self, *children: Widget, title: str = _("Edit Colors"), selected_color: str|None, handle_selected_color: Callable[[str], None], **kwargs: Any) -> None:
        """Initialize the Edit Colors dialog."""
        super().__init__(handle_button=self.handle_button, *children, title=title, **kwargs)
        self.hue_degrees = 0.0
        self.sat_percent = 0.0
        self.lum_percent = 0.0
        # self._initial_color = selected_color
        if selected_color:
            self._current_color = selected_color
        self._color_by_button: dict[Button, str] = {}
        self._inputs_by_letter: dict[str, IntegerInput] = {}
        self._custom_colors_index = 0
        self.handle_selected_color = handle_selected_color
    
    def handle_button(self, button: Button) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        if button.has_class("cancel"):
            self.request_close()
        elif button.has_class("ok"):
            self.handle_selected_color(self._current_color.hex)
        elif button.has_class("add_to_custom_colors"):
            global custom_colors
            custom_colors = custom_colors[:]  # copy so that watch_color_list gets called
            # (it uses reference equality; an alternative would be to set always_update=True)
            custom_colors[self._custom_colors_index] = self._current_color.hex
            self.custom_colors_grid.color_list = custom_colors
            self._custom_colors_index = (self._custom_colors_index + 1) % len(custom_colors)

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        self.basic_colors_grid = ColorGrid(basic_colors, self._current_color.hex, classes="autofocus")
        self.custom_colors_grid = ColorGrid(custom_colors, self._current_color.hex)
        verticals_for_inputs: list[Vertical] = []
        for color_model in ["hsl", "rgb"]:
            input_containers: list[Container] = []
            for component_letter in color_model:
                text_with_hotkey: str = {
                    "h": _("Hu&e:"),
                    "s": _("&Sat:"),
                    "l": _("&Lum:"),
                    "r": _("&Red:"),
                    "g": _("&Green:"),
                    "b": _("Bl&ue:"),
                }[component_letter]
                text_without_hotkey = text_with_hotkey.replace("&", "")
                max_value: int = {
                    "h": 360,
                    "s": 100,
                    "l": 100,
                    "r": 255,
                    "g": 255,
                    "b": 255,
                }[component_letter]
                min_value: int = 0
                input = IntegerInput(min_value, max_value, name=component_letter)
                label = Label(text_without_hotkey)
                container = Container(label, input, classes="input_container")
                input_containers.append(container)
                self._inputs_by_letter[component_letter] = input
            verticals_for_inputs.append(Vertical(*input_containers))

        self.content.mount(
            Horizontal(
                Vertical(
                    Label(_("Basic Colors")),
                    self.basic_colors_grid,
                    Label(_("Custom Colors")),
                    self.custom_colors_grid,
                ),
                Vertical(
                    Horizontal(
                        ColorField(self.hue_degrees / 360, self.sat_percent / 100),
                        LuminosityRamp(self.hue_degrees / 360, self.sat_percent / 100, self.lum_percent / 100),
                    ),
                    Horizontal(
                        Vertical(
                            ColorPreview("black"),
                            Label(_("Color")),
                            classes="color_preview_area",
                        ),
                        *verticals_for_inputs,
                    ),
                    Button(_("Add to Custom Colors"), classes="add_to_custom_colors"),
                ),
            ),
            Container(
                Button(_("OK"), classes="ok submit", variant="primary"),
                Button(_("Cancel"), classes="cancel"),
                classes="buttons",
            )
        )

        self._update_inputs("hslrgb")

    def on_color_grid_changed(self, event: ColorGrid.Changed) -> None:
        """Called when the user selects a color from the grid."""
        self._current_color = event.color
        self._update_inputs("hslrgb")
        self._update_color_preview()
        if event.color_grid is self.custom_colors_grid:
            self._custom_colors_index = event.index
        # This is a little awkward, removing .selected for other grids here, but
        # for the clicked grid in the ColorGrid widget itself.
        for color_grid in self.query(ColorGrid):
            if event.color_grid is not color_grid:
                for button in color_grid.query(Button):
                    button.remove_class("selected")

    def on_luminosity_ramp_changed(self, event: LuminosityRamp.Changed) -> None:
        """Called when dragging the luminosity slider."""
        self.lum_percent = event.luminosity * 100
        self._update_inputs("lrgb")
        self._update_color_preview()

    def on_color_field_changed(self, event: ColorField.Changed) -> None:
        """Called when dragging the color field."""
        self.hue_degrees = event.hue * 360
        self.sat_percent = event.saturation * 100
        self._update_inputs("hsrgb")
        self._update_color_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Called when an input changes."""
        component_letter = event.input.name
        if component_letter is None:
            return
        assert isinstance(event.input, IntegerInput)
        value = event.input.last_valid_int
        if component_letter in "hsl":
            if component_letter == "h":
                self.hue_degrees = value
            elif component_letter == "s":
                self.sat_percent = value
            else:
                self.lum_percent = value
            self._update_inputs("rgb")
        else:
            rgb = list(self._current_color.rgb)
            rgb["rgb".index(component_letter)] = value
            self._current_color = Color(*rgb)
            self._update_inputs("hsl")
        self._update_color_preview()

    @property
    def _current_color(self) -> Color:
        """Get the current color."""
        return Color.from_hsl(self.hue_degrees / 360, self.sat_percent / 100, self.lum_percent / 100)

    @_current_color.setter
    def _current_color(self, color: Color | str) -> None:
        """Set the color values from the given textual.color.Color object or string."""
        if isinstance(color, str):
            color = Color.parse(color)
        hue, sat, lum = color.hsl
        self.hue_degrees = hue * 360
        self.sat_percent = sat * 100
        self.lum_percent = lum * 100

    def _update_inputs(self, component_letters: str) -> None:
        """Update the inputs for the given component letters."""
        with self.prevent(Input.Changed):
            for component_letter in component_letters:
                input = self._inputs_by_letter[component_letter]
                input.value = str(int({
                    "h": self.hue_degrees,
                    "s": self.sat_percent,
                    "l": self.lum_percent,
                    "r": self._current_color.rgb[0],
                    "g": self._current_color.rgb[1],
                    "b": self._current_color.rgb[2],
                }[component_letter]))

    def _update_color_preview(self) -> None:
        """Update the color preview."""
        self.query_one(ColorPreview).color = self._current_color.hex
        luminosity_ramp = self.query_one(LuminosityRamp)
        color_field = self.query_one(ColorField)
        luminosity_ramp.luminosity = self.lum_percent / 100
        luminosity_ramp.hue = self.hue_degrees / 360
        luminosity_ramp.saturation = self.sat_percent / 100
        color_field.hue = self.hue_degrees / 360
        color_field.saturation = self.sat_percent / 100
