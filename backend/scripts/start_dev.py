"""Start the local API and report worker as supervised child processes.

This launcher is intentionally local-development-only. Production keeps using
the separate API and worker commands defined by the deployment configuration.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Callable, Sequence


BACKEND_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ChildSpec:
    label: str
    command: tuple[str, ...]


def build_child_specs(
    *,
    python_executable: str | None = None,
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = True,
) -> tuple[ChildSpec, ChildSpec]:
    """Build commands with the interpreter that launched this supervisor."""

    python = python_executable or sys.executable
    api_command = [
        python,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        api_command.append("--reload")

    return (
        ChildSpec("api", tuple(api_command)),
        ChildSpec("worker", (python, "scripts/report_worker.py")),
    )


def format_command(command: Sequence[str]) -> str:
    """Return a copy/paste-friendly representation without executing it."""

    return subprocess.list2cmdline(command)


def _forward_output(label: str, stream: IO[str]) -> None:
    for line in iter(stream.readline, ""):
        print(f"[{label}] {line}", end="", flush=True)
    stream.close()


def terminate_children(
    children: Sequence[subprocess.Popen[str]], *, timeout: float = 5.0
) -> None:
    """Best-effort shutdown of every child, escalating to kill after timeout."""

    running = [child for child in children if child.poll() is None]
    for child in running:
        child.terminate()

    for child in running:
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=timeout)


def supervise(
    specs: Sequence[ChildSpec],
    *,
    cwd: Path = BACKEND_ROOT,
    poll_interval: float = 0.1,
    popen_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
) -> int:
    """Run all children until interrupted or until any child exits."""

    children: list[subprocess.Popen[str]] = []
    labels: dict[int, str] = {}
    try:
        for spec in specs:
            print(f"[dev] starting {spec.label}: {format_command(spec.command)}", flush=True)
            child = popen_factory(
                spec.command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            children.append(child)
            labels[id(child)] = spec.label
            if child.stdout is not None:
                threading.Thread(
                    target=_forward_output,
                    args=(spec.label, child.stdout),
                    daemon=True,
                ).start()

        while True:
            for child in children:
                return_code = child.poll()
                if return_code is not None:
                    label = labels[id(child)]
                    print(
                        f"[dev] {label} exited unexpectedly with code {return_code}; "
                        "stopping the remaining process.",
                        file=sys.stderr,
                        flush=True,
                    )
                    return return_code if return_code != 0 else 1
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[dev] shutdown requested; stopping API and worker.", flush=True)
        return 130
    except OSError as exc:
        print(f"[dev] failed to start child process: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        terminate_children(children)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the local FastAPI server and report worker together."
    )
    parser.add_argument("--host", default="0.0.0.0", help="Uvicorn bind host")
    parser.add_argument("--port", type=int, default=8000, help="Uvicorn bind port")
    parser.add_argument(
        "--no-reload", action="store_true", help="Disable Uvicorn auto-reload"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print child commands without starting either process",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    specs = build_child_specs(
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
    )
    if args.dry_run:
        print(f"[dev] working directory: {BACKEND_ROOT}")
        for spec in specs:
            print(f"[dev] {spec.label}: {format_command(spec.command)}")
        print("[dev] dry run complete; no child processes were started.")
        return 0
    return supervise(specs)


if __name__ == "__main__":
    raise SystemExit(main())
