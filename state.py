"""Learner state and what feedback does to it. The path is always rebuilt, never edited."""

from math import ceil

FIELDS = ("goal_skills", "known_skills", "weekly_hours", "horizon_weeks", "level", "style")


def new(profile=None):
    s = {k: (profile or {}).get(k) for k in FIELDS}
    return {**s, "known_skills": s["known_skills"] or [], "completed": [], "blocked": []}


def _add(state, key, value):
    if value and value not in state[key]:
        state[key].append(value)


def apply(state, event, skill=None, resource_id=None):
    """One click, one state change. Nothing here can remove a skill the path depends on."""
    s = {**state, "known_skills": list(state["known_skills"]),
         "completed": list(state["completed"]), "blocked": list(state["blocked"])}

    if event == "already_know":          # never needed it, so drop it from the plan
        _add(s, "known_skills", skill)
    elif event == "completed":           # did the work, so keep it visible and ticked
        _add(s, "completed", skill)
    elif event in ("too_hard", "too_easy", "not_interested"):
        _add(s, "blocked", resource_id)  # the skill stays, we pick the next best thing for it
        if event != "not_interested":
            # Blocking one course alone would hand them another at the same level, so move the level too.
            s["level"] = min(5, max(1, (s["level"] or 2) + (-1 if event == "too_hard" else 1)))
    else:
        raise ValueError(f"unknown event: {event}")
    return s


def progress(state, path):
    """Read off state and path every time. A stored counter would drift the moment the plan changes."""
    done = set(state["completed"])
    mods = [m for ph in path["phases"] for m in ph["modules"]]
    hours = lambda ms: sum(m["resource"]["hours"] for m in ms if m["resource"])
    left = [m for m in mods if m["skill"] not in done]
    phase = next((ph for ph in path["phases"] if any(m["skill"] not in done for m in ph["modules"])), None)

    return {"skills_done": len(mods) - len(left), "skills_total": len(mods),
            "percent": round(100 * (len(mods) - len(left)) / len(mods)) if mods else 0,
            "hours_done": hours(mods) - hours(left), "hours_total": hours(mods),
            "weeks_left": ceil(hours(left) / state["weekly_hours"]) if state["weekly_hours"] else None,
            "current_phase": phase["title"] if phase else None,
            "next_action": left[0] if left else None}
