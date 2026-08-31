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

**Commit 9, the real graph and relevance.** `scripts/build_graph.py` and `embed.py`. Turns 350 labelled
courses into the actual prerequisite graph and switches semantic ranking on.

Two problems we only found by looking at the paths it produced. Building purely from the corpus lost 23
of our 34 hand written edges, because course descriptions say "assumes basic machine learning" and never
"assumes backpropagation". And even after keeping ours, one bad corpus edge put cloud before supervised
learning, which dragged JavaScript and Aruba networking into a generative AI path.

So corpus edges are now additive only and may not point at a skill we wrote by hand. Path went from 25
skills back to 18, and the chain behind supervised learning from 14 to 6.

The taxonomy needed no merging at all. Every labelling batch saw the whole taxonomy, so the model reused
ids rather than inventing synonyms, and the design prevented the duplicates instead of us cleaning up
after them.

63 skills, 59 edges, 362 catalog items, 350 of them real Coursera courses.

**Commit 10, the review pass.** Three agents read every file and verified by running code. They found
sixteen real bugs and we fixed all of them.

The two that mattered most. Course hours were wrong for half the catalog, because most rows state the
total outright and we ignored it and multiplied the span by the weekly rate instead. And the frozen seed
file was untracked while skills.json was modified, so one commit would have published the derived graph
with no freeze and the next build would have read its own output back as hand verified.

Also fixed: a course teaching two skills was counted as work twice, milestone hours were left out of the
schedule entirely, picking had no tie break so regenerating the catalog reshuffled recommendations,
three courses shared an id, the explainer crashed on any path containing a skill with no course, and the
profile cleaner raised on four shapes the model actually returns.

None of it was visible in the numbers we print. All of it was found by running the code against
adversarial input or checking a figure against the raw source.

Rebuilt after the fixes: 72 skills, 65 edges, 370 catalog items. Verified end to end, all seven roles
produce paths with no ordering violations.

**Commit 11, connecting the two halves properly.** The frontend existed and looked good, but three
things between it and the engine were broken.

Feedback lost most of what it changed, because the API rebuilt from the request rather than from the
state it had just updated. Already knowing a skill did nothing and too hard never moved the level.
Relevance was never passed in, so the strongest ranking signal sat inert and the goal text we collect
was unused. And progress carried the same double count we had fixed in the builder, reporting 587 hours
against 520 and a weeks left that disagreed with the roadmap on screen.

On the interface: every page held its own copy of the path, so building one in the co-pilot and clicking
to My path showed nothing. Only completed was wired of the five reactions. And the roadmap drew five
milestones while the header counted fourteen.

Two content gaps turned up as well. Nothing in the 400 courses mentions backpropagation and only one
mentions Git, so both now carry real courses we added by hand and flagged to survive rebuilds.

The last one was the most interesting. Ranking normalises relevance across the candidates for a skill,
so the best match takes the whole term no matter how small the real gap. A 0.09 edge became a 0.40
advantage, enough to pick a 173 hour data science specialisation to teach Git over a 16 hour Git course.
A course now has to fit inside eight weeks of the learner's time unless nothing shorter teaches the
skill. That took a route from 81 weeks to 49.

Verified in the browser end to end: chat builds a path, it survives navigation and refresh, all five
reactions change the plan, questions get answered, and the API being down reads as a sentence.

**Commit 12, the conversation itself.** Three bugs sat on the first thing anyone will try.

Saying "machine learning" produced no skills, so the assistant asked the same question forever. Saying
"8 hours a week" was answered as though it were a question, so the time never reached the profile, and
with no hours the schedule divided by one and reported 138 weeks for four skills. And the validation
error from sending our own profile back rendered as "[object Object]" on screen.

The chat endpoint now re-reads the learner on every message and decides for itself whether anything
changed, rather than asking the model whether the message was a change request. Same conversation now
ends in a 10 week path.

**Commit 13, the conversation has a memory.** Answering a question with a bare "15" did nothing,
because only the newest message ever reached extraction. The interface now sends what has been said so
far, which is what we designed extraction around in the first place and lost when the interface was
built. Short answers and corrections both work again with no special handling.

**Commit 14, it asks what you already know.** We only ever required a goal and weekly hours, so nobody
was asked about their existing skills unless they happened to mention them. That is the setting that
changes a path the most. The first path now comes back with one question naming the steps it starts
with, and answering it collapses the roadmap in front of you.

**Commit 15, everything on screen is real.** Eleven controls did nothing when clicked, and the streak
and activity chart were invented on a product that stores nothing.

Roadmap nodes and milestone rows open the real course now. New focus clears the route. The sidebar and
the header show real progress. The chart is hours per phase. The per module explanation, which existed
and was tested but was never called by anything, has an endpoint and appears under the current step.

Dead code out: four unused dependencies, an unused helper, a dead component, four dead style rules and
an unused import.

**Commit 16, learners are remembered.** Anonymous id minted by the browser, one SQLite row per learner
holding their state and the last twelve chat turns. The path is never stored, only rebuilt.

Saving happens inside the endpoints that already pass state around, so there is no way to change
something without it being written down. Wiping the browser cache and keeping only the id brings back
both the roadmap and the conversation.

The chat thread moved into the shared session too, so the co-pilot page and the dashboard are one
conversation instead of two that could not see each other.

**Commit 17, the ranking learns per person.** Each learner carries their own four ranking weights,
nudged by their own reactions and stored with the rest of their state. Too hard raises how much
difficulty matters, not for me raises subject match, and a vague rejection of a very long course is read
as being about length. Finishing something reinforces at half a step, because rejecting says more than
finishing.

Nudges are small, bounded and renormalised so the four always sum to one. A new goal resets the subject
and style signals and keeps what we learned about the person.

The four bars are on the dashboard in plain words. Three too hard clicks move difficulty from 25 to 31
percent in front of you.

**Commit 18, it stopped lying about what it can do.** Asked to shorten a path, the assistant replied
"we'll trim total hours and drop the least essential module" and trimmed nothing. A made up action rather
than a made up course, which is harder to catch because the plan looks fine.

Three causes. The explainer wrote in the first person about changes. We compute a change request flag and
had stopped using it. And shortening had no lever behind it at all, since the deadline only ever set a
flag and never touched the plan.

Now the deadline gap is arithmetic instead of a label: "12 weeks against your 4 week deadline, about 58
hours a week would make it, rather than 20." An impossible ask walks to a real answer, and the planner
stays deadline blind on purpose.

**Commit 19, an audit under load.** A teammate added the Docker and deployment config, so we stress
tested the whole thing rather than only reading it.

Two real concurrency bugs, both invisible in normal use. One sqlite connection shared across FastAPI's
thread pool failed six times in eighty concurrent requests. And two first requests arriving together
both entered the embedding model loader, which raised inside tqdm and reached the browser as a 500 that
looked like a CORS failure, which sent us looking in the wrong place for a while.

Both fixed and tested. Sixty concurrent requests, zero errors. The model, graph and catalog now load at
startup, and the image downloads the model at build time so a cold container never races on it.

Also: a made up goal returned 200 and an empty plan, goal_text had no length limit, and .DS_Store was
committed.

**Commit 20, evals first, then the change they justified.** Built `evals.py` and `EVALS.md`: standard
recommender, slot filling and grounding measures rather than numbers we invented, plus a linear
programming lower bound so optimisation quality is distance from optimal instead of distance from
another heuristic.

The evals said course selection was leaving 40 percent of study time redundant, so selection became a
weighted set cover. Median study hours 295 to 180, median weeks 27 to 17, violations still zero,
coverage still complete, and we sit a median 1.27 times the lower bound.

They also surfaced two things we had not seen: 43 of 72 skills are unreachable from any role, and only
26 of 366 courses are ever recommended. Both point at the same cheap fix, more roles.

**Commit 21, acting on what the evals found.** Nine more roles chosen by where the catalog actually has
depth rather than by what sounded good, real courses for the five skills backed by a single option, and
a tuned fit exponent.

The exponent is the one worth explaining. Set cover values coverage per hour, which swamped how well a
course suits the learner, so their own weights moved only 6 percent of picks. Sweeping it from 1 to 6
and measuring showed 4 gives 22 percent at the same distance from optimal and slightly fewer hours.
Better on every axis rather than a trade, and not guessed.

Unreachable skills 43 to 24. Fragile skills 17 to 12. Median study hours 180 to 80. Still zero
prerequisite violations across all 48 plans.

**Commit 22, roles proposed and reviewed.** `scripts/propose_roles.py` suggests roles for skills nothing
reaches, ranked by how much each would open up, and writes them for a person to accept or delete. Took
two of five. Skills no role can reach is now 19, down from 43 before any of this.

Extraction measures clean: role, hours and style all 100 percent, known skills precision and recall both
perfect, groundedness 100 percent. Style needed a line in the prompt telling it how to read the way
someone describes learning, which we had simply never written.

One bug worth remembering: --apply originally re-ran the proposal and overwrote the file we had just
edited, applying its own five instead of our two. A review step that discards the review.

**Commit 23, one rule for every course.** A four hour course about networking was beating a sixteen
hour course about Git on the Git step. The four hour one claimed one skill, the sixteen hour one
claimed one skill, and one skill in four hours is cheaper per hour than one skill in sixteen. The
course was not better, it was shorter.

The cause was a free pass we had written ourselves. We only trust a course to teach a skill properly
per six hours of its length, but we let every course keep at least one claim no matter how short it
was. So the rule applied to long courses and not to short ones, and the shortest entries in the catalog
came out looking like the best value in it.

Removed the exception. A course too short to teach one skill properly now teaches none. That drops 106
courses, 8 percent of the catalog, and leaves every single skill still covered. Git now resolves to a
course about version control, and calculus and linear algebra to one maths course that covers both.

We considered special casing the offending courses and threw that idea out. The system has to hold up
on a catalog we have never seen, and a fix that names courses is a fix that only works on ours.

**Commit 24, an audit that went after our own numbers.** Attacked the whole thing rather than reading
it: 300 concurrent mixed requests, 27 hostile request bodies, 9 prompt injections, a clean clone, and
every number in every document checked against what the code prints now.

Most of it held. No secrets anywhere in git history. Zero 500s, every bad body caught as a 422, no way
found to read another learner's state. Nine attempts to make the model invent a course, leak the system
prompt, leak the key, or promise a change it cannot make, and none of them worked: asked to cut a plan
to two weeks it answered with the arithmetic instead of a promise, and told its plan was three weeks it
gave back the real numbers.

Two things were wrong. Our approximation ratio counted milestone and assessment hours in the numerator
while the bound was built from a pool that excluded them, so it had been comparing two different
questions and reading 1.41x where the honest figure is 1.24x. It made us look worse than we are, which
is the safe direction, but it did not measure what our own document said it measured. And the goals and
profile pages printed fixed text, prerendered at build time, so everyone saw the same "Balanced
builder" whatever their actual profile said.

Both fixed. Two smaller things we found and deliberately left, with reasons, in decisions 111.

**Commit 27, the submission pass.** Clicked every control in the interface with a real path loaded
rather than reading the code and assuming: four nav links, the view switch, all five feedback buttons,
mark complete, new focus, the chat, and fifteen roadmap links. Every one has a real effect and the
empty state disables the six that need a plan.

Two ghosts found. "Engine linked" and "LLM connected" were literals next to a green dot, claiming a
working backend whatever was happening; they read real reachability now and go red when you kill the
API. And a CSS rule was styling a button that had been removed from the markup.

Probed what the API trusts from the client: garbage known skills, fifty duplicate goal skills, a
learner claiming to know all ninety one skills, garbage completed ids and a horizon of ninety nine
thousand weeks are all absorbed without corruption, and an unrecognised goal skill is refused with a
422 rather than silently dropped. One gap found and left, in decision 117.

Deleted main.py, two unused imports and the dead CSS. Wrote README.md, which we had never had.

## Roughly where we stand

Engine done, nothing to look at yet.

| Piece | State |
| --- | --- |
| Conversation to profile | done |
| Goal to skills | done |
| Skill gap and ordering | done |
| Scheduling into phases | done |
| Explanations and learner questions | done |
| Interface and dashboard | done |
| Progress tracking and feedback | done |
| Real catalog with embeddings | done |

Eight of eight. The whole thing runs end to end, engine and interface, on real data.

## Next

Polish and the submission itself: the demo video, the solution document, and a deployed URL. The engine
and the interface are both working, so what is left is presentation rather than building.

## Known gaps we are carrying on purpose

Hosting on Hugging Face Spaces wipes the disk on restart, so remembered learners survive the session
and not the week. Fine for judging, wrong for real use, and the fix is a hosted database rather than a
code change.

Eight percent of the catalog can never be recommended because it teaches nothing our taxonomy knows
about. The taxonomy grows from the catalog, so this shrinks as the catalog grows, and we would rather
carry it than invent skills to absorb the leftovers.

The share of the catalog we actually hand out is low, but that is set cover doing its job rather than a
defect. See EVALS.md, which explains why the two coverage numbers disagree.

**Commit 11, the UI layer.** Implemented the Next.js frontend. Replaced the initial Streamlit plan with a custom React architecture to achieve the "Cockpit" aesthetic. Built the three-column layout: navigation sidebar with daily streak tracking, a cinematic hero section, and a dynamic SVG-based roadmap graph. Integrated the industrial color palette (Iron Core, Aqua, Rust).
