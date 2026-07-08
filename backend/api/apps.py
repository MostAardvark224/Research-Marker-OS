import os
import sys
from datetime import date

from django.apps import AppConfig


def _parse_last_import_date(value):
    if value is None or value == "" or value == "null":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        # Skip the parent process during `manage.py runserver` autoreload only.
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return

        from django.test import RequestFactory
        from rest_framework import status

        from api.user_preferences import load_user_preferences, write_user_preferences
        from api.views import FetchScholarInboxPapers

        prefs = load_user_preferences()
        user_data = prefs.get('user_preferences', {})
        scholar_prefs = user_data.get('scholar_inbox', {})
        auto_import = scholar_prefs.get('auto_import', False)
        if not auto_import:
            return

        last_import_date = _parse_last_import_date(scholar_prefs.get('last_import_date'))
        today = date.today()
        if last_import_date == today:
            return

        amount_to_import = scholar_prefs.get('amount_to_import', 1)
        if amount_to_import == 0:
            return

        print("Fetching Scholar Inbox papers")
        factory = RequestFactory()
        request = factory.post(
            '/fetch-scholar-inbox-papers/',
            {'amount_to_import': amount_to_import},
            format='json',
        )

        view = FetchScholarInboxPapers.as_view()
        response = view(request)

        if response.status_code != status.HTTP_200_OK:
            print(f"Scholar Inbox auto-import failed with status {response.status_code}")
            return

        scholar_prefs['last_import_date'] = today.isoformat()
        user_data['scholar_inbox'] = scholar_prefs
        prefs['user_preferences'] = user_data
        write_user_preferences(prefs)
        print("Scholar Inbox papers fetched on startup.")
