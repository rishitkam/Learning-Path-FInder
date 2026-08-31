"use client";
import { FormEvent, useState } from "react";
import { Bot, Send, Sparkles } from "lucide-react";
import { chat, defaultProfile, type PathData, type Profile } from "@/lib/api";
import { useTurns } from "@/lib/store";

const GREETING = "Tell me what you want to learn and how many hours you have each week. I’ll build your route from real prerequisites and courses.";

export default function Copilot({ data, onPath }: { data: PathData | null; onPath: (data: PathData) => void }) {
  // The thread lives in the shared session, so both pages show one conversation and it survives a reload.
  const [turns, setTurns] = useTurns();
  const [input, setInput] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);
  // The header used to say "LLM connected" unconditionally, next to a green dot, even when every
  // request was failing. A status light that cannot go out is decoration, not status.
  const [reachable, setReachable] = useState(true);
  const shown = turns.length ? turns : [{ role: "assistant" as const, content: GREETING }];

  async function send(event: FormEvent | { preventDefault: () => void }) {
    event.preventDefault();
    const message = input.trim();
    if (!message || busy) return;
    setInput("");
    const asked = [...turns, { role: "user" as const, content: message }];
    setTurns(asked);
    setBusy(true);
    try {
      const activeProfile = data?.profile ?? profile;
      const result = await chat(message, activeProfile, data?.state.completed ?? [], data?.state.blocked ?? [], turns);
      if (result.profile) setProfile({ ...defaultProfile, ...result.profile });
      if (result.data) { setProfile(result.data.profile); onPath(result.data); }
      setTurns([...asked, { role: "assistant", content: result.reply }]);
      setReachable(true);
    } catch (reason) {
      setReachable(false);
      setTurns([...asked, { role: "assistant", content: reason instanceof Error ? reason.message : "I couldn’t reach the co-pilot." }]);
    } finally { setBusy(false); }
  }

  return <aside className="copilot">
    <div className="copilot-head">
      <div className="copilot-icon"><Bot size={17}/></div>
      <div><p>ALMA CO-PILOT</p><small className={reachable ? "" : "pill-down"}><i/> {reachable ? "LLM connected" : "Cannot reach ALMA"}</small></div>
    </div>
    <div className="chat-thread">
      {shown.map((turn, index) => <div className={`chat-message ${turn.role}`} key={index}>
        {turn.role === "assistant" && <Sparkles size={13}/>}<span>{turn.content}</span>
      </div>)}
      {busy && <div className="chat-typing"><i/><i/><i/></div>}
    </div>
    <form className="chat-form" onSubmit={send}>
      <input value={input} onChange={(event) => setInput(event.target.value)}
             onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); send(event); } }}
             placeholder="Tell ALMA your goal…"/>
      <button aria-label="Send message" disabled={busy || !input.trim()}><Send size={15}/></button>
    </form>
  </aside>;
}
