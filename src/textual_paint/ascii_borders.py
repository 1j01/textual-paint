"""Provides ASCII borders for older terminals."""

from textual._border import BORDER_CHARS, BORDER_LOCATIONS


def force_ascii_borders() -> None:
    """Force all borders to use ASCII characters."""

    # replace all with ascii border style
    for key in BORDER_CHARS:
        if key not in ("ascii", "none", "hidden", "blank", ""):
            BORDER_CHARS[key] = (
                ("+", "-", "+"),
                ("|", " ", "|"),
                ("+", "-", "+"),
            )

    # BORDER_CHARS[""] = (
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    # )
    # # was originally: (
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # # )

    # BORDER_CHARS["ascii"] = (
    #     ("+", "-", "+"),
    #     ("|", " ", "|"),
    #     ("+", "-", "+"),
    # )
    # # was originally: (
    # #     ("+", "-", "+"),
    # #     ("|", " ", "|"),
    # #     ("+", "-", "+"),
    # # )

    # BORDER_CHARS["none"] = (
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    # )
    # # was originally: (
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # # )

    # BORDER_CHARS["hidden"] = (
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    # )
    # # was originally: (
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # # )

    # BORDER_CHARS["blank"] = (
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    #     (" ", " ", " "),
    # )
    # # was originally: (
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # #     (" ", " ", " "),
    # # )

    BORDER_CHARS["round"] = (
        (".", "-", "."),
        ("|", " ", "|"),
        ("'", "-", "'"),
    )
    # was originally: (
    #     ("╭", "─", "╮"),
    #     ("│", " ", "│"),
    #     ("╰", "─", "╯"),
    # )

    # This is actually supported in at least some old terminals; it's part of CP437, but not ASCII.
    # BORDER_CHARS["solid"] = (
    #     ("┌", "─", "┐"),
    #     ("│", " ", "│"),
    #     ("└", "─", "┘"),
    # )
    # # was originally: (
    # #     ("┌", "─", "┐"),
    # #     ("│", " ", "│"),
    # #     ("└", "─", "┘"),
    # # )

    BORDER_CHARS["double"] = (
        ("#", "=", "#"),
        ("#", " ", "#"),
        ("#", "=", "#"),
    )
    # was originally: (
    #     ("╔", "═", "╗"),
    #     ("║", " ", "║"),
    #     ("╚", "═", "╝"),
    # )

    BORDER_CHARS["dashed"] = (
        (":", '"', ":"),
        (":", " ", ":"),
        ("'", '"', "'"),
    )
    # was originally: (
    #     ("┏", "╍", "┓"),
    #     ("╏", " ", "╏"),
    #     ("┗", "╍", "┛"),
    # )

    BORDER_CHARS["heavy"] = (
        ("#", "=", "#"),
        ("#", " ", "#"),
        ("#", "=", "#"),
    )
    # was originally: (
    #     ("┏", "━", "┓"),
    #     ("┃", " ", "┃"),
    #     ("┗", "━", "┛"),
    # )

    BORDER_CHARS["inner"] = (
        (" ", " ", " "),
        (" ", " ", " "),
        (" ", " ", " "),
    )
    # was originally: (
    #     ("▗", "▄", "▖"),
    #     ("▐", " ", "▌"),
    #     ("▝", "▀", "▘"),
    # )

    BORDER_CHARS["outer"] = (
        (" ", " ", " "),
        (" ", " ", " "),
        (" ", " ", " "),
    )
    # was originally: (
    #     ("▛", "▀", "▜"),
    #     ("▌", " ", "▐"),
    #     ("▙", "▄", "▟"),
    # )

    BORDER_CHARS["thick"] = (
        (" ", " ", " "),
        (" ", " ", " "),
        (" ", " ", " "),
    )
    # was originally: (
    #     ("█", "▀", "█"),
    #     ("█", " ", "█"),
    #     ("█", "▄", "█"),
    # )

    BORDER_CHARS["hkey"] = (
        (" ", " ", " "),
        (" ", " ", " "),
        ("_", "_", "_"),
    )
    # was originally: (
    #     ("▔", "▔", "▔"),
    #     (" ", " ", " "),
    #     ("▁", "▁", "▁"),
    # )

    BORDER_CHARS["vkey"] = (
        ("[", " ", "]"),
        ("[", " ", "]"),
        ("[", " ", "]"),
    )
    # was originally: (
    #     ("▏", " ", "▕"),
    #     ("▏", " ", "▕"),
    #     ("▏", " ", "▕"),
    # )

    BORDER_CHARS["tall"] = (
        ("[", " ", "]"),
        ("[", " ", "]"),
        ("[", "_", "]"),
    )
    # was originally: (
    #     ("▊", "▔", "▎"),
    #     ("▊", " ", "▎"),
    #     ("▊", "▁", "▎"),
    # )

    BORDER_CHARS["panel"] = (
        ("[", " ", "]"),
        ("|", " ", "|"),
        ("|", "_", "|"),
    )
    # was originally: (
    #     ("▊", "█", "▎"),
    #     ("▊", " ", "▎"),
    #     ("▊", "▁", "▎"),
    # )

    BORDER_CHARS["wide"] = (
        ("_", "_", "_"),
        ("[", " ", "]"),
        (" ", " ", " "),
    )
    # was originally: (
    #     ("▁", "▁", "▁"),
    #     ("▎", " ", "▊"),
    #     ("▔", "▔", "▔"),
    # )

    # Prevent inverse colors
    for key in BORDER_LOCATIONS:
        BORDER_LOCATIONS[key] = tuple(
            tuple(value % 2 for value in row)
            for row in BORDER_LOCATIONS[key]
        )
    # Prevent imbalanced borders
    BORDER_LOCATIONS["tall"] = (
        (0, 0, 0),
        (0, 0, 0),
        (0, 0, 0),
    )
    BORDER_LOCATIONS["wide"] = (
        (1, 1, 1),
        (0, 1, 0),
        (1, 1, 1),
    )
    BORDER_LOCATIONS["panel"] = (
        (3, 3, 3), # invert colors
        (0, 0, 0),
        (0, 0, 0),
    )
    for key in ("thick", "inner", "outer"):
        BORDER_LOCATIONS[key] = (
            (3, 3, 3), # invert colors
            (3, 0, 3), # invert colors except middle
            (3, 3, 3), # invert colors
        )


if __name__ == "__main__":
    force_ascii_borders()

    from textual.app import App
    from textual.containers import Grid
    from textual.widgets import Label

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

    app = AllBordersApp()
    app.run()
