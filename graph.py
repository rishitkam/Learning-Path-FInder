"""Prerequisite DAG over skills. Pure logic: no LLM, no I/O beyond the initial load."""

import json
from itertools import groupby
from pathlib import Path

import networkx as nx

DATA = Path(__file__).resolve().parent / "data"


class SkillGraph:
    def __init__(self, skills, roles=None):
        self.skills, self.roles = skills, roles or {}
        edges = [(p, s) for s, v in skills.items() for p in v["prereqs"]]

        # Fail at startup, not mid demo: a typo'd id or a cycle makes every path silently wrong.
        unknown = ({p for p, _ in edges} | {s for r in self.roles.values() for s in r}) - set(skills)
        if unknown:
            raise ValueError(f"unknown skill ids: {sorted(unknown)}")

        self.g = nx.DiGraph()
        self.g.add_nodes_from(skills)
        self.g.add_edges_from(edges)
        if not nx.is_directed_acyclic_graph(self.g):
            raise ValueError(f"cycle in skill graph: {nx.find_cycle(self.g)}")

        # depth = longest chain of prerequisites behind a skill. Derived, so it can never
        # contradict the edges the way a hand written "level" field would.
        self.depth = {}
        for s in nx.topological_sort(self.g):
            self.depth[s] = 1 + max((self.depth[p] for p in self.g.pred[s]), default=-1)

    def name(self, skill):
        return self.skills[skill]["name"]

    def role_skills(self, role):
        """Target skills for a known role. Returns None so the caller can fall back to the LLM."""
        return self.roles.get(role)

    def closure(self, known):
        """Knowing a skill implies knowing everything it was built on."""
        return set(known) | {a for k in known for a in nx.ancestors(self.g, k)}

    def gap(self, goal, known=()):
        """Everything the goal depends on, minus everything the learner already has."""
        return self.closure(goal) - self.closure(known)

    def order(self, gap):
        """Teachable order. Tie broken on (depth, id) so the same profile always gives the same path."""
        return list(nx.lexicographical_topological_sort(
            self.g.subgraph(gap), key=lambda s: (self.depth[s], s)))

    def phases(self, gap):
        """Group the ordered skills by depth. Same depth means no prerequisite ties them,
        so a phase is a set of things genuinely learnable in parallel."""
        return [list(g) for _, g in groupby(self.order(gap), key=self.depth.get)]


def load(data=DATA):
    read = lambda f: json.loads((data / f).read_text())
    return SkillGraph(read("skills.json"), read("roles.json"))
