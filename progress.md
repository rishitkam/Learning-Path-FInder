# Progress

Where we are, what each commit added, and what is left.

## The pipeline

```
conversation  ->  profile  ->  skill gap  ->  ordering  ->  schedule  ->  path
                profile.py      graph.py      graph.py       path.py
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

**Uncommitted, the profile extractor.** `profile.py`. This is the language layer and the only place
free text enters the system. It turns a conversation into the profile dict the path builder already
eats. Skill ids and role names are enums in the tool schema, so the model can only pick from our list.
We re read the whole conversation every turn, which means a learner correcting themselves halfway
through just works with no extra code.

We tested three Groq models on the same three conversations before choosing gpt-oss-20b. Notes are in
decisions.md.

## Roughly where we stand

Engine done, nothing to look at yet.

| Piece | State |
| --- | --- |
| Conversation to profile | done |
| Goal to skills | done |
| Skill gap and ordering | done |
| Scheduling into phases | done |
| Explanations and learner questions | not started |
| Interface and dashboard | not started |
| Progress tracking and feedback | not started |
| Real catalog with embeddings | not started |

Four of eight. The half that is done is the half that is hard to fake, and the half that is left is
mostly wiring and presentation.

## Next

Streamlit interface, so all of the above is finally visible. Then explanations, then the feedback loop,
then swap the seed catalog for a real one.

## Known gaps we are carrying on purpose

Relevance scoring is flat until embeddings land, so ranking currently runs on three signals instead of
four. Ranking weights are hard coded because we have no feedback data yet. The catalog is hand written,
though the file shape is final so the real one drops straight in.
