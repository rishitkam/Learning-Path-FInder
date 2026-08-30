"""Cleans the raw Coursera rows and keeps the tech and data ones. Writes data/raw/filtered.json."""

import ast, hashlib, json, re
from pathlib import Path

import numpy as np
import pandas as pd
from model2vec import StaticModel

ROOT = Path(__file__).resolve().parents[1]
KEEP = 450
# A course is ours if it looks more like one of these than like one of those. A single mean anchor
# was too blunt: it scored a spreadsheets course the same as a Python one.
POS = ["python programming", "software engineering and code", "data analysis with statistics",
       "machine learning models", "deep learning neural networks", "sql and databases",
       "cloud computing and devops", "natural language processing and language models",
       "data visualization and dashboards", "computer science algorithms"]
NEG = ["business management and leadership", "marketing and sales", "finance and accounting",
       "healthcare and medicine", "design and user experience", "careers and workplace skills",
       "spreadsheets and office software", "law policy and ethics", "teaching and education",
       "learning a foreign language, spanish chinese english grammar",
       "physics optics lasers and photonics", "electrical and mechanical engineering hardware",
       "biology chemistry and laboratory science", "geography maps and spatial planning",
       "solar energy batteries and power systems", "robotics and mechatronics",
       "supply chain manufacturing and operations"]
MARGIN = 0.05
LEVELS = {"Beginner level": 1, "Intermediate level": 3, "Advanced level": 5}


def hours(schedule):
    """Most rows state the total outright: '7 hours to complete (3 weeks at 2 hours a week)'. Use it.
    Multiplying the span by the weekly rate instead is wrong for about half of them, because Coursera
    rounds the weekly figure down. Only the '3 months (at 5 hours a week)' shape has no stated total."""
    if not isinstance(schedule, str):
        return None
    stated = re.match(r"\s*(\d+)\s*hours? to complete", schedule)
    if stated:
        return int(stated.group(1))
    span = re.search(r"(\d+)\s*(month|week)", schedule)
    per = re.search(r"(\d+)\s*hours? a week", schedule)
    if not span or not per:
        return None
    weeks = int(span.group(1)) * (4.33 if span.group(2) == "month" else 1)
    return round(weeks * int(per.group(1)))


def tags(raw):
    try:
        return sorted({t.strip() for t in ast.literal_eval(raw) if t.strip()})
    except Exception:
        return []


def main():
    df = pd.read_csv(ROOT / "data/raw/coursera.csv")
    df = df[df.Description.notna() & df.Level.notna()]
    df["hours"] = df.Schedule.map(hours)
    df = df[df.hours.between(4, 200)]                     # drop degrees and stubs, keep real courses
    df["tags"] = df.Skills.fillna("[]").map(tags)
    df = df[df.tags.map(len) > 0]
    df["enrolled_n"] = pd.to_numeric(df.enrolled.astype(str).str.replace(",", ""), errors="coerce").fillna(0)
    # Ids hash the title, and several universities publish courses under identical titles. Keep the most
    # enrolled of each so an id always means one course.
    df = df.sort_values("enrolled_n", ascending=False).drop_duplicates("title")

    model = StaticModel.from_pretrained("minishlab/potion-base-8M")
    text = (df.title + ". " + df.tags.map(", ".join) + ". " + df.Description.str.slice(0, 400)).tolist()
    norm = lambda v: v / np.linalg.norm(v, axis=-1, keepdims=True)
    vecs = norm(model.encode(text, show_progress_bar=False))
    df["domain"] = (vecs @ norm(model.encode(POS)).T).max(1) - (vecs @ norm(model.encode(NEG)).T).max(1)

    kept = df[df.domain > MARGIN].sort_values("enrolled_n", ascending=False).head(KEEP)

    # Id comes from the title, not the row number, so refiltering never invalidates existing labels.
    cid = lambda t: "cs." + hashlib.sha1(t.encode()).hexdigest()[:8]
    out = [{"id": cid(r.title), "title": r.title, "provider": r.Organization, "url": r.URL,
            "hours": int(r.hours), "level": LEVELS[r.Level], "kind": "course",
            "tags": r.tags, "description": " ".join(str(r.Description).split())[:600],
            "enrolled": int(r.enrolled_n)}
           for r in kept.itertuples()]

    (ROOT / "data/raw/filtered.json").write_text(json.dumps(out, indent=1))
    print(f"{len(df)} usable -> kept {len(out)}  (domain score {kept.domain.min():.2f} to {kept.domain.max():.2f})")
    print("levels:", kept.Level.value_counts().to_dict())
    print("hours: median", int(kept.hours.median()), "range", int(kept.hours.min()), "to", int(kept.hours.max()))
    for r in out[:5]:
        print(f"  {r['enrolled']:>9,}  L{r['level']} {r['hours']:>3}h  {r['title'][:58]}")

if __name__ == "__main__":
    main()
