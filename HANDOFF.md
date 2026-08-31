# Handoff

Read this first if you are picking up this project cold. It says what we are building, why it is built
this way, where everything is, and what happens next.

Companion files: `README.md` is the short version for someone seeing this for the first time, `decisions.md` is every choice and why, `progress.md` is where we are per commit.
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
| `data/catalog.json` | 358 real Coursera courses plus 12 hand written projects and assessments. |
| `data/seed_skills.json` | Frozen copy of the 29 hand written skills. The graph build reads this, never its own output. |
| `data/vectors.npy` | Frozen course embeddings, same order as catalog.json. |
| `embed.py` | Goal text to course relevance, normalised across the candidates for one skill. |
| `scripts/build_graph.py` | Labels to the real graph. Report by default, `--apply` to write. |
| `api.py` | FastAPI adapter. `/health`, `/path`, `/path/feedback`, `/chat`. |
| `db.py` | Anonymous learner storage. SQLite, state as JSON, path never stored. |
| `test_core.py` | 46 tests, most with no API calls, about a second. |
| `learning-path-finder/` | Next.js interface. `lib/store.ts` holds the one shared path. |
| `scripts/fetch.py` | Downloads the Coursera CSV from Hugging Face. |
| `scripts/normalise.py` | Cleans, parses hours and level, filters to our domain, keeps 400. |
| `scripts/label.py` | Labels each course with teaches and assumes, growing the taxonomy. |
| `data/raw/` | Pipeline intermediates. The 22MB CSV is gitignored, the rest is committed. |

Scripts are offline. They run once and never at demo time.

## 4. Running it

```
pip install -r requirements.txt
echo "GROQ_API_KEY=..." > .env
python3 -m uvicorn api:app --port 8000          # engine
cd learning-path-finder && npm install && npm run dev   # interface on :3000
```

The interface needs the API. If it says "Awaiting you" forever, the API is not running.

To run the tests and the eval suite, install the dev extras instead. They pull pytest and scipy, which
the API never imports and which we keep out of the deployed image:

```
pip install -r requirements-dev.txt
python3 -m pytest -q      # 69 tests
python3 evals.py          # full measurement report, about a second, no model calls
```

Rebuilding the catalog from scratch, which needs about half an hour of free tier calls:

```
python3 scripts/fetch.py && python3 scripts/normalise.py
python3 scripts/label.py && python3 scripts/build_graph.py --apply
```

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

**Extraction reads the whole conversation, not one message.** It is what makes "15" and "actually make
it 20" work with no code for either. The interface must keep sending the history.

**Check the data, not the summary counts.** Our first labelling run reported healthy totals while 13
percent of courses taught and assumed the same skill, which would have been a cycle. Later, three review
agents found sixteen bugs, none of which showed up in anything we print. Course hours were wrong for
half the catalog for the same reason: the number looked plausible, and nobody compared it to the source
string it came from.

**data/seed_skills.json must stay in git.** The graph build reads it as the hand written truth. If it is
missing, the build freezes whatever is in skills.json instead, which after one `--apply` is the derived
graph, and corpus noise becomes permanently unbreakable.

**When a patch reveals the same class of hole twice, the approach is wrong.** We patched embedding
anchors twice before accepting that embeddings cannot make that judgement.

## 6. How we work

Pseudocode and reasoning before code, agreed with the human first.
Only what is needed. No extra abstraction, no defensive scaffolding, no files nobody asked for.
Every decision recorded in `decisions.md` in plain English with the tradeoff, no jargon, no hyphens.
Commits are small and describe the reasoning, not the diff.

## 7. Where we are

Everything is built. Skill graph, path builder, profile extractor, explainer, feedback handling, the
catalog pipeline, semantic relevance, persistence, per learner ranking weights, the API and the
interface.

91 skills, 86 edges, 1214 catalog items, 18 roles. 69 tests pass. `python3 evals.py` prints the full
measurement report in about a second without touching a model.

What is left is submission work rather than building: the demo video, the solution document, and a
deployed URL that stays up.

## 8. How the two halves connect

`api.py` is FastAPI and is the only thing the frontend talks to. Endpoints: `/health`, `/state` for GET
and DELETE, `/path`, `/path/feedback`, `/explain`, `/chat`.

Every request carries an `X-Learner-Id` header minted by the browser. No login, no personal data. That
id is the SQLite key, one row per learner holding their profile, their four ranking weights and their
last twelve conversation turns.

The path is never stored. It is rebuilt from the learner's state on every request, which takes about two
milliseconds and means what is on screen always matches the profile that produced it. Feedback posts an
event, the state changes, the next build reflects it.

The frontend is Next.js in `learning-path-finder/`. `lib/store.ts` holds the session, `lib/api.ts` wraps
the fetch calls, and the components are the sidebar, the chat, the roadmap graph and the telemetry
cards.

To run both: `uvicorn api:app --port 8000` and `npm run dev` in the frontend folder. The API needs
`GROQ_API_KEY` in `.env`. Extra keys named `GROQ_API_KEY2` and so on are picked up automatically and
rotated when one runs out of quota.

## 9. Known gaps we are carrying on purpose

Hugging Face Spaces wipes its disk on restart, so remembered learners last the session and not the
week. The fix is a hosted database, not a code change.
Eight percent of the catalog teaches nothing our taxonomy knows about and can never be recommended.
Every skill has at least one course, so the "no resource" case is unreached but still handled.
Some new skills, game development and blockchain among them, sit outside what our roles target. They
are harmless and widen what the tool can answer.
