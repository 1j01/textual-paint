# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `--ascii-only-icons` now uses color, and has been otherwise tweaked to make tools easier to distinguish.
- `--ascii-only-icons` now affects the icons in the Stretch/Skew dialog, and the Help window icon, not just tool icons.
- It is now recommended to install using `pipx` instead of `pip`; to switch to `pipx`, run `pip uninstall textual-paint && pipx install textual-paint`.

### Added

- Added `--ascii-only` option which affects the whole UI, not just tool icons as with `--ascii-only-icons`; this makes Textual Paint more usable in older terminals like Windows Console Host (`conhost.exe`), or XTerm.

### Fixed

- Stretch/Skew dialog's icons were missing from the package, and didn't show up in the dialog, in the release build.
- Fixed misaligned rows of text in Kitty terminal due to Pencil and Brush tool emojis. The Text and Curve tool icons are also swapped out for options that look better in Kitty.

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
