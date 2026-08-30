"""Labels courses with what they teach and assume, growing the taxonomy as it goes.

Each batch sees every skill named so far, so the model reuses ids instead of coining synonyms.
Easiest courses first, so foundations exist before advanced courses point at them.
Results are cached per batch, so a rate limit costs one batch and not the whole run.
"""

import json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile import call

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/raw/labels.json"
# Qwen, not either gpt-oss. 120b runs out of free tier budget long before 400 courses are done.
# 20b never proposes a new skill, so it crams every course into the seed 29 and mislabels most of them.
# Qwen readily names new skills, which is the whole point of this pass.
MODEL, BATCH = "qwen/qwen3.8-27b", 8
# The free tier allows 8000 tokens a minute per key. We rotate across keys on a refusal, so the pace
# can be brisker than the 16 seconds a single key needed.
MAX_OUT, DESC = 1500, 150
# A batch costs about 1800 tokens, so four a minute is the most the budget allows. Pacing
# deterministically is more reliable than firing fast and leaning on the retries.
PACE = 6

TOOL = {"type": "function", "function": {"name": "label", "parameters": {"type": "object", "properties": {
    "new_skills": {"type": "array", "description": "Skills you had to invent because none of the existing ids fit.",
        "items": {"type": "object", "required": ["id", "name"], "properties": {
            "id": {"type": "string", "description": "lowercase, dotted, like nlp.embeddings"},
            "name": {"type": "string"}}}},
    "courses": {"type": "array", "items": {"type": "object",
        "required": ["course_id", "relevant", "teaches", "assumes"],
        "properties": {"course_id": {"type": "string"},
                       "relevant": {"type": "boolean", "description":
                           "False if the course is not about software, data, or AI."},
                       "teaches": {"type": "array", "items": {"type": "string"}},
                       "assumes": {"type": "array", "items": {"type": "string"}}}}}},
    "required": ["new_skills", "courses"]}}}

SYS = """You label online courses against a skill taxonomy.

For each course give the skill ids it TEACHES and the ids it ASSUMES the learner already has.
Reuse an existing id whenever one fits, even loosely. Only invent a new skill when nothing fits,
and then declare it in new_skills. Keep ids lowercase and dotted, like ml.supervised.

Two to four teaches per course. Assumes should be genuine prerequisites, not related topics.
Never list the same id in both teaches and assumes for one course.

In scope: software and programming, data, AI and machine learning, cloud, devops, security,
networking, databases, and IT infrastructure.

Set relevant to false only for things clearly outside that: spoken languages, video and graphic design,
CAD, physics, biology, medicine, economics, business process work. Do not invent skills for those."""


def run(courses, taxonomy):
    # Ids only, no names. The ids read well enough on their own and this halves the prompt.
    listing = ", ".join(sorted(taxonomy))
    body = "\n\n".join(f"course_id: {c['id']}\ntitle: {c['title']}\nlevel: {c['level']}\n"
                       f"tags: {', '.join(c['tags'][:6])}\nabout: {c['description'][:DESC]}" for c in courses)
    for attempt in range(5):
        try:
            r = call(
                model=MODEL, temperature=0, max_tokens=MAX_OUT, reasoning_effort="low", tools=[TOOL],
                tool_choice={"type": "function", "function": {"name": "label"}},
                messages=[{"role": "system", "content": SYS},
                          {"role": "user", "content": f"EXISTING SKILLS:\n{listing}\n\nCOURSES:\n{body}"}])
            return json.loads(r.choices[0].message.tool_calls[0].function.arguments)
        except Exception as e:
            m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(e))
            wait = (int(m.group(1) or 0) * 60 + float(m.group(2)) + 3) if m else 30
            print(f"\n  rate limited, waiting {wait:.0f}s", flush=True)
            if attempt == 4 or "rate" not in type(e).__name__.lower() + str(e).lower():
                raise
            time.sleep(wait)


def clean(teaches, assumes, taxonomy):
    """The model puts a skill in both lists about one course in eight, which would be a self loop
    and therefore a cycle. A course listing a skill in both is usually gating on it rather than being
    the place to learn it, so it comes out of teaches. When every skill it teaches is also assumed we
    take it out of assumes instead, since an empty teaches list would drop the course entirely."""
    t = [s for s in dict.fromkeys(teaches) if s in taxonomy]
    a = [s for s in dict.fromkeys(assumes) if s in taxonomy]
    both = set(t) & set(a)
    if both:
        if len(t) > len(both):
            t = [s for s in t if s not in both]
        else:
            a = [s for s in a if s not in both]
    return t, a


def main(limit=None):
    courses = json.loads((ROOT / "data/raw/filtered.json").read_text())
    courses.sort(key=lambda c: (c["level"], c["hours"]))
    taxonomy = {k: v["name"] for k, v in json.loads((ROOT / "data/skills.json").read_text()).items()}
    done = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    taxonomy.update(done.get("taxonomy", {}))
    labels = done.get("labels", {})

    batches = [courses[i:i + BATCH] for i in range(0, len(courses), BATCH)][:limit]
    for n, batch in enumerate(batches, 1):
        if all(c["id"] in labels for c in batch):
            continue
        try:
            out = run(batch, taxonomy)
        except Exception as e:
            print(f"\nbatch {n} failed: {type(e).__name__}"); continue
        for s in out.get("new_skills", []):
            if s["id"] not in taxonomy:
                taxonomy[s["id"]] = s["name"]
        for c in out.get("courses", []):
            if c["course_id"] in {b["id"] for b in batch} and c.get("relevant", True):
                t, a = clean(c["teaches"], c["assumes"], taxonomy)
                if t:
                    labels[c["course_id"]] = {"teaches": t, "assumes": a}
        CACHE.write_text(json.dumps({"taxonomy": taxonomy, "labels": labels}, indent=1))
        print(f"\rbatch {n}/{len(batches)}  taxonomy {len(taxonomy)}  labelled {len(labels)}", end="", flush=True)
        time.sleep(PACE)
    print()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
