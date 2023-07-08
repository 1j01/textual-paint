
Textual Paint
=============

MS Paint in your terminal.

This is a TUI (Text User Interface) image editor, inspired by MS Paint, built with [Textual](https://textual.textualize.io/).

<img src="screenshot.svg" alt="MS Paint like interface" />

## Features

- [x] Open and save images
  - [x] Fancy file dialogs
  - [x] Drag and drop files to open
  - [x] Warnings when overwriting an existing file, or closing with unsaved changes
  - [x] Automatically saves a temporary `.ans~` backup file alongside the file you're editing, for recovery in case of a crash
  - File formats, chosen by typing a file extension in the Save As dialog:
    - [x] ANSI (.ans) — Note that while it handles many more ANSI control codes when loading than those that it uses to save files, you may have limited success loading other ANSI files that you find on the web, or create with other tools. ANSI files can vary a lot and even encode animations!
    - [x] Plain Text (.txt)
    - [x] SVG (.svg) — can open SVGs saved by Textual Paint, which embed ANSI data; can also open some other SVGs that consist of a grid of rectangles and text elements. For fun, as a challenge, I made it quite flexible; it can handle uneven grids of unsorted rectangles. But that's only used as a fallback, because it's not perfect.
    - [x] HTML (.htm, html) — write-only (opening not supported)
    - [x] PNG (.png) — opens first frame of an APNG file
    - [x] Bitmap (.bmp)
    - [x] GIF (.gif) — opens first frame
    - [x] TIFF (.tiff) — opens first frame
    - [x] WebP (.webp) — opens first frame
    - [x] JPEG (.jpg, .jpeg) — saving disabled because it's lossy (it would destroy your pixel art)
    - [x] Windows Icon (.ico) — opens largest size in the file
    - [x] Mac OS Icon (.icns) — opens largest size in the file; saving disabled because it requires specific sizes
    - [x] Windows Cursor (.cur) — opens largest size in the file; saving not supported by Pillow (and it would need a defined hot spot)
    - See [Pillow's documentation](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html) for more supported formats.
    - Note that metadata is not preserved when opening and saving image files. (This is however common for many image editors.)
- Tools
    - [x] Free-Form Select
    - [x] Select
    - [x] Eraser/Color Eraser
    - [x] Fill With Color
    - [x] Pick Color
    - [x] Magnifier
    - [x] Pencil
    - [x] Brush
    - [x] Airbrush
    - [x] Text
    - [x] Line
    - [x] Curve
    - [x] Rectangle
    - [x] Polygon
    - [x] Ellipse
    - [x] Rounded Rectangle
- [x] Color palette
- [x] Undo/Redo
- [x] Efficient screen updates and undo/redo history, by tracking regions affected by each action
	- You could totally use this program over SSH! Haha, this "what if" project could actually be useful. Of course, it should be mentioned that you can also run graphical programs over SSH, but this might be more responsive, or just fit your vibe better.
- [x] Brush previews
- [x] Menu bar
- [x] Status bar
- [x] Keyboard shortcuts
- [x] Localization into 26 languages: Arabic, Czech, Danish, German, Greek, English, Spanish, Finnish, French, Hebrew, Hungarian, Italian, Japanese, Korean, Dutch, Norwegian, Polish, Portuguese, Brazilian Portuguese, Russian, Slovak, Slovenian, Swedish, Turkish, Chinese, Simplified Chinese

## Usage

<!-- ### Installation

```bash
pip install textual-paint
```

### Running

```bash
textual-paint
``` -->

### Command Line Options

```
$ python3 paint.py --help
usage: textual-paint [options] [filename]

Paint in the terminal.

positional arguments:
  filename              Path to a file to open. File will be created if it
                        doesn't exist.

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --theme {light,dark}  Theme to use, either "light" or "dark"
  --language {ar,cs,da,de,el,en,es,fi,fr,he,hu,it,ja,ko,nl,no,pl,pt,pt-br,ru,sk,sl,sv,tr,zh,zh-simplified}
                        Language to use
  --ascii-only-icons    Use only ASCII characters for tool icons
  --backup-folder FOLDER
                        Folder to save backups to. By default a backup is saved
                        alongside the edited file.
  --inspect-layout      Inspect the layout with middle click, for development
  --clear-screen        Clear the screen before starting; useful for
                        development, to avoid seeing fixed errors
  --restart-on-changes  Restart the app when the source code is changed, for
                        development
  --recode-samples      Open and save each file in samples/, for testing
```

### Keyboard Shortcuts

- <kbd>Ctrl</kbd>+<kbd>D</kbd>: Toggle Dark Mode
- <kbd>Ctrl</kbd>+<kbd>Q</kbd>: Quit
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>S</kbd>: Save As **IF SHIFT IS DETECTED** — ⚠️ it might trigger Save instead, and overwrite the open file!
- <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd>: Redo **IF SHIFT IS DETECTED** — ⚠️ it might trigger Undo instead.

The rest match MS Paint's keyboard shortcuts:

- <kbd>Ctrl</kbd>+<kbd>S</kbd>: Save
- <kbd>Ctrl</kbd>+<kbd>O</kbd>: Open
- <kbd>Ctrl</kbd>+<kbd>N</kbd>: New
- <kbd>Ctrl</kbd>+<kbd>T</kbd>: Toggle Tools Box
- <kbd>Ctrl</kbd>+<kbd>W</kbd>: Toggle Colors Box
- <kbd>Ctrl</kbd>+<kbd>Z</kbd>: Undo
- <kbd>Ctrl</kbd>+<kbd>Y</kbd>: Redo
- <kbd>F4</kbd>: Redo
- <kbd>Ctrl</kbd>+<kbd>A</kbd>: Select All
- <kbd>Delete</kbd>: Clear Selection
- <kbd>Ctrl</kbd>+<kbd>C</kbd>: Copy
- <kbd>Ctrl</kbd>+<kbd>V</kbd>: Paste
- <kbd>Ctrl</kbd>+<kbd>X</kbd>: Cut
- <kbd>Ctrl</kbd>+<kbd>E</kbd>: Image Attributes
- <kbd>Ctrl</kbd>+<kbd>PageUp</kbd>: Large Size
- <kbd>Ctrl</kbd>+<kbd>PageDown</kbd>: Normal Size

### Tips

You can draw with a character by clicking the selected color display area in the palette and then typing the character,
or by double clicking the same area to pick a character from a list.

You can set the text color by holding Ctrl while clicking a color in the palette, or while double clicking a color to open the Edit Colors dialog.

You can display a saved ANSI file in the terminal with `cat`:

```bash
cat samples/ship.ans
```

To view all the sample files, run:

```bash
find samples -type f -exec file --mime-type {} \; | grep -v -e "image/png" -e "image/svg" | cut -d: -f1 | sort | xargs -I{} sh -c 'echo "File: {}"; cat "{}"; echo "\n-----------------------\n"'
```
<details>
<summary>Command Explanation</summary>
Let's break down the command:

1. `find samples -type f -exec file --mime-type {} \;`: This part uses the `find` command to locate all files (`-type f`) within the "samples" folder and its subdirectories. For each file, it executes the `file --mime-type` command to determine the file's MIME type. This outputs a line like "samples/ship.ans: text/plain".

2. `grep -v -e "image/png" -e "image/svg"`: This filters out any lines containing the MIME types "image/png" or "image/svg", effectively excluding PNG and SVG files. `-v` means "invert the match", so it will only output lines that don't match the given patterns.

3. `cut -d: -f1`: This extracts only the file paths from the output of the `file` command, removing the MIME type information.

4. `sort`: This sorts the file paths alphabetically.

5. `xargs -I{} sh -c 'echo "File: {}"; cat "{}"; echo "\n-----------------------\n"'`: Finally, this executes the `sh -c` command for each file, echoing the filename, catting its content, and adding a separator line.

This command will sort and display the content of all non-PNG files within the "samples" folder and its subdirectories. Remember to run this command in the directory where the "samples" folder is located.
</details>

To preview ANSI art files in file managers like Nautilus, Thunar, Nemo, or Caja, you can install the [ansi-art-thumbnailer](https://github.com/1j01/ansi-art-thumbnailer) program I made to go along with this project.


## Known Issues

- Undo/Redo doesn't work inside the Text tool's textbox. Ctrl+Z will delete the textbox. (Also note that the Text tool works differently from MS Paint; it will overwrite characters and the cursor can move freely, which makes it better for ASCII art, but worse for prose.)
- The selection box border appears inside instead of outside (and lacks dashes). For the text box, I hid the border because it was too visually confusing, but it should also have an outer border.
- Pick Color can't be cancelled (with Esc or by pressing both mouse buttons), since it samples the color continuously.
- Pressing both mouse buttons stops the current tool, but doesn't undo the current action.
- Due to limitations of the terminal, shortcuts using Shift or Alt might not work.
- Menus are not keyboard navigable.
- The Zoom submenu flickers as it opens, and may not always open in the right place.
- The canvas flickers when zooming in with the Magnifier tool.
- Some languages don't display correctly.
- Large files can make the program very slow, as can magnifying the canvas. There is a 500 KB limit when opening files to prevent it from freezing.
- Free-Form Select stamping/finalizing is incorrect when the selection is off-screen to the left or top.
- Status bar description can be left blank when selecting a menu item <!--I'm guessing Leave can come after close-->
- Menu items like Copy/Cut/Paste are not grayed out when inapplicable. Only unimplemented items are grayed out.
- Set As Wallpaper may not work on your system. For me, on Ubuntu, the wallpaper setting is updated but the picture is not, unless I manually pick it. There is however untested support for many platforms, and you may have better luck than me.
- If you paste and then stamp the selection with Ctrl+Click, the stamp(s) can't be undone. An undo state is only created when finalizing the selection, for pasted selections.
- ANSI files (.ans) are treated as UTF-8 when saving and loading, rather than CP437 or Windows-1252 or any other encodings. Unicode is nice and modern terminals support it, but it's not the standard for ANSI files. There isn't really a standard for ANSI files.
- ANSI files are loaded with a white background. This may make sense as a default for text files, but ANSI files either draw a background or assume a black background, being designed for terminals.
- Can click Cancel button of Edit Colors dialog while opening it, if the mouse lines up with it.

The program has only been tested on Linux. Issues on other platforms are as-yet _unknown_ :)

## Development

Recommended: first, create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

Install Textual and other dependencies:
```bash
pip install -r requirements.txt
```

Run the app via Textual's CLI for live-reloading CSS support, and enable other development features:
```bash
textual run --dev "src.textual_paint.paint --clear-screen --inspect-layout --restart-on-changes"
```

Or run more basically:
```bash
python -m src.textual_paint.paint
```

Or install the CLI globally\*:
```bash
pip install --editable .
```

Then run:
```bash
textual-paint
```

\*If you use a virtual environment, it will only install within that environment.

`--clear-screen` is useful for development, because it's sometimes jarring or perplexing to see error messages that have actually been fixed, when exiting the program.

`--inspect-layout` enables a DOM inspector accessible with F12, which I built. It also lets you apply a rainbow highlight and labels to all ancestors under the mouse with middle click, but this is mostly obsolete/redundant with the DOM inspector now. The labels affect the layout, so you can also hold Ctrl to only colorize, and you can remember how the colors correspond to the labels, to build a mental model of the layout.

`--restart-on-changes` automatically restarts the program when any Python files change. This works by the program restarting itself directly. (Programs like `modd` or `nodemon` that run your program in a subprocess don't work well with Textual's escape sequences.)

There are also launch tasks configured for VS Code, so you can run the program from the Run and Debug panel.
Note that it runs slower in VS Code's debugger.

To see logs, run [`textual console`](https://textual.textualize.io/guide/devtools/#console) and then run the program via `textual run --dev`.
This also makes it run slower.

Often it's useful to exclude events with `textual console -x EVENT`.

To test file encoding, run `textual run --dev "src.textual_paint.paint --recode-samples"`.

If there are differences in the ANSI files, you can set up a special diff like this:
```bash
git config --local "diff.cat-show-all.textconv" "cat --show-all"
```
but you should check that `cat --show-all samples/2x2.ans` works on your system first.
Also, note that it might not work with your Git GUI of choice; you may need to use the command line.

### Troubleshooting

> `Unable to import 'app' from module 'src.textual_paint.paint'`

- Make sure to activate the virtual environment, if you're using one.
- Make sure to run the program from the root directory of the repository.

> `ModuleNotFoundError: No module named 'src'`

- Make sure to run the program from the root directory of the repository.

> `ImportError: attempted relative import with no known parent package`

- `paint.py` can only be run as a module, not as a script. I just... I haven't had the heart to remove the shebang line.

### Linting
  
```bash
pyright  # type checking
cspell-cli lint .  # spell checking
```

### Update Dependencies

```bash
python -m pipreqs.pipreqs --ignore .history --force
```


## License

[MIT](LICENSE.txt)


## Unicode Symbols and Emojis for Paint Tools

The first thing I did in this project was to collect possible characters to represent all the tool icons in MS Paint, to gauge how good of a recreation it would be possible to achieve, starting from looks.
As it turns out, I didn't run into any significant roadblocks, so I ended up recreating MS Paint. [Again.](https://jspaint.app)

These are the symbols I've found so far:

- Free-Form Select:  ✂️📐🆓🕸✨⚝⛤⛥⛦⛧🫥🇫/🇸◌⁛⁘ ⢼⠮
- Select: ⬚▧🔲 ⣏⣹ ⛶
- Eraser/Color Eraser: 🧼🧽🧹🚫👋🗑️▰▱
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
- Polygon: ▙𝗟𝙇﹄』𓊋⬣⬟🔶🔷🔸🔹🔺🔻△▲
- Ellipse: ⬭⭕🔴🟠🟡🟢🔵🟣🟤⚫⚪🫧
- Rounded Rectangle: ▢⬜⬛

The default symbols used may not be the best on your particular system, so I may add some kind of configuration for this in the future.

### Cursor

A crosshair cursor could use one of `+✜✛⊹✚╋╬⁘⁛⌖⯐`, but whilst that imitates the look, it might be better to show the pixel under the cursor, i.e. character cell, surrounded by dashes, like this:

```
 ╻
╺█╸
 ╹
```

## See Also

- [JavE](http://jave.de/), an advanced Java-based ASCII art editor
- [Playscii](http://vectorpoem.com/playscii/), a beautiful ASCII/ANSI art editor. This is also written in Python and MIT licensed, so I might take some code from it, for converting images to ANSI, for example. Who knows, maybe I could even try to support its file format.
- [cmdpxl](https://github.com/knosmos/cmdpxl), a pixel art editor for the terminal using the keyboard
- [pypixelart](https://github.com/douglascdev/pypixelart), a pixel art editor using vim-like keybindings, inspired by cmdpxl but not terminal-based
