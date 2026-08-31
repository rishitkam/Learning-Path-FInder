"""Turns a conversation into a learner profile. The only place free text enters the system."""

import json
import os
from functools import lru_cache
from itertools import cycle

from dotenv import load_dotenv
from groq import BadRequestError, Groq, RateLimitError

MODEL = "openai/gpt-oss-20b"
STYLES = ["balanced", "project first", "theory first"]
class Unavailable(RuntimeError):
    """We could not read the learner because the model was unreachable, not because they said nothing.

    This used to be swallowed: a rate limited extraction returned an empty profile, so the assistant
    asked the same question forever and nothing on screen said why. An eval run that had exhausted the
    daily token budget scored it as the model getting every field wrong.
    """


QUESTIONS = {"goal_skills": "What do you want to be able to do at the end? A role works, like data analyst "
                            "or machine learning engineer, or just the thing you want to build.",
             "weekly_hours": "How many hours a week can you realistically give this?"}


@lru_cache(maxsize=1)
def _clients():
    """Every GROQ_API_KEY in the environment, so a spent daily budget is a pause and not a wall.
    The free tier is 200k tokens a day, which one full evaluation run can exhaust on its own."""
    load_dotenv()
    keys = [v for k, v in sorted(os.environ.items()) if k.startswith("GROQ_API_KEY") and v]
    return [Groq(api_key=key) for key in keys] or [Groq()]


def client():
    return _clients()[0]


def call(**kwargs):
    """One completion, trying each key in turn when a daily budget runs out."""
    last = None
    for groq in _clients():
        try:
            return groq.chat.completions.create(**kwargs)
        except RateLimitError as spent:
            last = spent
    raise last


def _tool(g):
    nullable = lambda t, **kw: {"type": [t, "null"], **kw}
    ids, roles = sorted(g.skills), sorted(g.roles)
    return {"type": "function", "function": {
        "name": "set_profile", "description": "Record what the conversation says about the learner.",
        "parameters": {"type": "object", "properties": {
            "goal_text": nullable("string", description="What they want, in their own words, verbatim."),
            "out_of_scope": nullable("boolean", description=
                "True only if they named a goal this taxonomy cannot express at all, like becoming a "
                "chef, a nurse or learning a spoken language. Not for a vague message."),
            "role": nullable("string", enum=roles + [None]),
            "goal_skills": {"type": "array", "items": {"type": "string", "enum": ids}},
            "known_skills": {"type": "array", "items": {"type": "string", "enum": ids}},
            "weekly_hours": nullable("number"), "horizon_weeks": nullable("number"),
            "level": nullable("integer"), "style": nullable("string", enum=STYLES + [None])},
            "required": ["goal_text", "out_of_scope", "role", "goal_skills", "known_skills",
                         "weekly_hours", "horizon_weeks", "level", "style"]}}}


def _num(v, lo, hi, default=None):
    """The model sometimes hands back "10" or a list. Coerce or fall back, never raise."""
    try:
        return min(hi, max(lo, float(v)))
    except (TypeError, ValueError):
        return default


def _clean(g, p, role_is_new=False):
    """Drop what the model got wrong instead of raising. A slightly thinner profile beats a crash."""
    for k in ("goal_skills", "known_skills"):
        v = p.get(k)
        p[k] = [s for s in v if s in g.skills] if isinstance(v, list) else []
    if not isinstance(p.get("role"), str) or p["role"] not in g.roles:
        p.pop("role", None)
    elif role_is_new or not p["goal_skills"]:
        # A role named this turn is the better answer, since the table covers the whole job rather
        # than the one or two skills the model happened to pick out. A role we recorded several turns
        # ago only fills a gap, so it cannot overwrite skills the learner just stated.
        p["goal_skills"] = list(g.role_skills(p["role"]))
    hours = _num(p.get("weekly_hours"), 1, 60)
    p["weekly_hours"] = None if hours is None else (int(hours) if hours == int(hours) else round(hours, 1))
    p["level"] = int(_num(p.get("level"), 1, 5, 2))
    if p.get("style") not in STYLES:
        p["style"] = "balanced"
    if not isinstance(p.get("goal_text"), str) or not p["goal_text"].strip():
        p.pop("goal_text", None)
    return p


def extract(g, transcript, prior=None):
    """Re read the whole conversation every turn, so a later correction simply overwrites an earlier answer."""
    p = dict(prior or {})
    system = (f"Extract the learner profile. Skill ids ONLY from: {', '.join(sorted(g.skills))}. "
              f"Roles ONLY from: {', '.join(sorted(g.roles))}. "
              "Null any field the conversation does not state. Never invent a skill they did not "
              "mention, but do record every one they did: having done, used, studied, worked with or "
              "being comfortable with something all count, wherever in the sentence it appears. "
              "Goals are the exception: if they name any subject, field or role THIS TAXONOMY COVERS, "
              "even as a bare phrase like 'machine learning', treat it as their goal and map it to the "
              "closest skills. If their goal is outside it entirely, a trade, a profession, a language, "
              "anything that is not software, data or AI, set out_of_scope true, leave goal_skills "
              "empty and do not reach for the nearest thing you do have. A word can look like ours and "
              "not be: a building architect is not cs.architecture. "
              "Later messages win. When they correct an earlier goal, extract the correction, not the "
              "thing they are correcting. "
              "Style follows from how they describe learning: building, projects or hands on means "
              "project first, lectures, theory or fundamentals means theory first.")
    user = f"KNOWN SO FAR:\n{json.dumps(p)}\n\nCONVERSATION:\n{transcript}"

    problem = None
    for _ in range(2):  # one retry, then say so rather than pretending they told us nothing
        try:
            r = call(
                model=MODEL, temperature=0, tools=[_tool(g)],
                tool_choice={"type": "function", "function": {"name": "set_profile"}},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
            new = json.loads(r.choices[0].message.tool_calls[0].function.arguments)
            if new.get("out_of_scope"):
                # Clear the goal rather than merging. The merge below drops empty lists so that a
                # quiet turn cannot wipe what we already know, but that also meant a correction
                # could not undo a wrong guess: told "architect" then "I meant BUILDINGS", the
                # extractor kept cs.architecture from the first reading. An out of scope goal is
                # exactly the case where the previous answer has to go.
                cleared = _clean(g, {**p, "role": None, "goal_skills": []})
                cleared["goal_text"] = new.get("goal_text") or p.get("goal_text")
                cleared["out_of_scope"] = True
                return cleared
            # Merge into a copy. A failed attempt must not leave half its answer in the profile.
            return _clean(g, {**p, **{k: v for k, v in new.items() if v not in (None, [])}},
                          role_is_new=bool(new.get("role")))
        except BadRequestError as refused:
            problem = refused
        except Exception as failure:
            problem = failure
    if isinstance(problem, BadRequestError):
        # It reached the model and the model produced nothing valid. On a short message like "hi"
        # that is simply "they told us nothing new", not a service we could not reach.
        return _clean(g, p)
    raise Unavailable(str(problem))


def next_question(p):
    """Goal and hours are the only fields we cannot build a path without."""
    return next((q for k, q in QUESTIONS.items() if not p.get(k)), None)
