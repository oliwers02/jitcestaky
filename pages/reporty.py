"""Reporty — koľko mi patrí (jednodňové + viacdňové) a koľko mi treba vyplatiť."""
import datetime as dt

import pandas as pd
import streamlit as st

from core import calc, db, ui

st.title("📈 Reporty a vyplácanie náhrad")

emps = {e["id"]: e for e in db.fetch_all("employees")}
vehs = {v["id"]: v for v in db.fetch_all("vehicles")}

rok = st.selectbox("Rok", list(range(dt.date.today().year, 2023, -1)))

trips = db.fetch_all("trips", "datum LIKE ?", (f"{rok}-%",), order="datum")
bts = db.fetch_all("business_trips", "datum_zaciatku LIKE ?", (f"{rok}-%",),
                   order="datum_zaciatku")

# Konzistentné súčty — jednodňové aj viacdňové dokopy, bez duplicity stravného.
totals = calc.compute_totals(trips, bts)
km = sum(float(t["vzdialenost_km"] or 0) for t in trips)

# ----------------------------------------------- čo mi patrí za rok ---------
st.subheader(f"Čo mi patrí za rok {rok}")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Náhrada za auto (PHM + km)", ui.eur(totals["auto"]))
k2.metric("Stravné spolu", ui.eur(totals["stravne_spolu"]))
k3.metric("Ostatné (ubytovanie, vedľajšie)", ui.eur(totals["ostatne"]))
k4.metric("CELKOM náhrady", ui.eur(totals["celkom"]))
st.caption(f"Stravné spolu = jednodňové {ui.eur(totals['stravne_jednodnove'])} + "
           f"viacdňové diéty {ui.eur(totals['stravne_viacdnove'])}. "
           f"Cesty: {len(trips)} jednodňových + {len(bts)} viacdňových, "
           f"{km:,.0f} km.".replace(",", " "))
if totals["overlap_trip_ids"]:
    st.caption(f"ℹ️ {len(totals['overlap_trip_ids'])} jednodňových ciest spadá do "
               "viacdňovej cesty — ich stravné je rátané len v diétach (bez duplicity).")

# ---------------------------------- zjednotená tabuľka ciest so stravným -----
if trips or bts:
    riadky = []
    for t in trips:
        v_multi = (t.get("employee_id"), str(t.get("datum"))) in totals["covered_days"]
        stravne = 0.0 if v_multi else calc._trip_stravne_eur(t)
        auto = (float(t["vypocitana_phm_nahrada"] or 0)
                + float(t["vypocitana_zakladna_nahrada"] or 0))
        vedl = float(t["vedlajsie_vydavky_eur"] or 0)
        riadky.append({
            "Dátum": str(t["datum"]),
            "Typ": "Jednodňová",
            "Cesta": t.get("ciel_cesty") or "—",
            "Km": round(float(t["vzdialenost_km"] or 0), 1),
            "Auto (€)": round(auto, 2),
            "Stravné (€)": round(stravne, 2),
            "Ostatné (€)": round(vedl, 2),
            "Spolu (€)": round(auto + stravne + vedl, 2),
        })
    for b in bts:
        dni = db.fetch_all("business_trip_days", "business_trip_id = ?",
                           (b["id"],), order="datum")
        s = calc.suhrn_viacdnovej(b, dni)
        auto = float(b["kilometrovne_eur"] or 0)
        stravne = s["stravne_eur"] or 0.0
        ostatne = float(b["ubytovanie_eur"] or 0) + float(b["navstevy_rodiny_eur"] or 0)
        riadky.append({
            "Dátum": f"{b['datum_zaciatku']} – {b['datum_konca']}",
            "Typ": "Viacdňová",
            "Cesta": b.get("nazov") or "—",
            "Km": 0.0,
            "Auto (€)": round(auto, 2),
            "Stravné (€)": round(stravne, 2),
            "Ostatné (€)": round(ostatne, 2),
            "Spolu (€)": round(auto + stravne + ostatne, 2),
        })
    df_all = pd.DataFrame(riadky).sort_values("Dátum").reset_index(drop=True)
    sucet = {"Dátum": "SPOLU", "Typ": "", "Cesta": "", "Km": round(df_all["Km"].sum(), 1)}
    for c in ["Auto (€)", "Stravné (€)", "Ostatné (€)", "Spolu (€)"]:
        sucet[c] = round(df_all[c].sum(), 2)
    df_all = pd.concat([df_all, pd.DataFrame([sucet])], ignore_index=True)
    st.dataframe(df_all, hide_index=True, width="stretch")

st.divider()

# ============================ VYPLÁCANIE NÁHRAD (modul) =====================
st.subheader("💶 Vyplácanie náhrad")
st.caption("Eviduj, kedy a koľko si si vyplatil. Saldo počíta zo **všetkých** "
           "ciest a výplat (všetky roky), takže vždy vidíš, koľko ti ešte treba "
           "vyplatiť.")

# saldo cez všetky roky (čo mi patrí celkovo − čo už bolo vyplatené)
all_trips = db.fetch_all("trips")
all_bts = db.fetch_all("business_trips")
all_totals = calc.compute_totals(all_trips, all_bts)
payouts = db.fetch_all("payouts", order="datum DESC")
vyplatene = round(sum(float(p["suma_eur"] or 0) for p in payouts), 2)
zostava = round(all_totals["celkom"] - vyplatene, 2)

s1, s2, s3 = st.columns(3)
s1.metric("Čo mi patrí spolu (všetky cesty)", ui.eur(all_totals["celkom"]))
s2.metric("Už vyplatené", ui.eur(vyplatene))
s3.metric("➡️ Zostáva vyplatiť", ui.eur(zostava))
if zostava < -0.005:
    st.warning(f"Vyplatené je o {ui.eur(-zostava)} viac, než činia náhrady "
               "(preplatok). Skontroluj zadané výplaty.")
elif zostava <= 0.005:
    st.success("Všetky náhrady sú vyplatené. ✅")

# pridať výplatu
with st.form("nova_vyplata", clear_on_submit=True):
    st.markdown("**Pridať výplatu**")
    c1, c2, c3 = st.columns([1, 1, 2])
    p_datum = c1.date_input("Dátum výplaty", dt.date.today())
    p_suma = c2.number_input("Suma (€)", 0.0, 1_000_000.0,
                             value=float(zostava) if zostava > 0 else 0.0, step=10.0)
    p_pozn = c3.text_input("Poznámka (napr. spôsob úhrady, obdobie)")
    p_emp = None
    if len(emps) > 1:
        e = st.selectbox("Zamestnanec (voliteľné)", [None] + list(emps.values()),
                         format_func=lambda x: "—" if x is None else x["meno_priezvisko"])
        p_emp = e["id"] if e else None
    if st.form_submit_button("💾 Zaznamenať výplatu", type="primary"):
        if p_suma <= 0:
            st.error("Zadaj sumu väčšiu ako 0.")
        else:
            db.insert("payouts", {"employee_id": p_emp,
                                  "datum": p_datum.isoformat(),
                                  "suma_eur": round(p_suma, 2), "poznamka": p_pozn})
            st.success(f"Výplata {ui.eur(p_suma)} zaznamenaná.")
            st.rerun()

# história výplat
if payouts:
    st.markdown("**História výplat**")
    df_p = pd.DataFrame([{
        "ID": p["id"], "Dátum": p["datum"], "Suma (€)": round(float(p["suma_eur"] or 0), 2),
        "Zamestnanec": emps.get(p["employee_id"], {}).get("meno_priezvisko", "—")
        if p["employee_id"] else "—",
        "Poznámka": p["poznamka"] or "",
    } for p in payouts])
    st.dataframe(df_p, hide_index=True, width="stretch")
    c1, c2 = st.columns([1, 3])
    zmaz = c1.selectbox("Zmazať výplatu (ID)", [p["id"] for p in payouts],
                        format_func=lambda i: f"#{i}")
    if c2.button("🗑️ Zmazať vybranú výplatu"):
        db.delete("payouts", zmaz)
        st.success("Výplata zmazaná.")
        st.rerun()
else:
    st.info("Zatiaľ žiadne výplaty. Po pridaní uvidíš, koľko ešte zostáva vyplatiť.")

st.divider()

# ------------------------------------------- mesačný prehľad (rok) ----------
st.subheader(f"Mesačný prehľad {rok}")
riadky = []
for m in range(1, 13):
    prefix = f"{rok}-{m:02d}"
    mt = [t for t in trips if str(t["datum"]).startswith(prefix)]
    mb = [b for b in bts if str(b["datum_zaciatku"]).startswith(prefix)]
    mtot = calc.compute_totals(mt, mb)
    riadky.append({
        "Mesiac": ui.MESIACE[m - 1],
        "Jednodňové": len(mt),
        "Viacdňové": len(mb),
        "Km": round(sum(float(t["vzdialenost_km"] or 0) for t in mt), 1),
        "Auto (€)": mtot["auto"],
        "Stravné (€)": mtot["stravne_spolu"],
        "Spolu (€)": mtot["celkom"],
    })
df_m = pd.DataFrame(riadky)
sucet = {"Mesiac": "SPOLU"} | {
    k: round(df_m[k].sum(), 2) for k in df_m.columns if k != "Mesiac"}
df_m = pd.concat([df_m, pd.DataFrame([sucet])], ignore_index=True)
st.dataframe(df_m, hide_index=True, width="stretch")
st.bar_chart(df_m.iloc[:12].set_index("Mesiac")["Spolu (€)"])

# ------------------------------------------- štatistiky podľa vozidiel ------
voz_stat = {}
for t in trips:
    if not t["vehicle_id"]:
        continue
    kluc = ui.vozidlo_label(vehs.get(t["vehicle_id"], {}))
    s = voz_stat.setdefault(kluc, {"cesty": 0, "km": 0.0, "auto": 0.0})
    s["cesty"] += 1
    s["km"] += float(t["vzdialenost_km"] or 0)
    s["auto"] += (float(t["vypocitana_phm_nahrada"] or 0)
                  + float(t["vypocitana_zakladna_nahrada"] or 0))
if voz_stat:
    st.subheader("Štatistiky podľa vozidiel")
    st.dataframe(pd.DataFrame([
        {"Vozidlo": k, "Cesty": v["cesty"], "Km": round(v["km"], 1),
         "Náhrada za auto (€)": round(v["auto"], 2)}
        for k, v in voz_stat.items()]), hide_index=True, width="stretch")
