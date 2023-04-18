import json

translations = {}

def load_language(language_code: str):
	"""Load a language from the translations directory."""
	global translations
	translations = {}
	try:
		with open(f"localization/{language_code}/localizations.js", "r") as f:
			# find the JSON object
			js = f.read()
			start = js.find("{")
			end = js.rfind("}")
			# parse the JSON object
			translations = json.loads(js[start:end + 1])
	except FileNotFoundError:
		print(f"Could not find language file for '{language_code}'.")
	except json.decoder.JSONDecodeError as e:
		print(f"Could not parse language file for '{language_code}': {e}")
	except Exception as e:
		print(f"Could not load language '{language_code}': {e}")

def get(base_language_str: str) -> str:
	"""Get a localized string."""
	if base_language_str in translations:
		return translations[base_language_str]
	else:
		return base_language_str
