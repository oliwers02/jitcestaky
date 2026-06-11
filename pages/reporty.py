"""Reporty — ročné prehľady a štatistiky."""
import datetime as dt

import pandas as pd
import streamlit as st

from core import calc, db, ui

st.title("📈 Reporty")

rok = st.selectbox("Rok", list(range(dt.date.today().year, 2023, -1)))

trips = db.fetch_all("trips", "datum LIKE ?", (f"{rok}-%",), order="datum")
bts = db.fetch_all("business_trips", "datum_zaciatku LIKE ?", (f"{rok}-%",),
                   order="datum_zaciatku")
vehs = {v["id"]: v for v in db.fetch_all("vehicles")}

if not trips and not bts:
    st.info(f"V roku {rok} nie sú žiadne cesty.")
    st.stop()

# ----------------------------------------------------------- ročný súhrn ----
phm = sum(float(t["vypocitana_phm_nahrada"] or 0) for t in trips)
zakl = sum(float(t["vypocitana_zakladna_nahrada"] or 0) for t in trips)
stravne_eur = sum(float(t["vypocitane_stravne"] or 0) for t in trips
                  if (t["stravne_mena"] or "EUR") == "EUR")
vedl = sum(float(t["vedlajsie_vydavky_eur"] or 0) for t in trips)
jednodnove = sum(float(t["nahrada_spolu"] or 0) for t in trips)
km = sum(float(t["vzdialenost_km"] or 0) for t in trips)
viacdnove_naklady = sum(float(b["ubytovanie_eur"] or 0)
                        + float(b["kilometrovne_eur"] or 0)
                        + float(b["navstevy_rodiny_eur"] or 0) for b in bts)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Celková náhrada (jednodňové)", ui.eur(jednodnove))
k2.metric("Viacdňové (bez stravného)", ui.eur(viacdnove_naklady))
k3.metric("Najazdené km", f"{km:,.0f} km".replace(",", " "))
k4.metric("Počet ciest", f"{len(trips)} + {len(bts)} viacdňových")

st.divider()
c1, c2 = st.columns(2)

with c1:
    st.subheader("Rozpis náhrad (jednodňové)")
    df_rozpis = pd.DataFrame({
        "Zložka": ["PHM náhrada", "Základná náhrada", "Stravné (EUR)",
                   "Vedľajšie výdavky"],
        "Suma (€)": [round(phm, 2), round(zakl, 2), round(stravne_eur, 2),
                     round(vedl, 2)],
    })
    st.dataframe(df_rozpis, hide_index=True, width="stretch")
    st.bar_chart(df_rozpis.set_index("Zložka"))

with c2:
    st.subheader("Tuzemské vs zahraničné")
    tuz = [t for t in trips if not t["zahranicna"]]
    zahr = [t for t in trips if t["zahranicna"]]
    bt_tuz = [b for b in bts if not b["zahranicna"]]
    bt_zahr = [b for b in bts if b["zahranicna"]]
    df_tz = pd.DataFrame({
        "Kategória": ["Tuzemské", "Zahraničné"],
        "Jednodňové": [len(tuz), len(zahr)],
        "Viacdňové": [len(bt_tuz), len(bt_zahr)],
        "Náhrady jednodňové (€)": [
            round(sum(float(t["nahrada_spolu"] or 0) for t in tuz), 2),
            round(sum(float(t["nahrada_spolu"] or 0) for t in zahr), 2)],
    })
    st.dataframe(df_tz, hide_index=True, width="stretch")

    st.subheader("Štatistiky podľa vozidiel")
    voz_stat = {}
    for t in trips:
        if not t["vehicle_id"]:
            continue
        kluc = ui.vozidlo_label(vehs.get(t["vehicle_id"], {}))
        s = voz_stat.setdefault(kluc, {"cesty": 0, "km": 0.0, "nahrady": 0.0})
        s["cesty"] += 1
        s["km"] += float(t["vzdialenost_km"] or 0)
        s["nahrady"] += float(t["nahrada_spolu"] or 0)
    if voz_stat:
        df_voz = pd.DataFrame([
            {"Vozidlo": k, "Cesty": v["cesty"], "Km": round(v["km"], 1),
             "Náhrady (€)": round(v["nahrady"], 2)}
            for k, v in voz_stat.items()])
        st.dataframe(df_voz, hide_index=True, width="stretch")

st.divider()
st.subheader(f"Mesačný prehľad {rok}")
riadky = []
for m in range(1, 13):
    prefix = f"{rok}-{m:02d}"
    mt = [t for t in trips if str(t["datum"]).startswith(prefix)]
    mb = [b for b in bts if str(b["datum_zaciatku"]).startswith(prefix)]
    riadky.append({
        "Mesiac": ui.MESIACE[m - 1],
        "Jednodňové cesty": len(mt),
        "Viacdňové cesty": len(mb),
        "Km": round(sum(float(t["vzdialenost_km"] or 0) for t in mt), 1),
        "PHM (€)": round(sum(float(t["vypocitana_phm_nahrada"] or 0) for t in mt), 2),
        "Základná (€)": round(sum(float(t["vypocitana_zakladna_nahrada"] or 0) for t in mt), 2),
        "Stravné EUR": round(sum(float(t["vypocitane_stravne"] or 0) for t in mt
                                 if (t["stravne_mena"] or "EUR") == "EUR"), 2),
        "Spolu (€)": round(sum(float(t["nahrada_spolu"] or 0) for t in mt), 2),
    })
df_m = pd.DataFrame(riadky)
sucet = {"Mesiac": "SPOLU"} | {
    k: round(df_m[k].sum(), 2) for k in df_m.columns if k != "Mesiac"}
df_m = pd.concat([df_m, pd.DataFrame([sucet])], ignore_index=True)
st.dataframe(df_m, hide_index=True, width="stretch")
st.bar_chart(df_m.iloc[:12].set_index("Mesiac")["Spolu (€)"])
