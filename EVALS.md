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
approximation ratio     median 1.41x     worst 2.00x     best 1.03x
```

The worst cases are the smallest plans, where the bound is loose rather than the plan bad: a fractional
tenth of a course is not something a person can enrol in.

This got worse on purpose. It was 1.22x when courses were allowed to claim more skills than their
length could support, because a four hour course claiming five skills is a bargain greedy loves and a
lie. Both our plan and the lower bound are computed on the same trimmed catalog, so the comparison is
still fair. We are further from optimal against an honest catalog, which we prefer to being close to
optimal against a fictional one.

For context, greedy set cover is provably within a log factor of optimal. We do not claim optimal.

## Path quality, 18 roles by 3 learner profiles, 54 plans

```
prerequisite violations        0 / 0 / 0        worst / median / best
skills covered by a course     100% everywhere
study hours                    241 / 93 / 24
weeks                          22 / 8 / 2
modules per distinct course    2.00 / 1.20 / 1.00
```

Prerequisite violations is a hard constraint, not a score. Any number other than zero is a bug, and it
is checked on all 54 plans on every run.

## Personalisation

```
different people, same goal      29%    of picks differ
weights changed the picks        69%
three "too hard" clicks changed  76%
```

The weights figure was 6% until we measured it. Set cover values coverage per hour, a ratio that varies
far more than a fit score, so the learner's own weights barely moved a pick. Sweeping the exponent on
fit from 1 to 6 showed 4 was the right setting.

It then sat at 22% for a while because of a flaw in this file, not in the code. Our test learner had no
goal in their own words and a learning style nothing matched, so relevance and style were constant for
every course and two of the four signals were switched off in every measurement. Giving the test
learner a real goal took it from 22% to 69%. We had spent five experiments redesigning the ranker for a
problem that lived in the harness.

One minus mean pairwise Jaccard similarity between recommendation lists, the usual recommender
definition. Two people asking for the same job get materially different plans, and reacting to the plan
changes it.

## Reach and speed

```
reachable by some goal      91%   (1102 of 1208 courses)
surfaced by our test goals  8%    (95 courses, over 54 role plans and 60 random goals)
path build                  2 ms p50, 6 ms p95
```

These are two different questions and we report both because only one of them is a problem.

Reachable asks whether a course can ever be recommended to anybody. At 91% it is fine, and the missing
9% are courses that teach nothing in our taxonomy.

Surfaced asks how many we actually hand out across our own test goals. It is low by design: set cover
concentrates on courses covering several skills at once, so out of eleven options for a skill it picks
the same strong one every time. That is the algorithm working. Raising this number means asking for
more different things, not writing a better recommender.

## Determinism

```
identical across repeated runs and reversed catalog order    18 of 18 roles
```

The same learner gets the same plan every time. This is why ranking ties break on course id.

Reversing the catalog is the half that earns its keep. It caught us scoring courses against embedding
vectors by list position instead of by id, so shuffling the catalog silently compared every course to
the wrong vector. Repeated runs alone would never have seen it.

## A note on running these

Groq's free tier allows 200,000 tokens a day. A full `--llm` run costs about 30k and rebuilding the
catalog about 90k, so a few runs and a rebuild will exhaust a day.

If the budget is gone the extraction section reports that it could not run, rather than printing zeros
that look like a broken model. We learned that the hard way: an exhausted budget once scored as the
extractor getting every field wrong, and we went looking for a prompt bug that was not there.

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
