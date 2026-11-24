const ENV = {};

async function readStdin() {
  let text = "";
  process.stdin.setEncoding("utf-8");
  for await (const chunk of process.stdin) text += chunk;
  return text;
}

async function execute() {
  const goal = await readStdin();
  const response = await fetch("http://127.0.0.1:8010/api/v1/retriever/execute", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ capability: "local_fs_read", target: goal }),
    signal: AbortSignal.timeout(600_000),
  });
  const responseText = await response.text();
  if (!response.ok) {
    throw new Error(`agent request failed: ${response.status} ${responseText.slice(0, 300)}`);
  }
  return { agent_reply: responseText };
}

const PHASES = { execute };
const fn = PHASES[process.argv[2]];
if (!fn) throw new Error(`unknown phase: ${process.argv[2]}`);
const result = await fn();
if (result) console.log(JSON.stringify(result));
