"""Nastavenia — sadzby s verzovaním, diéty, profil, téma, záloha dát."""
import datetime as dt
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from core import calc, cloud_sync, db, ui

st.title("🛠️ Nastavenia")

(tab_sadzby, tab_diety, tab_profil, tab_vzhlad,
 tab_cloud, tab_zaloha) = st.tabs(
    ["💶 Sadzby", "🍽️ Diéty SK/CZ/AT", "🏢 Osobné údaje", "🎨 Vzhľad",
     "☁️ Cloud sync", "💾 Záloha dát"])

# ---------------------------------------------------------------- sadzby ----
with tab_sadzby:
    verzie = db.fetch_all("settings", order="platne_od DESC, id DESC")
    st.caption("Sadzby sú verzované — pri výpočte sa použije verzia platná "
               "k dátumu cesty. Skontrolujte podľa platného opatrenia MF SR "
               "pre rok 2026.")
    verzia = st.selectbox(
        "Verzia sadzieb", verzie,
        format_func=lambda v: f"platné od {v['platne_od']} (#{v['id']})")
    r = json.loads(verzia["rates_json"])

    st.subheader("Náhrady za použitie súkromného vozidla (§7)")
    c1, c2 = st.columns(2)
    auto = c1.number_input("Základná náhrada — osobné auto (€/km)", 0.0, 2.0,
                           float(r["zakladna_nahrada"]["osobne_auto"]), 0.001,
                           format="%.3f")
    moto = c2.number_input("Základná náhrada — motocykel (€/km)", 0.0, 1.0,
                           float(r["zakladna_nahrada"]["motocykel"]), 0.01)

    st.subheader("Priemerné ceny PHM (ŠÚ SR)")
    p1, p2, p3, p4, p5 = st.columns(5)
    benzin = p1.number_input("Benzín 95 (€/l)", 0.0, 5.0, float(r["ceny_phm"]["benzin"]), 0.01)
    diesel = p2.number_input("Diesel (€/l)", 0.0, 5.0, float(r["ceny_phm"]["diesel"]), 0.01)
    lpg = p3.number_input("LPG (€/l)", 0.0, 5.0, float(r["ceny_phm"]["lpg"]), 0.01)
    cng = p4.number_input("CNG (€/kg)", 0.0, 5.0, float(r["ceny_phm"]["cng"]), 0.01)
    elektrina = p5.number_input("Elektrina (€/kWh)", 0.0, 5.0,
                                float(r["ceny_phm"].get("elektrina", 0.25)), 0.01)

    st.subheader("Stravné tuzemské — SK (§5)")
    s1, s2, s3 = st.columns(3)
    sk1 = s1.number_input("5 – 12 h (€)", 0.0, 100.0, float(r["stravne_sk"]["pasmo_5_12"]), 0.1)
    sk2 = s2.number_input("12 – 18 h (€)", 0.0, 100.0, float(r["stravne_sk"]["pasmo_12_18"]), 0.1)
    sk3 = s3.number_input("nad 18 h (€)", 0.0, 100.0, float(r["stravne_sk"]["pasmo_nad_18"]), 0.1)

    st.subheader("Ostatné")
    o1, o2 = st.columns(2)
    kurz_txt = o1.text_input(
        "Kurz CZK → EUR (počet CZK za 1 €; prázdne = diéty ostanú v CZK)",
        "" if not r.get("kurz_czk_eur") else str(r["kurz_czk_eur"]),
        help="České diéty sa týmto kurzom prepočítavajú na EUR. Predvolený "
             "24,231 = ECB referenčný kurz publikovaný NBS (jún 2026) — "
             "aktualizujte podľa nbs.sk.")
    vreckove_max = o2.number_input("Vreckové — maximálne % zo stravného (§14)",
                                   0.0, 100.0, float(r.get("vreckove_max_percent", 40)), 5.0)

    platne_od = st.date_input("Platné od (nová verzia sadzieb)",
                              dt.date.fromisoformat(verzia["platne_od"]))

    b1, b2 = st.columns(2)
    nove_rates = {
        "zakladna_nahrada": {"osobne_auto": auto, "motocykel": moto},
        "ceny_phm": {"benzin": benzin, "diesel": diesel, "lpg": lpg,
                     "cng": cng, "elektrina": elektrina},
        "jednotky_phm": r.get("jednotky_phm", {}),
        "stravne_sk": {"pasmo_5_12": sk1, "pasmo_12_18": sk2, "pasmo_nad_18": sk3},
        "kratenie_jedal": r.get("kratenie_jedal",
                                {"ranajky": 0.25, "obed": 0.40, "vecera": 0.35}),
        "kurz_czk_eur": float(kurz_txt.replace(",", ".")) if kurz_txt.strip() else None,
        "vreckove_max_percent": vreckove_max,
    }
    if b1.button("💾 Uložiť ako novú verziu", type="primary", width="stretch"):
        nove_rates["platne_od"] = platne_od.isoformat()
        db.insert("settings", {"platne_od": platne_od.isoformat(),
                               "rates_json": json.dumps(nove_rates, ensure_ascii=False)})
        st.success(f"Nová verzia sadzieb uložená (platná od {platne_od}).")
        st.rerun()
    if b2.button("✏️ Prepísať zvolenú verziu", width="stretch"):
        nove_rates["platne_od"] = verzia["platne_od"]
        db.update("settings", verzia["id"],
                  {"rates_json": json.dumps(nove_rates, ensure_ascii=False)})
        st.success("Verzia sadzieb prepísaná.")
        st.rerun()

# ----------------------------------------------------------------- diéty ----
with tab_diety:
    st.caption("Číselník diét pre SK, CZ a AT (súbor data/per_diems_2026.csv). "
               "CZ v CZK, AT v EUR. Krátenie za jedlá (25/40/35 %) platí pre "
               "všetky krajiny. **Skontrolujte podľa platného opatrenia MF SR "
               "pre rok 2026.**")
    df = calc.load_per_diems()
    upravene = st.data_editor(df, hide_index=True, width="stretch",
                              disabled=["kod_krajiny"])
    if st.button("💾 Uložiť diéty"):
        calc.save_per_diems(upravene)
        st.success("Diéty uložené do data/per_diems_2026.csv.")

# ---------------------------------------------------------------- profil ----
with tab_profil:
    st.caption("Údaje sa použijú v **hlavičke PDF** dokumentov (cestovný príkaz, "
               "vyúčtovanie). Zadajte **sídlo firmy** — nie bydlisko zamestnanca "
               "(to sa eviduje pri zamestnancovi).")
    profil = ui.get_profil()
    c1, c2 = st.columns(2)
    with c1:
        nazov = st.text_input("Názov firmy", profil.get("nazov", ""))
        adresa = st.text_input("Sídlo (adresa firmy)", profil.get("adresa", ""),
                               help="Napr. Karpatské námestie 7770/10A, "
                                    "831 06 Bratislava")
    with c2:
        ico = st.text_input("IČO", profil.get("ico", ""))
        dic = st.text_input("DIČ", profil.get("dic", ""))
        icdph = st.text_input("IČ DPH (ak ste platiteľ DPH)", profil.get("icdph", ""))
    if st.button("💾 Uložiť údaje", type="primary"):
        db.set_config("profil", {"nazov": nazov, "adresa": adresa,
                                 "ico": ico, "dic": dic, "icdph": icdph})
        st.success("Údaje uložené.")

# ---------------------------------------------------------------- vzhľad ----
with tab_vzhlad:
    cfg_path = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"
    aktualna = "dark" if (cfg_path.exists() and 'base = "dark"' in
                          cfg_path.read_text(encoding="utf-8")) else "light"
    rezim = st.radio("Režim zobrazenia", ["light", "dark"],
                     index=0 if aktualna == "light" else 1,
                     format_func=lambda x: "☀️ Svetlý" if x == "light" else "🌙 Tmavý",
                     horizontal=True)
    if st.button("💾 Uložiť tému"):
        cfg_path.parent.mkdir(exist_ok=True)
        cfg_path.write_text(f'[theme]\nbase = "{rezim}"\n', encoding="utf-8")
        st.success("Téma uložená — obnovte stránku v prehliadači (F5), "
                   "aby sa zmena prejavila.")

# ------------------------------------------------------------ cloud sync ----
with tab_cloud:
    st.subheader("Automatická záloha do GitHub Gistu")
    st.write(cloud_sync.status_text())
    if cloud_sync.enabled():
        st.success("Sync je zapnutý. Po každej zmene sa dáta automaticky uložia "
                   "do súkromného gistu a pri otvorení appky sa načítajú späť. "
                   "Gist nereštartuje appku.")
        c1, c2 = st.columns(2)
        if c1.button("⬆️ Zálohovať teraz do cloudu", width="stretch"):
            st.success("Záloha uložená.") if cloud_sync.push() else \
                st.error(st.session_state.get("_sync_error") or "Zlyhalo.")
        if c2.button("⬇️ Načítať z cloudu (prepíše dáta)", width="stretch"):
            if cloud_sync.pull():
                st.success("Dáta načítané z cloudu.")
                st.rerun()
            else:
                st.warning("V cloude zatiaľ nie sú žiadne dáta "
                           "(alebo nastala chyba).")
        gid = st.session_state.get("_gist_id")
        if gid:
            st.caption(f"Gist: https://gist.github.com/{gid}")
    else:
        st.info("Sync je **vypnutý**. Zapnete ho pridaním tokenu do Streamlit "
                "secrets — potom appka prežije reštart bez straty dát.")
        st.markdown(
            "**Postup (jednorazovo, ~3 min):**\n"
            "1. GitHub → *Settings → Developer settings → Personal access "
            "tokens → Fine-grained tokens → Generate new token*.\n"
            "2. V sekcii **Account permissions → Gists** nastavte "
            "**Read and write**. Token skopírujte (začína `github_pat_…`).\n"
            "3. V Streamlit Cloude: *App → ⋮ → Settings → Secrets* a vložte:\n"
            "   ```toml\n"
            '   github_token = "github_pat_VAS_TOKEN"\n'
            "   ```\n"
            "4. Uložte secrets — appka sa reštartuje a sync sa zapne. Gist na "
            "zálohu sa vytvorí automaticky.\n\n"
            "Potom stačí raz nahrať dáta (napr. cez *Záloha dát → Obnoviť zo "
            "zálohy*) a od tej chvíle sa všetko ukladá samo.")
        st.caption("Token sa ukladá iba do Streamlit secrets (na server), "
                   "nikdy sa nezobrazuje v prehliadači. Odporúčame fine-grained "
                   "token obmedzený len na oprávnenie Gists.")

# ---------------------------------------------------------------- záloha ----
with tab_zaloha:
    if cloud_sync.enabled():
        st.info("ℹ️ Máte zapnutý **cloud sync** — dáta sa zálohujú automaticky. "
                "Manuálna záloha nižšie je doplnková (napr. na archiváciu).")
    else:
        st.warning("⚠️ **Streamlit Community Cloud má dočasné úložisko** — pri "
                   "reštarte sa SQLite databáza resetuje. Zapnite **Cloud sync** "
                   "(predošlá záložka), alebo si pravidelne sťahujte zálohu "
                   "a po reštarte ju obnovte.")

    st.divider()
    if db.is_empty():
        if st.button("🧪 Načítať ukážkové dáta (1 zamestnanec, vozidlo, "
                     "ukážkové cesty)"):
            db.seed_sample_data()
            st.success("Ukážkové dáta načítané.")
            st.rerun()
        st.divider()
    st.download_button(
        "⬇️ Stiahnuť zálohu celej databázy (JSON)",
        db.export_db_json().encode("utf-8"),
        file_name=f"cestaky_zaloha_{dt.date.today().isoformat()}.json",
        mime="application/json", type="primary")

    subor = st.file_uploader("Obnoviť databázu zo zálohy (JSON)", type=["json"])
    if subor is not None:
        st.error("Obnova **prepíše všetky existujúce dáta** v databáze.")
        if st.button("♻️ Obnoviť zo zálohy", type="secondary"):
            db.import_db_json(subor.read().decode("utf-8"))
            st.success("Databáza obnovená zo zálohy.")
            st.rerun()
