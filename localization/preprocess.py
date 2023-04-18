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
    m = re.search(r"[^&]&[^&\s]", f" {text}")
    return m.start() if m else -1

def has_hotkey(text):
    return index_of_hotkey(text) != -1


def remove_hotkey(text):
    text = re.sub(r"\s?\(&.\)", "", text)
    text = re.sub(r"([^&]|^)&([^&\s])", r"\1\2", text)
    return text


def remove_ellipsis(string):
    return string.replace("...", "")


def only_unique(value, index, self):
    return self.index(value) == index


def get_strings(lang):
    rc_files = glob.glob(f"{os.path.dirname(__file__)}/{lang}/**/*.rc", recursive=True)
    for rc_file in rc_files:
        with open(rc_file, "r", encoding="utf16") as f:
            yield from parse_rc_file(f.read().replace("\ufeff", ""))


base_strings = list(get_strings(base_lang))
for target_lang in target_langs:
    target_strings = list(get_strings(target_lang))
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
                    add_localizations(re.split(splitter, base_string), re.split(splitter, target_string))
                else:
                    add_localization(remove_ellipsis(base_string), remove_ellipsis(target_string), 1)
                    if has_hotkey(base_string):
                        add_localization(remove_ellipsis(remove_hotkey(base_string)), remove_ellipsis(remove_hotkey(target_string)), 3)

    add_localizations(base_strings, target_strings)

    for base_string, options in localizations.items():
        options.sort(key=lambda x: x["fudgedness"])
        unique_strings = list(set(option["target_string"] for option in options))
        if len(unique_strings) > 1:
            unique_strings_json = json.dumps(unique_strings, indent="\t")
            print(f'Collision for "{base_string}": {unique_strings_json}')
        localizations[base_string] = unique_strings[0]

    localizations_json = json.dumps(localizations, indent="\t")
    js = f"""
//
// NOTE: This is a generated file! Don't edit it directly.
// Eventually community translation will be set up on some translation platform.
// 
// Generated with: npm run update-localization
//
loaded_localizations("{target_lang}", {localizations_json});
"""

    with open(f"{os.path.dirname(__file__)}/{target_lang}/localizations.js", "w", encoding="utf8") as f:
        f.write(js)

# file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "index.html"))
# with open(file_path, "r") as f:
#     code = f.read()
# available_langs_json = json.dumps(available_langs).replace('","', '", "')
# code = re.sub(r"(available_languages\s*=\s*)\[[^\]]*\]", f"$1{available_langs_json}]", code)
# with open(file_path, "w") as f:
#     f.write(code)
# print(f'Updated available_languages list in "{file_path}"')
