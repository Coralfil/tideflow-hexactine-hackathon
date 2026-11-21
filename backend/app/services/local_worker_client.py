"""Local RTX 3060 / Ollama inference offload client with deterministic fallback."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from typing import Any

import httpx

from app.config import Settings
from app.models.schemas import InferenceSource, ThoughtClassification, ThoughtKind

EMBEDDING_DIM = 384

_BLOCKER_KEYWORDS = (
    "blocked",
    "stuck",
    "waiting on",
    "failing",
    "error",
    "broken",
    "cannot",
    "blocker",
    "crash",
)
_SIDE_QUEST_KEYWORDS = (
    "side quest",
    "side-quest",
    "someday",
    "maybe later",
    "rabbit hole",
    "explore",
    "curious",
    "weekend",
    "tangent",
)
_TASK_KEYWORDS = (
    "implement",
    "fix",
    "ship",
    "write",
    "test",
    "deploy",
    "refactor",
    "build",
    "add",
    "create",
    "finish",
    "verify",
)

_DOMAIN_LEXICON = (
    "graph",
    "neo4j",
    "relate",
    "hexactine",
    "pagerank",
    "leiden",
    "cadence",
    "scheduler",
    "retriever",
    "nemoclaw",
    "houdini",
    "momentum",
    "breadcrumb",
    "triage",
    "telemetry",
    "marine",
    "api",
    "ui",
    "shader",
    "memory",
)

_HASHTAG_RE = re.compile(r"#([A-Za-z0-9_-]{2,32})")
_WORD_RE = re.compile(r"[a-zA-Z0-9]{2,}")
_STUB_MARKERS = ("OBELISK_14B_DET_OK", "<GLYPH:")


def _compile_keyword_patterns(
    keywords: tuple[str, ...],
) -> tuple[tuple[str, re.Pattern[str]], ...]:
    return tuple(
        (kw, re.compile(rf"\b{re.escape(kw)}(?:s|es|ed|ing)?\b"))
        for kw in keywords
    )


_BLOCKER_PATTERNS = _compile_keyword_patterns(_BLOCKER_KEYWORDS)
_SIDE_QUEST_PATTERNS = _compile_keyword_patterns(_SIDE_QUEST_KEYWORDS)
_TASK_PATTERNS = _compile_keyword_patterns(_TASK_KEYWORDS)
_DOMAIN_LEXICON_PATTERNS = _compile_keyword_patterns(_DOMAIN_LEXICON)


def _strip_markdown_fences(raw: str) -> str:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _safe_parse_energy(raw_energy: Any, default: int = 2) -> int:
    if raw_energy is None or isinstance(raw_energy, bool):
        return default
    if isinstance(raw_energy, float) and not math.isfinite(raw_energy):
        return default
    try:
        energy = int(raw_energy)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(1, min(5, energy))


def _parse_resume_card_lines(raw_text: str) -> list[str] | None:
    if is_stub_or_invalid_llm_output(raw_text):
        return None
    cleaned = _strip_markdown_fences(raw_text)
    if not cleaned or is_stub_or_invalid_llm_output(cleaned):
        return None

    candidate_lines: list[str] | None = None
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and isinstance(parsed.get("card_lines"), list):
            candidate_lines = [str(item) for item in parsed["card_lines"]]
        elif isinstance(parsed, list):
            candidate_lines = [str(item) for item in parsed]
    except json.JSONDecodeError:
        raw_lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if len(raw_lines) == 3 and not any(
            line.startswith("{") or line.startswith("[") for line in raw_lines
        ):
            candidate_lines = raw_lines

    if not candidate_lines or len(candidate_lines) != 3:
        return None

    normalized: list[str] = []
    for line in candidate_lines:
        clean_line = line.replace("\u2014", "-").strip()
        if not clean_line or is_stub_or_invalid_llm_output(clean_line):
            return None
        normalized.append(clean_line[:220])
    return normalized


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "general"


def hash_embed_384(text: str) -> list[float]:
    """Deterministic 384-dim unit-normalized feature hashing fallback."""
    vec = [0.0] * EMBEDDING_DIM
    tokens = _WORD_RE.findall(text.lower())
    if not tokens:
        vec[0] = 1.0
        return vec

    features: list[str] = list(tokens)
    for i in range(len(tokens) - 1):
        features.append(f"{tokens[i]}_{tokens[i + 1]}")

    for feat in features:
        digest = hashlib.sha256(feat.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 1e-12:
        vec[0] = 1.0
        return vec
    return [round(v / norm, 6) for v in vec]


def _cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return dot / (na * nb)


def is_stub_or_invalid_llm_output(content: str) -> bool:
    """Reject wave1_worker_daemon deterministic stub glyphs or empty output."""
    stripped = (content or "").strip()
    if not stripped:
        return True
    return any(marker in stripped for marker in _STUB_MARKERS)


class LocalWorkerClient:
    """Client for D:\\coralfil-os-worker (:8000/:8001/:8003) and optional Ollama (:11434)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _fast_timeout(self, read_timeout: float) -> httpx.Timeout:
        return httpx.Timeout(connect=0.25, read=read_timeout, write=1.0, pool=0.5)

    async def probe_services(self) -> dict[str, bool]:
        """Probe local worker endpoints with short timeout."""
        if not self.settings.local_worker_enabled:
            return {"embeddings": False, "chat": False, "ollama": False, "any": False}

        timeout = self._fast_timeout(self.settings.local_worker_probe_timeout)
        emb_ok = False
        chat_ok = False
        ollama_ok = False

        async def _check(url: str) -> bool:
            try:
                resp = await client.get(url)
                return resp.status_code == 200
            except Exception:
                return False

        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            emb_ok, chat_ok, ollama_ok = await asyncio.gather(
                _check(self.settings.local_worker_embeddings_health_url),
                _check(f"{self.settings.local_worker_chat_url.rstrip('/')}/health"),
                _check(f"{self.settings.local_ollama_url.rstrip('/')}/api/tags"),
            )

        return {
            "embeddings": emb_ok,
            "chat": chat_ok,
            "ollama": ollama_ok,
            "any": emb_ok or chat_ok or ollama_ok,
        }

    async def probe_health(self) -> bool:
        status = await self.probe_services()
        return status["any"]

    async def embed(self, texts: list[str]) -> tuple[list[list[float]], InferenceSource]:
        """Generate 384-dim embeddings via :8001/embeddings or deterministic hashing."""
        if not texts:
            return [], "deterministic_fallback"

        if self.settings.local_worker_enabled:
            try:
                async with httpx.AsyncClient(
                    timeout=self._fast_timeout(self.settings.local_worker_infer_timeout),
                    trust_env=False,
                ) as client:
                    resp = await client.post(
                        self.settings.local_worker_embeddings_url,
                        json={"input": texts},
                    )
                if resp.status_code == 200:
                    payload = resp.json()
                    data = payload.get("data") or []
                    vectors = [item.get("embedding") for item in data]
                    if len(vectors) == len(texts) and all(
                        isinstance(v, list) and len(v) > 0 for v in vectors
                    ):
                        return [
                            [float(x) for x in v] for v in vectors
                        ], "local_worker"
            except Exception:
                pass

        return [hash_embed_384(t) for t in texts], "deterministic_fallback"

    async def rerank(
        self, query: str, documents: list[str]
    ) -> tuple[list[tuple[int, float, str]], InferenceSource]:
        """Score documents against query via :8001/rerank or hash cosine similarity."""
        if not documents:
            return [], "deterministic_fallback"

        if self.settings.local_worker_enabled:
            try:
                async with httpx.AsyncClient(
                    timeout=self._fast_timeout(self.settings.local_worker_infer_timeout),
                    trust_env=False,
                ) as client:
                    resp = await client.post(
                        self.settings.local_worker_rerank_url,
                        json={"query": query, "documents": documents},
                    )
                if resp.status_code == 200:
                    payload = resp.json()
                    results = payload.get("results") or []
                    if results:
                        parsed = [
                            (
                                int(r["index"]),
                                float(r["score"]),
                                str(r.get("document") or documents[int(r["index"])]),
                            )
                            for r in results
                        ]
                        parsed.sort(key=lambda item: (-item[1], item[0]))
                        return parsed, "local_worker"
            except Exception:
                pass

        q_vec = hash_embed_384(query)
        scored: list[tuple[int, float, str]] = []
        for idx, doc in enumerate(documents):
            score = _cosine_sim(q_vec, hash_embed_384(doc))
            scored.append((idx, round(score, 6), doc))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored, "deterministic_fallback"

    def _deterministic_classify(
        self,
        text: str,
        explicit_kind: ThoughtKind | None = None,
        explicit_tags: list[str] | None = None,
        extra_semantic_tags: list[str] | None = None,
        source: InferenceSource = "deterministic_fallback",
    ) -> ThoughtClassification:
        lower = text.lower()
        if explicit_kind is not None:
            kind: ThoughtKind = explicit_kind
        elif any(pat.search(lower) for _, pat in _BLOCKER_PATTERNS):
            kind = "blocker"
        elif any(pat.search(lower) for _, pat in _SIDE_QUEST_PATTERNS):
            kind = "side_quest"
        elif any(pat.search(lower) for _, pat in _TASK_PATTERNS):
            kind = "project_task"
        else:
            kind = "spark_idea"

        tags: list[str] = []
        for raw_tag in explicit_tags or []:
            slug = _slugify(raw_tag)
            if slug and slug not in tags:
                tags.append(slug)

        for match in _HASHTAG_RE.findall(text):
            slug = _slugify(match)
            if slug and slug not in tags:
                tags.append(slug)

        for kw, pat in _DOMAIN_LEXICON_PATTERNS:
            if pat.search(lower) and kw not in tags:
                tags.append(kw)

        for sem_tag in extra_semantic_tags or []:
            slug = _slugify(sem_tag)
            if slug and slug not in tags:
                tags.append(slug)

        if not tags:
            tags.append(kind)
        tags = tags[:3]

        if kind == "blocker":
            energy = 4
            micro = f"Isolate the root cause of: {text.strip()[:80]}"
        elif kind == "project_task":
            energy = 3
            micro = f"Spend 10 focused minutes on: {text.strip()[:80]}"
        elif kind == "side_quest":
            energy = 2
            micro = f"Keep parked until deep_tide tasks clear: {text.strip()[:70]}"
        else:
            energy = 2
            micro = f"Capture 1 concrete next check for: {text.strip()[:75]}"

        return ThoughtClassification(
            kind=kind,
            energy_cost=energy,
            concept_tags=tags,
            suggested_micro_step=micro,
            inference_source=source,
        )

    async def _try_llm_classify(
        self, text: str
    ) -> tuple[dict[str, Any], InferenceSource] | None:
        """Attempt Ollama or local worker chat JSON classification, rejecting stubs."""
        if not self.settings.local_worker_enabled:
            return None

        prompt = (
            "Classify this ADD thought into JSON with keys "
            "kind (one of: spark_idea, project_task, side_quest, blocker), "
            "energy_cost (integer 1..5), concept_tags (array of 1..3 lowercase slugs), "
            "suggested_micro_step (short string). Respond ONLY with JSON.\n"
            f"Text: {text}"
        )

        # 1. Try local Ollama if reachable
        try:
            async with httpx.AsyncClient(
                timeout=self._fast_timeout(self.settings.local_worker_infer_timeout),
                trust_env=False,
            ) as client:
                resp = await client.post(
                    f"{self.settings.local_ollama_url.rstrip('/')}/api/generate",
                    json={
                        "model": self.settings.local_ollama_model,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                    },
                )
            if resp.status_code == 200:
                raw = str(resp.json().get("response") or "")
                if not is_stub_or_invalid_llm_output(raw):
                    parsed = json.loads(_strip_markdown_fences(raw))
                    if isinstance(parsed, dict) and parsed.get("kind") in {
                        "spark_idea",
                        "project_task",
                        "side_quest",
                        "blocker",
                    }:
                        return parsed, "ollama"
        except Exception:
            pass

        # 2. Try local worker chat (:8000/v1/chat/completions), rejecting OBELISK_14B_DET_OK stub
        try:
            async with httpx.AsyncClient(
                timeout=self._fast_timeout(self.settings.local_worker_infer_timeout),
                trust_env=False,
            ) as client:
                resp = await client.post(
                    f"{self.settings.local_worker_chat_url.rstrip('/')}/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                        "max_tokens": 160,
                    },
                )
            if resp.status_code == 200:
                choices = resp.json().get("choices") or []
                if choices:
                    content = str(
                        ((choices[0] or {}).get("message") or {}).get("content") or ""
                    )
                    if not is_stub_or_invalid_llm_output(content):
                        parsed = json.loads(_strip_markdown_fences(content))
                        if isinstance(parsed, dict) and parsed.get("kind") in {
                            "spark_idea",
                            "project_task",
                            "side_quest",
                            "blocker",
                        }:
                            return parsed, "local_worker"
        except Exception:
            pass

        return None

    async def classify_and_extract(
        self,
        text: str,
        explicit_kind: ThoughtKind | None = None,
        explicit_tags: list[str] | None = None,
    ) -> ThoughtClassification:
        """Classify a captured thought using local worker / Ollama or deterministic rules."""
        llm_result = await self._try_llm_classify(text)
        if llm_result is not None:
            parsed, source = llm_result
            raw_kind = explicit_kind or parsed.get("kind", "spark_idea")
            kind: ThoughtKind = raw_kind if raw_kind in {
                "spark_idea",
                "project_task",
                "side_quest",
                "blocker",
            } else "spark_idea"
            if explicit_tags:
                tags = [_slugify(str(t)) for t in explicit_tags if str(t).strip()]
            else:
                tags = []
                for match in _HASHTAG_RE.findall(text):
                    slug = _slugify(match)
                    if slug and slug not in tags:
                        tags.append(slug)
                raw_concept_tags = parsed.get("concept_tags")
                if isinstance(raw_concept_tags, str):
                    normalized_tags = [
                        part.strip()
                        for part in raw_concept_tags.split(",")
                        if part.strip()
                    ]
                elif isinstance(raw_concept_tags, (list, tuple, set)):
                    normalized_tags = [
                        str(item).strip()
                        for item in raw_concept_tags
                        if item is not None and str(item).strip()
                    ]
                else:
                    normalized_tags = []
                for raw_tag in normalized_tags:
                    slug = _slugify(raw_tag)
                    if slug and slug not in tags:
                        tags.append(slug)
            tags = list(dict.fromkeys(tags))[:3]
            if not tags:
                tags = [kind]
            energy = _safe_parse_energy(parsed.get("energy_cost"), default=2)
            micro = str(parsed.get("suggested_micro_step") or "").replace("\u2014", "-").strip()
            if not micro or is_stub_or_invalid_llm_output(micro):
                fallback = self._deterministic_classify(text, explicit_kind=kind)
                micro = fallback.suggested_micro_step
            return ThoughtClassification(
                kind=kind,
                energy_cost=energy,
                concept_tags=tags,
                suggested_micro_step=micro,
                inference_source=source,
            )

        # Optional semantic concept enrichment via :8001/rerank when online
        semantic_tags: list[str] = []
        source: InferenceSource = "deterministic_fallback"
        if self.settings.local_worker_enabled and not explicit_tags:
            ranked, rank_src = await self.rerank(text, list(_DOMAIN_LEXICON))
            if rank_src == "local_worker" and ranked:
                semantic_tags = [doc for _, score, doc in ranked[:2] if score >= 0.22]
                if semantic_tags:
                    source = "local_worker"

        return self._deterministic_classify(
            text=text,
            explicit_kind=explicit_kind,
            explicit_tags=explicit_tags,
            extra_semantic_tags=semantic_tags,
            source=source,
        )

    async def summarize_resume_card(
        self,
        project_name: str,
        last_action: str,
        next_micro_step: str,
        linked_sparks: list[str],
    ) -> list[str]:
        """Build a 3-line resume card via Ollama/local worker with deterministic fallback."""
        sparks_text = ", ".join(linked_sparks) if linked_sparks else "None linked"
        fallback_lines = [
            f"Last ({project_name}): {last_action}",
            f"Next: {next_micro_step}",
            f"Sparks: {sparks_text}",
        ]
        if not self.settings.local_worker_enabled:
            return fallback_lines

        prompt = (
            "Summarize this project resume context into JSON with key "
            "card_lines (an array of exactly 3 short strings: "
            "line 1 starting with 'Last', line 2 starting with 'Next:', "
            "line 3 starting with 'Sparks:'). Use no em dashes. Respond ONLY with JSON.\n"
            f"Project: {project_name}\n"
            f"Last action: {last_action}\n"
            f"Next step: {next_micro_step}\n"
            f"Linked sparks: {sparks_text}"
        )

        # 1. Try Ollama /api/generate
        try:
            async with httpx.AsyncClient(
                timeout=self._fast_timeout(self.settings.local_worker_infer_timeout),
                trust_env=False,
            ) as client:
                resp = await client.post(
                    f"{self.settings.local_ollama_url.rstrip('/')}/api/generate",
                    json={
                        "model": self.settings.local_ollama_model,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                    },
                )
            if resp.status_code == 200:
                raw = str(resp.json().get("response") or "")
                parsed_lines = _parse_resume_card_lines(raw)
                if parsed_lines is not None:
                    return parsed_lines
        except Exception:
            pass

        # 2. Try local worker chat (:8000/v1/chat/completions), rejecting stub outputs
        try:
            async with httpx.AsyncClient(
                timeout=self._fast_timeout(self.settings.local_worker_infer_timeout),
                trust_env=False,
            ) as client:
                resp = await client.post(
                    f"{self.settings.local_worker_chat_url.rstrip('/')}/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                        "max_tokens": 180,
                    },
                )
            if resp.status_code == 200:
                choices = resp.json().get("choices") or []
                if choices:
                    content = str(
                        ((choices[0] or {}).get("message") or {}).get("content") or ""
                    )
                    parsed_lines = _parse_resume_card_lines(content)
                    if parsed_lines is not None:
                        return parsed_lines
        except Exception:
            pass

        return fallback_lines
