# Progress

Where we are, what each commit added, and what is left.

## The pipeline

```
conversation  ->  profile  ->  skill gap  ->  ordering  ->  schedule  ->  path  ->  explanation
                profile.py      graph.py      graph.py       path.py            explain.py
```

Everything after the profile is plain Python. The model only appears at the two ends, reading the
learner in and later writing the explanation out. It never picks or orders content.

## What we have committed

**Initial commit.** Repo and README.

**Commit 2, the skill graph.** `graph.py` plus `data/skills.json` and `data/roles.json`. This is the
prerequisite layer and the part everything else stands on. It works out what a learner is missing for
their goal, closes their stated skills downward so saying one advanced thing marks the whole chain
below it, and returns a teachable order that is the same on every run. It also refuses to start if a
prerequisite points at a skill that does not exist or if two skills depend on each other. 29 seed
skills, 7 roles.

**Commit 3, the path builder.** `path.py` plus `data/catalog.json`. This is the scheduling layer. It
picks one resource per skill out of the catalog, scores it on four visible signals, then cuts the
ordered skills into phases sized to about a month of that learner's time. Same skill order gives 3
phases at 15 hours a week and 8 at 4 hours a week. Each phase gets weeks, a milestone project and a
check, all pulled from the catalog rather than invented. 41 seed items covering all 29 skills.

**Commit 4, the profile extractor.** `profile.py`. This is the language layer and the only place
free text enters the system. It turns a conversation into the profile dict the path builder already
eats. Skill ids and role names are enums in the tool schema, so the model can only pick from our list.
We re read the whole conversation every turn, which means a learner correcting themselves halfway
through just works with no extra code.

We tested three Groq models on the same three conversations before choosing gpt-oss-20b. Notes are in
decisions.md.

**Commit 5, progress notes.** This file.

**Commit 6, the explainer.** `explain.py`. Says why each resource was picked and where it sits, and
answers questions about the plan. The reasons are not written by the model. Where a skill sits comes
from the graph edges and why a resource won comes from the score breakdown we already store, so an
explanation cannot contradict the plan and still shows the facts as plain text if Groq is unreachable.

Questions come back with a flag saying whether the learner was asking about the plan or trying to change
it. A change request goes back to the profile extractor and the path rebuilds, so feedback only ever
enters through one door.

This one runs on gpt-oss-120b, the opposite of the extractor. Strict schemas suit the small model,
prose and judgement suit the big one. Both decided by testing.

**Commit 7, feedback handling.** `state.py`. Five buttons: already knew this, finished it, too hard,
too easy, not interested. Each one changes the learner state and the path rebuilds from it. Nothing
edits a path in place.

Rejecting a course blocks that course and we pick the next best thing for the same skill, so feedback
can never break the prerequisite chain. Too hard also drops their level, which changes everything ahead
of them rather than just the one course.

Progress for the dashboard is read off the state and the path every time, never stored, so it cannot
drift when the plan changes underneath it.

**Commit 8, the catalog pipeline.** `scripts/fetch.py`, `normalise.py`, `label.py`. Pulls 6645 real
Coursera courses with no login, parses their real durations and difficulty, filters to our domain and
keeps the 400 most enrolled, then labels each one with what it teaches and what it assumes.

The taxonomy grows while labelling. Each batch sees every skill named so far, so the model reuses ids
rather than coining synonyms, and only invents a skill when nothing fits. 29 seed skills became 63.
350 of 400 courses labelled, the other 50 dropped as off topic.

This one took several attempts and the failures are worth knowing. Our first run reported healthy
numbers while 13 percent of courses both taught and assumed the same skill, which would have been a
cycle. We filtered off topic courses with embedding anchors twice before accepting the model should
make that call instead. And we went through three models: 120b runs out of free tier budget, 20b never
proposes a new skill so it crams everything into the seed ids and mislabels most of it, qwen does the
job properly. All of it is in decisions.md.

## Roughly where we stand

Engine done, nothing to look at yet.

| Piece | State |
| --- | --- |
| Conversation to profile | done |
| Goal to skills | done |
| Skill gap and ordering | done |
| Scheduling into phases | done |
| Explanations and learner questions | done |
| Interface and dashboard | not started |
| Progress tracking and feedback | done |
| Real catalog with embeddings | pipeline done, graph build next |

Six and a half of eight. The engine works end to end in the terminal and we now have 350 real courses
labelled against a 63 skill taxonomy.

## Next

Build the real prerequisite graph from those labels: dedupe the taxonomy, draw the edges, break any
cycles, and switch relevance scoring on. The dedupe produces a short review list for us to check before
anything overwrites the current graph.

Then the interface, which waits until the whole team is on it since that is the part we should build
together. HANDOFF.md has the full detail.

## Known gaps we are carrying on purpose

Relevance scoring is flat until embeddings land, so ranking currently runs on three signals instead of
four. Ranking weights are hard coded because we have no feedback data yet. The catalog is hand written,
though the file shape is final so the real one drops straight in.
