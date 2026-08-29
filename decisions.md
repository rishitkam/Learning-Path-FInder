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
