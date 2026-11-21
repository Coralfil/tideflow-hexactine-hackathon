from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


E2E_DIR = Path(__file__).resolve().parent
RUNNER_SCRIPT = E2E_DIR / "_playwright_runner.mjs"


def find_node_playwright_dir() -> Path | None:
    """Resolve cached Node Playwright module path without touching app dependencies."""
    env_override = os.getenv("PLAYWRIGHT_NODE_MODULES", "").strip()
    if env_override:
        candidate = Path(env_override)
        if (candidate / "playwright").exists():
            return candidate
        if candidate.name == "playwright" and candidate.exists():
            return candidate.parent

    local_nm = E2E_DIR / "node_modules"
    if (local_nm / "playwright").exists():
        return local_nm

    local_app_data = os.getenv("LOCALAPPDATA", "")
    if local_app_data:
        npx_root = Path(local_app_data) / "npm-cache" / "_npx"
        if npx_root.exists():
            matches = sorted(
                npx_root.glob("*/node_modules/playwright"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if matches:
                return matches[0].parent
    return None


def find_chromium_binary() -> Path | None:
    """Locate local Chromium or Chrome executable for headless verification."""
    env_chrome = os.getenv("KANE_CLI_CHROME_PATH", "").strip()
    if env_chrome and Path(env_chrome).exists():
        return Path(env_chrome)

    local_app_data = os.getenv("LOCALAPPDATA", "")
    candidates: list[Path] = []
    if local_app_data:
        ms_pw = Path(local_app_data) / "ms-playwright"
        if ms_pw.exists():
            candidates.extend(sorted(ms_pw.glob("chromium-*/chrome-win64/chrome.exe"), reverse=True))
    candidates.extend(
        [
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def browser_environment_status() -> dict[str, Any]:
    node_bin = shutil.which("node")
    pw_dir = find_node_playwright_dir()
    chrome_bin = find_chromium_binary()
    python_pw = False
    try:
        import importlib.util

        python_pw = importlib.util.find_spec("playwright") is not None
    except Exception:
        python_pw = False
    return {
        "node_available": bool(node_bin),
        "node_bin": node_bin,
        "node_playwright_dir": str(pw_dir) if pw_dir else None,
        "chromium_binary": str(chrome_bin) if chrome_bin else None,
        "python_playwright": python_pw,
        "ready": bool((node_bin and pw_dir and chrome_bin) or (python_pw and chrome_bin)),
    }


def run_browser_spec(spec: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    """Execute a headless Chromium scenario via zero-install Node Playwright."""
    node_bin = shutil.which("node")
    pw_dir = find_node_playwright_dir()
    chrome_bin = find_chromium_binary()

    if not node_bin:
        raise RuntimeError("Node.js binary not found on PATH")
    if not pw_dir:
        raise RuntimeError(
            "Node Playwright package not found in PLAYWRIGHT_NODE_MODULES, tests/e2e/node_modules, or npm-cache/_npx"
        )
    if not chrome_bin:
        raise RuntimeError("Chromium binary not found in ms-playwright or KANE_CLI_CHROME_PATH")

    env = os.environ.copy()
    env["NODE_PATH"] = str(pw_dir)
    env["PLAYWRIGHT_NODE_MODULES"] = str(pw_dir)
    env["KANE_CLI_CHROME_PATH"] = str(chrome_bin)

    proc = subprocess.run(
        [node_bin, str(RUNNER_SCRIPT)],
        input=json.dumps(spec),
        text=True,
        capture_output=True,
        env=env,
        timeout=timeout,
        encoding="utf-8",
    )
    stdout = (proc.stdout or "").strip()
    if not stdout:
        raise RuntimeError(
            f"Browser runner produced empty stdout (exit={proc.returncode}): {(proc.stderr or '').strip()}"
        )
    data = json.loads(stdout)
    if proc.returncode != 0 or not data.get("ok"):
        raise AssertionError(
            f"Browser run failed (exit={proc.returncode}): {data.get('error') or proc.stderr}"
        )
    return data
