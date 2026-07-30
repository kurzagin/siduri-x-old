const health = document.querySelector("#health");
const version = document.querySelector("#version");
const approval = document.querySelector("#approval");
const output = document.querySelector("#output");
const trigger = document.querySelector("#trigger");
const observeRespond = document.querySelector("#observe-respond");
const approveResponse = document.querySelector("#approve-response");
const meEditor = document.querySelector("#me-editor");
const loadMe = document.querySelector("#load-me");
const saveMe = document.querySelector("#save-me");
const meStatus = document.querySelector("#me-status");
const evidenceOutput = document.querySelector("#evidence-output");
const mockObservation = document.querySelector("#mock-observation");
const refreshEvidence = document.querySelector("#refresh-evidence");
const responseEvidence = document.querySelector("#response-evidence");
const memoryProposals = document.querySelector("#memory-proposals");
const refreshProposals = document.querySelector("#refresh-proposals");
const proposalStatus = document.querySelector("#proposal-status");
let pendingCorrelationId = null;
const API = "http://127.0.0.1:8765";
async function loadMeProfile() {
    if (meStatus)
        meStatus.textContent = "Loading…";
    const response = await fetch("http://127.0.0.1:8765/me");
    if (!response.ok)
        throw new Error(`/me returned HTTP ${response.status}`);
    const profile = await response.json();
    if (meEditor)
        meEditor.value = JSON.stringify(profile, null, 2);
    if (meStatus)
        meStatus.textContent = "Loaded";
}
async function loadStatus() {
    const [healthResponse, versionResponse] = await Promise.all([fetch("http://127.0.0.1:8765/health"), fetch("http://127.0.0.1:8765/version")]);
    const healthData = await healthResponse.json();
    const versionData = await versionResponse.json();
    if (health)
        health.textContent = `Orchestrator: ${healthData.status}`;
    if (version)
        version.textContent = `Version: ${versionData.version}`;
}
trigger?.addEventListener("click", async () => {
    const response = await fetch("http://127.0.0.1:8765/dev/mock-response", { method: "POST" });
    const data = await response.json();
    if (approval)
        approval.textContent = data.event.payload.requires_operator_approval ? "Approval required" : "Approved for mock local display";
    if (output)
        output.textContent = JSON.stringify(data.event.payload, null, 2);
});
observeRespond?.addEventListener("click", async () => {
    const response = await fetch("http://127.0.0.1:8765/dev/observe-and-respond", { method: "POST" });
    const data = await response.json();
    if (responseEvidence)
        responseEvidence.textContent = JSON.stringify({
            correlation_id: data.metadata && data.metadata.correlation_id,
            response: data.response,
            citations: data.metadata && data.metadata.citations,
        }, null, 2);
    pendingCorrelationId = data.metadata && typeof data.metadata.correlation_id === "string" ? data.metadata.correlation_id : null;
    if (approveResponse)
        approveResponse.disabled = !pendingCorrelationId;
    if (approval)
        approval.textContent = pendingCorrelationId ? "Approval required before public output" : "No response queued";
    if (output)
        output.textContent = JSON.stringify(data.response, null, 2);
});
approveResponse?.addEventListener("click", async () => {
    if (!pendingCorrelationId)
        return;
    const response = await fetch("http://127.0.0.1:8765/dev/approve-response", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ correlation_id: pendingCorrelationId }) });
    const data = await response.json();
    if (approval)
        approval.textContent = response.ok ? "Approved and published" : String(data.error ?? "Approval failed");
    if (output)
        output.textContent = JSON.stringify(data.response, null, 2);
    pendingCorrelationId = null;
    if (approveResponse)
        approveResponse.disabled = true;
});
loadStatus().catch(() => { if (health)
    health.textContent = "Orchestrator: offline"; });
loadMe?.addEventListener("click", () => { void loadMeProfile().catch((error) => { if (meStatus)
    meStatus.textContent = `Error: ${String(error)}`; }); });
saveMe?.addEventListener("click", async () => {
    try {
        const body = JSON.parse(meEditor?.value ?? "{}");
        const response = await fetch("http://127.0.0.1:8765/me", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (!response.ok)
            throw new Error(await response.text());
        if (meStatus)
            meStatus.textContent = "Saved for this orchestrator session";
    }
    catch (error) {
        if (meStatus)
            meStatus.textContent = `Error: ${String(error)}`;
    }
});
void loadMeProfile().catch((error) => { if (meStatus)
    meStatus.textContent = `Error: ${String(error)}`; });
async function loadEvidence() {
    const [evidenceResponse, observationResponse] = await Promise.all([
        fetch("http://127.0.0.1:8765/evidence"), fetch("http://127.0.0.1:8765/observations"),
    ]);
    const evidence = await evidenceResponse.json();
    const observations = await observationResponse.json();
    if (evidenceOutput)
        evidenceOutput.textContent = JSON.stringify({ evidence, observations }, null, 2);
}
async function loadProposals() {
    const response = await fetch(`${API}/memory/proposals`);
    const data = await response.json();
    const pending = data.proposals.filter((proposal) => proposal.status === "pending");
    if (!memoryProposals)
        return;
    memoryProposals.replaceChildren();
    if (!pending.length) {
        memoryProposals.textContent = "No pending candidates.";
        return;
    }
    for (const proposal of pending) {
        const card = document.createElement("div");
        card.className = "proposal";
        const meta = document.createElement("div");
        meta.className = "proposal-meta";
        meta.textContent = `${proposal.provenance} · ${proposal.sensitivity} · ${proposal.proposal_id}`;
        const editor = document.createElement("textarea");
        editor.value = proposal.content;
        editor.setAttribute("aria-label", `Memory candidate ${proposal.proposal_id}`);
        const edit = document.createElement("button");
        edit.className = "secondary";
        edit.textContent = "Save edit";
        const approve = document.createElement("button");
        approve.textContent = "Approve";
        const reject = document.createElement("button");
        reject.className = "secondary";
        reject.textContent = "Reject";
        edit.addEventListener("click", async () => { await proposalAction("/memory/proposals/update", { proposal_id: proposal.proposal_id, content: editor.value }); });
        approve.addEventListener("click", async () => { await proposalAction("/memory/proposals/approve", { proposal_id: proposal.proposal_id }); });
        reject.addEventListener("click", async () => { await proposalAction("/memory/proposals/reject", { proposal_id: proposal.proposal_id }); });
        card.append(meta, editor, edit, document.createTextNode(" "), approve, document.createTextNode(" "), reject);
        memoryProposals.append(card);
    }
}
async function proposalAction(path, body) {
    const response = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (proposalStatus)
        proposalStatus.textContent = response.ok ? "Updated" : `Error: ${await response.text()}`;
    await loadProposals();
}
mockObservation?.addEventListener("click", async () => {
    await fetch("http://127.0.0.1:8765/dev/mock-observation", { method: "POST" });
    await loadEvidence();
});
refreshEvidence?.addEventListener("click", () => { void loadEvidence(); });
void loadEvidence().catch(() => { if (evidenceOutput)
    evidenceOutput.textContent = "Evidence service offline"; });
refreshProposals?.addEventListener("click", () => { void loadProposals(); });
void loadProposals().catch(() => { if (memoryProposals)
    memoryProposals.textContent = "Memory service offline"; });
export {};
