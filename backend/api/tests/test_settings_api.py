from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


class SettingsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("api.views.load_user_preferences", return_value={"user_preferences": {"theme": "dark"}})
    def test_get_user_preferences(self, _load):
        response = self.client.get(reverse("user-preferences"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user_preferences"]["theme"], "dark")

    @patch("api.views.write_user_preferences")
    def test_put_user_preferences_persists_object(self, write):
        preferences = {"user_preferences": {"general": {"startup_scripts": []}}}
        response = self.client.put(
            reverse("user-preferences"), {"preferences": preferences}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        write.assert_called_once_with(preferences)

    @patch("api.views.write_user_preferences")
    def test_put_user_preferences_rejects_non_object(self, write):
        response = self.client.put(
            reverse("user-preferences"), {"preferences": ["bad"]}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        write.assert_not_called()

    @patch("api.views.sanitize_startup_script_paths")
    @patch("api.views.write_user_preferences")
    def test_invalid_startup_script_does_not_write_preferences(self, write, sanitize):
        sanitize.return_value = ([], [{"path": "bad", "error": "not absolute"}])
        response = self.client.put(
            reverse("user-preferences"),
            {"preferences": {"user_preferences": {"general": {"startup_scripts": ["bad"]}}}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        write.assert_not_called()

    @patch("api.views.get_env_vars_potential_list", return_value=["GEMINI_API_KEY"])
    @patch("api.views.intitial_env_vars_data", return_value={"exists": False})
    @patch("api.views.load_env_vars", return_value={"exists": True, "GEMINI_API_KEY": "secret"})
    def test_get_environment_variables_contract(self, _load, _initial, _potential):
        response = self.client.get(reverse("environment-variables"))
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data["exists"], True)
        self.assertEqual(response.data["potential_list"], ["GEMINI_API_KEY"])

    @patch("api.views.get_all_provider_models")
    @patch("api.views.load_env_vars", return_value={"GEMINI_API_KEY": "new"})
    @patch("api.views.write_env_vars")
    def test_put_environment_variables_writes_and_refreshes_models(self, write, load, models):
        variables = {"GEMINI_API_KEY": "new"}
        response = self.client.put(
            reverse("environment-variables"), {"variables": variables}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        write.assert_called_once_with(variables)
        models.assert_called_once_with(load.return_value, force_refresh=True)

    @patch("api.views.get_startup_scripts_status", return_value={"complete": True})
    def test_startup_script_status(self, _status):
        response = self.client.get(reverse("startup-scripts-status"))
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data["complete"], True)

    @patch("api.views.get_ocr_providers", return_value=[{"id": "paddleocr"}])
    @patch("api.views.load_env_vars", return_value={})
    def test_ocr_provider_catalog(self, _load, _providers):
        response = self.client.get(reverse("ocr-providers"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["providers"][0]["id"], "paddleocr")
