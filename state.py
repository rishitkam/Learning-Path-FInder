"""Learner state and what feedback does to it. The path is always rebuilt, never edited."""

from path import W

FIELDS = ("goal_text", "goal_skills", "known_skills", "weekly_hours", "horizon_weeks", "level", "style")
STEP, FLOOR, CEILING = 0.04, 0.05, 0.60
# What a rejection tells us about how this person weighs a course. Rejecting says more than finishing,
# so a completed course reinforces at half the step.
BLAMES = {"too_hard": "level", "too_easy": "level", "not_interested": "relevance"}


def _reweigh(weights, term, step):
    """Nudge one term, hold every term inside its bounds, then renormalise.

    Renormalising matters: raising one weight has to lower the others or nothing changes in the
    ranking, only the scale. It also keeps scores comparable between learners, so the explainer's
    "closest match" means the same thing for everyone.
    """
    nudged = {**weights, term: weights.get(term, W[term]) + step}
    bounded = {k: min(CEILING, max(FLOOR, v)) for k, v in nudged.items()}
    total = sum(bounded.values())
    return {k: round(v / total, 4) for k, v in bounded.items()}


def refocus(weights):
    """Keep what is true about the person, drop what was true about the old goal. Renormalised like
    every other change, or the weights stop summing to one and scores stop being comparable."""
    reset = {**weights, "relevance": W["relevance"], "style": W["style"]}
    total = sum(reset.values())
    return {k: round(v / total, 4) for k, v in reset.items()}


def new(profile=None):
    """Copies every list, so a state never shares mutable data with the profile it came from."""
    s = {k: (profile or {}).get(k) for k in FIELDS}
    return {**s, "goal_skills": list(s["goal_skills"] or []), "known_skills": list(s["known_skills"] or []),
            "level": s["level"] or 2, "completed": [], "blocked": [],
            "weights": dict((profile or {}).get("weights") or W)}


def _add(state, key, value):
    """Returns whether anything actually changed, so a repeated click cannot keep moving the level."""
    if value and value not in state[key]:
        state[key].append(value)
        return True
    return False


def apply(state, event, skill=None, resource_id=None, module=None):
    """One click, one state change. Nothing here can remove a skill the path depends on."""
    s = {**state, "goal_skills": list(state["goal_skills"] or []),
         "known_skills": list(state["known_skills"]), "completed": list(state["completed"]),
         "blocked": list(state["blocked"]), "weights": dict(state.get("weights") or W)}
    resource = (module or {}).get("resource") or {}
    why = (module or {}).get("why") or {}

    if event == "already_know":          # never needed it, so drop it from the plan
        _add(s, "known_skills", skill)    # says nothing about ranking, so weights do not move
    elif event == "completed":           # did the work, so keep it visible and ticked
        if _add(s, "completed", skill) and why:
            best = max(why, key=lambda k: s["weights"].get(k, 0) * why.get(k, 0))
            s["weights"] = _reweigh(s["weights"], best, STEP / 2)
    elif event in ("too_hard", "too_easy", "not_interested"):
        changed = _add(s, "blocked", resource_id)  # the skill stays, we pick the next best for it
        if changed and event != "not_interested":
            # Blocking one course alone would hand them another at the same level, so move the level
            # too. Only on a real block, or clicking the same button twice would slide it twice.
            s["level"] = min(5, max(1, (s["level"] or 2) + (-1 if event == "too_hard" else 1)))
        if changed:
            # "Not for me" does not say why, so a course far longer than a month of their time was
            # most likely refused for its length. Too hard and too easy already told us the reason,
            # and we should believe them rather than second guess it.
            month = (s.get("weekly_hours") or 1) * 4
            vague_and_long = event == "not_interested" and resource.get("hours", 0) > month
            s["weights"] = _reweigh(s["weights"], "effort" if vague_and_long else BLAMES[event], STEP)
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
