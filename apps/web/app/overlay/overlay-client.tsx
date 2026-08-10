"use client";

import { useEffect, useState } from "react";
import { WS_URL } from "../../lib/api";

type ResponseEvent = { type: "response_plan"; event: { payload: { spoken_ja: string; subtitle_en: string; subtitle_id: string; emotion: string } } };
type SpeechEvent = { type: "speech_event"; event: { event_type: string; payload: { amplitude?: number } } };

export default function OverlayClient() {
  const [status, setStatus] = useState("connecting");
  const [state, setState] = useState("idle");
  const [amplitude, setAmplitude] = useState(0);
  const [captions, setCaptions] = useState({ ja: "", en: "", id: "" });

  useEffect(() => {
    let retry: number | undefined;
    let socket: WebSocket;
    const connect = () => {
      socket = new WebSocket(WS_URL);
      socket.onopen = () => setStatus("online · idle");
      socket.onclose = () => { setStatus("reconnecting"); retry = window.setTimeout(connect, 1500); };
      socket.onerror = () => socket.close();
      socket.onmessage = (message) => {
        const incoming = JSON.parse(message.data) as ResponseEvent | SpeechEvent;
        if (incoming.type === "response_plan") {
          const plan = incoming.event.payload;
          setCaptions({ ja: plan.spoken_ja, en: plan.subtitle_en, id: plan.subtitle_id });
          setState(plan.emotion === "idle" ? "idle" : "thinking");
          setStatus("online · preparing voice");
        } else {
          const payload = incoming.event.payload;
          if (typeof payload.amplitude === "number") setAmplitude(payload.amplitude);
          if (incoming.event.event_type === "SpeechStarted") { setState("speaking"); setStatus("online · speaking"); }
          if (incoming.event.event_type === "SpeechCompleted" || incoming.event.event_type === "SubtitleFallback") {
            setState("idle"); setStatus(incoming.event.event_type === "SubtitleFallback" ? "online · subtitle-only" : "online · idle");
          }
        }
      };
    };
    connect();
    return () => { if (retry) window.clearTimeout(retry); socket?.close(); };
  }, []);

  return <main id="overlay" aria-live="polite">
    <div id="venus" className={`venus ${state}`} style={{ "--amplitude": amplitude } as React.CSSProperties}><span className="halo" /><span className="core">✦</span></div>
    <div className="status">{status}</div>
    <section id="captions" hidden={!captions.ja && !captions.en && !captions.id}><p id="ja">{captions.ja}</p><p id="en">{captions.en}</p><p id="id">{captions.id}</p></section>
  </main>;
}
