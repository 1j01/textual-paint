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
    extracted_text_half = ""
    extracted_text_full = ""

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

            # Extract as text
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
            # extracted_text += '(end of character ' + str(row * num_textures_x + col) + ')\n'

            # Extract as text 2
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

    return extracted_image, extracted_text_half, extracted_text_full

base_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
samples_folder = os.path.join(base_folder, 'samples')
image_path = os.path.join(samples_folder, 'NanoTiny_v14.png')
output_path = os.path.join(samples_folder, 'NanoTiny_v14_no_border.png')
half_size_text_output_path = os.path.join(base_folder, 'NanoTiny_v14_2x2.txt')
full_size_text_output_path = os.path.join(base_folder, 'NanoTiny_v14_4x4.txt')

extracted_image, extracted_text_half, extracted_text_full = extract_textures(image_path)
extracted_image.save(output_path)
print(f'Wrote extracted textures to {output_path}')
with open(full_size_text_output_path, 'w') as f:
    f.write(extracted_text_full)
print(f'Wrote extracted textures to {full_size_text_output_path}')
with open(half_size_text_output_path, 'w') as f:
    f.write(extracted_text_half)
print(f'Wrote extracted textures to {half_size_text_output_path}')
