"use client";
import { Check, Lock, ArrowUpRight, LoaderCircle } from "lucide-react";
import type { PathData } from "@/lib/api";

const COLUMNS = 4;
const ROW_HEIGHT = 190;

type Node = { id: string; name: string; sub: string; url?: string; done: boolean; active: boolean; locked: boolean; x: number; y: number };

/** Lays every milestone out on a serpentine grid. It used to draw only the first five of them while
 *  the header counted all of them, so more than half a long path was unreachable. */
function layout(count: number, index: number) {
  const columns = Math.min(COLUMNS, Math.max(count, 1));
  const rows = Math.ceil(count / columns);
  const row = Math.floor(index / columns);
  const raw = index % columns;
  const column = row % 2 ? columns - 1 - raw : raw;      // snake back on every other row
  return { x: ((column + 0.5) / columns) * 100, y: ((row + 0.5) / rows) * 100, rows };
}

export default function RoadmapGraph({ view, path, completed, loading }: { view: "roadmap" | "outline"; path?: PathData["path"]; completed: string[]; loading: boolean }) {
  const modules = path?.phases.flatMap((phase) => phase.modules) ?? [];
  const done = new Set(completed);
  const activeIndex = modules.findIndex((module) => !done.has(module.skill));
  const rows = Math.ceil(modules.length / Math.min(COLUMNS, Math.max(modules.length, 1))) || 1;

  const nodes: Node[] = modules.map((module, index) => ({
    id: module.skill,
    name: module.name,
    sub: module.resource?.title ?? "No course for this yet",
    url: module.resource?.url,
    done: done.has(module.skill),
    active: index === activeIndex,
    locked: activeIndex !== -1 && index > activeIndex,
    ...layout(modules.length, index),
  }));

  if (loading && !path) return <div className="graph-loading"><LoaderCircle className="spin"/> Loading your real path…</div>;
  if (!modules.length) return <div className="graph-loading">Tell ALMA your goal to see a route here.</div>;

  if (view === "outline") return <div className="milestone-list">{nodes.map((node, index) =>
    <a className={`milestone-row ${node.active ? "milestone-active" : ""}`} key={node.id}
       href={node.url} target="_blank" rel="noreferrer" title={node.url ? `Open ${node.sub}` : undefined}>
      <span className="milestone-number">{String(index + 1).padStart(2, "0")}</span>
      <div className="mini-ring" style={{ "--progress": `${node.done ? 360 : 0}deg` } as React.CSSProperties}>
        {node.done ? <Check size={14}/> : node.locked ? <Lock size={13}/> : "→"}
      </div>
      <div><b>{node.name}</b><small>{node.sub}</small></div>
      <span className="milestone-status">{node.done ? "Complete" : node.active ? "In progress" : "Locked"}</span>
      <ArrowUpRight size={17}/>
    </a>)}</div>;

  return <div className="graph-wrap" style={{ height: Math.max(508, rows * ROW_HEIGHT) }}>
    <div className="graph-glow"/>
    <svg className="path-lines" viewBox="0 0 100 100" preserveAspectRatio="none">
      <polyline points={nodes.map((node) => `${node.x},${node.y}`).join(" ")} vectorEffect="non-scaling-stroke"/>
    </svg>
    {nodes.map((node) =>
      <a key={node.id} className={`path-node ${node.active ? "node-active" : ""} ${node.locked ? "node-locked" : ""}`}
         style={{ left: `${node.x}%`, top: `${node.y}%` }} href={node.url} target="_blank" rel="noreferrer"
         title={node.url ? `Open ${node.sub}` : "No course for this yet"}>
        <span className="node-ring" style={{ "--progress": `${node.done ? 360 : 0}deg` } as React.CSSProperties}>
          {node.done ? <Check size={22}/> : node.locked ? <Lock size={17}/> : <b>Now</b>}
        </span>
        <span className="node-label"><b>{node.name}</b><small>{node.sub}</small></span>
        {node.active && <span className="active-tag">You are here</span>}
      </a>)}
    <div className="destination">{modules.length} MILESTONES <span>↗</span></div>
  </div>;
}
