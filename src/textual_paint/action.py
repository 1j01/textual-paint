"""Action that can be undone."""

from textual.geometry import Offset, Region

from textual_paint.ansi_art_document import AnsiArtDocument, Selection


class Action:
    """An action that can be undone efficiently using a region update.

    This uses an image patch to undo the action, except for resizes, which store the entire document state.
    In either case, the action stores image data in sub_image_before.
    The image data from _after_ the action is not stored, because the Action exists only for undoing.

    TODO: In the future it would be more efficient to use a mask for the region update,
    to store only modified pixels, and use RLE compression on the mask and image data.

    NOTE: Not to be confused with Textual's `class Action(Event)`, or the type of law suit.
    Indeed, Textual's actions are used significantly in this application, with action_* methods,
    but this class is not related. Perhaps I should rename this class to UndoOp, or HistoryOperation.
    """

    def __init__(self, name: str, region: Region|None = None) -> None:
        """Initialize the action using the document state before modification."""

        self.name = name
        """The name of the action, for future display."""

        self.region = region
        """The region of the document that was modified."""

        self.is_full_update = False
        """Indicates that this action resizes the document, and thus should not be undone with a region update.

        That is, unless in the future region updates support a mask and work in tandem with resizes.
        """

        self.sub_image_before: AnsiArtDocument|None = None
        """The image data from the region of the document before modification."""

        self.cursor_position_before: Offset|None = None
        """The cursor position before the action was performed. (This may be generalized into a Selection state in the future to hold textbox contents.)"""

    def update(self, document: AnsiArtDocument) -> None:
        """Grabs the image data from the current region of the document."""
        assert self.region is not None, "Action.update called without a defined region"
        self.sub_image_before = AnsiArtDocument(self.region.width, self.region.height)
        self.sub_image_before.copy_region(document, self.region)

    def undo(self, target_document: AnsiArtDocument) -> None:
        """Undo this action. Note that a canvas refresh is not performed here."""
        # Warning: these warnings are hard to see in the terminal, since the terminal is being redrawn.
        # You have to use `textual console` to see them.
        if not self.sub_image_before:
            print("Warning: No undo data for Action. (Action.undo was called before any Action.update)")
            return
        if self.region is None:
            print("Warning: Action.undo called without a defined region")
            return
        if self.is_full_update:
            target_document.copy(self.sub_image_before)
        else:
            target_document.copy_region(self.sub_image_before, target_region=self.region)
        if self.cursor_position_before:
            target_document.selection = Selection(Region.from_offset(self.cursor_position_before, (1, 1)))
            target_document.selection.textbox_mode = True
            target_document.selection.copy_from_document(target_document)
