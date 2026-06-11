"""Vozidlá — CRUD súkromných vozidiel."""
import pandas as pd
import streamlit as st

from core import calc, db, ui

st.title("🚙 Vozidlá (súkromné)")
st.caption("Evidujú sa výhradne súkromné vozidlá používané na pracovné cesty "
           "(§7 zákona č. 283/2002 Z. z.).")

vehs = db.fetch_all("vehicles", order="predvolene DESC, znacka")

if vehs:
    df = pd.DataFrame([{
        "ID": v["id"],
        "Typ": calc.TYP_VOZIDLA.get(v["typ"], v["typ"]),
        "Značka": v["znacka"], "Model": v["model"], "Rok": v["rok_vyroby"],
        "Objem (cm³)": v["objem_motora_cm3"],
        "Palivo": calc.TYP_PALIVA.get(v["typ_paliva"], v["typ_paliva"]),
        "Spotreba (l/100 km)": v["spotreba_l_100km"],
        "ŠPZ": v["spz"],
        "Predvolené": "⭐" if v["predvolene"] else "",
    } for v in vehs])
    st.dataframe(df, hide_index=True, width="stretch")

st.subheader("Pridať / upraviť vozidlo")
vyber = st.selectbox("Vozidlo", [None] + vehs,
                     format_func=lambda v: "➕ Nové vozidlo" if v is None
                     else ui.vozidlo_label(v))
e = vyber or {}

c1, c2, c3 = st.columns(3)
with c1:
    typ = st.selectbox("Typ", list(calc.TYP_VOZIDLA),
                       index=list(calc.TYP_VOZIDLA).index(e.get("typ", "osobne_auto")),
                       format_func=calc.TYP_VOZIDLA.get)
    znacka = st.text_input("Značka", e.get("znacka") or "")
    model = st.text_input("Model", e.get("model") or "")
with c2:
    rok = st.number_input("Rok výroby", 1980, 2030, int(e.get("rok_vyroby") or 2020))
    objem = st.number_input("Objem motora (cm³)", 0, 10000,
                            int(e.get("objem_motora_cm3") or 1500), 50)
    palivo = st.selectbox("Typ paliva", list(calc.TYP_PALIVA),
                          index=list(calc.TYP_PALIVA).index(e.get("typ_paliva", "benzin")),
                          format_func=calc.TYP_PALIVA.get)
with c3:
    spotreba = st.number_input(
        "Spotreba podľa TP (l/100 km; kWh pri elektrine, kg pri CNG)",
        0.0, 50.0, float(e.get("spotreba_l_100km") or 6.5), 0.1)
    spz = st.text_input("ŠPZ", e.get("spz") or "")
    predvolene = st.checkbox("Predvolené vozidlo ⭐", bool(e.get("predvolene")))

b1, b2 = st.columns(2)
if b1.button("💾 Uložiť vozidlo", type="primary", width="stretch"):
    data = {"typ": typ, "znacka": znacka, "model": model, "rok_vyroby": rok,
            "objem_motora_cm3": objem, "typ_paliva": palivo,
            "spotreba_l_100km": spotreba, "spz": spz,
            "predvolene": int(predvolene)}
    if predvolene:  # iba jedno predvolené vozidlo
        for v in vehs:
            if v["predvolene"]:
                db.update("vehicles", v["id"], {"predvolene": 0})
    if vyber:
        db.update("vehicles", vyber["id"], data)
        st.success("Vozidlo aktualizované.")
    else:
        db.insert("vehicles", data)
        st.success("Vozidlo pridané.")
    st.rerun()

if vyber and b2.button("🗑️ Zmazať vozidlo", type="secondary", width="stretch"):
    db.delete("vehicles", vyber["id"])
    st.success("Vozidlo zmazané.")
    st.rerun()
