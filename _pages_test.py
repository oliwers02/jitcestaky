"""Render-test všetkých stránok cez streamlit.testing.AppTest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from streamlit.testing.v1 import AppTest  # noqa: E402

from core import db  # noqa: E402

db.init_db()
db.seed_sample_data()

PAGES = ["prehlad", "cesty", "viacdnove", "generator", "vozidla",
         "zamestnanci", "miesta", "export", "reporty", "nastavenia"]

chyby = 0
for p in PAGES:
    at = AppTest.from_file(f"pages/{p}.py", default_timeout=30)
    at.run()
    if at.exception:
        chyby += 1
        print(f"CHYBA {p}: {at.exception[0].value}")
        print(at.exception[0].stack_trace[-1] if at.exception[0].stack_trace else "")
    else:
        print(f"OK {p}")

sys.exit(1 if chyby else 0)
