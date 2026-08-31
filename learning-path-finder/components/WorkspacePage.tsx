"use client";
import { ArrowUpRight, CheckCircle2, CircleDashed, Target } from "lucide-react";
import Header from "@/components/Header";
import Sidebar from "@/components/Sidebar";
import { usePathData } from "@/lib/store";

// These two pages used to print "Balanced builder" and "Ready" as fixed text, so they said the same
// thing whether you had a plan or not. They read the session now. The old copy is still here, but as
// the empty state it always claimed to be.
const STYLES: Record<string, string> = {
  "project first": "Project first", "reading first": "Reading first",
  "video first": "Video first", balanced: "Balanced builder",
};
const LEVELS = ["", "Beginner", "Early intermediate", "Intermediate", "Advanced", "Expert"];

export default function WorkspacePage({ kind }: { kind: "goals" | "profile" }) {
  const [data] = usePathData();
  const p = data?.profile;
  const progress = data?.progress;

  return <div className="app-shell"><Sidebar /><div className="app-content"><Header /><main className="dashboard subpage">
    <p className="eyebrow"><span className="pulse-dot" /> {kind === "profile" ? "Learner profile" : "Goal control"}</p>
    <h1>{kind === "profile" ? <>Learn how <em>you</em> learn.</> : <>Turn intent into <em>momentum.</em></>}</h1>
    <p className="subpage-intro">{kind === "profile"
      ? "Your preferences shape how ALMA ranks courses and plans your workload."
      : "Set a clear target, then let ALMA convert it into an ordered, achievable route."}</p>

    <section className="subpage-grid">{kind === "profile" ? <>
      <article className="detail-card">
        <p className="section-kicker">LEARNING STYLE</p>
        <h2>{p ? STYLES[p.style ?? "balanced"] ?? "Balanced builder" : "Not set yet"}</h2>
        <p>{p
          ? `${LEVELS[p.level ?? 2]} level, ${p.weekly_hours ?? 0} hours a week. ALMA ranks every course against these before it picks one.`
          : "ALMA is ready to balance practical projects and essential theory once you introduce yourself in Co-pilot."}</p>
        <a href="/copilot">{p ? "Change preferences" : "Set learning preferences"} <ArrowUpRight size={15} /></a>
      </article>
      <article className="detail-card accent-card">
        <p className="section-kicker">PROFILE SIGNAL</p>
        <strong>{p ? `${p.known_skills?.length ?? 0} skills known` : "Ready"}</strong>
        <p>{p
          ? `Telling ALMA what you already know removes those steps from the plan.`
          : "Your profile will become personal as you chat with ALMA."}</p>
      </article>
    </> : <>
      <article className="detail-card">
        <p className="section-kicker">NEXT TARGET</p>
        <h2>{p?.goal_text || p?.role || "Start with a conversation"}</h2>
        <p>{progress
          ? `${progress.skills_total - progress.skills_done} of ${progress.skills_total} steps still to go, ${data?.path.total_weeks} weeks at your current pace.`
          : "Tell ALMA the role or project you are aiming for, along with the hours you can realistically commit each week."}</p>
        <a href="/copilot">{p ? "Change your goal" : "Build a goal"} <ArrowUpRight size={15} /></a>
      </article>
      <article className="detail-card accent-card">
        <p className="section-kicker">HOW IT WORKS</p>
        <div className="goal-steps">
          <span><Target size={15} /> Define outcome</span>
          <span><CircleDashed size={15} /> Map the gap</span>
          <span><CheckCircle2 size={15} /> Follow the route</span>
        </div>
      </article>
    </>}</section>
  </main></div></div>;
}
