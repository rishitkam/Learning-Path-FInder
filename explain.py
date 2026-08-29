"""Explains a path the code already built. The model phrases reasons, it never sources them."""

import json

from path import W
from profile import client

MODEL = "openai/gpt-oss-120b"
# Relevance is flat until embeddings land, so we do not claim a course matches their goal yet.
TERMS = {"level": "sits at about their level",
         "style": "matches how they like to learn",
         "effort": "is short enough to finish in a couple of weeks at their pace"}
_CACHE = {}


def why_order(g, skill, in_path):
    """Which prerequisites inside this path put the skill here. Straight off the graph."""
    return [g.name(p) for p in g.g.pred[skill] if p in in_path]


def why_resource(mod):
    """The two signals that contributed most to this resource winning."""
    if not mod["why"]:
        return []
    ranked = sorted(TERMS, key=lambda k: -W[k] * mod["why"][k])
    return [TERMS[k] for k in ranked[:2]]


def _facts(g, mod, in_path):
    r = mod["resource"] or {}
    after = why_order(g, mod["skill"], in_path)
    # Omit empty keys rather than send them. A null makes the model narrate the absence.
    return {k: v for k, v in {"skill": mod["name"], "resource": r.get("title"), "total_hours": r.get("hours"),
                              "comes_after": after, "chosen_because": why_resource(mod)}.items() if v}


def _say(system, payload, cap=300):
    try:
        r = client().chat.completions.create(
            model=MODEL, temperature=0, max_tokens=cap, reasoning_effort="low",
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": json.dumps(payload)}])
        return r.choices[0].message.content.strip()
    except Exception:
        return None


def _cached(key, make):
    """Facts change only when the plan changes, so this is keyed on the facts themselves."""
    if key not in _CACHE:
        _CACHE[key] = make()
    return _CACHE[key]


SYS_MODULE = ("Say what this step of the plan is and why it was chosen. You did not create the plan. "
              "Use only the facts given. Address the learner as you, never as I or we. "
              "Two short sentences, no lists. Never invent a number, a schedule, or study advice. "
              "Do not tell them how to pace or approach the material.")


def explain_module(g, mod, in_path):
    f = _facts(g, mod, in_path)
    after, because = f.get("comes_after"), f.get("chosen_because")
    plain = (f"{f['resource']} covers {f['skill']}"
             + (f", which follows {' and '.join(after)}" if after else "")
             + (f". Picked because it {' and '.join(because)}." if because else "."))
    return _cached(json.dumps(f), lambda: _say(SYS_MODULE, f) or plain)


def summary(g, path, profile):
    """Compact view of the plan. Small enough to send, complete enough to answer from."""
    in_path = {s for ph in path["phases"] for s in ph["skills"]}
    return {"profile": {k: profile.get(k) for k in ("level", "style", "weekly_hours", "horizon_weeks")},
            "total_weeks": path["total_weeks"], "feasible": path["feasible"],
            "phases": [{"title": ph["title"], "weeks": ph["weeks"],
                        "milestone": (ph["milestone"] or {}).get("title"),
                        "modules": [_facts(g, m, in_path) for m in ph["modules"]]}
                       for ph in path["phases"]]}


ANSWER_TOOL = {"type": "function", "function": {"name": "answer", "parameters": {"type": "object",
    "properties": {"answer": {"type": "string"},
                   "is_change_request": {"type": "boolean",
                       "description": "True if the learner is asking to alter the plan or telling us "
                                      "something new about themselves, rather than asking about it."}},
    "required": ["answer", "is_change_request"]}}}

SYS_ASK = ("Answer using ONLY the plan given. You did not build it and cannot change it. "
           "If the learner wants it changed or tells you something new about themselves, "
           "set is_change_request and say it will be updated. Three sentences at most.")


def ask(g, question, path, profile):
    """Returns the answer plus a flag. A change request is handed back to the profile extractor."""
    try:
        r = client().chat.completions.create(
            model=MODEL, temperature=0, tools=[ANSWER_TOOL], reasoning_effort="low",
            tool_choice={"type": "function", "function": {"name": "answer"}},
            messages=[{"role": "system", "content": SYS_ASK},
                      {"role": "user", "content": f"PLAN:\n{json.dumps(summary(g, path, profile))}"
                                                  f"\n\nQUESTION:\n{question}"}])
        return json.loads(r.choices[0].message.tool_calls[0].function.arguments)
    except Exception:
        return {"answer": "I could not reach the model just now. The plan itself is unchanged.",
                "is_change_request": False}
