"""Provides ASCII alternatives for older terminals."""

from textual._border import BORDER_CHARS, BORDER_LOCATIONS, get_box
from textual.scrollbar import ScrollBar
from textual.widgets import RadioButton

from textual_paint.scrollbars import ASCIIScrollBarRender
from textual_paint.windows import WindowTitleBar

replacements: list[tuple[object, str, object, object]] = []

def replace(obj: object, attr: str, ascii_only_value: object) -> None:
    """Replace an attribute with a value for --ascii-only mode."""
    if isinstance(obj, dict):
        replacements.append((obj, attr, ascii_only_value, obj[attr]))  # type: ignore
    else:
        replacements.append((obj, attr, ascii_only_value, getattr(obj, attr)))

def set_ascii_only_mode(ascii_only: bool) -> None:
    """Set the --ascii-only mode for all replacements."""
    for obj, attr, ascii_only_value, non_ascii_value in replacements:
        value = ascii_only_value if ascii_only else non_ascii_value
        if isinstance(obj, dict):
            obj[attr] = value
        else:
            setattr(obj, attr, value)
    
    get_box.cache_clear()

replace(RadioButton, "BUTTON_INNER", "*") # "*", "o", "O", "@"
# Defined on internal superclass ToggleButton
replace(RadioButton, "BUTTON_LEFT", "(")
replace(RadioButton, "BUTTON_RIGHT", ")")

replace(ScrollBar, "renderer", ASCIIScrollBarRender)

replace(WindowTitleBar, "MINIMIZE_ICON", "_")
replace(WindowTitleBar, "MAXIMIZE_ICON", "[]")
replace(WindowTitleBar, "RESTORE_ICON", "\\[/]" )
replace(WindowTitleBar, "CLOSE_ICON", "X")


def replace_borders() -> None:
    """Conditionally force all borders to use ASCII characters."""

    # replace all with ascii border style
    for key in BORDER_CHARS:
        if key not in ("ascii", "none", "hidden", "blank", ""):
            replace(BORDER_CHARS, key, (
                ("+", "-", "+"),
                ("|", " ", "|"),
                ("+", "-", "+"),
            ))

    # replace(BORDER_CHARS, "", (
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    # ))
    # # was originally: (
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # # )

    # replace(BORDER_CHARS, "ascii", (
    #     ("+", "-", "+"),
    #     ("|", " ", "|"),
    #     ("+", "-", "+"),
    # ))
    # # was originally: (
    # #     ("+", "-", "+"),
    # #     ("|", " ", "|"),
    # #     ("+", "-", "+"),
    # # )

    # replace(BORDER_CHARS, "none", (
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    # ))
    # # was originally: (
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # # )

    # replace(BORDER_CHARS, "hidden", (
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    # ))
    # # was originally: (
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # # )

    # replace(BORDER_CHARS, "blank", (
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    # ))
    # # was originally: (
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # # )

    replace(BORDER_CHARS, "round", (
        (".", "-", "."),
        ("|", " ", "|"),
        ("'", "-", "'"),
    ))
    # was originally: (
    #     ("╭", "─", "╮"),
    #     ("│", " ", "│"),
    #     ("╰", "─", "╯"),
    # )

    # This is actually supported in at least some old terminals; it's part of CP437, but not ASCII.
    # replace(BORDER_CHARS, "solid", (
    #     ("┌", "─", "┐"),
    #     ("│", " ", "│"),
    #     ("└", "─", "┘"),
    # ))
    # # was originally: (
    # #     ("┌", "─", "┐"),
    # #     ("│", " ", "│"),
    # #     ("└", "─", "┘"),
    # # )

    replace(BORDER_CHARS, "double", (
        ("#", "=", "#"),
        ("#", " ", "#"),
        ("#", "=", "#"),
    ))
    # was originally: (
    #     ("╔", "═", "╗"),
    #     ("║", " ", "║"),
    #     ("╚", "═", "╝"),
    # )

    replace(BORDER_CHARS, "dashed", (
        (":", '"', ":"),
        (":", " ", ":"),
        ("'", '"', "'"),
    ))
    # was originally: (
    #     ("┏", "╍", "┓"),
    #     ("╏", " ", "╏"),
    #     ("┗", "╍", "┛"),
    # )

    replace(BORDER_CHARS, "heavy", (
        ("#", "=", "#"),
        ("#", " ", "#"),
        ("#", "=", "#"),
    ))
    # was originally: (
    #     ("┏", "━", "┓"),
    #     ("┃", " ", "┃"),
    #     ("┗", "━", "┛"),
    # )

    replace(BORDER_CHARS, "inner", (
        (" ", " ", " "),
        (" ", " ", " "),
        (" ", " ", " "),
    ))
    # was originally: (
    #     ("▗", "▄", "▖"),
    #     ("▐", " ", "▌"),
    #     ("▝", "▀", "▘"),
    # )

    replace(BORDER_CHARS, "outer", (
        (" ", " ", " "),
        (" ", " ", " "),
        (" ", " ", " "),
    ))
    # was originally: (
    #     ("▛", "▀", "▜"),
    #     ("▌", " ", "▐"),
    #     ("▙", "▄", "▟"),
    # )

    replace(BORDER_CHARS, "thick", (
        (" ", " ", " "),
        (" ", " ", " "),
        (" ", " ", " "),
    ))
    # was originally: (
    #     ("█", "▀", "█"),
    #     ("█", " ", "█"),
    #     ("█", "▄", "█"),
    # )

    replace(BORDER_CHARS, "hkey", (
        (" ", " ", " "),
        (" ", " ", " "),
        ("_", "_", "_"),
    ))
    # was originally: (
    #     ("▔", "▔", "▔"),
    #     (" ", " ", " "),
    #     ("▁", "▁", "▁"),
    # )

    replace(BORDER_CHARS, "vkey", (
        ("[", " ", "]"),
        ("[", " ", "]"),
        ("[", " ", "]"),
    ))
    # was originally: (
    #     ("▏", " ", "▕"),
    #     ("▏", " ", "▕"),
    #     ("▏", " ", "▕"),
    # )

    replace(BORDER_CHARS, "tall", (
        ("[", " ", "]"),
        ("[", " ", "]"),
        ("[", "_", "]"),
    ))
    # was originally: (
    #     ("▊", "▔", "▎"),
    #     ("▊", " ", "▎"),
    #     ("▊", "▁", "▎"),
    # )

    replace(BORDER_CHARS, "panel", (
        ("[", " ", "]"),
        ("|", " ", "|"),
        ("|", "_", "|"),
    ))
    # was originally: (
    #     ("▊", "█", "▎"),
    #     ("▊", " ", "▎"),
    #     ("▊", "▁", "▎"),
    # )

    replace(BORDER_CHARS, "wide", (
        ("_", "_", "_"),
        ("[", " ", "]"),
        (" ", " ", " "),
    ))
    # was originally: (
    #     ("▁", "▁", "▁"),
    #     ("▎", " ", "▊"),
    #     ("▔", "▔", "▔"),
    # )

    # Prevent inverse colors
    for key in BORDER_LOCATIONS:
        replace(BORDER_LOCATIONS, key, tuple(
            tuple(value % 2 for value in row)
            for row in BORDER_LOCATIONS[key]
        ))
    # Prevent imbalanced borders
    replace(BORDER_LOCATIONS, "tall", (
        (0, 0, 0),
        (0, 0, 0),
        (0, 0, 0),
    ))
    replace(BORDER_LOCATIONS, "wide", (
        (1, 1, 1),
        (0, 1, 0),
        (1, 1, 1),
    ))
    replace(BORDER_LOCATIONS, "panel", (
        (3, 3, 3), # invert colors
        (0, 0, 0),
        (0, 0, 0),
    ))
    for key in ("thick", "inner", "outer"):
        replace(BORDER_LOCATIONS, key, (
            (3, 3, 3), # invert colors
            (3, 0, 3), # invert colors except middle
            (3, 3, 3), # invert colors
        ))

replace_borders()


if __name__ == "__main__":
    replace_borders()
    set_ascii_only_mode(True)

    from textual.app import App
    from textual.containers import Grid
    from textual.widgets import Label, Switch

    class AllBordersApp(App[None]):
        """Demo app for ASCII borders. Based on https://textual.textualize.io/styles/border/#all-border-types"""

        CSS = """
        #ascii {
            border: ascii $accent;
        }

        #panel {
            border: panel $accent;
        }

        #dashed {
            border: dashed $accent;
        }

        #double {
            border: double $accent;
        }

        #heavy {
            border: heavy $accent;
        }

        #hidden {
            border: hidden $accent;
        }

        #hkey {
            border: hkey $accent;
        }

        #inner {
            border: inner $accent;
        }

        #outer {
            border: outer $accent;
        }

        #round {
            border: round $accent;
        }

        #solid {
            border: solid $accent;
        }

        #tall {
            border: tall $accent;
        }

        #thick {
            border: thick $accent;
        }

        #vkey {
            border: vkey $accent;
        }

        #wide {
            border: wide $accent;
        }

        Grid {
            grid-size: 3 5;
            align: center middle;
            grid-gutter: 1 2;
        }

        Label {
            width: 20;
            height: 3;
            content-align: center middle;
        }
        """

        def compose(self):
            yield Grid(
                Label("ascii", id="ascii"),
                Label("panel", id="panel"),
                Label("dashed", id="dashed"),
                Label("double", id="double"),
                Label("heavy", id="heavy"),
                Label("hidden/none/blank", id="hidden"),
                Label("hkey", id="hkey"),
                Label("inner", id="inner"),
                Label("outer", id="outer"),
                Label("round", id="round"),
                Label("solid", id="solid"),
                Label("tall", id="tall"),
                Label("thick", id="thick"),
                Label("vkey", id="vkey"),
                Label("wide", id="wide"),
            )
            yield Switch(True, id="ascii_only_switch")

        def on_switch_changed(self, event: Switch.Changed) -> None:
            # event.switch.styles.background = "red"
            set_ascii_only_mode(event.value)
            # event.switch.styles.background = "yellow"

            # Refreshing each widget separately seems to be necessary
            for widget in self.query("*"):
                widget.refresh()
            # Or clearing each widget's caches manually and then refreshing the screen:
            # for widget in self.query("*"):
            #     widget._styles_cache.clear()
            #     # widget._rich_style_cache = {}
            # self.refresh()


    app = AllBordersApp()
    app.run()
