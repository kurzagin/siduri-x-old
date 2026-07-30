type ChatMessage = { role: "user" | "assistant"; content: string; spokenJa?: string; subtitleId?: string; evidenceIds?: string[] };
type ChatResponse = { response: { semantic_summary: string; spoken_ja: string; subtitle_en: string; subtitle_id: string; confidence: number; evidence_ids: string[] }; metadata: { observation_count: number; evidence_ids: string[] } };

const messages = document.querySelector<HTMLDivElement>("#messages");
const composer = document.querySelector<HTMLFormElement>("#composer");
const input = document.querySelector<HTMLTextAreaElement>("#message");
const send = document.querySelector<HTMLButtonElement>("#send");
const status = document.querySelector<HTMLSpanElement>("#status");
const evidence = document.querySelector<HTMLSpanElement>("#evidence");
const history: ChatMessage[] = [];

function addMessage(message: ChatMessage, role: "user" | "assistant"): void {
  const article = document.createElement("article");
  article.className = `message ${role === "user" ? "user-message" : "siduri-message"}`;
  const mark = document.createElement("div"); mark.className = "message-mark"; mark.textContent = role === "user" ? "K" : "S";
  const body = document.createElement("div");
  const label = document.createElement("p"); label.className = "message-label"; label.textContent = role === "user" ? "MASTER" : "SIDURI";
  const primary = document.createElement("p"); primary.textContent = role === "user" ? message.content : (message.spokenJa ?? message.content);
  body.append(label, primary);
  if (role === "assistant" && message.content) { const translation = document.createElement("p"); translation.className = "translation"; translation.textContent = message.content; body.append(translation); }
  article.append(mark, body); messages?.append(article); messages?.scrollTo({ top: messages.scrollHeight, behavior: "smooth" });
}

input?.addEventListener("input", () => { if (input) { input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 150)}px`; } });
input?.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); composer?.requestSubmit(); } });
composer?.addEventListener("submit", async (event) => {
  event.preventDefault(); const content = input?.value.trim() ?? ""; if (!content || !send) return;
  addMessage({ role: "user", content }, "user"); history.push({ role: "user", content });
  if (input) { input.value = ""; input.style.height = "auto"; } send.disabled = true; if (status) status.textContent = "thinking";
  try {
    const response = await fetch("http://127.0.0.1:8765/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: content, history: history.slice(-20) }) });
    const data = await response.json() as ChatResponse | { error: string }; if (!response.ok || !("response" in data)) throw new Error("error" in data ? data.error : "chat unavailable");
    const plan = data.response; const assistant: ChatMessage = { role: "assistant", content: plan.subtitle_en, spokenJa: plan.spoken_ja, subtitleId: plan.subtitle_id, evidenceIds: plan.evidence_ids };
    addMessage(assistant, "assistant"); history.push(assistant); if (status) status.textContent = "online"; if (evidence) evidence.textContent = plan.evidence_ids.length ? `${plan.evidence_ids.length} evidence link${plan.evidence_ids.length === 1 ? "" : "s"}` : "No observation evidence attached";
  } catch (error) { addMessage({ role: "assistant", content: `I couldn’t reach the orchestrator. ${String(error)}` }, "assistant"); if (status) status.textContent = "offline"; }
  finally { send.disabled = false; input?.focus(); }
});
fetch("http://127.0.0.1:8765/health").then(() => { if (status) status.textContent = "online"; }).catch(() => { if (status) status.textContent = "offline"; });

export {};
