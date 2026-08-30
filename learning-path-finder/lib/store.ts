"use client";
import { useEffect, useSyncExternalStore } from "react";
import type { PathData } from "./api";

// One path shared by every route. Each page used to hold its own useState, so building a path in the
// co-pilot and clicking through to My path showed an empty dashboard. Saved so a refresh keeps it too.
const KEY = "alma.path";
const listeners = new Set<() => void>();
let data: PathData | null = null;
let hydrated = false;

function emit() {
  listeners.forEach((listener) => listener());
}

export function setPathData(next: PathData | null) {
  data = next;
  try {
    if (next) localStorage.setItem(KEY, JSON.stringify(next));
    else localStorage.removeItem(KEY);
  } catch {}
  emit();
}

function hydrate() {
  if (hydrated) return;
  hydrated = true;
  try {
    const saved = localStorage.getItem(KEY);
    if (saved && !data) {
      data = JSON.parse(saved) as PathData;
      emit();
    }
  } catch {}
}

export function usePathData() {
  // Reading after mount rather than at module scope, so the server and the first client render agree.
  const value = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => void listeners.delete(listener);
    },
    () => data,
    () => null,
  );
  useEffect(hydrate, []);
  return [value, setPathData] as const;
}
