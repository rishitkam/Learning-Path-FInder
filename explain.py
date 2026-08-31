"""Explains a path the code already built. The model phrases reasons, it never sources them."""

import json

from path import W
from profile import call

MODEL = "openai/gpt-oss-120b"
TERMS = {"relevance": "is the closest match to what they said they want",
         "level": "sits at about their level",
         "style": "matches how they like to learn",
         "effort": "is short enough to finish in a couple of weeks at their pace"}
_CACHE = {}


def why_order(g, skill, in_path):
    """Which prerequisites inside this path put the skill here. Straight off the graph."""
    return [g.name(p) for p in g.g.pred[skill] if p in in_path]


def why_resource(mod):
    """The two signals that contributed most to this resource winning."""
    why = mod["why"]
    if not why:
        return []
    if why.get("only_option"):
        return ["is the only course we have for this skill"]   # nothing won, so claim nothing
    terms = {k: v for k, v in TERMS.items() if not (k == "relevance" and why.get("flat_relevance"))}
    ranked = sorted(terms, key=lambda k: -W[k] * why.get(k, 0))
    return [terms[k] for k in ranked[:2]]


def _facts(g, mod, in_path):
    r = mod["resource"] or {}
    after = why_order(g, mod["skill"], in_path)
    # Omit empty keys rather than send them. A null makes the model narrate the absence.
    return {k: v for k, v in {"skill": mod["name"], "resource": r.get("title"), "total_hours": r.get("hours"),
                              "comes_after": after, "chosen_because": why_resource(mod)}.items() if v}


def _say(system, payload, cap=300):
    try:
        r = call(
            model=MODEL, temperature=0, max_tokens=cap, reasoning_effort="low",
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": json.dumps(payload)}])
        return r.choices[0].message.content.strip()
    except Exception:
        return None


def _cached(key, make):
    """Facts change only when the plan changes, so this is keyed on the facts themselves.
    Only a real answer is stored. Caching a fallback would make one bad minute permanent."""
    if not _CACHE.get(key):
        got = make()
        if got:
            _CACHE[key] = got
        return got
    return _CACHE[key]


SYS_MODULE = ("Say what this step of the plan is and why it was chosen. You did not create the plan. "
              "Use only the facts given. Address the learner as you, never as I or we. "
              "Two short sentences, no lists. Never invent a number, a schedule, or study advice. "
              "Do not tell them how to pace or approach the material.")


def explain_module(g, mod, in_path):
    f = _facts(g, mod, in_path)
    after, because = f.get("comes_after"), f.get("chosen_because")
    if not f.get("resource"):
        return f"We have no course for {f['skill']} in the catalog yet."
    plain = (f"{f['resource']} covers {f['skill']}"
             + (f", which follows {' and '.join(after)}" if after else "")
             + (f". Picked because it {' and '.join(because)}." if because else "."))
    said = _cached(json.dumps(f), lambda: _say(SYS_MODULE, f))
    return said or plain          # the fallback is never cached, so a bad minute is not permanent


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

SYS_ASK = ("Answer using ONLY the plan given. You did not build it, you cannot change it, and you must "
           "never say or imply that you have. Never write 'we will', 'I have updated', 'the plan has "
           "been trimmed', or anything else that promises a change. Describe what the plan is, not what "
           "it will become. If they are asking for it to be different, set is_change_request and say "
           "plainly that you cannot change it yourself. Three sentences at most.")


def ask(g, question, path, profile):
    """Returns the answer plus a flag. A change request is handed back to the profile extractor."""
    try:
        r = call(
            model=MODEL, temperature=0, tools=[ANSWER_TOOL], reasoning_effort="low",
            tool_choice={"type": "function", "function": {"name": "answer"}},
            messages=[{"role": "system", "content": SYS_ASK},
                      {"role": "user", "content": f"PLAN:\n{json.dumps(summary(g, path, profile))}"
                                                  f"\n\nQUESTION:\n{question}"}])
        return json.loads(r.choices[0].message.tool_calls[0].function.arguments)
    except Exception:
        return {"answer": "I could not reach the model just now. The plan itself is unchanged.",
                "is_change_request": False}


# What we can actually plan, said once so the refusal and the scope answer cannot drift apart.
COVERS = "software, data and AI: programming, machine learning, cloud, data engineering, security"

# Used when the model is unreachable or its line fails the checks below. Indexed by how many turns
# have been spoken, so a learner who sends three greetings does not get the same sentence three times.
FALLBACKS = {
    "out_of_scope": [
        f"That one is outside my shelf. I only have courses in {COVERS}. Name something in there and "
        "I will build you a route.",
        f"I cannot help with that one, I am afraid. My catalog stops at {COVERS}. What would you like "
        "to learn inside that?",
        f"Not something I have courses for. I stick to {COVERS}. Tell me a goal in that space and I "
        "will map it out.",
        f"Outside what I can teach. Everything I have is {COVERS}. What are you aiming at in there?",
    ],
    "greeting": [
        "Hello. What would you like to be able to do at the end?",
        "Hi there. Tell me what you want to learn and I will work out the route.",
        "Hey. What are you aiming at? A role works, or just the thing you want to build.",
    ],
    "thanks": [
        "Any time. Say the word if you want the plan changed.",
        "Glad it helps. I am here if you want to adjust anything.",
        "You are welcome. Come back whenever you want to shift the plan.",
    ],
    "about_service": [
        f"I build learning routes. You tell me a goal and the hours you have, I work out the order "
        f"from a prerequisite graph and pick real courses for each step. I cover {COVERS}.",
        f"I turn a goal into an ordered plan through real courses, working out what has to come "
        f"first. I only cover {COVERS}.",
    ],
    "unclear": [
        "I did not follow that. What do you want to be able to do at the end?",
        "Not sure I caught that. Tell me the thing you want to learn.",
    ],
}

SYS_NUDGE = (
    "You are ALMA, a learning path planner. Write ONE short reply, two sentences at most, warm and "
    "plain, no emoji, no exclamation marks, no lists.\n"
    f"You can only plan: {COVERS}.\n"
    "NEVER name a course, a provider, a duration or a number of weeks. You have no plan in front of "
    "you and inventing one is the only thing you must not do.\n"
    "NEVER promise to change or shorten anything.\n"
    "If ASK is given, your reply must end by asking exactly that, in your own words."
)


def _acceptable(text, must_ask):
    """The refusal and the nudge are the two places we generate prose with no plan to check against,
    so the checks are about what must be absent: any figure could only have been invented."""
    if not text or len(text) > 320:
        return False
    low = text.lower()
    if any(ch.isdigit() for ch in text):
        return False
    if any(w in low for w in ("course", "week", "hour", "module", "coursera", "udemy", "i will trim",
                              "i will shorten", "i have changed", "i've changed")):
        return False
    return not must_ask or "?" in text


def nudge(kind, ask=None, said=None, turn=0):
    """A varied line for the turns where there is no plan to talk about yet: a goal we cannot teach,
    a greeting, a thank you, a question about what this is, or something we could not read.

    One repeated sentence reads like a wall. This asks the model for the same content in its own
    words each time and checks what comes back, falling back to a rotating set when the model is
    unreachable or writes something it should not.
    """
    pool = FALLBACKS.get(kind) or FALLBACKS["unclear"]
    spare = pool[turn % len(pool)]
    try:
        told = f"THE LEARNER SAID:\n{said}\n\n" if said else ""
        want = f"ASK:\n{ask}\n\n" if ask else ""
        why = {"out_of_scope": "Their goal is outside what you can plan. Say so plainly, without "
                               "apologising twice, and invite them to name something you do cover.",
               "greeting": "They greeted you. Greet them back in one clause and get to the point.",
               "thanks": "They thanked you or said goodbye. Acknowledge it briefly. Do not ask "
                         "anything unless ASK is given.",
               "about_service": "They asked what you do. Say it in one or two sentences.",
               "unclear": "You could not read their message. Say so lightly and ask again."}
        r = call(model=MODEL, temperature=0.7, reasoning_effort="low", max_tokens=120,
                 messages=[{"role": "system", "content": SYS_NUDGE},
                           {"role": "user", "content": f"{told}{want}SITUATION:\n{why.get(kind, why['unclear'])}"}])
        text = (r.choices[0].message.content or "").strip()
        return text if _acceptable(text, must_ask=bool(ask)) else spare
    except Exception:
        return spare
