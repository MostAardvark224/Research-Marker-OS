"""
moved from manage.py runserver to launcher.py for a couple of reasons : 
1. only way to run embeddings on app startup was thru a diff command, querying db in any other way is considered unsafe
2. To run the qcluster process (lib=django-q2, runs process for smart collections), I needed another thread. This thread will sit idle 99% of the time but it eats neglible amt of CPU
"""
import sys
import threading
from django.core.management import call_command
import os
import django

def start_app():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    django.setup()

    # Determine execution mode
    use_reload = '--dev' in sys.argv
    is_reloader_child = os.environ.get('RUN_MAIN') == 'true'

    if not is_reloader_child:
        print("Performing Startup Checks...")
        call_command('migrate', interactive=False)
        
        # Start embeddings initialization in bg 
        def run_embs():
            try:
                call_command('run_embs') 
            except Exception as e:
                print(f"Embedding Error: {e}")
        
        t_embs = threading.Thread(target=run_embs, daemon=True)
        t_embs.start()

    if not use_reload or is_reloader_child:
        print(f"Starting Q Cluster (Mode: {'Dev/Reload' if use_reload else 'Production'})...")
        
        def run_q_cluster():
            try:
                call_command('qcluster')
            except Exception as e:
                print(f"Q Cluster Error: {e}")

        t_q = threading.Thread(target=run_q_cluster, daemon=True)
        t_q.start()

    print(f"Starting server (Auto-reload: {use_reload})...")
    
    # This blocks the main thread until the app is closed
    call_command('runserver', '127.0.0.1:8000', use_reloader=use_reload)

if __name__ == "__main__":
    start_app()