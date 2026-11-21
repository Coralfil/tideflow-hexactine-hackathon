from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from tests.e2e._browser_driver import browser_environment_status, run_browser_spec


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
API_URL = os.getenv("TIDEFLOW_API_URL", "http://127.0.0.1:8010").rstrip("/")
UI_URL = os.getenv("TIDEFLOW_UI_URL", "http://127.0.0.1:5173").rstrip("/")
REQUIRE_LIVE = os.getenv("TIDEFLOW_E2E_REQUIRE_LIVE", "").strip().lower() in {"1", "true", "yes"}

EM_DASH = "\u2014"
BANNED_SLOP_WORDS = (
    "delve",
    "tapestry",
    "paradigm",
    "leverage",
    "robust",
    "comprehensive",
    "synergy",
    "seamless",
    "game-changer",
    "unlock the power",
    "nestled",
    "testament",
)
CHATBOT_PHRASES = (
    "certainly!",
    "as an ai",
    "feel free to ask",
    "i hope this helps",
    "sure, let me",
)
VALID_BACKEND_MODES = {"relate", "inprocess", "memory", "neo4j"}
CAPABILITY_KEYS = (
    "local_fs_read",
    "repo_git_scan",
    "web_fetch_public",
    "local_llm_ollama",
)


def make_slug(prefix: str = "e2e") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


@pytest.fixture
def unique_slug() -> str:
    return make_slug()


@pytest.fixture(scope="session")
def workspace_root() -> Path:
    return WORKSPACE_ROOT


@pytest.fixture(scope="session")
def api_url() -> str:
    return API_URL


@pytest.fixture(scope="session")
def ui_url() -> str:
    return UI_URL


@pytest.fixture(scope="session")
def api_client() -> httpx.Client:
    with httpx.Client(base_url=API_URL, timeout=10.0) as client:
        yield client


@pytest.fixture(scope="session")
def require_api(api_client: httpx.Client) -> dict[str, Any]:
    try:
        resp = api_client.get("/api/v1/health", timeout=2.0)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        msg = f"Backend API unreachable at {API_URL}/api/v1/health: {exc}"
        if REQUIRE_LIVE:
            pytest.fail(msg)
        pytest.skip(msg)
    if resp.status_code != 200:
        pytest.fail(f"/api/v1/health returned HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


@pytest.fixture(scope="session")
def require_ui() -> str:
    try:
        resp = httpx.get(UI_URL, timeout=2.0)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        msg = f"Frontend UI unreachable at {UI_URL}: {exc}"
        if REQUIRE_LIVE:
            pytest.fail(msg)
        pytest.skip(msg)
    if resp.status_code != 200:
        pytest.fail(f"UI root {UI_URL} returned HTTP {resp.status_code}")
    return UI_URL


@pytest.fixture(scope="session")
def require_browser(require_ui: str) -> dict[str, Any]:
    status = browser_environment_status()
    if not status["ready"]:
        msg = f"Headless browser runner not ready: {status}"
        if REQUIRE_LIVE:
            pytest.fail(msg)
        pytest.skip(msg)
    return {"ui_url": require_ui, **status}


@pytest.fixture
def browser_runner(require_browser: dict[str, Any]):
    def _run(
        actions: list[dict[str, Any]] | None = None,
        *,
        url: str | None = None,
        viewport: dict[str, int] | None = None,
        reduced_motion: str = "no-preference",
        disable_paint_worklet: bool = False,
        settle_ms: int = 350,
    ) -> dict[str, Any]:
        spec: dict[str, Any] = {
            "url": url or require_browser["ui_url"],
            "actions": actions or [],
            "reducedMotion": reduced_motion,
            "disablePaintWorklet": disable_paint_worklet,
            "settleMs": settle_ms,
        }
        if viewport is not None:
            spec["viewport"] = viewport
        return run_browser_spec(spec)

    return _run


def require_workspace_artifact(relative_path: str, milestone_hint: str) -> Path:
    target = WORKSPACE_ROOT / relative_path
    if target.exists():
        return target
    msg = f"Pending {milestone_hint}: {relative_path} not yet created"
    if REQUIRE_LIVE:
        pytest.fail(msg)
    pytest.skip(msg)


@pytest.fixture
def reset_retriever_permissions(api_client: httpx.Client, require_api: dict[str, Any]):
    baseline = {cap: False for cap in CAPABILITY_KEYS}
    init_resp = api_client.put("/api/v1/retriever/permissions", json=baseline)
    if init_resp.status_code != 404:
        init_resp.raise_for_status()
    try:
        yield baseline
    finally:
        try:
            teardown_resp = api_client.put("/api/v1/retriever/permissions", json=baseline)
            if teardown_resp.status_code != 404:
                teardown_resp.raise_for_status()
        except httpx.HTTPError:
            pass


@pytest.fixture
def created_schedule_blocks(api_client: httpx.Client, require_api: dict[str, Any]):
    created_ids: list[str] = []
    yield created_ids
    for block_id in created_ids:
        try:
            api_client.delete(f"/api/v1/schedule/blocks/{block_id}")
        except httpx.HTTPError:
            pass


# --- Strict Contract Validators & Minor Alias Extractors ---


def unwrap_thought(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("thought"), dict):
        return payload["thought"]
    return payload


def extract_id(obj: dict[str, Any]) -> str:
    target = unwrap_thought(obj)
    val = target.get("id") or target.get("node_id") or target.get("project_id") or target.get("block_id")
    assert isinstance(val, str) and val.strip(), f"Expected non-empty id field in {obj}"
    return val


def unwrap_list(payload: Any, *extra_keys: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "projects", "thoughts", "blocks", "audit", "entries", "prompts", "nodes", *extra_keys):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    raise AssertionError(f"Expected list or wrapped list payload, got: {type(payload).__name__} {payload}")


def extract_edges(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    if "edges" in snapshot and isinstance(snapshot["edges"], list):
        return snapshot["edges"]
    if "links" in snapshot and isinstance(snapshot["links"], list):
        return snapshot["links"]
    raise AssertionError(f"Expected 'edges' or 'links' list in snapshot keys: {list(snapshot.keys())}")


def extract_audit_verdict(entry: dict[str, Any]) -> str:
    val = entry.get("verdict") or entry.get("decision") or entry.get("status") or entry.get("outcome")
    assert isinstance(val, str) and val.strip(), f"Expected audit verdict in {entry}"
    return val.upper()


def assert_health_contract(data: dict[str, Any]) -> None:
    required = {"status", "backend_mode", "relate_available", "neo4j_available", "active_cadence"}
    missing = required - set(data.keys())
    assert not missing, f"Missing health keys: {missing} in {data}"
    assert isinstance(data["relate_available"], bool), f"relate_available must be bool: {data}"
    assert isinstance(data["neo4j_available"], bool), f"neo4j_available must be bool: {data}"
    assert str(data["backend_mode"]).lower() in VALID_BACKEND_MODES, f"Unexpected backend_mode: {data['backend_mode']}"
    assert isinstance(data["active_cadence"], str) and data["active_cadence"].strip()


def assert_triage_contract(data: dict[str, Any]) -> None:
    required = {"now", "next", "parked_count", "overwhelm_index", "recommendation"}
    missing = required - set(data.keys())
    assert not missing, f"Missing triage keys: {missing} in {data}"
    assert isinstance(data["now"], list) and len(data["now"]) <= 1, f"Now cap exceeded: {data['now']}"
    assert isinstance(data["next"], list) and len(data["next"]) <= 2, f"Next cap exceeded: {data['next']}"
    assert isinstance(data["parked_count"], int) and data["parked_count"] >= 0
    assert isinstance(data["overwhelm_index"], (int, float))
    assert 0.0 <= float(data["overwhelm_index"]) <= 1.0, f"overwhelm_index out of bounds: {data['overwhelm_index']}"
    assert isinstance(data["recommendation"], str) and data["recommendation"].strip()


def assert_permissions_contract(data: dict[str, Any]) -> None:
    for key in CAPABILITY_KEYS:
        assert key in data, f"Missing capability key {key} in {data}"
        assert isinstance(data[key], bool), f"Capability {key} must be bool: {data[key]}"


def find_slop_matches(text: str) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for word in BANNED_SLOP_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            hits.append(word)
    return hits


def find_chatbot_phrases(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in CHATBOT_PHRASES if phrase in lowered]


def assert_zero_em_dashes(text: str, source_label: str) -> None:
    assert EM_DASH not in text, f"Found forbidden U+2014 em dash in {source_label}"


def assert_no_server_errors(browser_result: dict[str, Any]) -> None:
    assert not browser_result["pageErrors"], f"Uncaught pageerror(s): {browser_result['pageErrors']}"
    bad_responses = [r for r in browser_result["responses"] if r["status"] >= 500]
    assert not bad_responses, f"HTTP >=500 response(s): {bad_responses}"
