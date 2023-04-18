import os
import re
import glob
import json

from parse_rc_file import parse_rc_file


base_lang = "en"
available_langs = [dir for dir in os.listdir(os.path.dirname(__file__)) if re.match(r"^\w+(-\w+)?$", dir)]
target_langs = [lang for lang in available_langs if lang != base_lang]

print("Target languages:", target_langs)

# & defines accelerators (hotkeys) in menus and buttons and things, which get underlined in the UI.
# & can be escaped by doubling it, e.g. "&Taskbar && Start Menu"
def index_of_hotkey(text):
	# Returns the index of the ampersand that defines a hotkey, or -1 if not present.
	# The space here handles beginning-of-string matching and counteracts the offset for the [^&] so it acts like a negative lookbehind
    return f" {text}".find(re.compile(r"[^&]&[^&\s]"))

def has_hotkey(text):
    return index_of_hotkey(text) != -1


def remove_hotkey(text):
    return re.sub(r"\s?\(&.\)", "", text).replace(re.compile(r"([^&]|^)&([^&\s])"), r"\1\2")


def remove_ellipsis(string):
    return string.replace("...", "")


def only_unique(value, index, self):
    return self.index(value) == index


def get_strings(lang):
    return [parse_rc_file(open(rc_file, "r", encoding="utf16").read().replace("\ufeff", "")) for rc_file in glob.glob(f"{os.path.dirname(__file__)}/{lang}/**/*.rc")]


base_strings = get_strings(base_lang)
for target_lang in target_langs:
    target_strings = get_strings(target_lang)
    localizations = {}

    def add_localization(base_string, target_string, fudgedness):
        localizations[base_string] = localizations.get(base_string, [])
        localizations[base_string].append({"target_string": target_string, "fudgedness": fudgedness})

    def add_localizations(base_strings, target_strings):
        for i, target_string in enumerate(target_strings):
            base_string = base_strings[i]
            if base_string != target_string and base_string and target_string:
                # Split strings like "&Attributes...\tCtrl+E"
                # and "Fills an area with the current drawing color.\nFill With Color"
                splitter = re.compile(r"\t|\r?\n")
                if splitter.search(base_string):
                    add_localizations(base_string.split(splitter), target_string.split(splitter))
                else:
                    add_localization(remove_ellipsis(base_string), remove_ellipsis(target_string), 1)
                    if has_hotkey(base_string):
                        add_localization(remove_ellipsis(remove_hotkey(base_string)), remove_ellipsis(remove_hotkey(target_string)), 3)

    add_localizations(base_strings, target_strings)

    for base_string, options in localizations.items():
        options.sort(key=lambda x: x["fudgedness"])
        unique_strings = list(set(option["target_string"] for option in options))
        if len(unique_strings) > 1:
            print(f'Collision for "{base_string}": {json.dumps(unique_strings, indent="\t")}')
        localizations[base_string] = unique_strings[0]

    js = f"""
//
// NOTE: This is a generated file! Don't edit it directly.
// Eventually community translation will be set up on some translation platform.
// 
// Generated with: npm run update-localization
//
loaded_localizations("{target_lang}", {json.dumps(localizations, indent="\t")});
"""

    with open(f"{os.path.dirname(__file__)}/{target_lang}/localizations.js", "w", encoding="utf8") as f:
        f.write(js)

file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "index.html"))
with open(file_path, "r") as f:
    code = f.read()
code = re.sub(r"(available_languages\s*=\s*)\[[^\]]*\]", f"$1{json.dumps(available_langs).replace('","', '", "')}]", code)
with open(file_path, "w") as f:
    f.write(code)
print(f'Updated available_languages list in "{file_path}"')
