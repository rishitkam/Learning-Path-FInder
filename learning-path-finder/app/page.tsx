"use client";
import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import RoadmapGraph from "@/components/RoadmapGraph";
import TelemetryCards from "@/components/TelemetryCards";
import Copilot from "@/components/Copilot";
import { sendFeedback, type FeedbackEvent } from "@/lib/api";
import { usePathData } from "@/lib/store";

export default function Home() {
  const [view, setView] = useState<"roadmap" | "outline">("roadmap");
  const [data, setData] = usePathData();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const feedback = async (event: FeedbackEvent) => {
    const action = data?.progress.next_action;
    if (!data || !action) return;
    setLoading(true); setError(null);
    try { setData(await sendFeedback(data.profile, data.state.completed, data.state.blocked, event, action.skill, action.resource?.id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save your progress."); }
    finally { setLoading(false); }
  };
  return <div className="app-shell"><Sidebar/><div className="app-content"><Header/><main className="dashboard">
    <section className="hero-section"><div className="hero-orbit hero-orbit-one"/><div className="hero-orbit hero-orbit-two"/><div className="eyebrow"><span className="pulse-dot"/> {data ? `Live learning path · ${data.progress.skills_done} / ${data.progress.skills_total} milestones` : "Talk to ALMA to build your live path"}</div><div className="hero-heading-row"><div><h1>Make your next<br/><em>move matter.</em></h1><p className="hero-copy">Tell ALMA your goal and available time. The path only appears when it is built from your actual answer.</p></div><div className="hero-score"><span>Path status</span><strong>{data?.path.feasible ? "On track" : data ? "Stretch" : "Awaiting you"}</strong><small>{data ? `${data.path.total_weeks} week route` : "No example route loaded"}</small></div></div><div className="hero-actions"><div className="view-switch"><button onClick={() => setView("roadmap")} className={view === "roadmap" ? "active" : ""}>Path map</button><button onClick={() => setView("outline")} className={view === "outline" ? "active" : ""}>Milestones</button></div><div className="hero-meta">{error ? <span className="api-error">{error}</span> : data ? <><span>{data.progress.hours_total}h</span> of curated learning</> : "Start with the co-pilot →"}</div></div></section>
    <section className="dashboard-grid"><div className="path-card"><div className="card-heading"><div><p className="section-kicker">YOUR LEARNING CONSTELLATION</p><h2>{view === "roadmap" ? "The big picture" : "The next steps"}</h2></div><div className="path-legend"><span><i className="done"/> Mastered</span><span><i className="current"/> In progress</span></div></div><RoadmapGraph view={view} path={data?.path} completed={data?.state.completed ?? []} loading={loading}/></div><div className="side-stack"><TelemetryCards data={data} loading={loading} onFeedback={feedback}/></div></section>
    <Copilot data={data} onPath={setData}/>
  </main></div></div>;
}
