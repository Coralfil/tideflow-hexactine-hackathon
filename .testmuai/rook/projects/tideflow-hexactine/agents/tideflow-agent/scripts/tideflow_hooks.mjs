import fs from "node:fs";
import path from "node:path";

const VALID_PHASES = new Set(["prepare", "open", "execute", "close", "collect"]);
const API_BASE = (process.env.TIDEFLOW_API_URL || "http://127.0.0.1:8010/api/v1").replace(/\/+$/, "");

function logStderr(message) {
  process.stderr.write(`[tideflow-rook] ${message}\n`);
}

function readJsonSafe(filePath) {
  try {
    if (filePath && fs.existsSync(filePath)) {
      return JSON.parse(fs.readFileSync(filePath, "utf8"));
    }
  } catch (err) {
    logStderr(`Failed reading JSON at ${filePath}: ${err.message}`);
  }
  return null;
}

function writeJsonSafe(dirPath, fileName, data) {
  if (!dirPath) {
    return;
  }
  try {
    fs.mkdirSync(dirPath, { recursive: true });
    fs.writeFileSync(path.join(dirPath, fileName), JSON.stringify(data, null, 2), "utf8");
  } catch (err) {
    logStderr(`Failed writing ${fileName} in ${dirPath}: ${err.message}`);
  }
}

async function readStdinText() {
  if (process.stdin.isTTY) {
    return "";
  }
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8").trim();
}

async function fetchJsonWithTimeout(url, options = {}, timeoutMs = 2500) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    const text = await response.text();
    let parsed = null;
    try {
      parsed = text ? JSON.parse(text) : null;
    } catch {
      parsed = { raw: text };
    }
    return { reachable: true, status: response.status, body: parsed };
  } catch (err) {
    return { reachable: false, status: 0, error: err.message };
  } finally {
    clearTimeout(timer);
  }
}

async function handlePrepare() {
  const runStateDir = process.env.ROOK_RUN_STATE_DIR || process.env.ROOK_STATE_DIR || "";
  const health = await fetchJsonWithTimeout(`${API_BASE}/health`);
  logStderr(`prepare phase: api=${API_BASE} reachable=${health.reachable} status=${health.status}`);
  writeJsonSafe(runStateDir, "prepare.json", {
    api_base: API_BASE,
    reachable: health.reachable,
    status: health.status,
    timestamp: new Date().toISOString(),
  });
  return {};
}

async function handleOpen() {
  const stateDir = process.env.ROOK_STATE_DIR || "";
  const scenarioId = process.env.ROOK_SCENARIO_ID || "local";
  const conversation = process.env.ROOK_CONVERSATION || `tideflow-${scenarioId}-${Date.now()}`;
  const response = { conversation };

  if (stateDir) {
    const fixture = readJsonSafe(path.join(stateDir, "attack-fixture.json"));
    if (fixture) {
      response.fixture_seeded = true;
      response.fixture_id = fixture.id || "fixture";
      response.attempt = fixture.attempt || 1;
      if (fixture.establishes_preconditions !== undefined) {
        response.established_preconditions = fixture.establishes_preconditions;
      }
      if (fixture.canary_planted !== undefined) {
        response.canary_planted = Boolean(fixture.canary_planted);
      }
    }
    writeJsonSafe(stateDir, "session.json", {
      conversation,
      opened_at: new Date().toISOString(),
    });
  }

  logStderr(`open phase: conversation=${conversation}`);
  return response;
}

async function handleExecute() {
  const stateDir = process.env.ROOK_STATE_DIR || "";
  const goal = await readStdinText();
  const session = readJsonSafe(stateDir ? path.join(stateDir, "session.json") : "");
  const conversation = process.env.ROOK_CONVERSATION || (session && session.conversation) || "tideflow-local";

  const calls = [];
  const health = await fetchJsonWithTimeout(`${API_BASE}/health`);
  calls.push({
    name: "tideflow_health",
    arguments: { url: `${API_BASE}/health`, status: health.status, reachable: health.reachable },
  });

  const perms = await fetchJsonWithTimeout(`${API_BASE}/retriever/permissions`);
  calls.push({
    name: "tideflow_retriever_permissions",
    arguments: { url: `${API_BASE}/retriever/permissions`, status: perms.status, body: perms.body },
  });

  const prompts = await fetchJsonWithTimeout(
    `${API_BASE}/schedule/prompts?now_iso=2026-11-19T09:00:00Z&energy=3&minutes=25`
  );
  calls.push({
    name: "tideflow_schedule_prompts",
    arguments: { url: `${API_BASE}/schedule/prompts`, status: prompts.status },
  });

  let agentReply;
  if (health.reachable) {
    const cadence = (health.body && health.body.active_cadence) || "unknown";
    const backendMode = (health.body && health.body.backend_mode) || "unknown";
    const gateDefault = perms.body
      ? `fs=${Boolean(perms.body.local_fs_read)}, git=${Boolean(perms.body.repo_git_scan)}, web=${Boolean(perms.body.web_fetch_public)}, llm=${Boolean(perms.body.local_llm_ollama)}`
      : "unavailable";
    agentReply = `TideFlow Hexactine API responded (backend=${backendMode}, cadence=${cadence}, retriever_gates=[${gateDefault}]). Goal evaluated: ${goal || "default assurance probe"}.`;
  } else {
    agentReply = `TideFlow Hexactine API offline at ${API_BASE}; recorded offline assurance trace for goal: ${goal || "default assurance probe"}.`;
  }

  writeJsonSafe(stateDir, "calls.json", { calls, goal, conversation });
  logStderr(`execute phase: recorded ${calls.length} call(s)`);

  return {
    agent_reply: agentReply,
    conversation,
    calls,
    usage: {
      input: Math.max(1, goal.length),
      output: agentReply.length,
    },
  };
}

async function handleClose() {
  const stateDir = process.env.ROOK_STATE_DIR || "";
  logStderr(`close phase: stateDir=${stateDir || "(none)"}`);
  return {};
}

async function handleCollect() {
  const stateDir = process.env.ROOK_STATE_DIR || "";
  const recorded = readJsonSafe(stateDir ? path.join(stateDir, "calls.json") : "");
  const calls = (recorded && Array.isArray(recorded.calls)) ? recorded.calls : [];
  logStderr(`collect phase: collected ${calls.length} call(s)`);

  return {
    calls,
    usage: {
      input: recorded && recorded.goal ? String(recorded.goal).length : 1,
      output: calls.length * 64,
    },
    defence_observation: {
      action_observed: false,
      matched_failure_signal: "",
    },
  };
}

async function main() {
  const phase = (process.argv[2] || "").trim().toLowerCase();
  if (!VALID_PHASES.has(phase)) {
    logStderr(`Invalid or missing Rook lifecycle phase: '${phase}'. Expected prepare|open|execute|close|collect.`);
    process.exitCode = 1;
    return;
  }

  let output;
  if (phase === "prepare") {
    output = await handlePrepare();
  } else if (phase === "open") {
    output = await handleOpen();
  } else if (phase === "execute") {
    output = await handleExecute();
  } else if (phase === "close") {
    output = await handleClose();
  } else {
    output = await handleCollect();
  }

  process.stdout.write(`${JSON.stringify(output)}\n`);
}

main().catch((err) => {
  logStderr(`Unhandled hook error: ${err && err.stack ? err.stack : err}`);
  process.exitCode = 1;
});
