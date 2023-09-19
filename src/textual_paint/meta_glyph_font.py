"""Drawing large text characters with smaller characters."""

import os

from pyfiglet import Figlet, FigletFont  # type: ignore


class MetaGlyphFont:
    """A font where each character is drawn with sub-characters."""

    def __init__(self, file_path: str, width: int, height: int, covered_characters: str):
        self.file_path = file_path
        """The path to the font file."""
        self.glyphs: dict[str, list[str]] = {}
        """Maps characters to meta-glyphs, where each meta-glyph is a list of rows of characters."""
        self.width = width
        """The width in characters of a meta-glyph."""
        self.height = height
        """The height in characters of a meta-glyph."""
        self.covered_characters = covered_characters
        """The characters supported by this font."""

        # EXCLUDE certain characters which are better handled by procedural glyph rendering.
        for ch in " ░▒▓██▔🮂🮃▀🮄🮅🮆▇▆▅▄▃▂▁▏▎▍▌▋▊▉███🮋🮊🮉▐🮈🮇▕":
            self.covered_characters = self.covered_characters.replace(ch, "")

        self.load()

    def load(self):
        """Load the font from the .flf FIGlet font file."""
        # fig = Figlet(font=self.file_path) # gives FontNotFound error!
        # Figlet constructor only supports looking for installed fonts.
        # I could install the font, with FigletFont.installFonts,
        # maybe with some prefixed name, but I don't want to do that.

        with open(self.file_path, encoding="utf-8") as f:
            flf = f.read()
            fig_font = FigletFont()
            fig_font.data = flf
            fig_font.loadFont()
            fig = Figlet()
            # fig.setFont(font=fig_font) # nope, that's also looking for a font name
            fig.font = self.file_path  # may not be used
            fig.Font = fig_font  # this feels so wrong
            for char in self.covered_characters:
                meta_glyph = fig.renderText(char)
                self.glyphs[char] = meta_glyph.split("\n")

covered_characters = R""" !"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~"""
meta_glyph_fonts: dict[int, MetaGlyphFont] = {
    2: MetaGlyphFont(os.path.join(os.path.dirname(__file__), "fonts/NanoTiny/NanoTiny_v14_2x2.flf"), 2, 2, covered_characters),
    # 4: MetaGlyphFont(os.path.join(os.path.dirname(__file__), "fonts/NanoTiny/NanoTiny_v14_4x4.flf"), 4, 4, covered_characters),
    # TODO: less specialized (more practical) fonts for larger sizes
    # Also ASCII-only fonts for --ascii-only mode
}

def largest_font_that_fits(max_width: int, max_height: int) -> MetaGlyphFont | None:
    """Get the largest font with glyphs that can all fit in the given dimensions."""
    for font_size in sorted(meta_glyph_fonts.keys(), reverse=True):
        font = meta_glyph_fonts[font_size]
        if font.width <= max_width and font.height <= max_height:
            return font
    return None

