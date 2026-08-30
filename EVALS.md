# How we measure this

Run `python3 evals.py` for the structural report, about a second and no model calls.
Run `python3 evals.py --llm` to add the two that need Groq.

Every number below came out of that script. Nothing here is estimated.

## Why these metrics

The system is three things at once, so it needs three families of measurement.

It is a **recommender**, so we use the standard recommender measures: catalog coverage, personalisation
as one minus pairwise Jaccard between users, and constraint violation rate.

It is a **structured extraction** problem, so slot filling precision, recall and F1 per field.

It is a **generation** problem grounded in facts we supply, so a groundedness rate.

And underneath it is an **optimisation** problem, so we measure distance from optimal rather than
guessing.

## Optimisation quality: distance from optimal

Choosing the cheapest set of courses covering a learner's skill gap is minimum cost set cover, which is
NP hard. We solve it greedily, weighted by how well each course suits the learner.

To know how good that is, we solve the **linear relaxation** of the same problem with scipy: allow
fractional courses, minimise total hours, require every skill covered. The relaxation can only be
cheaper than the true integer optimum, so our hours divided by it is an honest upper bound on how far
from optimal we are.

```
approximation ratio     median 1.27x     mean 1.42x
```

The worst case, 4.00x, is a two skill plan where the bound is loose rather than the plan bad: a
fractional tenth of a course is not something a person can enrol in. On the larger plans, where the
relaxation is tight, we sit between 1.04x and 1.11x.

For context, greedy set cover is provably within a log factor of optimal. We do not claim optimal.

## Path quality, 7 roles by 3 learner profiles

```
prerequisite violations        0 / 0 / 0        worst / median / best
skills covered by a course     100% everywhere
study hours                    467 / 180 / 16
weeks                          41 / 17 / 2
modules per distinct course    2.00 / 1.31 / 1.00
```

Prerequisite violations is a hard constraint, not a score. Any number other than zero is a bug, and it
is checked on all 21 plans on every run.

## Personalisation

```
different people, same goal      38%    of picks differ
weights changed the picks        12%
three "too hard" clicks changed  55%
```

One minus mean pairwise Jaccard similarity between recommendation lists, the usual recommender
definition. Two people asking for the same job get materially different plans, and reacting to the plan
changes it.

## Reach and speed

```
catalog coverage      7%   (26 of 366 courses ever recommended)
path build            1 ms p50 and p95
```

Catalog coverage is deliberately reported even though it is bad. Across every role and profile we
recommend 26 distinct courses, so the effective catalog is far smaller than the 372 we loaded. Two
causes: only seven roles, and set cover concentrating on courses that cover several skills at once.
More roles is the fix, and it is cheap.

## Determinism

```
identical across repeated runs and reversed catalog order    7 of 7 roles
```

The same learner gets the same plan every time. This is why ranking ties break on course id.

## Extraction, against golden utterances

Precision, recall and F1 per slot, over hand written utterances with known correct answers.

Set valued slots used to be scored by subset, which is recall only: a model returning every skill in the
taxonomy would have scored a hundred percent. Precision is the half that matters here, because an
invented known skill silently deletes steps from someone's plan.

## Groundedness

The share of generated explanations where every claim traces to the facts we supplied. RAG evaluation
normally does this with a second model as judge. Ours is a deterministic proxy: every number in the text
must appear in the facts, and no phrase may promise an action we cannot take.

It is cheaper, reproducible, and unlike a model judge it cannot hallucinate. It exists because the
explainer once answered a request to shorten a path with "we'll trim total hours and drop the least
essential module", having trimmed nothing.
