#!/usr/bin/env python3

import os
from PIL import Image

block_char_lookup = {
    0x0: ' ',
    0x1: '▘',
    0x2: '▝',
    0x3: '▀',
    0x4: '▖',
    0x5: '▌',
    0x6: '▞',
    0x7: '▛',
    0x8: '▗',
    0x9: '▚',
    0xA: '▐',
    0xB: '▜',
    0xC: '▄',
    0xD: '▙',
    0xE: '▟',
    0xF: '█',
}

def spacePad(num: int) -> str:
    return ' ' * num

def blankLines(num: int, width: int) -> str:
    lines = [spacePad(width) for _ in range(num)]
    return '\n'.join(lines)

class FIGletFontWriter:
    """Used to write FIGlet fonts.
    
    createFigFileData() returns a string that can be written to a .flf file.

    It can automatically fix some common problems with FIGlet fonts, such as
    incorrect character widths/heights, and missing lowercase characters.

    This Python code is based on JS from http://patorjk.com/figlet-editor/
    """

    """
    Copyright (c) 2023 Patrick Gillespie

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
    """

    charOrder: list[int] = [ii for ii in range(32, 127)] + [196, 214, 220, 228, 246, 252, 223]
    R"""Character codes that are required to be in any FIGlet font.
    
    Printable portion of the ASCII character set:
32 (blank/space) 64 @             96  `
33 !             65 A             97  a
34 "             66 B             98  b
35 #             67 C             99  c
36 $             68 D             100 d
37 %             69 E             101 e
38 &             70 F             102 f
39 '             71 G             103 g
40 (             72 H             104 h
41 )             73 I             105 i
42 *             74 J             106 j
43 +             75 K             107 k
44 ,             76 L             108 l
45 -             77 M             109 m
46 .             78 N             110 n
47 /             79 O             111 o
48 0             80 P             112 p
49 1             81 Q             113 q
50 2             82 R             114 r
51 3             83 S             115 s
52 4             84 T             116 t
53 5             85 U             117 u
54 6             86 V             118 v
55 7             87 W             119 w
56 8             88 X             120 x
57 9             89 Y             121 y
58 :             90 Z             122 z
59 ;             91 [             123 {
60 <             92 \             124 |
61 =             93 ]             125 }
62 >             94 ^             126 ~
63 ?             95 _
Additional required Deutsch FIGcharacters, in order:
196 Ä (umlauted "A" -- two dots over letter "A")
214 Ö (umlauted "O" -- two dots over letter "O")
220 Ü (umlauted "U" -- two dots over letter "U")
228 ä (umlauted "a" -- two dots over letter "a")
246 ö (umlauted "o" -- two dots over letter "o")
252 ü (umlauted "u" -- two dots over letter "u")
223 ß ("ess-zed" -- see FIGcharacter illustration below)
                              ___
                             / _ \
                            | |/ /
          Ess-zed >>--->    | |\ \
                            | ||_/
                            |_|

Additional characters must use code tagged characters, which are not yet supported.
"""

    def __init__(
        self,
        figChars: dict[int, str] = {},
        height: int | None = None,
        baseline: int | None = None,
        maxLength: int | None = None,
        commentLines: list[str] = [],
        rightToLeft: bool = False,
        horizontalLayout: str = 'Universal Smushing',
        verticalLayout: str = 'Universal Smushing',
        codeTagCount: int = 0,
        hardBlank: str = "$",
        endMark: str = "@",
        caseInsensitive: bool = False,
    ):
        self.figChars: dict[int, str] = figChars
        """Dictionary that maps character codes to FIGcharacter strings."""
        self.height = height
        """Height of a FIGcharacter, in characters."""
        self.baseline = baseline
        """Distance from the top of the character to the baseline. If not specified, defaults to height."""
        self.maxLength = maxLength
        """Maximum length of a line INCLUDING two endMark characters."""
        self.commentLines: list[str] = commentLines
        """List of comment lines to be included in the header. It's recommended to include at least the name of the font and the name of the author."""
        self.rightToLeft = rightToLeft
        """Indicates RTL writing direction (or LTR if False)."""
        self.codeTagCount = codeTagCount
        """Number of extra characters included in the font (in addition to the required 102 untagged characters). Outputting tagged characters is not yet supported."""
        self.hardBlank = hardBlank
        """Invisible character used to prevent smushing."""
        self.endMark = endMark
        """Denotes the end of a line. Two of these characters in a row denotes the end of a FIGcharacter."""
        self.horizontalLayout = horizontalLayout
        """One of 'Full', 'Fitted', 'Universal Smushing', or 'Controlled Smushing'"""
        self.verticalLayout = verticalLayout
        """One of 'Full', 'Fitted', 'Universal Smushing', or 'Controlled Smushing'"""
        self.hRule = [False] * 7
        """Horizontal Smushing Rules, 1-6 (0 is not used, so that indices correspond with the names of the parameters). horizontalLayout must be 'Controlled Smushing' for these to take effect."""
        self.vRule = [False] * 6
        """Vertical Smushing Rules, 1-5 (0 is not used, so that indices correspond with the names of the parameters). verticalLayout must be 'Controlled Smushing' for these to take effect."""
        self.caseInsensitive = caseInsensitive
        """Makes lowercase same as uppercase. Note that this is one-way overwrite. It doesn't check if a character already exists, and it won't fill in uppercase using lowercase."""

    def _getOldLayoutValue(self) -> int:
        val = 0
        if self.horizontalLayout == 'Full':
            return -1
        elif self.horizontalLayout == 'Fitted':
            return 0
        elif self.horizontalLayout == 'Universal Smushing':
            return 0
        else:
            val += 1 if self.hRule[1] else 0
            val += 2 if self.hRule[2] else 0
            val += 4 if self.hRule[3] else 0
            val += 8 if self.hRule[4] else 0
            val += 16 if self.hRule[5] else 0
            val += 32 if self.hRule[6] else 0
        return val

    def _getFullLayoutValue(self) -> int:
        val = 0

        # horizontal rules
        if self.horizontalLayout == 'Full':
            val += 0
        elif self.horizontalLayout == 'Fitted':
            val += 64
        elif self.horizontalLayout == 'Universal Smushing':
            val += 128
        else:
            val += 128
            val += 1 if self.hRule[1] else 0
            val += 2 if self.hRule[2] else 0
            val += 4 if self.hRule[3] else 0
            val += 8 if self.hRule[4] else 0
            val += 16 if self.hRule[5] else 0
            val += 32 if self.hRule[6] else 0

        # vertical rules
        if self.verticalLayout == 'Full':
            val += 0
        elif self.verticalLayout == 'Fitted':
            val += 8192
        elif self.verticalLayout == 'Universal Smushing':
            val += 16384
        else:
            val += 16384
            val += 256 if self.vRule[1] else 0
            val += 512 if self.vRule[2] else 0
            val += 1024 if self.vRule[3] else 0
            val += 2048 if self.vRule[4] else 0
            val += 4096 if self.vRule[5] else 0

        return val

    def generateFigFontHeader(self) -> str:
        header: list[str] = []
        baseline = self.baseline

        if self.height is None:
            raise ValueError("Height must be specified, or should be automatically determined.")
        if baseline is None:
            baseline = self.height
        baseline = int(baseline)
        if baseline <= 0 or baseline > self.height:
            baseline = self.height

        header.append('flf2a' + self.hardBlank)
        header.append(str(self.height))
        header.append(str(baseline))
        header.append(str(self.maxLength))
        header.append(str(self._getOldLayoutValue()))
        header.append(str(len(self.commentLines)))
        header.append("1" if self.rightToLeft else "0")
        header.append(str(self._getFullLayoutValue()))
        header.append(str(self.codeTagCount))

        return ' '.join(header)

    def _fixFigChars(self):
        height = 0
        charWidth: dict[int, int] = {}
        maxWidth = 0

        # Fix case insensitivity
        if self.caseInsensitive is True:
            for ii in range(97, 123):
                self.figChars[ii] = self.figChars[ii - 32]

        # Calculate max height and ensure consistent width for each character
        for idx in self.figChars:
            figChar = self.figChars[idx].replace('\r\n', '\n').split('\n')
            height = max(height, len(figChar))
            charWidth[idx] = 0

            for line in figChar:
                charWidth[idx] = max(charWidth[idx], len(line))

            for i in range(len(figChar)):
                if len(figChar[i]) < charWidth[idx]:
                    figChar[i] += spacePad(charWidth[idx] - len(figChar[i]))

                maxWidth = max(maxWidth, charWidth[idx])

            self.figChars[idx] = '\n'.join(figChar)

        # Fix any height issues
        for idx in self.figChars:
            figChar = self.figChars[idx].replace('\r\n', '\n').split('\n')
            if len(figChar) < height:
                self.figChars[idx] = '\n'.join(figChar) + '\n' + blankLines(height - len(figChar), charWidth[idx])

        self.height = height
        self.maxLength = maxWidth + 2

    def createFigFileData(self) -> str:
        """Generates the FIGlet file data for the current font."""
        output = ''
        self._fixFigChars()

        output = self.generateFigFontHeader() + '\n'
        output += "\n".join(self.commentLines) + '\n'

        for char in self.charOrder:
            figChar = self.figChars.get(char)
            if figChar is None:
                raise Exception(f"Character {char} missing from figChars")
            output += (self.endMark + '\n').join(figChar.split('\n'))
            output += self.endMark + self.endMark + '\n'

        return output

def extract_textures(image_path: str):
    """Removes the border around glyphs in an image, creates a new image without the border, and converts the image into FIGlet format font files."""

    # Open the image
    image = Image.open(image_path)

    # Calculate the texture size and border width
    width, height = image.size
    texture_width = 4
    texture_height = 4
    border_width = 1

    # Calculate the number of textures in each dimension
    num_textures_x = (width - border_width) // (texture_width + border_width)
    num_textures_y = (height - border_width) // (texture_height + border_width)

    # Create a new image to store the extracted textures
    extracted_image = Image.new('RGB', (num_textures_x * texture_width, num_textures_y * texture_height))
    
    half_size_meta_glyphs: dict[int, str] = {}
    full_size_meta_glyphs: dict[int, str] = {}

    # Extract textures
    for row in range(num_textures_y):
        for col in range(num_textures_x):
            # Calculate the coordinates for the current texture
            left = col * (texture_width + border_width) + border_width
            upper = row * (texture_height + border_width) + border_width
            right = left + texture_width
            lower = upper + texture_height

            # Crop the texture from the original image
            texture = image.crop((left, upper, right, lower))

            # Calculate the paste coordinates on the extracted image
            paste_x = col * texture_width
            paste_y = row * texture_height

            # Paste the texture onto the extracted image
            extracted_image.paste(texture, (paste_x, paste_y))

            # Calculate the ordinal of the character
            ordinal = row * num_textures_x + col
            ordinal -= 2
            
            # Extract as half-size FIGlet font
            extracted_text_half = ""
            for y in range(0, texture_height, 2):
                for x in range(0, texture_width, 2):
                    # Get the four pixels that make up a character
                    fg_palette_index = 1
                    aa = texture.getpixel((x, y)) == fg_palette_index
                    ab = texture.getpixel((x, y + 1)) == fg_palette_index
                    ba = texture.getpixel((x + 1, y)) == fg_palette_index
                    bb = texture.getpixel((x + 1, y + 1)) == fg_palette_index

                    # Convert the pixel to a character
                    # char = block_char_lookup[(aa << 3) | (ab << 2) | (ba << 1) | bb]
                    char = block_char_lookup[(bb << 3) | (ab << 2) | (ba << 1) | aa]

                    # Add the character to the extracted text
                    extracted_text_half += char

                # Add a newline after each row
                extracted_text_half += '\n'
            
            half_size_meta_glyphs[ordinal] = extracted_text_half
            
            # Extract as full-size FIGlet font
            extracted_text_full = ""
            for y in range(texture_height):
                for x in range(texture_width):
                    # Get the pixel
                    fg_palette_index = 1
                    pixel = texture.getpixel((x, y)) == fg_palette_index

                    # Convert the pixel to a character
                    char = '█' if pixel else ' '

                    # Add the character to the extracted text
                    extracted_text_full += char

                # Add a newline after each row
                extracted_text_full += '\n'
            
            full_size_meta_glyphs[ordinal] = extracted_text_full
    
    for figChars in [half_size_meta_glyphs, full_size_meta_glyphs]:
        # Fill in the space characters with hard blanks
        # figChars[32] = figChars[32].replace(' ', '$')
        # Or just half of the max width of the FIGcharacters
        figChars[32] = '\n'.join(['$' * (len(row) // 2) for row in figChars[32].split('\n')])
        # Add hard blanks to the end of non-whitespace of each row of each FIGcharacter
        # With the "Full" layout, this will ensure a space between rendered FIGcharacters.
        # The fixup code (_fixFigChars) will handle the ragged right edge.
        for ordinal in figChars:
            figChars[ordinal] = '\n'.join([row.rstrip() + '$' for row in figChars[ordinal].split('\n')])
    
    shared_comment_lines = [
        "by Isaiah Odhner",
        "",
        "Copyright (c) 2023, Isaiah Odhner (https://isaiahodhner.io),",
        "with Reserved Font Name NanoTiny.",
        "",
        "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
        "This license is available in OFL.txt and is also available with a FAQ at:",
        "http://scripts.sil.org/OFL",
    ]
    half_size_font = FIGletFontWriter(
        figChars=half_size_meta_glyphs,
        baseline=2,
        commentLines=[
            "NanoTiny 2x2 (version 14)",
            *shared_comment_lines,
        ],
        horizontalLayout="Full",
        verticalLayout="Full",
    )
    full_size_font = FIGletFontWriter(
        figChars=full_size_meta_glyphs,
        baseline=4,
        commentLines=[
            "NanoTiny 4x4 (version 14)",
            *shared_comment_lines,
        ],
        horizontalLayout="Full",
        verticalLayout="Full",
    )

    return extracted_image, half_size_font.createFigFileData(), full_size_font.createFigFileData()

repo_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
font_folder = os.path.join(repo_folder, 'fonts/NanoTiny')
image_input_path = os.path.join(font_folder, 'NanoTiny_v14.png')
image_output_path = os.path.join(font_folder, 'NanoTiny_v14_no_border.png')
half_size_flf_output_path = os.path.join(font_folder, 'NanoTiny_v14_2x2.flf')
full_size_flf_output_path = os.path.join(font_folder, 'NanoTiny_v14_4x4.flf')

extracted_image, extracted_text_half, extracted_text_full = extract_textures(image_input_path)
extracted_image.save(image_output_path)
print(f'Wrote extracted textures to {image_output_path}')
with open(full_size_flf_output_path, 'w') as f:
    f.write(extracted_text_full)
print(f'Wrote FIGlet font {full_size_flf_output_path}')
with open(half_size_flf_output_path, 'w') as f:
    f.write(extracted_text_half)
print(f'Wrote FIGlet font {half_size_flf_output_path}')
