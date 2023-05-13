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

    charOrder: list[int] = [ii for ii in range(32, 127)] + [196, 214, 220, 228, 246, 252, 223]

    def __init__(
        self,
        fontName: str,
        figChars: dict[int, str],
        height: int,
        baseline: int,
        maxLength: int,
        commentLines: list[str],
        rightToLeft: bool = False,
        horizontalLayout: str = 'Universal Smushing',
        verticalLayout: str = 'Universal Smushing',
        codeTagCount: int = 0,
        hardBlank: str = "$",
        endMark: str = "@",
        caseInsensitive: bool = False
    ):
        self.fontName = fontName
        self.figChars: dict[int, str] = figChars
        self.height = height
        self.baseline = baseline
        self.maxLength = maxLength
        self.commentLines: list[str] = commentLines
        self.rightToLeft = rightToLeft
        self.codeTagCount = codeTagCount
        self.hardBlank = hardBlank
        self.endMark = endMark
        self.horizontalLayout = horizontalLayout
        self.verticalLayout = verticalLayout
        self.hRule = [False] * 7
        self.vRule = [False] * 7
        self.caseInsensitive = caseInsensitive

    def getOldLayoutValue(self) -> int:
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

    def getFullLayoutValue(self) -> int:
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

        if not baseline:
            baseline = self.height
        baseline = int(baseline)
        if baseline <= 0 or baseline > self.height:
            baseline = self.height

        header.append('flf2a' + self.hardBlank)
        header.append(str(self.height))
        header.append(str(baseline))
        header.append(str(self.maxLength))
        header.append(str(self.getOldLayoutValue()))
        header.append(str(len(self.commentLines)))
        header.append("1" if self.rightToLeft else "0")
        header.append(str(self.getFullLayoutValue()))
        header.append(str(self.codeTagCount))

        return ' '.join(header)

    def fixFigChars(self):
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
        output = ''
        self.fixFigChars()

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
    
    half_size_meta_glyphs = {}
    full_size_meta_glyphs = {}

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
            
    
    half_size_font = FIGletFontWriter(
        fontName="NanoTiny 2x2",
        figChars=half_size_meta_glyphs,
        height=2,
        baseline=2,
        maxLength=2,
        commentLines=[
            "NanoTiny 2x2",
            "by Isaiah Odhner",
        ],
        horizontalLayout="Full",
        verticalLayout="Full",
    )
    full_size_font = FIGletFontWriter(
        fontName="NanoTiny 4x4",
        figChars=full_size_meta_glyphs,
        height=4,
        baseline=4,
        maxLength=4,
        commentLines=[
            "NanoTiny 4x4",
            "by Isaiah Odhner",
        ],
        horizontalLayout="Full",
        verticalLayout="Full",
    )

    return extracted_image, half_size_font.createFigFileData(), full_size_font.createFigFileData()

base_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
samples_folder = os.path.join(base_folder, 'samples')
image_path = os.path.join(samples_folder, 'NanoTiny_v14.png')
output_path = os.path.join(samples_folder, 'NanoTiny_v14_no_border.png')
half_size_flf_output_path = os.path.join(base_folder, 'NanoTiny_v14_2x2.flf')
full_size_flf_output_path = os.path.join(base_folder, 'NanoTiny_v14_4x4.flf')

extracted_image, extracted_text_half, extracted_text_full = extract_textures(image_path)
extracted_image.save(output_path)
print(f'Wrote extracted textures to {output_path}')
with open(full_size_flf_output_path, 'w') as f:
    f.write(extracted_text_full)
print(f'Wrote FIGlet font {full_size_flf_output_path}')
with open(half_size_flf_output_path, 'w') as f:
    f.write(extracted_text_half)
print(f'Wrote FIGlet font {half_size_flf_output_path}')
