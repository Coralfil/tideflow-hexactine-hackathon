"""Permission-gated Nemoclaw Retriever with SSRF/path guards and audit logging."""

from __future__ import annotations

import ipaddress
import socket
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from app.config import Settings, _REPO_ROOT
from app.graph.backend import GraphBackend
from app.graph.science import GraphScienceService
from app.models.schemas import (
    AuditDecision,
    AuditEntryView,
    CapabilityName,
    InferenceSource,
    RetrievalArtifactView,
    RetrieverExecuteRequest,
    RetrieverExecuteResponse,
    RetrieverPermissionsUpdateRequest,
    RetrieverPermissionsView,
    format_iso_utc,
)
from app.services.local_worker_client import is_stub_or_invalid_llm_output

CAPABILITY_NAMES: tuple[CapabilityName, ...] = (
    "local_fs_read",
    "repo_git_scan",
    "web_fetch_public",
    "local_llm_ollama",
)

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "169.254.169.254",
        "0.0.0.0",
        "::1",
    }
)

_SENSITIVE_FILENAMES = frozenset({"id_rsa", "id_ed25519", "id_ecdsa", "credentials.json"})
_SENSITIVE_SUFFIXES = frozenset({".pem", ".key", ".pfx", ".p12"})


class PermissionDeniedError(PermissionError):
    """Raised when PermissionGate blocks a retrieval request."""

    def __init__(self, reason: str, audit_entry: AuditEntryView) -> None:
        super().__init__(reason)
        self.reason = reason
        self.audit_entry = audit_entry


class RetrieverExecutionError(RuntimeError):
    """Raised when an allowed external execution step fails cleanly."""


def _is_forbidden_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def _has_traversal_segment(raw_target: str) -> bool:
    for part in PureWindowsPath(raw_target).parts + PurePosixPath(raw_target).parts:
        if part == "..":
            return True
    normalized_slashes = raw_target.replace("\\", "/")
    return any(seg == ".." for seg in normalized_slashes.split("/"))


def _is_sensitive_path(resolved: Path, allowed_root: Path) -> bool:
    try:
        rel_parts = [p.lower() for p in resolved.relative_to(allowed_root).parts]
    except ValueError:
        rel_parts = [p.lower() for p in resolved.parts]

    for part in rel_parts:
        if part == ".git" or part == ".env" or part.startswith(".env."):
            return True
        if part == "secrets":
            return True
    if len(rel_parts) >= 2 and rel_parts[0] == ".testmuai" and rel_parts[1] == "evidence":
        return True
    name_lower = resolved.name.lower()
    if name_lower in _SENSITIVE_FILENAMES or resolved.suffix.lower() in _SENSITIVE_SUFFIXES:
        return True
    return False


class PermissionGate:
    """Default-deny capability manifest and boundary guard for Nemoclaw."""

    def __init__(
        self,
        allowed_paths: list[str] | None = None,
        allowed_domains: list[str] | None = None,
        updated_at: str = "",
    ) -> None:
        self._lock = threading.RLock()
        self._capabilities: dict[CapabilityName, bool] = {
            "local_fs_read": False,
            "repo_git_scan": False,
            "web_fetch_public": False,
            "local_llm_ollama": False,
        }
        self._allowed_paths: list[str] = (
            [str(Path(p).resolve()) for p in allowed_paths]
            if allowed_paths is not None
            else [str(_REPO_ROOT.resolve())]
        )
        self._allowed_domains: list[str] = (
            [d.strip().lower() for d in allowed_domains if d.strip()]
            if allowed_domains is not None
            else []
        )
        self._updated_at = updated_at

    def get_permissions(self) -> RetrieverPermissionsView:
        with self._lock:
            return RetrieverPermissionsView(
                local_fs_read=self._capabilities["local_fs_read"],
                repo_git_scan=self._capabilities["repo_git_scan"],
                web_fetch_public=self._capabilities["web_fetch_public"],
                local_llm_ollama=self._capabilities["local_llm_ollama"],
                allowed_paths=list(self._allowed_paths),
                allowed_domains=list(self._allowed_domains),
                updated_at=self._updated_at,
            )

    def update_permissions(
        self, payload: RetrieverPermissionsUpdateRequest, updated_at: str
    ) -> RetrieverPermissionsView:
        with self._lock:
            for cap in CAPABILITY_NAMES:
                val = getattr(payload, cap)
                if val is not None:
                    self._capabilities[cap] = bool(val)
            if payload.allowed_paths is not None:
                cleaned_paths = [
                    str(Path(p.strip()).resolve())
                    for p in payload.allowed_paths
                    if p.strip()
                ]
                self._allowed_paths = cleaned_paths
            if payload.allowed_domains is not None:
                self._allowed_domains = [
                    d.strip().lower() for d in payload.allowed_domains if d.strip()
                ]
            self._updated_at = updated_at
            return self.get_permissions()

    def _validate_path_target(self, target: str) -> tuple[bool, str, Path | None]:
        if "\x00" in target:
            return False, "Path contains forbidden null byte.", None
        if _has_traversal_segment(target):
            return False, f"Path traversal segment rejected: {target}", None
        if not self._allowed_paths:
            return False, "No allowed_paths configured for filesystem retrieval.", None

        raw_path = Path(target)
        for root_str in self._allowed_paths:
            root = Path(root_str).resolve()
            candidate = raw_path if raw_path.is_absolute() else (root / raw_path)
            try:
                resolved = candidate.resolve(strict=False)
            except OSError as exc:
                return False, f"Invalid path target: {exc}", None
            if resolved.is_relative_to(root):
                if _is_sensitive_path(resolved, root):
                    return False, f"Access to sensitive path blocked: {target}", None
                return True, "Path authorized inside allowed workspace root.", resolved

        return False, f"Target path outside allowed_paths: {target}", None

    def _validate_web_target(
        self, target: str, has_mock_transport: bool = False
    ) -> tuple[bool, str]:
        parsed = urlsplit(target)
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https"}:
            return False, f"Blocked non-public URL scheme: {scheme or 'none'}"
        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            return False, "URL missing valid hostname."
        if (
            hostname in _BLOCKED_HOSTNAMES
            or hostname.endswith(".local")
            or hostname.endswith(".internal")
            or hostname.endswith(".localhost")
        ):
            return False, f"Blocked local or metadata host: {hostname}"

        try:
            ip_literal = ipaddress.ip_address(hostname)
            if _is_forbidden_ip(ip_literal):
                return False, f"Blocked private/loopback/link-local IP: {hostname}"
        except ValueError:
            try:
                infos = socket.getaddrinfo(hostname, parsed.port or (443 if scheme == "https" else 80), type=socket.SOCK_STREAM)
                for info in infos:
                    sock_ip = str(info[4][0]).split("%")[0]
                    resolved_ip = ipaddress.ip_address(sock_ip)
                    if _is_forbidden_ip(resolved_ip):
                        return (
                            False,
                            f"Blocked SSRF DNS resolution to restricted IP {sock_ip} for {hostname}",
                        )
            except OSError:
                if not has_mock_transport:
                    return False, f"Could not verify public DNS resolution for host: {hostname}"

        if self._allowed_domains:
            matched = any(
                hostname == dom or hostname.endswith(f".{dom}")
                for dom in self._allowed_domains
            )
            if not matched:
                return False, f"Domain '{hostname}' not in allowed_domains."

        return True, "Public HTTP(S) target authorized."

    def authorize(
        self,
        capability: str,
        target: str,
        has_mock_transport: bool = False,
    ) -> tuple[bool, str, Path | None]:
        """Validate capability state and target boundary before any side effect."""
        with self._lock:
            if capability not in CAPABILITY_NAMES:
                return False, f"Unknown capability rejected: {capability}", None

            cap_name: CapabilityName = capability  # type: ignore[assignment]
            if not self._capabilities.get(cap_name, False):
                return False, f"Capability '{cap_name}' is disabled by default-deny manifest.", None

            if cap_name in {"local_fs_read", "repo_git_scan"}:
                return self._validate_path_target(target)

            if cap_name == "web_fetch_public":
                ok, reason = self._validate_web_target(
                    target, has_mock_transport=has_mock_transport
                )
                return ok, reason, None

            lowered = target.lower()
            if "file://" in lowered or "\x00" in target:
                return False, "Unsafe target pattern for local_llm_ollama.", None
            return True, "Local LLM synthesis authorized.", None


class NemoclawRetriever:
    """Executes permission-gated retrieval and grounds RetrievalArtifact nodes."""

    def __init__(
        self,
        backend: GraphBackend,
        science: GraphScienceService,
        settings: Settings,
        clock: Callable[[], datetime] | None = None,
        http_transport: httpx.AsyncBaseTransport | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self.backend = backend
        self.science = science
        self.settings = settings
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._http_transport = http_transport
        self._repo_root = (repo_root or _REPO_ROOT).resolve()
        self._audit_lock = threading.RLock()
        self.gate = PermissionGate(
            allowed_paths=[str(self._repo_root)],
            allowed_domains=[],
            updated_at=self._now_iso(),
        )
        self._audit_entries: list[AuditEntryView] = self._load_existing_audit()

    def _now_iso(self) -> str:
        return format_iso_utc(self._clock())

    def _load_existing_audit(self) -> list[AuditEntryView]:
        nodes = self.backend.query_nodes("AuditEntry", limit=2000)
        entries: list[AuditEntryView] = []
        for node in nodes:
            props = node.get("properties") or {}
            verdict_raw = str(props.get("verdict") or props.get("decision") or "DENIED")
            verdict: AuditDecision = "ALLOWED" if verdict_raw == "ALLOWED" else "DENIED"
            entries.append(
                AuditEntryView(
                    id=node["id"],
                    trace_id=str(props.get("trace_id") or ""),
                    service=str(props.get("service") or "nemoclaw-retriever"),
                    capability=str(props.get("capability") or ""),
                    target=str(props.get("target") or ""),
                    verdict=verdict,
                    decision=verdict,
                    reason=str(props.get("reason") or ""),
                    artifact_id=props.get("artifact_id"),
                    timestamp=str(props.get("timestamp") or ""),
                )
            )
        entries.sort(key=lambda e: (e.timestamp, e.id))
        return entries

    def _record_audit(
        self,
        capability: str,
        target: str,
        verdict: AuditDecision,
        reason: str,
        artifact_id: str | None = None,
    ) -> AuditEntryView:
        entry = AuditEntryView(
            id=f"aud_{uuid4().hex[:10]}",
            trace_id=f"trace-{uuid4().hex[:8]}",
            service="nemoclaw-retriever",
            capability=capability,
            target=target,
            verdict=verdict,
            decision=verdict,
            reason=reason.replace("\u2014", "-"),
            artifact_id=artifact_id,
            timestamp=self._now_iso(),
        )
        with self._audit_lock:
            self.backend.upsert_node(
                "AuditEntry",
                {
                    "id": entry.id,
                    "title": f"{entry.verdict} {capability}",
                    "trace_id": entry.trace_id,
                    "service": entry.service,
                    "capability": entry.capability,
                    "target": entry.target,
                    "verdict": entry.verdict,
                    "decision": entry.decision,
                    "reason": entry.reason,
                    "artifact_id": entry.artifact_id,
                    "timestamp": entry.timestamp,
                },
            )
            self._audit_entries.append(entry)
        return entry

    def get_permissions(self) -> RetrieverPermissionsView:
        return self.gate.get_permissions()

    def update_permissions(
        self, payload: RetrieverPermissionsUpdateRequest
    ) -> RetrieverPermissionsView:
        return self.gate.update_permissions(payload, updated_at=self._now_iso())

    def list_audit(self) -> list[AuditEntryView]:
        with self._audit_lock:
            return list(self._audit_entries)

    def _resolve_grounding_target(
        self, project_id: str | None, thought_id: str | None
    ) -> str | None:
        if project_id is not None:
            proj = self.backend.get_node(project_id)
            if proj is None or "Project" not in proj.get("labels", []):
                raise KeyError(f"Project not found: {project_id}")
        if thought_id is not None:
            thought = self.backend.get_node(thought_id)
            if thought is None or "Thought" not in thought.get("labels", []):
                raise KeyError(f"Thought not found: {thought_id}")
        return thought_id or project_id

    def _run_local_fs_read(self, resolved: Path) -> tuple[str, str, str]:
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"Target file not found: {resolved.name}")
        raw_text = resolved.read_text(encoding="utf-8", errors="replace")
        excerpt = raw_text[:1200].replace("\u2014", "-")
        try:
            rel = str(resolved.relative_to(self._repo_root))
        except ValueError:
            rel = str(resolved)
        summary = f"Read {len(raw_text)} characters from {rel}."
        return summary, excerpt, rel

    def _run_repo_git_scan(self, resolved: Path) -> tuple[str, str, str]:
        if not resolved.exists():
            raise FileNotFoundError(f"Scan target not found: {resolved.name}")
        scan_dir = resolved if resolved.is_dir() else resolved.parent
        status_proc = subprocess.run(
            ["git", "-C", str(scan_dir), "status", "--short"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
        log_proc = subprocess.run(
            ["git", "-C", str(scan_dir), "log", "-n", "5", "--oneline"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
        if status_proc.returncode == 0 or log_proc.returncode == 0:
            lines = [
                "Git status:",
                status_proc.stdout.strip() or "(clean working tree)",
                "Recent commits:",
                log_proc.stdout.strip() or "(no commits)",
            ]
            excerpt = "\n".join(lines)[:1200].replace("\u2014", "-")
            summary = f"Scanned git repository at {scan_dir.name}."
            return summary, excerpt, str(scan_dir)

        entries = sorted(
            p.name for p in scan_dir.iterdir() if p.name not in {".git", ".env"}
        )[:40]
        excerpt = "Directory listing:\n" + "\n".join(entries)
        summary = f"Listed {len(entries)} entries under {scan_dir.name}."
        return summary, excerpt[:1200], str(scan_dir)

    async def _run_web_fetch_public(self, target: str) -> tuple[str, str, str]:
        timeout = max(self.settings.local_worker_infer_timeout, 2.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            trust_env=False,
            follow_redirects=False,
            transport=self._http_transport,
        ) as client:
            try:
                resp = await client.get(target)
            except httpx.HTTPError as exc:
                raise RetrieverExecutionError(f"Public fetch failed: {exc}") from exc

        if 300 <= resp.status_code < 400:
            raise PermissionError(
                f"Blocked HTTP redirect ({resp.status_code}) to prevent SSRF bypass."
            )
        if resp.status_code >= 400:
            raise RetrieverExecutionError(
                f"Public fetch returned HTTP {resp.status_code} for {target}"
            )

        excerpt = resp.text[:1200].replace("\u2014", "-")
        summary = f"Fetched HTTP {resp.status_code} ({len(resp.text)} chars) from {target}."
        return summary, excerpt, target

    async def _run_local_llm_ollama(
        self, target: str, query: str | None
    ) -> tuple[str, str, str, InferenceSource]:
        prompt = query.strip() if (query and query.strip()) else target
        if self.settings.local_worker_enabled or self._http_transport is not None:
            timeout = max(self.settings.local_worker_infer_timeout, 1.5)
            async with httpx.AsyncClient(
                timeout=timeout,
                trust_env=False,
                transport=self._http_transport,
            ) as client:
                try:
                    ollama_resp = await client.post(
                        f"{self.settings.local_ollama_url.rstrip('/')}/api/generate",
                        json={
                            "model": self.settings.local_ollama_model,
                            "prompt": prompt,
                            "stream": False,
                        },
                    )
                    if ollama_resp.status_code == 200:
                        data = ollama_resp.json()
                        text = str(data.get("response") or "").strip()
                        if not is_stub_or_invalid_llm_output(text):
                            clean = text[:1200].replace("\u2014", "-")
                            return (
                                f"Synthesized local Ollama response ({self.settings.local_ollama_model}).",
                                clean,
                                self.settings.local_ollama_url,
                                "ollama",
                            )
                except Exception:
                    pass

                try:
                    chat_resp = await client.post(
                        f"{self.settings.local_worker_chat_url.rstrip('/')}/chat/completions",
                        json={
                            "model": "qwen2.5-7b-instruct",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.2,
                        },
                    )
                    if chat_resp.status_code == 200:
                        data = chat_resp.json()
                        choices = data.get("choices") or []
                        if choices:
                            text = str(
                                (choices[0].get("message") or {}).get("content") or ""
                            ).strip()
                            if not is_stub_or_invalid_llm_output(text):
                                clean = text[:1200].replace("\u2014", "-")
                                return (
                                    "Synthesized local worker chat response.",
                                    clean,
                                    self.settings.local_worker_chat_url,
                                    "local_worker",
                                )
                except Exception:
                    pass

        fallback_excerpt = (
            f"Offline deterministic synthesis for '{target}': "
            f"focus on one bounded micro-step and verify output against graph state."
        )
        return (
            "Generated deterministic offline synthesis (local Ollama unavailable).",
            fallback_excerpt,
            "deterministic_fallback",
            "deterministic_fallback",
        )

    async def execute(
        self, payload: RetrieverExecuteRequest
    ) -> RetrieverExecuteResponse:
        """Enforce PermissionGate before execution; persist RetrievalArtifact and AuditEntry."""
        allowed, reason, resolved_path = self.gate.authorize(
            payload.capability,
            payload.target,
            has_mock_transport=self._http_transport is not None,
        )
        if not allowed:
            denied_entry = self._record_audit(
                capability=payload.capability,
                target=payload.target,
                verdict="DENIED",
                reason=reason,
            )
            raise PermissionDeniedError(reason=reason, audit_entry=denied_entry)

        primary_ground_id = self._resolve_grounding_target(
            payload.project_id, payload.thought_id
        )

        inference_source: InferenceSource = "deterministic_fallback"
        if payload.capability == "local_fs_read":
            assert resolved_path is not None
            try:
                summary, excerpt, source_ref = self._run_local_fs_read(resolved_path)
            except FileNotFoundError as exc:
                self._record_audit(
                    capability=payload.capability,
                    target=payload.target,
                    verdict="DENIED",
                    reason=str(exc),
                )
                raise
        elif payload.capability == "repo_git_scan":
            assert resolved_path is not None
            try:
                summary, excerpt, source_ref = self._run_repo_git_scan(resolved_path)
            except FileNotFoundError as exc:
                self._record_audit(
                    capability=payload.capability,
                    target=payload.target,
                    verdict="DENIED",
                    reason=str(exc),
                )
                raise
        elif payload.capability == "web_fetch_public":
            try:
                summary, excerpt, source_ref = await self._run_web_fetch_public(
                    payload.target
                )
            except PermissionError as exc:
                denied_entry = self._record_audit(
                    capability=payload.capability,
                    target=payload.target,
                    verdict="DENIED",
                    reason=str(exc),
                )
                raise PermissionDeniedError(
                    reason=str(exc), audit_entry=denied_entry
                ) from exc
        else:
            summary, excerpt, source_ref, inference_source = (
                await self._run_local_llm_ollama(payload.target, payload.query)
            )

        now_iso = self._now_iso()
        artifact_id = f"ret_{uuid4().hex[:10]}"
        title = f"{payload.capability}: {payload.target}"[:120].replace("\u2014", "-")
        artifact_props: dict[str, Any] = {
            "id": artifact_id,
            "title": title,
            "kind": "RetrievalArtifact",
            "capability": payload.capability,
            "target": payload.target,
            "summary": summary.replace("\u2014", "-"),
            "excerpt": excerpt,
            "source_ref": source_ref,
            "grounded_node_id": primary_ground_id,
            "routed_via_subhub": False,
            "subhub_id": None,
            "inference_source": inference_source,
            "created_at": now_iso,
        }
        self.backend.upsert_node("RetrievalArtifact", artifact_props)

        grounded_edge_id: str | None = None
        routed_via_subhub = False
        subhub_id: str | None = None

        link_targets: list[str] = []
        if payload.thought_id is not None:
            link_targets.append(payload.thought_id)
        if payload.project_id is not None and payload.project_id != payload.thought_id:
            link_targets.append(payload.project_id)

        for target_node_id in link_targets:
            edge, routed, hub = self.science.link_with_hexactine_invariant(
                self.backend,
                artifact_id,
                "GROUNDS",
                target_node_id,
                edge_props={"weight": 1.0},
            )
            if grounded_edge_id is None:
                grounded_edge_id = edge["id"]
            routed_via_subhub = routed_via_subhub or routed
            subhub_id = subhub_id or hub

        if routed_via_subhub or subhub_id is not None:
            self.backend.upsert_node(
                "RetrievalArtifact",
                {
                    "id": artifact_id,
                    "routed_via_subhub": routed_via_subhub,
                    "subhub_id": subhub_id,
                },
            )

        artifact_view = RetrievalArtifactView(
            id=artifact_id,
            title=title,
            label="RetrievalArtifact",
            capability=payload.capability,
            target=payload.target,
            summary=summary.replace("\u2014", "-"),
            excerpt=excerpt,
            source_ref=source_ref,
            grounded_node_id=primary_ground_id,
            routed_via_subhub=routed_via_subhub,
            subhub_id=subhub_id,
            inference_source=inference_source,
            created_at=now_iso,
        )
        audit_entry = self._record_audit(
            capability=payload.capability,
            target=payload.target,
            verdict="ALLOWED",
            reason=reason,
            artifact_id=artifact_id,
        )
        return RetrieverExecuteResponse(
            job_id=f"nemo-{uuid4().hex[:8]}",
            verdict="ALLOWED",
            decision="ALLOWED",
            artifact=artifact_view,
            audit_entry=audit_entry,
            grounded_edge_id=grounded_edge_id,
        )
