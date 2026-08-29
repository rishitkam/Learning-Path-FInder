"""Turns an ordered skill gap into a scheduled path of real catalog items. Pure, no LLM."""

import json
from math import ceil
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
W = {"relevance": 0.40, "level": 0.25, "style": 0.20, "effort": 0.15}
PREF = {"project first": "project", "theory first": "course"}


def load_catalog(g, data=DATA):
    catalog = json.loads((data / "catalog.json").read_text())
    bad = {s for c in catalog for s in c["teaches"] + c["assumes"]} - set(g.skills)
    if bad:
        raise ValueError(f"catalog references unknown skill ids: {sorted(bad)}")
    return catalog


def _terms(c, p, relevance):
    """The four ranking signals. Kept separately so the explainer can show its work."""
    return {"relevance": relevance(c),
            "level": 1 - abs(c["level"] - p["level"]) / 4,
            "style": 1.0 if c["kind"] == PREF.get(p.get("style")) else 0.5,
            "effort": 1.0 if c["hours"] <= p["weekly_hours"] * 2 else 0.6}


def _score(c, p, relevance):
    return sum(W[k] * v for k, v in _terms(c, p, relevance).items())


def _best(cands, p, relevance):
    return max(cands, key=lambda c: _score(c, p, relevance), default=None)


def build(g, gap, profile, catalog, known=(), blocked=(), relevance=lambda c: 0.5):
    ordered = g.order(gap)

    # One resource per skill. A skill with no match stays in the path with nothing attached,
    # because dropping it would break the chain and hiding it would be a lie.
    mods = {}
    for s in ordered:
        best = _best([c for c in catalog if s in c["teaches"] and c["kind"] != "assessment"
                      and c["id"] not in blocked], profile, relevance)
        mods[s] = {"skill": s, "name": g.name(s), "resource": best,
                   "why": _terms(best, profile, relevance) if best else None}

    # Cut into phases at depth boundaries only, once a bucket holds about a month of their time.
    target, buckets, bucket, hrs = profile["weekly_hours"] * 4, [], [], 0
    for group in g.phases(gap):
        bucket += group
        hrs += sum(mods[s]["resource"]["hours"] if mods[s]["resource"] else 0 for s in group)
        if hrs >= target:
            buckets.append((bucket, hrs))
            bucket, hrs = [], 0
    if bucket:
        buckets.append((bucket, hrs))

    covered, used, week, phases = set(g.closure(known)), set(), 0, []
    for skills, hrs in buckets:
        covered |= set(skills)
        used |= {mods[s]["resource"]["id"] for s in skills if mods[s]["resource"]}
        end = week + ceil(hrs / profile["weekly_hours"])
        extra = lambda kind: _best(
            [c for c in catalog if c["kind"] == kind and c["id"] not in used | set(blocked)
             and set(c["assumes"]) <= covered and set(c["teaches"]) & set(skills)],
            profile, relevance)
        milestone, assessment = extra("project"), extra("assessment")
        used |= {x["id"] for x in (milestone, assessment) if x}
        phases.append({"title": ", ".join(g.name(s) for s in skills[-2:]),
                       "skills": skills, "modules": [mods[s] for s in skills],
                       "weeks": (week, end), "hours": hrs,
                       "milestone": milestone, "assessment": assessment})
        week = end

    return {"phases": phases, "total_weeks": week,
            "feasible": week <= (profile.get("horizon_weeks") or week)}
