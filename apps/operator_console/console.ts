const health = document.querySelector<HTMLParagraphElement>("#health");
const version = document.querySelector<HTMLParagraphElement>("#version");
const approval = document.querySelector<HTMLParagraphElement>("#approval");
const output = document.querySelector<HTMLPreElement>("#output");
const trigger = document.querySelector<HTMLButtonElement>("#trigger");
const observeRespond = document.querySelector<HTMLButtonElement>("#observe-respond");
const approveResponse = document.querySelector<HTMLButtonElement>("#approve-response");
const meEditor = document.querySelector<HTMLTextAreaElement>("#me-editor");
const loadMe = document.querySelector<HTMLButtonElement>("#load-me");
const saveMe = document.querySelector<HTMLButtonElement>("#save-me");
const meStatus = document.querySelector<HTMLSpanElement>("#me-status");
const evidenceOutput = document.querySelector<HTMLPreElement>("#evidence-output");
const mockObservation = document.querySelector<HTMLButtonElement>("#mock-observation");
const refreshEvidence = document.querySelector<HTMLButtonElement>("#refresh-evidence");
const responseEvidence = document.querySelector<HTMLPreElement>("#response-evidence");
const memoryProposals = document.querySelector<HTMLDivElement>("#memory-proposals");
const refreshProposals = document.querySelector<HTMLButtonElement>("#refresh-proposals");
const proposalStatus = document.querySelector<HTMLSpanElement>("#proposal-status");
const refreshPlatforms = document.querySelector<HTMLButtonElement>("#refresh-platforms");
const platformEvents = document.querySelector<HTMLPreElement>("#platform-events");
const platformActions = document.querySelector<HTMLDivElement>("#platform-actions");
const suggestPlatformReply = document.querySelector<HTMLButtonElement>("#suggest-platform-reply");
const platformStatus = document.querySelector<HTMLSpanElement>("#platform-status");
let pendingCorrelationId: string | null = null;
const API = "http://127.0.0.1:8765";

async function loadMeProfile(): Promise<void> {
  if (meStatus) meStatus.textContent = "Loading…";
  const response = await fetch("http://127.0.0.1:8765/me");
  if (!response.ok) throw new Error(`/me returned HTTP ${response.status}`);
  const profile = await response.json() as Record<string, unknown>;
  if (meEditor) meEditor.value = JSON.stringify(profile, null, 2);
  if (meStatus) meStatus.textContent = "Loaded";
}

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
observeRespond?.addEventListener("click", async () => {
  const response = await fetch("http://127.0.0.1:8765/dev/observe-and-respond", { method: "POST" });
  const data = await response.json() as Record<string, unknown>;
  if (responseEvidence) responseEvidence.textContent = JSON.stringify({
    correlation_id: data.metadata && (data.metadata as Record<string, unknown>).correlation_id,
    response: data.response,
    citations: data.metadata && (data.metadata as Record<string, unknown>).citations,
  }, null, 2);
  pendingCorrelationId = data.metadata && typeof (data.metadata as Record<string, unknown>).correlation_id === "string" ? (data.metadata as Record<string, string>).correlation_id : null;
  if (approveResponse) approveResponse.disabled = !pendingCorrelationId;
  if (approval) approval.textContent = pendingCorrelationId ? "Approval required before public output" : "No response queued";
  if (output) output.textContent = JSON.stringify(data.response, null, 2);
});
approveResponse?.addEventListener("click", async () => {
  if (!pendingCorrelationId) return;
  const response = await fetch("http://127.0.0.1:8765/dev/approve-response", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ correlation_id: pendingCorrelationId }) });
  const data = await response.json() as Record<string, unknown>;
  if (approval) approval.textContent = response.ok ? "Approved and published" : String(data.error ?? "Approval failed");
  if (output) output.textContent = JSON.stringify(data.response, null, 2);
  pendingCorrelationId = null;
  if (approveResponse) approveResponse.disabled = true;
});
loadStatus().catch(() => { if (health) health.textContent = "Orchestrator: offline"; });
loadMe?.addEventListener("click", () => { void loadMeProfile().catch((error) => { if (meStatus) meStatus.textContent = `Error: ${String(error)}`; }); });
saveMe?.addEventListener("click", async () => {
  try {
    const body = JSON.parse(meEditor?.value ?? "{}") as Record<string, unknown>;
    const response = await fetch("http://127.0.0.1:8765/me", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!response.ok) throw new Error(await response.text());
    if (meStatus) meStatus.textContent = "Saved for this orchestrator session";
  } catch (error) {
    if (meStatus) meStatus.textContent = `Error: ${String(error)}`;
  }
});
void loadMeProfile().catch((error) => { if (meStatus) meStatus.textContent = `Error: ${String(error)}`; });

async function loadEvidence(): Promise<void> {
  const [evidenceResponse, observationResponse] = await Promise.all([
    fetch("http://127.0.0.1:8765/evidence"), fetch("http://127.0.0.1:8765/observations"),
  ]);
  const evidence = await evidenceResponse.json() as Record<string, unknown>;
  const observations = await observationResponse.json() as Record<string, unknown>;
  if (evidenceOutput) evidenceOutput.textContent = JSON.stringify({ evidence, observations }, null, 2);
}

type Proposal = { proposal_id: string; content: string; provenance: string; sensitivity: string; allowed_audiences: string[]; status: string };
async function loadProposals(): Promise<void> {
  const response = await fetch(`${API}/memory/proposals`);
  const data = await response.json() as { proposals: Proposal[] };
  const pending = data.proposals.filter((proposal) => proposal.status === "pending");
  if (!memoryProposals) return;
  memoryProposals.replaceChildren();
  if (!pending.length) { memoryProposals.textContent = "No pending candidates."; return; }
  for (const proposal of pending) {
    const card = document.createElement("div"); card.className = "proposal";
    const meta = document.createElement("div"); meta.className = "proposal-meta";
    meta.textContent = `${proposal.provenance} · ${proposal.sensitivity} · ${proposal.proposal_id}`;
    const editor = document.createElement("textarea"); editor.value = proposal.content; editor.setAttribute("aria-label", `Memory candidate ${proposal.proposal_id}`);
    const edit = document.createElement("button"); edit.className = "secondary"; edit.textContent = "Save edit";
    const approve = document.createElement("button"); approve.textContent = "Approve";
    const reject = document.createElement("button"); reject.className = "secondary"; reject.textContent = "Reject";
    edit.addEventListener("click", async () => { await proposalAction("/memory/proposals/update", { proposal_id: proposal.proposal_id, content: editor.value }); });
    approve.addEventListener("click", async () => { await proposalAction("/memory/proposals/approve", { proposal_id: proposal.proposal_id }); });
    reject.addEventListener("click", async () => { await proposalAction("/memory/proposals/reject", { proposal_id: proposal.proposal_id }); });
    card.append(meta, editor, edit, document.createTextNode(" "), approve, document.createTextNode(" "), reject); memoryProposals.append(card);
  }
}
async function proposalAction(path: string, body: Record<string, unknown>): Promise<void> {
  const response = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (proposalStatus) proposalStatus.textContent = response.ok ? "Updated" : `Error: ${await response.text()}`;
  await loadProposals();
}
type PlatformAction = { action_id: string; platform: string; target_id: string; text: string; status: string; evidence_ids: string[] };
async function loadPlatforms(): Promise<void> {
  const [eventsResponse, actionsResponse] = await Promise.all([fetch(`${API}/platforms/events`), fetch(`${API}/platforms/actions`)]);
  const events = await eventsResponse.json() as { events: unknown[] };
  const actions = await actionsResponse.json() as { actions: PlatformAction[] };
  if (platformEvents) platformEvents.textContent = JSON.stringify(events, null, 2);
  if (!platformActions) return;
  platformActions.replaceChildren();
  const pending = actions.actions.filter((action) => action.status === "proposed");
  if (!pending.length) { platformActions.textContent = "No pending outbound suggestions."; return; }
  for (const action of pending) {
    const card = document.createElement("div"); card.className = "proposal";
    const meta = document.createElement("div"); meta.className = "proposal-meta"; meta.textContent = `${action.platform} · ${action.target_id} · ${action.action_id}`;
    const editor = document.createElement("textarea"); editor.value = action.text; editor.setAttribute("aria-label", `Platform action ${action.action_id}`);
    const approve = document.createElement("button"); approve.textContent = "Approve";
    const reject = document.createElement("button"); reject.className = "secondary"; reject.textContent = "Reject";
    approve.addEventListener("click", async () => { await platformAction("/platforms/actions/approve", { action_id: action.action_id, text: editor.value }); });
    reject.addEventListener("click", async () => { await platformAction("/platforms/actions/reject", { action_id: action.action_id }); });
    card.append(meta, editor, approve, document.createTextNode(" "), reject); platformActions.append(card);
  }
}
async function platformAction(path: string, body: Record<string, unknown>): Promise<void> {
  await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  await loadPlatforms();
}
suggestPlatformReply?.addEventListener("click", async () => {
  try {
    const response = await fetch(`${API}/platforms/events`);
    const data = await response.json() as { events: Array<{ event_id: string }> };
    const newest = data.events.at(-1);
    if (!newest) throw new Error("No platform event is available");
    const suggestion = await fetch(`${API}/platforms/actions/suggest`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ event_id: newest.event_id, language: "en" }) });
    if (!suggestion.ok) throw new Error(await suggestion.text());
    if (platformStatus) platformStatus.textContent = "Reply suggestion queued for approval";
    await loadPlatforms();
  } catch (error) {
    if (platformStatus) platformStatus.textContent = `Error: ${String(error)}`;
  }
});
mockObservation?.addEventListener("click", async () => {
  await fetch("http://127.0.0.1:8765/dev/mock-observation", { method: "POST" });
  await loadEvidence();
});
refreshEvidence?.addEventListener("click", () => { void loadEvidence(); });
refreshPlatforms?.addEventListener("click", () => { void loadPlatforms(); });
void loadPlatforms().catch(() => { if (platformEvents) platformEvents.textContent = "Platform service offline"; });
void loadEvidence().catch(() => { if (evidenceOutput) evidenceOutput.textContent = "Evidence service offline"; });
refreshProposals?.addEventListener("click", () => { void loadProposals(); });
void loadProposals().catch(() => { if (memoryProposals) memoryProposals.textContent = "Memory service offline"; });

export {};
