#!/usr/bin/env python3

# Install with `pip install -e .` in the root directory of the repository before running this script.
# This is needed because PYTHON HAS NO GOOD WAY OF IMPORTING FILES RELATIVELY.
# It can't be done outside of a package. Why? WHY?!

import os
from PIL import Image

from textual_paint.figlet_font_writer import FIGletFontWriter

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

            # getpixel returns different types depending on the image mode
            assert texture.getbands() == ('P',), f'Expected palettized image, got {texture.getbands()}'
            def at(x: int, y: int) -> bool:
                fg_palette_index = 1
                return texture.getpixel((x, y)) == fg_palette_index # type: ignore

            # Extract as half-size FIGlet font
            extracted_text_half = ""
            for y in range(0, texture_height, 2):
                for x in range(0, texture_width, 2):
                    # Get the four pixels that make up a character
                    aa = at(x, y)
                    ab = at(x, y + 1)
                    ba = at(x + 1, y)
                    bb = at(x + 1, y + 1)

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
                    extracted_text_full += '█' if at(x, y) else ' '

                # Add a newline after each row
                extracted_text_full += '\n'
            
            full_size_meta_glyphs[ordinal] = extracted_text_full
    
    for figChars in [half_size_meta_glyphs, full_size_meta_glyphs]:
        # Fill in the space characters with hard blanks
        # figChars[32] = figChars[32].replace(' ', '$')
        # Or just half of the max width of the FIGcharacters
        figChars[32] = '\n'.join(['$' * (len(row) // 2) for row in figChars[32].split('\n')])
        # Add hard blanks to the end of non-whitespace of each row of each FIGcharacter
        # With FIGletFontWriter.Layout.FULL, this will ensure a space between rendered FIGcharacters.
        # The fixup code (_fixFigChars) will handle the ragged right edge,
        # although it won't look pretty having the dollar signs scattered in the font file.
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
        horizontalLayout=FIGletFontWriter.Layout.FULL,
        verticalLayout=FIGletFontWriter.Layout.FULL,
    )
    full_size_font = FIGletFontWriter(
        figChars=full_size_meta_glyphs,
        baseline=4,
        commentLines=[
            "NanoTiny 4x4 (version 14)",
            *shared_comment_lines,
        ],
        horizontalLayout=FIGletFontWriter.Layout.FULL,
        verticalLayout=FIGletFontWriter.Layout.FULL,
    )

    return extracted_image, half_size_font.createFigFileData(), full_size_font.createFigFileData()

repo_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
font_folder = os.path.join(repo_folder, 'src/textual_paint/fonts/NanoTiny')
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
