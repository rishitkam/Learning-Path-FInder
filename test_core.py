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
    """A course teaching two skills is the module for both, but it is only that much work once.
    Scheduled hours are exactly the distinct courses plus the milestones and checks attached."""
    for role in g.roles:
        r = build(g, g.gap(g.role_skills(role)), PROFILE, cat)
        mods = [m for ph in r["phases"] for m in ph["modules"] if m["resource"]]
        distinct = {m["resource"]["id"]: m["resource"]["hours"] for m in mods}
        extras = sum(ph[k]["hours"] for ph in r["phases"] for k in ("milestone", "assessment") if ph[k])
        assert sum(ph["hours"] for ph in r["phases"]) == sum(distinct.values()) + extras, role


def test_milestone_is_never_also_a_module(g, cat):
    for role in g.roles:
        r = build(g, g.gap(g.role_skills(role)), PROFILE, cat)
        mods = {m["resource"]["id"] for ph in r["phases"] for m in ph["modules"] if m["resource"]}
        extras = {ph[k]["id"] for ph in r["phases"] for k in ("milestone", "assessment") if ph[k]}
        assert not mods & extras, role


def test_a_long_course_loses_to_a_short_one_that_teaches_the_skill(g, cat):
    """A small semantic edge used to win the whole relevance term, which sent people into a 173 hour
    specialisation to learn Git. Over the cap is allowed only when nothing shorter teaches it."""
    from path import MAX_WEEKS_PER_COURSE
    cap = PROFILE["weekly_hours"] * MAX_WEEKS_PER_COURSE
    r = build(g, g.gap(g.role_skills("machine-learning-engineer")), PROFILE, cat)
    for phase in r["phases"]:
        for module in phase["modules"]:
            if module["resource"] and module["resource"]["hours"] > cap:
                shorter = [c for c in cat if module["skill"] in c["teaches"]
                           and c["kind"] != "assessment" and c["hours"] <= cap]
                assert not shorter, f"{module['skill']} took a long course over {shorter}"


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
    assert st.progress(st.new({}), {"phases": [], "total_weeks": 0})["percent"] == 0


def test_progress_agrees_with_the_schedule(g, cat):
    """The dashboard must not say 74 weeks left beside a roadmap that ends at week 76."""
    for role in g.roles:
        r = build(g, g.gap(g.role_skills(role)), PROFILE, cat)
        s = st.new({**PROFILE, "goal_skills": g.role_skills(role)})
        assert st.progress(s, r)["weeks_left"] == r["total_weeks"], role
        every = [m["skill"] for ph in r["phases"] for m in ph["modules"]]
        assert st.progress({**s, "completed": every}, r)["weeks_left"] == 0, role


def test_a_shared_course_is_not_counted_as_work_twice(g, cat):
    """progress had the same double count that build did, and reported 587 hours against 520."""
    r = build(g, g.gap(g.role_skills("genai-engineer"), ["prog.python"]), PROFILE, cat, ["prog.python"])
    s = st.new({**PROFILE, "goal_skills": g.role_skills("genai-engineer")})
    assert st.progress(s, r)["hours_total"] == sum(ph["hours"] for ph in r["phases"])


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


def test_relevance_survives_a_reordered_catalog_and_refuses_an_unknown_one(cat):
    """Vectors used to be matched by position, so reversing the catalog silently scored every course
    against the wrong vector. They are looked up by id now, and a course we have no vector for is a
    loud error rather than a wrong number."""
    goal = "i want to build machine learning systems"
    forward, backward = relevance(goal, cat), relevance(goal, list(reversed(cat)))
    assert all(abs(forward(c) - backward(c)) < 1e-9 for c in cat[:40])
    assert relevance(goal, cat[:10])(cat[0])                      # a subset is fine
    with pytest.raises(ValueError, match="no vector"):
        relevance(goal, cat + [{**cat[0], "id": "ghost.course"}])


# --- the data on disk ---------------------------------------------------------------------------

def test_catalog_and_vectors_line_up(cat):
    assert len(np.load("data/vectors.npy")) == len(cat)


def test_every_catalog_skill_exists_and_every_skill_is_teachable(g, cat):
    """Teachable means a course or a project. An assessment is a check, not a way to learn something,
    and build() will not offer one as a module, so counting them hid a real gap."""
    assert not {s for c in cat for s in c["teaches"] + c["assumes"]} - set(g.skills)
    assert not [s for s in g.skills
                if not any(s in c["teaches"] and c["kind"] != "assessment" for c in cat)]


def test_hand_added_catalog_items_survive_a_rebuild(cat):
    """They cover skills the scraped catalog does not reach, so losing them reopens those gaps."""
    handmade = [c for c in cat if c.get("handmade")]
    assert {"eng.git", "dl.backprop"} <= {s for c in handmade for s in c["teaches"]}


def test_the_frozen_seed_is_still_the_hand_written_one():
    """If this grows, someone let the build read its own output back in as hand written truth."""
    assert len(json.load(open("data/seed_skills.json"))) == 29


# --- the HTTP contract, no model calls ----------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import api
    return TestClient(api.app)


def test_the_profile_the_api_returns_is_one_it_will_accept_back(client):
    """The interface echoes the profile on the next turn. When a field was missing from the response
    the model default silently refilled it, and when weekly_hours came back null we rejected our own
    output with a 422 that reached the screen as [object Object]."""
    body = {"profile": {"goal_text": "ml engineer", "role": "machine-learning-engineer",
                        "known_skills": ["prog.python"], "weekly_hours": 10}}
    first = client.post("/path", json=body)
    assert first.status_code == 200
    again = client.post("/path", json={"profile": first.json()["profile"], "completed": [], "blocked": []})
    assert again.status_code == 200, again.text
    assert again.json()["profile"]["role"] == "machine-learning-engineer"


def test_a_path_is_refused_rather_than_invented(client):
    assert client.post("/path", json={"profile": {}}).status_code == 422
    assert client.post("/path", json={"profile": {"role": "data-analyst"}}).status_code == 422


def test_feedback_carries_back_everything_it_changed(client):
    body = {"profile": {"role": "machine-learning-engineer", "known_skills": ["prog.python"],
                        "weekly_hours": 10, "level": 3}, "completed": [], "blocked": []}
    path = client.post("/path", json=body).json()
    resource = path["progress"]["next_action"]["resource"]["id"]
    harder = client.post("/path/feedback", json={**body, "event": "too_hard", "resource_id": resource}).json()
    assert harder["profile"]["level"] == 2 and resource in harder["state"]["blocked"]
    known = client.post("/path/feedback", json={**body, "event": "already_know", "skill": "math.stats"}).json()
    assert "math.stats" in known["profile"]["known_skills"]
    assert known["progress"]["skills_total"] < path["progress"]["skills_total"]


# --- persistence ---------------------------------------------------------------------------------

def test_a_learner_is_remembered_and_two_learners_do_not_mix(client):
    import db
    for who in ("alice", "bob"):
        client.delete("/state", headers={"X-Learner-Id": who})
    body = {"profile": {"role": "data-analyst", "known_skills": ["prog.python"], "weekly_hours": 10}}
    built = client.post("/path", json=body, headers={"X-Learner-Id": "alice"}).json()

    back = client.get("/state", headers={"X-Learner-Id": "alice"}).json()
    assert back["data"]["path"]["total_weeks"] == built["path"]["total_weeks"]
    assert client.get("/state", headers={"X-Learner-Id": "bob"}).json()["data"] is None
    assert client.get("/state").json()["data"] is None          # no id at all is not an error

    client.post("/path/feedback", headers={"X-Learner-Id": "alice"},
                json={"profile": back["data"]["profile"], "completed": [], "blocked": [],
                      "event": "already_know", "skill": "math.stats"})
    after = client.get("/state", headers={"X-Learner-Id": "alice"}).json()
    assert "math.stats" in after["data"]["profile"]["known_skills"]
    assert after["data"]["progress"]["skills_total"] < built["progress"]["skills_total"]

    client.delete("/state", headers={"X-Learner-Id": "alice"})
    assert client.get("/state", headers={"X-Learner-Id": "alice"}).json()["data"] is None


def test_the_transcript_is_capped_rather_than_archived():
    import db
    db.forget("chatty")
    for i in range(30):
        db.save("chatty", {"weekly_hours": 5}, [{"role": "user", "content": str(i)}])
    assert len(db.load("chatty")[1]) == db.TURNS_KEPT
    db.forget("chatty")


# --- per learner weights -------------------------------------------------------------------------

def test_weights_start_at_the_defaults_and_always_sum_to_one():
    from path import W
    weights = st.new({})["weights"]
    assert weights == W
    for _ in range(30):
        weights = st._reweigh(weights, "level", st.STEP)
    assert abs(sum(weights.values()) - 1) < 0.01
    assert max(weights.values()) <= st.CEILING and min(weights.values()) >= st.FLOOR - 0.01


def test_each_reaction_blames_the_right_signal():
    base = st.new({"weekly_hours": 10, "level": 3})
    short, long = {"resource": {"hours": 12}}, {"resource": {"hours": 200}}
    rose = lambda before, after, term: after["weights"][term] > before["weights"][term]
    assert rose(base, st.apply(base, "too_hard", resource_id="a", module=short), "level")
    assert rose(base, st.apply(base, "too_easy", resource_id="b", module=short), "level")
    assert rose(base, st.apply(base, "not_interested", resource_id="c", module=short), "relevance")
    # Only the vague reaction gets second guessed. Too hard already told us why.
    assert rose(base, st.apply(base, "not_interested", resource_id="d", module=long), "effort")
    assert rose(base, st.apply(base, "too_hard", resource_id="e", module=long), "level")


def test_already_know_says_nothing_about_ranking():
    base = st.new({"weekly_hours": 10})
    assert st.apply(base, "already_know", skill="math.stats")["weights"] == base["weights"]


def test_a_repeated_click_moves_the_weights_once():
    state = st.new({"weekly_hours": 10, "level": 3})
    once = st.apply(state, "too_hard", resource_id="same", module={"resource": {"hours": 12}})
    twice = st.apply(once, "too_hard", resource_id="same", module={"resource": {"hours": 12}})
    assert once["weights"] == twice["weights"]


def test_a_new_goal_resets_what_was_about_the_goal(g):
    weights = st.new({})["weights"]
    for _ in range(6):
        weights = st._reweigh(weights, "level", st.STEP)
    for _ in range(4):
        weights = st._reweigh(weights, "relevance", st.STEP)
    after = st.refocus(weights)
    assert after["relevance"] != weights["relevance"]      # was about the old goal
    assert after["level"] > st.new({})["weights"]["level"]  # is about the person
    assert abs(sum(after.values()) - 1) < 0.01


def test_weights_actually_change_which_course_wins(g, cat):
    """Needs a learner with a goal in their own words. Without one, relevance is constant for every
    course and style matches nothing, so half the ranking is switched off and the test proves nothing.
    We believed the weights were dead for a while because the evals had this same blind spot."""
    from embed import relevance
    profile = {**PROFILE, "goal_text": "i want to build machine learning systems in production"}
    gap = g.gap(g.role_skills("machine-learning-engineer"))
    rel = relevance(profile["goal_text"], cat)
    picks = lambda w: [(m["skill"], (m["resource"] or {}).get("id"))
                       for ph in build(g, gap, profile, cat, weights=w, relevance=rel)["phases"]
                       for m in ph["modules"]]
    lengthy = {"relevance": 0.05, "level": 0.05, "style": 0.05, "effort": 0.85}
    assert picks(None) != picks(lengthy)


# --- the deadline ---------------------------------------------------------------------------------

def test_the_deadline_never_changes_the_plan(g, cat):
    """Trimming to hit a date means dropping skills or taking worse courses, and then the plan quietly
    stops being the plan. We build the honest route and say what the date would cost."""
    gap = g.gap(g.role_skills("machine-learning-engineer"))
    picks = lambda horizon: [(m["skill"], (m["resource"] or {}).get("id"))
                             for ph in build(g, gap, {**PROFILE, "horizon_weeks": horizon}, cat)["phases"]
                             for m in ph["modules"]]
    assert picks(None) == picks(4) == picks(200)


def test_an_impossible_deadline_says_what_it_would_take(g, cat):
    gap = g.gap(g.role_skills("machine-learning-engineer"))
    tight = build(g, gap, {**PROFILE, "horizon_weeks": 4}, cat)
    assert not tight["feasible"]
    assert tight["weekly_hours_needed"] > PROFILE["weekly_hours"]
    assert tight["weekly_hours_needed"] == -(-tight["total_hours"] // 4)      # ceil, no rounding down
    roomy = build(g, gap, {**PROFILE, "horizon_weeks": 200}, cat)
    assert roomy["feasible"] and roomy["weekly_hours_needed"] is None


def test_more_hours_a_week_is_a_real_lever(g, cat):
    gap = g.gap(g.role_skills("machine-learning-engineer"))
    slow = build(g, gap, {**PROFILE, "weekly_hours": 8}, cat)["total_weeks"]
    fast = build(g, gap, {**PROFILE, "weekly_hours": 40}, cat)["total_weeks"]
    assert fast < slow


def test_the_explainer_is_told_it_cannot_promise_changes():
    """It once answered "shorten the path" with "we'll trim total hours", having trimmed nothing."""
    import explain
    for banned in ["never say or imply that you have", "we will", "promises a change"]:
        assert banned in explain.SYS_ASK


# --- holding up under load and abuse --------------------------------------------------------------

def test_the_database_survives_concurrent_writers():
    """FastAPI answers on a thread pool. One sqlite connection shared across threads without
    serialising raises "bad parameter or other API misuse", which it did, six times in eighty."""
    from concurrent.futures import ThreadPoolExecutor
    import db
    db.forget("crowd")
    def write(i):
        db.save("crowd", {"weekly_hours": i}, [{"role": "user", "content": str(i)}])
        return db.load("crowd")
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(write, range(60)))
    assert all(state is not None for state, _ in results)
    assert len(db.load("crowd")[1]) <= db.TURNS_KEPT
    db.forget("crowd")


def test_a_goal_we_do_not_recognise_is_refused_not_answered_with_nothing(client):
    """It used to return 200 and an empty plan, which reads on screen as though no goal was given."""
    made_up = {"profile": {"role": None, "goal_skills": ["not.a.skill"], "weekly_hours": 10}}
    assert client.post("/path", json=made_up).status_code == 422


def test_a_skill_id_that_vanished_in_a_rebuild_does_not_lock_someone_out(client):
    """Saved learners outlive catalog rebuilds, so a stale id is dropped rather than fatal."""
    body = {"profile": {"role": None, "goal_skills": ["gone.away", "ml.supervised"], "weekly_hours": 10}}
    assert client.post("/path", json=body).status_code == 200


def test_free_text_from_a_learner_is_bounded(client):
    assert client.post("/path", json={"profile": {"role": "data-analyst", "weekly_hours": 10,
                                                  "goal_text": "a" * 100_000}}).status_code == 422


def test_the_embedding_model_loads_once_under_a_stampede():
    """lru_cache remembers a result, it does not stop two threads running the loader at once. Two
    concurrent first requests both entered it and tqdm raised inside, surfacing as a 500."""
    from concurrent.futures import ThreadPoolExecutor
    import embed
    embed._load_model.cache_clear()
    embed._load_vectors.cache_clear()
    with ThreadPoolExecutor(max_workers=12) as pool:
        models = list(pool.map(lambda _: embed._model(), range(12)))
    assert all(model is models[0] for model in models)
    assert embed._load_model.cache_info().misses == 1


def test_an_unreachable_model_is_reported_not_swallowed(monkeypatch):
    """A rate limited extraction used to return an empty profile, so the assistant asked the same
    question forever and nothing said why. It also scored in the evals as the model being wrong."""
    import profile as pf
    def refuse(**_):
        raise RuntimeError("429 rate limit")
    monkeypatch.setattr(pf, "call", refuse)
    with pytest.raises(pf.Unavailable):
        pf.extract(load(), "learner: i want to be a data analyst")


def test_the_chat_says_so_when_the_model_is_unreachable(client, monkeypatch):
    import api, profile as pf
    monkeypatch.setattr(api.learner_profile, "extract",
                        lambda *a, **k: (_ for _ in ()).throw(pf.Unavailable("429")))
    reply = client.post("/chat", json={"message": "hi", "profile": None, "completed": [],
                                       "blocked": [], "history": []}).json()["reply"]
    assert "could not reach" in reply.lower()


def _stub_extraction(monkeypatch, payload):
    """Make the model return exactly `payload` from its tool call, no network."""
    import profile as pf, json as _json
    class _Fn:
        arguments = _json.dumps(payload)
    class _Call:
        function = _Fn()
    class _Msg:
        tool_calls = [_Call()]
    class _Choice:
        message = _Msg()
    class _Resp:
        choices = [_Choice()]
    monkeypatch.setattr(pf, "call", lambda **_: _Resp())


def test_an_out_of_scope_goal_clears_the_goal_we_guessed_before(monkeypatch):
    """Told "architect" then "I meant BUILDINGS", the extractor kept cs.architecture from the first
    reading, because the merge drops empty lists so a quiet turn cannot wipe what we know. That also
    stopped a correction undoing a wrong guess, and the learner got Programming Fundamentals."""
    import profile as pf
    _stub_extraction(monkeypatch, {"goal_text": "I want to design buildings", "out_of_scope": True,
                                   "role": None, "goal_skills": [], "known_skills": [],
                                   "weekly_hours": None, "horizon_weeks": None, "level": None,
                                   "style": None})
    prior = {"goal_text": "i want to be an architect", "role": "solutions-architect",
             "goal_skills": ["cs.architecture", "prog.fundamentals"], "known_skills": [],
             "weekly_hours": 19, "horizon_weeks": 4, "level": 2, "style": "project first"}
    out = pf.extract(load(), "learner: I want to design buildings", prior)
    assert out["out_of_scope"] is True
    assert out["goal_skills"] == []          # the guessed software skills are gone
    assert out.get("role") is None           # and so is the role they never asked for
    assert out["goal_text"] == "I want to design buildings"   # their correction, not the old text


def test_out_of_scope_refuses_even_when_the_model_still_named_skills(client, monkeypatch):
    """The guard used to require goal_skills to be empty as well, which meant it could never fire:
    the extractor is told to map any goal to the closest skills, so the list is almost never empty."""
    import api
    monkeypatch.setattr(api.learner_profile, "extract", lambda *a, **k: {
        "goal_text": "i want to design buildings", "out_of_scope": True,
        "role": None, "goal_skills": ["cs.architecture"], "known_skills": [],
        "weekly_hours": 10, "horizon_weeks": 8, "level": 2, "style": "balanced"})
    body = client.post("/chat", json={"message": "i want to design buildings", "profile": None,
                                      "completed": [], "blocked": [], "history": []}).json()
    assert "outside what i have courses for" in body["reply"].lower()
    assert body.get("data") is None          # and no path was built anyway


def test_a_mis_clicked_known_skill_can_be_taken_back(g):
    """Marking a skill known subtracts it from the gap, so a mis-click deleted a prerequisite from
    the plan and nothing could put it back short of throwing the whole route away."""
    import state as st
    s = st.new({"role": "machine-learning-engineer", "goal_skills": [], "known_skills": [],
                "weekly_hours": 10, "horizon_weeks": 20, "level": 2, "style": "project first",
                "goal_text": "ml engineer"})
    s = st.apply(s, "already_know", "prog.python")
    assert s["known_skills"] == ["prog.python"]
    s = st.apply(s, "already_know", "prog.python")
    assert s["known_skills"] == []          # pressing again takes it back
    s = st.apply(s, "completed", "ml.evaluation")
    assert s["completed"] == ["ml.evaluation"]
    s = st.apply(s, "completed", "ml.evaluation")
    assert s["completed"] == []


def test_taking_a_skill_back_puts_the_step_back_in_the_plan(g):
    """The point of the undo: the prerequisite everything downstream assumes has to reappear."""
    import state as st
    from path import build, load_catalog
    catalog = load_catalog(g)
    profile = {"role": "machine-learning-engineer", "goal_skills": [], "weekly_hours": 10,
               "horizon_weeks": 20, "level": 2, "style": "project first", "goal_text": "ml engineer"}
    wanted = g.role_skills("machine-learning-engineer")
    teaches = lambda known: any(
        m["skill"] == "prog.python"
        for phase in build(g, g.gap(wanted, known), profile, catalog, known)["phases"]
        for m in phase["modules"])
    assert not teaches(["prog.python"])     # while we think they know it, the step is gone
    assert teaches([])                      # once taken back, it returns


def test_a_retraction_in_chat_removes_the_skill(monkeypatch):
    """An empty known_skills cannot mean "forget it", because the merge ignores empty lists so a
    quiet turn cannot wipe the profile. Retraction needs its own field."""
    import profile as pf
    _stub_extraction(monkeypatch, {"goal_text": "ml engineer", "out_of_scope": False,
                                   "role": None, "goal_skills": [], "known_skills": [],
                                   "retracted_skills": ["prog.python"], "weekly_hours": None,
                                   "horizon_weeks": None, "level": None, "style": None})
    prior = {"goal_text": "ml engineer", "known_skills": ["prog.python", "math.stats"],
             "goal_skills": ["ml.evaluation"], "weekly_hours": 10, "horizon_weeks": 20,
             "level": 2, "style": "project first"}
    out = pf.extract(load(), "learner: i never actually used python", prior)
    assert out["known_skills"] == ["math.stats"]        # only the retracted one goes
    assert "retracted_skills" not in out               # and it never reaches the profile


def test_a_quiet_turn_still_cannot_wipe_what_we_know(monkeypatch):
    """The protection the retraction field exists to preserve: "ok" must change nothing."""
    import profile as pf
    _stub_extraction(monkeypatch, {"goal_text": None, "out_of_scope": False, "role": None,
                                   "goal_skills": [], "known_skills": [], "retracted_skills": [],
                                   "weekly_hours": None, "horizon_weeks": None, "level": None,
                                   "style": None})
    prior = {"goal_text": "ml engineer", "known_skills": ["prog.python"],
             "goal_skills": ["ml.evaluation"], "weekly_hours": 10, "horizon_weeks": 20,
             "level": 2, "style": "project first"}
    out = pf.extract(load(), "learner: ok", prior)
    assert out["known_skills"] == ["prog.python"]
    assert out["goal_skills"] == ["ml.evaluation"]
