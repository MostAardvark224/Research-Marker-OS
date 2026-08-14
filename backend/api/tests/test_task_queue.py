import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from api import task_queue


class OnDemandTaskQueueTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    @patch("api.task_queue.subprocess.Popen")
    def test_only_one_live_cluster_is_spawned(self, popen):
        popen.return_value = SimpleNamespace(pid=43210)
        with patch.dict(os.environ, {"RESEARCH_MARKER_DISABLE_Q_AUTOSTART": "0"}), patch(
            "api.task_queue.get_app_data_dir", return_value=Path(self.temp.name)
        ), patch(
            "api.task_queue._pid_is_alive", side_effect=lambda pid: pid == 43210
        ):
            self.assertTrue(task_queue.ensure_qcluster_running())
            self.assertFalse(task_queue.ensure_qcluster_running())

        self.assertEqual(popen.call_count, 1)
        self.assertEqual(
            (Path(self.temp.name) / "qcluster.pid").read_text(encoding="ascii"),
            "43210",
        )

    def test_cluster_stops_after_queue_stays_idle(self):
        sentinel = MagicMock()
        sentinel.is_alive.return_value = True
        cluster = MagicMock(sentinel=sentinel)
        broker = MagicMock()
        broker.queue_size.side_effect = [1, 0, 0]
        broker.lock_size.return_value = 0

        with patch("api.task_queue.get_app_data_dir", return_value=Path(self.temp.name)), patch(
            "django_q.cluster.Cluster", return_value=cluster
        ), patch("django_q.brokers.get_broker", return_value=broker), patch(
            "api.task_queue.time.sleep"
        ), patch("api.task_queue.time.monotonic", side_effect=[10, 16]):
            task_queue.run_qcluster_until_idle(idle_timeout=5)

        cluster.start.assert_called_once_with()
        cluster.stop.assert_called_once_with()
        self.assertFalse((Path(self.temp.name) / "qcluster.pid").exists())
