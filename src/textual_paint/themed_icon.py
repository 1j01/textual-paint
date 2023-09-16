
from rich.console import RenderableType
from rich.protocol import is_renderable
from textual.errors import RenderError
from textual.widgets import Static

from textual_paint.localization.i18n import get as _


def _check_renderable(renderable: object):
    """Check if a renderable conforms to the Rich Console protocol
    (https://rich.readthedocs.io/en/latest/protocol.html)

    Args:
        renderable: A potentially renderable object.

    Raises:
        RenderError: If the object can not be rendered.
    """
    if not is_renderable(renderable):
        raise RenderError(
            f"unable to render {renderable!r}; a string, Text, or other Rich renderable is required"
        )

class ThemedIcon(Static):
    """A Static widget that changes its content based on the theme.
    
    Args:
        light_renderable: A Rich renderable, or string containing console markup, for the light theme.
        dark_renderable: A Rich renderable, or string containing console markup, for the dark theme.
        name: Name of widget.
        id: ID of Widget.
        classes: Space separated list of class names.
        disabled: Whether the static is disabled or not.
    """

    def __init__(
        self,
        light_renderable: RenderableType,
        dark_renderable: RenderableType, 
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        """Initialize the icon."""
        super().__init__("", 
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self.light_renderable = light_renderable
        self.dark_renderable = dark_renderable
        _check_renderable(light_renderable)
        _check_renderable(dark_renderable)
        self.watch(self.app, "dark", self._on_dark_changed, init=False)
        self._on_dark_changed(False, self.app.dark)

    def _on_dark_changed(self, old_value: bool, dark: bool) -> None:
        if dark:
            self.update(self.dark_renderable)
        else:
            self.update(self.light_renderable)
