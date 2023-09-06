"""Templates for exporting to SVG and HTML."""

# This SVG template is based on the template in rich/_export_format.py
# It removes the simulated window frame, and crops the SVG to just the terminal content.
# It also adds a placeholder for ANSI data to be stored in the SVG,
# in order to support opening the file after saving it, in a perfectly lossless way.
# (I have also implemented a more general SVG loading mechanism, but it's now a fallback.)
# It was very nice during development to automate saving a file as SVG:
# textual run --dev "src.textual_paint.paint --restart-on-changes samples/ship.ans" --press ctrl+shift+s,.,s,v,g,enter
# (The Ctrl+Shift+S shortcut doesn't work when actually trying it as a user, but it works to simulate it.)
CUSTOM_CONSOLE_SVG_FORMAT = """\
<svg
    class="rich-terminal"
    viewBox="0 0 {terminal_width} {terminal_height}"
    xmlns="http://www.w3.org/2000/svg"
    xmlns:txtpnt="http://github.com/1j01/textual-paint"
>
    <!-- Generated with Rich https://www.textualize.io and Textual Paint https://github.com/1j01/textual-paint -->
    <style>

    @font-face {{
        font-family: "Fira Code";
        src: local("FiraCode-Regular"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff2/FiraCode-Regular.woff2") format("woff2"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff/FiraCode-Regular.woff") format("woff");
        font-style: normal;
        font-weight: 400;
    }}
    @font-face {{
        font-family: "Fira Code";
        src: local("FiraCode-Bold"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff2/FiraCode-Bold.woff2") format("woff2"),
                url("https://cdnjs.cloudflare.com/ajax/libs/firacode/6.2.0/woff/FiraCode-Bold.woff") format("woff");
        font-style: bold;
        font-weight: 700;
    }}

    .{unique_id}-matrix {{
        font-family: Fira Code, monospace;
        font-size: {char_height}px;
        line-height: {line_height}px;
        font-variant-east-asian: full-width;
    }}

    {styles}
    </style>

    <defs>
    <clipPath id="{unique_id}-clip-terminal">
      <rect x="0" y="0" width="{terminal_width}" height="{terminal_height}" />
    </clipPath>
    {lines}
    <txtpnt:ansi>%ANSI_GOES_HERE%</txtpnt:ansi>
    </defs>

    <g clip-path="url(#{unique_id}-clip-terminal)">
    {backgrounds}
    <g class="{unique_id}-matrix">
    {matrix}
    </g>
    </g>
</svg>
"""

CUSTOM_CONSOLE_HTML_FORMAT = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
{stylesheet}
body {{
    color: {foreground};
    background-color: {background};
}}
</style>
</head>
<body>
    <pre style="font-family:monospace;line-height:1"><code>{code}</code></pre>
</body>
</html>
"""
