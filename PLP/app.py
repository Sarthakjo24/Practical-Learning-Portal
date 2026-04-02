from __future__ import annotations

import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
ENV_FILE = BACKEND_DIR / ".env"


def read_env_value(key: str, default: str) -> str:
    if not ENV_FILE.exists():
        return default

    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.*)\s*$")
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        value = match.group(1).strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        return value
    return default


def resolve_backend_port() -> int:
    frontend_base_url = read_env_value("FRONTEND_BASE_URL", "http://localhost:5180")
    parsed = urlparse(frontend_base_url)
    if parsed.port:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    return 80


def venv_python() -> Path:
    if os.name == "nt":
        candidate = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT_DIR / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def npm_command() -> str:
    explicit = "npm.cmd" if os.name == "nt" else "npm"
    if shutil.which(explicit):
        return explicit
    fallback = shutil.which("npm")
    if fallback:
        return fallback
    raise RuntimeError("npm is not available on PATH. Install Node.js before running app.py.")


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def run_command(command: list[str], cwd: Path, label: str) -> None:
    print(f"[launcher] {label}...")
    subprocess.run(command, cwd=str(cwd), check=True)


def ensure_windows_service(service_name: str, port: int) -> None:
    if is_port_open(port):
        print(f"[launcher] {service_name} already available on port {port}.")
        return

    if os.name != "nt":
        raise RuntimeError(f"Port {port} is unavailable. Start the required service before running app.py.")

    print(f"[launcher] Starting Windows service {service_name}...")
    completed = subprocess.run(
        ["net", "start", service_name],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        shell=False,
    )

    if completed.returncode != 0 and "service has already been started" not in completed.stdout.lower():
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        raise RuntimeError(
            f"Could not start {service_name}. "
            f"{stdout or stderr or 'Run PowerShell as Administrator or start the service manually.'}"
        )

    deadline = time.time() + 12
    while time.time() < deadline:
        if is_port_open(port):
            print(f"[launcher] {service_name} is ready on port {port}.")
            return
        time.sleep(0.5)

    raise RuntimeError(f"{service_name} did not start listening on port {port}.")


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]
    thread: threading.Thread


def _stream_output(name: str, stream) -> None:
    try:
        for line in iter(stream.readline, ""):
            text = line.rstrip()
            if text:
                print(f"[{name}] {text}")
    finally:
        stream.close()


def start_process(name: str, command: list[str], cwd: Path) -> ManagedProcess:
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    thread = threading.Thread(target=_stream_output, args=(name, process.stdout), daemon=True)
    thread.start()
    return ManagedProcess(name=name, process=process, thread=thread)


def terminate_processes(processes: list[ManagedProcess]) -> None:
    for managed in processes:
        if managed.process.poll() is None:
            managed.process.terminate()

    deadline = time.time() + 8
    while time.time() < deadline:
        if all(managed.process.poll() is not None for managed in processes):
            break
        time.sleep(0.2)

    for managed in processes:
        if managed.process.poll() is None:
            managed.process.kill()


def main() -> int:
    python_exec = str(venv_python())
    backend_port = resolve_backend_port()

    if not Path(python_exec).exists():
        raise RuntimeError("Python executable for the project could not be resolved.")

    if is_port_open(backend_port):
        raise RuntimeError(
            f"Port {backend_port} is already in use. Stop the existing process or change FRONTEND_BASE_URL in backend/.env."
        )

    ensure_windows_service("MySQL80", 3306)
    ensure_windows_service("Memurai", 6379)

    run_command([npm_command(), "run", "build"], FRONTEND_DIR, "Building frontend")

    processes: list[ManagedProcess] = []
    try:
        processes.append(
            start_process(
                "celery",
                [
                    python_exec,
                    "-m",
                    "celery",
                    "-A",
                    "app.workers.celery_app.celery_app",
                    "worker",
                    "--loglevel=INFO",
                    "--pool=solo",
                ],
                BACKEND_DIR,
            )
        )
        processes.append(
            start_process(
                "api",
                [
                    python_exec,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(backend_port),
                    "--app-dir",
                    ".",
                ],
                BACKEND_DIR,
            )
        )

        print()
        print(f"[launcher] Practical Learning Portal is starting on http://localhost:{backend_port}")
        print(f"[launcher] FastAPI docs: http://localhost:{backend_port}/docs")
        print("[launcher] Press Ctrl+C to stop the API and worker.")
        print()

        while True:
            for managed in processes:
                exit_code = managed.process.poll()
                if exit_code is not None:
                    raise RuntimeError(f"{managed.name} exited unexpectedly with code {exit_code}.")
            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print("[launcher] Stopping Practical Learning Portal...")
        terminate_processes(processes)
        return 0
    except Exception:
        terminate_processes(processes)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[launcher] {exc}", file=sys.stderr)
        raise SystemExit(1)
