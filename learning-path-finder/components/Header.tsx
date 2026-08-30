"use client";
import Link from "next/link";
import { Command, Plus } from "lucide-react";
import { usePathData } from "@/lib/store";

export default function Header() {
  const [data, setData] = usePathData();
  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
  return <header className="topbar">
    <div className="date-chip"><Command size={14}/><span>{today}</span></div>
    <div className="topbar-right">
      <button className="new-button" onClick={() => setData(null)} disabled={!data} title="Clear this route and start again">
        <Plus size={15}/> New focus
      </button>
      <Link href="/profile" className="profile-button">
        <span className="avatar">You</span>
        <span><b>Your route</b><small>{data ? `${data.progress.percent}% complete` : "Not started"}</small></span>
      </Link>
    </div>
  </header>;
}
