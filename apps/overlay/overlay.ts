type ResponseEvent = { type: "response_plan"; event: { payload: { spoken_ja: string; subtitle_en: string; subtitle_id: string; emotion: string } } };
type SpeechEvent = { type: "speech_event"; event: { event_type: string; payload: { amplitude?: number; status?: string } } };

const status = document.querySelector<HTMLDivElement>("#status");
const venus = document.querySelector<HTMLDivElement>("#venus");
const captions = document.querySelector<HTMLElement>("#captions");
const ja = document.querySelector<HTMLParagraphElement>("#ja");
const en = document.querySelector<HTMLParagraphElement>("#en");
const id = document.querySelector<HTMLParagraphElement>("#id");

function connect(): void {
  const socket = new WebSocket("ws://127.0.0.1:8765/ws");
  socket.onopen = () => { if (status) status.textContent = "online · idle"; };
  socket.onclose = () => { if (status) status.textContent = "reconnecting"; window.setTimeout(connect, 1500); };
  socket.onerror = () => socket.close();
  socket.onmessage = (message: MessageEvent<string>) => {
    const incoming = JSON.parse(message.data) as ResponseEvent | SpeechEvent;
    if (incoming.type === "response_plan") {
      const plan = incoming.event.payload;
      if (ja) ja.textContent = plan.spoken_ja;
      if (en) en.textContent = plan.subtitle_en;
      if (id) id.textContent = plan.subtitle_id;
      if (captions) captions.hidden = false;
      if (venus) venus.className = `venus ${plan.emotion === "idle" ? "idle" : "thinking"}`;
      if (status) status.textContent = "online · preparing voice";
      return;
    }
    if (incoming.type === "speech_event") {
      const payload = incoming.event.payload;
      if (typeof payload.amplitude === "number" && venus) venus.style.setProperty("--amplitude", String(payload.amplitude));
      if (incoming.event.event_type === "SpeechStarted") {
        if (venus) venus.className = "venus speaking";
        if (status) status.textContent = "online · speaking";
      } else if (incoming.event.event_type === "SpeechCompleted" || incoming.event.event_type === "SubtitleFallback") {
        if (venus) venus.className = "venus idle";
        if (status) status.textContent = incoming.event.event_type === "SubtitleFallback" ? "online · subtitle-only" : "online · idle";
      }
    }
  };
}
connect();

export {};
