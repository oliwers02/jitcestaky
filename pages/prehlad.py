"""Prehľad (Dashboard) — KPI, graf za 6 mesiacov, posledné cesty."""
import datetime as dt

import pandas as pd
import streamlit as st

from core import calc, db, ui

st.title("📊 Prehľad")

dnes = dt.date.today()
zac_mesiaca = dnes.replace(day=1).isoformat()

trips = db.fetch_all("trips", order="datum DESC, id DESC")
bts = db.fetch_all("business_trips", order="datum_zaciatku DESC")

mes_trips = [t for t in trips if str(t["datum"]) >= zac_mesiaca]
mes_km = sum(float(t["vzdialenost_km"] or 0) for t in mes_trips)
mes_nahrady = sum(float(t["nahrada_spolu"] or 0) for t in mes_trips)
priemer = mes_nahrady / len(mes_trips) if mes_trips else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Cesty tento mesiac", len(mes_trips))
c2.metric("Najazdené km (mesiac)", f"{mes_km:,.0f} km".replace(",", " "))
c3.metric("Náhrady tento mesiac", ui.eur(mes_nahrady))
c4.metric("Priemerná náhrada / cesta", ui.eur(priemer))

st.divider()

# graf za posledných 6 mesiacov
st.subheader("Náhrady a kilometre za posledných 6 mesiacov")
mesiace = []
m = dnes.replace(day=1)
for _ in range(6):
    mesiace.append(m)
    m = (m - dt.timedelta(days=1)).replace(day=1)
mesiace.reverse()

riadky = []
for m in mesiace:
    prefix = m.strftime("%Y-%m")
    mt = [t for t in trips if str(t["datum"]).startswith(prefix)]
    riadky.append({
        "Mesiac": f"{ui.MESIACE[m.month - 1][:3]} {m.year}",
        "Náhrady (€)": round(sum(float(t["nahrada_spolu"] or 0) for t in mt), 2),
        "Kilometre": round(sum(float(t["vzdialenost_km"] or 0) for t in mt), 1),
    })
df6 = pd.DataFrame(riadky).set_index("Mesiac")
g1, g2 = st.columns(2)
g1.bar_chart(df6["Náhrady (€)"], color="#1f77b4")
g2.bar_chart(df6["Kilometre"], color="#2ca02c")

st.divider()
l1, l2 = st.columns(2)

with l1:
    st.subheader("Posledné jednodňové cesty")
    if trips:
        emps = {e["id"]: e["meno_priezvisko"] for e in db.fetch_all("employees")}
        df = pd.DataFrame([{
            "Dátum": t["datum"],
            "Cieľ": t["ciel_cesty"],
            "Zamestnanec": emps.get(t["employee_id"], "—"),
            "Km": t["vzdialenost_km"],
            "Spolu (€)": t["nahrada_spolu"],
        } for t in trips[:8]])
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.info("Zatiaľ žiadne cesty — pridajte prvú na stránke **Cesty**.")

with l2:
    st.subheader("Viacdňové cesty")
    if bts:
        df = pd.DataFrame([{
            "Názov": b["nazov"],
            "Od": b["datum_zaciatku"],
            "Do": b["datum_konca"],
            "Krajina": b["cielova_krajina"],
            "Status": calc.STATUSY.get(b["status"], b["status"]),
        } for b in bts[:8]])
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.info("Žiadne viacdňové cesty.")
