"""Turns a conversation into a learner profile. The only place free text enters the system."""

import json
from functools import lru_cache

from dotenv import load_dotenv
from groq import Groq

MODEL = "openai/gpt-oss-20b"
STYLES = ["balanced", "project first", "theory first"]
QUESTIONS = {"goal_skills": "What do you want to be able to do at the end? A role or a project is fine.",
             "weekly_hours": "How many hours a week can you realistically give this?"}


@lru_cache(maxsize=1)
def client():
    load_dotenv()
    return Groq()


def _tool(g):
    nullable = lambda t, **kw: {"type": [t, "null"], **kw}
    ids, roles = sorted(g.skills), sorted(g.roles)
    return {"type": "function", "function": {
        "name": "set_profile", "description": "Record what the conversation says about the learner.",
        "parameters": {"type": "object", "properties": {
            "role": nullable("string", enum=roles + [None]),
            "goal_skills": {"type": "array", "items": {"type": "string", "enum": ids}},
            "known_skills": {"type": "array", "items": {"type": "string", "enum": ids}},
            "weekly_hours": nullable("number"), "horizon_weeks": nullable("number"),
            "level": nullable("integer"), "style": nullable("string", enum=STYLES + [None])},
            "required": ["role", "goal_skills", "known_skills", "weekly_hours",
                         "horizon_weeks", "level", "style"]}}}


def _clean(g, p):
    """Drop what the model got wrong instead of raising. A slightly thinner profile beats a crash."""
    for k in ("goal_skills", "known_skills"):
        p[k] = [s for s in p.get(k) or [] if s in g.skills]
    if p.get("role") not in g.roles:
        p.pop("role", None)
    else:
        p["goal_skills"] = g.role_skills(p["role"])  # table wins: instant and always valid
    if p.get("weekly_hours"):
        p["weekly_hours"] = min(60, max(1, p["weekly_hours"]))
    p["level"] = min(5, max(1, p.get("level") or 2))
    if p.get("style") not in STYLES:
        p["style"] = "balanced"
    return p


def extract(g, transcript, prior=None):
    """Re read the whole conversation every turn, so a later correction simply overwrites an earlier answer."""
    p = dict(prior or {})
    system = (f"Extract the learner profile. Skill ids ONLY from: {', '.join(sorted(g.skills))}. "
              f"Roles ONLY from: {', '.join(sorted(g.roles))}. "
              "Null any field the conversation does not state. Do not guess.")
    user = f"KNOWN SO FAR:\n{json.dumps(p)}\n\nCONVERSATION:\n{transcript}"

    for _ in range(2):  # one retry, then give up and let the caller ask a plain question
        try:
            r = client().chat.completions.create(
                model=MODEL, temperature=0, tools=[_tool(g)],
                tool_choice={"type": "function", "function": {"name": "set_profile"}},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
            new = json.loads(r.choices[0].message.tool_calls[0].function.arguments)
            p.update({k: v for k, v in new.items() if v not in (None, [])})
            return _clean(g, p)
        except Exception:
            continue
    return _clean(g, p)


def next_question(p):
    """Goal and hours are the only fields we cannot build a path without."""
    return next((q for k, q in QUESTIONS.items() if not p.get(k)), None)
