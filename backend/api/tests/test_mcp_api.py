from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.errors import DocumentNotFound


class McpSecurityAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.token_patcher = patch("api.mcp.views.load_or_create_token", return_value="token-123")
        self.token_patcher.start()

    def tearDown(self):
        self.token_patcher.stop()

    def auth(self):
        return {"HTTP_AUTHORIZATION": "Bearer token-123", "REMOTE_ADDR": "127.0.0.1"}

    @patch("api.mcp.views.mcp_tools.active_paper_payload")
    def test_missing_and_invalid_tokens_are_rejected(self, active):
        missing = self.client.get(reverse("mcp-tools-active"), REMOTE_ADDR="127.0.0.1")
        invalid = self.client.get(
            reverse("mcp-tools-active"),
            HTTP_AUTHORIZATION="Bearer wrong",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)
        active.assert_not_called()

    @patch("api.mcp.views.mcp_tools.active_paper_payload")
    def test_non_loopback_client_is_forbidden_even_with_token(self, active):
        response = self.client.get(
            reverse("mcp-tools-active"),
            HTTP_AUTHORIZATION="Bearer token-123",
            REMOTE_ADDR="10.0.0.8",
        )
        self.assertEqual(response.status_code, 403)
        active.assert_not_called()

    @patch("api.mcp.views.mcp_tools.active_paper_payload", return_value={"active": False})
    def test_authorized_active_paper(self, active):
        response = self.client.get(reverse("mcp-tools-active"), **self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"active": False})
        active.assert_called_once_with()

    @patch("api.mcp.views.mcp_tools.page_payload", return_value={"page_number": 2})
    def test_page_parses_query_parameters(self, page):
        response = self.client.get(
            reverse("mcp-tools-page") + "?page=2&document_id=7&include_image=true",
            **self.auth(),
        )
        self.assertEqual(response.status_code, 200)
        page.assert_called_once_with(page_number=2, document_id=7, include_image=True)

    def test_pages_requires_both_bounds(self):
        response = self.client.get(reverse("mcp-tools-pages") + "?start=1", **self.auth())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "research_marker_error")

    @patch("api.mcp.views.mcp_tools.pages_payload", return_value={"pages": []})
    def test_pages_delegates_valid_range(self, pages):
        response = self.client.get(
            reverse("mcp-tools-pages")
            + "?start=2&end=4&document_id=7&include_images=true",
            **self.auth(),
        )
        self.assertEqual(response.status_code, 200)
        pages.assert_called_once_with(
            start_page=2, end_page=4, document_id=7, include_images=True
        )

    @patch("api.mcp.views.mcp_tools.selection_payload", return_value={"active": True, "text": "selected"})
    def test_selection_returns_tool_payload(self, selection):
        response = self.client.get(reverse("mcp-tools-selection"), **self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["text"], "selected")
        selection.assert_called_once_with()

    @patch("api.mcp.views.mcp_tools.search_payload")
    def test_search_requires_nonempty_query(self, search):
        response = self.client.get(reverse("mcp-tools-search") + "?query=", **self.auth())
        self.assertEqual(response.status_code, 400)
        search.assert_not_called()

    @patch("api.mcp.views.mcp_tools.search_payload", return_value={"chunks": []})
    def test_search_caps_contract_is_delegated(self, search):
        response = self.client.get(
            reverse("mcp-tools-search") + "?query=methods&document_id=9&limit=4",
            **self.auth(),
        )
        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with(query="methods", document_id=9, limit=4)

    @patch("api.mcp.views.mcp_tools.resolve_question_payload")
    def test_resolve_requires_question(self, resolve):
        response = self.client.post(reverse("mcp-tools-resolve"), {}, format="json", **self.auth())
        self.assertEqual(response.status_code, 400)
        resolve.assert_not_called()

    @patch("api.mcp.views.mcp_tools.resolve_question_payload", return_value={"referenced_pages": [3]})
    def test_resolve_delegates_valid_request(self, resolve):
        response = self.client.post(
            reverse("mcp-tools-resolve"),
            {"question": "Explain @page:3", "document_id": 8, "include_page_image": False},
            format="json",
            **self.auth(),
        )
        self.assertEqual(response.status_code, 200)
        resolve.assert_called_once_with(
            question="Explain @page:3", document_id=8, include_page_image=False
        )

    @patch("api.mcp.views.mcp_tools.active_paper_payload")
    def test_domain_error_status_is_preserved(self, active):
        active.side_effect = DocumentNotFound("No active document")
        response = self.client.get(reverse("mcp-tools-active"), **self.auth())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"], "document_not_found")

    def test_setup_is_localhost_only(self):
        response = self.client.get(reverse("mcp-setup"), REMOTE_ADDR="10.0.0.8")
        self.assertEqual(response.status_code, 403)

    @patch("api.mcp.views.setup_payload", return_value={"configured": True})
    @patch("api.mcp.discovery.ensure_discovery_matches_live_backend")
    @patch("api.mcp.views.build_claude_desktop_config", return_value={"mcpServers": {}})
    def test_setup_get_returns_config_for_loopback(self, _config, _ensure, _payload):
        response = self.client.get(reverse("mcp-setup"), REMOTE_ADDR="127.0.0.1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("claude_desktop_config_json", response.data)

    def test_setup_rejects_unknown_action(self):
        response = self.client.post(
            reverse("mcp-setup"),
            {"action": "unsupported"},
            format="json",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "unknown_action")

    @patch("api.mcp.views.setup_payload", return_value={"configured": True})
    @patch("api.mcp.discovery.ensure_discovery_matches_live_backend")
    @patch("api.mcp.views.build_claude_desktop_config", return_value={"mcpServers": {}})
    @patch("api.mcp.views.regenerate_token", return_value="fresh-token")
    def test_setup_can_regenerate_token(self, regenerate, _config, _ensure, _payload):
        response = self.client.post(
            reverse("mcp-setup"),
            {"action": "regenerate_token"},
            format="json",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["token"], "fresh-token")
        regenerate.assert_called_once_with()
