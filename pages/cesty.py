"""Cesty (jednodňové) — zoznam s filtrom, formulár Nová/Upraviť."""
import datetime as dt

import pandas as pd
import streamlit as st

from core import calc, db, ui

st.title("🚗 Cesty (jednodňové)")

emps = {e["id"]: e for e in db.fetch_all("employees")}
vehs = {v["id"]: v for v in db.fetch_all("vehicles")}

tab_zoznam, tab_form = st.tabs(["📋 Zoznam", "➕ Nová / Upraviť cesta"])

# ------------------------------------------------------------------ zoznam --
with tab_zoznam:
    trips = db.fetch_all("trips", order="datum DESC, id DESC")
    mesiace = sorted({str(t["datum"])[:7] for t in trips}, reverse=True)
    f1, f2 = st.columns([1, 3])
    filter_m = f1.selectbox("Mesiac", ["Všetky"] + mesiace)
    if filter_m != "Všetky":
        trips = [t for t in trips if str(t["datum"]).startswith(filter_m)]

    if trips:
        df = pd.DataFrame([{
            "ID": t["id"],
            "Dátum": t["datum"],
            "Trasa": f"{t['miesto_zaciatku'] or ''} → {t['ciel_cesty'] or ''}",
            "Zamestnanec": emps.get(t["employee_id"], {}).get("meno_priezvisko", "—"),
            "Km": t["vzdialenost_km"],
            "PHM (€)": t["vypocitana_phm_nahrada"],
            "Zákl. (€)": t["vypocitana_zakladna_nahrada"],
            "Stravné": ui.suma_mena(t["vypocitane_stravne"], t["stravne_mena"] or "EUR"),
            "Spolu (€)": t["nahrada_spolu"],
        } for t in trips])
        st.dataframe(df, hide_index=True, width="stretch")
        st.caption(f"Spolu: **{len(trips)} ciest**, "
                   f"{sum(float(t['vzdialenost_km'] or 0) for t in trips):,.0f} km, "
                   f"náhrady {ui.eur(sum(float(t['nahrada_spolu'] or 0) for t in trips))}"
                   .replace(",", " "))

        c1, c2 = st.columns([1, 1])
        vyber = c1.selectbox("Cesta (ID) na úpravu / kopírovanie / zmazanie",
                             [t["id"] for t in trips],
                             format_func=lambda i: f"#{i} — "
                             f"{next(t for t in trips if t['id'] == i)['datum']} "
                             f"{next(t for t in trips if t['id'] == i)['ciel_cesty']}")

        def _reset_form_widgets():
            for k in ("trip_od", "trip_do", "trip_emp", "trip_veh"):
                st.session_state.pop(k, None)
            st.session_state.pop("edit_trip_id", None)
            st.session_state.pop("copy_trip_id", None)

        b1, b2, b3 = c2.columns(3)
        if b1.button("✏️ Upraviť", width="stretch"):
            _reset_form_widgets()
            st.session_state["edit_trip_id"] = vyber
            st.rerun()
        if b2.button("📋 Kopírovať", width="stretch",
                     help="Predvyplní novú cestu podľa vybranej — stačí "
                          "zmeniť dátum a čas."):
            _reset_form_widgets()
            st.session_state["copy_trip_id"] = vyber
            st.rerun()
        if b3.button("🗑️ Zmazať", type="secondary", width="stretch"):
            db.delete("trips", vyber)
            st.success(f"Cesta #{vyber} zmazaná.")
            st.rerun()
    else:
        st.info("Žiadne cesty vo zvolenom období.")

# ---------------------------------------------------------------- formulár --
with tab_form:
    edit_id = st.session_state.get("edit_trip_id")
    copy_id = st.session_state.get("copy_trip_id")
    edit = db.fetch_one("trips", edit_id) if edit_id else None
    predloha = db.fetch_one("trips", copy_id) if (copy_id and not edit) else None
    if edit:
        st.info(f"Upravujete cestu #{edit_id}. "
                "Pre novú cestu kliknite na „Zrušiť úpravu“.")
        if st.button("Zrušiť úpravu"):
            del st.session_state["edit_trip_id"]
            st.rerun()
    elif predloha:
        st.info(f"📋 Kopírujete cestu #{copy_id} ({predloha['datum']} → "
                f"{predloha['ciel_cesty']}). Trasa, km, vozidlo aj účel sú "
                "predvyplnené — zmeňte dátum a čas a uložte ako novú cestu.")
        if st.button("Zrušiť kopírovanie"):
            del st.session_state["copy_trip_id"]
            st.rerun()

    e = edit or predloha or {}
    c1, c2 = st.columns(2)
    with c1:
        zam = ui.select_zamestnanec("trip_emp", default_id=e.get("employee_id"))
        # pri kópii sa dátum predvolí na dnešok — ostatné polia z predlohy
        datum = st.date_input("Dátum cesty",
                              dt.date.fromisoformat(str(e.get("datum")))
                              if (edit and e.get("datum")) else dt.date.today())
        cas_od = ui.cas_input("Čas odchodu", e.get("cas_odchodu") or "07:00", "trip_od")
        cas_do = ui.cas_input("Čas príchodu", e.get("cas_prichodu") or "17:00", "trip_do")
        typ_dopravy = st.selectbox(
            "Typ dopravy", list(calc.TYP_DOPRAVY),
            index=list(calc.TYP_DOPRAVY).index(e.get("typ_dopravy", "sukromne_auto")),
            format_func=calc.TYP_DOPRAVY.get)
        voz = None
        if typ_dopravy == "sukromne_auto":
            voz = ui.select_vozidlo("trip_veh", default_id=e.get("vehicle_id"))
        ucel = st.text_input("Účel cesty", e.get("ucel_cesty") or "")
    with c2:
        miesta = db.fetch_all("locations", order="nazov")
        zaciatok_default = e.get("miesto_zaciatku") or (zam or {}).get("adresa_bydliska", "")
        miesto_zac = st.text_input("Miesto začiatku (bydlisko)", zaciatok_default)
        ciel = st.text_input("Cieľ cesty", e.get("ciel_cesty") or "")
        if miesta:
            vyb = st.selectbox("…alebo vyberte z obľúbených miest",
                               [None] + miesta,
                               format_func=lambda m: "—" if m is None else m["nazov"])
            if vyb:
                ciel = vyb["adresa"] or vyb["nazov"]
                st.caption(f"Cieľ nastavený na: {ciel}")
        typ_trasy = st.selectbox(
            "Typ trasy", list(calc.TYP_TRASY),
            index=list(calc.TYP_TRASY).index(e.get("typ_trasy", "zmiesana")),
            format_func=calc.TYP_TRASY.get)
        km = st.number_input("Vzdialenosť spolu — tam a späť (km)",
                             0.0, 5000.0, float(e.get("vzdialenost_km") or 0.0), 1.0)
        # offline odhad vzdialenosti z obľúbených miest so súradnicami
        so_surad = [m for m in miesta if m["lat"] and m["lon"]]
        if len(so_surad) >= 2:
            with st.expander("📐 Odhad vzdialenosti (vzdušnou čiarou, offline)"):
                ma = st.selectbox("Z miesta", so_surad, format_func=lambda m: m["nazov"], key="hav_a")
                mb = st.selectbox("Do miesta", so_surad, format_func=lambda m: m["nazov"], key="hav_b")
                if ma and mb and ma["id"] != mb["id"]:
                    d = calc.haversine_km(ma["lat"], ma["lon"], mb["lat"], mb["lon"])
                    st.caption(f"Vzdušná vzdialenosť: **{d} km** "
                               f"(tam a späť ≈ {2 * d:.0f} km; cestná býva o 20 – 30 % dlhšia)")
        vedlajsie = st.number_input("Vedľajšie výdavky (parkovné, mýto…) €",
                                    0.0, 10000.0, float(e.get("vedlajsie_vydavky_eur") or 0.0), 0.5)

    c3, c4, c5 = st.columns(3)
    zahranicna = c3.checkbox("Zahraničná cesta", bool(e.get("zahranicna")))
    krajina = "SK"
    vreckove_pct = 0.0
    if zahranicna:
        krajina = c3.selectbox("Cieľová krajina", ["CZ", "AT"],
                               index=["CZ", "AT"].index(e["cielova_krajina"])
                               if e.get("cielova_krajina") in ("CZ", "AT") else 0,
                               format_func=lambda k: calc.KRAJINY[k])
        max_v = float(calc.get_rates(datum).get("vreckove_max_percent", 40))
        vreckove_pct = c3.slider("Vreckové (% zo stravného)", 0.0, max_v,
                                 float(e.get("vreckove_percent") or 0.0), 5.0)
    cena_dokl = c4.number_input(
        "Cena PHM z dokladu €/l (§7 ods. 5 — voliteľné)", 0.0, 10.0,
        float(e.get("cena_phm_z_dokladu_eur_l") or 0.0), 0.01,
        help="Ak je zadaná, použije sa namiesto priemernej ceny ŠÚ SR.")
    suhlas = c5.checkbox("Súhlas zamestnanca s vyslaním (§3) ✅",
                         bool(e.get("suhlas_zamestnanca")))
    st.info("ℹ️ **§3 zákona 283/2002 Z. z.** — zamestnanca možno vyslať na pracovnú "
            "cestu len s jeho súhlasom (ak vyslanie nevyplýva z pracovnej zmluvy). "
            "**§7 ods. 5** — cenu PHM možno preukázať dokladom o kúpe; inak sa použije "
            "priemerná cena ŠÚ SR.")

    if st.button("💾 Uložiť a prepočítať", type="primary"):
        if not zam:
            st.error("Vyberte zamestnanca.")
        elif typ_dopravy == "sukromne_auto" and not voz:
            st.error("Vyberte vozidlo.")
        else:
            data = {
                "employee_id": zam["id"],
                "vehicle_id": voz["id"] if voz else None,
                "typ_dopravy": typ_dopravy,
                "datum": datum.isoformat(),
                "cas_odchodu": cas_od,
                "cas_prichodu": cas_do,
                "miesto_zaciatku": miesto_zac,
                "ciel_cesty": ciel,
                "typ_trasy": typ_trasy,
                "ucel_cesty": ucel,
                "vedlajsie_vydavky_eur": vedlajsie,
                "vzdialenost_km": km,
                "zahranicna": int(zahranicna),
                "cielova_krajina": krajina,
                "cena_phm_z_dokladu_eur_l": cena_dokl or None,
                "suhlas_zamestnanca": int(suhlas),
                "vreckove_percent": vreckove_pct,
            }
            vysledok = calc.vypocitaj_jednodnovu(data, voz)
            rates = vysledok.pop("_rates")
            hodiny, pasmo = vysledok.pop("_hodiny"), vysledok.pop("_pasmo")
            prepocitane = vysledok.pop("_stravne_prepocitane")
            data.update(vysledok)
            if edit:
                db.update("trips", edit_id, data)
                del st.session_state["edit_trip_id"]
                st.success(f"Cesta #{edit_id} aktualizovaná.")
            else:
                nid = db.insert("trips", data)
                if predloha:
                    st.session_state.pop("copy_trip_id", None)
                    st.success(f"Cesta #{nid} uložená (kópia cesty #{copy_id}).")
                else:
                    st.success(f"Cesta #{nid} uložená.")

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("PHM náhrada", ui.eur(vysledok["vypocitana_phm_nahrada"]))
            r2.metric("Základná náhrada", ui.eur(vysledok["vypocitana_zakladna_nahrada"]))
            r3.metric(f"Stravné ({pasmo}, {hodiny} h)",
                      ui.suma_mena(vysledok["vypocitane_stravne"], vysledok["stravne_mena"]))
            r4.metric("Náhrada spolu", ui.eur(vysledok["nahrada_spolu"]))
            if not prepocitane:
                st.warning("Stravné v CZK nie je zahrnuté v sume spolu — zadajte "
                           "kurz CZK→EUR v Nastaveniach.")
            ui.panel_pouzite_sadzby(datum.isoformat(), rates, krajina)
