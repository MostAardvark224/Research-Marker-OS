import os 
import json
from pathlib import Path
from .utils import get_base_dir # WILL HAVE TO CHANGE THIS TO APP DATA DIR. Make sure to change all base dir usages as well 


def intitial_user_prefs(): 
    init_data = {
        "user_preferences": {
            "general": {},
            "scholar_inbox": {
            "auto_import": False,
            "last_import_date": "null",
            "amount_to_import": 0
            },
            "ai": {
                "GEMINI_MODEL" : "gemini-3-flash-preview" 
            }
        }
    }

    return init_data

# Load user preferences from local json file
def load_user_preferences():
    BASE_DIR = get_base_dir() 
    file = os.path.join(BASE_DIR, 'user_preferences.json')
    if os.path.isfile(file):
        with open(file, 'r') as f:
            return json.load(f)
    else: 
        # will create the file if it doesn't exist
        print(f"Creating new file at: {file}")

        initial_data = intitial_user_prefs()

        with open(file, 'w') as f:
            json.dump(initial_data, f, indent=4)
        return initial_data


import collections.abc

# Recursively update the source dictionary with the overrides dictionary.
def deep_update(source, overrides):
    for key, value in overrides.items():
        if isinstance(value, collections.abc.Mapping) and value:
            returned = deep_update(source.get(key, {}), value)
            source[key] = returned
        else:
            source[key] = overrides[key]
    return source

# gets a dict key, even if its nested
def deep_get(data, target_key, default=None):
    if target_key in data:
        return data[target_key]

    for value in data.values():
        if isinstance(value, dict):
            result = deep_get(value, target_key)
            if result is not None:
                return result

    return default

# Write new preferences to local json file
# Preferences should be a json object
def write_user_preferences(preferences):
    BASE_DIR = get_base_dir() 
    file = os.path.join(BASE_DIR, 'user_preferences.json')

    original_prefs = load_user_preferences()

    cleaned_prefs = preferences
    if isinstance(cleaned_prefs, str): 
        try: 
            cleaned_prefs = json.loads(cleaned_prefs)
        except Exception as e: 
            print("failed to load prefs as a dict")
            return

    if not isinstance(cleaned_prefs, dict): 
        print("prefs is not a python dictionary")
        return
    
    deep_update(original_prefs, cleaned_prefs) # only changes prefs that were included in the param, keeps existing
    
    with open(file, 'w') as f:
        json.dump(original_prefs, f, indent=4)