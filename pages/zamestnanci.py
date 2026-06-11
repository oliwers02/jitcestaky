"""Zamestnanci — CRUD."""
import pandas as pd
import streamlit as st

from core import db

st.title("👤 Zamestnanci")

emps = db.fetch_all("employees", order="meno_priezvisko")

if emps:
    df = pd.DataFrame([{
        "ID": e["id"], "Meno a priezvisko": e["meno_priezvisko"],
        "Pozícia": e["pozicia"],
        "Adresa bydliska (štart)": e["adresa_bydliska"],
        "E-mail": e["email"], "Telefón": e["telefon"],
        "Aktívny": "✅" if e["aktivny"] else "—",
    } for e in emps])
    st.dataframe(df, hide_index=True, width="stretch")

st.subheader("Pridať / upraviť zamestnanca")
vyber = st.selectbox("Zamestnanec", [None] + emps,
                     format_func=lambda e: "➕ Nový zamestnanec" if e is None
                     else e["meno_priezvisko"])
e = vyber or {}

c1, c2 = st.columns(2)
with c1:
    meno = st.text_input("Meno a priezvisko *", e.get("meno_priezvisko") or "")
    pozicia = st.text_input("Pozícia", e.get("pozicia") or "")
    adresa = st.text_input("Adresa bydliska (štartovací bod ciest)",
                           e.get("adresa_bydliska") or "")
with c2:
    email = st.text_input("E-mail", e.get("email") or "")
    telefon = st.text_input("Telefón", e.get("telefon") or "")
    aktivny = st.checkbox("Aktívny", bool(e.get("aktivny", 1)))

b1, b2 = st.columns(2)
if b1.button("💾 Uložiť", type="primary", width="stretch"):
    if not meno.strip():
        st.error("Meno a priezvisko je povinné.")
    else:
        data = {"meno_priezvisko": meno, "pozicia": pozicia,
                "adresa_bydliska": adresa, "email": email,
                "telefon": telefon, "aktivny": int(aktivny)}
        if vyber:
            db.update("employees", vyber["id"], data)
            st.success("Zamestnanec aktualizovaný.")
        else:
            db.insert("employees", data)
            st.success("Zamestnanec pridaný.")
        st.rerun()

if vyber and b2.button("🗑️ Zmazať", type="secondary", width="stretch"):
    db.delete("employees", vyber["id"])
    st.success("Zamestnanec zmazaný.")
    st.rerun()
