# Handoff

Read this first if you are picking up this project cold. It says what we are building, why it is built
this way, where everything is, and what happens next.

Companion files: `decisions.md` is every choice and why, `progress.md` is where we are per commit.
Keep all three current. Every commit updates progress.md, and any commit that involves a judgement
call updates decisions.md too.

---

## 1. What we are building

Hackathon brief: an AI powered personalised learning path recommender. A learner describes a goal in
plain language, we work out what they are missing, and we produce a structured roadmap of real courses
with prerequisites, phases and milestones, explain every choice, and adapt when they give feedback.

Judged on functionality 25, problem understanding 20, AI implementation 20, innovation 15, interface 10,
code quality 10.

## 2. The one idea everything follows from

The obvious build is to ask an LLM for a roadmap and print it. It invents courses that do not exist,
answers differently every time, and cannot guarantee that linear algebra comes before backpropagation.

So the model never writes the curriculum. The path comes out of a skill graph plus a real catalog, and
the model only sits at the two ends: reading the learner in, and writing the explanation out.

```
conversation -> profile -> skill gap -> ordering -> schedule -> path -> explanation
                profile.py  graph.py    graph.py    path.py            explain.py
                                                                       state.py (feedback)
```

Everything between the two ends is a pure function. Same profile gives the same path every time, no
course can be invented, and the prerequisite order is provably correct rather than hopefully correct.

## 3. Files

| File | What it does |
| --- | --- |
| `graph.py` | The prerequisite DAG. Gap analysis, ordering, phases. No LLM, no I/O beyond load. |
| `path.py` | Picks a resource per skill, cuts phases sized to the learner's hours, adds milestones. |
| `profile.py` | Conversation to profile. The only place free text enters. Runs gpt-oss-20b. |
| `explain.py` | Why each pick was made, and questions about the plan. Runs gpt-oss-120b. |
| `state.py` | Learner state and what feedback does to it. Path is rebuilt, never edited. |
| `data/skills.json` | Skill ids, names, prerequisites. The spine. |
| `data/roles.json` | Common career roles to their target skills. |
| `data/catalog.json` | Courses, projects, assessments. Currently 41 hand written seed items. |
| `scripts/fetch.py` | Downloads the Coursera CSV from Hugging Face. |
| `scripts/normalise.py` | Cleans, parses hours and level, filters to our domain, keeps 400. |
| `scripts/label.py` | Labels each course with teaches and assumes, growing the taxonomy. |
| `data/raw/` | Pipeline intermediates. The 22MB CSV is gitignored, the rest is committed. |

Scripts are offline. They run once and never at demo time.

## 4. Running it

```
pip install groq python-dotenv networkx model2vec pandas numpy
echo "GROQ_API_KEY=..." > .env
python3 scripts/fetch.py && python3 scripts/normalise.py && python3 scripts/label.py
```

There is no interface yet. Everything is exercised from the terminal.

## 5. Things that cost us time, so you do not repeat them

**Free tier is 8000 tokens a minute.** A batch costs about 1800, so four a minute is the ceiling. Pace
deliberately, do not fire fast and rely on retries.

**Never let a retry sleep without printing.** A stalled run looked identical to a working one for
thirteen minutes.

**Model choice is per job, decided by testing, never by size.**
gpt-oss-20b for schemas and extraction. It follows a schema and returns nulls instead of guessing.
gpt-oss-120b for prose and judgement. Better reasons, but its free budget dies under bulk work.
qwen3.8-27b for labelling. It readily names new skills, which is a flaw in extraction and the whole
point in labelling.

**Reasoning tokens count against max_tokens.** Set reasoning effort to low or completions come back
empty, and the amount varies run to run so a generous cap is not a fix.

**Check the data, not the summary counts.** Our first labelling run reported healthy totals while 13
percent of courses taught and assumed the same skill, which would have been a cycle.

**When a patch reveals the same class of hole twice, the approach is wrong.** We patched embedding
anchors twice before accepting that embeddings cannot make that judgement.

## 6. How we work

Pseudocode and reasoning before code, agreed with the human first.
Only what is needed. No extra abstraction, no defensive scaffolding, no files nobody asked for.
Every decision recorded in `decisions.md` in plain English with the tradeoff, no jargon, no hyphens.
Commits are small and describe the reasoning, not the diff.

## 7. Where we are

Done: skill graph, path builder, profile extractor, explainer, feedback handling, catalog pipeline
through labelling. 350 courses labelled, taxonomy grown from 29 to 63 skills.

Not done: the graph build from those labels, the interface, and wiring relevance scoring on.

## 8. Next step, in detail

**Build the real graph from the labels.** `scripts/build_graph.py`, output reviewed by the human before
anything overwrites `data/skills.json`.

1. Dedupe the taxonomy, three filters cheapest first.
   Structural blocks: never merge two skills if one course teaches both, or if one appears in the
   other's assumes. That kills the dangerous pairs, supervised against unsupervised, for free.
   Context embeddings: embed the descriptions of courses that teach a skill, not the skill's name.
   Names put opposites two characters apart.
   Model judge on whatever survives, with the courses and prerequisites as evidence.
   The human sees only what the judge is unsure about, probably two or three pairs.
2. Edges from the labels. Every id in assumes points to every id in teaches. Count how many courses
   support each edge.
3. Break cycles by dropping the least supported edge, and report every break.
4. Contract skills that are assumed but never taught, so paths do not contain steps with no resource.
5. Embed courses and freeze. Vectors go in a separate `.npy`, not inside the JSON, so the catalog stays
   readable.
6. Wire relevance into `path.build`, which already takes it as a function.

Then the interface, which is deliberately last because the whole team wants to build that part together.

## 9. Known gaps we are carrying on purpose

Relevance scoring is flat until step 6, so ranking runs on three signals instead of four.
Ranking weights are hard coded because we have no feedback data yet.
`dl.backprop` and `nlp.finetune` have no course in the real catalog, so paths through them show a gap.
Some new skills, game development and blockchain among them, sit outside what our roles target. They
are harmless and widen what the tool can answer.
