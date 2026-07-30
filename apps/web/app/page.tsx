import Link from "next/link";

export default function HomePage() {
  return <main className="web-route" style={{ padding: "12rem 2rem", textAlign: "center" }}>
    <p className="eyebrow">SIDURI / LOCAL-FIRST COMPANION</p>
    <h1>Stay a while.</h1>
    <p className="muted">Choose a private surface.</p>
    <p><Link href="/chat">Chat</Link> · <Link href="/operator">Operator Console</Link> · <Link href="/overlay">Overlay</Link></p>
  </main>;
}
