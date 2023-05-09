#!/usr/bin/env python3

import os
import math

# ANSI escape codes for truecolor
CSI = '\u001b['
RESET = CSI + '0m'

# Glyphs to use for the gradient
GLYPHS = ['🌸', '🌷', '🌹', '🌺', '🌻', '🌼']

def spiral(m):
    r = math.sqrt(m[0]**2 + m[1]**2) * .05
    a = math.atan2(m[1], m[0])
    v = math.sin(100. * (math.sqrt(r) - 0.02 * a))
    return max(0., min(1., v))

def generate_ansi_art(width, height, file):
    # Calculate the center coordinates of the image
    center_x = width // 2
    center_y = height // 2

    for y in range(height):
        for x in range(width):
            # Calculate the coordinates relative to the center
            rel_x = x - center_x
            rel_y = y - center_y

            # Evaluate the spiral function
            scale = 0.1
            v = spiral((rel_x * scale, rel_y * scale))

            # Calculate the color based on the spiral value
            r = int(v * 255)
            g = int(((1 - v) * 255)*0.8)
            b = int(v * 255)

            # Generate the truecolor escape code
            # background:
            color = CSI + f'48;2;{r};{g};{b}m'
            # and foreground:
            color += CSI + f'38;2;{r//10};{g//10};{b//10}m'

            # Calculate the index of the glyph based on visual weight
            glyph_index = int(v * (len(GLYPHS) - 1))

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
