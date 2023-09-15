"""Enumeration of the tools available in the Paint app."""

import os
from enum import Enum

from textual_paint.__init__ import PYTEST
from textual_paint.args import args
from textual_paint.localization.i18n import get as _


class Tool(Enum):
    """The tools available in the Paint app."""
    free_form_select = 1
    select = 2
    eraser = 3
    fill = 4
    pick_color = 5
    magnifier = 6
    pencil = 7
    brush = 8
    airbrush = 9
    text = 10
    line = 11
    curve = 12
    rectangle = 13
    polygon = 14
    ellipse = 15
    rounded_rectangle = 16

    def get_icon(self) -> str:
        """Get the icon for this tool."""
        # Alternatives collected:
        # - Free-Form Select: ✂️📐🆓🕸✨☆⚝⛤⛥⛦⛧⚛🫥🇫/🇸◌⁛⁘ ⢼⠮ 📿➰➿𓍼യ🪢𓍯 𔗫 𓍲 𓍱 ౿ Ꮼ Ꮘ
        # - Select: ✂️⬚▧🔲 ⣏⣹ ⛶
        # - Eraser/Color Eraser: 🧼🧽🧹🚫👋🗑️▰▱
        # - Fill With Color: 🌊💦💧🩸🌈🎉🎊🪣🫗🚰⛽🍯 ꗃ﹆ ⬙﹅ 🪣﹅
        # - Pick Color: 🎨🌈💉💅💧🩸🎈📌📍🪛🪠🥍🩼🌡💄🎯𖡡⤤𝀃🝯⊸⚲𓋼🗡𓍊🍶🧪🍼🌂👁️‍🗨️🧿🍷⤵❣⚗ ⤆Ϸ ⟽þ ⇐ c⟾ /̥͚̥̥͚͚̊̊
        # - Magnifier: 🔍🔎👀🔬🔭🧐🕵️‍♂️🕵️‍♀️
        # - Pencil: ✏️✎✍️🖎🖊️🖋️✒️🖆📝🖍️🪶🪈🥖🥕▪
        # - Brush: 🖌👨‍🎨🧑‍🎨💅🧹🪮🪥🪒🪠ⵄ⑃ሐ⋔⋲ ▭⋹ 𝈸⋹ ⊏⋹ ⸦⋹ ⊂⋹ ▬▤
        # - Airbrush: ⛫💨дᖜ💨╔💨🧴🥤🧃🧯🧨🍾🥫💈🫠🌬️🗯☄💭༄༺☁️🌪️🌫🌀🚿 ⪧𖤘 ᗒᗣ дᖜᗕ
        # - Text: 📝📄📃📜AＡ🅰️🆎🔤🔠𝐴
        # - Line: 📏📉📈＼⟍𝈏╲⧹\⧵∖
        # - Curve: ↪️🪝🌙〰️◡◠~∼≈∽∿〜〰﹋﹏≈≋～⁓
        # - Rectangle: ▭▬▮▯➖🟥🟧🟨🟩🟦🟪🟫⬛⬜🔲🔳⏹️◼️◻️◾◽▪️▫️
        # - Polygon: ▙𝗟𝙇﹄』𓊋⬣⬟🔶🔷🔸🔹🔺🔻△▲☖⛉♦️🛑📐🪁✴️
        # - Ellipse: ⬭⭕🔴🟠🟡🟢🔵🟣🟤⚫⚪🔘🫧🕳️🥚💫💊🛞
        # - Rounded Rectangle: ▢⬜⬛𓋰⌨️⏺️💳📺🧫

        if args.ascii_only or args.ascii_only_icons:
            enum_to_icon = {
                Tool.free_form_select: "'::.",  # "*" "<^>" "<[u]^[/]7" "'::." ".::." "<%>"
                Tool.select: "::",  # "#" "::" ":_:" ":[u]:[/]:" ":[u]'[/]:"
                Tool.eraser: "[rgb(255,0,255)][u]/[/]7[/]",  # "47" "27" "/_/" "[u]/[/]7" "<%>"
                Tool.fill: "[u i]H[/][blue][b]?[/][/]",  # "#?" "H?" "[u i]F[/]?"
                Tool.pick_color: "[u i red] P[/]",  # "[u].[/]" "[u i]\\P[/]"
                Tool.magnifier: ",[rgb(0,128,255)]O[/]",  # ",O" "o-" "O-" "o=" "O=" "Q"
                Tool.pencil: "[rgb(255,0,255)]c[/][rgb(128,128,64)]==[/]-",  # "c==>" "==-" "-=="
                Tool.brush: "E[rgb(128,128,64)])=[/]",  # "[u],h.[/u]" "[u],|.[/u]" "[u]h[/u]"
                Tool.airbrush: "[u i]H[/][rgb(0,128,255)]<)[/]",  # "H`" "H`<" "[u i]H[/]`<" "[u i]6[/]<"
                Tool.text: "A",  # "Abc"
                Tool.line: "\\",
                Tool.curve: "S",  # "~" "S" "s"
                Tool.rectangle: "[_]",  # "[]" "[_]" ("[\x1B[53m_\x1B[55m]" doesn't work right, is there no overline tag?)
                Tool.polygon: "[b]L[/b]",  # "L"
                Tool.ellipse: "O",  # "()"
                Tool.rounded_rectangle: "{_}", # "(_)" "{_}" ("(\x1B[53m_\x1B[55m)" doesn't work right, is there no overline tag?)
            }
            return enum_to_icon[self]
        if not PYTEST:
            # Some glyphs cause misalignment of everything to the right of them, including the canvas,
            # so alternative characters need to be chosen carefully for each platform.
            # "🫗" causes jutting out in Ubuntu terminal, "🪣" causes the opposite in VS Code terminal
            # VS Code sets TERM_PROGRAM to "vscode", so we can use that to detect it
            # Don't swap out tool button icons when running in pytest, to avoid snapshot differences across platforms.
            TERM_PROGRAM = os.environ.get("TERM_PROGRAM")
            if TERM_PROGRAM == "vscode":
                if self == Tool.fill:
                    # return "🫗" # is also hard to see in the light theme
                    return "🌊" # is a safe alternative
                    # return "[on black]🫗 [/]" # no way to make this not look like a selection highlight
                if self == Tool.pencil:
                    # "✏️" doesn't display in color in VS Code
                    return "🖍️" # or "🖊️", "🖋️"
            elif TERM_PROGRAM == "iTerm.app":
                # 🪣 (Fill With Color) and ⚝ (Free-Form Select) defaults are missing in iTerm2 on macOS 10.14 (Mojave)
                # They show as a question mark in a box, and cause the rest of the row to be misaligned.
                if self == Tool.fill:
                    return "🌊"
                if self == Tool.free_form_select:
                    return "⢼⠮"
            elif os.environ.get("WT_SESSION"):
                # The new Windows Terminal app sets WT_SESSION to a GUID.
                # Caveats:
                # - If you run `cmd` inside WT, this env var will be inherited.
                # - If you run a GUI program that launches another terminal emulator, this env var will be inherited.
                # - If you run via ssh, using Microsoft's official openssh server, WT_SESSION will not be set.
                # - If you hold alt and right click in Windows Explorer, and say Open Powershell Here, WT_SESSION will not be set,
                #   because powershell.exe is launched outside of the Terminal app, then later attached to it.
                # Source: https://github.com/microsoft/terminal/issues/11057

                # Windows Terminal has alignment problems with the default Pencil symbol "✏️"
                # as well as alternatives "🖍️", "🖊️", "🖋️", "✍️", "✒️"
                # "🖎" and "🖆" don't cause alignment issues, but don't show in color and are illegibly small.
                if self == Tool.pencil:
                    # This looks more like it would represent the Text tool than the Pencil,
                    # so it's far from ideal, especially when there IS an actual pencil emoji...
                    return "📝"
                # "🖌️" is causes misalignment (and is hard to distinguish from "✏️" at a glance)
                # "🪮" shows as tofu
                if self == Tool.brush:
                    return "🧹"
                # "🪣" shows as tofu
                if self == Tool.fill:
                    return "🌊"
            elif os.environ.get("KITTY_WINDOW_ID"):
                # Kitty terminal has alignment problems with the default Pencil symbol "✏️"
                # as well as alternatives "🖍️", "🖊️", "🖋️", "✍️", "✒️", "🪈"
                # and Brush symbol "🖌️" and alternatives "🧹", "🪮"
                # "🖎", "🖆", and "✎" don't cause alignment issues, but don't show in color and are illegibly small.
                if self == Tool.pencil:
                    # Working for me: "🪶", "🥖", "🥕", "▪", and "📝", the last one looking more like a Text tool than a Pencil tool,
                    # but at least has a pencil...
                    return "📝"
                if self == Tool.brush:
                    # Working for me: "👨‍🎨", "💅", "🪥", "🪒", "🪠", "▭⋹" (basically any of the lame options)
                    # return "[tan]▬[/][#5c2121]⋹[/]"
                    return "[tan]▬[/]▤"
                if self == Tool.text:
                    # The wide character "Ａ" isn't centered-looking? And is faint/small...
                    return "𝐴" # not centered, but closer to MS Paint's icon, with serifs
                if self == Tool.curve:
                    # "～" appears tiny!
                    # "〜" looks good; should I use that for other platforms too?
                    # (It's funny, they look identical in my IDE (VS Code))
                    return "〜"
        return {
            Tool.free_form_select: "⚝",
            Tool.select: "⬚",
            Tool.eraser: "🧼",
            Tool.fill: "🪣",
            Tool.pick_color: "💉",
            Tool.magnifier: "🔍",
            Tool.pencil: "✏️",
            Tool.brush: "🖌️",
            Tool.airbrush: "💨",
            Tool.text: "Ａ",
            Tool.line: "⟍",
            Tool.curve: "～",
            Tool.rectangle: "▭",
            Tool.polygon: "𝙇",
            Tool.ellipse: "⬭",
            Tool.rounded_rectangle: "▢",
        }[self]

    def get_name(self) -> str:
        """Get the localized name for this tool.

        Not to be confused with tool.name, which is an identifier.
        """
        return {
            Tool.free_form_select: _("Free-Form Select"),
            Tool.select: _("Select"),
            Tool.eraser: _("Eraser/Color Eraser"),
            Tool.fill: _("Fill With Color"),
            Tool.pick_color: _("Pick Color"),
            Tool.magnifier: _("Magnifier"),
            Tool.pencil: _("Pencil"),
            Tool.brush: _("Brush"),
            Tool.airbrush: _("Airbrush"),
            Tool.text: _("Text"),
            Tool.line: _("Line"),
            Tool.curve: _("Curve"),
            Tool.rectangle: _("Rectangle"),
            Tool.polygon: _("Polygon"),
            Tool.ellipse: _("Ellipse"),
            Tool.rounded_rectangle: _("Rounded Rectangle"),
        }[self]
