"""Provides the AnsiArtDocument and Selection classes (and exceptions.)"""
import base64
import io
import math
import os
import re
from random import randint
from typing import Any, NamedTuple, Optional

import stransi
from PIL import Image
from rich.console import Console
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from stransi.instruction import Instruction
from textual.color import Color, ColorParseError
from textual.geometry import Offset, Region

from textual_paint.export_templates import (CUSTOM_CONSOLE_HTML_FORMAT,
                                            CUSTOM_CONSOLE_SVG_FORMAT)
from textual_paint.localization.i18n import get as _
from textual_paint.palette_data import IRC_PALETTE

DEBUG_REGION_UPDATES = False

DEBUG_SVG_LOADING = False # writes debug.svg when flexible character grid loader is used

# JPEG is disabled because of low quality.
# On the scale of images you're able to (performantly) edit in this app (currently),
# JPEG is not a good choice.
# ICNS is disabled because it only supports a limited set of sizes.
SAVE_DISABLED_FORMATS = ["JPEG", "ICNS"]


# Detects ANSI escape sequences.
# ansi_escape_pattern = re.compile(r"(\N{ESC}\[[\d;]*[a-zA-Z])")

# Detects all control codes, including newlines and tabs.
# ansi_control_code_pattern = re.compile(r'[\x00-\x1F\x7F]')

# Detects all control codes, including tabs and carriage return (CR) if used alone, but excluding line feed (LF) and CR+LF.
ansi_detector_pattern = re.compile(r'[\x00-\x09\x0B\x0C\x0E-\x1F\x7F]|\r(?!\n)')
# Explanation:
# [\x00-\x09\x0B\x0C\x0E-\x1F\x7F]: Matches any control character except CR (\x0D) or LF (\x0A).
# \r(?<!\r\n): Matches CR (\x0D) if it's not part of CRLF (\x0D\x0A).
#   (?<!\r\n): Negative lookbehind assertion to ensure that the matched CR (if any) is not part of CRLF.
# Tabs are included because they need to be expanded to spaces or they'll mess up the layout, currently,
# and if the text isn't detected as ANSI, it won't currently be expanded.
# Development strategy:
# I used https://www.debuggex.com/ to develop a simpler regex that operates on letters as stand-ins for control codes,
# since I don't know that I could input isolated control codes into the site.
# e|r(?!n)
# using test data:
# ---e--- (e representing any control code except CR or LF)
# ---r---
# ---n--- <- shouldn't match
# ---rn-- <- shouldn't match
# ---nr--

assert ansi_detector_pattern.search("\x0A") is None, "LF should not be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x0D") is not None, "CR by itself (not part of CRLF) should be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x0D\x0A") is None, "CRLF should not be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x09") is not None, "TAB should be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x1B") is not None, "ESC should be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x7F") is not None, "DEL should be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x00") is not None, "NUL should be matched by ansi_detector_pattern"
assert ansi_detector_pattern.search("\x80") is None, "Ç (in CP 437) or € (U+0080) should not be matched by ansi_detector_pattern"

class FormatWriteNotSupported(Exception):
    """The format doesn't support writing."""
    def __init__(self, localized_message: str):
        self.localized_message = localized_message
        super().__init__(localized_message)

class FormatReadNotSupported(Exception):
    """The format doesn't support reading."""
    def __init__(self, localized_message: str):
        self.localized_message = localized_message
        super().__init__(localized_message)


class AnsiArtDocument:
    """A document that can be rendered as ANSI."""

    def __init__(self, width: int, height: int, default_bg: str = "#ffffff", default_fg: str = "#000000") -> None:
        """Initialize the document."""
        # Pyright is really confused by height for some reason, doesn't have a problem with width.
        # I narrowed it down to the resize method, lines with new_bg/new_fg, but
        # I have no idea why that would be a problem.
        # Ideally I would try to pare this down to a minimal reproducible example,
        # and file a bug report (or learn something about my code),
        # but for now, I just want to silence 100+ errors.
        # I'm leaving width unannotated to highlight the fragility of programming.
        self.width = width
        self.height: int = height
        self.ch = [[" " for _ in range(width)] for _ in range(height)]
        self.bg = [[default_bg for _ in range(width)] for _ in range(height)]
        self.fg = [[default_fg for _ in range(width)] for _ in range(height)]
        self.selection: Optional[Selection] = None

    def copy(self, source: 'AnsiArtDocument') -> None:
        """Copy the image size and data from another document. Does not copy the selection."""
        self.width = source.width
        self.height = source.height
        self.ch = [row[:] for row in source.ch]
        self.bg = [row[:] for row in source.bg]
        self.fg = [row[:] for row in source.fg]
        self.selection = None

    def copy_region(self, source: 'AnsiArtDocument', source_region: Region|None = None, target_region: Region|None = None, mask: list[list[bool]]|None = None) -> None:
        """Copy a region from another document into this document."""
        if source_region is None:
            source_region = Region(0, 0, source.width, source.height)
        if target_region is None:
            target_region = Region(0, 0, source_region.width, source_region.height)
        source_offset = source_region.offset
        target_offset = target_region.offset
        random_color: Optional[str] = None  # avoid "possibly unbound"
        if DEBUG_REGION_UPDATES:
            random_color = "rgb(" + str(randint(0, 255)) + "," + str(randint(0, 255)) + "," + str(randint(0, 255)) + ")"
        for y in range(target_region.height):
            for x in range(target_region.width):
                if source_region.contains(x + source_offset.x, y + source_offset.y) and (mask is None or mask[y][x]):
                    self.ch[y + target_offset.y][x + target_offset.x] = source.ch[y + source_offset.y][x + source_offset.x]
                    self.bg[y + target_offset.y][x + target_offset.x] = source.bg[y + source_offset.y][x + source_offset.x]
                    self.fg[y + target_offset.y][x + target_offset.x] = source.fg[y + source_offset.y][x + source_offset.x]
                    if DEBUG_REGION_UPDATES:
                        assert random_color is not None
                        # self.bg[y + target_offset.y][x + target_offset.x] = "rgb(" + str((x + source_offset.x) * 255 // self.width) + "," + str((y + source_offset.y) * 255 // self.height) + ",0)"
                        self.bg[y + target_offset.y][x + target_offset.x] = random_color
                else:
                    if DEBUG_REGION_UPDATES:
                        self.ch[y + target_offset.y][x + target_offset.x] = "?"
                        self.bg[y + target_offset.y][x + target_offset.x] = "#ff00ff"
                        self.fg[y + target_offset.y][x + target_offset.x] = "#000000"

    def resize(self, width: int, height: int, default_bg: str = "#ffffff", default_fg: str = "#000000") -> None:
        """Resize the document."""
        if width == self.width and height == self.height:
            return
        new_ch = [[" " for _ in range(width)] for _ in range(height)]
        new_bg = [[default_bg for _ in range(width)] for _ in range(height)]
        new_fg = [[default_fg for _ in range(width)] for _ in range(height)]
        for y in range(min(height, self.height)):
            for x in range(min(width, self.width)):
                new_ch[y][x] = self.ch[y][x]
                new_bg[y][x] = self.bg[y][x]
                new_fg[y][x] = self.fg[y][x]
        self.width = width
        self.height = height
        self.ch = new_ch
        self.bg = new_bg
        self.fg = new_fg

    def invert(self) -> None:
        """Invert the foreground and background colors."""
        self.invert_region(Region(0, 0, self.width, self.height))

    def invert_region(self, region: Region) -> None:
        """Invert the foreground and background colors in the given region."""
        # TODO: DRY color inversion, and/or simplify it. It shouldn't need a Style object.
        for y in range(region.y, region.y + region.height):
            for x in range(region.x, region.x + region.width):
                style = Style(color=self.fg[y][x], bgcolor=self.bg[y][x])
                assert style.color is not None
                assert style.bgcolor is not None
                assert style.color.triplet is not None
                assert style.bgcolor.triplet is not None
                self.bg[y][x] = f"#{(255 - style.bgcolor.triplet.red):02x}{(255 - style.bgcolor.triplet.green):02x}{(255 - style.bgcolor.triplet.blue):02x}"
                self.fg[y][x] = f"#{(255 - style.color.triplet.red):02x}{(255 - style.color.triplet.green):02x}{(255 - style.color.triplet.blue):02x}"

    @staticmethod
    def format_from_extension(file_path: str) -> str | None:
        """Get the format ID from the file extension of the given path.

        Most format IDs are similar to the extension, e.g. 'PNG' for '.png',
        but some are different, e.g. 'JPEG2000' for '.jp2'.
        """
        # Ignore case and trailing '~' (indicating a backup file)
        # Alternative: pathlib.Path.suffix
        file_ext_with_dot = os.path.splitext(file_path)[1].lower().rstrip("~")
        # print("File extension:", file_ext_with_dot)
        ext_to_id = Image.registered_extensions() # maps extension to format ID, e.g. '.jp2': 'JPEG2000'
        # print("Supported image formats by extension:", Image.EXTENSION)
        if file_ext_with_dot in ext_to_id:
            return ext_to_id[file_ext_with_dot]
        ext_to_id = {
            ".svg": "SVG",
            ".html": "HTML",
            ".htm": "HTML",
            ".txt": "PLAINTEXT",
            ".asc": "PLAINTEXT",
            ".diz": "PLAINTEXT",
            ".ans": "ANSI",
            ".irc": "IRC",
            ".mirc": "IRC",
            "._rich_console_markup": "RICH_CONSOLE_MARKUP",
        }
        if file_ext_with_dot in ext_to_id:
            return ext_to_id[file_ext_with_dot]
        return None

    def encode_based_on_file_extension(self, file_path: str) -> bytes:
        """Encode the image according to the file extension."""
        return self.encode_to_format(self.format_from_extension(file_path))

    def encode_to_format(self, format_id: str | None) -> bytes:
        """Encode the image into the given file format."""
        # print("Supported image formats for writing:", Image.SAVE.keys())
        if format_id is None:
            raise FormatWriteNotSupported(localized_message=_("Unknown file extension.") + "\n\n" + _("To save your changes, use a different filename."))
        elif format_id == "ANSI":
            # This maybe shouldn't use UTF-8... but there's not a singular encoding for "ANSI art".
            return self.get_ansi().encode("utf-8")
        elif format_id == "IRC":
            # Also not sure about UTF-8 here.
            return self.get_irc().encode("utf-8")
        elif format_id == "SVG":
            return self.get_svg().encode("utf-8")
        elif format_id == "HTML":
            return self.get_html().encode("utf-8")
        elif format_id == "PLAINTEXT":
            return self.get_plain().encode("utf-8")
        elif format_id == "RICH_CONSOLE_MARKUP":
            return self.get_rich_console_markup().encode("utf-8")
        elif format_id in Image.SAVE and format_id not in SAVE_DISABLED_FORMATS:
            return self.encode_image_format(format_id)
        else:
            raise FormatWriteNotSupported(localized_message=_("Cannot write files in %1 format.", format_id) + "\n\n" + _("To save your changes, use a different filename."))

    def encode_image_format(self, pil_format_id: str) -> bytes:
        """Encode the document as an image file."""
        size = (self.width, self.height)
        image = Image.new("RGB", size, color="#000000")
        pixels = image.load()
        assert pixels is not None, "failed to load pixels for new image"
        for y in range(self.height):
            for x in range(self.width):
                color = Color.parse(self.bg[y][x])
                pixels[x, y] = (color.r, color.g, color.b)
        buffer = io.BytesIO()
        # `lossless` is for WebP
        # `sizes` is for ICO, since it defaults to a list of square sizes, blurring/distorting the image.
        # `bitmap_format` is also for ICO. I get "Compressed icons are not supported" in Ubuntu's image viewer,
        # and thumbnails don't render when it uses the default PNG sub-format.
        image.save(buffer, pil_format_id, lossless=True, sizes=[size], bitmap_format="bmp")
        return buffer.getvalue()

    def get_ansi(self) -> str:
        """Get the ANSI representation of the document."""
        renderable = self.get_renderable()
        console = self.get_console(render_contents=False)
        segments = renderable.render(console=console)
        ansi = ""
        for text, style, _ in Segment.filter_control(
            Segment.simplify(segments)
        ):
            if style:
                ansi += style.render(text)
            else:
                ansi += text
        return ansi

    def get_irc(self) -> str:
        """Get the mIRC code representation of the document."""
        renderable = self.get_renderable()
        console = self.get_console(render_contents=False)
        segments = renderable.render(console=console)

        def color_distance(a: Color, b: Color) -> float:
            """Perceptual color distance between two colors."""
            # https://www.compuphase.com/cmetric.htm
            red_mean = (a.r + b.r) // 2
            red = a.r - b.r
            green = a.g - b.g
            blue = a.b - b.b
            return math.sqrt((((512 + red_mean) * red * red) >> 8) + 4 * green * green + (((767 - red_mean) * blue * blue) >> 8))

        def closest_color(color: Color) -> int:
            """Get the closest color in the palette to the given color."""
            closest_color = 0
            closest_distance = float("inf")
            for index, hex in enumerate(IRC_PALETTE):
                distance = color_distance(color, Color.parse(hex))
                if distance < closest_distance:
                    closest_color = index
                    closest_distance = distance
            return closest_color

        # TODO: simplify after converting to IRC colors, to remove unnecessary color codes
        irc_text = ""
        for text, style, _ in Segment.filter_control(
            Segment.simplify(segments)
        ):
            if style and style.color is not None and style.bgcolor is not None:
                irc_text += "\x03"
                irc_text += str(closest_color(Color.from_rich_color(style.color)))
                irc_text += ","
                irc_text += str(closest_color(Color.from_rich_color(style.bgcolor)))
                if text[0] in "0123456789,":
                    # separate the color code from the text with an ending escape character
                    irc_text += "\x03"
                irc_text += text
            else:
                irc_text += text
        # ^O is the mIRC code for "reset to default colors"
        return irc_text + "\x0F"

    def get_plain(self) -> str:
        """Get the plain text representation of the document."""
        text = ""
        for y in range(self.height):
            for x in range(self.width):
                text += self.ch[y][x]
            text += "\n"
        return text

    def get_rich_console_markup(self) -> str:
        """Get the Rich API markup representation of the document."""
        return self.get_renderable().markup

    def get_html(self) -> str:
        """Get the HTML representation of the document."""
        console = self.get_console()
        return console.export_html(inline_styles=True, code_format=CUSTOM_CONSOLE_HTML_FORMAT)

    def get_svg(self) -> str:
        """Get the SVG representation of the document."""
        console = self.get_console()
        svg = console.export_svg(code_format=CUSTOM_CONSOLE_SVG_FORMAT)
        # Include ANSI in the SVG so it can be loaded perfectly when re-opened.
        # This can't use the .format() template since e.g. "{anything}" in the document would case a KeyError.
        # (And I can't do it beforehand on the template because the template uses .format() itself...
        # unless I escaped all the braces, but that would be ugly! So I'm just using a different syntax.)
        # `html.escape` leaves control codes, which blows up ET.fromstring, so use base64 instead.
        return svg.replace("%ANSI_GOES_HERE%", base64.b64encode(self.get_ansi().encode("utf-8")).decode("utf-8"))

    def get_renderable(self) -> Text:
        """Get a Rich renderable for the document."""
        joiner = Text("\n")
        lines: list[Text] = []
        for y in range(self.height):
            line = Text()
            for x in range(self.width):
                line.append(self.ch[y][x], style=Style(bgcolor=self.bg[y][x], color=self.fg[y][x]))
            lines.append(line)
        result = joiner.join(lines)
        return result

    def get_console(self, render_contents: bool = True) -> Console:
        """Get a Rich Console with the document rendered in it."""
        console = Console(
            width=self.width,
            height=self.height,
            file=io.StringIO(),
            force_terminal=True,
            color_system="truecolor",
            record=True,
            legacy_windows=False,
        )
        if render_contents:
            console.print(self.get_renderable())
        return console

    @staticmethod
    def from_plain(text: str, default_bg: str = "#ffffff", default_fg: str = "#000000") -> 'AnsiArtDocument':
        """Creates a document from the given plain text."""
        lines = text.splitlines()
        width = 1
        for line in lines:
            width = max(len(line), width)
        height = max(len(lines), 1)
        document = AnsiArtDocument(width, height, default_bg, default_fg)
        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                document.ch[y][x] = char
        return document

    @staticmethod
    def from_irc(text: str, default_bg: str = "#ffffff", default_fg: str = "#000000") -> 'AnsiArtDocument':
        """Creates a document from text with mIRC codes."""

        document = AnsiArtDocument(0, 0, default_bg, default_fg)
        # Minimum size of 1x1, so that the document is never empty.
        width = 1
        height = 1

        x = 0
        y = 0
        bg_color = default_bg
        fg_color = default_fg

        color_escape = "\x03"
        # an optional escape code at the end disambiguates a digit from part of the color code
        color_escape_re = re.compile(r"\x03(\d{1,2})?(?:,(\d{1,2}))?\x03?")
        reset_escape = "\x0F"

        index = 0
        while index < len(text):
            char = text[index]
            if char == color_escape:
                match = color_escape_re.match(text[index:])
                if match:
                    index += len(match.group(0))
                    # TODO: should a one-value syntax reset the background?
                    bg_color = default_bg
                    fg_color = default_fg
                    if match.group(1):
                        fg_color = IRC_PALETTE[int(match.group(1))]
                    if match.group(2):
                        bg_color = IRC_PALETTE[int(match.group(2))]
                    continue
            if char == reset_escape:
                index += 1
                bg_color = default_bg
                fg_color = default_fg
                continue
            if char == "\n":
                width = max(width, x)
                x = 0
                y += 1
                height = max(height, y)
                index += 1
                continue
            # Handle a single character, adding rows/columns as needed.
            while len(document.ch) <= y:
                document.ch.append([])
                document.bg.append([])
                document.fg.append([])
            while len(document.ch[y]) <= x:
                document.ch[y].append(' ')
                document.bg[y].append(default_bg)
                document.fg[y].append(default_fg)
            document.ch[y][x] = char
            document.bg[y][x] = bg_color
            document.fg[y][x] = fg_color
            width = max(x + 1, width)
            height = max(y + 1, height)
            x += 1
            index += 1

        document.width = width
        document.height = height
        # Handle minimum height.
        while len(document.ch) <= document.height:
            document.ch.append([])
            document.bg.append([])
            document.fg.append([])
        # Pad rows to a consistent width.
        for y in range(document.height):
            for x in range(len(document.ch[y]), document.width):
                document.ch[y].append(' ')
                document.bg[y].append(default_bg)
                document.fg[y].append(default_fg)

        return document

    @staticmethod
    def from_ansi(text: str, default_bg: str = "#ffffff", default_fg: str = "#000000", max_width: int = 100000) -> 'AnsiArtDocument':
        """Creates a document from the given ANSI text."""

        # TODO: use Rich API to render ANSI to a virtual screen,
        # and remove dependency on stransi
        # or improve ANSI handling based on Playscii's code
        # It kind of looks like Rich's API isn't designed to handle absolute positioning,
        # since it parses a line at a time, but I only looked at it briefly.

        # rich_text = Text.from_ansi(text, style=Style(bgcolor=default_bg, color=default_fg))
        # # This takes a console and options, but I want the width of the console to come from the text...
        # # Do I need to create a console huge and then resize it (or make a new one)?
        # measurement = Measurement.get(console, options, rich_text)
        # document = AnsiArtDocument(measurement.width, measurement.height, default_bg, default_fg)
        # console = document.get_console(rich_text)
        # # then see export_html et. al. for how to get the data out? or just use the rich_text?


        # Workaround for unwanted color rounding
        # RGB.__post_init__ rounds the color components, in decimal, causing 128 to become 127.
        from ochre.spaces import RGB
        RGB.__post_init__ = lambda self: None


        ansi = stransi.Ansi(text)

        document = AnsiArtDocument(0, 0, default_bg, default_fg)
        # Minimum size of 1x1, so that the document is never empty.
        width = 1
        height = 1

        x = 0
        y = 0
        bg_color = default_bg
        fg_color = default_fg
        instruction: Instruction[Any] | str
        for instruction in ansi.instructions():
            if isinstance(instruction, str):
                # Text and control characters other than escape sequences
                for char in instruction:
                    if char == '\r':
                        x = 0
                    elif char == '\n':
                        x = 0
                        y += 1
                        # Don't increase height until there's a character to put in the new row.
                        # This avoids an extra row if the file ends with a newline.
                    elif char == '\t':
                        x += 8 - (x % 8)
                        if x > max_width - 1:
                            x = max_width - 1  # I'm not sure if this is the right behavior; should it wrap?
                    elif char == '\b':
                        x -= 1
                        if x < 0:
                            x = 0
                            # on some terminals, backspace at the start of a line moves the cursor up,
                            # but we're not defining a width for the document up front, so we can't do that
                            # (could use max_width, but since there will be some incompatibility anyway,
                            # better to go with the simpler, more understandable behavior)
                    elif char == '\x07':
                        # ignore bell
                        # TODO: ignore other unhandled control characters
                        pass
                    else:
                        while len(document.ch) <= y:
                            document.ch.append([])
                            document.bg.append([])
                            document.fg.append([])
                        while len(document.ch[y]) <= x:
                            document.ch[y].append(' ')
                            document.bg[y].append(default_bg)
                            document.fg[y].append(default_fg)
                        document.ch[y][x] = char
                        document.bg[y][x] = bg_color
                        document.fg[y][x] = fg_color
                        width = max(x + 1, width)
                        height = max(y + 1, height)
                        x += 1
                        if x > max_width - 1:
                            x = 0
                            y += 1
            elif isinstance(instruction, stransi.SetColor) and instruction.color is not None:
                # Color (I'm not sure why instruction.color would be None, but it's typed as Optional[Color])
                # (maybe just for initial state?)
                if instruction.role == stransi.color.ColorRole.FOREGROUND:
                    rgb = instruction.color.rgb
                    fg_color = "rgb(" + str(int(rgb.red * 255)) + "," + str(int(rgb.green * 255)) + "," + str(int(rgb.blue * 255)) + ")"
                elif instruction.role == stransi.color.ColorRole.BACKGROUND:
                    rgb = instruction.color.rgb
                    bg_color = "rgb(" + str(int(rgb.red * 255)) + "," + str(int(rgb.green * 255)) + "," + str(int(rgb.blue * 255)) + ")"
            elif isinstance(instruction, stransi.SetCursor):
                # Cursor position is encoded as y;x, so stransi understandably gets this backwards.
                # TODO: fix stransi to interpret ESC[<y>;<x>H correctly
                # (or update it if it gets fixed)
                # Note that stransi gives 0-based coordinates; the underlying ANSI is 1-based.
                if instruction.move.relative:
                    x += instruction.move.y
                    y += instruction.move.x
                else:
                    x = instruction.move.y
                    y = instruction.move.x
                x = max(0, x)
                y = max(0, y)
                x = min(max_width - 1, x)
                width = max(x + 1, width)
                height = max(y + 1, height)
                while len(document.ch) <= y:
                    document.ch.append([])
                    document.bg.append([])
                    document.fg.append([])
            elif isinstance(instruction, stransi.SetClear):
                def clear_line(row_to_clear: int, before: bool, after: bool):
                    cols_to_clear: list[int] = []
                    if before:
                        cols_to_clear += range(0, len(document.ch[row_to_clear]))
                    if after:
                        cols_to_clear += range(x, len(document.ch[row_to_clear]))
                    for col_to_clear in cols_to_clear:
                        document.ch[row_to_clear][col_to_clear] = ' '
                        document.bg[row_to_clear][col_to_clear] = default_bg
                        document.fg[row_to_clear][col_to_clear] = default_fg
                match instruction.region:
                    case stransi.clear.Clear.LINE:
                        # Clear the current line
                        clear_line(y, True, True)
                    case stransi.clear.Clear.LINE_AFTER:
                        # Clear the current line after the cursor
                        clear_line(y, False, True)
                    case stransi.clear.Clear.LINE_BEFORE:
                        # Clear the current line before the cursor
                        clear_line(y, True, False)
                    case stransi.clear.Clear.SCREEN:
                        # Clear the entire screen
                        for row_to_clear in range(len(document.ch)):
                            clear_line(row_to_clear, True, True)
                        # and reset the cursor to home
                        x, y = 0, 0
                    case stransi.clear.Clear.SCREEN_AFTER:
                        # Clear the screen after the cursor
                        for row_to_clear in range(y, len(document.ch)):
                            clear_line(row_to_clear, row_to_clear > y, True)
                    case stransi.clear.Clear.SCREEN_BEFORE:
                        # Clear the screen before the cursor
                        for row_to_clear in range(y):
                            clear_line(row_to_clear, True, row_to_clear < y)
            elif isinstance(instruction, stransi.SetAttribute):
                # Attribute
                pass
            elif isinstance(instruction, stransi.Unsupported):
                raise ValueError("Unknown instruction " + repr(instruction.token))
            else:
                raise ValueError("Unknown instruction type " + str(type(instruction)))
        document.width = width
        document.height = height
        # Handle minimum height.
        while len(document.ch) <= document.height:
            document.ch.append([])
            document.bg.append([])
            document.fg.append([])
        # Pad rows to a consistent width.
        for y in range(document.height):
            for x in range(len(document.ch[y]), document.width):
                document.ch[y].append(' ')
                document.bg[y].append(default_bg)
                document.fg[y].append(default_fg)
        return document

    @staticmethod
    def from_text(text: str, default_bg: str = "#ffffff", default_fg: str = "#000000") -> 'AnsiArtDocument':
        """Creates a document from the given text, detecting if it uses ANSI control codes or not."""
        if ansi_detector_pattern.search(text):
            return AnsiArtDocument.from_ansi(text, default_bg, default_fg)
        else:
            return AnsiArtDocument.from_plain(text, default_bg, default_fg)

    @staticmethod
    def from_image_format(content: bytes) -> 'AnsiArtDocument':
        """Creates a document from the given bytes, detecting the file format.

        Raises UnidentifiedImageError if the format is not detected.
        """
        image = Image.open(io.BytesIO(content))
        rgb_image = image.convert('RGB') # handles indexed images, etc.
        width, height = rgb_image.size
        document = AnsiArtDocument(width, height)
        for y in range(height):
            for x in range(width):
                r, g, b = rgb_image.getpixel((x, y))  # type: ignore
                document.bg[y][x] = "#" + hex(r)[2:].zfill(2) + hex(g)[2:].zfill(2) + hex(b)[2:].zfill(2)  # type: ignore
        return document

    @staticmethod
    def from_svg(svg: str, default_bg: str = "#ffffff", default_fg: str = "#000000") -> 'AnsiArtDocument':
        """Creates a document from an SVG containing a character grid with rects for cell backgrounds.

        - If the SVG contains a special <ansi> element, this is used instead of anything else.
        Otherwise it falls back to flexible grid detection:
        - rect elements can be in any order.
        - rect elements can even be in different groups, however transforms are not considered.
        - rect elements can vary in size, spanning different numbers of cells, and the grid can be wonky.
        - rect elements can be missing, in which case the default background is used.
        - rect elements that frame the entire grid are ignored. (maybe should be used for background color?)
        - if there are any rect elements outside the grid, they will extend the grid; they're not distinguished.
        - fill OR style attributes (of rect/text elements) are used to determine the background/foreground colors.
        - text elements are assumed to be belonging to the cell according to their x/y,
          without regard to their size (textLength) or alignment (text-anchor).
        - stylesheets are partially supported.
        - not all CSS/SVG color formats are supported.

        To test the flexibility of this loader, I created pathological_character_grid.svg
        It contains out-of-order unevenly sized rects, missing rects, a background rect, and an emoji.
        It doesn't currently contain varying color formats, font sizes, alignments, or transforms,
        and it only uses style rather than fill, and text with tspan rather than text without.
        It also doesn't have spanned rects, because I didn't realize that was a thing until afterward.
        (Fun fact: I got the pathological SVG working before the rigid grid SVG as saved by the app.)

        To test it, run the following command:
        textual run --dev "src.textual_paint.paint --language en --clear-screen --inspect-layout --restart-on-changes 'samples/pathological_character_grid.svg'" --press ctrl+shift+s,left,left,left,left,.,s,a,v,e,d,enter,enter
        and check samples/pathological_character_grid.saved.svg
        There's also useful debug visuals saved in debug.svg (if enabled).
        Then add ".saved" to that command and run it to check the saved file.
        """
        import xml.etree.ElementTree as ET
        root = ET.fromstring(svg)

        ansi_el = root.find(".//{http://github.com/1j01/textual-paint}ansi")
        if ansi_el is not None:
            if ansi_el.text is None:
                return AnsiArtDocument(1, 1, default_bg, default_fg)
            ansi_text = base64.b64decode(ansi_el.text).decode("utf-8")
            return AnsiArtDocument.from_ansi(ansi_text, default_bg, default_fg)

        def add_debug_marker(x: float, y: float, color: str) -> None:
            """Adds a circle to the SVG at the given position, for debugging."""
            if not DEBUG_SVG_LOADING:
                return
            # without the namespace, it won't show up!
            marker = ET.Element("{http://www.w3.org/2000/svg}circle")
            marker.attrib["cx"] = str(x)
            marker.attrib["cy"] = str(y)
            marker.attrib["r"] = "1"
            marker.attrib["fill"] = color
            marker.attrib["stroke"] = "black"
            marker.attrib["stroke-width"] = "0.1"
            root.append(marker)

        # Parse stylesheets.
        # Textual's CSS parser can't handle at-rules like the @font-face in the SVG,
        # as of textual 0.24.1, so we either need to parse it manually or remove it.
        from textual.css.model import RuleSet
        from textual.css.parse import parse
        rule_sets: list[RuleSet] = []
        # OK this is seriously hacky. It doesn't support browser CSS really at all,
        # so I'm rewriting properties as different properties that it does support.
        property_map = {
            "fill": "color",
        }
        reverse_property_map = {v: k for k, v in property_map.items()}
        def rewrite_property(match: re.Match[str]) -> str:
            property_name = match.group(1)
            property_value = match.group(2)

            if property_name in property_map:
                rewritten_name = property_map[property_name]
                return f"{rewritten_name}: {property_value}"

            return match.group(0)  # Return the original match if no rewrite is needed

        for style_element in root.findall(".//{http://www.w3.org/2000/svg}style"):
            assert style_element.text is not None, "style element has no text"
            css = style_element.text
            at_rule_pattern = r"\s*@[\w-]+\s*{[^}]+}"  # doesn't handle nested braces
            css = re.sub(at_rule_pattern, "", css)
            property_pattern = r"([\w-]+)\s*:\s*([^;}]+)"

            css = re.sub(property_pattern, rewrite_property, css)

            for rule_set in parse(scope="", css=css, path="inline <style> (modified)"):
                rule_sets.append(rule_set)
        # Apply stylesheets as inline styles.
        for rule_set in rule_sets:
            # list[tuple[str, Specificity6, Any]]
            rules = rule_set.styles.extract_rules((0, 0, 0))
            for css_selector in rule_set.selector_names:
                # Just need to handle class and id selectors.
                if css_selector.startswith("."):
                    class_name = css_selector[1:]
                    # xpath = f".//*[contains(@class, '{class_name}')]" # not supported
                    xpath = f".//*[@class='{class_name}']"
                elif css_selector.startswith("#"):
                    id = css_selector[1:]
                    xpath = f".//*[@id='{id}']"
                else:
                    # xpath = "./.." # root's parent never matches
                    # (absolute xpath is not allowed here, but we're querying from root)
                    # Alternatively, we could do this:
                    xpath = ".//*[id='never-match-me-please']"
                for element in root.findall(xpath):
                    for rule in rules:
                        prop, _, value = rule
                        prop = reverse_property_map.get(prop, prop)
                        # it adds auto_color: False when setting a color; hacks on top of hacks
                        if isinstance(value, str):
                            element.attrib[prop] = value
                        elif isinstance(value, Color):
                            element.attrib[prop] = value.hex

        # Search for rect elements to define the background, and the cell locations.
        rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
        if len(rects) == 0:
            raise ValueError("No rect elements found in SVG.")
        # Remove any rects that contain other rects.
        # This targets any background/border rects framing the grid.
        # TODO: fix combinatorial explosion (maybe sort by size and do something fancier with that?)
        # Collision bucketization could apply here, but seems like overkill.
        # And what would be the bucket size? 1/10th of the smallest rect?
        # We haven't determined the cell size yet.
        def rect_contains(outer_rect: ET.Element, inner_rect: ET.Element) -> bool:
            return (
                float(outer_rect.attrib["x"]) <= float(inner_rect.attrib["x"]) and
                float(outer_rect.attrib["y"]) <= float(inner_rect.attrib["y"]) and
                float(outer_rect.attrib["x"]) + float(outer_rect.attrib["width"]) >= float(inner_rect.attrib["x"]) + float(inner_rect.attrib["width"]) and
                float(outer_rect.attrib["y"]) + float(outer_rect.attrib["height"]) >= float(inner_rect.attrib["y"]) + float(inner_rect.attrib["height"])
            )
        rects_to_ignore: set[ET.Element] = set()
        for i, outer_rect in enumerate(rects):
            for inner_rect in rects[i + 1:]:
                if outer_rect != inner_rect and rect_contains(outer_rect, inner_rect):
                    rects_to_ignore.add(outer_rect)
                    # Combinatorial explosion is much worse with logging enabled.
                    # print("Ignoring outer_rect: " + ET.tostring(outer_rect, encoding="unicode"))
                    # For debugging, outline the ignored rect.
                    if DEBUG_SVG_LOADING:
                        outer_rect.attrib["style"] = "stroke:#ff0000;stroke-width:1;stroke-dasharray:1,1;fill:none"

        rects = [rect for rect in rects if rect not in rects_to_ignore]

        # This could technically happen if there are two rects of the same size and position.
        assert len(rects) > 0, "No rect elements after removing rects containing other rects."

        # Find the cell size.
        # (This starts with a guess, and then is refined after guessing the document bounds.)
        # Strategy 1: average the rect sizes.
        # cell_width = sum(float(rect.attrib["width"]) for rect in rects) / len(rects)
        # cell_height = sum(float(rect.attrib["height"]) for rect in rects) / len(rects)
        # Rects can span multiple cells, so this doesn't turn out well.
        # Strategy 2: find the smallest rect.
        # cell_width = min(float(rect.attrib["width"]) for rect in rects)
        # cell_height = min(float(rect.attrib["height"]) for rect in rects)
        # That way there's at least a decent chance of it being a single cell.
        # But this doesn't contend with varying cell sizes of the pathological test case.
        # Strategy 3: find the smallest rect, then sort rects into rows and columns,
        # using the smallest rect as a baseline to decide what constitutes a row/column gap,
        # then use the average spacing between rects in adjacent rows/columns,
        # also using the smallest rect to avoid averaging in gaps that are more than one cell.
        # TODO: handle case that there's no 1x1 cell rect.
        min_width = min(float(rect.attrib["width"]) for rect in rects)
        min_height = min(float(rect.attrib["height"]) for rect in rects)
        # Start with each rect in its own track, then join tracks that are close enough.
        measures: dict[str, float] = {}
        Track = NamedTuple("Track", [("rects", list[ET.Element]), ("min_center", float), ("max_center", float)])
        def join_tracks(track1: Track, track2: Track) -> Track:
            return Track(track1.rects + track2.rects, min(track1.min_center, track2.min_center), max(track1.max_center, track2.max_center))
        def rect_center(rect: ET.Element, coord_attrib: str, size_attrib: str) -> float:
            return float(rect.attrib[coord_attrib]) + float(rect.attrib[size_attrib]) / 2
        axes: list[tuple[str, str, float]] = [("x", "width", min_width), ("y", "height", min_height)]
        for (coord_attrib, size_attrib, min_rect_size) in axes:
            # Can't have too many rects or this will be slow.
            # Note: this optimization invalidates most of the grid estimation strategy here,
            # without the second sort in the opposite axis.
            # (But it still worked without it, for the few cases I tested,
            # but probably more through luck of the first rect being the right size or something like that.
            # Um, not that, because it's using the spacing between rects, right? but something like that.)
            # (At any rate, just look at the debug.svg output to see what I mean.)
            # TODO: is the first sort even necessary?
            rects.sort(key=lambda rect: float(rect.attrib[coord_attrib]))
            rects.sort(key=lambda rect: float(rect.attrib["x" if coord_attrib == "y" else "y"]))
            max_rects = 30
            # Have to ignore rects that span multiple cells, since their centers can be half-off the grid
            # of cell-sized rect centers (which is normally half-off from the grid of cell corners).
            max_rect_size = min_rect_size * 1.5
            tracks = [
                Track(
                    [rect],
                    rect_center(rect, coord_attrib, size_attrib),
                    rect_center(rect, coord_attrib, size_attrib),
                )
                for rect in rects[:max_rects] if float(rect.attrib[size_attrib]) <= max_rect_size
            ]
            joined = True
            while joined and len(tracks) > 1:
                joined = False
                for i in range(len(tracks)):
                    for j in range(i + 1, len(tracks)):
                        # The cell spacing will be at least min_rect_size, probably.
                        # However, if we join columns that are one cell apart, we'll
                        # fail to measure the cell spacing, it'll be too big.
                        # We only want to join rects within a single column.
                        max_offset = min_rect_size * 0.9
                        """
                        # i_min--j_min--i_max--j_max
                        # (always join)
                        # or
                        # j_min--i_min--j_max--i_max
                        # (always join)
                        # or
                        # i_min----------------i_max j_min----------------j_max
                        # (join if abs(i_max - j_min) <= max_offset)
                        # or
                        # j_min----------------j_max i_min----------------i_max
                        # (join if abs(j_max - i_min) <= max_offset)

                        i_min = tracks[i].min_center
                        i_max = tracks[i].max_center
                        j_min = tracks[j].min_center
                        j_max = tracks[j].max_center

                        ranges_overlap = (i_min <= j_min <= i_max) or (j_min <= i_min <= j_max)
                        ends_near = min(abs(i_max - j_min), abs(j_max - i_min)) <= max_offset
                        if ranges_overlap or ends_near:
                        """
                        i_center = (tracks[i].min_center + tracks[i].max_center) / 2
                        j_center = (tracks[j].min_center + tracks[j].max_center) / 2
                        if abs(i_center - j_center) <= max_offset:
                            tracks[i] = join_tracks(tracks[i], tracks[j])
                            del tracks[j]
                            joined = True
                            break
                    if joined:
                        break
            # Sort tracks
            tracks.sort(key=lambda track: (track.min_center + track.max_center) / 2)
            # Visualize the tracks for debug
            if DEBUG_SVG_LOADING:
                for track in tracks:
                    ET.SubElement(root, "{http://www.w3.org/2000/svg}rect", {
                        "x": str(track.min_center) if coord_attrib == "x" else "0",
                        "y": str(track.min_center) if coord_attrib == "y" else "0",
                        "width": str(track.max_center - track.min_center + 0.001) if coord_attrib == "x" else "100%",
                        "height": str(track.max_center - track.min_center + 0.001) if coord_attrib == "y" else "100%",
                        # "style": "stroke:#0000ff;stroke-width:0.1;stroke-dasharray:1,1;fill:none"
                        "style": "fill:#0000ff;fill-opacity:0.1;stroke:#0000ff;stroke-width:0.1"
                    })

            # Find the average spacing between tracks, ignoring gaps that are likely to be more than one cell.
            # I'm calling this gap because I'm lazy.
            max_gap = min_rect_size * 2
            all_gaps: list[float] = []
            gaps: list[float] = []
            for i in range(len(tracks) - 1):
                i_center = (tracks[i].max_center + tracks[i].min_center) / 2
                j_center = (tracks[i + 1].max_center + tracks[i + 1].min_center) / 2
                gap = abs(j_center - i_center) # abs shouldn't be necessary, but just in case I guess
                if DEBUG_SVG_LOADING:
                    ET.SubElement(root, "{http://www.w3.org/2000/svg}line", {
                        "x1": str(i_center) if coord_attrib == "x" else ("5%" if i % 2 == 0 else "2%"),
                        "y1": str(i_center) if coord_attrib == "y" else ("5%" if i % 2 == 0 else "2%"),
                        "x2": str(j_center) if coord_attrib == "x" else ("5%" if i % 2 == 0 else "2%"),
                        "y2": str(j_center) if coord_attrib == "y" else ("5%" if i % 2 == 0 else "2%"),
                        "stroke": "#ff0000" if gap > max_gap else "#0051ff",
                    })
                all_gaps.append(gap)
                if gap <= max_gap:
                    gaps.append(gap)
            if len(gaps) == 0:
                measures[coord_attrib] = min_rect_size
            else:
                measures[coord_attrib] = sum(gaps) / len(gaps)

        cell_width = measures["x"]
        cell_height = measures["y"]

        print("Initial cell size guess: " + str(cell_width) + " x " + str(cell_height))
        # Find the document bounds.
        min_x = min(float(rect.attrib["x"]) for rect in rects)
        min_y = min(float(rect.attrib["y"]) for rect in rects)
        max_x = max(float(rect.attrib["x"]) + float(rect.attrib["width"]) for rect in rects)
        max_y = max(float(rect.attrib["y"]) + float(rect.attrib["height"]) for rect in rects)
        add_debug_marker(min_x, min_y, "blue")
        add_debug_marker(max_x, max_y, "blue")
        width = int((max_x - min_x) / cell_width + 1/9)
        height = int((max_y - min_y) / cell_height + 1/9)
        # Adjust cell width/height based on document bounds.
        cell_width = (max_x - min_x) / width
        cell_height = (max_y - min_y) / height
        print("Refined cell size estimate: " + str(cell_width) + " x " + str(cell_height))
        # Create the document.
        document = AnsiArtDocument(width, height, default_bg, default_fg)
        # Fill the document with the background colors.
        def get_fill(el: ET.Element) -> Optional[str]:
            fill = None
            try:
                fill = el.attrib["fill"]
            except KeyError:
                try:
                    style = el.attrib["style"]
                except KeyError:
                    print("Warning: element has no fill or style attribute: " + ET.tostring(el, encoding="unicode"))
                else:
                    for style_part in style.split(";"):
                        if style_part.startswith("fill:"):
                            fill = style_part[len("fill:"):]
                            break
            if fill is None or fill == "none" or fill == "":
                print("Warning: element has no fill defined: " + ET.tostring(el, encoding="unicode"))
                return None
            try:
                r, g, b = Color.parse(fill).rgb
                return "#" + hex(r)[2:].zfill(2) + hex(g)[2:].zfill(2) + hex(b)[2:].zfill(2)
            except ColorParseError:
                print("Warning: element has invalid fill: " + ET.tostring(el, encoding="unicode"))
                return None

        for rect in rects:
            fill = get_fill(rect)
            for x_offset in range(int(float(rect.attrib["width"]) / cell_width + 1/2)):
                for y_offset in range(int(float(rect.attrib["height"]) / cell_height + 1/2)):
                    x = float(rect.attrib["x"]) + cell_width * (x_offset + 1/2)
                    y = float(rect.attrib["y"]) + cell_height * (y_offset + 1/2)
                    add_debug_marker(x, y, "red")
                    x = int((x - min_x) / cell_width)
                    y = int((y - min_y) / cell_height)
                    if fill is not None:
                        try:
                            document.bg[y][x] = fill
                        except IndexError:
                            print("Warning: rect out of bounds: " + ET.tostring(rect, encoding="unicode"))

        # Find text elements to define the foreground.
        texts = root.findall(".//{http://www.w3.org/2000/svg}text")
        if len(texts) == 0:
            raise ValueError("No text elements found in SVG.")
        for text in texts:
            # approximate center of text
            # y position really depends on font size, as well as the baseline y position.
            x = (float(text.attrib["x"]) + cell_width/2)
            y = (float(text.attrib["y"]) - cell_height/4)
            add_debug_marker(x, y, "yellow")
            x = int((x - min_x) / cell_width)
            y = int((y - min_y) / cell_height)

            ch = text.text
            if ch is None:
                tspans = text.findall(".//{http://www.w3.org/2000/svg}tspan")
                if len(tspans) == 0:
                    print("Warning: text element has no text or tspan: " + ET.tostring(text, encoding="unicode"))
                    continue
                ch = ""
                for tspan in tspans:
                    if tspan.text is not None:
                        ch += tspan.text
                    else:
                        print("Warning: tspan element has no text: " + ET.tostring(tspan, encoding="unicode"))
            # This is likely to cause problems with multi-character emojis, like flags,
            # although such characters are unlikely to work in the terminal anyway.
            # if len(ch) > 1:
            #     print("Warning: text element has more than one character: " + ET.tostring(text, encoding="unicode"))
            #     ch = ch[0]
            fill = get_fill(text)
            try:
                document.ch[y][x] = ch
                if fill is not None:
                    document.fg[y][x] = fill
            except IndexError:
                print("Warning: text element is out of bounds: " + ET.tostring(text, encoding="unicode"))
                continue

        # For debugging, write the SVG with the ignored rects outlined, and coordinate markers added.
        if DEBUG_SVG_LOADING:
            ET.ElementTree(root).write("debug.svg", encoding="unicode")

        return document

    @staticmethod
    def decode_based_on_file_extension(content: bytes, file_path: str, default_bg: str = "#ffffff", default_fg: str = "#000000") -> 'AnsiArtDocument':
        """Creates a document from the given bytes, detecting the file format.

        Raises FormatReadNotSupported if the file format is not supported for reading. Some are write-only.
        Raises UnicodeDecodeError, which can be a very long message, so make sure to handle it!
        Raises UnidentifiedImageError if the format is not detected.
        """
        format_id = AnsiArtDocument.format_from_extension(file_path)
        # print("Supported image formats for reading:", Image.OPEN.keys())
        # TODO: try loading as image first, then as text if that fails with UnidentifiedImageError
        # That way it can handle images without file extensions.
        if format_id in Image.OPEN:
            return AnsiArtDocument.from_image_format(content)
        elif format_id == "ANSI":
            return AnsiArtDocument.from_ansi(content.decode('utf-8'), default_bg, default_fg)
        elif format_id == "IRC":
            return AnsiArtDocument.from_irc(content.decode('utf-8'), default_bg, default_fg)
        elif format_id == "PLAINTEXT":
            return AnsiArtDocument.from_plain(content.decode('utf-8'), default_bg, default_fg)
        elif format_id == "SVG":
            return AnsiArtDocument.from_svg(content.decode('utf-8'), default_bg, default_fg)
        elif format_id in Image.SAVE or format_id in ["HTML", "RICH_CONSOLE_MARKUP"]:
            # This is a write-only format.
            raise FormatReadNotSupported(localized_message=_("Cannot read files saved as %1 format.", format_id))
        else:
            # This is an unknown format.
            # For now at least, I'm preserving the behavior of loading as ANSI/PLAINTEXT.
            return AnsiArtDocument.from_text(content.decode('utf-8'), default_bg, default_fg)

class Selection:
    """
    A selection within an AnsiArtDocument.

    AnsiArtDocument can contain a Selection, and Selection can contain an AnsiArtDocument.
    However, the selection's AnsiArtDocument should never itself contain a Selection.

    When a selection is created, it has no image data, but once it's dragged,
    it gets a copy of the image data from the document.
    The image data is stored as an AnsiArtDocument, since it's made up of characters and colors.
    """
    def __init__(self, region: Region) -> None:
        """Initialize a selection."""
        self.region: Region = region
        """The region of the selection within the outer document."""
        self.contained_image: Optional[AnsiArtDocument] = None
        """The image data contained in the selection, None until dragged, except for text boxes."""
        self.pasted: bool = False
        """Whether the selection was pasted from the clipboard, and thus needs an undo state created for it when melding."""
        self.textbox_mode = False
        """Whether the selection is a text box. Either way it's text, but it's a different editing mode."""
        self.textbox_edited = False
        """Whether text has been typed into the text box, ever. If not, the textbox can be deleted when clicking off."""
        self.text_selection_start = Offset(0, 0)
        """The start position of the text selection within the text box. This may be before or after the end."""""
        self.text_selection_end = Offset(0, 0)
        """The end position of the text selection within the text box. This may be before or after the start."""""
        self.mask: Optional[list[list[bool]]] = None
        """A mask of the selection to cut out, used for Free-Form Select tool. Coordinates are relative to the selection region."""

    def copy_from_document(self, document: 'AnsiArtDocument') -> None:
        """Copy the image data from the document into the selection."""
        self.contained_image = AnsiArtDocument(self.region.width, self.region.height)
        self.contained_image.copy_region(source=document, source_region=self.region)

    def copy_to_document(self, document: 'AnsiArtDocument') -> None:
        """Draw the selection onto the document."""
        if not self.contained_image:
            # raise ValueError("Selection has no image data.")
            return

        # Prevent out of bounds errors (IndexError: list assignment index out of range)
        # by clipping the target region to the document, and adjusting the source region accordingly.
        target_region = self.region.intersection(Region(0, 0, document.width, document.height))
        source_region = Region(target_region.x - self.region.x, target_region.y - self.region.y, self.contained_image.width, self.contained_image.height)

        # Offset mask due to account for the intersection.
        # This is probably not the best way (or place) to do this.
        # If refactoring, make sure to run:
        #     pytest -k test_free_form_select_meld_negative_coords
        # (and then all the tests)
        offset = target_region.offset - self.region.offset
        if self.mask:
            def sample(x: int, y: int) -> bool:
                assert self.mask is not None
                try:
                    return self.mask[y + offset.y][x + offset.x]
                except IndexError:
                    return False
            mask = [[sample(x, y) for x in range(source_region.width)] for y in range(source_region.height)]
        else:
            mask = None

        document.copy_region(source=self.contained_image, source_region=source_region, target_region=target_region, mask=mask)
