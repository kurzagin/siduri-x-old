"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  spokenJa?: string;
  evidenceIds?: string[];
  createdAt: number;
};

type Conversation = {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
};

type ChatResponse = { response: { spoken_ja: string; subtitle_en: string; evidence_ids: string[] } };

const API = "http://127.0.0.1:8765";
const STORAGE_KEY = "siduri.chat.conversations.v1";

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

function formatTime(timestamp: number): string {
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(timestamp);
}

function readConversations(): Conversation[] {
  try {
    const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "[]") as unknown;
    return Array.isArray(value) ? value as Conversation[] : [];
  } catch {
    return [];
  }
}

export default function ChatClient() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("connecting");
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const messagesRef = useRef<HTMLDivElement>(null);

  const activeConversation = useMemo(() => conversations.find((item) => item.id === activeId) ?? null, [activeId, conversations]);

  useEffect(() => {
    const stored = readConversations();
    setConversations(stored);
    setActiveId(stored[0]?.id ?? null);
    setReady(true);
    fetch(`${API}/health`).then(() => setStatus("online")).catch(() => setStatus("offline"));
  }, []);

  useEffect(() => {
    if (ready) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations, ready]);

  useEffect(() => {
    messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: "smooth" });
  }, [activeId, activeConversation?.messages.length, busy]);

  function createConversation(): Conversation {
    return { id: newId(), title: "New conversation", messages: [], updatedAt: Date.now() };
  }

  function updateConversation(id: string, update: (conversation: Conversation) => Conversation): void {
    setConversations((current) => current.map((conversation) => conversation.id === id ? update(conversation) : conversation));
  }

  function startNewChat(): void {
    const conversation = createConversation();
    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
    setMessage("");
    setStatus("online");
  }

  function removeConversation(id: string): void {
    setConversations((current) => current.filter((conversation) => conversation.id !== id));
    if (activeId === id) {
      const next = conversations.find((conversation) => conversation.id !== id);
      setActiveId(next?.id ?? null);
    }
  }

  async function submit(event: FormEvent): Promise<void> {
    event.preventDefault();
    const content = message.trim();
    if (!content || busy) return;

    let conversation = activeConversation;
    if (!conversation) {
      conversation = createConversation();
      setConversations((current) => [conversation as Conversation, ...current]);
      setActiveId(conversation.id);
    }

    const userMessage: ChatMessage = { id: newId(), role: "user", content, createdAt: Date.now() };
    const nextMessages = [...conversation.messages, userMessage];
    const title = conversation.messages.length === 0 ? content.slice(0, 42) : conversation.title;
    updateConversation(conversation.id, (current) => ({ ...current, title, messages: nextMessages, updatedAt: Date.now() }));
    setMessage("");
    setBusy(true);
    setStatus("thinking");

    try {
      const response = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: content, history: nextMessages.slice(-20).map(({ role, content: text }) => ({ role, content: text })) }),
      });
      const data = await response.json() as ChatResponse | { error: string };
      if (!response.ok || !("response" in data)) throw new Error("error" in data ? data.error : "chat unavailable");
      const plan = data.response;
      const assistant: ChatMessage = { id: newId(), role: "assistant", content: plan.subtitle_en, spokenJa: plan.spoken_ja, evidenceIds: plan.evidence_ids, createdAt: Date.now() };
      updateConversation(conversation.id, (current) => ({ ...current, messages: [...current.messages, assistant], updatedAt: Date.now() }));
      setStatus("online");
    } catch (error) {
      const assistant: ChatMessage = { id: newId(), role: "assistant", content: `I couldn’t reach the orchestrator. ${String(error)}`, createdAt: Date.now() };
      updateConversation(conversation.id, (current) => ({ ...current, messages: [...current.messages, assistant], updatedAt: Date.now() }));
      setStatus("offline");
    } finally {
      setBusy(false);
    }
  }

  const messages = activeConversation?.messages ?? [];
  const evidenceCount = messages.at(-1)?.evidenceIds?.length ?? 0;

  return <div className={`chat-app ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
    <aside className="chat-sidebar" aria-label="Conversation history">
      <div className="chat-sidebar-top"><a className="chat-brand" href="/chat"><span className="chat-brand-mark">S</span><span>SIDURI</span></a><button className="sidebar-collapse" type="button" onClick={() => setSidebarCollapsed((value) => !value)} aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}>{sidebarCollapsed ? "→" : "←"}</button></div>
      <button className="new-chat-button" type="button" onClick={startNewChat}><span>＋</span> New conversation</button>
      <div className="history-heading"><span>Recent conversations</span><span>{conversations.length}</span></div>
      <div className="conversation-list">
        {!ready ? <p className="history-empty">Loading history…</p> : conversations.length === 0 ? <p className="history-empty">Your private conversations will appear here.</p> : conversations.slice().sort((a, b) => b.updatedAt - a.updatedAt).map((conversation) => <div className={`conversation-row ${conversation.id === activeId ? "selected" : ""}`} key={conversation.id}><button type="button" className="conversation-select" onClick={() => setActiveId(conversation.id)}><span className="conversation-title">{conversation.title}</span><span className="conversation-date">{formatTime(conversation.updatedAt)}</span></button><button type="button" className="conversation-delete" onClick={() => removeConversation(conversation.id)} aria-label={`Delete ${conversation.title}`}>×</button></div>)}
      </div>
      <div className="sidebar-footer"><a className="sidebar-console" href="/operator"><span>⌘</span><span>Operator console</span><b>↗</b></a></div>
    </aside>

    <main className="chat-workspace">
      <div className="chat-top-status"><span className="connection-pill"><span className={`status-light ${status === "online" ? "online" : ""}`} />{status}</span></div>
      <section className="conversation-surface" aria-label="Private chat">
        <div ref={messagesRef} className="conversation-scroll" aria-live="polite">
          {messages.length === 0 ? <div className="chat-empty-state"><div className="siduri-orb">✦</div><h2>What shall we record today?</h2><p>Talk with Siduri privately. Conversations stay in this browser unless you choose to clear them.</p><div className="starter-prompts"><button type="button" onClick={() => setMessage("What should we remember from today?")}>Remember something</button><button type="button" onClick={() => setMessage("Tell me what you know about this scene.")}>Explore an observation</button></div></div> : messages.map((item) => <article className={`platform-message ${item.role}`} key={item.id}><div className="message-avatar">{item.role === "user" ? "K" : "S"}</div><div className="message-body"><div className="message-meta"><span>{item.role === "user" ? "You" : "Siduri"}</span><time>{formatTime(item.createdAt)}</time></div><p className="message-primary">{item.role === "assistant" ? item.spokenJa ?? item.content : item.content}</p>{item.role === "assistant" && item.spokenJa && <p className="message-translation">{item.content}</p>}{item.evidenceIds && item.evidenceIds.length > 0 && <span className="evidence-chip">{item.evidenceIds.length} evidence link{item.evidenceIds.length === 1 ? "" : "s"}</span>}</div></article>)}
          {busy && <div className="platform-message assistant thinking-message"><div className="message-avatar">S</div><div className="message-body"><div className="message-meta"><span>Siduri</span><span className="thinking-label">thinking</span></div><div className="thinking-dots"><i /><i /><i /></div></div></div>}
        </div>
        <form className="platform-composer" onSubmit={submit}><textarea value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Message Siduri…" rows={1} maxLength={4000} aria-label="Message Siduri" disabled={busy} /><div className="composer-bottom"><span>Private local session · {evidenceCount ? `${evidenceCount} evidence link${evidenceCount === 1 ? "" : "s"}` : "No evidence attached"}</span><button type="submit" disabled={busy || !message.trim()} aria-label="Send message">{busy ? "" : "↑"}</button></div></form>
      </section>
      <p className="chat-disclaimer">Siduri can be uncertain. Verify important details against the evidence.</p>
    </main>
  </div>;
}
