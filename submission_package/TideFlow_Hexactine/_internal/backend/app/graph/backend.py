"""Dual-mode GraphBackend protocol and Relate / InProcess / Neo4j drivers."""

from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from collections import deque
from datetime import date, datetime, time as dt_time
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from app.config import Settings
from app.models.schemas import BackendMode

try:
    import relate  # type: ignore[import-untyped]
except ImportError:
    relate = None  # type: ignore[assignment]

try:
    from neo4j import GraphDatabase  # type: ignore[import-untyped]
    from neo4j.exceptions import (  # type: ignore[import-untyped]
        AuthError,
        ClientError,
        ConnectionAcquisitionTimeoutError,
        DatabaseUnavailable,
        DriverError,
        Neo4jError,
        ServiceUnavailable,
    )
except ImportError:
    GraphDatabase = None  # type: ignore[assignment]
    AuthError = ClientError = ConnectionAcquisitionTimeoutError = Exception  # type: ignore[misc,assignment]
    DatabaseUnavailable = DriverError = Neo4jError = ServiceUnavailable = Exception  # type: ignore[misc,assignment]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_JSON_PREFIX = "__json__:"
_LOCK_RETRY_DELAYS = (0.05, 0.15, 0.35)


class BackendUnavailableError(RuntimeError):
    """Raised when a configured graph backend cannot be initialized or reached."""


def _validate_identifier(value: str, kind: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid {kind} identifier: {value!r}")
    return value


def _serialize_prop_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date, dt_time)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        items = [_serialize_prop_value(v) for v in value if v is not None]
        if all(isinstance(v, str) for v in items):
            return items
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in items):
            return items
        if all(isinstance(v, bool) for v in items):
            return items
        return _JSON_PREFIX + json.dumps(items, sort_keys=True)
    if isinstance(value, dict):
        return _JSON_PREFIX + json.dumps(value, sort_keys=True, default=str)
    return str(value)


def _deserialize_prop_value(value: Any) -> Any:
    if value is None:
        return None
    if relate is not None and isinstance(value, getattr(relate, "Temporal", ())):
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
    if isinstance(value, (datetime, date, dt_time)):
        return value.isoformat()
    if isinstance(value, str) and value.startswith(_JSON_PREFIX):
        raw = value[len(_JSON_PREFIX) :]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    if isinstance(value, list):
        return [_deserialize_prop_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _deserialize_prop_value(v) for k, v in value.items()}
    return value


def _sanitize_props_for_cypher(props: dict[str, Any]) -> dict[str, Any]:
    return {str(k): _serialize_prop_value(v) for k, v in props.items()}


def _normalize_props_from_store(props: dict[str, Any] | None) -> dict[str, Any]:
    if not props:
        return {}
    return {
        str(k): _deserialize_prop_value(v)
        for k, v in props.items()
        if v is not None
    }


def _strip_internal_labels(labels: list[str]) -> list[str]:
    filtered = [str(lbl) for lbl in labels if lbl != "TideNode"]
    return filtered if filtered else [str(lbl) for lbl in labels]


def _make_edge_id(src_id: str, rel_type: str, dst_id: str) -> str:
    return f"{src_id}->{rel_type}->{dst_id}"


def _node_recency_sort_key(node: dict[str, Any]) -> tuple[int, float, str]:
    props = node.get("properties") or {}
    raw_ts = (
        props.get("updated_at")
        or props.get("recorded_at")
        or props.get("closed_at")
        or props.get("created_at")
        or props.get("captured_at")
        or props.get("valid_from")
        or ""
    )
    if isinstance(raw_ts, str) and raw_ts:
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).timestamp()
            return (0, -ts, str(node["id"]))
        except ValueError:
            pass
    return (1, 0.0, str(node["id"]))


def _select_default_subgraph_ids(
    all_nodes: dict[str, dict[str, Any]],
    all_edges: list[dict[str, Any]],
    limit: int,
) -> set[str]:
    if limit <= 0 or not all_nodes:
        return set()
    if len(all_nodes) <= limit:
        return set(all_nodes.keys())

    adj: dict[str, set[str]] = {nid: set() for nid in all_nodes}
    for edge in all_edges:
        src = str(edge.get("source") or "")
        dst = str(edge.get("target") or "")
        if src in all_nodes and dst in all_nodes:
            adj[src].add(dst)
            adj[dst].add(src)

    ranked = sorted(
        all_nodes.keys(),
        key=lambda nid: _node_recency_sort_key(all_nodes[nid]),
    )
    selected_set: set[str] = set()
    for nid in ranked:
        if len(selected_set) >= limit:
            break
        selected_set.add(nid)
        neighbors = sorted(
            adj.get(nid, set()),
            key=lambda x: _node_recency_sort_key(all_nodes[x]),
        )[:4]
        for nbr in neighbors:
            if len(selected_set) >= limit:
                break
            selected_set.add(nbr)
    return selected_set


@runtime_checkable
class GraphBackend(Protocol):
    """Unified graph storage contract for InProcess, Relate, and Neo4j drivers."""

    @property
    def backend_name(self) -> BackendMode: ...

    def upsert_node(self, label: str, props: dict[str, Any]) -> dict[str, Any]: ...

    def upsert_edge(
        self,
        src_id: str,
        rel_type: str,
        dst_id: str,
        props: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def get_subgraph(
        self, focus_id: str | None = None, limit: int = 200
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...

    def query_nodes(
        self,
        label: str,
        filters: dict[str, Any] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]: ...

    def get_node(self, node_id: str) -> dict[str, Any] | None: ...

    def get_edges(
        self,
        node_id: str | None = None,
        rel_type: str | None = None,
        direction: Literal["out", "in", "both"] = "both",
        limit: int = 2000,
    ) -> list[dict[str, Any]]: ...

    def get_node_degree(
        self, node_id: str, excluded_rel_types: set[str] | None = None
    ) -> int: ...

    def delete_node(self, node_id: str) -> bool: ...

    def close(self) -> None: ...


class InProcessGraphDriver:
    """Thread-safe zero-dependency in-process graph driver for CI and fallback."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: dict[tuple[str, str, str], dict[str, Any]] = {}

    @property
    def backend_name(self) -> BackendMode:
        return "inprocess"

    def upsert_node(self, label: str, props: dict[str, Any]) -> dict[str, Any]:
        _validate_identifier(label, "label")
        working = dict(props)
        extra_labels = [
            _validate_identifier(lbl, "label")
            for lbl in working.pop("_extra_labels", [])
        ]
        node_id = str(working.get("id") or "").strip()
        if not node_id:
            raise ValueError("Node props must include a non-empty 'id'")
        working["id"] = node_id

        with self._lock:
            existing = self._nodes.get(node_id)
            if existing is None:
                merged_props = {
                    str(k): _deserialize_prop_value(v)
                    for k, v in working.items()
                    if v is not None
                }
                labels = list(dict.fromkeys([label, *extra_labels]))
                record = {"id": node_id, "labels": labels, "properties": merged_props}
                self._nodes[node_id] = record
            else:
                merged_props = dict(existing["properties"])
                for k, v in working.items():
                    if v is None:
                        merged_props.pop(str(k), None)
                    else:
                        merged_props[str(k)] = _deserialize_prop_value(v)
                labels = list(dict.fromkeys([*existing["labels"], label, *extra_labels]))
                existing["labels"] = labels
                existing["properties"] = merged_props
                record = existing
            return {
                "id": record["id"],
                "labels": list(record["labels"]),
                "properties": dict(record["properties"]),
            }

    def upsert_edge(
        self,
        src_id: str,
        rel_type: str,
        dst_id: str,
        props: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _validate_identifier(rel_type, "relationship type")
        with self._lock:
            if src_id not in self._nodes:
                raise KeyError(f"Source node not found: {src_id}")
            if dst_id not in self._nodes:
                raise KeyError(f"Target node not found: {dst_id}")
            key = (src_id, rel_type, dst_id)
            existing = self._edges.get(key)
            incoming = dict(props or {})
            if existing is None:
                merged_props = {
                    str(k): _deserialize_prop_value(v)
                    for k, v in incoming.items()
                    if v is not None
                }
                edge_rec = {
                    "id": _make_edge_id(src_id, rel_type, dst_id),
                    "source": src_id,
                    "target": dst_id,
                    "rel_type": rel_type,
                    "properties": merged_props,
                }
                self._edges[key] = edge_rec
            else:
                merged_props = dict(existing["properties"])
                for k, v in incoming.items():
                    if v is None:
                        merged_props.pop(str(k), None)
                    else:
                        merged_props[str(k)] = _deserialize_prop_value(v)
                existing["properties"] = merged_props
                edge_rec = existing
            return {
                "id": edge_rec["id"],
                "source": edge_rec["source"],
                "target": edge_rec["target"],
                "rel_type": edge_rec["rel_type"],
                "properties": dict(edge_rec["properties"]),
            }

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        with self._lock:
            rec = self._nodes.get(node_id)
            if rec is None:
                return None
            return {
                "id": rec["id"],
                "labels": list(rec["labels"]),
                "properties": dict(rec["properties"]),
            }

    def query_nodes(
        self,
        label: str,
        filters: dict[str, Any] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        _validate_identifier(label, "label")
        if limit <= 0:
            return []
        flt = filters or {}
        with self._lock:
            results: list[dict[str, Any]] = []
            for nid in sorted(self._nodes):
                rec = self._nodes[nid]
                if label not in rec["labels"]:
                    continue
                if all(rec["properties"].get(k) == v for k, v in flt.items()):
                    results.append(
                        {
                            "id": rec["id"],
                            "labels": list(rec["labels"]),
                            "properties": dict(rec["properties"]),
                        }
                    )
                    if len(results) >= limit:
                        break
            return results

    def get_edges(
        self,
        node_id: str | None = None,
        rel_type: str | None = None,
        direction: Literal["out", "in", "both"] = "both",
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        if rel_type is not None:
            _validate_identifier(rel_type, "relationship type")
        with self._lock:
            out: list[dict[str, Any]] = []
            for key in sorted(self._edges):
                src, rtype, dst = key
                if rel_type is not None and rtype != rel_type:
                    continue
                if node_id is not None:
                    if direction == "out" and src != node_id:
                        continue
                    if direction == "in" and dst != node_id:
                        continue
                    if direction == "both" and src != node_id and dst != node_id:
                        continue
                rec = self._edges[key]
                out.append(
                    {
                        "id": rec["id"],
                        "source": rec["source"],
                        "target": rec["target"],
                        "rel_type": rec["rel_type"],
                        "properties": dict(rec["properties"]),
                    }
                )
                if len(out) >= limit:
                    break
            return out

    def get_node_degree(
        self, node_id: str, excluded_rel_types: set[str] | None = None
    ) -> int:
        excluded = excluded_rel_types or set()
        with self._lock:
            count = 0
            for src, rtype, dst in self._edges:
                if rtype in excluded:
                    continue
                if src == node_id:
                    count += 1
                if dst == node_id and src != node_id:
                    count += 1
                elif dst == node_id and src == node_id:
                    count += 1
            return count

    def get_subgraph(
        self, focus_id: str | None = None, limit: int = 200
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        with self._lock:
            if not self._nodes:
                return [], []
            if focus_id and focus_id in self._nodes:
                adj: dict[str, set[str]] = {nid: set() for nid in self._nodes}
                for src, _, dst in self._edges:
                    adj.setdefault(src, set()).add(dst)
                    adj.setdefault(dst, set()).add(src)
                selected: list[str] = []
                visited: set[str] = {focus_id}
                queue: deque[str] = deque([focus_id])
                while queue and len(selected) < limit:
                    curr = queue.popleft()
                    selected.append(curr)
                    for nbr in sorted(adj.get(curr, set())):
                        if nbr not in visited:
                            visited.add(nbr)
                            queue.append(nbr)
                selected_set = set(selected)
            else:
                edge_dicts = [
                    {"source": k[0], "target": k[2]} for k in self._edges
                ]
                selected_set = _select_default_subgraph_ids(
                    self._nodes, edge_dicts, limit
                )

            nodes = [
                {
                    "id": self._nodes[nid]["id"],
                    "labels": list(self._nodes[nid]["labels"]),
                    "properties": dict(self._nodes[nid]["properties"]),
                }
                for nid in sorted(selected_set)
            ]
            edges = [
                {
                    "id": self._edges[k]["id"],
                    "source": self._edges[k]["source"],
                    "target": self._edges[k]["target"],
                    "rel_type": self._edges[k]["rel_type"],
                    "properties": dict(self._edges[k]["properties"]),
                }
                for k in sorted(self._edges)
                if k[0] in selected_set and k[2] in selected_set
            ]
            return nodes, edges

    def delete_node(self, node_id: str) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                return False
            self._nodes.pop(node_id, None)
            to_remove = [
                key
                for key in self._edges
                if key[0] == node_id or key[2] == node_id
            ]
            for key in to_remove:
                self._edges.pop(key, None)
            return True

    def close(self) -> None:
        return None


class RelateGraphDriver:
    """Relate v1.0.1 .rl graph driver using short-lived locked connections + CLI fallback."""

    def __init__(
        self,
        db_path: str,
        relate_bin: str = "relate",
        timeout_secs: float = 10.0,
        prefer_cli: bool = False,
    ) -> None:
        self.db_path = db_path
        self.relate_bin = relate_bin
        self.timeout_secs = timeout_secs
        self.prefer_cli = prefer_cli
        self._lock = threading.RLock()

        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._use_native = (relate is not None) and (not prefer_cli)
        if not self._use_native and shutil.which(relate_bin) is None:
            raise BackendUnavailableError(
                "Neither relate-db Python module nor relate CLI binary is available"
            )

        self._ensure_schema()

    @property
    def backend_name(self) -> BackendMode:
        return "relate"

    def _ensure_schema(self) -> None:
        self._run_cypher(
            "CREATE CONSTRAINT tide_node_id IF NOT EXISTS "
            "FOR (n:TideNode) REQUIRE n.id IS UNIQUE"
        )

    def _run_cypher(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        payload = {"p": params or {}}
        with self._lock:
            last_exc: Exception | None = None
            for attempt in range(len(_LOCK_RETRY_DELAYS) + 1):
                try:
                    if self._use_native:
                        return self._execute_native(cypher, payload)
                    return self._execute_cli(cypher, payload["p"])
                except Exception as exc:
                    msg = str(exc).lower()
                    is_lock = "locked" in msg or "conflict" in msg
                    if is_lock and attempt < len(_LOCK_RETRY_DELAYS):
                        last_exc = exc
                        time.sleep(_LOCK_RETRY_DELAYS[attempt])
                        continue
                    raise
            assert last_exc is not None
            raise last_exc

    def _execute_native(
        self, cypher: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        assert relate is not None
        conn = relate.connect(self.db_path)
        try:
            cursor = conn.execute(cypher, params)
            rows = cursor.fetchall()
            conn.commit()
            return [dict(row) for row in rows]
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def _execute_cli(
        self, cypher: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        cmd = [
            self.relate_bin,
            "query",
            "--database",
            self.db_path,
            "--mode",
            "envelope",
            "--safe",
        ]
        tmp_path: Path | None = None
        try:
            if params:
                encoded_params = json.dumps(params)
                if len(encoded_params) <= 6000:
                    cmd.extend(["--param", f"p={encoded_params}"])
                else:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        suffix=".json",
                        encoding="utf-8",
                        delete=False,
                    ) as handle:
                        handle.write(encoded_params)
                        tmp_path = Path(handle.name)
                    cmd.extend(["--fetch-params", f"p={tmp_path}"])
            proc = subprocess.run(
                cmd,
                input=cypher,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_secs,
                check=False,
            )
        finally:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

        if proc.returncode == 5:
            raise RuntimeError(f"storage locked: {proc.stderr.strip()}")
        if proc.returncode != 0:
            raise RuntimeError(
                f"relate CLI exited {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
            )

        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if not lines:
            return []
        envelope = json.loads(lines[-1])
        return list(envelope.get("rows", []))

    def upsert_node(self, label: str, props: dict[str, Any]) -> dict[str, Any]:
        _validate_identifier(label, "label")
        working = dict(props)
        extra_labels = [
            _validate_identifier(lbl, "label")
            for lbl in working.pop("_extra_labels", [])
        ]
        node_id = str(working.get("id") or "").strip()
        if not node_id:
            raise ValueError("Node props must include a non-empty 'id'")
        working["id"] = node_id

        all_labels = list(dict.fromkeys([label, *extra_labels, "TideNode"]))
        label_expr = ":".join(all_labels)
        cypher = (
            f"MERGE (n:TideNode {{id: $p.id}}) "
            f"SET n:{label_expr} "
            f"SET n += $p.props "
            f"RETURN n.id AS id, labels(n) AS labels, properties(n) AS props"
        )
        rows = self._run_cypher(
            cypher,
            {"id": node_id, "props": _sanitize_props_for_cypher(working)},
        )
        row = rows[0]
        return {
            "id": str(row["id"]),
            "labels": _strip_internal_labels(list(row["labels"])),
            "properties": _normalize_props_from_store(row["props"]),
        }

    def upsert_edge(
        self,
        src_id: str,
        rel_type: str,
        dst_id: str,
        props: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _validate_identifier(rel_type, "relationship type")
        sanitized = _sanitize_props_for_cypher(props or {})
        cypher = (
            "MATCH (a:TideNode {id: $p.src_id}) "
            "MATCH (b:TideNode {id: $p.dst_id}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            "SET r += $p.props "
            "RETURN a.id AS source, type(r) AS rel_type, b.id AS target, properties(r) AS props "
            "LIMIT 1"
        )
        rows = self._run_cypher(
            cypher,
            {"src_id": src_id, "dst_id": dst_id, "props": sanitized},
        )
        if not rows:
            if self.get_node(src_id) is None:
                raise KeyError(f"Source node not found: {src_id}")
            raise KeyError(f"Target node not found: {dst_id}")
        row = rows[0]
        return {
            "id": _make_edge_id(str(row["source"]), str(row["rel_type"]), str(row["target"])),
            "source": str(row["source"]),
            "target": str(row["target"]),
            "rel_type": str(row["rel_type"]),
            "properties": _normalize_props_from_store(row["props"]),
        }

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        rows = self._run_cypher(
            "MATCH (n:TideNode {id: $p.id}) "
            "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props "
            "LIMIT 1",
            {"id": node_id},
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "id": str(row["id"]),
            "labels": _strip_internal_labels(list(row["labels"])),
            "properties": _normalize_props_from_store(row["props"]),
        }

    def query_nodes(
        self,
        label: str,
        filters: dict[str, Any] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        _validate_identifier(label, "label")
        if limit <= 0:
            return []
        flt = filters or {}
        if flt:
            rows = self._run_cypher(
                f"MATCH (n:{label}:TideNode) "
                "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props "
                "ORDER BY n.id ASC",
            )
        else:
            rows = self._run_cypher(
                f"MATCH (n:{label}:TideNode) "
                "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props "
                "ORDER BY n.id ASC LIMIT $p.limit",
                {"limit": int(limit)},
            )
        results: list[dict[str, Any]] = []
        for row in rows:
            props = _normalize_props_from_store(row["props"])
            if all(props.get(k) == v for k, v in flt.items()):
                results.append(
                    {
                        "id": str(row["id"]),
                        "labels": _strip_internal_labels(list(row["labels"])),
                        "properties": props,
                    }
                )
                if len(results) >= limit:
                    break
        return results

    def get_edges(
        self,
        node_id: str | None = None,
        rel_type: str | None = None,
        direction: Literal["out", "in", "both"] = "both",
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        rel_clause = f":{_validate_identifier(rel_type, 'relationship type')}" if rel_type else ""
        if node_id is None:
            cypher = (
                f"MATCH (a:TideNode)-[r{rel_clause}]->(b:TideNode) "
                "RETURN a.id AS source, type(r) AS rel_type, b.id AS target, properties(r) AS props "
                "LIMIT $p.limit"
            )
            params: dict[str, Any] = {"limit": int(limit)}
        elif direction == "out":
            cypher = (
                f"MATCH (a:TideNode {{id: $p.id}})-[r{rel_clause}]->(b:TideNode) "
                "RETURN a.id AS source, type(r) AS rel_type, b.id AS target, properties(r) AS props "
                "LIMIT $p.limit"
            )
            params = {"id": node_id, "limit": int(limit)}
        elif direction == "in":
            cypher = (
                f"MATCH (a:TideNode)-[r{rel_clause}]->(b:TideNode {{id: $p.id}}) "
                "RETURN a.id AS source, type(r) AS rel_type, b.id AS target, properties(r) AS props "
                "LIMIT $p.limit"
            )
            params = {"id": node_id, "limit": int(limit)}
        else:
            cypher = (
                f"MATCH (a:TideNode)-[r{rel_clause}]->(b:TideNode) "
                "WHERE a.id = $p.id OR b.id = $p.id "
                "RETURN a.id AS source, type(r) AS rel_type, b.id AS target, properties(r) AS props "
                "LIMIT $p.limit"
            )
            params = {"id": node_id, "limit": int(limit)}

        rows = self._run_cypher(cypher, params)
        edges = [
            {
                "id": _make_edge_id(str(r["source"]), str(r["rel_type"]), str(r["target"])),
                "source": str(r["source"]),
                "target": str(r["target"]),
                "rel_type": str(r["rel_type"]),
                "properties": _normalize_props_from_store(r["props"]),
            }
            for r in rows
        ]
        edges.sort(key=lambda e: (e["source"], e["rel_type"], e["target"]))
        return edges

    def get_node_degree(
        self, node_id: str, excluded_rel_types: set[str] | None = None
    ) -> int:
        excluded = excluded_rel_types or set()
        edges = self.get_edges(node_id=node_id, direction="both", limit=5000)
        count = 0
        for edge in edges:
            if edge["rel_type"] in excluded:
                continue
            if edge["source"] == node_id:
                count += 1
            if edge["target"] == node_id:
                count += 1
        return count

    def get_subgraph(
        self, focus_id: str | None = None, limit: int = 200
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        node_rows = self._run_cypher(
            "MATCH (n:TideNode) "
            "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props "
            "ORDER BY n.id ASC LIMIT $p.limit",
            {"limit": max(int(limit) * 25, 5000)},
        )
        all_nodes = {
            str(r["id"]): {
                "id": str(r["id"]),
                "labels": _strip_internal_labels(list(r["labels"])),
                "properties": _normalize_props_from_store(r["props"]),
            }
            for r in node_rows
        }
        if not all_nodes:
            return [], []

        all_edges = self.get_edges(limit=25000)
        if focus_id and focus_id in all_nodes:
            adj: dict[str, set[str]] = {nid: set() for nid in all_nodes}
            for edge in all_edges:
                adj.setdefault(edge["source"], set()).add(edge["target"])
                adj.setdefault(edge["target"], set()).add(edge["source"])
            selected: list[str] = []
            visited: set[str] = {focus_id}
            queue: deque[str] = deque([focus_id])
            while queue and len(selected) < limit:
                curr = queue.popleft()
                selected.append(curr)
                for nbr in sorted(adj.get(curr, set())):
                    if nbr not in visited:
                        visited.add(nbr)
                        queue.append(nbr)
            selected_set = set(selected)
        else:
            selected_set = _select_default_subgraph_ids(
                all_nodes, all_edges, limit
            )

        nodes = [all_nodes[nid] for nid in sorted(selected_set)]
        edges = [
            e
            for e in all_edges
            if e["source"] in selected_set and e["target"] in selected_set
        ]
        return nodes, edges

    def delete_node(self, node_id: str) -> bool:
        rows = self._run_cypher(
            "MATCH (n:TideNode {id: $p.id}) "
            "DETACH DELETE n "
            "RETURN count(n) AS deleted",
            {"id": node_id},
        )
        return bool(rows and int(rows[0].get("deleted") or 0) > 0)

    def close(self) -> None:
        return None


class Neo4jGDSDriver:
    """Optional live Neo4j 5.26+ Bolt driver with fast-fail connectivity verification."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        connection_timeout: float = 1.5,
    ) -> None:
        if GraphDatabase is None:
            raise BackendUnavailableError("neo4j Python driver is not installed")
        self.uri = uri
        self.database = database
        self._driver = None
        auth = (user, password) if (user or password) else None
        try:
            self._driver = GraphDatabase.driver(
                uri,
                auth=auth,
                connection_timeout=connection_timeout,
                connection_acquisition_timeout=connection_timeout,
                max_connection_pool_size=20,
            )
            self._driver.verify_connectivity()
            self._execute(
                "CREATE CONSTRAINT tide_node_id IF NOT EXISTS "
                "FOR (n:TideNode) REQUIRE n.id IS UNIQUE"
            )
        except (
            ServiceUnavailable,
            AuthError,
            ConnectionAcquisitionTimeoutError,
            DatabaseUnavailable,
            DriverError,
            OSError,
            ValueError,
        ) as exc:
            self.close()
            raise BackendUnavailableError(
                f"Neo4j unreachable at {uri}: {type(exc).__name__}"
            ) from exc

    @property
    def backend_name(self) -> BackendMode:
        return "neo4j"

    def _execute(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        assert self._driver is not None
        records, _, _ = self._driver.execute_query(
            cypher,
            parameters_=params or {},
            database_=self.database,
        )
        return [dict(record) for record in records]

    def run_gds_procedure(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]] | None:
        """Run optional Neo4j GDS procedure; returns None if GDS plugin is absent."""
        try:
            return self._execute(cypher, params)
        except (ClientError, Neo4jError):
            return None

    def upsert_node(self, label: str, props: dict[str, Any]) -> dict[str, Any]:
        _validate_identifier(label, "label")
        working = dict(props)
        extra_labels = [
            _validate_identifier(lbl, "label")
            for lbl in working.pop("_extra_labels", [])
        ]
        node_id = str(working.get("id") or "").strip()
        if not node_id:
            raise ValueError("Node props must include a non-empty 'id'")
        working["id"] = node_id
        all_labels = list(dict.fromkeys([label, *extra_labels, "TideNode"]))
        label_expr = ":".join(all_labels)
        rows = self._execute(
            f"MERGE (n:TideNode {{id: $id}}) SET n:{label_expr} SET n += $props "
            "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props",
            {"id": node_id, "props": _sanitize_props_for_cypher(working)},
        )
        row = rows[0]
        return {
            "id": str(row["id"]),
            "labels": _strip_internal_labels(list(row["labels"])),
            "properties": _normalize_props_from_store(row["props"]),
        }

    def upsert_edge(
        self,
        src_id: str,
        rel_type: str,
        dst_id: str,
        props: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _validate_identifier(rel_type, "relationship type")
        rows = self._execute(
            "MATCH (a:TideNode {id: $src_id}), (b:TideNode {id: $dst_id}) "
            f"MERGE (a)-[r:{rel_type}]->(b) SET r += $props "
            "RETURN a.id AS source, type(r) AS rel_type, b.id AS target, properties(r) AS props",
            {
                "src_id": src_id,
                "dst_id": dst_id,
                "props": _sanitize_props_for_cypher(props or {}),
            },
        )
        if not rows:
            raise KeyError(f"Missing endpoint for edge {src_id}->{dst_id}")
        row = rows[0]
        return {
            "id": _make_edge_id(str(row["source"]), str(row["rel_type"]), str(row["target"])),
            "source": str(row["source"]),
            "target": str(row["target"]),
            "rel_type": str(row["rel_type"]),
            "properties": _normalize_props_from_store(row["props"]),
        }

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        rows = self._execute(
            "MATCH (n:TideNode {id: $id}) "
            "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props LIMIT 1",
            {"id": node_id},
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "id": str(row["id"]),
            "labels": _strip_internal_labels(list(row["labels"])),
            "properties": _normalize_props_from_store(row["props"]),
        }

    def query_nodes(
        self,
        label: str,
        filters: dict[str, Any] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        _validate_identifier(label, "label")
        if limit <= 0:
            return []
        flt = filters or {}
        if flt:
            rows = self._execute(
                f"MATCH (n:{label}:TideNode) "
                "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props "
                "ORDER BY n.id ASC",
            )
        else:
            rows = self._execute(
                f"MATCH (n:{label}:TideNode) "
                "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props "
                "ORDER BY n.id ASC LIMIT $limit",
                {"limit": int(limit)},
            )
        results: list[dict[str, Any]] = []
        for row in rows:
            props = _normalize_props_from_store(row["props"])
            if all(props.get(k) == v for k, v in flt.items()):
                results.append(
                    {
                        "id": str(row["id"]),
                        "labels": _strip_internal_labels(list(row["labels"])),
                        "properties": props,
                    }
                )
                if len(results) >= limit:
                    break
        return results

    def get_edges(
        self,
        node_id: str | None = None,
        rel_type: str | None = None,
        direction: Literal["out", "in", "both"] = "both",
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        rel_clause = f":{_validate_identifier(rel_type, 'relationship type')}" if rel_type else ""
        if node_id is None:
            cypher = (
                f"MATCH (a:TideNode)-[r{rel_clause}]->(b:TideNode) "
                "RETURN a.id AS source, type(r) AS rel_type, b.id AS target, properties(r) AS props "
                "LIMIT $limit"
            )
            params: dict[str, Any] = {"limit": int(limit)}
        elif direction == "out":
            cypher = (
                f"MATCH (a:TideNode {{id: $id}})-[r{rel_clause}]->(b:TideNode) "
                "RETURN a.id AS source, type(r) AS rel_type, b.id AS target, properties(r) AS props "
                "LIMIT $limit"
            )
            params = {"id": node_id, "limit": int(limit)}
        elif direction == "in":
            cypher = (
                f"MATCH (a:TideNode)-[r{rel_clause}]->(b:TideNode {{id: $id}}) "
                "RETURN a.id AS source, type(r) AS rel_type, b.id AS target, properties(r) AS props "
                "LIMIT $limit"
            )
            params = {"id": node_id, "limit": int(limit)}
        else:
            cypher = (
                f"MATCH (a:TideNode)-[r{rel_clause}]->(b:TideNode) "
                "WHERE a.id = $id OR b.id = $id "
                "RETURN a.id AS source, type(r) AS rel_type, b.id AS target, properties(r) AS props "
                "LIMIT $limit"
            )
            params = {"id": node_id, "limit": int(limit)}

        rows = self._execute(cypher, params)
        edges = [
            {
                "id": _make_edge_id(str(r["source"]), str(r["rel_type"]), str(r["target"])),
                "source": str(r["source"]),
                "target": str(r["target"]),
                "rel_type": str(r["rel_type"]),
                "properties": _normalize_props_from_store(r["props"]),
            }
            for r in rows
        ]
        edges.sort(key=lambda e: (e["source"], e["rel_type"], e["target"]))
        return edges

    def get_node_degree(
        self, node_id: str, excluded_rel_types: set[str] | None = None
    ) -> int:
        excluded = excluded_rel_types or set()
        edges = self.get_edges(node_id=node_id, direction="both", limit=5000)
        count = 0
        for edge in edges:
            if edge["rel_type"] in excluded:
                continue
            if edge["source"] == node_id:
                count += 1
            if edge["target"] == node_id:
                count += 1
        return count

    def get_subgraph(
        self, focus_id: str | None = None, limit: int = 200
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows = self._execute(
            "MATCH (n:TideNode) RETURN n.id AS id, labels(n) AS labels, properties(n) AS props "
            "ORDER BY n.id ASC LIMIT $limit",
            {"limit": max(int(limit) * 25, 5000)},
        )
        all_nodes = {
            str(r["id"]): {
                "id": str(r["id"]),
                "labels": _strip_internal_labels(list(r["labels"])),
                "properties": _normalize_props_from_store(r["props"]),
            }
            for r in rows
        }
        if not all_nodes:
            return [], []
        all_edges = self.get_edges(limit=25000)
        if focus_id and focus_id in all_nodes:
            adj: dict[str, set[str]] = {nid: set() for nid in all_nodes}
            for edge in all_edges:
                adj.setdefault(edge["source"], set()).add(edge["target"])
                adj.setdefault(edge["target"], set()).add(edge["source"])
            selected: list[str] = []
            visited: set[str] = {focus_id}
            queue: deque[str] = deque([focus_id])
            while queue and len(selected) < limit:
                curr = queue.popleft()
                selected.append(curr)
                for nbr in sorted(adj.get(curr, set())):
                    if nbr not in visited:
                        visited.add(nbr)
                        queue.append(nbr)
            selected_set = set(selected)
        else:
            selected_set = _select_default_subgraph_ids(
                all_nodes, all_edges, limit
            )
        return (
            [all_nodes[nid] for nid in sorted(selected_set)],
            [
                e
                for e in all_edges
                if e["source"] in selected_set and e["target"] in selected_set
            ],
        )

    def delete_node(self, node_id: str) -> bool:
        rows = self._execute(
            "MATCH (n:TideNode {id: $id}) "
            "DETACH DELETE n "
            "RETURN count(n) AS deleted",
            {"id": node_id},
        )
        return bool(rows and int(rows[0].get("deleted") or 0) > 0)

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:
                pass
            self._driver = None


def _tcp_port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_backend_status(settings: Settings) -> dict[str, bool]:
    """Non-mutating probe of Relate and Neo4j availability."""
    relate_ok = (relate is not None) or (shutil.which(settings.relate_bin) is not None)
    neo4j_ok = False
    if GraphDatabase is not None and settings.neo4j_uri.startswith("bolt://"):
        host_port = settings.neo4j_uri.removeprefix("bolt://").split("/")[0]
        host, _, port_str = host_port.partition(":")
        port = int(port_str) if port_str.isdigit() else 7687
        neo4j_ok = _tcp_port_open(host or "127.0.0.1", port, timeout=0.25)
    return {"relate_available": relate_ok, "neo4j_available": neo4j_ok}


def create_graph_backend(settings: Settings) -> GraphBackend:
    """Instantiate the configured GraphBackend with deterministic fallback."""
    if settings.graph_mode == "inprocess":
        return InProcessGraphDriver()

    if settings.graph_mode == "neo4j":
        try:
            return Neo4jGDSDriver(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
                database=settings.neo4j_database,
            )
        except BackendUnavailableError:
            pass

    if settings.graph_mode in {"auto", "relate", "neo4j"}:
        try:
            return RelateGraphDriver(
                db_path=settings.relate_db_path,
                relate_bin=settings.relate_bin,
                timeout_secs=settings.relate_timeout_secs,
            )
        except Exception:
            if settings.graph_mode == "relate":
                raise

    return InProcessGraphDriver()
