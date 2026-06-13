"""Generátor ciest — hromadné vytvorenie jednodňových ciest za obdobie."""
import datetime as dt

import pandas as pd
import streamlit as st

from core import calc, cloud_sync, db, holidays_sk, ui

st.title("⚙️ Generátor ciest")
st.caption("Hromadne vytvorí jednodňové cesty za zvolené obdobie podľa "
           "definovaných trás a percentuálneho rozdelenia dní.")

c1, c2 = st.columns(2)
with c1:
    zam = ui.select_zamestnanec("gen_emp")
    voz = ui.select_vozidlo("gen_veh")
    d_od = st.date_input("Obdobie od", dt.date.today().replace(day=1))
    d_do = st.date_input("Obdobie do", dt.date.today())
with c2:
    cas_od = ui.cas_input("Čas odchodu", "07:30", "gen_od")
    cas_do = ui.cas_input("Čas príchodu", "16:30", "gen_do")
    vikendy = st.checkbox("Vrátane víkendov", False)
    sviatky = st.checkbox("Vrátane štátnych sviatkov (SK)", False)
    ucel = st.text_input("Účel ciest", "obchodné rokovanie")

dni = holidays_sk.pracovne_dni(d_od, d_do, vikendy, sviatky) if d_od <= d_do else []
st.metric("Náhľad: počet dní na vygenerovanie", len(dni))
if d_od <= d_do:
    sviatky_v_obdobi = {d: n for d, n in holidays_sk.sviatky_sk(d_od.year).items()
                        if d_od <= d <= d_do}
    if d_do.year != d_od.year:
        sviatky_v_obdobi |= {d: n for d, n in holidays_sk.sviatky_sk(d_do.year).items()
                             if d_od <= d <= d_do}
    if sviatky_v_obdobi:
        st.caption("Sviatky v období: " + ", ".join(
            f"{d.strftime('%d.%m.')} ({n})" for d, n in sorted(sviatky_v_obdobi.items())))

st.subheader("Trasy a rozdelenie dní")
st.caption("Definujte trasy so zástavkami; percentá musia spolu dávať 100 %. "
           "Dni sa medzi trasy rozdelia pomerne a striedajú sa.")

default_trasy = pd.DataFrame([
    {"Cieľ": "Klient Trenčín", "Zástavky": "", "Km (tam a späť)": 180.0, "Percento": 60},
    {"Cieľ": "Sklad Žilina", "Zástavky": "Považská Bystrica", "Km (tam a späť)": 90.0, "Percento": 40},
])
trasy_df = st.data_editor(
    st.session_state.get("gen_trasy", default_trasy),
    num_rows="dynamic", key="gen_trasy_editor", width="stretch",
    column_config={
        "Km (tam a späť)": st.column_config.NumberColumn(min_value=0.0, step=1.0),
        "Percento": st.column_config.NumberColumn(min_value=0, max_value=100, step=5),
    })

trasy = [r for _, r in trasy_df.iterrows()
         if str(r.get("Cieľ") or "").strip() and float(r.get("Percento") or 0) > 0]
sucet_pct = sum(float(r["Percento"]) for r in trasy)
if trasy and abs(sucet_pct - 100) > 0.01:
    st.error(f"Percentá trás musia spolu dávať 100 % (teraz {sucet_pct:.0f} %).")

typ_trasy = st.selectbox("Typ trasy", list(calc.TYP_TRASY),
                         index=2, format_func=calc.TYP_TRASY.get)
suhlas = st.checkbox("Súhlas zamestnanca s vyslaním (§3) pre všetky cesty ✅", True)

if st.button("🚀 Vygenerovať cesty", type="primary",
             disabled=not (dni and trasy and abs(sucet_pct - 100) <= 0.01)):
    if not zam or not voz:
        st.error("Vyberte zamestnanca aj vozidlo.")
    else:
        # pomerné rozdelenie počtu dní medzi trasy (metóda najväčších zvyškov)
        n = len(dni)
        podiely = [float(t["Percento"]) * n / 100 for t in trasy]
        pocty = [int(p) for p in podiely]
        zvysok = n - sum(pocty)
        poradie = sorted(range(len(trasy)), key=lambda i: podiely[i] - pocty[i],
                         reverse=True)
        for i in poradie[:zvysok]:
            pocty[i] += 1
        # striedanie trás po dňoch
        rozpis: list[int] = []
        zostatok = pocty[:]
        while len(rozpis) < n:
            for i in range(len(trasy)):
                if zostatok[i] > 0:
                    rozpis.append(i)
                    zostatok[i] -= 1
                if len(rozpis) == n:
                    break

        vytvorene = 0
        spolu = 0.0
        db.suspend_change(True)  # počas hromadného vkladania nezálohuj po každej ceste
        for den, idx in zip(dni, rozpis):
            t = trasy[idx]
            ciel = str(t["Cieľ"])
            zastavky = str(t.get("Zástavky") or "").strip()
            if zastavky:
                ciel = f"{ciel} (cez {zastavky})"
            data = {
                "employee_id": zam["id"], "vehicle_id": voz["id"],
                "typ_dopravy": "sukromne_auto", "datum": den.isoformat(),
                "cas_odchodu": cas_od, "cas_prichodu": cas_do,
                "miesto_zaciatku": zam.get("adresa_bydliska") or "",
                "ciel_cesty": ciel, "typ_trasy": typ_trasy, "ucel_cesty": ucel,
                "vedlajsie_vydavky_eur": 0.0,
                "vzdialenost_km": float(t["Km (tam a späť)"] or 0),
                "zahranicna": 0, "cielova_krajina": "SK",
                "suhlas_zamestnanca": int(suhlas),
            }
            vysledok = calc.vypocitaj_jednodnovu(data, voz)
            data.update({k: v for k, v in vysledok.items() if not k.startswith("_")})
            db.insert("trips", data)
            vytvorene += 1
            spolu += data["nahrada_spolu"]
        db.suspend_change(False)
        if cloud_sync.enabled():
            cloud_sync.push()  # jedna spoločná záloha po celom generovaní
        st.success(f"✅ Vygenerovaných {vytvorene} ciest, náhrady spolu {ui.eur(spolu)}. "
                   "Nájdete ich na stránke Cesty.")
        ui.panel_pouzite_sadzby(dni[0].isoformat(), calc.get_rates(dni[0]))
