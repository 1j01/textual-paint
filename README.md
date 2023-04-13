
Textual Paint
=============

MS Paint in your terminal.

This is a TUI (Text User Interface) image editor, inspired by MS Paint, built with [Textual](https://textual.textualize.io/).

No [Paint](https://jspaint.app), no gain, that's what I always say!

<!-- GitHub doesn't support line-height style in markdown, so I can't use inline HTML for the screenshot without seams between rows of text. But I can include the HTML inside <foreignObject> in an SVG file and include that as an <img> element. -->
<!-- GitHub doesn't support figure/figcaption in markdown, so I have to use a table. -->
<table>
<tr><td align="center">
<img src="screenshot.svg" alt="MS Paint like interface" />
</td></tr>
<tr><td align="center">This screenshot of Textual Paint is the terminal's screen buffer copied as HTML, wrapped in SVG, placed in HTML inside Markdown.<br>This might not render correctly in your browser.</tr></td>
</table>

## Features

- Open and save images
	- [ ] PNG (.png)
	- [ ] Bitmap (.bmp)
	- [x] ANSI (.ans)
		- only supports loading files saved by this program; ANSI files can vary a lot and even encode animations
- Tools
    - [ ] Free-Form Select
    - [ ] Rectangular Select
    - [x] Eraser
        - [ ] Color Eraser
    - [x] Fill With Color
    - [x] Pick Color
    - [ ] Magnifier
    - [x] Pencil
    - [x] Brush
    - [x] Airbrush
    - [ ] Text
    - [x] Line
    - [ ] Curve
    - [x] Rectangle
    - [ ] Polygon
    - [x] Ellipse
    - [x] Rounded Rectangle
- [x] Color palette
- [x] Undo/Redo
- [x] Efficient screen updates and undo/redo history, by tracking regions affected by each action
	- You could totally use this program over SSH! Haha, this "what if" project could actually be useful. Of course, it should be mentioned that you can also run graphical programs over SSH, but this might be more responsive, or just fit your vibe better.
- [x] Brush previews
- [x] Menu bar

## Development

Install Textual and Stransi:
```bash
pip install "textual[dev]" "stransi"
```

Run supporting live-reloading CSS:
```bash
textual run --dev paint.py
```

Or run normally:
```bash
python paint.py
```


## License

[MIT](LICENSE.txt)


## Unicode Symbols and Emojis for Paint Tools

The first thing I did in this project was to collect possible characters to represent all the tool icons in MS Paint, to gauge how good of a recreation it would be possible to achieve, starting from looks.
Unfortunately, I haven't run into any significant roadblocks, so I'm apparently recreating MS Paint. [Again.](https://jspaint.app)

These are the symbols I've found so far:

- Free-Form Select:  ✂️📐🆓🕸✨⚝🫥🇫/🇸◌⁛⁘ ⢼⠮
- Rectangular Select: ⬚▧🔲 ⣏⣹
- Eraser/Color Eraser: 🧼🧽🧹🚫👋🗑️
- Fill With Color: 🌊💦💧🌈🎉🎊🪣🫗
- Pick Color: 🎨💉💅💧📌📍⤤𝀃🝯🍶
- Magnifier: 🔍🔎👀🔬🔭🧐🕵️‍♂️🕵️‍♀️
- Pencil: ✏️✎✍️🖎🖊️🖋️✒️🖆📝🖍️
- Brush: 🖌️🖌👨‍🎨🧑‍🎨💅
- Airbrush: 💨ᖜ╔🧴🥤🫠
- Text: 🆎📝📄📃🔤📜AＡ
- Line: 📏📉📈⟍𝈏╲⧹\⧵∖
- Curve: ↪️🪝🌙〰️◡◠~∼≈∽∿〜〰﹋﹏≈≋～⁓
- Rectangle: ▭▬▮▯🟥🟧🟨🟩🟦🟪🟫⬛⬜◼️◻️◾◽▪️▫️
- Polygon: ▙𝗟𝙇﹄』⬣⬟🔶🔷🔸🔹🔺🔻△▲
- Ellipse: ⬭⭕🔴🟠🟡🟢🔵🟣🟤⚫⚪🫧
- Rounded Rectangle: ▢⬜⬛

The default symbols used may not be the best on your particular system, so I may add some kind of configuration for this in the future.

### Cursor

A crosshair cursor could use one of `+✜✛✚╋╬`, but whilst that imitates the look, it might be better to show the pixel under the cursor, i.e. character cell, surrounded by dashes, like this:

```
 ╻
╺█╸
 ╹
```

## See Also

- [JavE](http://jave.de/), an advanced Java-based ASCII art editor
- [Playscii](http://vectorpoem.com/playscii/), a beautiful ASCII/ANSI art editor
- [cmdpxl](https://github.com/knosmos/cmdpxl), a pixel art editor for the terminal using the keyboard
- [pypixelart](https://github.com/douglascdev/pypixelart), a pixel art editor using vim-like keybindings, inspired by cmdpxl but not terminal-based

## Notes

save dialog

Action constructor: remove document param, in favor of a update/grab() method

classes = "..." -> add_class()
toolsbox/colorsbox:
	refactor to send message for selected tool
	invalid ids for colors because of #

use Rich API code like
	segments = []
	for x in range(self.image.width):
		bg = self.image.bg[y][x]
		fg = self.image.fg[y][x]
		ch = self.image.ch[y][x]
		segments.append(Segment(ch, Style.parse(fg+" on "+bg)))
	return Strip(segments, self.size.width) 
when saving .ans file

------------------------
Textual

Bugs:
- mouse move event offset in scrolled container
- captured mouse events not listed in `textual console`
- pouring glass unicode emoji width unstable
	- there's a FAQ for this
- Oscillating layout bug, see branch `oscillating-layout-bug`

Docs:
- "Events are reserved for use by Textual" was unclear. later it's clearer that it really means that: "events are simply messages reserved for use by Textual"
- where "markup" is mentioned, link to Rich API. mention that text is parsed as Rich API markup by default in Static
- `"""Called when a button is pressed."""` -> `"""Called when a button widget is pressed."""` or otherwise disambiguate with on_key
	- `"""Called when a button is clicked or activated with the keyboard."""`
- "toggle attribute" (or similar) confusing for dark mode; I don't know how to do that. toggle_class isn't it. action_toggle_dark seems to work though...

Other Feedback:
- layouts are hard to use, auto width doesn't work
