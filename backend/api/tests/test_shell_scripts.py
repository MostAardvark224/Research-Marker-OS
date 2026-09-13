import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from api.startup_scripts import (
    load_configured_startup_scripts,
    queue_shell_scripts,
    run_shell_scripts,
    sanitize_shell_script_entries,
)


class ShellScriptConfigurationTests(SimpleTestCase):
    def test_legacy_paths_are_migrated_to_startup_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "legacy.sh"
            script.write_text("#!/bin/bash\n", encoding="utf-8")

            entries, errors = sanitize_shell_script_entries([str(script)])

        self.assertEqual(errors, [])
        self.assertEqual(
            entries,
            [{"path": str(script), "run_on_startup": True}],
        )

    @patch("api.user_preferences.load_user_preferences")
    def test_only_selected_entries_run_at_startup(self, load_preferences):
        with tempfile.TemporaryDirectory() as directory:
            startup = Path(directory) / "startup.sh"
            manual = Path(directory) / "manual.sh"
            startup.write_text("#!/bin/bash\n", encoding="utf-8")
            manual.write_text("#!/bin/bash\n", encoding="utf-8")
            load_preferences.return_value = {
                "user_preferences": {
                    "general": {
                        "shell_scripts": [
                            {"path": str(startup), "run_on_startup": True},
                            {"path": str(manual), "run_on_startup": False},
                        ]
                    }
                }
            }

            configured = load_configured_startup_scripts()

        self.assertEqual(configured, [str(startup)])


class ShellScriptExecutionTests(SimpleTestCase):
    def test_runtime_execution_captures_output(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "hello.sh"
            script.write_text("#!/bin/bash\nprintf 'hello from script'\n", encoding="utf-8")
            status_path = Path(directory) / "runtime-status.json"

            with patch("api.startup_scripts._runtime_status_path", return_value=status_path):
                result = run_shell_scripts([str(script)], run_id="run-1")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["run_id"], "run-1")
        self.assertEqual(result["results"][0]["message"], "hello from script")
        self.assertEqual(result["results"][0]["exit_code"], 0)

    def test_runtime_queue_only_accepts_configured_scripts(self):
        with tempfile.TemporaryDirectory() as directory:
            configured = Path(directory) / "configured.sh"
            unconfigured = Path(directory) / "unconfigured.sh"
            configured.write_text("#!/bin/bash\n", encoding="utf-8")
            unconfigured.write_text("#!/bin/bash\n", encoding="utf-8")
            status_path = Path(directory) / "runtime-status.json"

            with (
                patch(
                    "api.startup_scripts.load_configured_shell_scripts",
                    return_value=[
                        {"path": str(configured), "run_on_startup": False}
                    ],
                ),
                patch("api.startup_scripts.get_shell_scripts_status", return_value={"status": "idle"}),
                patch("api.startup_scripts._runtime_status_path", return_value=status_path),
                patch("api.task_queue.enqueue_task", return_value="task-1") as enqueue,
            ):
                queued = queue_shell_scripts([str(configured)])
                with self.assertRaisesMessage(
                    ValueError, "Only shell scripts saved in Settings can be run."
                ):
                    queue_shell_scripts([str(unconfigured)])

        self.assertEqual(queued["task_id"], "task-1")
        self.assertEqual(enqueue.call_count, 1)
