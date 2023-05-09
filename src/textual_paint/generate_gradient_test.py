#!/usr/bin/env python3

import os

# ANSI escape codes for truecolor
CSI = '\u001b['
RESET = CSI + '0m'

# Glyphs ordered by visual weight
GLYPHS = [' ', '.', ':', '!', '*', 'x', '%', '#']

def generate_ansi_art(width, height, file):
    for y in range(height):
        for x in range(width):
            # Calculate the color based on position
            r = int((x / width) * 255)
            g = int(((width - x) / width) * 255)
            b = int((y / height) * 255)

            # Generate the truecolor escape code
            # background:
            color = CSI + f'48;2;{r};{g};{b}m'
            # and foreground:
            color += CSI + f'38;2;{r/10};{g/10};{b/10}m'

            # Calculate the index of the glyph based on visual weight
            glyph_index = int(((width - x) + y) / (width + height) * (len(GLYPHS) - 1))

            # Write the colored glyph to the file
            file.write(color + GLYPHS[glyph_index])
        
        # Reset the color at the end of each row and add a newline character
        file.write(RESET + '\n')

# Set the size of the ANSI art
width = 80
height = 24

# Generate and write the ANSI art to a file
file_path = os.path.join(os.path.dirname(__file__), '../../samples/gradient_test.ans')
file_path = os.path.abspath(file_path)
with open(file_path, 'w') as file:
    generate_ansi_art(width, height, file)

# Print the art to the terminal
with open(file_path, 'r') as file:
    print(file.read())

# Print the path to the file, and resulting file size
print(f'Wrote ANSI art to {file_path} ({os.path.getsize(file_path)} bytes)')
