"""Downloads the Coursera CSV from Hugging Face. No auth, no extra libraries."""

import urllib.request
from pathlib import Path

URL = "https://huggingface.co/datasets/azrai99/coursera-course-dataset/resolve/main/coursera_course_2024.csv"
OUT = Path(__file__).resolve().parents[1] / "data/raw/coursera.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)
req = urllib.request.Request(URL, headers={"User-Agent": "curl/8"})
OUT.write_bytes(urllib.request.urlopen(req, timeout=120).read())
print(f"wrote {OUT.stat().st_size / 1e6:.1f} MB to {OUT}")
