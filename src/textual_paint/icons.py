"""Icons for message boxes, as `Static` widget factories.

Reusing widget instances doesn't work, for obvious reasons in the case of multiple dialogs open at once,
and reasons mysterious to me in the case of closing and re-opening a single dialog.

Some of these icons are designed inside Textual Paint itself,
and saved as `*._rich_console_markup` as a way to export the markup for embedding in the source code.
The warning icon I did by hand in markup.

Some icons used elsewhere in the application are loaded from .ans files.
Two nice things about embedding it are:
1. there's no possibility of file system errors, and
2. it's easier to dynamically modify them to remove the background color.

TODO: dynamic dark mode (I already have alternate versions of some icons)
"""

from textual.widgets import Static

from textual_paint.args import args
from textual_paint.localization.i18n import get as _

# ASCII line art version:
# get_warning_icon = lambda: Static("""[#ffff00]
#     _
#    / \\
#   / | \\
#  /  .  \\
# /_______\\
# [/]""", classes="warning_icon message_box_icon")
# Unicode solid version 1:
# get_warning_icon = lambda: Static("""[#ffff00 on #000000]
#     _
#    ◢█◣
#   ◢[#000000 on #ffff00] ▼ [/]◣
#  ◢[#000000 on #ffff00]  ●  [/]◣
# ◢███████◣
# [/]""", classes="warning_icon message_box_icon")
# Unicode line art version (' might be a better than ╰/╯):
# get_warning_icon = lambda: Static("""[#ffff00]
#     _
#    ╱ ╲
#   ╱ │ ╲
#  ╱  .  ╲
# ╰───────╯
# """, classes="warning_icon message_box_icon")
# Unicode solid version 2:
# get_warning_icon = lambda: Static("""[#ffff00 on #000000]
#      🭯
#     🭅[#000000 on #ffff00]🭯[/]🭐
#    🭅[#000000 on #ffff00] ▼ [/]🭐
#   🭅[#000000 on #ffff00]  ●  [/]🭐
#  🭅███████🭐
# [/]""", classes="warning_icon message_box_icon")
# Unicode solid version 3, now with a border:
# VS Code's terminal seems unsure of the width of these characters (like it's rendering 2 wide but advancing by 1), and has gaps/seams.
# Ubuntu's terminal looks better, and the graphics have less gaps, but the overall shape is worse.
# I guess a lot of this comes down to the font as well.
# get_warning_icon = lambda: Static("""
#     [#000000]🭋[#ffff00 on #000000]🭯[/]🭀[/]
#    [#000000]🭋[#ffff00 on #000000]🭅█🭐[/]🭀[/]
#   [#000000]🭋[#ffff00 on #000000]🭅[#000000 on #ffff00] ▼ [/]🭐[/]🭀[/]
#  [#000000]🭋[#ffff00 on #000000]🭅[#000000 on #ffff00]  ●  [/]🭐[/]🭀[/]
# [#000000]🭋[#ffff00 on #000000]🭅███████🭐[/]🭀[/]
# [#000000]🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃[/]
# """, classes="warning_icon message_box_icon")
# Unicode solid version 4:
# This now looks great in Ubuntu's terminal.
# In VS Code's terminal, all the gaps make it look like it's under frosted glass,
# but it's acceptable. Alternatively, you may see it as looking "spiky",
# which is sensible for a warning icon, if not particularly attractive.
# get_warning_icon = lambda: Static("""
#     [#000000]◢[#ffff00 on #000000]🭯[/]◣[/]
#    [#000000]◢[#ffff00 on #000000]◢█◣[/]◣[/]
#   [#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00] ▼ [/]◣[/]◣[/]
#  [#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00]  ●  [/]◣[/]◣[/]
# [#000000]◢[#ffff00 on #000000]◢███████◣[/]◣[/]
# [#000000]🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃[/]
# """, classes="warning_icon message_box_icon")
# Unicode solid version 5, rounder exclamation mark:
# get_warning_icon = lambda: Static("""
#     [#000000]◢[#ffff00 on #000000]🭯[/]◣[/]
#    [#000000]◢[#ffff00 on #000000]◢█◣[/]◣[/]
#   [#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00] ⬮ [/]◣[/]◣[/]
#  [#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00]  •  [/]◣[/]◣[/]
# [#000000]◢[#ffff00 on #000000]◢███████◣[/]◣[/]
# [#000000]🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃🮃[/]
# """, classes="warning_icon message_box_icon")
# Unicode solid version 6, smaller overall:
warning_icon_markup_unicode = """
   [#000000]◢[#ffff00 on #000000]🭯[/]◣[/]
  [#000000]◢[#ffff00 on #000000]◢█◣[/]◣[/]
 [#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00] ⬮ [/]◣[/]◣[/]
[#000000]◢[#ffff00 on #000000]◢[#000000 on #ffff00]  •  [/]◣[/]◣[/]
[#000000]🮃🮃🮃🮃🮃🮃🮃🮃🮃[/]
"""
# ASCII line art version 2a, with BG color:
# warning_icon_markup_ascii = """
#     [#000000]_[/]
#    [#000000 on #ffff00]/ \\\\[/]
#   [#000000 on #ffff00]/ | \\\\[/]
#  [#000000 on #ffff00]/  .  \\\\[/]
# [#000000 on #ffff00](_______)[/]
# """
# # ASCII line art version 2b, only FG color:
# warning_icon_markup_ascii_dark_mode = """[#ffff00]
#     _
#    / \\
#   / | \\
#  /  .  \\
# (_______)
# [/]"""
# ASCII line art version 3a, with BG color:
warning_icon_markup_ascii = """
    [#000000]_[/]
   [#000000 on #ffff00]/ \\\\[/]
  [#000000 on #ffff00]/   \\\\[/]
 [#000000 on #ffff00]/  [b]![/b]  \\\\[/]
[#000000 on #ffff00](_______)[/]
"""
# ASCII line art version 3b, only FG color:
warning_icon_markup_ascii_dark_mode = """[#ffff00]
    _
   / \\
  /   \\
 /  [b]![/b]  \\
(_______)
[/]"""

def get_warning_icon() -> Static:
    markup = warning_icon_markup_ascii if args.ascii_only else warning_icon_markup_unicode
    # TODO: Use warning_icon_markup_ascii_dark_mode for a less blocky looking outline in dark mode.
    return Static(markup, classes="warning_icon message_box_icon")


# question_icon_ansi = ""
# def get_question_icon() -> Static:
#     global question_icon_ansi
#     if not question_icon_ansi:
#         with open("question_icon.ans", "r", encoding="utf-8") as f:
#             question_icon_ansi = f.read()
#     return Static(question_icon_ansi, classes="question_icon message_box_icon")

# I added a little stopgap to save as Rich console markup by using file extension "._RICH_CONSOLE_MARKUP".
# It's very messy markup because it's generated from the ANSI art.
question_icon_console_markup = """
[rgb(255,255,255) on rgb(128,128,128)]▂[rgb(255,255,255) on rgb(128,128,128)][/rgb(255,255,255) on rgb(128,128,128)]▆[rgb(0,0,0) on rgb(255,255,255)][/rgb(255,255,255) on rgb(128,128,128)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(255,255,255) on rgb(128,128,128)][/rgb(0,0,0) on rgb(255,255,255)]▆[rgb(255,255,255) on rgb(128,128,128)][/rgb(255,255,255) on rgb(128,128,128)]▂[rgb(0,0,0) on rgb(128,128,128)][/rgb(255,255,255) on rgb(128,128,128)] [/rgb(0,0,0) on rgb(128,128,128)]
[rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,255) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]𝟔[rgb(0,0,255) on rgb(255,255,255)][/rgb(0,0,255) on rgb(255,255,255)]❩[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,255) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(255,255,255)]▌[/rgb(0,0,0) on rgb(128,128,128)]
[rgb(255,255,255) on rgb(128,128,128)]🮂[rgb(0,0,0) on rgb(255,255,255)][/rgb(255,255,255) on rgb(128,128,128)]▂[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,255) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]•[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,255) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]▁[rgb(255,255,255) on rgb(0,0,0)][/rgb(0,0,0) on rgb(255,255,255)]🮂[rgb(0,0,0) on rgb(128,128,128)][/rgb(255,255,255) on rgb(0,0,0)]▘[/rgb(0,0,0) on rgb(128,128,128)]
[rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]🮂[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]🮂[rgb(255,255,255) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]◥[rgb(0,0,0) on rgb(128,128,128)][/rgb(255,255,255) on rgb(128,128,128)]▛[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]🮂[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [/rgb(0,0,0) on rgb(128,128,128)]
"""
# make background transparent
question_icon_console_markup = question_icon_console_markup.replace(" on rgb(128,128,128)", "")
# class QuestionIcon(Static):
#     """A question mark icon."""
#
#     def __init__(self) -> None:
#         """Initialize the icon."""
#         super().__init__("", classes="question_icon message_box_icon")
#         # This assertion fails.
#         # > type(self.app)
#         # <class '<run_path>.PaintApp'>
#         # > type(PaintApp())
#         # <class 'paint.PaintApp'>
#         # from paint import PaintApp
#         # assert isinstance(self.app, PaintApp), "QuestionIcon should be used in PaintApp, but got: " + repr(self.app)
#         self.watch(self.app, "dark", self._on_dark_changed, init=False)
#         self._on_dark_changed(False, self.app.dark)
#
#     def _on_dark_changed(self, old_value: bool, dark: bool) -> None:
#         # tweak colors according to the theme
#         if dark:
#             # Never happens?
#             self.update(question_icon_console_markup.replace("rgb(0,0,0)", "rgb(255,0,255)"))
#         else:
#             self.update(question_icon_console_markup.replace("rgb(0,0,0)", "rgb(128,128,128)"))
#
# def get_question_icon() -> QuestionIcon:
#     return QuestionIcon()


# also the shadow is normally gray, I just drew it black because I was using gray as the background
question_icon_console_markup = question_icon_console_markup.replace("rgb(0,0,0)", "rgb(128,128,128)")
# I tried underlining "❩" to make it look like the question mark has a serif, but it looks bad because it's a wide character.
# question_icon_console_markup = question_icon_console_markup.replace("❩", "[u]❩[/u]")

question_icon_console_markup_ascii = """
[rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]_[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]_[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]_[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]_[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)]_[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [/rgb(0,0,0) on rgb(128,128,128)]
[rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(128,128,128)]/[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]\\\\[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(255,255,255)] [/rgb(0,0,0) on rgb(128,128,128)]
[rgb(0,0,0) on rgb(255,255,255)]|[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,255) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]?[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,255) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]|[/rgb(0,0,0) on rgb(255,255,255)]
[rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(128,128,128)]\\\\[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]_[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]_[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]_[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]_[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]/[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(255,255,255)] [/rgb(0,0,0) on rgb(128,128,128)]
[rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(128,128,128)]\\\\[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]|[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on rgb(128,128,128)] [/rgb(0,0,0) on rgb(128,128,128)]
"""
# make background transparent
question_icon_console_markup_ascii = question_icon_console_markup_ascii.replace(" on rgb(128,128,128)", "")
# bold question mark
question_icon_console_markup_ascii = question_icon_console_markup_ascii.replace("?", "[b]?[/b]")

def get_question_icon() -> Static:
    markup = question_icon_console_markup_ascii if args.ascii_only else question_icon_console_markup
    return Static(markup, classes="question_icon message_box_icon")


paint_icon_console_markup = """
[rgb(0,0,0) on rgb(255,0,255)]⡀[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,0,255)].[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)],[rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(192,192,192) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]🮈[rgb(255,255,255) on rgb(255,0,255)][/rgb(192,192,192) on rgb(255,255,255)]◣[/rgb(255,255,255) on rgb(255,0,255)]
[rgb(0,0,255) on rgb(255,0,255)]🙽[rgb(255,0,0) on rgb(255,255,255)][/rgb(0,0,255) on rgb(255,0,255)]┃[rgb(255,255,0) on rgb(255,255,255)][/rgb(255,0,0) on rgb(255,255,255)]🙼[rgb(0,0,0) on rgb(255,255,255)][/rgb(255,255,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(192,192,192) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]░[/rgb(192,192,192) on rgb(255,255,255)]
[rgb(255,255,255) on rgb(255,0,255)]🮉[rgb(128,128,128) on #e3e3e3][/rgb(255,255,255) on rgb(255,0,255)]_[rgb(128,128,128) on #e3e3e3][/rgb(128,128,128) on #e3e3e3]_[#c6c6c6 on rgb(128,128,128)][/rgb(128,128,128) on #e3e3e3]▋[rgb(255,255,255) on #e3e3e3][/#c6c6c6 on rgb(128,128,128)]🮉[rgb(0,0,0) on rgb(255,255,255)][/rgb(255,255,255) on #e3e3e3] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [/rgb(0,0,0) on rgb(255,255,255)]
[rgb(192,192,192) on rgb(255,0,255)]🮈[rgb(128,128,128) on #e3e3e3][/rgb(192,192,192) on rgb(255,0,255)]_[rgb(128,128,128) on #e3e3e3][/rgb(128,128,128) on #e3e3e3]_[rgb(128,128,128) on #e3e3e3][/rgb(128,128,128) on #e3e3e3]▍[rgb(0,0,0) on rgb(255,255,255)][/rgb(128,128,128) on #e3e3e3] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [/rgb(0,0,0) on rgb(255,255,255)]
"""
# make fuchsia transparent
paint_icon_console_markup = paint_icon_console_markup.replace(" on rgb(255,0,255)", "")

# NOTE: I had to manually replace "\" with "\\\\" in the markup below.
# One level of escaping because this is a string literal, and another level because
# Text.markup fails to escape backslashes:
# https://github.com/Textualize/rich/issues/2993
paint_icon_console_markup_ascii = """
[rgb(0,0,0) on rgb(255,0,255)].[#000000 on #ffffff][/rgb(0,0,0) on rgb(255,0,255)] [rgb(0,0,0) on rgb(255,255,255)][/#000000 on #ffffff].[#000000 on #ffffff][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/#000000 on #ffffff] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)],[rgb(255,255,255) on rgb(255,0,255)][/rgb(0,0,0) on rgb(255,255,255)]\\\\[/rgb(255,255,255) on rgb(255,0,255)]
[rgb(0,0,255) on rgb(255,0,255)]\\\\[#000000 on #ffffff][/rgb(0,0,255) on rgb(255,0,255)] [rgb(255,0,0) on rgb(255,255,255)][/#000000 on #ffffff]|[#000000 on #ffffff][/rgb(255,0,0) on rgb(255,255,255)] [rgb(255,255,0) on rgb(255,255,255)][/#000000 on #ffffff]/[rgb(0,0,0) on rgb(255,255,255)][/rgb(255,255,0) on rgb(255,255,255)] [rgb(192,192,192) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)]~[/rgb(192,192,192) on rgb(255,255,255)]
[rgb(0,0,0) on #e6e6e6][[rgb(0,0,0) on rgb(220,220,220)][/rgb(0,0,0) on #e6e6e6]_[rgb(0,0,0) on rgb(220,220,220)][/rgb(0,0,0) on rgb(220,220,220)]_[rgb(0,0,0) on #aaaaaa][/rgb(0,0,0) on rgb(220,220,220)]_[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on #aaaaaa]][rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [/rgb(0,0,0) on rgb(255,255,255)]
[rgb(192,192,192) on rgb(255,0,255)] [rgb(0,0,0) on #e6e6e6][/rgb(192,192,192) on rgb(255,0,255)][[rgb(0,0,0) on #aaaaaa][/rgb(0,0,0) on #e6e6e6]_[rgb(0,0,0) on rgb(128,128,128)][/rgb(0,0,0) on #aaaaaa]][rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(128,128,128)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [rgb(0,0,0) on rgb(255,255,255)][/rgb(0,0,0) on rgb(255,255,255)] [/rgb(0,0,0) on rgb(255,255,255)]
"""
# make fuchsia transparent
paint_icon_console_markup_ascii = paint_icon_console_markup_ascii.replace(" on rgb(255,0,255)", "")

def get_paint_icon() -> Static:
    markup = paint_icon_console_markup_ascii if args.ascii_only else paint_icon_console_markup
    return Static(markup, classes="paint_icon message_box_icon")

__all__ = [
    "get_warning_icon",
    "get_question_icon",
    "get_paint_icon",
]
