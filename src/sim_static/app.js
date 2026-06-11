import { PerspectiveCamera, Scene, WebGLRenderer } from "/sim_static/three-lite.js";

const canvas = document.getElementById("threeScene");
const renderer = new WebGLRenderer({ canvas });
const scene = new Scene();
const camera = new PerspectiveCamera();
let latestSnapshot = null;

scene.add({
  draw(ctx, width, height) {
    if (!latestSnapshot) return;
    drawWorld(ctx, width, height, latestSnapshot.body.sim);
  },
});

function resize() {
  const rect = canvas.getBoundingClientRect();
  renderer.setSize(Math.max(320, Math.floor(rect.width)), Math.max(260, Math.floor(rect.height)));
}

function worldToScreen(x, z, world, width, height) {
  const sx = width / 2 + (x / world.width) * width * 0.72;
  const sy = height / 2 + (z / world.depth) * height * 0.72;
  return [sx, sy];
}

function drawWorld(ctx, width, height, sim) {
  const world = sim.world;
  const robot = sim.robot;
  const pose = robot.pose;
  ctx.strokeStyle = "#aab4c0";
  ctx.lineWidth = 1;
  for (let i = -4; i <= 4; i += 1) {
    const x = width / 2 + (i / world.width) * width * 0.72;
    const y = height / 2 + (i / world.depth) * height * 0.72;
    ctx.beginPath();
    ctx.moveTo(x, height * 0.12);
    ctx.lineTo(x, height * 0.88);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(width * 0.12, y);
    ctx.lineTo(width * 0.88, y);
    ctx.stroke();
  }

  for (const obstacle of world.obstacles) {
    const [ox, oy] = worldToScreen(obstacle.x, obstacle.z, world, width, height);
    ctx.fillStyle = "#7b8795";
    ctx.beginPath();
    ctx.arc(ox, oy, obstacle.radius * 32, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#202833";
    ctx.fillText(obstacle.id, ox + 12, oy - 12);
  }

  const [rx, ry] = worldToScreen(pose.x, pose.z, world, width, height);
  ctx.save();
  ctx.translate(rx, ry);
  ctx.rotate((pose.heading_degrees * Math.PI) / 180);
  ctx.fillStyle = "#385f71";
  ctx.fillRect(-28, -38, 56, 76);
  ctx.fillStyle = "#4fa3c7";
  ctx.beginPath();
  ctx.arc(0, -52, 24, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "#f6c85f";
  ctx.lineWidth = 5;
  ctx.beginPath();
  ctx.moveTo(-28, -4);
  ctx.lineTo(-54, -8 + robot.channels.left_flutter);
  ctx.moveTo(28, -4);
  ctx.lineTo(54, -8 + robot.channels.right_flutter);
  ctx.stroke();
  ctx.strokeStyle = "#10202a";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(0, -52);
  ctx.lineTo(robot.channels.head_yaw * 0.8, -76);
  ctx.stroke();
  ctx.restore();

  ctx.fillStyle = "#202833";
  ctx.fillText(`expression: ${robot.expression}`, 16, 24);
  ctx.fillText(`camera y=${camera.position.y}`, 16, 42);
}

async function refresh() {
  const response = await fetch("/sim/state");
  latestSnapshot = await response.json();
  const readiness = await fetch("/sim/readiness").then((r) => r.json());
  renderPanels(latestSnapshot, readiness);
  resize();
  renderer.render(scene, camera);
}

function renderPanels(snapshot, readiness) {
  const sim = snapshot.body.sim;
  const last = snapshot.last_event || {};
  document.getElementById("backendBadge").textContent = `backend: ${snapshot.body.backend}`;
  document.getElementById("gatePanel").textContent = JSON.stringify(last.gate || {}, null, 2);
  document.getElementById("statusPanel").textContent = JSON.stringify({
    state: snapshot.state,
    robot: sim.robot,
  }, null, 2);
  document.getElementById("sensorPanel").textContent = JSON.stringify(sim.sensors, null, 2);
  document.getElementById("readinessPanel").textContent = JSON.stringify(readiness, null, 2);
  const eventLog = document.getElementById("eventLog");
  eventLog.innerHTML = "";
  for (const event of snapshot.events.slice(-12).reverse()) {
    const item = document.createElement("li");
    item.textContent = `${event.raw_input} -> ${event.action} (${event.approved ? "approved" : "blocked"})`;
    eventLog.appendChild(item);
  }
}

async function sendCommand(command) {
  await fetch("/sim/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  });
  await refresh();
}

document.getElementById("commandForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await sendCommand(document.getElementById("commandInput").value);
});

document.getElementById("resetSim").addEventListener("click", async () => {
  await fetch("/sim/reset", { method: "POST" });
  document.getElementById("proposalPanel").textContent = "{}";
  document.getElementById("replayPanel").textContent = "{}";
  await refresh();
});

document.getElementById("quickCommands").addEventListener("click", async (event) => {
  const command = event.target.getAttribute("data-command");
  if (command) {
    document.getElementById("commandInput").value = command;
    await sendCommand(command);
  }
});

document.getElementById("exportSim").addEventListener("click", async () => {
  const exported = await fetch("/sim/export").then((r) => r.json());
  document.getElementById("replayPanel").textContent = JSON.stringify({
    export_schema: exported.export_schema,
    event_count: exported.event_log.length,
  }, null, 2);
});

document.getElementById("runScenarios").addEventListener("click", async () => {
  const result = await fetch("/sim/scenarios/run-all", { method: "POST" }).then((r) => r.json());
  document.getElementById("replayPanel").textContent = JSON.stringify(result, null, 2);
});

document.getElementById("previewProposal").addEventListener("click", async () => {
  const command = document.getElementById("commandInput").value;
  const result = await fetch("/sim/proposals/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  }).then((r) => r.json());
  document.getElementById("proposalPanel").textContent = JSON.stringify(result, null, 2);
});

window.addEventListener("resize", refresh);
refresh();
