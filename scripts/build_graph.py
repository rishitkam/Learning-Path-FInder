"""Turns the labelled catalog into a real skill graph.

Prints a report by default. Pass --apply to overwrite data/skills.json and data/catalog.json.
"""

import json, sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
from model2vec import StaticModel

ROOT = Path(__file__).resolve().parents[1]
SIM = 0.80          # below this a pair is not even a merge candidate
MIN_SUPPORT = 2     # courses that must claim an edge for it to stand


def load():
    """The label cache is a superset across runs, so drop labels for courses the current filter no
    longer keeps, and drop skills nothing surviving teaches or assumes."""
    d = json.loads((ROOT / "data/raw/labels.json").read_text())
    courses = {c["id"]: c for c in json.loads((ROOT / "data/raw/filtered.json").read_text())}
    labels = {k: v for k, v in d["labels"].items() if k in courses}
    seed = set(json.loads((ROOT / "data/seed_skills.json").read_text()))
    live = seed | {s for l in labels.values() for s in l["teaches"] + l["assumes"]}
    return {k: v for k, v in d["taxonomy"].items() if k in live}, labels, courses


def context(taxonomy, labels, courses, model):
    """A skill means what its courses talk about. Names put opposites two characters apart."""
    blurb = defaultdict(list)
    for cid, l in labels.items():
        for s in l["teaches"]:
            blurb[s].append(courses[cid]["title"] + ". " + courses[cid]["description"][:200])
    ids = sorted(taxonomy)
    v = model.encode([taxonomy[s] + ". " + " ".join(blurb[s][:6]) for s in ids], show_progress_bar=False)
    return ids, v / np.linalg.norm(v, axis=1, keepdims=True)


def blocked(labels):
    """Pairs the corpus itself says are different: taught together, or one gates the other."""
    out = set()
    for l in labels.values():
        out |= {p for p in combinations(sorted(set(l["teaches"])), 2)}
        out |= {tuple(sorted((a, b))) for a in l["assumes"] for b in l["teaches"]}
    return out


SEED_SUPPORT = 999   # hand verified beats corpus derived, so a seed edge is never the one we drop


def seed_edges():
    """Course descriptions are marketing copy. They say 'assumes basic machine learning', never
    'assumes backpropagation', so the corpus reproduces only 11 of our 34 hand written edges.
    We keep ours and let the corpus connect the skills it discovered."""
    # Read from the frozen seed, never from skills.json, which --apply overwrites. Otherwise a second
    # run would read its own output back in as hand verified and bake corpus noise in permanently.
    src = ROOT / "data/seed_skills.json"
    if not src.exists():
        src.write_text((ROOT / "data/skills.json").read_text())
    seed = json.loads(src.read_text())
    return {(p, s): SEED_SUPPORT for s, v in seed.items() for p in v["prereqs"]}, \
           {s: v["name"] for s, v in seed.items()}


def edges(labels):
    c = Counter()
    for l in labels.values():
        for a in set(l["assumes"]):
            for b in set(l["teaches"]):
                if a != b:
                    c[(a, b)] += 1
    return c


def acyclic(kept, log):
    """Break each cycle by dropping its least supported edge. The corpus votes on direction."""
    g = nx.DiGraph(); g.add_edges_from(kept)
    while True:
        try:
            cycle = nx.find_cycle(g)
        except nx.NetworkXNoCycle:
            return {e: n for e, n in kept.items() if g.has_edge(*e)}
        weakest = min((e[:2] for e in cycle), key=lambda e: kept[e])
        if kept[weakest] == SEED_SUPPORT:
            raise ValueError(f"a cycle of hand written edges: {cycle}. Fix data/seed_skills.json.")
        log.append((weakest, kept[weakest], [e[:2] for e in cycle]))
        g.remove_edge(*weakest)


def main(apply=False):
    tax, labels, courses = load()
    model = StaticModel.from_pretrained("minishlab/potion-base-8M")
    ids, vecs = context(tax, labels, courses, model)
    sim, block = vecs @ vecs.T, blocked(labels)
    cand = sorted([(ids[i], ids[j], float(sim[i, j])) for i in range(len(ids)) for j in range(i + 1, len(ids))
                   if sim[i, j] > SIM and tuple(sorted((ids[i], ids[j]))) not in block], key=lambda x: -x[2])

    e = edges(labels)
    seed, seed_names = seed_edges()
    # Corpus edges may not add prerequisites to a skill we wrote by hand. Descriptions list topics
    # that appear together, not real prerequisites, and one bad edge (cloud before supervised
    # learning) dragged JavaScript and networking into a generative AI path. Our 29 already have
    # correct prerequisites; the corpus is here to connect the skills it discovered.
    corpus = {k: v for k, v in e.items() if v >= MIN_SUPPORT and k[1] not in seed_names}
    kept = {**corpus, **seed}
    broken = []
    kept = acyclic(kept, broken)
    g = nx.transitive_reduction(nx.DiGraph(list(kept)))   # keep only direct prerequisites
    g.add_nodes_from(tax)

    depth = {}
    for n in nx.topological_sort(g):
        depth[n] = 1 + max((depth[p] for p in g.pred[n]), default=-1)
    taught = Counter(s for l in labels.values() for s in l["teaches"])

    print(f"skills {len(tax)} | corpus edges {len(e)} raw, {len(corpus)} kept at support "
          f"{MIN_SUPPORT} and not aimed at a hand written skill, plus {len(seed)} hand written -> {len(kept)} "
          f"-> {g.number_of_edges()} after transitive reduction")
    print(f"merge candidates surviving structural blocks: {len(cand)} (blocked {len(block)})")
    print(f"max depth {max(depth.values())} | roots {sum(1 for n in g if g.in_degree(n) == 0)} "
          f"| taught by nobody {sorted(set(tax) - set(taught))}")
    print("\ncycles broken:")
    for (a, b), n, cyc in broken:
        loop = " -> ".join([x for x, _ in cyc] + [cyc[0][0]])
        print(f"  dropped {a} -> {b} (support {n}) from {loop}")
    print("\nmerge candidates, none applied:")
    for a, b, s in cand[:15]:
        print(f"  {s:.3f}  {tax[a][:30]:<32} | {tax[b][:30]}")
    print("\ndepth spread:", sorted(Counter(depth.values()).items()))

    if not apply:
        print("\nreport only. rerun with --apply to write data/skills.json and data/catalog.json")
        return

    names = {**tax, **seed_names}
    skills = {s: {"name": names[s], "prereqs": sorted(g.pred[s])} for s in sorted(tax)}
    (ROOT / "data/skills.json").write_text(json.dumps(skills, indent=1))

    old = json.loads((ROOT / "data/catalog.json").read_text())
    handmade = [c for c in old if c["kind"] != "course"]        # our projects and assessments stay
    catalog = [{"id": c["id"], "title": c["title"], "provider": c["provider"], "url": c["url"],
                "hours": c["hours"], "level": c["level"], "kind": "course",
                "teaches": labels[c["id"]]["teaches"], "assumes": labels[c["id"]]["assumes"]}
               for c in courses.values() if c["id"] in labels] + handmade
    (ROOT / "data/catalog.json").write_text(json.dumps(catalog, indent=1))

    text = [c["title"] + ". " + courses.get(c["id"], {}).get("description", "")[:300] for c in catalog]
    v = model.encode(text, show_progress_bar=False)
    np.save(ROOT / "data/vectors.npy", (v / np.linalg.norm(v, axis=1, keepdims=True)).astype("float32"))
    print(f"\nwrote {len(skills)} skills, {len(catalog)} catalog items, vectors {v.shape}")


if __name__ == "__main__":
    main("--apply" in sys.argv)
