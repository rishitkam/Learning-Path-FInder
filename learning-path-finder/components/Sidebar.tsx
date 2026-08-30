"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Map, Target, User, Zap, ChevronRight, Route } from "lucide-react";
import { usePathData } from "@/lib/store";
import type { PathData } from "@/lib/api";

const MENU = [
  { name: "Co-pilot", href: "/copilot", icon: Bot, desc: "Ask anything" },
  { name: "My path", href: "/", icon: Map, desc: "Your learning route" },
  { name: "Goals", href: "/goals", icon: Target, desc: "Targets in motion" },
  { name: "Profile", href: "/profile", icon: User, desc: "Your learner file" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [data] = usePathData();
  const done = new Set(data?.state.completed ?? []);
  const phases: (PathData["path"]["phases"][number] | null)[] = data?.path.phases ?? [];
  return <aside className="sidebar">
    <div className="brand"><div className="brand-mark"><Zap size={17} fill="currentColor"/></div><span>alma<span>/</span></span></div>
    <div className="workspace-label">Workspace</div>
    <nav className="nav-list">{MENU.map(({ name, href, icon: Icon, desc }) => {
      const active = pathname === href;
      return <Link key={name} href={href} className={`nav-item ${active ? "selected" : ""}`}>
        <span className="nav-icon"><Icon size={19}/></span>
        <span><b>{name}</b><small>{desc}</small></span>
        {active && <ChevronRight size={15} className="nav-arrow"/>}
      </Link>;
    })}</nav>
    <div className="sidebar-bottom"><div className="streak-card">
      <div className="streak-icon"><Route size={17}/></div>
      <p>Your progress</p>
      <strong>{data?.progress.skills_done ?? 0} <small>of {data?.progress.skills_total ?? 0} steps</small></strong>
      <div className="streak-bars">{(phases.length ? phases : Array<null>(7).fill(null)).map((phase, index) =>
        <i key={index} className={phase && phase.modules.every((module) => done.has(module.skill)) ? "filled" : ""}/>)}</div>
      <span>{data ? `${data.progress.weeks_left} weeks left of ${data.path.total_weeks}` : "No route yet"}</span>
    </div></div>
  </aside>;
}
