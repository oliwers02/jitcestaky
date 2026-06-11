"""Viacdňové cesty — zoznam, detail s denným rozpisom stravného, PDF."""
import datetime as dt

import pandas as pd
import streamlit as st

from core import calc, db, exporters, ui

st.title("🧳 Viacdňové cesty")

emps = {e["id"]: e for e in db.fetch_all("employees")}

tab_zoznam, tab_nova = st.tabs(["📋 Zoznam a detail", "➕ Nová cesta"])

# -------------------------------------------------------------------- nová --
with tab_nova:
    c1, c2 = st.columns(2)
    with c1:
        zam = ui.select_zamestnanec("bt_emp")
        nazov = st.text_input("Názov cesty", "")
        ucel = st.text_input("Účel cesty", "")
        d_od = st.date_input("Dátum začiatku", dt.date.today())
        d_do = st.date_input("Dátum konca", dt.date.today() + dt.timedelta(days=2))
    with c2:
        cas_od = ui.cas_input("Čas odchodu (prvý deň)", "07:00", "bt_od")
        cas_do = ui.cas_input("Čas návratu (posledný deň)", "18:00", "bt_do")
        zahr = st.checkbox("Zahraničná cesta")
        krajina = "SK"
        vreckove = 0.0
        if zahr:
            krajina = st.selectbox("Cieľová krajina", ["CZ", "AT"],
                                   format_func=lambda k: calc.KRAJINY[k])
            max_v = float(calc.get_rates(d_od).get("vreckove_max_percent", 40))
            vreckove = st.slider("Vreckové (% zo stravného, §14)", 0.0, max_v, 0.0, 5.0)
        poznamky = st.text_area("Poznámky", "")
        suhlas = st.checkbox("Súhlas zamestnanca s vyslaním (§3) ✅")

    if st.button("💾 Vytvoriť cestu a denný rozpis", type="primary"):
        if not zam:
            st.error("Vyberte zamestnanca.")
        elif d_do < d_od:
            st.error("Dátum konca nemôže byť pred dátumom začiatku.")
        else:
            bt_data = {
                "employee_id": zam["id"], "nazov": nazov, "ucel": ucel,
                "datum_zaciatku": d_od.isoformat(), "datum_konca": d_do.isoformat(),
                "cas_odchodu_prvy_den": cas_od, "cas_navratu_posledny_den": cas_do,
                "zahranicna": int(zahr), "cielova_krajina": krajina,
                "poznamky": poznamky, "suhlas_zamestnanca": int(suhlas),
                "status": "koncept", "vreckove_percent": vreckove,
            }
            bt_id = db.insert("business_trips", bt_data)
            dni = calc.rozpis_dni(d_od.isoformat(), d_do.isoformat(), cas_od, cas_do)
            dni = calc.prepocitaj_dni({**bt_data, "id": bt_id}, dni)
            for d in dni:
                db.insert("business_trip_days", {
                    "business_trip_id": bt_id, "datum": d["datum"],
                    "typ_dna": d["typ_dna"], "pocet_hodin": d["pocet_hodin"],
                    "stravne_den_eur": d["stravne_den_eur"],
                })
            st.success(f"Cesta „{nazov}“ vytvorená (#{bt_id}) s {len(dni)} dňami. "
                       "Detail nájdete v záložke Zoznam a detail.")

# ---------------------------------------------------------- zoznam + detail --
with tab_zoznam:
    bts = db.fetch_all("business_trips", order="datum_zaciatku DESC")
    if not bts:
        st.info("Žiadne viacdňové cesty — vytvorte prvú v záložke „Nová cesta“.")
        st.stop()

    df = pd.DataFrame([{
        "ID": b["id"], "Názov": b["nazov"],
        "Zamestnanec": emps.get(b["employee_id"], {}).get("meno_priezvisko", "—"),
        "Od": b["datum_zaciatku"], "Do": b["datum_konca"],
        "Krajina": b["cielova_krajina"] if b["zahranicna"] else "SK",
        "Status": calc.STATUSY.get(b["status"], b["status"]),
    } for b in bts])
    st.dataframe(df, hide_index=True, width="stretch")

    vyber = st.selectbox("Detail cesty", bts,
                         format_func=lambda b: f"#{b['id']} {b['nazov']} "
                         f"({b['datum_zaciatku']} – {b['datum_konca']})")
    bt = vyber
    zam = emps.get(bt["employee_id"], {})
    dni = db.fetch_all("business_trip_days", "business_trip_id = ?",
                       (bt["id"],), order="datum")

    st.divider()
    st.subheader(f"🧳 {bt['nazov']} — detail")

    suhrn = calc.suhrn_viacdnovej(bt, dni)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Trvanie", f"{suhrn['trvanie_dni']} dní")
    k2.metric("Stravné", ui.suma_mena(suhrn["stravne"], suhrn["mena"]))
    k3.metric("Ubytovanie", ui.eur(bt["ubytovanie_eur"]))
    k4.metric("Celkom (EUR)",
              ui.eur(suhrn["spolu_eur"]) if suhrn["spolu_eur"] is not None
              else "— (chýba kurz)")
    if suhrn["vreckove"] > 0:
        st.caption(f"Vreckové ({bt['vreckove_percent']:.0f} %): "
                   f"{ui.suma_mena(suhrn['vreckove'], suhrn['mena'])}")
    if suhrn["spolu_eur"] is None:
        st.warning("Stravné v CZK — pre celkový súčet v EUR zadajte kurz CZK→EUR "
                   "v Nastaveniach.")

    # status + súhlas (validácia §3)
    s1, s2, s3 = st.columns(3)
    novy_status = s1.selectbox("Status", list(calc.STATUSY),
                               index=list(calc.STATUSY).index(bt["status"]),
                               format_func=calc.STATUSY.get)
    suhlas = s2.checkbox("Súhlas zamestnanca (§3)", bool(bt["suhlas_zamestnanca"]),
                         key=f"suhlas_{bt['id']}")
    if s3.button("Uložiť status"):
        if novy_status == "schvalena" and not suhlas:
            st.error("⚖️ Cestu nemožno schváliť bez súhlasu zamestnanca s vyslaním "
                     "(§3 zákona č. 283/2002 Z. z.).")
        else:
            db.update("business_trips", bt["id"],
                      {"status": novy_status, "suhlas_zamestnanca": int(suhlas)})
            st.success("Status uložený.")
            st.rerun()

    # náklady
    n1, n2, n3 = st.columns(3)
    ubyt = n1.number_input("Ubytovanie (€)", 0.0, 100000.0,
                           float(bt["ubytovanie_eur"] or 0), 1.0)
    kilom = n2.number_input("Kilometrovné — PHM + základná náhrada (€)", 0.0, 100000.0,
                            float(bt["kilometrovne_eur"] or 0), 1.0,
                            help="Vypočítajte ako jednodňovú cestu alebo zadajte ručne.")
    rodina = n3.number_input("Návštevy rodiny (€)", 0.0, 100000.0,
                             float(bt["navstevy_rodiny_eur"] or 0), 1.0)
    if st.button("Uložiť náklady"):
        db.update("business_trips", bt["id"],
                  {"ubytovanie_eur": ubyt, "kilometrovne_eur": kilom,
                   "navstevy_rodiny_eur": rodina})
        st.success("Náklady uložené.")
        st.rerun()

    st.subheader("Denný rozpis stravného")
    st.caption("Krátenie za poskytnuté jedlá: raňajky −25 %, obed −40 %, večera −35 %.")
    krajina = bt["cielova_krajina"] if bt["zahranicna"] else "SK"
    zmenene = False
    for d in dni:
        cc = st.columns([2, 2, 1, 1, 1, 1, 2])
        cc[0].write(f"**{d['datum']}**")
        cc[1].write(calc.TYP_DNA.get(d["typ_dna"], d["typ_dna"]))
        cc[2].write(f"{d['pocet_hodin']:.1f} h")
        r = cc[3].checkbox("🥐 R", bool(d["ranajky_poskytnute"]), key=f"r{d['id']}")
        o = cc[4].checkbox("🍲 O", bool(d["obed_poskytnuty"]), key=f"o{d['id']}")
        v = cc[5].checkbox("🍽️ V", bool(d["vecera_poskytnuta"]), key=f"v{d['id']}")
        rates_d = calc.get_rates(d["datum"])
        zaklad, mena, pasmo = calc.stravne_pre_hodiny(d["pocet_hodin"], krajina, rates_d)
        nove = calc.kratenie_jedal(zaklad, r, o, v, rates_d)
        cc[6].write(f"{ui.suma_mena(nove, mena)}  \n*{pasmo}*")
        if (r, o, v, nove) != (bool(d["ranajky_poskytnute"]), bool(d["obed_poskytnuty"]),
                               bool(d["vecera_poskytnuta"]), float(d["stravne_den_eur"] or 0)):
            db.update("business_trip_days", d["id"], {
                "ranajky_poskytnute": int(r), "obed_poskytnuty": int(o),
                "vecera_poskytnuta": int(v), "stravne_den_eur": nove})
            zmenene = True
    if zmenene:
        st.rerun()

    ui.panel_pouzite_sadzby(bt["datum_zaciatku"],
                            calc.get_rates(bt["datum_zaciatku"]), krajina)

    st.subheader("Dokumenty (PDF)")
    profil = ui.get_profil()
    p1, p2, p3 = st.columns(3)
    p1.download_button(
        "📄 Príkaz na pracovnú cestu (PDF)",
        exporters.pdf_cestovny_prikaz(bt, zam, profil),
        file_name=f"cestovny_prikaz_{bt['id']}.pdf", mime="application/pdf",
        width="stretch")
    p2.download_button(
        "🧾 Vyúčtovanie pracovnej cesty (PDF)",
        exporters.pdf_vyuctovanie(bt, zam, profil, dni, suhrn),
        file_name=f"vyuctovanie_{bt['id']}.pdf", mime="application/pdf",
        width="stretch")
    if p3.button("🗑️ Zmazať cestu", type="secondary", width="stretch"):
        db.delete("business_trips", bt["id"])
        st.success("Cesta zmazaná.")
        st.rerun()

    with st.expander("📋 Kopírovať cestu s novým termínom"):
        st.caption("Vytvorí novú cestu s rovnakým názvom, účelom, krajinou aj "
                   "nákladmi — zmení sa len termín; denný rozpis stravného sa "
                   "vygeneruje nanovo.")
        trvanie = (dt.date.fromisoformat(bt["datum_konca"])
                   - dt.date.fromisoformat(bt["datum_zaciatku"])).days
        k1, k2 = st.columns(2)
        novy_od = k1.date_input("Nový dátum začiatku", dt.date.today(),
                                key=f"kop_od_{bt['id']}")
        novy_do = k2.date_input("Nový dátum konca",
                                dt.date.today() + dt.timedelta(days=trvanie),
                                key=f"kop_do_{bt['id']}")
        kc1, kc2 = st.columns(2)
        with kc1:
            kop_cas_od = ui.cas_input("Čas odchodu",
                                      bt["cas_odchodu_prvy_den"] or "07:00",
                                      f"kop_cas_od_{bt['id']}")
        with kc2:
            kop_cas_do = ui.cas_input("Čas návratu",
                                      bt["cas_navratu_posledny_den"] or "18:00",
                                      f"kop_cas_do_{bt['id']}")
        if st.button("📋 Vytvoriť kópiu", type="primary", key=f"kop_btn_{bt['id']}"):
            if novy_do < novy_od:
                st.error("Dátum konca nemôže byť pred dátumom začiatku.")
            else:
                kopia = {k: bt[k] for k in
                         ("employee_id", "nazov", "ucel", "zahranicna",
                          "cielova_krajina", "poznamky", "suhlas_zamestnanca",
                          "ubytovanie_eur", "kilometrovne_eur",
                          "navstevy_rodiny_eur", "vreckove_percent")}
                kopia.update({
                    "datum_zaciatku": novy_od.isoformat(),
                    "datum_konca": novy_do.isoformat(),
                    "cas_odchodu_prvy_den": kop_cas_od,
                    "cas_navratu_posledny_den": kop_cas_do,
                    "status": "koncept",
                })
                novy_id = db.insert("business_trips", kopia)
                nove_dni = calc.rozpis_dni(kopia["datum_zaciatku"],
                                           kopia["datum_konca"],
                                           kop_cas_od, kop_cas_do)
                nove_dni = calc.prepocitaj_dni({**kopia, "id": novy_id}, nove_dni)
                for d in nove_dni:
                    db.insert("business_trip_days", {
                        "business_trip_id": novy_id, "datum": d["datum"],
                        "typ_dna": d["typ_dna"], "pocet_hodin": d["pocet_hodin"],
                        "stravne_den_eur": d["stravne_den_eur"]})
                st.success(f"Kópia vytvorená ako #{novy_id} "
                           f"({kopia['datum_zaciatku']} – {kopia['datum_konca']}, "
                           f"{len(nove_dni)} dní, status koncept).")
                st.rerun()
