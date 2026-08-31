# ALMA — Learning Path Finder

Tell it what you want to be able to do and how many hours a week you actually have. It returns an
ordered route through real courses, with the prerequisites in the right order and a reason for every
step.

The interesting part is not that it uses an LLM. It is where the LLM is **not**.

---

## The one design decision everything else follows from

An LLM asked to "recommend a learning path" will produce a confident, plausible, unverifiable list.
It will invent courses that do not exist. It will put linear algebra after deep learning. It will
promise to shorten a plan and change nothing. None of that is a prompting problem, and no amount of
prompt engineering makes the output checkable.

So the model never picks anything.

```
    learner types                                                   prose out
         │                                                              ▲
         ▼                                                              │
   ┌───────────┐     ┌──────────────────────────────────────┐    ┌────────────┐
   │  EXTRACT  │ ──▶ │   pure functions, no model involved  │ ──▶│  EXPLAIN   │
   │   (LLM)   │     │                                      │    │   (LLM)    │
   └───────────┘     │  prerequisite graph  →  topological  │    └────────────┘
                     │  order  →  weighted set cover over   │
                     │  1214 real courses  →  schedule      │
                     └──────────────────────────────────────┘
```

The LLM reads a person in at one edge and writes prose out at the other. Everything between is a
pure function of state and catalog. It is deterministic, it is testable, and **it cannot recommend a
course that does not exist**, because it only ever selects from rows we scraped.

Two consequences we can state as measurements rather than claims:

- The same learner and the same catalog produce **byte-identical plans**, verified across 18 roles
  and shuffled catalog orders.
- **Zero prerequisite violations** across all 54 role-and-persona combinations, because ordering
  comes off a DAG rather than out of a model.

---

## How a path is actually built

**1. The gap.** 91 skills in a prerequisite DAG with 86 edges. Your goal expands to the skills a role
needs; what you already know is subtracted, transitively.

**2. The order.** Topological sort of the gap, grouped into phases by depth. A prerequisite can never
land after the thing that needs it — this is a property of the graph, not something we hope the model
respects.

**3. The courses.** This is a **weighted set cover**, not one-course-per-skill. Picking the best
course per skill left about 40% of study time redundant, because one course often teaches several
things you need. Greedy set cover, value per step = coverage per hour × how well it fits you.

**4. The fit.** Four signals — goal relevance (static embeddings, no API call), your level, how you
like to learn, and course length. Feedback moves the weights, so the ranking becomes yours.

**5. The schedule.** Your weekly hours against the total. If the deadline does not fit we say so and
give the arithmetic; we do not quietly drop steps to make a number look good.

---

## What we measure, and what it says

Run `python3 evals.py` — about a second, no model calls.

| | |
|---|---|
| Prerequisite violations | **0** across 54 plans |
| Skills covered by a real course | **100%** |
| Distance from optimal | **1.25×** median vs a linear-programming lower bound |
| Determinism | **18/18** roles identical across runs and catalog order |
| Groundedness of explanations | **100%** (8/8) |
| Personalisation | **69%** of picks change when the weights change |
| | **76%** of picks change after three "too hard" clicks |
| Extraction | role 100%, known-skills F1 1.00, on 135 held-out cases |
| Tests | **69**, no network required |

The approximation ratio is measured against a real lower bound (scipy `linprog` on the LP relaxation
of minimum-cost set cover), not against another greedy run. Comparing greedy to greedy proves nothing.

**Numbers we report that do not flatter us:** 39 of the 91 skills cannot be reached from any role we
ship, 9% of the catalog teaches nothing we know about and can never be recommended, and our own test
goals only ever surface 8% of it. Those are data coverage problems, and they are in the report rather
than hidden, because a catalog metric that only counts what we happened to exercise would read as
100% while telling us nothing.

---

## Things it refuses to do

This is the part we are most pleased with, because each one is a bug we shipped first and then caught:

- **It will not plan what it cannot teach.** Ask to become a building architect and it says so,
  rather than routing you through Computer Architecture because the word matched. It used to do
  exactly that, complete with a confident explanation.
- **It will not invent a course.** Nine prompt-injection attempts, including one naming a fake course
  outright, produced no invented course, no leaked prompt, no leaked key.
- **It will not promise what it cannot do.** Ask it to cut a 19-week plan to 2 and it answers with
  arithmetic — what your deadline would actually cost — rather than agreeing and changing nothing.
- **It will not pretend to be connected.** The status lights read real reachability. Kill the API and
  they go red.

---

## Running it

```bash
pip install -r requirements.txt
echo "GROQ_API_KEY=..." > .env
python3 -m uvicorn api:app --port 8000
```

```bash
cd learning-path-finder && npm install && npm run dev     # interface on :3000
```

Tests and the eval suite need two extra packages the API itself never imports:

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q      # 69 tests
python3 evals.py          # the full measurement report
```

---

## Layout

| | |
|---|---|
| `graph.py` | the prerequisite DAG, gap and topological order |
| `path.py` | weighted set cover, ranking, scheduling |
| `embed.py` | static embeddings for goal relevance |
| `profile.py` | the LLM edge that reads a learner in |
| `explain.py` | the LLM edge that writes prose out |
| `state.py` | feedback events and per-learner weights |
| `api.py` | FastAPI endpoints |
| `evals.py` | everything in the table above |
| `scripts/` | catalog scrape, labelling, graph build |
| `decisions.md` | **114 entries.** Every decision, including the wrong ones and what they cost |
| `EVALS.md` | what each metric means and why it is the right one |
| `HANDOFF.md` | pick the project up cold |

`decisions.md` is the honest record. It documents the bugs above as bugs, the numbers that got worse
when we measured them properly, and the two experiments we ran, measured, and deleted. If you read one
supporting file, read that one.
