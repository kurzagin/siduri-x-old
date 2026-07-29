const health = document.querySelector<HTMLParagraphElement>("#health");
const version = document.querySelector<HTMLParagraphElement>("#version");
const approval = document.querySelector<HTMLParagraphElement>("#approval");
const output = document.querySelector<HTMLPreElement>("#output");
const trigger = document.querySelector<HTMLButtonElement>("#trigger");

async function loadStatus(): Promise<void> {
  const [healthResponse, versionResponse] = await Promise.all([fetch("http://127.0.0.1:8765/health"), fetch("http://127.0.0.1:8765/version")]);
  const healthData = await healthResponse.json() as { status: string };
  const versionData = await versionResponse.json() as { version: string };
  if (health) health.textContent = `Orchestrator: ${healthData.status}`;
  if (version) version.textContent = `Version: ${versionData.version}`;
}
trigger?.addEventListener("click", async () => {
  const response = await fetch("http://127.0.0.1:8765/dev/mock-response", { method: "POST" });
  const data = await response.json() as { event: { payload: { requires_operator_approval: boolean } } };
  if (approval) approval.textContent = data.event.payload.requires_operator_approval ? "Approval required" : "Approved for mock local display";
  if (output) output.textContent = JSON.stringify(data.event.payload, null, 2);
});
loadStatus().catch(() => { if (health) health.textContent = "Orchestrator: offline"; });

export {};
