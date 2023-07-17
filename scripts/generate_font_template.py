#!/usr/bin/env python3

import os
from typing import TextIO

# Character set
# NUL at the beginning (0), SP in the middle (32), and NBSP at the end (255)
# are all treated as space when selected. Null can cause the screen to malfunction
# if it's inserted into the document.
# spell-checker: disable
code_page_437 = " ☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼ !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~⌂ÇüéâäàåçêëèïîìÄÅÉæÆôöòûùÿÖÜ¢£¥₧ƒáíóúñÑªº¿⌐¬½¼¡«»░▒▓│┤╡╢╖╕╣║╗╝╜╛┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀αßΓπΣσµτΦΘΩδ∞φε∩≡±≥≤⌠⌡÷≈°∙·√ⁿ²■ "
# spell-checker: enable

# ANSI escape codes for box drawing characters
BOX_UPPER_LEFT = '\u250C'
BOX_UPPER_RIGHT = '\u2510'
BOX_LOWER_LEFT = '\u2514'
BOX_LOWER_RIGHT = '\u2518'
BOX_HORIZONTAL = '\u2500'
BOX_VERTICAL = '\u2502'

# Box dimensions
box_inner_width = 4
box_inner_height = 4
box_outer_width = box_inner_width + 2
box_outer_height = box_inner_height + 2

# Color commands
CSI = '\u001b['
RESET = CSI + '0m'
# gray on dark gray
border_color = CSI + '37;100m'
# white on black
character_color = CSI + '37;40m'


def format_border_title(character: str) -> str:
    # return f'▏{character}▕'
    # return f'[{character_color}{character}{border_color}]'
    # return f'{BOX_HORIZONTAL}{character_color}{character}{border_color}{BOX_HORIZONTAL}'
    return f'╴{character_color}{character}{border_color}╶'

title_width = 3 # not using len(title) because it contains ANSI escape codes

def write_ansi_file(file: TextIO) -> None:
    write = file.write

    # Write the ANSI escape code to clear the screen and set the cursor position
    write('\u001b[2J')
    write('\u001b[H')

    # Loop through each character
    rows = 16
    cols = 16
    for i in range(rows):
        for j in range(cols):
            character = code_page_437[i * cols + j]

            # Calculate the starting position of the box
            start_x = j * box_outer_width + 1
            start_y = i * box_outer_height + 1

            # Set color for border, light gray on black
            write(border_color)

            # Write the box's top border with the character in the center
            write(f'\u001b[{start_y};{start_x}H')  # Set cursor position

            # Write the top border line, including the border title
            title = format_border_title(character)
            padding_left = (box_inner_width - title_width) // 2
            padding_right = box_inner_width - title_width - padding_left
            write(BOX_UPPER_LEFT)
            write(BOX_HORIZONTAL * padding_left + title + BOX_HORIZONTAL * padding_right)
            write(BOX_UPPER_RIGHT)

            # Write the box's bottom border
            write(f'\u001b[{start_y + box_outer_height - 1};{start_x}H')  # Set cursor position
            write(BOX_LOWER_LEFT)
            write(BOX_HORIZONTAL * box_inner_width)
            write(BOX_LOWER_RIGHT)

            # Write the box's left and right borders
            for k in range(box_inner_height):
                write(f'\u001b[{start_y + k + 1};{start_x}H')
                write(BOX_VERTICAL)
                write(f'\u001b[{start_y + k + 1};{start_x + box_outer_width - 1}H')
                write(BOX_VERTICAL)
            
            # Write the character in the center of the box
            # write(f'\u001b[{start_y + box_inner_height // 2 + 1};{start_x + box_inner_width // 2 - 1}H')
            # write(character)

            # Write the ANSI escape code to reset the colors
            write('\u001b[0m')

# Generate and write to a file
file_path = os.path.join(os.path.dirname(__file__), f'../samples/{box_inner_width}x{box_inner_height}_font_template.ans')
file_path = os.path.abspath(file_path)
with open(file_path, 'w', encoding='utf-8') as file:
    write_ansi_file(file)

# Print the art to the terminal
with open(file_path, 'r', encoding='utf-8') as file:
    print(file.read())

# Print the path to the file, and resulting file size
print(f'Wrote font template to {file_path} ({os.path.getsize(file_path)} bytes)')
