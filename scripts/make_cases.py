"""Builds extraction test cases by composing known labels into messy sentences.

The old set was fifteen utterances written by hand, after the system existed, by the person who built
it, and then the prompt was tuned until they passed. Everything scored perfectly, which measured the
fixture rather than the extractor.

These are synthesised the other way round: start from a label we choose, render it as language a person
might actually type, and the expectation is correct by construction. Phrasings include typos, filler,
slang and irrelevant chatter, because those are what real learners send.

    python3 scripts/make_cases.py       writes data/cases.json
"""

import json, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graph import load

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260830

ROLE_WORDS = {"data-analyst": ["data analyst", "a data analyst"],
              "machine-learning-engineer": ["ML engineer", "machine learning engineer", "an ml eng"],
              "data-scientist": ["data scientist"], "nlp-engineer": ["NLP engineer"],
              "devops-engineer": ["devops engineer", "a devops person"],
              "security-engineer": ["security engineer"], "data-engineer": ["data engineer"],
              "frontend-developer": ["frontend dev", "front end developer"],
              "backend-developer": ["backend developer", "backend dev"],
              "game-developer": ["game developer", "game dev"]}
GOAL_FRAMES = ["i want to be a {}", "trying to become a {}", "my goal is to be a {}",
               "i wanna get into being a {}", "looking to switch careers to {}", "{} is the target"]
TOPICS = {"machine learning": ["ml.concepts"], "deep learning": ["dl.neuralnets"],
          "data visualisation": ["data.viz"], "sql": ["data.sql"], "docker": ["ops.docker"],
          "web development": ["web.frontend"], "cyber security": ["sec.fundamentals"]}
TOPIC_FRAMES = ["{}", "i want to learn {}", "interested in {}", "can you teach me {}", "{} pls"]
SKILL_WORDS = {"prog.python": ["python", "Python"], "data.pandas": ["pandas"], "data.sql": ["sql", "SQL"],
               "math.stats": ["statistics", "stats"], "ml.supervised": ["supervised learning"],
               "prog.oop": ["object oriented programming", "OOP"], "eng.git": ["git"],
               "data.viz": ["data visualisation"], "prog.javascript": ["javascript", "JS"]}
KNOWN_FRAMES = ["i already know {}", "i know {} pretty well", "ive done {} before",
                "comfortable with {}", "i have experience with {}", "already did {}"]
HOUR_FRAMES = ["{} hours a week", "{}h/week", "about {} hours weekly", "i can do {} a week",
               "{} hrs per week", "roughly {} hours each week", "maybe {}h a week"]
STYLE_WORDS = {"project first": ["i learn best by building things", "i prefer hands on projects",
                                 "i like building stuff rather than watching lectures"],
               "theory first": ["i prefer theory first", "i like lectures and fundamentals",
                                "i want to understand the theory before coding"]}
NOISE = ["", "", "", " thanks!", " bro", " umm", " ok so", " hey", " pls help", " :)"]


def main():
    g = load()
    random.seed(SEED)
    cases = []

    def add(said, expect):
        cases.append({"said": "learner: " + said.strip(), "expect": expect})

    for role, words in ROLE_WORDS.items():
        for frame in GOAL_FRAMES:
            add(frame.format(random.choice(words)) + random.choice(NOISE), {"role": role})
    for topic, skills in TOPICS.items():
        for frame in TOPIC_FRAMES:
            add(frame.format(topic) + random.choice(NOISE), {"goal_skills": skills})
    for skill, words in SKILL_WORDS.items():
        for frame in KNOWN_FRAMES:
            add(frame.format(random.choice(words)) + random.choice(NOISE), {"known_skills": [skill]})
    for hours in (4, 5, 8, 10, 12, 15, 20, 25):
        for frame in HOUR_FRAMES:
            add(frame.format(hours) + random.choice(NOISE), {"weekly_hours": hours})
    for style, phrases in STYLE_WORDS.items():
        for phrase in phrases:
            add(phrase + random.choice(NOISE), {"style": style})

    # Combinations, which is where a real message lives.
    for _ in range(40):
        role = random.choice(list(ROLE_WORDS))
        skill = random.choice(list(SKILL_WORDS))
        hours = random.choice([4, 6, 10, 12, 20])
        add(f"{random.choice(GOAL_FRAMES).format(random.choice(ROLE_WORDS[role]))}, "
            f"{random.choice(KNOWN_FRAMES).format(random.choice(SKILL_WORDS[skill]))}, "
            f"{random.choice(HOUR_FRAMES).format(hours)}" + random.choice(NOISE),
            {"role": role, "known_skills": [skill], "weekly_hours": hours})

    # Cases where the right answer is to say nothing.
    for said in ["hi", "hello?", "what is this", "idk", "just looking around", "ok", "thanks",
                 "can you help me", "how does this work", "test"]:
        add(said, {"goal_skills": [], "known_skills": [], "weekly_hours": None})

    # Multi turn, where the answer only means something next to the question.
    for hours in (6, 9, 14, 18):
        cases.append({"said": "assistant: How many hours a week can you realistically give this?\n"
                              f"learner: {hours}", "expect": {"weekly_hours": hours}})
    for role in ["data-analyst", "devops-engineer"]:
        cases.append({"said": "assistant: What do you want to be able to do at the end?\n"
                              f"learner: {random.choice(ROLE_WORDS[role])}", "expect": {"role": role}})
    # Corrections, where the later statement has to win.
    for first, second in [(20, 5), (10, 30), (8, 12)]:
        cases.append({"said": f"learner: {first} hours a week\nlearner: actually make it {second}",
                      "expect": {"weekly_hours": second}})

    random.shuffle(cases)
    half = len(cases) // 2
    (ROOT / "data/cases.json").write_text(json.dumps(
        {"dev": cases[:half], "test": cases[half:]}, indent=1))
    print(f"  {len(cases)} cases: {half} dev, {len(cases) - half} held out")
    print("  tune against dev, report test, and never look at test while changing prompts")


if __name__ == "__main__":
    main()
