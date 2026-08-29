"""Locks in the invariants we cannot afford to lose. No API calls, runs in about a second.

Everything here was a real bug at some point. If one of these fails, read decisions.md before
changing the test, because the test is probably right.
"""

import json

import numpy as np
import pytest

import state as st
from embed import relevance
from graph import SkillGraph, load
from path import build, load_catalog
from profile import _clean

PROFILE = {"level": 2, "style": "project first", "weekly_hours": 10, "horizon_weeks": 40}


@pytest.fixture(scope="module")
def g():
    return load()


@pytest.fixture(scope="module")
def cat(g):
    return load_catalog(g)


# --- the graph refuses to load anything wrong ---------------------------------------------------

def test_cycle_is_rejected():
    with pytest.raises(ValueError, match="cycle"):
        SkillGraph({"a": {"name": "A", "prereqs": ["b"]}, "b": {"name": "B", "prereqs": ["a"]}})


def test_unknown_prereq_is_rejected():
    with pytest.raises(ValueError, match="unknown"):
        SkillGraph({"a": {"name": "A", "prereqs": ["ghost"]}})


def test_real_graph_is_a_dag(g):
    assert g.depth and max(g.depth.values()) > 0


# --- gap and ordering ---------------------------------------------------------------------------

def test_known_skill_closes_downward(g):
    """Saying you know transformers must not also ask you to tick backpropagation."""
    assert "dl.backprop" in g.closure(["dl.transformers"])


def test_gap_is_goal_minus_known(g):
    goal = ["dl.transformers"]
    assert len(g.gap(goal, ["dl.backprop"])) < len(g.gap(goal))


def test_unknown_ids_are_ignored_not_fatal(g):
    assert g.closure(["prog.python", "typo.skill"]) == g.closure(["prog.python"])
    assert g.order({"prog.python", "typo.skill"}) == ["prog.python"]


def test_order_is_topological_and_stable(g):
    gap = g.gap(g.role_skills("genai-engineer"))
    order = g.order(gap)
    at = {s: i for i, s in enumerate(order)}
    assert all(at[p] < at[s] for s in order for p in g.g.pred[s] if p in at)
    assert order == g.order(gap)


def test_phases_are_contiguous_by_depth(g):
    """A phase means skills at one depth, so no phase may contain a prerequisite of its own members."""
    for group in g.phases(g.gap(g.role_skills("genai-engineer"))):
        assert not any(p in group for s in group for p in g.g.pred[s])


# --- the path -----------------------------------------------------------------------------------

def test_every_role_orders_prerequisites_correctly(g, cat):
    for role in g.roles:
        r = build(g, g.gap(g.role_skills(role)), PROFILE, cat)
        at = {s: i for i, ph in enumerate(r["phases"]) for s in ph["skills"]}
        assert not [(p, s) for s in at for p in g.g.pred[s] if p in at and at[p] > at[s]], role


def test_one_course_is_counted_once(g, cat):
    """A course teaching two skills is the module for both, but it is only that much work once."""
    r = build(g, g.gap(g.role_skills("data-analyst")), PROFILE, cat)
    mods = [m for ph in r["phases"] for m in ph["modules"] if m["resource"]]
    distinct = {m["resource"]["id"]: m["resource"]["hours"] for m in mods}
    assert sum(ph["hours"] for ph in r["phases"]) >= sum(distinct.values())
    assert sum(ph["hours"] for ph in r["phases"]) < sum(m["resource"]["hours"] for m in mods) + 1


def test_milestone_is_never_also_a_module(g, cat):
    for role in g.roles:
        r = build(g, g.gap(g.role_skills(role)), PROFILE, cat)
        mods = {m["resource"]["id"] for ph in r["phases"] for m in ph["modules"] if m["resource"]}
        extras = {ph[k]["id"] for ph in r["phases"] for k in ("milestone", "assessment") if ph[k]}
        assert not mods & extras, role


def test_picks_do_not_depend_on_catalog_order(g, cat):
    pick = lambda c: [(m["skill"], (m["resource"] or {}).get("id"))
                      for ph in build(g, g.gap(g.role_skills("nlp-engineer")), PROFILE, c)["phases"]
                      for m in ph["modules"]]
    assert pick(cat) == pick(list(reversed(cat)))


def test_blocked_swaps_the_course_but_keeps_the_skill(g, cat):
    gap = g.gap(g.role_skills("data-scientist"))
    before = build(g, gap, PROFILE, cat)
    first = next(m for ph in before["phases"] for m in ph["modules"] if m["resource"])
    after = build(g, gap, PROFILE, cat, blocked=[first["resource"]["id"]])
    skills = lambda r: [m["skill"] for ph in r["phases"] for m in ph["modules"]]
    assert skills(before) == skills(after)
    assert first["resource"]["id"] not in {(m["resource"] or {}).get("id")
                                           for ph in after["phases"] for m in ph["modules"]}


def test_build_survives_a_bare_state(g, cat):
    """A fresh state has no level and no hours, and must not divide by zero or compare None."""
    s = st.new({"goal_skills": ["ml.supervised"]})
    assert build(g, g.gap(s["goal_skills"]), s, cat)["phases"]


def test_no_deadline_means_feasible_and_zero_does_not(g, cat):
    gap = g.gap(g.role_skills("data-analyst"))
    assert build(g, gap, {**PROFILE, "horizon_weeks": None}, cat)["feasible"]
    assert not build(g, gap, {**PROFILE, "horizon_weeks": 0}, cat)["feasible"]


# --- feedback -----------------------------------------------------------------------------------

def test_feedback_does_not_mutate_the_state_it_was_given():
    s = st.new({"goal_skills": ["nlp.rag"], "known_skills": ["prog.python"], "weekly_hours": 10})
    st.apply(s, "already_know", skill="math.stats")
    st.apply(s, "too_hard", resource_id="c.x")
    assert s["known_skills"] == ["prog.python"] and s["blocked"] == []


def test_repeating_the_same_click_moves_the_level_once():
    s = st.new({"level": 3})
    for _ in range(4):
        s = st.apply(s, "too_hard", resource_id="c.x")
    assert s["level"] == 2 and s["blocked"] == ["c.x"]


def test_already_know_shortens_the_path_but_completed_does_not(g, cat):
    base = {"goal_skills": g.role_skills("nlp-engineer"), "known_skills": [], "weekly_hours": 10,
            "level": 2, "style": "balanced"}
    s = st.new(base)
    n = lambda s: len(g.gap(s["goal_skills"], s["known_skills"]))
    assert n(st.apply(s, "already_know", skill="math.stats")) < n(s)
    assert n(st.apply(s, "completed", skill="math.stats")) == n(s)


def test_progress_handles_an_empty_path():
    assert st.progress(st.new({}), {"phases": []})["percent"] == 0


# --- the profile cleaner never raises -----------------------------------------------------------

@pytest.mark.parametrize("bad", [{"weekly_hours": "10"}, {"level": "3"}, {"role": ["data-analyst"]},
                                 {"goal_skills": 3}, {"known_skills": None}, {"weekly_hours": 0},
                                 {"style": 7}, {"goal_text": "   "}, {}])
def test_clean_survives_whatever_the_model_returns(g, bad):
    out = _clean(g, dict(bad))
    assert out["level"] in range(1, 6)
    assert out["weekly_hours"] is None or 1 <= out["weekly_hours"] <= 60


def test_a_stale_role_does_not_overwrite_stated_skills(g):
    assert _clean(g, {"role": "data-analyst", "goal_skills": ["nlp.llm"]})["goal_skills"] == ["nlp.llm"]


def test_role_skills_are_copied_not_shared(g):
    assert _clean(g, {"role": "data-analyst"})["goal_skills"] is not g.roles["data-analyst"]


# --- relevance ----------------------------------------------------------------------------------

@pytest.mark.parametrize("empty", [None, "", "   "])
def test_relevance_is_flat_without_a_usable_goal(cat, empty):
    assert relevance(empty, cat)(cat[0]) == 0.5


def test_relevance_refuses_a_catalog_it_was_not_built_for(cat):
    with pytest.raises(ValueError, match="vectors"):
        relevance("data engineering", cat[:10])


# --- the data on disk ---------------------------------------------------------------------------

def test_catalog_and_vectors_line_up(cat):
    assert len(np.load("data/vectors.npy")) == len(cat)


def test_every_catalog_skill_exists_and_every_skill_is_teachable(g, cat):
    assert not {s for c in cat for s in c["teaches"] + c["assumes"]} - set(g.skills)
    assert not [s for s in g.skills if not any(s in c["teaches"] for c in cat)]


def test_the_frozen_seed_is_still_the_hand_written_one():
    """If this grows, someone let the build read its own output back in as hand written truth."""
    assert len(json.load(open("data/seed_skills.json"))) == 29
