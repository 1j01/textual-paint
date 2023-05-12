#!/usr/bin/env python3

import os
from PIL import Image

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

    return extracted_image

samples_folder = os.path.join(os.path.dirname(__file__), '../../samples')
image_path = os.path.join(samples_folder, 'NanoTiny_v14.png')
output_path = os.path.join(samples_folder, 'NanoTiny_v14_no_border.png')

extracted_image = extract_textures(image_path)
extracted_image.save(output_path)
print(f'Wrote extracted textures to {output_path}')
