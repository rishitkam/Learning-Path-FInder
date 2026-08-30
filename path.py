"""Turns an ordered skill gap into a scheduled path of real catalog items. Pure, no LLM."""

import json
from math import ceil
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
W = {"relevance": 0.40, "level": 0.25, "style": 0.20, "effort": 0.15}
# A course longer than this many weeks of the learner's time is only offered when nothing shorter
# teaches the skill. Ranking alone could not express it: a small semantic edge becomes the whole
# relevance term once scores are normalised, which was enough to send someone into a 173 hour
# specialisation to learn Git rather than a 16 hour course on it.
MAX_WEEKS_PER_COURSE = 8
PREF = {"project first": "project", "theory first": "course"}


def load_catalog(g, data=DATA):
    catalog = json.loads((data / "catalog.json").read_text())
    bad = {s for c in catalog for s in c["teaches"] + c["assumes"]} - set(g.skills)
    if bad:
        raise ValueError(f"catalog references unknown skill ids: {sorted(bad)}")
    return catalog


def _terms(c, p, rel):
    """The four ranking signals. Kept separately so the explainer can show its work."""
    return {"relevance": rel,
            "level": 1 - abs(c["level"] - (p.get("level") or 2)) / 4,
            "style": 1.0 if c["kind"] == PREF.get(p.get("style")) else 0.5,
            "effort": 1.0 if c["hours"] <= (p.get("weekly_hours") or 1) * 2 else 0.6}


def _affordable(cands, p):
    """Prefer courses that fit inside a couple of months. Fall back only if that leaves nothing."""
    cap = (p.get("weekly_hours") or 1) * MAX_WEEKS_PER_COURSE
    return [c for c in cands if c["hours"] <= cap] or cands


def _best(cands, p, relevance, weights=W):
    """Relevance is normalised across the candidates for one skill. Absolute cosine clusters too
    tightly to matter, and every candidate here teaches the same skill, so only the ranking does.
    Ties break on id, so regenerating the catalog cannot quietly reshuffle recommendations."""
    if not cands:
        return None, None
    cands = _affordable(cands, p)
    raw = [relevance(c) for c in cands]
    lo, hi = min(raw), max(raw)
    scored = [(_terms(c, p, (r - lo) / (hi - lo) if hi > lo else 0.5), c) for c, r in zip(cands, raw)]
    why, best = max(scored, key=lambda x: (sum(weights[k] * v for k, v in x[0].items()), x[1]["id"]))
    if len(cands) == 1:
        why["only_option"] = True      # nothing was chosen, so do not let the explainer claim it was
    elif hi <= lo:
        why["flat_relevance"] = True   # every candidate scored alike, so relevance decided nothing
    return best, why


def _cover(gap, catalog, p, relevance, weights, blocked):
    """Choose the cheapest set of courses covering the gap, weighted by how well they suit the learner.

    Picking the best course for each skill on its own left about 40 percent of the study time
    redundant, because one course often teaches several things the learner needs and we were only
    noticing after the fact. This is the textbook greedy set cover, whose value per step is coverage
    per hour, multiplied by our fit score so a cheap course they will hate cannot win. Greedy is
    within a log factor of optimal, which is worth saying plainly rather than claiming it is optimal.
    """
    gap = set(gap)
    pool = [c for c in catalog if c["kind"] != "assessment" and c["id"] not in blocked
            and set(c["teaches"]) & gap]
    # Relevance is normalised once across every candidate for the whole gap. Doing it per skill made
    # the best of two candidates worth the entire term however small the real difference was.
    raw = {c["id"]: relevance(c) for c in pool}
    lo, hi = (min(raw.values()), max(raw.values())) if raw else (0, 0)
    spread = hi > lo

    def terms(c):
        t = _terms(c, p, (raw[c["id"]] - lo) / (hi - lo) if spread else 0.5)
        if not spread:
            t["flat_relevance"] = True
        return t

    fit = lambda c: sum(weights[k] * v for k, v in terms(c).items() if k in weights)

    uncovered, chosen = set(gap), []
    while uncovered:
        reachable = [c for c in pool if set(c["teaches"]) & uncovered]
        if not reachable:
            break
        best = max(_affordable(reachable, p),
                   key=lambda c: (fit(c) * len(set(c["teaches"]) & uncovered) / max(c["hours"], 1), c["id"]))
        chosen.append(best)
        uncovered -= set(best["teaches"])
    return chosen, terms, fit


def build(g, gap, profile, catalog, known=(), blocked=(), relevance=lambda c: 0.5, weights=None):
    blocked, weights = set(blocked), weights or profile.get("weights") or W
    per_week = profile.get("weekly_hours") or 1
    groups = g.phases(gap)                       # one topological sort, reused for the ordering below

    # One resource per skill, drawn from a set chosen to cover the whole gap. A skill with no match
    # keeps its slot with nothing attached, because dropping it would break the chain.
    ordered = [s for grp in groups for s in grp]
    chosen, terms, fit = _cover(ordered, catalog, profile, relevance, weights, blocked)
    mods = {}
    for s in ordered:
        covering = [c for c in chosen if s in c["teaches"]]
        best = max(covering, key=lambda c: (fit(c), c["id"])) if covering else None
        mods[s] = {"skill": s, "name": g.name(s), "resource": best,
                   "why": terms(best) if best else None,
                   # What else this one course covers, so the explainer can say so.
                   "also_covers": sorted(set(best["teaches"]) & set(ordered) - {s}) if best else []}
    module_ids = {m["resource"]["id"] for m in mods.values() if m["resource"]}

    # One course can teach several skills in the path. It is the module for each of them, but its
    # hours are real work only once, so we count a resource the first time we meet it.
    counted, hours = set(), {}
    for s in mods:
        r = mods[s]["resource"]
        hours[s] = 0 if not r or r["id"] in counted else r["hours"]
        if r:
            counted.add(r["id"])

    covered, used, week, phases = set(g.closure(known)), set(), 0, []
    bucket, target = [], per_week * 4            # a phase is about a month of this learner's time
    for i, group in enumerate(groups):
        bucket += group
        if sum(hours[s] for s in bucket) < target and i < len(groups) - 1:
            continue                             # keep filling, but never leave a tail unemitted

        skills = bucket
        bucket = []
        covered |= set(skills)
        # A milestone must not be a course a later phase will present as a module, so we exclude
        # every module id up front rather than only the ones seen so far.
        extra = lambda kind: _best(
            [c for c in catalog if c["kind"] == kind and c["id"] not in used | blocked | module_ids
             and set(c["assumes"]) <= covered and set(c["teaches"]) & set(skills)],
            profile, relevance, weights)[0]
        milestone, assessment = extra("project"), extra("assessment")
        used |= {x["id"] for x in (milestone, assessment) if x}

        hrs = sum(hours[s] for s in skills) + sum(x["hours"] for x in (milestone, assessment) if x)
        end = week + ceil(hrs / per_week)
        phases.append({"title": ", ".join(g.name(s) for s in skills[-2:]),
                       "skills": skills, "modules": [mods[s] for s in skills],
                       "weeks": (week, end), "hours": hrs,
                       "milestone": milestone, "assessment": assessment})
        week = end

    # The deadline never shapes the plan. Trimming to hit a number means dropping skills or taking
    # worse courses, and then the plan quietly stops being the plan. We build the honest route and
    # say what it would take, which is decision 22 with the arithmetic it always needed.
    horizon, hours = profile.get("horizon_weeks"), sum(phase["hours"] for phase in phases)
    feasible = week <= horizon if horizon is not None else True
    return {"phases": phases, "total_weeks": week, "total_hours": hours, "feasible": feasible,
            "weekly_hours_needed": None if feasible or not horizon else ceil(hours / horizon)}
