from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

from scripts import start_dev


class FakeProcess:
    def __init__(self, poll_results: list[int | None]) -> None:
        self.stdout = io.StringIO("")
        self._poll_results = poll_results
        self._last_result: int | None = None
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        if self._poll_results:
            self._last_result = self._poll_results.pop(0)
        return self._last_result

    def terminate(self) -> None:
        self.terminated = True
        self._last_result = 0

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        return self._last_result or 0

    def kill(self) -> None:
        self.killed = True
        self._last_result = -9


def test_build_child_specs_use_active_interpreter() -> None:
    api, worker = start_dev.build_child_specs(host="127.0.0.1", port=8123)

    assert api.command == (
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8123",
        "--reload",
    )
    assert worker.command == (sys.executable, "scripts/report_worker.py")


def test_dry_run_prints_commands_without_starting_children(
    monkeypatch, capsys
) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("dry-run must not start a child process")

    monkeypatch.setattr(start_dev.subprocess, "Popen", fail_if_called)

    assert start_dev.main(["--dry-run", "--host", "127.0.0.1", "--port", "8123"]) == 0

    output = capsys.readouterr().out
    assert "[dev] api:" in output
    assert "app.main:app" in output
    assert "[dev] worker:" in output
    assert "scripts/report_worker.py" in output
    assert "no child processes were started" in output


def test_child_output_is_prefixed(capsys) -> None:
    stream = io.StringIO("ready\nnext line\n")

    start_dev._forward_output("worker", stream)

    assert capsys.readouterr().out == "[worker] ready\n[worker] next line\n"


def test_unexpected_child_exit_stops_remaining_child(monkeypatch, capsys) -> None:
    api = FakeProcess([7])
    worker = FakeProcess([None, None])
    created = iter((api, worker))
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_popen(command, *, cwd, **kwargs):
        del kwargs
        calls.append((command, cwd))
        return next(created)

    monkeypatch.setattr(start_dev.threading.Thread, "start", lambda self: None)
    specs = start_dev.build_child_specs(python_executable="python-test")

    result = start_dev.supervise(specs, popen_factory=fake_popen, poll_interval=0)

    assert result == 7
    assert [command for command, _ in calls] == [specs[0].command, specs[1].command]
    assert all(cwd == start_dev.BACKEND_ROOT for _, cwd in calls)
    assert worker.terminated is True
    assert "api exited unexpectedly with code 7" in capsys.readouterr().err


def test_partial_start_failure_cleans_up_started_child(capsys) -> None:
    api = FakeProcess([None, None])
    call_count = 0

    def fake_popen(command, **kwargs):
        nonlocal call_count
        del command, kwargs
        call_count += 1
        if call_count == 2:
            raise OSError("worker launch failed")
        return api

    result = start_dev.supervise(
        start_dev.build_child_specs(python_executable="python-test"),
        popen_factory=fake_popen,
    )

    assert result == 1
    assert api.terminated is True
    assert "worker launch failed" in capsys.readouterr().err


def test_cleanup_escalates_to_kill_after_timeout() -> None:
    class StubbornProcess(FakeProcess):
        def wait(self, timeout: float | None = None) -> int:
            if not self.killed:
                raise subprocess.TimeoutExpired("worker", timeout)
            return -9

    child = StubbornProcess([None])

    start_dev.terminate_children([child], timeout=0.01)

    assert child.terminated is True
    assert child.killed is True
