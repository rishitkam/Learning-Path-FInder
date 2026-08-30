"use client";
import { useEffect, useSyncExternalStore } from "react";
import { loadSession, type PathData, type Turn } from "./api";

// One session shared by every route: the path and the conversation. Each page used to hold its own
// copy of both, so building a path in the co-pilot and clicking to My path showed an empty dashboard
// and a second, separate chat. The browser copy is only an instant paint; the server is the truth.
const KEY = "alma.session";
const listeners = new Set<() => void>();
type Session = { data: PathData | null; turns: Turn[] };
// One frozen instance. Returning a fresh object from getServerSnapshot makes React think the store
// changed on every render.
const EMPTY: Session = { data: null, turns: [] };
let session: Session = EMPTY;
let hydrated = false;

function emit() {
  listeners.forEach((listener) => listener());
}

function set(next: Session) {
  session = next;
  try {
    if (next.data || next.turns.length) localStorage.setItem(KEY, JSON.stringify(next));
    else localStorage.removeItem(KEY);
  } catch {}
  emit();
}

export const setPathData = (data: PathData | null) => set({ ...session, data });
export const setTurns = (turns: Turn[]) => set({ ...session, turns });
export const clearSession = () => set({ data: null, turns: [] });

function hydrate() {
  if (hydrated) return;
  hydrated = true;
  try {
    const cached = localStorage.getItem(KEY);
    if (cached) set(JSON.parse(cached));
  } catch {}
  loadSession().then((saved) => { if (saved.data || saved.turns.length) set(saved); });
}

function useSession() {
  const value = useSyncExternalStore(
    (listener) => { listeners.add(listener); return () => void listeners.delete(listener); },
    () => session,
    () => EMPTY,
  );
  useEffect(hydrate, []);
  return value;
}

export const usePathData = () => [useSession().data, setPathData] as const;
export const useTurns = () => [useSession().turns, setTurns] as const;
