"use client";
import { useEffect, useState } from "react";
import { Play, ArrowUpRight, Clock3, BrainCircuit, Flame, LoaderCircle, Check, TrendingDown, TrendingUp, X } from "lucide-react";
import { explainCurrent, type FeedbackEvent, type PathData } from "@/lib/api";

// Every one of these rebuilds the path from the learner state, so the roadmap reacts to all of them,
// not just to finishing something.
// What the four ranking signals are called for a person rather than for the scorer.
const SIGNALS = [["relevance", "Goal match"], ["level", "Difficulty"], ["style", "How you learn"], ["effort", "Course length"]] as const;

const REACTIONS: { event: FeedbackEvent; label: string; icon: typeof Check }[] = [
  { event: "already_know", label: "Already know this", icon: Check },
  { event: "too_hard", label: "Too hard", icon: TrendingDown },
  { event: "too_easy", label: "Too easy", icon: TrendingUp },
  { event: "not_interested", label: "Not for me", icon: X },
];

export default function TelemetryCards({ data, loading, onFeedback }: { data: PathData | null; loading: boolean; onFeedback: (event: FeedbackEvent) => void }) {
  const action = data?.progress.next_action;
  const phases = data?.path.phases ?? [];
  const tallest = Math.max(1, ...phases.map((phase) => phase.hours));
  const currentPhase = phases.findIndex((phase) => phase.title === data?.progress.current_phase);
  // Asked once per step, since each answer costs a model call. Stored against the step it describes
  // so a stale answer can never sit under a step it was not about.
  const step = action ? `${action.skill}:${action.resource?.id ?? ""}` : "";
  const [reason, setReason] = useState({ step: "", text: "" });
  useEffect(() => {
    if (!data || !step) return;
    let live = true;
    explainCurrent(data.profile, data.state.completed, data.state.blocked)
      .then((result) => { if (live) setReason({ step, text: result.reason }); })
      .catch(() => undefined);
    return () => { live = false; };
  }, [step]);   // eslint-disable-line react-hooks/exhaustive-deps
  return <>
    <section className="focus-card">
      <div className="focus-top"><p className="section-kicker">CURRENT FOCUS</p><span className="live-pill"><i/> Engine linked</span></div>
      <div className="focus-course">
        <div className="course-icon"><BrainCircuit size={23}/></div>
        <div><h3>{action?.name ?? "Building your path"}</h3><p>{action?.resource?.provider ?? "Finding the best resource"}</p></div>
      </div>
      {reason.step === step && reason.text && <p className="focus-reason">{reason.text}</p>}
      <div className="course-progress">
        <div><span>Path progress</span><b>{data?.progress.percent ?? 0}%</b></div>
        <div className="progress-track"><i style={{ width: `${data?.progress.percent ?? 0}%` }}/></div>
      </div>
      <button className="start-button" onClick={() => onFeedback("completed")} disabled={!action || loading}>
        <span>{loading ? <LoaderCircle className="spin" size={15}/> : <Play size={15} fill="currentColor"/>} Mark current complete</span>
        <span>{action?.resource ? `${action.resource.hours}h` : ""}</span>
      </button>
      <div className="reaction-row">
        {REACTIONS.map(({ event, label, icon: Icon }) =>
          <button key={event} onClick={() => onFeedback(event)} disabled={!action || loading} title={label}>
            <Icon size={12}/> {label}
          </button>)}
      </div>
    </section>
    <section className="stats-card">
      <div className="stats-header"><p className="section-kicker">LIVE PATH DATA</p><ArrowUpRight size={17}/></div>
      <div className="stats-values">
        <div><strong>{data?.progress.hours_total ?? 0}<span>h</span></strong><p><Clock3 size={12}/> Planned learning</p></div>
        <div><strong>{data?.progress.weeks_left ?? 0}<span>w</span></strong><p><Flame size={12}/> Remaining route</p></div>
      </div>
      <div className="weekly-chart">{phases.map((phase, index) =>
        <i key={index} style={{ height: `${Math.max(8, (phase.hours / tallest) * 100)}%` }}
           className={index === currentPhase ? "today" : ""} title={`Phase ${index + 1}: ${phase.hours}h`}/>)}</div>
      <div className="week-days">{phases.map((_, index) => <span key={index}>P{index + 1}</span>)}</div>
    </section>
    {data && <section className="stats-card">
      <div className="stats-header"><p className="section-kicker">WHAT MATTERS TO YOU</p></div>
      <div className="signal-list">{SIGNALS.map(([key, label]) =>
        <div className="signal-row" key={key}>
          <span>{label}</span>
          <i><b style={{ width: `${(data.state.weights?.[key] ?? 0) * 160}%` }}/></i>
          <small>{Math.round((data.state.weights?.[key] ?? 0) * 100)}%</small>
        </div>)}</div>
      <p className="signal-note">Learned from what you skip and finish. Starts even, moves as you react.</p>
    </section>}
    <section className="nudge-card">
      <span className="nudge-star">✦</span>
      <div>
        <p>{data?.path.feasible === false ? "This path needs more runway" : data ? "Your route is ready" : "Nothing planned yet"}</p>
        <small>{data?.progress.current_phase ?? "Connect the engine to generate your plan."}</small>
      </div>
    </section>
  </>;
}
