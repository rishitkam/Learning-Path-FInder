"""Proposes career roles from the taxonomy, for a human to accept or throw away.

A role is a claim about what a job requires, which is knowledge about the world rather than about our
catalog. Clustering our own data would only tell us what Coursera bundles together. So the model
proposes and a person decides: this prints candidates and writes nothing until you pass --apply.

    python3 scripts/propose_roles.py            show what it suggests
    python3 scripts/propose_roles.py --apply    add the ones you have not deleted from the file
"""

import json, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graph import load
from path import load_catalog
from profile import client

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/proposed_roles.json"
MODEL = "openai/gpt-oss-120b"

TOOL = {"type": "function", "function": {"name": "propose", "parameters": {"type": "object",
    "properties": {"roles": {"type": "array", "items": {"type": "object",
        "required": ["name", "skills", "why"], "properties": {
            "name": {"type": "string", "description": "lowercase, hyphenated, like data-engineer"},
            "skills": {"type": "array", "items": {"type": "string"},
                       "description": "3 to 5 skill ids someone in this job is hired to be able to do"},
            "why": {"type": "string", "description": "one line on who this is for"}}}}},
    "required": ["roles"]}}}

SYS = """You propose career roles for a learning path tool.

A role is what someone is hired to do, so pick the skills a job advert would ask for, not everything
adjacent. Three to five each, and only ids from the list given.

Suggest roles that the existing ones do not already cover. Do not invent skills."""


def main(apply=False):
    if apply:
        # Read what you left in the file. Proposing again here would overwrite your edits with a
        # fresh set and apply those instead, which defeats the entire point of a review step.
        roles = json.loads((ROOT / "data/roles.json").read_text())
        chosen = json.loads(OUT.read_text())
        roles.update(chosen)
        (ROOT / "data/roles.json").write_text(json.dumps(roles, indent=1))
        print(f"  applied {len(chosen)}: {', '.join(chosen)}. roles.json now has {len(roles)}.")
        return

    g = load()
    catalog = load_catalog(g)
    taught = Counter(s for c in catalog if c["kind"] != "assessment" for s in c["teaches"])
    covered = set().union(*[g.closure(g.role_skills(r)) for r in g.roles])

    # Lead with the skills nothing reaches and the catalog backs well: that is where a missing role
    # is worth most, and it stops the model suggesting another flavour of what we already have.
    gaps = sorted((s for s in g.skills if s not in covered and taught[s] >= 3),
                  key=lambda s: -taught[s])
    if not gaps:
        print("every well backed skill is already reachable from a role")
        return

    listing = "\n".join(f"{s} ({g.name(s)}, {taught[s]} courses)" for s in gaps)
    answer = client().chat.completions.create(
        model=MODEL, temperature=0, max_tokens=1500, reasoning_effort="low", tools=[TOOL],
        tool_choice={"type": "function", "function": {"name": "propose"}},
        messages=[{"role": "system", "content": SYS},
                  {"role": "user", "content": f"EXISTING ROLES: {', '.join(sorted(g.roles))}\n\n"
                                              f"EVERY SKILL ID: {', '.join(sorted(g.skills))}\n\n"
                                              f"REACHED BY NO ROLE, MOST COURSES FIRST:\n{listing}"}])
    proposed = json.loads(answer.choices[0].message.tool_calls[0].function.arguments)["roles"]

    keep = {}
    for role in proposed:
        skills = [s for s in role["skills"] if s in g.skills]
        if role["name"] in g.roles or len(skills) < 2:
            continue
        keep[role["name"]] = skills
        newly = len(g.closure(skills) - covered)
        print(f"\n  {role['name']}")
        print(f"    {role['why']}")
        print(f"    {', '.join(skills)}")
        print(f"    reaches {newly} skills nothing reaches today")

    OUT.write_text(json.dumps(keep, indent=1))
    print(f"\n  written to {OUT.relative_to(ROOT)}. Delete what you disagree with, then rerun with --apply.")




if __name__ == "__main__":
    main("--apply" in sys.argv)
