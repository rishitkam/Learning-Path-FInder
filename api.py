"""HTTP adapter for the deterministic learning-path engine."""

import os
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
import graph
import path
import state
import profile as learner_profile
import explain
from embed import relevance, warm

# In production, FRONTEND_URL is set in the Render dashboard so the deployed
# Vercel URL is whitelisted. Locally it falls back to the dev ports.
_frontend = os.getenv("FRONTEND_URL", "")
_origins = ["http://localhost:3000", "http://localhost:3001"]
if _frontend:
    _origins.append(_frontend.rstrip("/"))

@asynccontextmanager
async def lifespan(_):
    """Graph, catalog and embedding model loaded before the first request rather than during it."""
    engine()
    warm()
    yield


app = FastAPI(title="Learning Path Finder API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Named learner_id, not learner: several endpoints already use `learner` for the state dict.
LearnerId = Header(default=None, alias="X-Learner-Id")


def stored(learner_id):
    """Weights and completion belong to the learner, not to the request, so they come from us."""
    saved, _ = db.load(learner_id)
    return saved or {}


def remember(learner_id, response, turns=()):
    """Save on the way out. The endpoints already receive and return the whole state, so persistence
    is one line each rather than a set of endpoints of its own."""
    db.save(learner_id, response["state"], turns)
    return response


@lru_cache(maxsize=1)
def engine():
    learning_graph = graph.load()
    return learning_graph, path.load_catalog(learning_graph)



class LearnerProfile(BaseModel):
    # Neutral defaults on purpose. A missing field must not quietly invent a goal for someone.
    goal_text: str = Field(default="", max_length=2_000)
    role: str | None = None
    goal_skills: list[str] = Field(default_factory=list)
    known_skills: list[str] = Field(default_factory=list)
    # Nullable because /chat hands this profile back before the learner has said how much time they
    # have, and the interface sends it straight back to us on the next turn.
    weekly_hours: float | None = Field(default=None, ge=1, le=60)
    horizon_weeks: int | None = Field(default=24, ge=1)
    level: int = Field(default=2, ge=1, le=5)
    style: Literal["balanced", "project first", "theory first"] = "balanced"


class PathRequest(BaseModel):
    profile: LearnerProfile
    completed: list[str] = Field(default_factory=list)
    blocked: list[str] = Field(default_factory=list)


class FeedbackRequest(PathRequest):
    event: Literal["already_know", "completed", "too_hard", "too_easy", "not_interested"]
    skill: str | None = None
    resource_id: str | None = None


class Turn(BaseModel):
    role: Literal["assistant", "user"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)
    # The conversation so far. Extraction reads the whole thing, because "15" only means anything
    # next to the question we just asked.
    history: list[Turn] = Field(default_factory=list, max_length=40)
    profile: LearnerProfile | None = None
    completed: list[str] = Field(default_factory=list)
    blocked: list[str] = Field(default_factory=list)


PROFILE_KEYS = ("role", "goal_skills", "known_skills", "weekly_hours", "horizon_weeks", "level", "style")


def build_response(profile: dict, completed=(), blocked=(), weights=None):
    """Takes a plain profile dict rather than the request, so feedback can hand back the profile it
    changed. Passing the request through meant a level drop or a newly known skill was thrown away."""
    learning_graph, catalog = engine()
    goal_skills = profile.get("goal_skills") or learning_graph.role_skills(profile.get("role") or "")
    # Drop ids the graph no longer has rather than failing, so a learner saved before a catalog
    # rebuild still loads. Only refuse when nothing they asked for is left.
    goal_skills = [skill for skill in (goal_skills or []) if skill in learning_graph.skills]
    if not goal_skills:
        raise HTTPException(status_code=422, detail="Choose a supported role or at least one goal skill.")
    if not profile.get("weekly_hours"):
        raise HTTPException(status_code=422, detail="Tell us how many hours a week you can give this.")
    learner = state.new({**profile, "goal_skills": goal_skills, "weights": weights})
    learner["completed"], learner["blocked"] = list(completed), list(blocked)
    roadmap = path.build(
        learning_graph,
        learning_graph.gap(goal_skills, learner["known_skills"]),
        learner,
        catalog,
        known=learner["known_skills"],
        blocked=learner["blocked"],
        relevance=relevance(learner.get("goal_text"), catalog),
        weights=learner["weights"],
    )
    # Carry the whole profile back, not only the fields state tracks, or role goes missing from the
    # response and the next request rebuilds it from the model default.
    return {"profile": {**profile, **{k: learner[k] for k in LearnerProfile.model_fields if k in learner}},
            "path": roadmap, "progress": state.progress(learner, roadmap), "state": learner}


@app.get("/state")
def read_state(learner_id: str | None = LearnerId):
    """What we know about them, rebuilt into a path. Unknown ids are new people, not errors."""
    state, turns = db.load(learner_id)
    if not state:
        return {"data": None, "turns": turns}
    try:
        return {"data": build_response(state, state.get("completed", []), state.get("blocked", []),
                                       state.get("weights")), "turns": turns}
    except HTTPException:
        return {"data": None, "turns": turns}      # they never finished telling us enough


@app.delete("/state")
def forget_state(learner_id: str | None = LearnerId):
    db.forget(learner_id)
    return {"ok": True}


@app.get("/health")
def health():
    learning_graph, catalog = engine()
    return {"ok": True, "skills": len(learning_graph.skills), "resources": len(catalog)}


@app.post("/path")
def generate_path(request: PathRequest, learner_id: str | None = LearnerId):
    return remember(learner_id, build_response(request.profile.model_dump(), request.completed,
                                               request.blocked, stored(learner_id).get("weights")))


@app.post("/path/feedback")
def apply_feedback(request: FeedbackRequest, learner_id: str | None = LearnerId):
    profile = request.profile.model_dump()
    before = build_response(profile, request.completed, request.blocked, stored(learner_id).get("weights"))
    learner = before["state"]
    # The module they reacted to, so a rejection can tell length apart from difficulty.
    module = next((m for phase in before["path"]["phases"] for m in phase["modules"]
                   if m["skill"] == request.skill
                   or (m["resource"] or {}).get("id") == request.resource_id), None)
    after = state.apply(learner, request.event, request.skill, request.resource_id, module)
    # Every field feedback can change has to travel back, not just the two lists.
    return remember(learner_id, build_response(
        {**profile, "level": after["level"], "known_skills": after["known_skills"]},
        after["completed"], after["blocked"], after["weights"]))


def _cannot_do_that(current):
    """A change we have no lever for. The model used to answer these itself and would promise to trim
    the plan, which is the one hallucination this whole design exists to prevent. So we answer with
    arithmetic instead: what the route costs, what their deadline would cost, and what actually helps.
    """
    plan, profile = current["path"], current["profile"]
    said = [f"Your route is {plan['total_weeks']} weeks, {plan['total_hours']} hours of study."]
    if plan["weekly_hours_needed"]:
        said.append(f"You asked for {profile['horizon_weeks']} weeks, which would take about "
                    f"{plan['weekly_hours_needed']} hours a week rather than {profile['weekly_hours']}.")
    said.append("I cannot cut steps out to make it shorter, because the prerequisites are what they are. "
                "What does shorten it: more hours a week, telling me what you already know, or a "
                "narrower goal.")
    return " ".join(said)


def _reply(learning_graph, prior, current):
    """On the first path, name the skills it starts with and ask whether they already have any.

    Known skills prune whole branches off the graph, so this is the question that changes a path the
    most. We ask it after building rather than before, so they see something first, and we can name
    their actual first steps instead of asking in the abstract.
    """
    # A path existed before only if they had already told us both things it needs. Goal alone is not
    # enough: that is exactly the turn where the first path gets built.
    already_planning = bool(prior and prior.get("weekly_hours")
                            and (prior.get("goal_skills")
                                 or learning_graph.role_skills(prior.get("role") or "")))
    opening = [module["name"] for module in current["path"]["phases"][0]["modules"]][:3]
    if already_planning or not opening:
        plan = current["path"]
        # Say what it is now, with the numbers, so they can check us. Setting a deadline we cannot
        # meet is not an update to the route, and saying so would be the same lie in our own words.
        if not plan["feasible"]:
            return _cannot_do_that(current)
        return (f"Updated: {current['progress']['skills_total']} steps over {plan['total_weeks']} "
                f"weeks, {plan['total_hours']} hours of study.")
    return (f"Here is your route: {current['progress']['skills_total']} steps over "
            f"{current['path']['total_weeks']} weeks. It starts with {', '.join(opening)}. "
            "Do you already know any of those, or anything else on the way? I will drop what you have.")


@app.post("/explain")
def explain_current(request: PathRequest):
    """Why the step they are on was chosen. Its own endpoint because it costs a model call, so the
    interface asks only when the step actually changes."""
    learning_graph, _ = engine()
    current = build_response(request.profile.model_dump(), request.completed, request.blocked)
    module = current["progress"]["next_action"]
    if not module:
        return {"reason": "You have finished every step on this route."}
    in_path = {skill for phase in current["path"]["phases"] for skill in phase["skills"]}
    return {"reason": explain.explain_module(learning_graph, module, in_path)}


@app.post("/chat")
def chat(request: ChatRequest, learner_id: str | None = LearnerId):
    """Read the learner every turn, then either answer or rebuild.

    We used to ask the explainer whether a message was a change request and only re-read the profile
    if it said yes. It said no to "8 hours a week", so we answered a question they had not asked and
    left their weekly time unset.
    """
    learning_graph, _ = engine()
    prior = request.profile.model_dump() if request.profile else None
    spoken = [*request.history[-12:], Turn(role="user", content=request.message)]
    transcript = "\n".join(f"{'learner' if turn.role == 'user' else 'assistant'}: {turn.content}"
                           for turn in spoken)
    try:
        extracted = learner_profile.extract(learning_graph, transcript, prior)
    except learner_profile.Unavailable:
        # Say so rather than asking them the same thing again as though they had not answered.
        return {"reply": "I could not reach the assistant just then. Say that again in a moment and "
                         "nothing you have told me is lost.", "profile": prior}

    said = [{"role": "user", "content": request.message}]
    kind = extracted.pop("message_kind", None)
    turn = len(request.history)

    def answered(reply):
        # Save the half finished profile too, so coming back resumes the conversation rather than
        # starting it again.
        db.save(learner_id, {**state.new(extracted), "completed": request.completed,
                             "blocked": request.blocked}, said + [{"role": "assistant", "content": reply}])
        return {"reply": reply, "profile": extracted}

    question = learner_profile.next_question(extracted)

    if extracted.pop("out_of_scope", False):
        # Say we cannot rather than asking the same question again. The taxonomy is software, data
        # and AI, and pretending otherwise would be the one thing this whole design refuses to do.
        #
        # This used to also require goal_skills to be empty, which meant it could never fire: the
        # extractor is told to map any goal to the closest skills, so the list is almost never empty.
        # Someone who said they wanted to design buildings got Computer Architecture and a confident
        # explanation of why an architect needs Programming Fundamentals.
        #
        # It is scoped to the last message now. Judged over the whole conversation it fired again on
        # every turn after the first refusal, so saying hello got the same wall of text back.
        return answered(explain.nudge("out_of_scope", ask=question, said=request.message, turn=turn))

    if question:
        # Nothing to plan yet. A greeting deserves a greeting, and a bare question repeated at someone
        # who just said hello reads like a form, not a conversation.
        if kind in ("greeting", "thanks", "about_service", "unclear"):
            return answered(explain.nudge(kind, ask=question if kind != "thanks" else None,
                                          said=request.message, turn=turn))
        return answered(question)

    saved = stored(learner_id)
    weights = saved.get("weights")
    # A new goal makes the old relevance and style signals stale. What we learned about their level
    # and their appetite for long courses is still true.
    if weights and saved.get("goal_skills") and set(saved["goal_skills"]) != set(extracted["goal_skills"]):
        weights = state.refocus(weights)
    current = build_response(extracted, request.completed, request.blocked, weights)
    told_us_something_new = prior is None or any(
        extracted.get(field) != prior.get(field) for field in PROFILE_KEYS)
    if told_us_something_new:
        reply = _reply(learning_graph, prior, current)
    else:
        # Nothing about them changed, so a change request here is one we have no lever for. We answer
        # that ourselves rather than letting the model's prose stand as the answer.
        answer = explain.ask(learning_graph, request.message, current["path"], current["profile"])
        reply = _cannot_do_that(current) if answer["is_change_request"] else answer["answer"]
    remember(learner_id, current, said + [{"role": "assistant", "content": reply}])
    return {"reply": reply, "data": current}
