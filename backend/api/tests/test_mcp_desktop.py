import asyncio
import json
from pathlib import Path
import sys
import tempfile
import tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from api.mcp.discovery import build_chatgpt_desktop_config, chatgpt_config_toml, setup_payload


class DesktopMcpConfigTests(SimpleTestCase):
    @patch("api.mcp.discovery.ensure_stable_mcp_launcher")
    @patch("api.mcp.discovery.resolve_command_and_args")
    def test_chatgpt_and_codex_config_round_trips_platform_paths(self, resolve, _launcher):
        for command in [r'C:\Users\Reader Name\Research Marker\api.exe', '/opt/Papers 🔬/"research marker"/api']:
            with self.subTest(command=command):
                resolve.return_value = (command, ["mcp", "argument with spaces"], {
                    "USER_DATA_DIR": r"C:\Users\Reader Name\Data",
                    "RESEARCH_MARKER_MCP_DISCOVERY": "/tmp/reader/discovery.json",
                })
                config = build_chatgpt_desktop_config()
                self.assertEqual(tomllib.loads(chatgpt_config_toml(config)), config)
                self.assertEqual(config["mcp_servers"]["research-marker"]["command"], command)

    @patch("api.mcp.discovery.ensure_discovery_matches_live_backend", return_value={"base_url": "http://127.0.0.1:8000/api"})
    @patch("api.mcp.discovery.load_or_create_token", return_value="test-token")
    @patch("api.mcp.discovery.write_discovery_payload")
    @patch("api.mcp.discovery.build_claude_desktop_config", return_value={"mcpServers": {}})
    @patch("api.mcp.discovery.build_chatgpt_desktop_config")
    def test_setup_includes_both_clients(self, chatgpt, _claude, _write, _token, _discovery):
        chatgpt.return_value = {"mcp_servers": {"research-marker": {
            "command": "api", "args": ["mcp"], "env": {},
            "startup_timeout_sec": 30, "tool_timeout_sec": 120,
        }}}
        payload = setup_payload()
        self.assertIn("claude_desktop_config", payload)
        self.assertEqual(tomllib.loads(payload["chatgpt_desktop_config_toml"]), payload["chatgpt_desktop_config"])


class DesktopMcpTransportTests(SimpleTestCase):
    def test_stdio_handshake_tools_and_paper_read_work_for_both_clients(self):
        """Exercise the same transport ChatGPT/Codex/Claude launch, without real papers."""
        calls = []

        class Backend(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append((self.path, self.headers.get("Authorization")))
                body = json.dumps({"active": True, "document_title": "Fixture paper", "current_page": 2}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        http_server = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        worker = Thread(target=http_server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                discovery = Path(directory) / "discovery.json"
                port = http_server.server_port
                discovery.write_text(json.dumps({
                    "base_url": f"http://127.0.0.1:{port}/api", "port": port, "token": "fixture-token",
                }))

                async def check_clients():
                    from mcp.client.session import ClientSession
                    from mcp.client.stdio import StdioServerParameters, stdio_client
                    for client_name in ("chatgpt", "codex"):
                        from mcp.types import Implementation
                        parameters = StdioServerParameters(
                            command=sys.executable, args=["-m", "api.mcp.server"],
                            env={"PYTHONPATH": str(Path(__file__).resolve().parents[2]),
                                 "RESEARCH_MARKER_MCP_DISCOVERY": str(discovery)},
                        )
                        async with stdio_client(parameters) as streams:
                            async with ClientSession(
                                streams[0], streams[1], client_info=Implementation(name=client_name, version="test"),
                            ) as session:
                                initialized = await session.initialize()
                                self.assertIn("Research Marker", initialized.instructions)
                                catalog = await session.list_tools()
                                self.assertEqual({tool.name for tool in catalog.tools}, {
                                    "get_active_paper", "get_page", "get_pages", "get_selection", "search_paper", "resolve_paper_question",
                                })
                                self.assertTrue(all(tool.annotations.read_only_hint for tool in catalog.tools))
                                result = await session.call_tool("get_active_paper", {})
                                self.assertFalse(result.is_error)
                                self.assertEqual(json.loads(result.content[0].text)["document_title"], "Fixture paper")

                async def bounded_check():
                    await asyncio.wait_for(check_clients(), timeout=20)

                async_to_sync(bounded_check)()
            self.assertTrue(calls)
            self.assertTrue(all(auth == "Bearer fixture-token" for _, auth in calls))
        finally:
            http_server.shutdown()
            http_server.server_close()
            worker.join(timeout=3)
