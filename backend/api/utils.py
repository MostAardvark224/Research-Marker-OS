import os
import json 
from pathlib import Path
import sys
from django.core.management.utils import get_random_secret_key

def generate_new_django_key():
    new_key = get_random_secret_key()
    return new_key

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent # desktop app 
    else:
        return Path(__file__).resolve().parent.parent # dev

# separate function to init necessary env vars
# for code readability and dev
def intitial_env_vars_data(): 
    new_django_key = generate_new_django_key()
    init_data = dict(
                DJANGO_SECRET_KEY = new_django_key, 
                GEMINI_MODEL = "gemini-3-flash-preview" # default
            )
    return init_data if init_data else {}

# Load env vars from local json file
def load_env_vars():
    BASE_DIR = get_base_dir()
    file = os.path.join(BASE_DIR, 'env.json')
    if os.path.isfile(file):
        with open(file, 'r') as f:
            return json.load(f)
    else: 
        # will create the file if it doesn't exist
        print(f"Creating new file at: {file}")

        initial_data = intitial_env_vars_data()

        with open(file, 'w') as f:
            json.dump(initial_data, f, indent=4)
        return initial_data

        
# Write new env vars to local json file
# vars should just be a python dictionary
def write_env_vars(vars):
    BASE_DIR = get_base_dir()
    file = os.path.join(BASE_DIR, 'env.json')
    original_vars = load_env_vars()

    cleaned_vars = vars
    if isinstance(vars, str): 
        try: 
            cleaned_vars = json.loads(vars)
        except Exception as e: 
            print("failed to load vars as a dict")
            return

    if not isinstance(cleaned_vars, dict): 
        print("vars is not a python dictionary")
        return
    
    original_vars.update(cleaned_vars) # only changes vars that were included in the param, keeps existing
    
    with open(file, 'w') as f:
        json.dump(original_vars, f, indent=4)