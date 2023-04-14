
textual-paint
=============

What if MS Paint isn't retro enough?
You need Paint in your terminal.

This is a TUI (Text User Interface) image editor, inspired by MS Paint, and built with [Textual](https://textual.textualize.io/).

## Features

- Open and save images
	- [ ] PNG (.png)
	- [ ] Bitmap (.bmp)
	- [x] ANSI (.ans)
		- only supports loading files saved by this program; ANSI files can vary a lot and even encode animations
	- no save dialog yet, you can only save a file opened via the command line
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

The first thing I did in this project was to collect possible characters to represent all the tool icons in MS Paint, to test feasibility.
In other words, I wanted to gauge how good of a recreation it would be possible to achieve, starting from looks.
Unfortunately, I haven't run into any significant roadblocks, so I'm apparently recreating MS Paint. [Again.](https://jspaint.app)

These are the symbols I've found so far:

- Free-Form Select:  ✂️📐🆓🕸✨⚝🫥🇫/🇸◌
- Rectangular Select: ⬚▧🔲
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
