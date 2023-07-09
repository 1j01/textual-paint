"""Horizontal text flipper supporting a wide range of Unicode characters."""

import regex as re
from rich.text import Text

ascii_mirror_characters: dict[str, str] = {
    "[": "]",
    "]": "[",
    "(": ")",
    ")": "(",
    "{": "}",
    "}": "{",
    "<": ">",
    ">": "<",
    "/": "\\",
    "\\": "/",
    "|": "|",
    "`": "'",
    "'": "`",
    "7": "F", # or Y
    "F": "7",
    "p": "q",
    "q": "p",
    "b": "d",
    "d": "b",
    "3": "E",
    "E": "3",
    "S": "2",
    "2": "S",
    "Z": "5",
    "5": "Z",
    "J": "L",
    "L": "J",
    "s": "z",
    "z": "s",
    "K": "4", # or >
    "4": "R", # or \, K, A
    "R": "4",
    "P": "9",
    "9": "P",
    "?": "S", # one-way
    "g": "p", # one-way
    # "S": "?",
    # "@": "6",
    # "a": "6",
    # "6": "a",
    # "9": "e",
    "&": "B", # or b, 8, 3, S
    "B": "&",
    # super-glyphs:
    # "c|": " b",
    # " K": ">|",
}
unicode_mirror_characters: dict[str, str] = {
    "“": "”",
    "”": "“",
    "‘": "’",
    "’": "‘",
    "┌": "┐",
    "┐": "┌",
    "└": "┘",
    "┘": "└",
    "├": "┤",
    "┤": "├",
    "┍": "┑",
    "┑": "┍",
    "┎": "┒",
    "┒": "┎",
    "┏": "┓",
    "┓": "┏",
    "┗": "┛",
    "┛": "┗",
    "┠": "┨",
    "┨": "┠",
    "┕": "┙",
    "┖": "┚",
    "┚": "┖",
    "┙": "┕",
    "┝": "┥",
    "┞": "┦",
    "┡": "┩",
    "┢": "┪",
    "┣": "┫",
    "┥": "┝",
    "┦": "┞",
    "┧": "┟",
    "┟": "┧",
    "┩": "┡",
    "┪": "┢",
    "┫": "┣",
    "┭": "┮",
    "┮": "┭",
    "┱": "┲",
    "┲": "┱",
    "┵": "┶",
    "┶": "┵",
    "┹": "┺",
    "┺": "┹",
    "┽": "┾",
    "┾": "┽",
    "╃": "╄",
    "╄": "╃",
    "╅": "╆",
    "╆": "╅",
    "╊": "╉",
    "╉": "╊",
    "╒": "╕",
    "╓": "╖",
    "╔": "╗",
    "╕": "╒",
    "╖": "╓",
    "╗": "╔",
    "╘": "╛",
    "╙": "╜",
    "╚": "╝",
    "╛": "╘",
    "╜": "╙",
    "╝": "╚",
    "╞": "╡",
    "╠": "╣",
    "╡": "╞",
    "╢": "╟",
    "╟": "╢",
    "╣": "╠",
    "╭": "╮",
    "╮": "╭",
    "╯": "╰",
    "╰": "╯",
    "╱": "╲",
    "╲": "╱",
    "╴": "╶",
    "╶": "╴",
    "╸": "╺",
    "╺": "╸",
    "╼": "╾",
    "╾": "╼",
    "▏": "▕",
    "▘": "▝",
    "▌": "▐",
    "▖": "▗",
    "▝": "▘",
    "▛": "▜",
    "▙": "▟",
    "▗": "▖",
    "▐": "▌",
    "▟": "▙",
    "▜": "▛",
    "▕": "▏",
    "▞": "▚",
    "▚": "▞",
    "🬀": "🬁",
    "🬁": "🬀",
    "🬃": "🬇",
    "🬄": "🬉",
    "🬅": "🬈",
    "🬆": "🬊",
    "🬇": "🬃",
    "🬈": "🬅",
    "🬉": "🬄",
    "🬊": "🬆",
    "🬌": "🬍",
    "🬍": "🬌",
    "🬏": "🬞",
    "🬐": "🬠",
    "🬑": "🬟",
    "🬒": "🬡",
    "🬓": "🬦",
    "🬔": "🬧",
    "🬕": "🬨",
    "🬖": "🬢",
    "🬗": "🬤",
    "🬘": "🬣",
    "🬙": "🬥",
    "🬚": "🬩",
    "🬛": "🬫",
    "🬜": "🬪",
    "🬝": "🬬",
    "🬞": "🬏",
    "🬟": "🬑",
    "🬠": "🬐",
    "🬡": "🬒",
    "🬢": "🬖",
    "🬣": "🬘",
    "🬤": "🬗",
    "🬥": "🬙",
    "🬦": "🬓",
    "🬧": "🬔",
    "🬨": "🬕",
    "🬩": "🬚",
    "🬪": "🬜",
    "🬫": "🬛",
    "🬬": "🬝",
    "🬮": "🬯",
    "🬯": "🬮",
    "🬱": "🬵",
    "🬲": "🬷",
    "🬳": "🬶",
    "🬴": "🬸",
    "🬵": "🬱",
    "🬶": "🬳",
    "🬷": "🬲",
    "🬸": "🬴",
    "🬺": "🬻",
    "🬻": "🬺",
    "🬼": "🭇",
    "🬽": "🭈",
    "🬾": "🭉",
    "🬿": "🭊",
    "🭀": "🭋",
    "🭁": "🭌",
    "🭂": "🭍",
    "🭃": "🭎",
    "🭄": "🭏",
    "🭅": "🭐",
    "🭆": "🭑",
    "🭇": "🬼",
    "🭈": "🬽",
    "🭉": "🬾",
    "🭊": "🬿",
    "🭋": "🭀",
    "🭌": "🭁",
    "🭍": "🭂",
    "🭎": "🭃",
    "🭏": "🭄",
    "🭐": "🭅",
    "🭑": "🭆",
    "🭒": "🭝",
    "🭓": "🭞",
    "🭔": "🭟",
    "🭕": "🭠",
    "🭖": "🭡",
    "🭗": "🭢",
    "🭘": "🭣",
    "🭙": "🭤",
    "🭚": "🭥",
    "🭛": "🭦",
    "🭜": "🭧",
    "🭝": "🭒",
    "🭞": "🭓",
    "🭟": "🭔",
    "🭠": "🭕",
    "🭡": "🭖",
    "🭢": "🭗",
    "🭣": "🭘",
    "🭤": "🭙",
    "🭥": "🭚",
    "🭦": "🭛",
    "🭧": "🭜",
    "🭨": "🭪",
    "🭪": "🭨",
    "🭬": "🭮",
    "🭮": "🭬",
    "🭰": "🭵",
    "🭱": "🭴",
    "🭲": "🭳",
    "🭳": "🭲",
    "🭴": "🭱",
    "🭵": "🭰",
    "🭼": "🭿",
    "🭽": "🭾",
    "🭾": "🭽",
    "🭿": "🭼",
    "🮕": "🮖",
    "🮖": "🮕",
    "🮘": "🮙",
    "🮙": "🮘",
    "🮠": "🮡",
    "🮡": "🮠",
    "🮢": "🮣",
    "🮣": "🮢",
    "🮤": "🮥",
    "🮥": "🮤",
    "🮨": "🮩",
    "🮩": "🮨",
    "🮪": "🮫",
    "🮫": "🮪",
    "🮬": "🮭",
    "🮭": "🮬",
    "🮵": "🮶",
    "🮶": "🮵",
    "🮜": "🮝",
    "🮝": "🮜",
    "🮞": "🮟",
    "🮟": "🮞",
    "🮌": "🮍",
    "🮍": "🮌",
    "▉": "🮋",
    "🮋": "▉",
    "▊": "🮊",
    "🮊": "▊",
    "▋": "🮉",
    "🮉": "▋",
    "▍": "🮈",
    "🮈": "▍",
    "▎": "🮇",
    "🮇": "▎",
    # "🯲": "🯵",
    # "🯵": "🯲",
    # "🯁🯂🯃": "👈 ",
    "👈": "👉",
    "👉": "👈",
    # "🮲🮳": "🏃",
    # "🏃": "🮲🮳",
    "🯇": "🯈",
    "🯈": "🯇",
    "◂": "▸",
    "▸": "◂",
    "◝": "◜",
    "◜": "◝",
    "◞": "◟",
    "◟": "◞",
    "◤": "◥",
    "►": "◄",
    "◃": "▹",
    "▶": "◀",
    "◄": "►",
    "▹": "◃",
    "◥": "◤",
    "◸": "◹",
    "◖": "◗",
    "◣": "◢",
    "◢": "◣",
    "◗": "◖",
    "◀": "▶",
    "▻": "◅",
    "◨": "◧",
    "◺": "◿",
    "◰": "◳",
    "◳": "◰",
    "◿": "◺",
    "◹": "◸",
    "◧": "◨",
    "▧": "▨",
    "▨": "▧",
    "▷": "◁",
    "◁": "▷",
    "◅": "▻",
    "◐": "◑",
    "◑": "◐",
    "◭": "◮",
    "◮": "◭",
    "◱": "◲",
    "◲": "◱",
    "◴": "◷",
    "◵": "◶",
    "◶": "◵",
    "◷": "◴",
    "⏢": "▱", # (dubious) or ▭ (symmetricalize)
    "▱": "⏢", # (dubious) or ▭ (symmetricalize)
    "?": "⸮",
    "⸮": "?",
    "1": "Ɩ",
    "Ɩ": "1",
    "2": "ς",
    "ς": "2",
    "3": "Ɛ",
    "Ɛ": "3",
    "4": "߂", # or ᔨ or բ or ᖨ or ߂ or μ
    "߂": "4",
    "5": "ट",
    "ट": "5",
    "6": "მ",
    "მ": "6",
    "7": "٢", # or Ⲋ or ߖ (RTL)
    "٢": "7",
    "9": "୧",
    "୧": "9",
    "a": "ɒ", # or ઠ or ₆ or 6
    "ɒ": "ɑ", # or a
    "ɑ": "ɒ",
    "c": "ɔ",
    "ɔ": "c",
    "e": "ɘ",
    "ɘ": "e",
    "f": "ʇ",
    "ʇ": "f",
    "g": "ϱ",
    "ϱ": "g",
    "h": "⑁", # or ᖽ or ᖹ or Ꮧ or H
    "⑁": "h",
    "j": "ᒑ", # or į or ᒫ or ⇂ or ᢺ
    "ᒑ": "j",
    "k": "ʞ",
    "ʞ": "k",
    "r": "ɿ",
    "ɿ": "r",
    "s": "ƨ",
    "ƨ": "s",
    "t": "Ɉ",
    "Ɉ": "t",
    "u": "υ",
    "υ": "u",
    "y": "γ",
    "B": "ઘ", # or Ƌ or 8 or 𐌇
    "ઘ": "B",
    "C": "Ɔ",
    "Ɔ": "C",
    "D": "ᗡ", # or Ⴇ
    "ᗡ": "D",
    "E": "Ǝ",
    "Ǝ": "E",
    "F": "ꟻ", # or ߔ or ╕ or ᆿ or 7 or ᒣ
    "ꟻ": "F",
    "G": "Ә",
    "Ә": "G",
    "J": "Ⴑ", # or し
    "Ⴑ": "J",
    "K": "ﻼ",
    "ﻼ": "K",
    "L": "⅃",
    "⅃": "L",
    "N": "И",
    "И": "N",
    "P": "ꟼ", # or Գ
    "ꟼ": "P",
    "Q": "Ϙ",
    # "Ϙ": "Q",
    "R": "Я",
    "Я": "R",
    "S": "Ƨ", # or Ꙅ
    "Ƨ": "S",
    "Z": "\u29f5\u0304\u0332", # or "\u29f5\u0305\u0332" or ⦣̅ or 5 or or \ or ⋝ or Ƹ or ⧖/ⴵ or Σ or ﭶ or ﳎ or צּ or ﮑ/ﻜ or ݎ or ܠ̅ (note: some of those are RTL)
    "\u29f5\u0304\u0332": "Z",
    "z": "⦣̅",
    "⦣̅": "z",
    "⋝": "⋜", # or Z
    "⋜": "⋝",
    "≤": "≥",
    "≥": "≤",
    "&": "კ", # or ₰ or 𐒈 or Ֆ
    "₰": "&",
    "კ": "&",
    "𐒈": "&",
    "Ֆ": "&",
    "ɜ": "ɛ",
    "ɞ": "ʚ",
    # "ɿ": "ɾ",
    "ʢ": "ʡ",
    "ˁ": "ˀ",
    "̔": "̓",
    "ͽ": "ͼ",
    "϶": "ϵ",
    "Ͻ": "Ϲ",
    "Ͽ": "Ͼ",
    "Ԑ": "З",
    "ԑ": "з",
    "ٝ": "ُ",
    "ܧ": "ܦ",
    "ྀ": "ི",
    "ཱྀ": "ཱི",
    "᚜": "᚛",
    "᳤": "᳣",
    "᳦": "᳥",
    "ᴎ": "ɴ",
    "ᴙ": "ʀ",
    "ᴲ": "ᴱ",
    "ᴻ": "ᴺ",
    "ᶔ": "ᶓ",
    "ᶟ": "ᵋ",
    "‵": "′",
    "‶": "″",
    "‷": "‴",
    "⁋": "¶",
    "⁏": ";",
    "Ↄ": "Ⅽ",
    "ↄ": "c",
    "∽": "~",
    "⌐": "¬",
    "☙": "❧",
    "⦣": "∠",
    "⦥": "⦤",
    "⦰": "∅",
    "⧹": "⧸",
    "⫭": "⫬",
    "⯾": "∟",
    "⸑": "⸐",
    "⹁": ",",
    "〝": "〞",
    "Ꙅ": "Ѕ",
    "ꙅ": "ѕ",
    "Ꙕ": "Ю",
    "ꙕ": "ю",
    "Ꙡ": "Ц",
    "ꙡ": "ц",
    "Ɜ": "Ɛ",
    "Ꟶ": "Ⱶ",
    "ꟶ": "ⱶ",
    "＼": "／",
    "𐞎": "ᵉ",
    "𐞴": "𐞳",
    "𑨉": "𑨁",
    "𜽬": "𜽛",
    "𝄃": "𝄂",
    "𝼁": "ɡ",
    "𝼃": "k",
    "𝼇": "ŋ",
    "🖑": "🖐",
    "🖒": "👍", # shows the same direction for me
    "🖓": "👎",
    "🖔": "✌",
    "🙽": "🙼",
    "🙿": "🙾",
    "󠁜": "󠀯",
    "ɛ": "ɜ",
    "ʚ": "ɞ",
    "ʡ": "ʢ",
    "ˀ": "ˁ",
    "̓": "̔",
    "ͼ": "ͽ",
    "ϵ": "϶",
    "Ϲ": "Ͻ",
    "Ͼ": "Ͽ",
    "З": "Ԑ",
    "з": "ԑ",
    "ُ": "ٝ",
    "ܦ": "ܧ",
    "ི": "ྀ",
    "ཱི": "ཱྀ",
    "᚛": "᚜",
    "᳣": "᳤",
    "᳥": "᳦",
    "ɴ": "ᴎ",
    "ʀ": "ᴙ",
    "ᴱ": "ᴲ",
    "ᴺ": "ᴻ",
    "ᶓ": "ᶔ",
    "ᵋ": "ᶟ",
    "′": "‵",
    "″": "‶",
    "‴": "‷",
    "¶": "⁋",
    ";": "⁏",
    "Ⅽ": "Ↄ",
    # "c": "ↄ",
    "~": "∽",
    "¬": "⌐",
    "❧": "☙",
    "∠": "⦣",
    "⦤": "⦥",
    "∅": "⦰",
    "⧸": "⧹",
    "⫬": "⫭",
    "∟": "⯾",
    "⸐": "⸑",
    ",": "⹁",
    "〞": "〝",
    "Ѕ": "Ꙅ",
    "ѕ": "ꙅ",
    "Ю": "Ꙕ",
    "ю": "ꙕ",
    "Ц": "Ꙡ",
    "ц": "ꙡ",
    # "Ɛ": "Ɜ",
    "Ⱶ": "Ꟶ",
    "ⱶ": "ꟶ",
    "／": "＼",
    "ᵉ": "𐞎",
    "𐞳": "𐞴",
    "𑨁": "𑨉",
    "𜽛": "𜽬",
    "𝄂": "𝄃",
    "ɡ": "𝼁",
    # "k": "𝼃",
    "ŋ": "𝼇",
    "🖐": "🖑",
    "👍": "🖒",
    "👎": "🖓",
    "✌": "🖔",
    "🙼": "🙽",
    "🙾": "🙿",
    "󠀯": "󠁜",
    "«": "»",
    "ʿ": "ʾ",
    "˂": "˃",
    "˓": "˒",
    "˱": "˲",
    "̘": "̙",
    "̜": "̹",
    "͑": "͗",
    "͔": "͕",
    "֎": "֍",
    "܆": "܇",
    # "ࡳ": "ࡲ", # can't see these, can't vet them (shows as code points)
    # "ࡸ": "ࡷ",
    # "ࢂ": "ࢁ",
    "ࣷ": "ࣸ",
    "ࣹ": "ࣺ",
    "࿖": "࿕",
    "࿘": "࿗",
    # "᫁": "᫂", # can't see these, can't vet them (shows as code points)
    # "᫃": "᫄",
    "᷷": "᷶",
    "᷸": "͘",
    "᷾": "͐",
    "‹": "›",
    "⁅": "⁆",
    "⁌": "⁍",
    "⁽": "⁾",
    "₍": "₎",
    "⃐": "⃑",
    "⃔": "⃕",
    "⃖": "⃗",
    # "⃚": "⃙", # not quite mirrors
    "⃭": "⃬",
    "⃮": "⃯",
    "←": "→",
    "↚": "↛",
    "↜": "↝",
    "↞": "↠",
    "↢": "↣",
    "↤": "↦",
    "↩": "↪",
    "↫": "↬",
    "↰": "↱",
    "↲": "↳",
    "↶": "↷",
    "↺": "↻",
    "↼": "⇀",
    "↽": "⇁",
    "↿": "↾",
    "⇃": "⇂",
    "⇇": "⇉",
    "⇍": "⇏", # not quite mirrors but ok
    "⇐": "⇒",
    "⇚": "⇛",
    "⇜": "⇝",
    "⇠": "⇢",
    "⇤": "⇥",
    "⇦": "⇨",
    "⇷": "⇸",
    "⇺": "⇻",
    "⇽": "⇾",
    # "∳": "∲", not mirrors
    "⊣": "⊢",
    "⋉": "⋊",
    "⋋": "⋌",
    "⌈": "⌉",
    "⌊": "⌋",
    "⌍": "⌌",
    "⌏": "⌎",
    "⌜": "⌝",
    "⌞": "⌟",
    "〈": "〉",
    "⌫": "⌦",
    "⍅": "⍆",
    "⍇": "⍈",
    "⎛": "⎞",
    "⎜": "⎟",
    "⎝": "⎠",
    "⎡": "⎤",
    "⎢": "⎥",
    "⎣": "⎦",
    "⎧": "⎫",
    "⎨": "⎬",
    "⎩": "⎭",
    "⎸": "⎹",
    "⏋": "⎾",
    "⏌": "⎿",
    "⏪": "⏩",
    "⏮": "⏭",
    "⏴": "⏵",
    "◩": "⬔",
    "☚": "☛",
    "☜": "☞",
    "⚟": "⚞",
    "⛦": "⛥",
    "❨": "❩",
    "❪": "❫",
    "❬": "❭",
    "❮": "❯",
    "❰": "❱",
    "❲": "❳",
    "❴": "❵",
    "➪": "➩",
    "⟅": "⟆",
    "⟕": "⟖",
    "⟞": "⟝",
    "⟢": "⟣",
    "⟤": "⟥",
    "⟦": "⟧",
    "⟨": "⟩",
    "⟪": "⟫",
    "⟬": "⟭",
    "⟮": "⟯",
    "⟲": "⟳",
    "⟵": "⟶",
    "⟸": "⟹",
    "⟻": "⟼",
    "⟽": "⟾",
    "⤂": "⤃",
    "⤆": "⤇",
    "⤌": "⤍",
    "⤎": "⤏",
    "⤙": "⤚",
    "⤛": "⤜",
    "⤝": "⤞",
    "⤟": "⤠",
    "⤶": "⤷",
    "⥀": "⥁",
    "⥆": "⥅",
    # "⥌": "⥏", # nope
    # "⥍": "⥏",
    # "⥑": "⥏",
    "⥒": "⥓",
    "⥖": "⥗",
    "⥘": "⥔",
    "⥙": "⥕",
    "⥚": "⥛",
    "⥞": "⥟",
    "⥠": "⥜",
    "⥡": "⥝",
    "⥢": "⥤",
    "⥪": "⥬",
    "⥫": "⥭",
    "⥳": "⥴",
    "⥼": "⥽",
    "⦃": "⦄",
    "⦅": "⦆",
    "⦇": "⦈",
    "⦉": "⦊",
    "⦋": "⦌",
    "⦍": "⦐",
    "⦏": "⦎",
    "⦑": "⦒",
    "⦗": "⦘",
    "⦩": "⦨",
    "⦫": "⦪",
    "⦭": "⦬",
    "⦯": "⦮",
    "⦴": "⦳",
    "⧑": "⧒",
    "⧔": "⧕",
    "⧘": "⧙",
    "⧚": "⧛",
    "⧨": "⧩",
    "⧼": "⧽",
    "⨭": "⨮",
    "⨴": "⨵",
    "⫍": "⫎",
    "⫥": "⊫",
    "⬅": "⮕",
    "⬐": "⬎",
    "⬑": "⬏",
    "⬕": "◪",
    "⬖": "⬗",
    "⬰": "⇴",
    "⬱": "⇶",
    "⬲": "⟴",
    "⬳": "⟿",
    "⬴": "⤀",
    "⬵": "⤁",
    "⬶": "⤅",
    "⬷": "⤐",
    "⬸": "⤑",
    "⬹": "⤔",
    "⬺": "⤕",
    "⬻": "⤖",
    "⬼": "⤗",
    "⬽": "⤘",
    "⬾": "⥇",
    "⬿": "⤳",
    "⭀": "⥱",
    # "⭁": "⭉", # only tilde is mirrored
    # "⭂": "⭊", # only tilde is mirrored
    "⭅": "⭆",
    # "⭇": "⥲", # only tilde is mirrored
    # "⭈": "⥵", # only tilde is mirrored
    "⭉": "⥲", # tilde isn't mirrored...
    "⭊": "⥵", # tilde isn't mirrored...
    # "⭋": "⥳", # only tilde is mirrored
    # "⭌": "⥴", # only tilde is mirrored
    # TODO: try to match those up better
    "⭠": "⭢",
    "⭪": "⭬",
    "⭯": "⭮",
    "⭰": "⭲",
    "⭺": "⭼",
    "⮄": "⮆",
    "⮈": "⮊",
    "⮎": "⮌",
    "⮐": "⮑",
    "⮒": "⮓",
    "⮘": "⮚",
    "⮜": "⮞",
    "⮠": "⮡",
    "⮢": "⮣",
    "⮤": "⮥",
    "⮦": "⮧",
    "⮨": "⮩",
    "⮪": "⮫",
    "⮬": "⮭",
    "⮮": "⮯",
    "⮰": "⮱",
    "⮲": "⮳",
    "⮴": "⮵",
    "⮶": "⮷",
    "⯇": "⯈",
    "⯨": "⯩",
    "⯪": "⯫",
    "⯬": "⯮",
    "⸂": "⸃",
    "⸄": "⸅",
    "⸉": "⸊",
    "⸌": "⸍",
    "⸜": "⸝",
    "⸠": "⸡",
    "⸢": "⸣",
    "⸤": "⸥",
    "⸦": "⸧",
    "⸨": "⸩",
    "⸶": "⸷",
    "⹑": "⹐",
    # "⹕": "⹖", # can't see these, can't vet 'em (shows as code points)
    # "⹗": "⹘",
    # "⹙": "⹚",
    # "⹛": "⹜",
    "⿸": "⿹",
    "〈": "〉",
    "《": "》",
    "「": "」",
    "『": "』",
    "【": "】",
    "〔": "〕",
    "〖": "〗",
    "〘": "〙",
    "〚": "〛",
    "㊧": "㊨",
    "꧁": "꧂", # not quite a perfect mirror but matching
    "꭪": "꭫",
    "﴾": "﴿",
    # can't see some of these due to them combining with the quotation marks
    # (and weirdly they show as tofu when commented out)
    # TODO: vet these
    # "︠": "︡",
    # "︢": "︣",
    # "︤": "︥",
    # "︧": "︨",
    # "︩": "︪",
    # "︫": "︬",
    # "︮": "︯",
    # these are not horizontal mirrors
    # "︵": "︶",
    # "︷": "︸",
    # "︹": "︺",
    # "︻": "︼",
    # "︽": "︾",
    # "︿": "﹀",
    # "﹁": "﹂",
    # "﹃": "﹄",
    # "﹇": "﹈",
    "﹙": "﹚",
    "﹛": "﹜",
    "﹝": "﹞",
    "（": "）",
    "［": "］",
    "｛": "｝",
    "｟": "｠",
    # "｢": "｣", # matching but not mirroring
    "￩": "￫",
    "𐡷": "𐡸",
    "𛱰": "𛱲",
    # "𜼀": "𜼌", can't see these, can't vet tofu
    # "𜼁": "𜼍",
    # "𜼂": "𜼎",
    # "𜼃": "𜼏",
    # "𜼄": "𜼐",
    # "𜼅": "𜼑",
    # "𜼆": "𜼒",
    # "𜼇": "𜼓",
    # "𜼈": "𜼔",
    # "𜼉": "𜼕",
    # "𜼊": "𜼖",
    # "𜼋": "𜼗",
    "𝄆": "𝄇",
    "𝅊": "𝅌",
    "𝅋": "𝅍",
    # "🔄": "🔃", # nope
    "🔍": "🔎",
    "🕃": "🕄",
    "🕻": "🕽",
    "🖉": "✎",
    "🖘": "🖙",
    "🖚": "🖛",
    "🖜": "🖝",
    "🗦": "🗧",
    "🗨": "🗩",
    "🗬": "🗭",
    "🗮": "🗯",
    "🙬": "🙮",
    "🞀": "🞂",
    "🠀": "🠂",
    "🠄": "🠆",
    "🠈": "🠊",
    "🠐": "🠒",
    "🠔": "🠖",
    "🠘": "🠚",
    "🠜": "🠞",
    "🠠": "🠢",
    "🠤": "🠦",
    "🠨": "🠪",
    "🠬": "🠮",
    "🠰": "🠲",
    "🠴": "🠶",
    "🠸": "🠺",
    "🠼": "🠾",
    "🡀": "🡂",
    "🡄": "🡆",
    "🡐": "🡒",
    "🡠": "🡢",
    "🡨": "🡪",
    "🡰": "🡲",
    "🡸": "🡺",
    "🢀": "🢂",
    "🢐": "🢒",
    "🢔": "🢖",
    "🢘": "🢚",
    "🢢": "🢣",
    "🢤": "🢥",
    "🢦": "🢥",
    "🢧": "🢥",
    "🢨": "🢩",
    "🢪": "🢫",
    "🤛": "🤜",
    # "🫲": "🫱", can't see this one (tofu)
    # "🮲": "🮳", # not mirrors
    # "🮹": "🮺",
    # "🯁": "🯃",
    # can't see these (invisible?)
    # "󠀨": "󠀩",
    # "󠁛": "󠁝",
    # "󠁻": "󠁽",
}

# Other spaces (en, em, hair, etc.) are often equal in a monospace font.
space = "\u0020"
# ideographicSpace = "\u3000"
spaceWidth = 1 # measureText(space)
# ideographicSpaceWidth = measureText(ideographicSpace)
def fit_spaces(targetWidth: int, ascii_only: bool = False) -> str:
    """Return a string of spaces that fits the target width. Dubious implementation."""
    return space * int(targetWidth / spaceWidth)

def measure_text(grapheme: str) -> int:
    """Measure the width of a grapheme (Unicode character). Dummy implementation."""
    return 1
    
def split_graphemes(line: str) -> list[str]:
    """Split a line into graphemes (Unicode characters). Dummy implementation."""
    return list(line)

# sort of lexical parsing, splitting lines then optionally splitting to alternating language and other text parts
# (for a mediocre definition of language, excluding punctuation, etc.)
def parse_text(text: str, preserve_words: bool = False):
    """Parse text into rows and parts, where each part can be considered lingual or literal."""
    lines = text.split("\n")
    rows = []
    
    for line in lines:
        width = sum(map(measure_text, split_graphemes(line)))
        graphemes = split_graphemes(line)
        parts = []
        current_part = {"text": "", "graphemes": [], "is_words": False}
        parts.append(current_part)
        
        i = 0
        while i < len(graphemes):
            if preserve_words:
                # Look for a whole word at once
                word = []
                j = i
                while j < len(graphemes):
                    if re.search(r"\p{Letter}", graphemes[j]):
                        word.append(graphemes[j])
                    else:
                        break
                    j += 1
                
                # Heuristic: filter out single letters but not "I", "a", or Chinese characters, etc.
                if word and (len(word) > 1 or re.search(r"[IAa]|[^A-Za-z]", "".join(word))):
                    if not current_part["is_words"]:
                        # Start a new part
                        current_part = {"text": "", "graphemes": [], "is_words": True}
                        parts.append(current_part)
                    current_part["text"] += "".join(word)
                    current_part["graphemes"].extend(word)
                    i = j - 1
                    continue
            
            if current_part["is_words"]:
                # Start a new part
                current_part = {"text": "", "graphemes": [], "is_words": False}
                parts.append(current_part)
            
            current_part["text"] += graphemes[i]
            current_part["graphemes"].append(graphemes[i])
            
            i += 1
        
        # Join adjacent words as parts
        if preserve_words:
            new_parts = []
            i = 0
            while i < len(parts):
                new_part = dict(parts[i])
                
                if parts[i]["is_words"] and parts[i + 2]["is_words"] and parts[i + 1]["text"].strip() == "":
                    while parts[i]["is_words"] and parts[i + 2]["is_words"] and parts[i + 1]["text"].strip() == "":
                        new_part["text"] += parts[i + 1]["text"] + parts[i + 2]["text"]
                        new_part["graphemes"].extend(parts[i + 1]["graphemes"] + parts[i + 2]["graphemes"])
                        i += 2
                new_parts.append(new_part)
                i += 1
            
            parts = new_parts
        
        rows.append({"width": width, "parts": parts})
    
    return rows

# function flipText(text, { asciiOnly = false, preserveWords = false, trimLines = true } = {}) {
#     const rows = parseText(text, { preserveWords });
#     const maxWidth = rows.reduce((acc, row) => Math.max(acc, row.width), 0);

#     return rows.map(({ width, parts }) => {
#         let text = fit_spaces(maxWidth - width, asciiOnly);
#         text += parts.map((part) => {
#             if (part.is_words && preserveWords) {
#                 return part.text;
#             }
#             return part.graphemes
#                 .map((grapheme) => flipGrapheme(grapheme, asciiOnly))
#                 .reverse()
#                 .join("");
#         })
#             .reverse()
#             .join("");
#         if (trimLines) {
#             text = text.replace(/\s+$/g, "");
#         }
#         return text;
#     }).join("\n");
# }

def flip_text(text: str, ascii_only: bool = False, preserve_words: bool = False, trim_lines: bool = True):
    rows = parse_text(text, preserve_words=preserve_words)
    max_width = max(row["width"] for row in rows)

    result = []
    for row in rows:
        width, parts = row["width"], row["parts"]
        flipped_text = fit_spaces(max_width - width, ascii_only)
        flipped_text += "".join(part["text"] if part["is_words"] and preserve_words else flip_grapheme(grapheme, ascii_only)
                                for part in reversed(parts)
                                for grapheme in reversed(part["graphemes"]))
        if trim_lines:
            flipped_text = flipped_text.rstrip()
        result.append(flipped_text)

    return "\n".join(result)


def flip_grapheme(grapheme: str, ascii_only: bool = False) -> str:
    if grapheme in unicode_mirror_characters and not ascii_only:
        return unicode_mirror_characters[grapheme]
    elif grapheme in ascii_mirror_characters:
        return ascii_mirror_characters[grapheme]
    else:
        return grapheme

# function visualizeParse(rows) {
#     const container = document.createElement("div");
#     for (const row of rows) {
#         const rowElement = document.createElement("pre");
#         for (const part of row.parts) {
#             const partElement = document.createElement("span");
#             partElement.textContent = part.text;
#             partElement.style.boxShadow = "0 0 3px black";
#             partElement.style.backgroundColor = "rgba(0, 0, 0, 0.1)";
#             if (part.is_words) {
#                 partElement.style.backgroundColor = "rgba(255, 255, 0, 0.2)";
#             }
#             rowElement.appendChild(partElement);
#         }
#         container.appendChild(rowElement);
#     }
#     return container;
# }

def visualize_parse(rows: list[dict]) -> Text:
    """Visualize the result of parse_text()."""
    text = Text()
    for row in rows:
        for part in row["parts"]:
            text.append(part["text"], style="on yellow" if part["is_words"] else "on #000055")
        text.append("\n")
    return text

if __name__ == "__main__":
    import argparse
    from rich import print
    parser = argparse.ArgumentParser(description="Flip text horizontally, mirroring characters.")
    parser.add_argument("text", help="Text to flip")
    parser.add_argument("--ascii-only", action="store_true", help="Only use ASCII mirror characters")
    parser.add_argument("--preserve-words", action="store_true", help="Tries to preserve segments of natural language un-flipped")
    parser.add_argument("--visualize-parse", action="store_true", help="Visualize detection of natural language segments, with colored output")
    parser.add_argument("--trim-lines", action="store_true", help="Trim trailing whitespace from lines")

    args = parser.parse_args()
    if args.visualize_parse:
        print(visualize_parse(parse_text(args.text, preserve_words=args.preserve_words)))
    else:
        print(flip_text(args.text, ascii_only=args.ascii_only, preserve_words=args.preserve_words, trim_lines=args.trim_lines))
