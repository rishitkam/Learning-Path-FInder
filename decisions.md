# Decisions

A running record of every choice we made, what else we could have done, and why we went the way we did.
Newest entries go at the bottom. 

---

## 1. The core idea: the AI does not write the curriculum

The obvious build is "send the goal to an LLM, print whatever roadmap it writes back". We did not do that.

The problem with it: the model invents course names that do not exist, gives a different answer every
time you ask, and cannot promise that linear algebra comes before backpropagation. None of that is
fixable with better prompting.

What we do instead: the learning path comes out of a skill graph plus a real course catalog. The LLM
sits only at the edges. It reads the human in (turning what they typed into a structured profile) and
it writes the explanation out. It never picks or orders the content.

Trade off: we have to build and maintain a skill graph, which is real work. What we get is a system that
gives the same answer twice, cannot invent a course, and can prove its ordering is correct.

## 2. Python, not JavaScript

We first sketched this in JavaScript because the deliverables are mostly a web app. We switched to Python.

Two reasons. The honest one is that the team writes Python and cannot defend a language it does not know
on pitch day. The technical one is that this is a retrieval and graph problem, and every library we want
lives in Python: networkx for the graph, sentence transformers for embeddings, scikit learn if we later
want to learn the ranking weights instead of hard coding them.

Cost of the switch: the interface will be Streamlit, which looks plainer than a custom React app. User
experience is 10 percent of the score so we accept the small hit and spend the time on the engine.

## 3. Streamlit for the interface

Alternatives were FastAPI with a React frontend (two services, two deploys, and JavaScript again) or
FastAPI with plain HTML templates (more control, more work).

Streamlit gives us chat, charts and a dashboard in one Python file and deploys free, which covers the
"application access" deliverable in minutes instead of hours. If it ever becomes the bottleneck we can
move to FastAPI with HTML templates without touching any of the logic, because none of the logic knows
the interface exists.

## 4. Groq for the model, embeddings run locally

We are on the Groq free tier. It is fast, which matters because we re read the learner profile on every
chat turn, and its API follows the OpenAI shape so the code is standard.

Two things it changes. Groq has no embeddings endpoint, so we run a small embedding model locally with
sentence transformers and bake the course vectors into a file ahead of time. That also means embeddings
cost nothing and work offline. And the free tier limits requests per minute rather than total spend, so
we cache what we can and keep a prepared profile ready in case the demo hits a limit on stage.

## 5. Skills and courses are two separate things

A skill is a unit of knowledge. A course is one way to get that skill. We keep them in separate files.

Why it matters: when a learner says a course is too hard or boring, we swap the course and the shape of
the path does not move. If we had merged the two, every swap would rebuild the whole plan.

## 6. Prerequisites live on the skill, not on the course

Three courses can teach the same skill. If each one carried its own prerequisite list they would drift
apart and contradict each other. One list per skill means one source of truth.

## 7. Depth is calculated, never typed in by hand

Each skill has a depth, meaning the longest chain of prerequisites sitting behind it. We work it out from
the graph itself rather than writing a level number into the file.

Hand written levels always end up disagreeing with the actual prerequisites once the file grows. A
calculated depth cannot disagree with the edges, because it is made from them.

## 8. The graph checks itself when the app starts

On load we confirm every prerequisite points at a skill that actually exists and that there are no
circular prerequisites. If either fails the app refuses to start.

A single typo in a skill id would otherwise produce a quietly wrong path that still looks fine. Five
lines of checking at startup is the cheapest reliability in the whole project.

## 9. Knowing a skill means knowing what it was built on

If a learner says they know transformers, we do not also ask them to tick backpropagation, neural
networks, supervised learning and Python. We walk the graph backwards and mark all of it as known.

This is one line of code and it is the single biggest reason the tool feels like it understood you. It
is also what makes two people with the same goal get genuinely different paths.

## 10. The order is deterministic, not just correct

There are usually many valid orders for the same set of skills. A plain topological sort returns any one
of them, which means the same learner could get a different looking path on a refresh.

We break ties on depth first and then on the skill id, so the same profile always produces exactly the
same path. Being able to say "this is reproducible" out loud is worth more than the two extra words it
took to write.

## 11. Phases come from the graph, not from a prompt

Skills that sit at the same depth have no prerequisite connecting them, which means by definition they
can be learned in parallel. So we group by depth and call each group a phase. A phase is therefore a
mathematical statement about the graph, not a cosmetic heading someone invented.

Known issue we are leaving for later: on a deep narrow graph this makes a lot of phases with one skill
each. Merging small phases is a scheduling concern, so it belongs to the path builder that knows how many
hours a week the learner has, not to the graph.

## 12. Goals resolve through a role table first, the model second

The learner types "I want to be a GenAI engineer". Something has to turn that into skill ids.

We keep a small file mapping common roles to their target skills. If the goal matches a known role we use
it: instant, free, and always valid. If it does not match, the model maps the goal onto skill ids instead,
picking only from our fixed list.

The lookup table lives next to the graph so its ids get checked at startup like everything else, but the
choice of which route to take sits outside the graph, in the profile layer. The graph only ever receives
finished skill ids, which keeps it a pure function we can test without mocking anything.


