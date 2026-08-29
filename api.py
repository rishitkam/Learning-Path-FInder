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
    goal_text: str = "Become a machine learning engineer"
    role: str | None = "machine-learning-engineer"
    goal_skills: list[str] = Field(default_factory=list)
    known_skills: list[str] = Field(default_factory=list)
    weekly_hours: float = Field(default=5, ge=1, le=60)
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


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)
    profile: LearnerProfile | None = None
    completed: list[str] = Field(default_factory=list)
    blocked: list[str] = Field(default_factory=list)


def build_response(request: PathRequest):
    learning_graph, catalog = engine()
    profile = request.profile.model_dump()
    goal_skills = profile["goal_skills"] or learning_graph.role_skills(profile.get("role") or "")
    if not goal_skills:
        raise HTTPException(status_code=422, detail="Choose a supported role or at least one goal skill.")
    learner = state.new({**profile, "goal_skills": goal_skills})
    learner["completed"] = request.completed
    learner["blocked"] = request.blocked
    roadmap = path.build(
        learning_graph,
        learning_graph.gap(goal_skills, learner["known_skills"]),
        profile,
        catalog,
        known=learner["known_skills"],
        blocked=learner["blocked"],
    )
    return {"profile": profile, "path": roadmap, "progress": state.progress(learner, roadmap), "state": learner}


@app.get("/health")
def health():
    learning_graph, catalog = engine()
    return {"ok": True, "skills": len(learning_graph.skills), "resources": len(catalog)}


@app.post("/path")
def generate_path(request: PathRequest):
    return build_response(request)


@app.post("/path/feedback")
def apply_feedback(request: FeedbackRequest):
    learner = state.new(request.profile.model_dump())
    learner["completed"] = request.completed
    learner["blocked"] = request.blocked
    next_state = state.apply(learner, request.event, request.skill, request.resource_id)
    return build_response(PathRequest(profile=request.profile, completed=next_state["completed"], blocked=next_state["blocked"]))


@app.post("/chat")
def chat(request: ChatRequest):
    """Use the LLM to understand the learner and explain a deterministic path."""
    learning_graph, _ = engine()
    prior = request.profile.model_dump() if request.profile else None
    if prior and (prior.get("goal_skills") or learning_graph.role_skills(prior.get("role") or "")):
        current = build_response(PathRequest(profile=request.profile, completed=request.completed, blocked=request.blocked))
        answer = explain.ask(learning_graph, request.message, current["path"], current["profile"])
        if not answer["is_change_request"]:
            return {"reply": answer["answer"], "data": current}
        extracted = learner_profile.extract(learning_graph, request.message, prior)
    else:
        extracted = learner_profile.extract(learning_graph, request.message, prior)
    question = learner_profile.next_question(extracted)
    if question:
        return {"reply": question, "profile": extracted}
    current = build_response(PathRequest(profile=LearnerProfile(**extracted), completed=request.completed, blocked=request.blocked))
    return {"reply": "Your live learning path is ready. I built it from your goal, current skills, and weekly time.", "data": current}
