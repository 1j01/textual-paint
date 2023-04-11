
textual-paint
=============

What if MS Paint isn't retro enough?
You need Paint in your terminal.

This is a TUI (Text User Interface) image editor, inspired by MS Paint, and built with [Textual](https://textual.textualize.io/).


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

- Free-Form Select:  ✂️📐🆓🕸✨⚝🫥🇫/🇸◌
- Rectangular Select: ⬚▧🔲
- Eraser: 🧼🧽🧹🚫👋🗑️
- Fill Bucket (Flood Fill): 🌊💦💧🌈🎉🎊🪣🫗
- Pick Color: 🎨💉
- Magnifier: 🔍🔎👀🔬🔭🧐🕵️‍♂️🕵️‍♀️
- Pencil: ✏️✍️🖎🖊️🖋️✒️🖆📝🖍️
- Brush: 🖌️🖌👨‍🎨🧑‍🎨💅
- Airbrush: 💨ᖜ╔🧴🥤🫠
- Text: 🆎📝📄📃🔤📜A
- Line: 📏📉📈⟍𝈏⧹
- Curve: ↪️🪝🌙〰️◡◠~∼≈∽∿〜〰﹋﹏≈≋～
- Rectangle: ▭▬▮▯◼️◻️⬜⬛🟧🟩
- Polygon: ▙𝗟𝙇⬣⬟△▲🔺🔻🔷🔶
- Ellipse: ⬭🔴🔵🔶🔷🔸🔹🟠🟡🟢🟣🫧
- Rounded Rectangle: ▢⬜⬛


## See Also

- [JavE](http://jave.de/), an advanced Java-based ASCII art editor
- [Playscii](http://vectorpoem.com/playscii/), a beautiful ASCII/ANSI art editor
- [cmdpxl](https://github.com/knosmos/cmdpxl), a pixel art editor for the terminal using the keyboard
- [pypixelart](https://github.com/douglascdev/pypixelart), a pixel art editor using vim-like keybindings, inspired by cmdpxl but not terminal-based
