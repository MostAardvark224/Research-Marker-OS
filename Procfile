# This file is replacing launcher.py as the startup command
# more robust for running embeddings, django-q2 bg process, and main django server
web: python manage.py migrate && python manage.py runserver

# Runs in its own process.
qcluster: python -u manage.py qcluster

# sleep is necessary so that the entire process doesn't stop whenever funcs are finished
# uses negligble cpu/ram
embeddings: python manage.py run_embs && python -c "import time; time.sleep(10000000)"
