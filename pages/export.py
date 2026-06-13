"""Export — XLSX / PDF / CSV / XML pre účtovníctvo."""
import datetime as dt

import streamlit as st

from core import calc, db, exporters, ui

st.title("📤 Export pre účtovníctvo")

emps = {e["id"]: e for e in db.fetch_all("employees")}
vehs = {v["id"]: v for v in db.fetch_all("vehicles")}

# ---------------------------------------------------------------- filtre ----
c1, c2, c3 = st.columns(3)
typ_ciest = c1.multiselect("Typ ciest", ["Jednodňové", "Viacdňové"],
                           default=["Jednodňové", "Viacdňové"])
rok = c2.selectbox("Rok", list(range(dt.date.today().year, 2023, -1)))
mesiac = c3.selectbox("Obdobie", ["Celý rok"] + ui.MESIACE)

c4, c5 = st.columns(2)
f_emp = c4.selectbox("Zamestnanec", [None] + list(emps.values()),
                     format_func=lambda e: "Všetci" if e is None else e["meno_priezvisko"])
f_veh = c5.selectbox("Vozidlo", [None] + list(vehs.values()),
                     format_func=lambda v: "Všetky" if v is None else ui.vozidlo_label(v))

if mesiac == "Celý rok":
    od, do = f"{rok}-01-01", f"{rok}-12-31"
else:
    m = ui.MESIACE.index(mesiac) + 1
    od = f"{rok}-{m:02d}-01"
    posledny = (dt.date(rok + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))
    do = posledny.isoformat()

# ------------------------------------------------------------------ dáta ----
trips = []
if "Jednodňové" in typ_ciest:
    where = "datum BETWEEN ? AND ?"
    params: list = [od, do]
    if f_emp:
        where += " AND employee_id = ?"
        params.append(f_emp["id"])
    if f_veh:
        where += " AND vehicle_id = ?"
        params.append(f_veh["id"])
    trips = db.fetch_all("trips", where, tuple(params), order="datum")
    for t in trips:
        t["zamestnanec"] = emps.get(t["employee_id"], {}).get("meno_priezvisko", "")
        v = vehs.get(t["vehicle_id"])
        t["vozidlo"] = ui.vozidlo_label(v) if v else "verejná doprava"

bts = []
if "Viacdňové" in typ_ciest:
    where = "datum_zaciatku <= ? AND datum_konca >= ?"
    params = [do, od]
    if f_emp:
        where += " AND employee_id = ?"
        params.append(f_emp["id"])
    bts = db.fetch_all("business_trips", where, tuple(params), order="datum_zaciatku")
    for b in bts:
        b["zamestnanec"] = emps.get(b["employee_id"], {}).get("meno_priezvisko", "")

# Konzistentné súčty bez duplicity stravného (stravné viacdňovej cesty
# žije len v Diétach; jednodňová cesta v deň pokrytý viacdňovou ho nemá).
totals = calc.compute_totals(trips, bts)
trips_df = exporters.trips_to_df(trips, totals["covered_days"])
diety_df = exporters.diety_to_df(bts)

# ---------------------------------------------------------------- náhľad ----
st.divider()
spolu_km = sum(float(t["vzdialenost_km"] or 0) for t in trips)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Jednodňové / viacdňové", f"{len(trips)} / {len(bts)}")
k2.metric("Náhrada za auto (PHM + km)", ui.eur(totals["auto"]))
k3.metric("Stravné spolu", ui.eur(totals["stravne_spolu"]))
k4.metric("CELKOM náhrady", ui.eur(totals["celkom"]))
if totals["overlap_trip_ids"]:
    st.caption(f"ℹ️ {len(totals['overlap_trip_ids'])} jednodňových ciest spadá "
               "do viacdňovej cesty — ich stravné je rátané len v Diétach "
               "(v hárku Cesty je pri nich 0, aby nevznikla duplicita).")

if trips:
    st.dataframe(trips_df, hide_index=True, width="stretch")
if not diety_df.empty:
    st.subheader("Diéty viacdňových ciest")
    st.dataframe(diety_df, hide_index=True, width="stretch")

if not trips and not bts:
    st.info("Vo zvolenom období nie sú žiadne cesty.")
    st.stop()

# --------------------------------------------------------------- exporty ----
st.divider()
st.subheader("Stiahnuť export")

obdobie = f"{rok}" if mesiac == "Celý rok" else f"{rok}_{ui.MESIACE.index(mesiac) + 1:02d}"
suhrn = {
    "Obdobie": f"{od} – {do}",
    "Počet jednodňových ciest": len(trips),
    "Počet viacdňových ciest": len(bts),
    "Najazdené km": round(spolu_km, 1),
    "Náhrada za auto (PHM + základná náhrada za km) (EUR)": totals["auto"],
    "Stravné jednodňové (EUR)": totals["stravne_jednodnove"],
    "Stravné viacdňové – diéty (EUR)": totals["stravne_viacdnove"],
    "Stravné spolu (EUR)": totals["stravne_spolu"],
    "Ubytovanie + iné výdavky (EUR)": totals["ostatne"],
    "CELKOM cestovné náhrady (EUR)": totals["celkom"],
    "Vygenerované": dt.date.today().isoformat(),
}
profil = ui.get_profil()

csv1, csv2 = st.columns(2)
oddelovac = csv1.selectbox("CSV oddeľovač", [";", ","],
                           help="Pre MRP / Money S3 / Pohoda zvyčajne ';'")
kodovanie = csv2.selectbox("CSV kódovanie", ["windows-1250", "utf-8"],
                           help="SK účtovné programy zvyčajne Windows-1250.")

e1, e2, e3, e4 = st.columns(4)
e1.download_button(
    "📊 XLSX", exporters.export_xlsx(trips_df, diety_df, suhrn),
    file_name=f"cestaky_{obdobie}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    width="stretch")
e2.download_button(
    "📄 PDF", exporters.pdf_prehlad(trips_df, diety_df, suhrn, profil,
                                    f"Cestovné príkazy {obdobie}"),
    file_name=f"cestaky_{obdobie}.pdf", mime="application/pdf", width="stretch")
e3.download_button(
    "🧾 CSV", exporters.export_csv(trips_df if not trips_df.empty else diety_df,
                                   sep=oddelovac,
                                   encoding="cp1250" if kodovanie == "windows-1250" else "utf-8"),
    file_name=f"cestaky_{obdobie}.csv", mime="text/csv", width="stretch")
dni_map = {b["id"]: db.fetch_all("business_trip_days", "business_trip_id = ?",
                                 (b["id"],), order="datum") for b in bts}
e4.download_button(
    "🗂️ XML", exporters.export_xml(trips, bts, dni_map),
    file_name=f"cestaky_{obdobie}.xml", mime="application/xml", width="stretch")

st.caption("CSV je pripravené na import do účtovného softvéru (MRP, Money S3, "
           "Pohoda) — oddeľovač ';' a kódovanie Windows-1250 sú predvolené pre "
           "SK programy. XML obsahuje štruktúru <cestovne_prikazy><cesta>…")

# ----------------------------------- hromadné PDF (príkazy + vyúčtovania) ----
st.divider()
st.subheader("🗜️ Hromadné PDF príkazy a vyúčtovania (ZIP)")
st.caption("Vyber cesty, typy dokumentov a stiahni všetky podpísané PDF naraz "
           "v jednom ZIP archíve.")

emps_full = {e["id"]: e for e in db.fetch_all("employees")}


def _trip_label(t):
    return (f"{t['datum']} • {t.get('miesto_zaciatku') or ''} → "
            f"{t.get('ciel_cesty') or ''}").strip(" •→")


def _bt_label(b):
    return f"{b['datum_zaciatku']}–{b['datum_konca']} • {b.get('nazov') or 'cesta'}"


sel_trips = st.multiselect("Jednodňové cesty", trips, default=trips,
                           format_func=_trip_label) if trips else []
sel_bts = st.multiselect("Viacdňové cesty", bts, default=bts,
                         format_func=_bt_label) if bts else []

d1, d2 = st.columns(2)
chk_prikaz = d1.checkbox("Zahrnúť cestovné príkazy", value=True)
chk_vyuct = d2.checkbox("Zahrnúť vyúčtovania", value=True)

if st.button("📦 Pripraviť ZIP", type="primary",
             disabled=not (sel_trips or sel_bts) or not (chk_prikaz or chk_vyuct)):
    items: list[tuple[str, bytes]] = []
    for t in sel_trips:
        zam = emps_full.get(t["employee_id"], {})
        v = vehs.get(t["vehicle_id"])
        vstr = ui.vozidlo_label(v) if v else "verejná doprava"
        zslug = exporters._slug(zam.get("meno_priezvisko", "")[:20] or "zam")
        base = f"{t['datum']}_{exporters._slug(t.get('ciel_cesty') or 'cesta')}_{zslug}"
        if chk_prikaz:
            items.append((f"jednodnove/prikaz_{base}.pdf",
                          exporters.pdf_prikaz_jednodnova(t, zam, profil, vstr)))
        if chk_vyuct:
            items.append((f"jednodnove/vyuctovanie_{base}.pdf",
                          exporters.pdf_vyuctovanie_jednodnova(t, zam, profil, vstr)))
    for b in sel_bts:
        zam = emps_full.get(b["employee_id"], {})
        dni = db.fetch_all("business_trip_days", "business_trip_id = ?",
                           (b["id"],), order="datum")
        s = calc.suhrn_viacdnovej(b, dni)
        base = f"{b['datum_zaciatku']}_{exporters._slug(b.get('nazov') or 'cesta')}"
        if chk_prikaz:
            items.append((f"viacdnove/prikaz_{base}.pdf",
                          exporters.pdf_cestovny_prikaz(b, zam, profil)))
        if chk_vyuct:
            items.append((f"viacdnove/vyuctovanie_{base}.pdf",
                          exporters.pdf_vyuctovanie(b, zam, profil, dni, s)))
    st.session_state["bulk_zip"] = exporters.build_zip(items)
    st.session_state["bulk_zip_name"] = f"prikazy_vyuctovania_{obdobie}.zip"
    st.session_state["bulk_zip_count"] = len(items)

if st.session_state.get("bulk_zip"):
    st.success(f"Pripravených {st.session_state['bulk_zip_count']} PDF dokumentov.")
    st.download_button(
        "⬇️ Stiahnuť ZIP", st.session_state["bulk_zip"],
        file_name=st.session_state["bulk_zip_name"],
        mime="application/zip", type="primary", width="stretch")
