"""Measures whether the recommender is any good, not just whether it runs.

Structural evals need no model and finish in a second, so they can run on every change. The two that
call Groq are opt in, because they cost rate limit.

    python3 evals.py            structure, paths, personalisation, adaptation
    python3 evals.py --llm      also extraction accuracy and explanation faithfulness
"""

import json, re, sys, time
from collections import Counter
from itertools import combinations
from statistics import mean

import networkx as nx
import numpy as np
from scipy.optimize import linprog

import state as st
from embed import relevance
from graph import load
from path import W, build, load_catalog

PERSONAS = {"fresh": [], "some python": ["prog.python", "data.pandas"],
            "experienced": ["prog.python", "data.pandas", "ml.supervised", "math.stats"]}
PROFILE = {"level": 2, "style": "balanced", "weekly_hours": 12, "horizon_weeks": 40}
G, CAT = load(), None


def pct(part, whole):
    return 100 * part / whole if whole else 0


def optimal_hours(gap):
    """A real lower bound on the cheapest possible set of courses covering the gap.

    Minimum cost set cover is NP hard, so we solve its linear relaxation: allow fractional courses
    and minimise total hours subject to every skill being covered at least once. The relaxation can
    only be cheaper than the true integer optimum, so any solution divided by this is an honest
    upper bound on how far from optimal we are.
    """
    gap = sorted(set(gap))
    pool = [c for c in CAT if c["kind"] != "assessment" and set(c["teaches"]) & set(gap)]
    if not pool or not gap:
        return 0
    cost = np.array([c["hours"] for c in pool], dtype=float)
    covers = np.array([[1.0 if skill in c["teaches"] else 0.0 for c in pool] for skill in gap])
    answer = linprog(cost, A_ub=-covers, b_ub=-np.ones(len(gap)), bounds=(0, 1), method="highs")
    return answer.fun if answer.success else 0


def structure():
    teach = Counter(s for c in CAT if c["kind"] != "assessment" for s in c["teaches"])
    depths = Counter(G.depth.values())
    reachable = set().union(*[G.closure(G.role_skills(r)) for r in G.roles])
    return {
        "skills": len(G.skills), "edges": G.g.number_of_edges(), "catalog": len(CAT),
        "is a dag": nx.is_directed_acyclic_graph(G.g),
        "max depth": max(G.depth.values()),
        "skills with no course": sum(1 for s in G.skills if not teach[s]),
        "skills with one course": sum(1 for s in G.skills if teach[s] == 1),
        "courses per skill, median": sorted(teach[s] for s in G.skills)[len(G.skills) // 2],
        "skills no role can reach": len(set(G.skills) - reachable),
        "roots": sum(1 for n in G.g if G.g.in_degree(n) == 0),
        "widest depth level": max(depths.values()),
    }


def paths():
    rows = []
    for role in sorted(G.roles):
        for persona, known in PERSONAS.items():
            gap = set(G.gap(G.role_skills(role), known))
            if not gap:
                continue
            r = build(G, gap, PROFILE, CAT, known)
            mods = [m for ph in r["phases"] for m in ph["modules"]]
            at = {s: i for i, ph in enumerate(r["phases"]) for s in ph["skills"]}
            violations = [(p, s) for s in at for p in G.g.pred[s] if p in at and at[p] > at[s]]
            hours = sum(ph["hours"] for ph in r["phases"])
            rows.append({
                "role": role, "persona": persona, "skills": len(gap), "weeks": r["total_weeks"],
                "hours": hours, "bound": optimal_hours(gap),
                "violations": len(violations),
                "covered": pct(sum(1 for m in mods if m["resource"]), len(mods)),
                "reuse": len(mods) / max(len({m["resource"]["id"] for m in mods if m["resource"]}), 1),
            })
    return rows


def personalisation():
    """Personalisation score and inter list diversity, the standard recommender measures: one minus
    the mean pairwise Jaccard similarity between different users' recommendation lists."""
    same_goal, weight_shift, adaptation = [], [], []
    for role in sorted(G.roles):
        picks = {}
        for persona, known in PERSONAS.items():
            gap = G.gap(G.role_skills(role), known)
            if not gap:
                continue
            picks[persona] = {(m["skill"], (m["resource"] or {}).get("id"))
                              for ph in build(G, gap, PROFILE, CAT, known)["phases"] for m in ph["modules"]}
        for a, b in combinations(picks.values(), 2):
            same_goal.append(100 - pct(len(a & b), len(a | b)))     # 1 - Jaccard, over every pair

        gap = G.gap(G.role_skills(role))
        base = {(m["skill"], (m["resource"] or {}).get("id"))
                for ph in build(G, gap, PROFILE, CAT)["phases"] for m in ph["modules"]}
        heavy = {(m["skill"], (m["resource"] or {}).get("id"))
                 for ph in build(G, gap, PROFILE, CAT, weights={"relevance": .05, "level": .05,
                                                                "style": .05, "effort": .85})["phases"]
                 for m in ph["modules"]}
        weight_shift.append(pct(len(base ^ heavy), len(base | heavy)))

        s = st.new({**PROFILE, "goal_skills": G.role_skills(role)})
        r = build(G, G.gap(s["goal_skills"]), s, CAT)
        for _ in range(3):
            mod = next((m for ph in r["phases"] for m in ph["modules"] if m["resource"]), None)
            if not mod:
                break
            s = st.apply(s, "too_hard", resource_id=mod["resource"]["id"], module=mod)
            r = build(G, G.gap(s["goal_skills"], s["known_skills"]), s, CAT, blocked=s["blocked"])
        after = {(m["skill"], (m["resource"] or {}).get("id")) for ph in r["phases"] for m in ph["modules"]}
        adaptation.append(pct(len(base ^ after), len(base | after)))
    return {"different people, same goal": mean(same_goal), "weights changed the picks": mean(weight_shift),
            "three too hard clicks changed": mean(adaptation)}


def catalog_coverage():
    """What share of the catalog the system ever recommends. A recommender that only ever surfaces
    twenty courses out of four hundred has a long tail it cannot reach."""
    seen = set()
    for role in G.roles:
        for known in PERSONAS.values():
            gap = G.gap(G.role_skills(role), known)
            if gap:
                seen |= {m["resource"]["id"] for ph in build(G, gap, PROFILE, CAT, known)["phases"]
                         for m in ph["modules"] if m["resource"]}
    teachable = {c["id"] for c in CAT if c["kind"] != "assessment"}
    return {"catalog coverage": f"{pct(len(seen), len(teachable)):.0f}%  ({len(seen)} of {len(teachable)})"}


def latency():
    times = []
    for role in sorted(G.roles):
        gap = G.gap(G.role_skills(role))
        start = time.perf_counter()
        build(G, gap, PROFILE, CAT)
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    return {"path build p50": f"{times[len(times)//2]:.0f} ms", "path build p95": f"{times[-1]:.0f} ms"}


def determinism():
    same = []
    for role in sorted(G.roles):
        gap = G.gap(G.role_skills(role))
        run = lambda catalog: [(m["skill"], (m["resource"] or {}).get("id"))
                               for ph in build(G, gap, PROFILE, catalog)["phases"] for m in ph["modules"]]
        same.append(run(CAT) == run(CAT) == run(list(reversed(CAT))))
    return {"identical across runs and catalog order": f"{sum(same)}/{len(same)} roles"}


def extraction():
    """Slot filling precision, recall and F1 against golden utterances.

    Set valued slots were scored by subset before, which is recall only: a model returning every
    skill in the taxonomy would have scored a hundred percent. Precision is the half that matters
    here, because an invented known skill silently deletes steps from someone's path.
    """
    import profile as pf
    cases = json.loads(open("data/golden.json").read())
    tp, fp, fn, exact, total = Counter(), Counter(), Counter(), Counter(), Counter()
    misses = []
    for case in cases:
        got = pf.extract(G, case["said"])
        for field, want in case["expect"].items():
            total[field] += 1
            if isinstance(want, list):
                want, mine = set(want), set(got.get(field) or [])
                tp[field] += len(want & mine)
                fp[field] += len(mine - want)
                fn[field] += len(want - mine)
                ok = want == mine
            else:
                ok = got.get(field) == want
                exact[field] += ok
            if not ok:
                misses.append(f"{case['said'][:32]!r} {field}: wanted {want}, got {got.get(field)}")
    out = {}
    for field in total:
        if tp[field] or fp[field] or fn[field]:
            p = tp[field] / max(tp[field] + fp[field], 1)
            r = tp[field] / max(tp[field] + fn[field], 1)
            out[f"{field} P/R/F1"] = f"{p:.2f} / {r:.2f} / {2*p*r/max(p+r, 1e-9):.2f}"
        else:
            out[f"{field} exact match"] = f"{pct(exact[field], total[field]):.0f}%"
    return out, misses


def groundedness():
    """Groundedness rate: the share of generated explanations in which every claim traces back to the
    facts we supplied. RAG evaluation usually measures this with a second model as judge; ours is a
    deterministic proxy, checking that every number in the text appears in the facts and that no
    phrase promises an action we cannot take. Cheaper, reproducible, and it cannot itself hallucinate.
    """
    import explain
    checked, clean, bad = 0, 0, []
    r = build(G, G.gap(G.role_skills("machine-learning-engineer"), ["prog.python"]), PROFILE, CAT, ["prog.python"])
    in_path = {s for ph in r["phases"] for s in ph["skills"]}
    for mod in [m for ph in r["phases"] for m in ph["modules"]][:8]:
        text = explain.explain_module(G, mod, in_path)
        facts = json.dumps(explain._facts(G, mod, in_path))
        invented = [n for n in re.findall(r"\b\d+\b", text) if n not in facts]
        promises = [p for p in ["we'll", "we will", "i've updated", "has been trimmed"] if p in text.lower()]
        checked += 1
        clean += not (invented or promises)
        if invented or promises:
            bad.append(f"{mod['name']}: numbers not in the facts {invented} {promises}")
    return {"groundedness rate": f"{pct(clean, checked):.0f}%  ({clean} of {checked} explanations)"}, bad


if __name__ == "__main__":
    CAT = load_catalog(G)
    rows = paths()
    ratio = mean(r["hours"] / r["bound"] for r in rows if r["bound"])

    print("\nSTRUCTURE")
    for k, v in structure().items():
        print(f"  {k:<30} {v}")

    print("\nPATHS  (7 roles x 3 personas)")
    print(f"  {'':<30} {'worst':>8} {'median':>8} {'best':>8}")
    for label, key, fmt in [("prerequisite violations", "violations", "{:.0f}"),
                            ("skills covered by a course %", "covered", "{:.0f}"),
                            ("weeks", "weeks", "{:.0f}"), ("study hours", "hours", "{:.0f}"),
                            ("modules per distinct course", "reuse", "{:.2f}")]:
        vals = sorted(r[key] for r in rows)
        print(f"  {label:<30} {fmt.format(vals[-1]):>8} {fmt.format(vals[len(vals)//2]):>8} {fmt.format(vals[0]):>8}")
    ratios = sorted(r["hours"] / r["bound"] for r in rows if r["bound"])
    print(f"  {'approximation ratio':<30} {ratios[-1]:>8.2f} {ratios[len(ratios)//2]:>8.2f} {ratios[0]:>8.2f}")
    print(f"       mean {ratio:.2f}x the linear programming lower bound on the cheapest possible cover")

    print("\nPERSONALISATION  (% of picks that differ)")
    for k, v in personalisation().items():
        print(f"  {k:<30} {v:>7.0f}%")
    print("\nREACH AND SPEED")
    for k, v in {**catalog_coverage(), **latency()}.items():
        print(f"  {k:<30} {v}")
    print("\nDETERMINISM")
    for k, v in determinism().items():
        print(f"  {k:<30} {v}")

    if "--llm" in sys.argv:
        print("\nEXTRACTION  (golden utterances)")
        scores, misses = extraction()
        for k, v in scores.items():
            print(f"  {k:<30} {v:>7}")
        for m in misses[:6]:
            print(f"    miss: {m}")
        print("\nGROUNDEDNESS")
        scores, bad = groundedness()
        for k, v in scores.items():
            print(f"  {k:<44} {v}")
        for b in bad[:4]:
            print(f"    {b}")
    print()
