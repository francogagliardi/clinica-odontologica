// Minimal MCP stdio client: initialize -> tools/list -> tools/call
// Usage: node mcp-driver.js <tool> <jsonArgs>
const { spawn } = require("child_process");
const fs = require("fs");

const tool = process.argv[2] || "list_schemas";
const args = JSON.parse(process.env.TOOL_ARGS_JSON || process.argv[3] || "{}");

const cmdSpec = process.env.MCP_CMD || "uvx postgres-mcp --access-mode=restricted";
const parts = cmdSpec.split(" ");
const proc = spawn(parts[0], parts.slice(1), {
  shell: true,
  env: { ...process.env },
});

let buffer = "";
const pending = new Map();
const log = [];

proc.stdout.on("data", (chunk) => {
  buffer += chunk.toString("utf8");
  let idx;
  while ((idx = buffer.indexOf("\n")) >= 0) {
    const line = buffer.slice(0, idx).trim();
    buffer = buffer.slice(idx + 1);
    if (!line) continue;
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      continue;
    }
    log.push({ direction: "server->client", message: msg });
    if (msg.id !== undefined && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
  }
});

proc.stderr.on("data", (c) => log.push({ direction: "stderr", text: c.toString() }));

function send(message) {
  log.push({ direction: "client->server", message });
  proc.stdin.write(JSON.stringify(message) + "\n");
}

function request(id, method, params) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timeout on ${method}`)), 120000);
    pending.set(id, (msg) => {
      clearTimeout(timer);
      resolve(msg);
    });
    send({ jsonrpc: "2.0", id, method, params });
  });
}

(async () => {
  const init = await request(1, "initialize", {
    protocolVersion: "2025-06-18",
    capabilities: {},
    clientInfo: { name: "clinica-odontologica-evidence", version: "1.0.0" },
  });
  send({ jsonrpc: "2.0", method: "notifications/initialized" });
  const tools = await request(2, "tools/list", {});
  const call = await request(3, "tools/call", { name: tool, arguments: args });

  const summary = {
    serverInfo: init.result?.serverInfo,
    protocolVersion: init.result?.protocolVersion,
    tools: (tools.result?.tools || []).map((t) => ({ name: t.name, description: t.description })),
    call: { name: tool, arguments: args, isError: call.result?.isError, content: call.result?.content },
  };
  fs.writeFileSync(process.env.OUT, JSON.stringify({ summary, log }, null, 2));
  console.log(JSON.stringify(summary, null, 2));
  proc.stdin.end();
  setTimeout(() => process.exit(0), 500);
})().catch((error) => {
  console.error("DRIVER ERROR:", error.message);
  console.error(JSON.stringify(log.slice(-5), null, 2));
  process.exit(1);
});
