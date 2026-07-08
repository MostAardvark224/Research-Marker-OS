import os
import sys
import threading
import uvicorn
from pathlib import Path
from django.core.management import call_command

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
from django.core.asgi import get_asgi_application

django.setup()
application = get_asgi_application()

if __name__ == "__main__":
    django.setup()

    print("Checking for database migrations...")
    try:
        call_command('migrate', interactive=False)
        print("Migrations applied successfully.")
    except Exception as e:
        print(f"Error applying migrations: {e}")

    def run_qcluster():
        try:
            print("Starting background task worker (qcluster)...")
            call_command('qcluster')
        except Exception as e:
            print(f"Q Cluster Error: {e}")

    q_thread = threading.Thread(target=run_qcluster, daemon=True)
    q_thread.start()

    uvicorn.run(application, host="127.0.0.1", port=0)