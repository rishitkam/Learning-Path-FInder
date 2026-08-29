"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import RoadmapGraph from "@/components/RoadmapGraph";
import TelemetryCards from "@/components/TelemetryCards";

export default function Home() {
  const [view, setView] = useState<"roadmap" | "outline">("roadmap");
  return <div className="app-shell"><Sidebar /><div className="app-content"><Header /><main className="dashboard">
    <section className="hero-section"><div className="hero-orbit hero-orbit-one" /><div className="hero-orbit hero-orbit-two" />
      <div className="eyebrow"><span className="pulse-dot" /> Your trajectory &middot; 04 / 12 milestones</div>
      <div className="hero-heading-row"><div><h1>Make your next<br /><em>move matter.</em></h1><p className="hero-copy">One path, shaped around your momentum. Follow the signal, build the skill, and keep moving.</p></div><div className="hero-score"><span>Path velocity</span><strong>+24%</strong><small>vs. last week</small></div></div>
      <div className="hero-actions"><div className="view-switch" role="group" aria-label="Roadmap view"><button onClick={() => setView("roadmap")} className={view === "roadmap" ? "active" : ""}>Path map</button><button onClick={() => setView("outline")} className={view === "outline" ? "active" : ""}>Milestones</button></div><div className="hero-meta"><span>12h 40m</span> invested in your future</div></div>
    </section>
    <section className="dashboard-grid"><div className="path-card"><div className="card-heading"><div><p className="section-kicker">YOUR LEARNING CONSTELLATION</p><h2>{view === "roadmap" ? "The big picture" : "The next steps"}</h2></div><div className="path-legend"><span><i className="done" /> Mastered</span><span><i className="current" /> In progress</span></div></div><RoadmapGraph view={view} /></div><div className="side-stack"><TelemetryCards /></div></section>
  </main></div></div>;
}
