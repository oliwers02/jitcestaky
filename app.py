"""MojeCestaky-Lite — cestovné príkazy podľa zákona č. 283/2002 Z. z. (2026)."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import db

st.set_page_config(page_title="MojeCestaky-Lite", page_icon="🚗", layout="wide")

db.init_db()

pages = st.navigation([
    st.Page("pages/prehlad.py", title="Prehľad", icon="📊", default=True),
    st.Page("pages/cesty.py", title="Cesty (jednodňové)", icon="🚗"),
    st.Page("pages/viacdnove.py", title="Viacdňové cesty", icon="🧳"),
    st.Page("pages/generator.py", title="Generátor ciest", icon="⚙️"),
    st.Page("pages/vozidla.py", title="Vozidlá", icon="🚙"),
    st.Page("pages/zamestnanci.py", title="Zamestnanci", icon="👤"),
    st.Page("pages/miesta.py", title="Miesta", icon="📍"),
    st.Page("pages/export.py", title="Export", icon="📤"),
    st.Page("pages/reporty.py", title="Reporty", icon="📈"),
    st.Page("pages/nastavenia.py", title="Nastavenia", icon="🛠️"),
])

with st.sidebar:
    st.caption(
        "⚠️ **Streamlit Cloud (free):** úložisko je dočasné — dáta sa môžu "
        "pri reštarte appky resetovať. Pravidelne si robte zálohu cez "
        "**Nastavenia → Záloha dát (JSON)**."
    )

pages.run()
