"""A dialog window that lets the user select a character."""

from typing import Any, Callable

from textual.widget import Widget
from textual.widgets import Button, DataTable

from textual_paint.localization.i18n import get as _
from textual_paint.windows import DialogWindow


class CharacterSelectorDialogWindow(DialogWindow):
    """A dialog window that lets the user select a character."""

    # class CharacterSelected(Message):
    #     """Sent when a character is selected."""
    #     def __init__(self, character: str) -> None:
    #         """Initialize the message."""
    #         self.character = character

    # NUL at the beginning (0), SP in the middle (32), and NBSP at the end (255)
    # are all treated as space when selected. Null can cause the screen to malfunction
    # if it's inserted into the document.
    # spell-checker: disable
    code_page_437 = "\0☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼ !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~⌂ÇüéâäàåçêëèïîìÄÅÉæÆôöòûùÿÖÜ¢£¥₧ƒáíóúñÑªº¿⌐¬½¼¡«»░▒▓│┤╡╢╖╕╣║╗╝╜╛┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀αßΓπΣσµτΦΘΩδ∞φε∩≡±≥≤⌠⌡÷≈°∙·√ⁿ²■ "
    # spell-checker: enable
    char_list = [char for char in code_page_437]

    def __init__(
        self,
        *children: Widget,
        selected_character: str | None,
        handle_selected_character: Callable[[str], None],
        **kwargs: Any,
    ) -> None:
        """Initialize the dialog window."""
        super().__init__(handle_button=self.handle_button, *children, **kwargs)
        self._selected_character: str | None = selected_character
        self.handle_selected_character = handle_selected_character

    def handle_button(self, button: Button) -> None:
        """Called when a button is clicked or activated with the keyboard."""
        if button.has_class("cancel"):
            self.request_close()
        else:
            if self._selected_character is None:
                # Probably shouldn't happen
                return
            # self.post_message(self.CharacterSelected(self._selected_character))
            # self.close()
            self.handle_selected_character(self._selected_character)

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        """Called when a cell is highlighted."""
        # assert isinstance(event.value, str), "DataTable should only contain strings, but got: " + repr(event.value)
        self._selected_character = (
            event.value if isinstance(event.value, str) and event.value != "\0" else " "
        )

    def on_mount(self) -> None:
        """Called when the window is mounted."""
        data_table: DataTable[str] = DataTable()
        column_count = 16
        data_table.add_columns(*([" "] * column_count))
        data_table.show_header = False
        for i in range(0, len(self.char_list), column_count):
            data_table.add_row(*self.char_list[i : i + column_count])
        self.content.mount(data_table)
        self.content.mount(Button(_("OK"), classes="ok submit"))
        self.content.mount(Button(_("Cancel"), classes="cancel"))
