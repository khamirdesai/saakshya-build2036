"""Install/start/stop the original app as per-user macOS background services.

Runtime files live in Application Support so background Python does not need
access to the protected Desktop folder. No system firewall or privacy settings
are changed. Existing ngrok authentication stays in its own private config.
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
BASE = HOME / "Library/Application Support/SAAKSHYA Build2036"
APP = BASE / "app"
ENV = BASE / "env"
LOGS = HOME / "Library/Logs/SAAKSHYA-Build2036"
AGENTS = HOME / "Library/LaunchAgents"
PREFIX = "com.khamirdesai.saakshya-build2036."
SUFFIXES = ("server", "tunnel", "awake")


def control(action: str, suffix: str):
    label = PREFIX + suffix
    target = f"gui/{os.getuid()}"
    arguments = ["launchctl", action, target + "/" + label]
    if action == "bootstrap":
        arguments = ["launchctl", action, target, str(AGENTS / (label + ".plist"))]
    return subprocess.run(arguments, capture_output=True, text=True)


def install():
    for path in (BASE, APP, LOGS, AGENTS):
        path.mkdir(parents=True, exist_ok=True)
    for suffix in SUFFIXES:
        control("bootout", suffix)
    for name in ("src", "ui", "config", "deployment"):
        shutil.copytree(ROOT / name, APP / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(ROOT / "pyproject.toml", APP / "pyproject.toml")
    uv = shutil.which("uv")
    ngrok = shutil.which("ngrok")
    if not uv or not ngrok:
        raise SystemExit("Install uv and configure ngrok before installing the PC server.")
    if not (ENV / "bin/python").is_file():
        subprocess.run([uv, "venv", "--python", "3.12", str(ENV)], check=True)
    subprocess.run([uv, "pip", "install", "--python", str(ENV / "bin/python"), "-e", str(APP)], check=True)
    common = {"WorkingDirectory": str(APP), "RunAtLoad": True,
              "KeepAlive": True, "ThrottleInterval": 10}
    public_config = ROOT / "deployment/public-url.json"
    public_url = json.loads(public_config.read_text()).get("application_url", "") if public_config.exists() else ""
    tunnel_args = [ngrok, "http", "http://127.0.0.1:8086", "--log", "stdout", "--log-format", "json"]
    if public_url:
        tunnel_args += ["--url", public_url]
    services = {
        "server": {"ProgramArguments": [str(ENV / "bin/python"), "-m", "uvicorn", "deployment.app:build", "--factory", "--host", "127.0.0.1", "--port", "8086", "--workers", "1"],
                   "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/bin:/bin", "PYTHONPATH": str(APP / "src") + ":" + str(APP), "SAAKSHYA_DEMO_RUNTIME": str(BASE / "runtime")}},
        "tunnel": {"ProgramArguments": tunnel_args},
        "awake": {"ProgramArguments": ["/usr/bin/caffeinate", "-is"]},
    }
    for suffix, settings in services.items():
        label = PREFIX + suffix
        config = {"Label": label, **common, **settings,
                  "StandardOutPath": str(LOGS / (suffix + ".log")),
                  "StandardErrorPath": str(LOGS / (suffix + ".log"))}
        with (AGENTS / (label + ".plist")).open("wb") as f:
            plistlib.dump(config, f)
    start()


def start():
    for suffix in SUFFIXES:
        result = control("bootstrap", suffix)
        if result.returncode:
            status = control("print", suffix)
            if status.returncode:
                raise SystemExit(f"Could not start {suffix}: {result.stderr.strip()}")
    print("Started original app on localhost:8086, HTTPS tunnel and awake service.")


def stop():
    for suffix in ("tunnel", "server", "awake"):
        control("bootout", suffix)
    print("Stopped this submission's app, tunnel and awake service.")


def status():
    for suffix in SUFFIXES:
        result = control("print", suffix)
        states = [line.strip() for line in result.stdout.splitlines()
                  if line.strip().startswith(("state =", "pid =", "last exit code ="))]
        print(suffix + ": " + ("; ".join(states[:3]) if states else "not loaded"))
    try:
        with urlopen("http://127.0.0.1:4040/api/tunnels", timeout=5) as response:
            tunnels = json.load(response)
        for tunnel in tunnels.get("tunnels", []):
            if tunnel.get("proto") == "https":
                print("Public application: " + tunnel["public_url"])
    except Exception:
        print("Tunnel URL is not available yet. See " + str(LOGS / "tunnel.log"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "start", "stop", "status"])
    args = parser.parse_args()
    {"install": install, "start": start, "stop": stop, "status": status}[args.action]()
