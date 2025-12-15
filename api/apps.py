from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    # simulating a fake request to run the view on django startup for Scholar Inbox integration 
    def ready(self):
        import os
        from datetime import date, datetime
        from api.scholar_inbox import fetch_scholar_inbox_papers
        from django.test import RequestFactory
        from api.views import FetchScholarInboxPapers
        from api.user_preferences import load_user_preferences, write_user_preferences
        
        # Check settings
        prefs = load_user_preferences()
        user_data = prefs.get('user_preferences', {})
        scholar_prefs = user_data.get('scholar_inbox', {})
        auto_import = scholar_prefs.get('auto_import', False)
        if auto_import:
            last_import_date_str = scholar_prefs.get('last_import_date', None)

            last_import_date = ""

            # making sure the import date is type safe
            if last_import_date_str is None:
                last_import_date = "01-01-0001"
            else:
                last_import_date = date.fromisoformat(scholar_prefs.get('last_import_date', ""))

            today = date.today()
            if last_import_date != today:
                print("Fetching Scholar Inbox papers")
                amount_to_import = scholar_prefs.get('amount_to_import', 1)

                if (amount_to_import is None) or (not isinstance(amount_to_import, int)) or (amount_to_import <= 0):
                    amount_to_import = 1  # Default value

                factory = RequestFactory()
                request = factory.post('/fetch-scholar-inbox-papers/', {'amount_to_import': amount_to_import})
                
                view = FetchScholarInboxPapers.as_view()
                response = view(request)
                
                # Update last import date, everythings nested so it takes a little bit of logic
                scholar_prefs['last_import_date'] = today.isoformat()
                user_data['scholar_inbox'] = scholar_prefs
                prefs['user_preferences'] = user_data

                write_user_preferences(prefs)
                print("Scholar Inbox papers fetched on startup.")



