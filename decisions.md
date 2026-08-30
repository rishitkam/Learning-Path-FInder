# Decisions

Every choice we made, what else we could have done, and why we went this way.
Newest at the bottom.

## 1. The AI does not write the curriculum

The obvious build is to ask an LLM for a roadmap and print it. It invents courses that do not exist,
answers differently every time, and cannot promise linear algebra comes before backpropagation.
Prompting does not fix any of that.

So the path comes from a skill graph plus a real catalog. The LLM only reads the learner in and writes
the explanation out. It never picks or orders content.

Trade off: we have to build the graph. What we get is reproducible, cannot invent a course, and can
prove its ordering.

## 2. Python, not JavaScript

We sketched it in JavaScript first. Switched because the team writes Python and cannot defend a language
it does not know on pitch day, and because every library we want is here: networkx, sentence
transformers, scikit learn if we later fit the ranking weights.

Cost: Streamlit looks plainer than a custom React app. Interface is 10 percent of the score, so we take
the hit and spend the time on the engine.

## 3. Streamlit for the interface

Alternatives were FastAPI plus React (two deploys, JavaScript again) or FastAPI plus HTML templates
(more control, more work). Streamlit gives chat, charts and a dashboard in one Python file and deploys
free, which covers the application access deliverable in minutes.

None of our logic knows the interface exists, so moving off it later touches nothing.

## 4. Groq for the model, embeddings run locally

Groq free tier. Fast, which matters because we re read the profile every chat turn, and the API follows
the OpenAI shape.

It has no embeddings endpoint, so we embed locally with sentence transformers and bake course vectors
into a file. That also makes embeddings free and offline. The free tier limits requests per minute, so
we cache and keep a prepared profile ready in case the demo hits a limit on stage.

## 5. Skills and courses are separate

A skill is knowledge. A course is one way to get it. Separate files means swapping a boring or hard
course never reshapes the path. Merged, every swap would rebuild the plan.

## 6. Prerequisites sit on the skill, not the course

Three courses can teach one skill. Separate prerequisite lists would drift apart and contradict each
other. One list per skill, one source of truth.

## 7. Depth is calculated, never typed in

Depth is the longest chain of prerequisites behind a skill, derived from the graph. Hand written level
numbers always end up disagreeing with the real prerequisites once the file grows. A derived number
cannot disagree with the edges it is made from.

## 8. The graph checks itself at startup

On load we confirm every prerequisite points at a real skill and there are no circular prerequisites,
and refuse to start otherwise. One typo would otherwise produce a quietly wrong path that still looks
fine. Five lines, cheapest reliability in the project.

## 9. Knowing a skill means knowing what it was built on

Say you know transformers and we mark backpropagation, neural networks, supervised learning and Python
known too. One line, and it is the main reason the tool feels like it understood you. It is also why two
people with the same goal get different paths.

## 10. The order is deterministic, not just correct

Many orders are valid for the same skills, and a plain topological sort returns any one of them, so a
refresh could change the path. We break ties on depth then id. Same profile, same path, always.

## 11. Phases come from the graph

Skills at the same depth have no prerequisite between them, so they can be learned in parallel. Group by
depth and each group is a phase. That makes a phase a fact about the graph, not a heading someone made up.

## 12. Goals resolve through a role table first, model second

Learner types "I want to be a GenAI engineer". A small file maps common roles to target skills. Match
means instant, free and always valid. No match and the model maps the goal, choosing only from our fixed
skill list.

The table sits next to the graph so its ids get checked at startup. The routing sits outside, in the
profile layer, so the graph only ever receives finished skill ids and stays testable without mocks.

## 13. Things we did not build

No vector database. A few hundred courses is a list and a dot product.
No LangChain. It would hide the exact part a judge should be able to read, our own pipeline.
No database for the graph. Twenty nine skills fit in memory and every operation takes microseconds.

## 14. Depth is universal, phase boundaries are personal

Depth never changes per learner. What changes is where we cut the line. A learner with 20 hours a week
gets three fat phases, one with 4 hours gets eight small ones, from the identical skill order.

Says it cleanly: the graph decides the sequence, the learner decides the pace. Prerequisites are never at
risk because regrouping never reorders.

## 15. A phase is about a month of the learner's time

Grouping strictly by depth gave eleven phases for nineteen skills, most holding one skill. Correct and
useless in a roadmap.

So we fill a phase until it holds roughly four weeks of their hours, then cut. We only cut at depth
boundaries and never split a depth level, so parallel skills stay together and nothing gets reordered.
We overshoot rather than undershoot, so no phase is a stray half hour.

## 16. Fake catalog first, real one later

The path builder needs a catalog and ours does not exist yet. Options were to build the real one first
(slow, blocks everything), stub the ranking, or hand write a small honest one.

We hand wrote 41 items covering all 29 skills. The file shape is final, so when the real catalog lands it
drops in and nothing gets rewritten.

## 17. Four ranking signals, weights visible

A course is scored on fit to the goal, level match, learning style and whether it fits their week.
Weights are 40, 25, 20 and 15 percent, hard coded in one dict.

We keep all four numbers on the module, not just the total, so the explanation is built from the actual
arithmetic instead of the model inventing a reason afterwards. Learning the weights needs feedback data
we do not have yet, and when we do it is a one line swap.

## 18. Relevance is pluggable and currently flat

Fit to the goal needs embeddings, which arrive with the real catalog. Until then it is a function passed
in that returns a constant, so ranking runs on the other three signals. No stub to rip out later, just a
different function.

## 19. A skill with no course stays in the path

If nothing in the catalog teaches a skill we keep it with nothing attached. Dropping it would break the
chain and hiding it would be a lie. On stage it also proves we are reading a real catalog.

## 20. Greedy pick, not a search over whole paths

We take the top scoring resource per skill. Searching whole path combinations is smarter and we are not
building it yet. There are rarely more than a handful of candidates per skill anyway.

## 21. Milestones and assessments come from the catalog too

Each phase gets a project and a check pulled under the same rule as courses: everything it assumes must
already be covered. Nothing invented. Nothing reused twice. If nothing fits, the phase has none, because
a missing milestone beats a fake one.

## 22. Weeks are back to back with no buffer

Phases run straight into each other. Real learners are messier, but an invented buffer is an invented
number. We give a clean estimate and a feasible flag, and let that flag start the conversation when the
plan does not fit the deadline.

## 23. We picked the model by testing, not by size

Ran three Groq models on the same three conversations: a clear one, a vague one, and one where the
learner corrects themselves.

gpt-oss-20b was the only one that got the clear case fully right and the only one that returned nulls on
"idk i just wanna get into AI stuff" instead of guessing. Qwen invented two skills there, which is the
exact failure that poisons a whole path. The 120b model returned an invalid tool call on the clear case.

So we run gpt-oss-20b. Bigger is not better for constrained extraction, and now we can say why.

## 24. Official Groq SDK, not raw HTTP

Our first test went through urllib and got blocked by Cloudflare, which reads the default Python user
agent as a bot. We could have faked the header. Using the SDK is one dependency, removes the problem,
and gives us retries and streaming when we need them.

## 25. Bad values get dropped, never raised

A free model occasionally returns a skill id that is nearly right. We filter those out, clamp hours to
1 to 60 and level to 1 to 5, and fall back to balanced style. A slightly thinner profile is fine. An
exception in front of judges is not.

## 26. One retry, then move on

If the call fails twice that is a model problem, not bad luck, and the learner is sitting there waiting.
We keep the profile we already had and ask a plain question instead.

## 27. Only two fields are actually required

Goal and weekly hours. Level defaults to 2, style to balanced, and no deadline just turns the feasible
flag off. Anything more and we are interrogating someone before showing them anything worth having.

Which field is missing is decided by code, not the model, so there is no second API call and the model
cannot skip a question we need.

## 28. The explainer never sources a reason, it only phrases one

Why a skill sits where it does comes from the graph edges. Why a resource won comes from the score
breakdown we already store on every module. The model receives those facts and turns them into a
sentence.

So an explanation cannot contradict the plan, because it is built from the same numbers that made the
plan. And if Groq is down we still show the facts as plain text instead of showing nothing.

## 29. Explanations are cached on the facts, not on the profile

Streamlit reruns the whole script on every click. Without a cache we would burn the rate limit just
scrolling. The key is the facts themselves, so an explanation is reused until something in the plan
actually changes.

## 30. Questions come back with a change flag

The model answers with two fields: the answer, and whether the learner was asking about the plan or
trying to change it. A change request gets handed to the profile extractor, which updates the profile
and rebuilds. Feedback goes through one door, so the explainer can never quietly alter a plan.

## 31. Big model for prose, small model for schemas

Same test as before, three explanations and four questions on both. gpt-oss-120b was clearly better:
real reasons instead of restating the score, and it correctly caught "can i skip the RNN part" as a
change request where 20b treated it as a question.

So extraction runs on 20b and explanation runs on 120b. Opposite jobs, opposite answers, and both
decided by running them rather than guessing.

## 32. Reasoning tokens count against the output limit

Our first explanations came back empty. These models spend tokens thinking before writing, and that
thinking counts against max_tokens, so a tight cap leaves nothing for the answer. Worse, the amount
varies run to run, so at 500 tokens it was still failing one time in three.

Setting reasoning effort to low fixed it, 3 out of 3 on both models. Worth remembering for every call we
add later.

## 33. Most hallucination here was our wording, not the model

The explainer kept inventing things. It told the learner to spend two of their ten weekly hours on the
first video chapter, none of which we had given it.

Three of the four causes were ours. A field called hours got read as hours per week, so we renamed it
total_hours. An empty list for prerequisites made the model narrate the absence, so we drop empty fields
instead of sending them. Our own phrase about fitting the weekly hours sat next to a total, so we
reworded it. Only the last bit needed a prompt rule, telling it not to give study advice.

Worth remembering. When a model invents something, check what we handed it before blaming it.

## 34. Feedback changes the state, never the path

A click updates one dict and the path gets rebuilt from it. Nothing edits a path in place. That is only
possible because building is already a pure function, and it means the plan on screen can never drift
away from the profile behind it.

The state is plain JSON, so saving a learner later is one column in SQLite.

## 35. Already knowing something and finishing it are different clicks

Already knowing a skill removes it from the plan, because it was never needed. Finishing one leaves it
in the roadmap and ticks it, because they did the work and should be able to see it.

So the gap is computed from known skills only, and completed is a display and progress concern.

## 36. Rejecting a course never removes a skill

The block list holds resource ids, not skills. Say a course is too hard or boring and the skill stays
while we pick the next best thing for it. If nothing else teaches it, the module simply shows no
resource, same as a skill the catalog does not cover.

This is the one guarantee we will not trade. Feedback can never break the prerequisite chain.

## 37. Too hard does two things

Blocking that one course alone would hand them another course at the same level. So we also drop their
level by one, which changes the ranking for everything ahead of them. One without the other is theatre.

Level moves by one and clamps between 1 and 5. Clicking too hard twice tells us something real. Clicking
it eight times does not, and the clamp is where we stop listening.

## 38. Too hard does not stretch the schedule

Someone struggling probably needs more time as well as an easier course. We leave the hours alone,
because weekly hours is something they told us and we should not quietly overwrite it. Better for the
assistant to spot the pattern and ask.

## 39. Real catalog: Coursera, pulled as a plain CSV

azrai99/coursera-course-dataset on Hugging Face. 6645 courses, no login needed, and it carries titles,
descriptions, skill tags, difficulty, real durations like "3 months at 5 hours a week", and URLs.

We download the CSV straight from the repo. The rows API rate limited us at 67 paged calls, and the
parquet route needs a library we do not have. One file, one request.

## 40. Course ids are a hash of the title

Not a row number. Refiltering the dataset then never invalidates labels we already paid for.

## 41. model2vec for embeddings, not sentence transformers

Static 256 dimension embeddings, no torch. We embed the learner's goal at runtime, and Streamlit gives
us 1GB of memory which torch would mostly eat.

Real tradeoff: static embeddings are weaker. Worth revisiting if relevance looks bad once wired in.

## 42. The domain filter is the model, not embeddings

We tried twice to filter off topic courses with embedding anchors. Both times about a tenth leaked, and
each fix only revealed the next hole: first languages and physics, then video, CAD and economics.

Static embeddings are the wrong tool for that judgement. The labeller already reads every course, so it
now returns a relevant flag and off topic courses are dropped before a skill is ever invented for them.

Lesson we should have taken one round earlier: when a patch reveals the same class of hole twice, the
approach is wrong, not the parameters.

## 43. Labelling runs on qwen, and here is why not the others

gpt-oss-120b gives the best labels but runs out of free tier budget long before 400 courses, asking for
waits of thirteen minutes. Unusable for anything bulk.

gpt-oss-20b never proposes a new skill. It crammed every course into our seed 29 and produced garbage:
MongoDB as data.sql, Java as prog.python, image processing as convolutional networks. It also threw away
Unix and C++ as irrelevant, because with no way to name a skill its only options are wrong or discard.

qwen3.8-27b names new skills readily. Back when we chose the profile extractor that same eagerness was
its flaw, because there we wanted nulls. Same trait, opposite job, opposite verdict.

## 44. Free tier limits are 8000 tokens a minute

A labelling batch costs about 1800 tokens, so four a minute is the ceiling. We pace at 16 seconds between
batches rather than firing fast and leaning on retries.

We lost time here by misdiagnosing twice. First we shrank prompts, when the limit was throughput not
size. Then we fixed pacing, by which point the daily budget on 120b was already the real blocker.

The mistake that actually cost us was a retry that slept without logging. A stalled run looked identical
to a working one for thirteen minutes. Every wait now prints.

## 45. Bulk work and conversation need different models

120b is fine for the explainer, which makes a handful of calls per session, and unusable for a fifty call
pipeline. Worth remembering before we add any other batch step.

## 46. The corpus cannot see fine grained prerequisites

We built the graph from the labels and it lost 23 of our 34 hand written edges, including the whole deep
learning spine: neural nets to backprop to CNN and RNN to transformers to large language models.

The reason is that course descriptions are marketing copy. They say "assumes Python and basic machine
learning". They never say "assumes backpropagation".

So we union instead of replace. Our hand written edges stay exactly as they are, and the corpus connects
the 34 skills it discovered. Hand written edges carry a support of 999 so a cycle break can never drop one.

## 47. Corpus edges may not point at a hand written skill

Even unioned, the first build produced a generative AI path containing JavaScript, Unix shell and Aruba
networking. One bad edge did it: the corpus claimed cloud comes before supervised learning, and cloud
carries JavaScript, shell, SQL and networking behind it.

Course descriptions list topics that appear together, not prerequisites. Our 29 already have correct
prerequisites, so the corpus is not allowed to add any to them. It only connects what it discovered.

That took the path from 25 skills back to 18, and the chain behind supervised learning from 14 to 6.

## 48. Nothing needed merging, because the design prevented duplicates

Twelve pairs survived the structural blocks and all twelve are false positives sitting around 0.82: C++
against C#, feature engineering against unsupervised learning.

There is nothing to merge because every labelling batch saw the whole taxonomy, so the model reused ids
instead of coining synonyms. We never built the model judge, since there was nothing for it to judge.
The structural blocks and the similarity report stay as a cheap check for when the catalog grows.

## 49. The build reads a frozen copy of the seed

--apply overwrites skills.json, which was also the file the seed edges were read from. A second run
would have read its own output back in as hand verified and baked corpus noise in permanently.

The seed is now frozen once into seed_skills.json and read from there. The build is idempotent.

## 50. Relevance is normalised across the candidates for one skill

Wired in, it changed nothing. Raw cosine across the catalog spans 0.52 to 0.75, so within one skill the
spread was 0.08 after weighting, while the style term alone swings 0.10.

Absolute similarity is meaningless here because every candidate teaches the same skill. Only the ranking
matters, so we normalise across the candidate set. Now the goal text visibly changes the picks: a data
engineering goal pulls data engineering courses, an LLM goal pulls the cloud ML ones.

## 51. What three review agents found

We had three agents read every file and verify by running code. They found sixteen real bugs. The ones
that mattered:

Course hours were wrong for half the catalog. Most rows state the total outright, "7 hours to complete
(3 weeks at 2 hours a week)", and we ignored it and multiplied 3 by 2. Coursera rounds the weekly figure
down so it never round trips. 2256 of 4757 raw rows wrong, and it silently threw away 374 valid short
courses that fell under our floor. Hours drive the effort score, the phase sizing and every week
estimate, so this was poisoning every schedule we had shown anyone.

The frozen seed was untracked while skills.json was modified. One commit would have published the
derived graph with no freeze, and the next build would have read its own output back as hand verified.
The exact corruption we wrote the freeze to prevent, sitting one command away.

A course teaching two skills in one path was counted as work twice, inflating schedules by up to seven
weeks. Milestone hours were left out of the schedule entirely, so a 300 hour capstone added no weeks at
all. Resource picking had no tie break, so regenerating the catalog quietly reshuffled recommendations,
which contradicts the reproducibility we claim.

Three courses shared an id, because the hash used the title alone and two universities both publish a
Machine Learning Specialization.

Lesson: none of this was visible in any summary we printed. Every one was found by running the code
against adversarial input or by checking a number against the raw source.

## 52. The explainer may not claim a reason that did not exist

Two cases where it was asserting things that were not true. A skill with one candidate has no winner,
yet it still said the course was the closest match to their goal. And with no goal text the relevance
signal is flat across every candidate, yet it outweighs the others and always ranked first, so it
claimed a match on a signal that decided nothing.

Both now say what actually happened, or say nothing. This matters more than it looks, because those
strings are handed to the model as fact.

## 53. Switched from Streamlit to Next.js for the frontend.

Streamlit was sufficient for the engine but had a low aesthetic ceiling. To maximize the Innovation (15%) and UI/UX (10%) scores, we moved to Next.js. This allows for smooth Framer Motion animations, custom SVG path rendering for the roadmap, and a professional "habit-forming" interface that Streamlit cannot replicate.

## 53. One path, shared by every page and saved

Each route held its own useState, so building a path in the co-pilot and clicking through to My path
showed an empty dashboard. There was no context, no store, nothing.

A small module level store now holds the one path and writes it to the browser, so it survives moving
between pages and a refresh. Reading happens after mount so the server and client first render agree.

## 54. All five reactions are on screen, not just finishing something

The interface could only send "completed". Too hard, too easy, already know this and not for me were
unreachable, which is most of the adaptation story we lead with.

They sit under the main action as a row of small buttons. Every one of them rebuilds the path, so the
roadmap visibly reacts.

## 55. The roadmap draws every milestone

It drew the first five on a hardcoded set of positions while the header counted all fourteen, so more
than half the plan was unreachable and the two numbers disagreed on screen.

Milestones now lay out on a serpentine grid that grows with the count, and the numbering pads properly,
which it did not past nine.

## 56. Feedback has to carry the whole profile back

The API rebuilt from the request it was given, so everything state.apply changed was thrown away except
the two lists. Already knowing a skill did nothing at all, and too hard blocked a course without ever
moving the level.

## 57. Relevance was never switched on in the API

path.build was called without it, so the strongest signal sat inert and the goal text we collected was
never used. Wired now, and the same role gives different courses for different goals.

## 58. A course must fit the learner, not just match the words

Ranking normalises relevance across the candidates for a skill, which makes the best one worth the whole
term however small the real gap is. A 0.09 edge became 1.00 against 0.00, worth 0.40, enough to send
someone into a 173 hour data science specialisation to learn Git instead of a 16 hour course on Git.

Weights could not express this, so it is a rule instead: a course longer than eight weeks of their time
is only offered when nothing shorter teaches the skill. That one line took a route from 81 weeks to 49.

## 59. Hand added catalog entries survive a rebuild

Two skills are not covered by the 400 most enrolled Coursera courses. Nothing in them mentions
backpropagation at all, and only one mentions Git. Both had real courses in our original seed catalog
and lost them when the scraped catalog replaced it.

Anything flagged as ours is now kept when the catalog is rebuilt, so those two carry real courses again.
We add real ones by hand, we do not invent them.

## 60. The engine being down should read like a sentence

fetch rejects rather than returning a response when nothing is listening, so the raw browser error
reached the screen as "Failed to fetch". Every call goes through one helper now and both failures say
something a person can act on.

## 61. Read the learner every turn, then answer or rebuild

The chat endpoint only re-read the profile when the explainer flagged a message as a change request.
It said no to "8 hours a week", so we answered a question they had not asked and left their weekly time
unset. With no hours the schedule divided by one and reported 138 weeks for four skills.

Extraction now runs on every message. If anything about them changed we rebuild and say so, otherwise
we answer their question. Whether the profile changed is a comparison we do ourselves rather than
something we ask the model to judge.

## 62. Never emit a profile we would reject

The interface sends our own profile back on the next turn. We returned weekly_hours as null before the
learner had said, then refused it, and the validation error surfaced as "[object Object]" because
FastAPI answers with a list of objects and JavaScript stringifies that.

The field is nullable now, missing hours is refused with a sentence, and error lists get joined into
readable text. Both directions are covered by tests that call the API rather than the functions.

## 63. A bare topic is a goal

"machine learning" produced no skills at all, so the assistant asked the same question forever. The
extraction prompt told it not to guess, and it read a two word answer as not stating anything.

Goals are now the stated exception: name any subject and we map it. Never guessing still applies to what
they already know, which is the part that would quietly corrupt a path.

A role named in the same turn still wins over loose skills, because the table covers the whole job
rather than the one or two ideas the model picked out.

## 64. The chat sends the conversation, not the last message

Answering "15" to "how many hours a week" did nothing, because the endpoint only ever passed the newest
message to extraction. On its own that is a number with no meaning, so the same question came back
again and again.

This was a decision we made early and then quietly lost when the interface was built. Extraction was
designed to re-read the whole conversation every turn, which is what makes short answers and later
corrections work without any special handling.

The interface now sends what has been said so far, capped at the last twelve turns. "deep learning",
then "5 hours", then "actually make it 20" goes from 108 weeks to 32 with no code for corrections.

## 65. We ask what they already know, but only after showing the path

Decision 27 said only two fields are required, goal and hours, so we never asked about anything else.
That is still right for getting someone to a path quickly, but it left the strongest lever untouched.
Known skills prune whole branches off the graph, so a learner who never volunteers them gets a route
that starts from nothing.

So the first path now comes back with one question attached, naming the skills it actually starts with:
"It starts with Version Control with Git, Calculus, Linear Algebra. Do you already know any of those?"

Asking after building rather than before means they see something first, and we can name their real
first steps instead of asking in the abstract. Answering it visibly collapses the roadmap, 16 steps to
14 and 35 weeks to 32 in our test, which is also the best thing this product does.

Level and style stay inferred. The too hard and too easy buttons already correct level from what
someone actually does, which beats asking them to rate themselves.

## 66. Nothing on screen pretends to work

The interface had eleven controls that did nothing when clicked: a search icon, a bell, a profile chip,
an upsell button, an arrow on a card, and every node on the roadmap. It also showed an eighteen day
streak and a weekly activity chart, both invented, on a product that stores nothing.

Anything that looks clickable now does something real, and anything that could not be made real is gone.

Roadmap nodes and milestone rows open the actual course. New focus clears the route and disables itself
when there is nothing to clear. The profile chip shows real completion. The sidebar card counts real
steps and real weeks left, one bar per phase, filled as phases finish. The activity chart is hours per
phase from the actual plan.

A fabricated streak is the kind of detail a judge notices, and it would put every real number next to it
in doubt.

## 67. The per module explanation is on screen

explain_module existed, was tested, and nothing ever called it. The one thing the brief asks for by name,
saying why a recommendation was made, was reachable only through a general question.

It has its own endpoint because it costs a model call, so the interface asks only when the step actually
changes, and the answer is stored against the step it describes so a stale one can never sit under the
wrong course.

## 68. Four dependencies removed

framer-motion and reactflow were never imported at all. clsx and tailwind-merge existed only for a helper
used by one dead component. Runtime dependencies went from eight to four.

## 69. Learners are anonymous, identified by an id the browser mints

A uuid made on first visit and sent as a header. No signup screen between a judge and the product,
which is worth more here than working across devices.

The honest limit: clear your browser storage and you are a new person. A shareable resume link carrying
the id would fix that, at the price of anyone with the link being you. Fine for this, not fine if it
ever held anything private.

## 70. We store state and the conversation, never the path

The path stays derived. It is already a pure function of state and catalog, takes microseconds to
rebuild, and storing it would mean every catalog rebuild quietly invalidates every saved plan.

The transcript is the one genuinely new thing. Without it someone comes back to their roadmap and an
empty chat, which reads as amnesia. We keep the last twelve turns, because it is context for the next
answer rather than an archive.

## 71. Saving happens inside the endpoints that already handle state

/chat, /path and /path/feedback all receive the whole state and return the new one, so each of them
saves on the way out. One line each, no separate save endpoint, and no way to change something without
it being written down.

## 72. The browser copy is a paint, the server is the truth

We keep the session in browser storage as well so a returning page is not blank while the server
answers. On arrival we read from the server and overwrite. Same reason the path is never stored: two
copies are fine as long as one of them is clearly in charge.

## 73. One conversation, not one per page

The co-pilot page and the dashboard each kept their own chat in component state, so the same learner
had two separate threads that could not see each other. The thread now lives in the session with the
path, which also means it survives a reload and comes back on another tab.

## 74. Each learner carries their own four weights

Not one set fitted from a crowd. Fitting four weights properly needs a few hundred events across many
people, and we will have a handful. A model fitted on forty clicks would be worse than the numbers we
picked by hand, and confidently so.

So the weights are per person, nudged by their own reactions, starting from our defaults. It needs no
dataset, it works from the first click, and it is visibly about them. We should not call it learning in
the statistical sense, because it is not. Saying that plainly is stronger than dressing it up.

## 75. Which signal a reaction blames

Too hard and too easy raise how much difficulty matters. Not for me raises how much the subject match
matters. Already knowing something moves nothing, because it changes the path rather than telling us
anything about how to rank it.

The one inference: "not for me" on a course far longer than a month of their time is read as being about
length, not subject. That is the only reaction that does not say why. Too hard already told us the
reason and we believe it, which is a correction from our first attempt where a long course marked too
hard was blamed on length.

Finishing something reinforces the signal that won that pick, at half a step. Rejecting a course is
strong evidence we ranked wrong, finishing one is weak evidence we ranked right.

## 76. Nudges are small, bounded and renormalised

A step of 0.04, every weight held between 0.05 and 0.60, and the four renormalised to sum to one after
every change.

Renormalising is the part that matters. Raising one weight has to lower the others or nothing changes in
the ranking, only the scale. It also keeps scores comparable between learners, so "closest match" means
the same thing for everyone. The bounds are the same reasoning as clamping level: three consistent
clicks are real, thirty are a mood.

## 77. A new goal resets what was about the goal

Change from data analyst to ML engineer and we keep what we learned about your appetite for difficulty
and for long courses, and reset the subject and style signals. Those were about the old goal.

## 78. The learner can see their own weights

Four bars on the dashboard, labelled in human words rather than our field names: goal match, difficulty,
how you learn, course length. Three "too hard" clicks visibly move difficulty from 25 to 31 percent.

This is the best answer we have to "how does it personalise", and it would have been a shame to compute
it and keep it to ourselves.

## 79. The explainer may not promise a change

Asked to shorten a path it replied "we'll trim total hours and drop the least essential module" and
trimmed nothing. Not a made up course, a made up action, which is worse because you cannot catch it by
looking at the plan.

Its prompt now forbids the first person about changes and forbids describing what the plan will become.
It describes what is. A test asserts those instructions are still in the prompt, because this is the
sentence someone will soften later without realising what it was for.

## 80. A change we cannot make is answered by us, not by the model

explain.ask has always returned an is_change_request flag and we stopped using it when the chat endpoint
was rewritten. Since we only reach the model when extraction changed nothing, a change request at that
point is by definition one we have no lever for.

So we answer those ourselves with arithmetic. No model call decides what to say about something we
cannot do.

## 81. The deadline gap is a sentence, not a label

feasible was a boolean painting two words, Stretch and This path needs more runway. Twelve weeks against
a four week deadline and thirteen against twelve both read the same, and we knew the exact gap the whole
time.

build now returns the total hours and how many hours a week the deadline would actually take. The card
reads "12 weeks against your 4 week deadline. About 58 hours a week would make it, rather than 20."

## 82. Our own replies have to be checkable too

After fixing the model we found the same fault in a string we wrote: setting an impossible deadline
answered "Updated your route from what you just told me", when the route had not changed at all and only
the flag had moved.

Replies now carry the numbers. "Updated: 2 steps over 4 weeks, 153 hours of study." If it did not change,
we say what it is and what would change it.

## 83. The levers are real, and the conversation now walks to them

Shortening a path is more hours a week, skills they already have, or a narrower goal. We refuse to add a
compress action, because hitting a date by dropping modules is fabricating a curriculum.

End to end, an impossible ask now lands somewhere true: asked for four weeks, told it needs 58 hours a
week, offered 40, route drops 12 weeks to 6, mentions knowing Python and statistics, and lands at 4 weeks
and feasible. Every number in that exchange is checkable against the plan.

## 84. One database connection needs a lock

FastAPI answers on a thread pool, and we shared one sqlite connection across those threads without
serialising. Under sixty concurrent requests it raised "bad parameter or other API misuse" six times.

SQLite serialises writes anyway and every call we make takes microseconds, so a lock costs nothing and
removes the whole class of bug. Sixty concurrent writers now, zero errors.

## 85. lru_cache does not stop two threads running the loader

Two first requests arriving together both entered the embedding model loader, and tqdm raised inside
it. It reached the browser as a 500 that looked like a CORS failure, which is what sent us looking in
the wrong place for a while.

The loader is behind a lock now, and the model, graph and catalog load at startup rather than on
whoever arrives first. The Docker image also downloads the model at build time, so a cold container
does not pay for it, and several requests cannot race on a download.

## 86. Refuse a goal we do not recognise

A goal of made up skill ids used to return 200 and an empty plan, which on screen looks the same as
never having given a goal. It is refused now.

Ids that no longer exist are dropped rather than fatal, because saved learners outlive catalog
rebuilds, and we only refuse when nothing they asked for is left.

## 87. Free text from a learner is bounded

goal_text had no limit, so a hundred thousand characters were embedded and written to the database.
Capped at two thousand, the same as a chat message.

## 88. Courses are chosen as a set, not one per skill

Picking the best course for each skill on its own ignored that one course often teaches several things
the learner needs. Measured across seven roles and three profiles, that left about 40 percent of the
study time redundant.

It is minimum cost set cover, solved greedily, where each step takes the best coverage per hour
multiplied by how well the course suits the learner. Median study hours went from 295 to 180 and median
weeks from 27 to 17, with prerequisite violations still zero and coverage still complete.

Greedy is within a log factor of optimal. We say that rather than claiming optimal.

## 89. Relevance is normalised across the whole gap, not per skill

Set cover has no per skill candidate list, so it forced a fix we needed anyway. Normalising within a
skill made the better of two candidates worth the entire relevance term however small the real
difference, which is what drowned out the other three signals.

## 90. We measure distance from optimal, not distance from another heuristic

Comparing our greedy answer to a different greedy answer proves nothing. We solve the linear relaxation
of the same set cover with scipy: fractional courses allowed, every skill covered, total hours
minimised. That can only be cheaper than the true integer optimum, so our hours over it is an honest
upper bound on how far from optimal we are.

Median 1.27 times the bound, and 1.04 to 1.11 on the larger plans where the relaxation is tight. The
worst case of 4.00 is a two skill plan where the bound is loose rather than the plan bad, since a tenth
of a course is not something a person can enrol in. Saying that is better than quoting the median alone.

## 91. Slot filling is scored by F1, because subset scoring was recall only

Set valued fields were checked by subset, so a model returning every skill in the taxonomy would have
scored a hundred percent. Precision is the half that matters, because an invented known skill silently
deletes steps from someone's plan.

## 92. Groundedness rather than a metric we invented

The share of explanations where every claim traces to the facts we supplied is the standard RAG measure,
usually judged by a second model. Ours is a deterministic proxy: every number in the text must appear in
the facts, and no phrase may promise an action we cannot take. Cheaper, reproducible, and unlike a model
judge it cannot hallucinate.

## 93. Catalog coverage is reported even though it is bad

Across every role and profile we recommend 26 distinct courses out of 366, so the effective catalog is a
fraction of what we loaded. Seven roles, and set cover concentrating on courses that cover several skills
at once.

Publishing a number that makes us look worse is the point of measuring. It is also the clearest argument
for the cheapest improvement we have: more roles.

## 94. Nine more roles, chosen from where the catalog actually is

Seven roles reached 29 of 72 skills, leaving half the catalog's teaching capacity findable only by
typing the right free text. ops.cloud alone had 64 courses and no role touching it.

The new roles were picked by course count rather than by what sounded good: software engineer, backend,
frontend, full stack, devops, security, data engineer, computer vision, game developer.

Unreachable skills went 43 to 24, fragile single course skills 17 to 12, and catalog coverage 7 to 12
percent. Coverage is still low, and the honest reason is that set cover deliberately concentrates on
courses that cover several skills at once.

## 95. Real courses for the skills backed by exactly one

Five skills on the core AI path had a single course behind them, so one "not for me" left the learner
with nothing. Added real named courses for backpropagation, sequence models, embeddings, fine tuning and
retrieval augmented generation, flagged as ours so a rebuild keeps them.

## 96. Fit raised to the fourth power, and we measured why

Set cover values coverage per hour, and that ratio varies far more than a fit score between about 0.4
and 0.9. The result was that the learner's own weights moved only 6 percent of picks, which makes the
personalisation we show them close to decoration.

Swept the exponent from 1 to 6 and measured all three things that matter at once:

    k=1   weights move 6%    1.22x bound   91h median
    k=4   weights move 22%   1.22x bound   80h median
    k=6   weights move 21%   1.22x bound   80h median

Four is the knee, and it is better on every axis at once rather than a trade. Past it, nothing improves.
This is the whole reason to have built the evals first: the exponent was not guessed.

## 97. A model we cannot reach is not a learner who said nothing

Extraction swallowed its failures and returned an empty profile. When the daily token budget ran out,
the assistant asked the same question forever and nothing on screen said why. The eval scored it as the
model getting every field wrong, which sent us hunting a prompt problem that did not exist.

It raises now, the chat says it could not reach the assistant and that nothing is lost, and the eval
reports that it could not run rather than printing a score it did not measure.

The lesson is the one we keep relearning: a silent failure is worse than a loud one, and it is worse
again when it corrupts the numbers you use to make decisions.

## 98. The real Groq limit is 200,000 tokens a day

Not the per minute cap we had been pacing against. A full eval run with the model half costs about 30k
and the labelling pipeline about 90k, so three eval runs and a rebuild will exhaust a day.

Worth planning around before demo day: do not run the model evals on the morning of.

## 99. Roles are proposed by the model and chosen by a person

scripts/propose_roles.py finds skills no role reaches that the catalog backs with three or more courses,
ranks them by course count, and asks for roles covering them. It prints each with how many unreachable
skills it would open up, writes them to a file, and stops. You delete what you disagree with and rerun
with --apply.

The ranking is what makes the review quick. Of five proposals, two opened three skills each and three
opened one, and those three were a language bolted onto a role we had, a job nobody is hired into, and
one already mostly covered.

We keep a person in this loop because a role is a claim about what a job requires. That is knowledge
about the world, not about our catalog, and clustering our own data would only tell us what Coursera
bundles together.

## 100. The review step has to actually review

The first version re-ran the proposal inside --apply, overwrote the file we had just edited, and applied
its fresh five instead of our chosen two. A human in the loop that silently discards the human.

--apply now reads the file and makes no model call at all.

## 101. Extraction measured clean once we scored each field properly

role 100 percent, weekly hours 100 percent, style 100 percent after telling the prompt how to infer it,
known skills precision and recall both 1.00, goal skills recall 1.00, groundedness 100 percent.

Style was 50 percent until we noticed we constrain skill ids and role names in the prompt and had never
said anything about how to read how someone likes to learn.
