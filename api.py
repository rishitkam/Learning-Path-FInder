"""HTTP adapter for the deterministic learning-path engine."""

from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import graph
import path
import state
import profile as learner_profile
import explain
from embed import relevance


app = FastAPI(title="Learning Path Finder API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def engine():
    learning_graph = graph.load()
    return learning_graph, path.load_catalog(learning_graph)


class LearnerProfile(BaseModel):
    # Neutral defaults on purpose. A missing field must not quietly invent a goal for someone.
    goal_text: str = ""
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


def build_response(profile: dict, completed=(), blocked=()):
    """Takes a plain profile dict rather than the request, so feedback can hand back the profile it
    changed. Passing the request through meant a level drop or a newly known skill was thrown away."""
    learning_graph, catalog = engine()
    goal_skills = profile.get("goal_skills") or learning_graph.role_skills(profile.get("role") or "")
    if not goal_skills:
        raise HTTPException(status_code=422, detail="Choose a supported role or at least one goal skill.")
    if not profile.get("weekly_hours"):
        raise HTTPException(status_code=422, detail="Tell us how many hours a week you can give this.")
    learner = state.new({**profile, "goal_skills": goal_skills})
    learner["completed"], learner["blocked"] = list(completed), list(blocked)
    roadmap = path.build(
        learning_graph,
        learning_graph.gap(goal_skills, learner["known_skills"]),
        learner,
        catalog,
        known=learner["known_skills"],
        blocked=learner["blocked"],
        relevance=relevance(learner.get("goal_text"), catalog),
    )
    # Carry the whole profile back, not only the fields state tracks, or role goes missing from the
    # response and the next request rebuilds it from the model default.
    return {"profile": {**profile, **{k: learner[k] for k in LearnerProfile.model_fields if k in learner}},
            "path": roadmap, "progress": state.progress(learner, roadmap), "state": learner}


@app.get("/health")
def health():
    learning_graph, catalog = engine()
    return {"ok": True, "skills": len(learning_graph.skills), "resources": len(catalog)}


@app.post("/path")
def generate_path(request: PathRequest):
    return build_response(request.profile.model_dump(), request.completed, request.blocked)


@app.post("/path/feedback")
def apply_feedback(request: FeedbackRequest):
    profile = request.profile.model_dump()
    learner = state.new(profile)
    learner["completed"], learner["blocked"] = list(request.completed), list(request.blocked)
    after = state.apply(learner, request.event, request.skill, request.resource_id)
    # Every field feedback can change has to travel back, not just the two lists.
    return build_response({**profile, "level": after["level"], "known_skills": after["known_skills"]},
                          after["completed"], after["blocked"])


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
        return "Updated your route from what you just told me."
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
def chat(request: ChatRequest):
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
    extracted = learner_profile.extract(learning_graph, transcript, prior)

    question = learner_profile.next_question(extracted)
    if question:
        return {"reply": question, "profile": extracted}

    current = build_response(extracted, request.completed, request.blocked)
    told_us_something_new = prior is None or any(
        extracted.get(field) != prior.get(field) for field in PROFILE_KEYS)
    if told_us_something_new:
        return {"reply": _reply(learning_graph, prior, current), "data": current}

    answer = explain.ask(learning_graph, request.message, current["path"], current["profile"])
    return {"reply": answer["answer"], "data": current}
