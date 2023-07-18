
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from textual_paint.paint import AnsiArtDocument

# load font
# font = ImageFont.truetype('fonts/ansi.ttf', size=16, layout_engine=ImageFont.Layout.BASIC)
# font = ImageFont.load_default()
# Pillow actually looks in most of these system font folders by default.
font_dirs = [
    # Windows
    R"C:\Windows\Fonts",
    R"C:\WINNT\Fonts",
    R"%LocalAppData%\Microsoft\Windows\Fonts", # (fonts installed only for the current user)
    # macOS
    "/Library/Fonts",
    "/System/Library/Fonts",
    "~/Library/Fonts", # (fonts installed only for the current user)
    # Linux:
    # "/usr/share/fonts", # handled more generally below:
    *[data_dir + "/fonts" for data_dir in os.environ.get("XDG_DATA_DIRS", "/usr/share").split(":")],
    "/usr/local/share/fonts",
    "~/.fonts", # (fonts installed only for the current user)
    # Android:
    "/system/fonts",
    "/data/fonts",
]
font_names = [
    "NotoSansMono",
    "DejaVuSansMono",
    "LiberationMono",
    "UbuntuMono",
    "Hack",
    "FiraMono",
    "Inconsolata",
    "SourceCodePro",
    "DroidSansMono",
    "Consolas",
    "CourierNew",
    "LucidaConsole",
    "Monaco",
    "Menlo",
    "Andale Mono",
    "Courier New",
]
font = None
for font_dir in font_dirs:
    path = Path(os.path.expandvars(os.path.expanduser(font_dir)))
    files = path.glob("**/*.ttf")
    # files = list(files) # printing consumes the generator without this!
    # print("path", path, "files", "\n".join(map(str, files)))
    for file in files:
        # print(f"stem {file.stem!r}", file.stem in font_names)
        if file.stem in font_names:
            font = ImageFont.truetype(str(file), size=16, layout_engine=ImageFont.LAYOUT_BASIC)
            break
    if font:
        break
if not font:
    print("Font not found, falling back to built-in font for rasterization.")
    font = ImageFont.load_default()

ch_width: int
ch_height: int
ch_width, ch_height = font.getsize('A')  # type: ignore
assert isinstance(ch_width, int), "ch_width is not an int, but a " + str(type(ch_width))  # type: ignore
assert isinstance(ch_height, int), "ch_height is not an int, but a " + str(type(ch_height))  # type: ignore

def rasterize(doc: 'AnsiArtDocument') -> Image.Image:
    # make PIL image
    img = Image.new('RGB', (doc.width * ch_width, doc.height * ch_height), color='black')
    draw = ImageDraw.Draw(img)

    # draw cell backgrounds
    for y in range(doc.height):
        for x in range(doc.width):
            bg_color = doc.bg[y][x]
            draw.rectangle((x * ch_width, y * ch_height, (x + 1) * ch_width, (y + 1) * ch_height), fill=bg_color)

    # draw text
    for y in range(doc.height):
        for x in range(doc.width):
            char = doc.ch[y][x]
            bg_color = doc.bg[y][x]
            fg_color = doc.fg[y][x]
            try:
                draw.text((x * ch_width, y * ch_height), char, font=font, fill=fg_color)
            except UnicodeEncodeError:
                pass

    return img
