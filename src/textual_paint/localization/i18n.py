import os
import json
import re

translations: dict[str, str] = {}
base_language = "en"
current_language = base_language
localization_folder = os.path.dirname(__file__)
untranslated_file = os.path.join(localization_folder, "untranslated.txt")

TRACK_UNTRANSLATED = False
"""Whether to update the untranslated.txt file with any untranslated strings.

This should be disabled in production.
A better way to do this would be static source code analysis, using xgettext, pybabel, or xpot.
https://docs.python.org/3/library/gettext.html#internationalizing-your-programs-and-modules
"""

def get_direction() -> str:
	"""Get the text direction for the current language."""
	if current_language in ["ar", "he"]:
		return "rtl"
	return "ltr"

def load_language(language_code: str):
	"""Load a language from the translations directory."""
	global translations
	translations = {}
	if language_code == base_language:
		return
	try:
		file = os.path.join(localization_folder, language_code, "localizations.js")
		with open(file, "r", encoding="utf-8") as f:
			# find the JSON object
			js = f.read()
			start = js.find("{")
			end = js.rfind("}")
			# parse the JSON object
			translations = json.loads(js[start:end + 1])
			global current_language
			current_language = language_code
	except FileNotFoundError:
		print(f"Could not find language file for '{language_code}'.")
	except json.decoder.JSONDecodeError as e:
		print(f"Could not parse language file for '{language_code}': {e}")
	except Exception as e:
		print(f"Could not load language '{language_code}': {e}")

if TRACK_UNTRANSLATED:
	untranslated: set[str] = set()
	try:
		with open(untranslated_file, "r", encoding="utf-8") as f:
			untranslated = set(f.read().splitlines())
	except FileNotFoundError:
		pass

def get(base_language_str: str, *interpolations: str) -> str:
	"""Get a localized string."""
	def find_localization(base_language_str: str) -> str:
		amp_index = index_of_hotkey(base_language_str)
		if amp_index > -1:
			without_hotkey = remove_hotkey(base_language_str)
			if without_hotkey in translations:
				hotkey_def = base_language_str[amp_index:amp_index + 2]
				if translations[without_hotkey].upper().find(hotkey_def.upper()) > -1:
					return translations[without_hotkey]
				else:
					if has_hotkey(translations[without_hotkey]):
						# window.console && console.warn(`Localization has differing accelerator (hotkey) hint: '${translations[without_hotkey]}' vs '${base_language_str}'`);
						# @TODO: detect differing accelerator more generally
						return f"{remove_hotkey(translations[without_hotkey])} ({hotkey_def})"
					return f"{translations[without_hotkey]} ({hotkey_def})"
		if base_language_str in translations:
			return translations[base_language_str]
		# special case for menu items, where we need to split the string into two parts to translate them separately
		# (maybe only because of how I preprocessed the localization files)	
		parts = base_language_str.split("\t")
		if len(parts) == 2:
			parts[0] = find_localization(parts[0])
			return "\t".join(parts)

		# special handling for ellipsis
		if base_language_str[-3:] == "...":
			return find_localization(base_language_str[:-3]) + "..."

		if TRACK_UNTRANSLATED:
			if base_language_str not in untranslated and current_language != base_language:
				untranslated.add(base_language_str)
				# append to untranslated strings file
				with open(untranslated_file, "a", encoding="utf-8") as f:
					f.write(base_language_str + "\n")

		return base_language_str

	def interpolate(text: str, interpolations: tuple[str, ...]):
		for i in range(len(interpolations)):
			text = text.replace(f"%{i + 1}", interpolations[i])
		return text

	return interpolate(find_localization(base_language_str), interpolations)

# & defines accelerators (hotkeys) in menus and buttons and things, which get underlined in the UI.
# & can be escaped by doubling it, e.g. "&Taskbar && Start Menu"
def index_of_hotkey(text: str) -> int:
	"""Returns the index of the ampersand that defines a hotkey, or -1 if not present."""
	# The space here handles beginning-of-string matching and counteracts the offset for the [^&] so it acts like a negative lookbehind
	m = re.search(r"[^&]&[^&\s]", f" {text}")
	return m.start() if m else -1

def has_hotkey(text: str) -> bool:
	"""Returns whether the text has a hotkey defined."""
	return index_of_hotkey(text) != -1

def remove_hotkey(text: str) -> str:
	"""Returns the text with the hotkey removed, keeping any hotkey escapes (&&) in tact."""
	# Translations sometimes have the hotkey in parentheses, e.g. "&Hide": "숨기기(&H)"
	# This removes the whole parenthetical.
	text = re.sub(r"\s?\(&.\)", "", text)
	# For other cases, just remove the ampersand, e.g. "&Taskbar && Start Menu" -> "Taskbar && Start Menu"
	text = re.sub(r"([^&]|^)&([^&\s])", r"\1\2", text)
	# A better way might be to use the index_of_hotkey function, ideally for the parenthetical removal too,
	# but in practice, there shouldn't be translations with ambiguous/multiple hotkeys like "&Taskbar &Start Menu".
	# index = index_of_hotkey(text)
	# text = text[:index] + text[index + 1:] if index != -1 else text
	return text

def markup_hotkey(text: str) -> str:
	"""Returns Rich API-compatible markup underlining the hotkey if present."""
	index = index_of_hotkey(text)
	if index == -1:
		return text
	else:
		return text[:index] + f"[u]{text[index + 1]}[/u]" + text[index + 2:]

def get_hotkey(text: str) -> str | None:
	"""Returns the hotkey if present."""
	index = index_of_hotkey(text)
	if index == -1:
		return None
	else:
		return text[index + 1]
