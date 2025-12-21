# launcher.py
import sys
import threading
from django.core.management import call_command
import os
import django

def start_app():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    django.setup()

    # Only run migrations/embeddings if NOT in reload mode (the child process)
    # prevents the background tasks from running twice when auto-reload is on.
    if os.environ.get('RUN_MAIN') != 'true':
        print("Performing Startup Checks")
        call_command('migrate', interactive=False)
        
        # Start embeddings in bg
        def run_bg():
            try:
                call_command('run_embs')
            except Exception as e:
                print(e)
        
        t = threading.Thread(target=run_bg, daemon=True)
        t.start()

    # Check if dev mode (reloading) or app mode (stable)
    # dev mode: python launcher.py --dev
    use_reload = '--dev' in sys.argv

    print(f"starting server (auto-reload: {use_reload})...")
    
    # We pass use_reloader explicitly
    call_command('runserver', '127.0.0.1:8000', use_reloader=use_reload)

if __name__ == "__main__":
    start_app()