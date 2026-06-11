"""Miesta — obľúbené lokality s voliteľnými súradnicami (haversine odhad)."""
import pandas as pd
import streamlit as st

from core import calc, db

st.title("📍 Obľúbené miesta")
st.caption("Súradnice sú voliteľné — umožňujú offline odhad vzdialenosti "
           "vzdušnou čiarou (bez plateného API).")

miesta = db.fetch_all("locations", order="nazov")

if miesta:
    df = pd.DataFrame([{
        "ID": m["id"], "Názov": m["nazov"], "Adresa": m["adresa"],
        "Lat": m["lat"], "Lon": m["lon"],
    } for m in miesta])
    st.dataframe(df, hide_index=True, width="stretch")

st.subheader("Pridať / upraviť miesto")
vyber = st.selectbox("Miesto", [None] + miesta,
                     format_func=lambda m: "➕ Nové miesto" if m is None else m["nazov"])
e = vyber or {}

c1, c2 = st.columns(2)
with c1:
    nazov = st.text_input("Názov *", e.get("nazov") or "")
    adresa = st.text_input("Adresa", e.get("adresa") or "")
with c2:
    lat = st.number_input("Zemepisná šírka (lat)", -90.0, 90.0,
                          float(e.get("lat") or 48.7), format="%.5f")
    lon = st.number_input("Zemepisná dĺžka (lon)", -180.0, 180.0,
                          float(e.get("lon") or 19.2), format="%.5f")
    pouzit_surad = st.checkbox("Uložiť súradnice", bool(e.get("lat")))

b1, b2 = st.columns(2)
if b1.button("💾 Uložiť miesto", type="primary", width="stretch"):
    if not nazov.strip():
        st.error("Názov je povinný.")
    else:
        data = {"nazov": nazov, "adresa": adresa,
                "lat": lat if pouzit_surad else None,
                "lon": lon if pouzit_surad else None}
        if vyber:
            db.update("locations", vyber["id"], data)
            st.success("Miesto aktualizované.")
        else:
            db.insert("locations", data)
            st.success("Miesto pridané.")
        st.rerun()

if vyber and b2.button("🗑️ Zmazať miesto", type="secondary", width="stretch"):
    db.delete("locations", vyber["id"])
    st.success("Miesto zmazané.")
    st.rerun()

so_surad = [m for m in miesta if m["lat"] and m["lon"]]
if len(so_surad) >= 2:
    st.subheader("📐 Vzdialenosť medzi miestami (vzdušnou čiarou)")
    c1, c2 = st.columns(2)
    ma = c1.selectbox("Z miesta", so_surad, format_func=lambda m: m["nazov"])
    mb = c2.selectbox("Do miesta", so_surad, format_func=lambda m: m["nazov"],
                      index=min(1, len(so_surad) - 1))
    if ma["id"] != mb["id"]:
        d = calc.haversine_km(ma["lat"], ma["lon"], mb["lat"], mb["lon"])
        st.metric(f"{ma['nazov']} → {mb['nazov']}",
                  f"{d} km (vzdušná) | tam a späť ≈ {2 * d:.0f} km")
        st.caption("Skutočná cestná vzdialenosť býva o 20 – 30 % dlhšia.")
