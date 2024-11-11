# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Free typing mode**
  - With the Text tool, you can now click anywhere on the canvas and start typing without dragging to create a textbox. This gives a much more useful workflow for ASCII art and ANSI art, as you can make tiny edits all over the canvas without having to create a new textbox each time.
  - You can also press <kbd>Insert</kbd> or arrow keys to make a cursor appear to start editing, and it will switch to the Text tool if needed.
- Focus is reset when pressing <kbd>Esc</kbd>. This is important to avoid getting stuck with the character input field focused, in order to use free typing mode, or move the selection with the arrow keys, or copy the selection with <kbd>Ctrl+C</kbd>. (The character input field is where it shows the currently selected colors.)
- Text cursor now blinks.

### Changed

- Plain text files (`.txt`) are now saved with CRLF line endings on Windows.
- When closing dialogs, the character input no longer becomes focused.

### Fixed

- Fixed errors when interacting with the command palette (opened by clicking the paint icon in the top left).
- Fixed double-acting arrow keys. Before it was moving between buttons of a dialog while also moving the selection on the canvas.
- Fixed image files opening as blank white. This bug was introduced in in Textual Paint v0.4.0.
- Fixed menu scrolling down when clicking a menu item when the screen was smaller than the menu. In some cases this lead to clicking the wrong menu item, such as Save instead of Open, which is a destructive action.
- The "File" menu button no longer receives focus when the app is opened.
- View Bitmap mode:
  - Fixed exiting View Bitmap mode with Escape key.
  - Prevented widgets keeping focus when entering View Bitmap mode.
  - May have fixed double-acting key presses when toggling View Bitmap mode in some cases.
  - Menus are now closed when entering View Bitmap mode.

## [0.4.0] - 2024-01-11

### Changed

- Updated Textual from 0.27.0 to 0.38.1
- Error details now use Textual's `Collapsible` widget (introduced in 0.37), simplifying the code, and giving it a distinct look, whereas before it looked just like the other buttons in the dialog, but on a separate row.
- The document model now uses `Style` objects instead of foreground and background color strings as separate 2D lists. This opens the door to supporting text attributes (bold, italic, and underline) in the future.
- I tried to improve the performance of canvas rendering, with the document model change and other optimizations. It's still slow when zoomed in, but it may be a bit better.
- The Fill With Color tool now compares colors numerically, instead of as strings, and has a slight tolerance when comparing colors.

### Broken

- Image files open as blank white. Also, when saving files, the canvas becomes blank white (to reflect how the app will read the file if re-opened), although the file is saved correctly. This regression was discovered after the release, and is fixed in the next release.

## [0.3.0] - 2023-09-16

### Removed

- `--recode-samples` option is removed, now covered by the `pytest` test suite.

### Changed

- Made radio buttons rounder in `--ascii-only` mode, using parentheses instead of square brackets.
- Improved the appearance of the warning icon and question icon in `--ascii-only` mode with the dark theme, and made it update when toggling dark mode with <kbd>Ctrl+D</kbd>. (The question icon is used only when pasting content larger than the canvas.)
- Split up code files (especially the huge `paint.py`) into lots of smaller modules, and refactored a bunch of things.

### Added

- Replaced a complex shell one-liner on the readme with a new ANSI art gallery app. You can run it from the repo root, with: `python -m src.textual_paint.gallery`
- Textual Paint now uses `pytest-textual-snapshot` and has tests covering most of the UI surface. This will allow me to update dependencies and do major restructuring of the code with confidence.
- I created a test recorder, which can generate test code by recording interactions with a running app. This is great for testing interactions with the canvas.
- Added docstrings to most of the code, where it was missing.

### Fixed

- Fixed behavior of Free-Form Select tool when melding with the canvas, when the selection was off-screen to the left or top (i.e. with negative coordinates).
- Fixed some false positives in the Polygon tool's double click detection. Before, it would close the polygon prematurely if you clicked quickly, even if you moved the mouse a significant distance between clicks.
- In-progress curves/polygons are now re-colored immediately when a color is selected. Before, it would only update if you moved the mouse over the canvas.
- Fixed "Show Details" button label not changing to "Hide Details" when clicked, in error message dialogs.

## [0.2.0] - 2023-09-05

I am now recommending to install using `pipx` instead of `pip`.
To switch to `pipx`, run `pip uninstall textual-paint && pipx install textual-paint`.

### Changed

- `--ascii-only-icons` now uses color, and has been otherwise tweaked to make tools easier to distinguish.
- The useless circle icon in the top left of the screen is now a cute ASCII art Paint icon. If you click to expand the header, you can see the full thing, but by default just the colorful brushes are visible.

### Added

- Added `--ascii-only` option which affects the whole UI, not just tool icons as with `--ascii-only-icons`. This makes Textual Paint more usable in older terminals like Windows Console Host (`conhost.exe`), or XTerm.
  - I created ASCII art versions of all the dialog icons, and tweaked everything that normally uses Unicode characters, including built-in Textual widgets, like the radio buttons and scrollbars.
- Right click can now be used as an alternative to Ctrl+click to pick a foreground color from the palette. In XTerm, Ctrl opens a context menu, so this is the only way in XTerm. It's also more convenient.
  - Note: Left click in MS Paint selects the foreground (primary) color, whereas in Textual Paint it selects the background color, which is, strangely, essentially the primary color, since you draw with a space character by default. It may be worth changing the default character to a full block character (█), and swapping these mouse button mappings, to bring it in line with MS Paint. This would also allow drawing "pixels" and saving as a plain text file without it all becoming blank when color information is discarded.
  - Side note: I was previously saving right click for a possible future UI where the foreground and background selections both have a foreground, background, and glyph, with the three components being analogous to a single color in MS Paint. I haven't explored that idea yet. It's likely too complicated conceptually, but it would allow more granular color replacement with the Color Eraser tool (if that's even desirable), and quicker access to two different glyphs.
- Right click or Ctrl+click on the current colors area to swap the foreground and background colors. This is a great convenience, especially when using the Color Eraser tool, or when using custom colors that may be similar to each other.
  - Side note: The only reason I didn't add this until now is because I didn't consider right click! (Unlike in JS Paint, where I've had this feature for a long time, left click is used to focus the character input field, which is also the current colors area.)

### Fixed

- The Stretch/Skew dialog's icons were missing from the package, and didn't show up in the dialog in the release build.
- Fixed misaligned rows of text in Kitty terminal due to Pencil and Brush tool emojis by swapping them out with alternatives, as with several other terminals. I also swapped out the Text and Curve tool icons for ones that look better in Kitty — on my computer, at least.

## [0.1.0] - 2023-07-24

First release!

### Added

- Open and save images
  - Drag and drop files to open
  - Warnings when overwriting an existing file, or closing with unsaved changes
  - Auto-saves a temporary `.ans~` backup file alongside the file you're editing, for crash recovery
  - Edits ANSI art, raster images, and SVG, and saves HTML
- All tools from MS Paint are implemented: Free-Form Select, Select, Eraser/Color Eraser, Fill With Color, Pick Color, Magnifier, Pencil, Brush, Airbrush, Text, Line, Curve, Rectangle, Polygon, Ellipse, and Rounded Rectangle
- Color palette
- Efficient screen updates and undo/redo history, by tracking regions affected by each action
- Brush previews
- Status bar
- Menu bar
- Keyboard shortcuts
- Nearly every command from MS Paint is supported, including fun ones like:
  - Flip/Rotate
  - Stretch/Skew
  - Edit Colors
  - Set As Wallpaper (Tiled/Centered)
- Localization into 26 languages: Arabic, Czech, Danish, German, Greek, English, Spanish, Finnish, French, Hebrew, Hungarian, Italian, Japanese, Korean, Dutch, Norwegian, Polish, Portuguese, Brazilian Portuguese, Russian, Slovak, Slovenian, Swedish, Turkish, Chinese, Simplified Chinese
- Dark mode
- Magnification using FIGlet font files as well as procedural meta-glyphs, with an optional grid

[unreleased]: https://github.com/1j01/textual-paint/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/1j01/textual-paint/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/1j01/textual-paint/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/1j01/textual-paint/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/1j01/textual-paint/releases/tag/v0.1.0
