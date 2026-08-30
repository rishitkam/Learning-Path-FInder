"""Learner state and what feedback does to it. The path is always rebuilt, never edited."""

FIELDS = ("goal_text", "goal_skills", "known_skills", "weekly_hours", "horizon_weeks", "level", "style")


def new(profile=None):
    """Copies every list, so a state never shares mutable data with the profile it came from."""
    s = {k: (profile or {}).get(k) for k in FIELDS}
    return {**s, "goal_skills": list(s["goal_skills"] or []), "known_skills": list(s["known_skills"] or []),
            "level": s["level"] or 2, "completed": [], "blocked": []}


def _add(state, key, value):
    """Returns whether anything actually changed, so a repeated click cannot keep moving the level."""
    if value and value not in state[key]:
        state[key].append(value)
        return True
    return False


def apply(state, event, skill=None, resource_id=None):
    """One click, one state change. Nothing here can remove a skill the path depends on."""
    s = {**state, "goal_skills": list(state["goal_skills"] or []),
         "known_skills": list(state["known_skills"]), "completed": list(state["completed"]),
         "blocked": list(state["blocked"])}

    if event == "already_know":          # never needed it, so drop it from the plan
        _add(s, "known_skills", skill)
    elif event == "completed":           # did the work, so keep it visible and ticked
        _add(s, "completed", skill)
    elif event in ("too_hard", "too_easy", "not_interested"):
        changed = _add(s, "blocked", resource_id)  # the skill stays, we pick the next best for it
        if changed and event != "not_interested":
            # Blocking one course alone would hand them another at the same level, so move the level
            # too. Only on a real block, or clicking the same button twice would slide it twice.
            s["level"] = min(5, max(1, (s["level"] or 2) + (-1 if event == "too_hard" else 1)))
    else:
        raise ValueError(f"unknown event: {event}")
    return s


def progress(state, path):
    """Read off state and path every time. A stored counter would drift the moment the plan changes.

    Hours are counted per distinct resource, the same way the schedule counts them, so one course
    serving two skills is not two lots of work. Milestones count with the phase they belong to."""
    done = set(state["completed"])
    counted, total, finished, left = set(), 0, 0, []
    for ph in path["phases"]:
        whole_phase = all(m["skill"] in done for m in ph["modules"])
        for m in ph["modules"]:
            r = m["resource"]
            hours = r["hours"] if r and r["id"] not in counted else 0
            if r:
                counted.add(r["id"])
            total += hours
            if m["skill"] in done:
                finished += hours
            else:
                left.append(m)
        for extra in (ph.get("milestone"), ph.get("assessment")):
            if extra:
                total += extra["hours"]
                finished += extra["hours"] if whole_phase else 0
    mods = [m for ph in path["phases"] for m in ph["modules"]]
    phase = next((ph for ph in path["phases"] if any(m["skill"] not in done for m in ph["modules"])), None)
    total_weeks = path.get("total_weeks", 0)
    done_to = phase["weeks"][0] if phase else total_weeks

    return {"skills_done": len(mods) - len(left), "skills_total": len(mods),
            "percent": round(100 * (len(mods) - len(left)) / len(mods)) if mods else 0,
            "hours_done": finished, "hours_total": total,
            # Read off the schedule, not recomputed from hours. Dividing again gave a number that
            # disagreed with the roadmap on screen, because the schedule rounds each phase up.
            "weeks_left": total_weeks - done_to,
            "current_phase": phase["title"] if phase else None,
            "next_action": left[0] if left else None}
