import os 
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load user preferences from local json file
def load_user_preferences():
    file = os.path.join(BASE_DIR, 'user_preferences.json')
    if os.path.isfile(file):
        with open(file, 'r') as f:
            return json.load(f)
    else: 
        print(file)
        print("No user preferences file found.")
        return {}

# Write new preferences to local json file
# Preferences should be a json object
def write_user_preferences(preferences):
    file = os.path.join(BASE_DIR, 'user_preferences.json')
    with open(file, 'w') as f:
        json.dump(preferences, f, indent=4)