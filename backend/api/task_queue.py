"""Django-Q enqueue helpers with an on-demand worker lifecycle."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from api.utils import get_app_data_dir


QCLUSTER_IDLE_TIMEOUT_SECONDS = max(
    5, int(os.getenv("RESEARCH_MARKER_Q_IDLE_TIMEOUT", "60"))
)
_QCLUSTER_PID_FILENAME = "qcluster.pid"


def _pid_path() -> Path:
    return Path(get_app_data_dir()) / _QCLUSTER_PID_FILENAME


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="ascii").strip())
    except (OSError, TypeError, ValueError):
        return None


def _remove_owned_pid_file(pid: int) -> None:
    path = _pid_path()
    if _read_pid(path) != pid:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _worker_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "qcluster"]
    backend_root = Path(__file__).resolve().parent.parent
    return [sys.executable, str(backend_root / "main.py"), "qcluster"]


def ensure_qcluster_running() -> bool:
    """Start the single on-demand cluster if another live cluster does not own it."""
    if os.environ.get("RESEARCH_MARKER_DISABLE_Q_AUTOSTART") == "1":
        return False
    if os.environ.get("RESEARCH_MARKER_QCLUSTER_CHILD") == "1":
        return False

    path = _pid_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    for _attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            existing_pid = _read_pid(path)
            if existing_pid is not None and _pid_is_alive(existing_pid):
                return False
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue

        try:
            # The temporary owner prevents concurrent request threads from spawning
            # more than one cluster before Popen returns.
            os.write(fd, str(os.getpid()).encode("ascii"))
        finally:
            os.close(fd)

        try:
            env = os.environ.copy()
            env["RESEARCH_MARKER_QCLUSTER_CHILD"] = "1"
            env["RESEARCH_MARKER_QCLUSTER_PARENT_PID"] = str(os.getpid())
            process = subprocess.Popen(
                _worker_command(),
                env=env,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            path.write_text(str(process.pid), encoding="ascii")
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            return True
        except Exception:
            _remove_owned_pid_file(os.getpid())
            raise
    return False


def enqueue_task(*args: Any, **kwargs: Any) -> str:
    """Queue a task and wake the on-demand worker after the ORM row is committed."""
    from django_q.tasks import async_task
    from django.db import connection, transaction

    task_id = async_task(*args, **kwargs)
    if connection.in_atomic_block:
        transaction.on_commit(ensure_qcluster_running)
    else:
        ensure_qcluster_running()
    return task_id


def run_qcluster_until_idle(
    *, idle_timeout: int = QCLUSTER_IDLE_TIMEOUT_SECONDS
) -> None:
    """Run one Django-Q cluster until its ORM queue has stayed empty."""
    from django_q.brokers import get_broker
    from django_q.cluster import Cluster

    pid = os.getpid()
    path = _pid_path()
    owner = _read_pid(path)
    parent_pid = int(os.environ.get("RESEARCH_MARKER_QCLUSTER_PARENT_PID", "0") or 0)
    if owner == parent_pid:
        deadline = time.monotonic() + 5
        while owner == parent_pid and time.monotonic() < deadline:
            time.sleep(0.01)
            owner = _read_pid(path)
    if owner not in (None, pid) and _pid_is_alive(owner):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid), encoding="ascii")

    cluster = Cluster()
    broker = get_broker()
    idle_since: float | None = None
    try:
        cluster.start()
        while cluster.sentinel is not None and cluster.sentinel.is_alive():
            queued = int(broker.queue_size() or 0)
            locked = int(broker.lock_size() or 0)
            if queued or locked:
                idle_since = None
            elif idle_since is None:
                idle_since = time.monotonic()
            elif time.monotonic() - idle_since >= idle_timeout:
                break
            time.sleep(1)
    finally:
        if cluster.sentinel is not None and cluster.sentinel.is_alive():
            cluster.stop()
        _remove_owned_pid_file(pid)
