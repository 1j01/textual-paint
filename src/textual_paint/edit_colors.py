from typing import Any, Callable
from rich.text import Text
from textual.containers import Container
from textual.css.styles import Styles
from textual.reactive import var
from textual.types import RenderStyles
from textual.widget import Widget
from textual.widgets import Button, DataTable
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

class ColorGrid(DataTable[Text], inherit_css=False):
    """A grid of colors."""
    # DEFAULT_CSS = (
    #     DataTable.DEFAULT_CSS
    #         .replace("datatable--cursor", "datatable--cursor-HACK-TO-NOT-MATCH")
    #         .replace("datatable--hover", "datatable--hover-HACK-TO-NOT-MATCH")
    # )
    def __init__(self, colors: list[str], **kwargs: Any) -> None:
        """Initialize the color grid."""
        super().__init__(**kwargs)
        column_count = 8
        self.add_columns(*([""] * column_count))
        self.show_header = False
        def cell_renderable(color: str) -> Text:
            """Return a static widget with the given color."""
            return Text("   ", style=f"on {color}")
        for i in range(0, len(colors), column_count):
            # self.add_row(*colors[i : i + column_count])
            self.add_row(*[cell_renderable(color) for color in colors[i : i + column_count]])
        self._selected_color = var(None)

    # def get_component_styles(self, name: str) -> RenderStyles:
    #     """HACK: there's no way to unset styles..."""
    #     if name in [
    #         "datatable--cursor",
    #         "datatable--hover",
    #     ]:
    #         return RenderStyles()
    #     return super().get_component_styles(name)

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
        else:
            self.handle_selected_color(self._color_by_button[button])

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        self.color_grid = ColorGrid(basic_colors + custom_colors, classes="color-grid")
        self.content.mount(self.color_grid)
        self.content.mount(Button(_("Cancel"), classes="cancel"))
