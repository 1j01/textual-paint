# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

I am now recommending to install using `pipx` instead of `pip`.
To switch to `pipx`, run `pip uninstall textual-paint && pipx install textual-paint`.

### Changed

- `--ascii-only-icons` now uses color, and has been otherwise tweaked to make tools easier to distinguish.
- The useless circle icon in the top left of the screen is now a cute ASCII art Paint icon. If you click to expand the header, you can see the full thing, but by default just the colorful brushes are visible.

### Added

- Added `--ascii-only` option which affects the whole UI, not just tool icons as with `--ascii-only-icons`. This makes Textual Paint more usable in older terminals like Windows Console Host (`conhost.exe`), or XTerm.
- Right click can now be used as an alternative to Ctrl+click to pick a foreground color from the palette. In XTerm, Ctrl opens a context menu, so this is the only way in XTerm. It's also more convenient.
  - Note: Left click in MS Paint selects the foreground (primary) color, whereas in Textual Paint it selects the background color, which is, strangely, essentially the primary color, since you draw with a space character by default. It may be worth changing the default character to a full block character (█), and swapping these mouse button mappings, to bring it in line with MS Paint. This would also allow drawing "pixels" and saving as a plain text file without it all becoming blank when color information is discarded.
  - Side note: I was previously saving right click for a possible future UI where the foreground and background selections both have a foreground, background, and glyph, with the three components being analogous to a single color in MS Paint. I haven't explored that idea yet. It's likely too complicated conceptually, but it would allow more granular color replacement with the Color Eraser tool (if that's even desirable), and quicker access to two different glyphs.
- Right click or Ctrl+click on the current colors area to swap the foreground and background colors. This is a great convenience, especially when using the Color Eraser tool, or when using custom colors that may be similar to each other.
  - Side note: The only reason I didn't add this until now is because I didn't consider right click! (Unlike in JS Paint, where I've had this feature for a long time, left click is used to focus the character input field, which is also the current colors area.)

### Fixed

- Stretch/Skew dialog's icons were missing from the package, and didn't show up in the dialog, in the release build.
- Fixed misaligned rows of text in Kitty terminal due to Pencil and Brush tool emojis (now swapped with alternatives, as with several other terminals). The Text and Curve tool icons are also swapped out for options that look better in Kitty (on my computer, at least).

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

[unreleased]: https://github.com/1j01/textual-paint/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/1j01/textual-paint/releases/tag/v0.1.0
