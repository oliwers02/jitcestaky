"""Self-test súhrnných súčtov generátora (kontrolné hodnoty zo zadania).

Auto (PHM 199,14 + km 671,03)                         = 870,17 €
Stravné viacdňové (64,30 + 90 + 90 + 61,90)           = 306,20 €
Stravné jednodňové (9,30 + 12,38 + 9,30)              =  30,98 €
CELKOM                                                = 1 207,35 €

Súčasne overuje, že stravné jednodňovej cesty 14.6., ktorá spadá do
viacdňovej cesty RFP (14.–16.6.), sa NEzapočíta dvakrát.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core import calc, db  # noqa: E402

db.DB_PATH = Path(tempfile.gettempdir()) / "_totals_test.db"
db.DB_PATH.unlink(missing_ok=True)
db.init_db()

emp = db.insert("employees", {"meno_priezvisko": "Test Konateľ", "aktivny": 1})
veh = db.insert("vehicles", {"typ": "osobne_auto", "typ_paliva": "diesel",
                             "spotreba_l_100km": 5.6, "predvolene": 1})


def jednodnova(datum, phm, zakl, stravne):
    db.insert("trips", {
        "employee_id": emp, "vehicle_id": veh, "typ_dopravy": "sukromne_auto",
        "datum": datum, "cielova_krajina": "SK", "stravne_mena": "EUR",
        "vypocitana_phm_nahrada": phm, "vypocitana_zakladna_nahrada": zakl,
        "vypocitane_stravne": stravne,
        "nahrada_spolu": round(phm + zakl + stravne, 2)})


def viacdnova(nazov, od, do, krajina, dni_stravne):
    zahr = 0 if krajina == "SK" else 1
    bt = db.insert("business_trips", {
        "employee_id": emp, "nazov": nazov, "datum_zaciatku": od,
        "datum_konca": do, "zahranicna": zahr, "cielova_krajina": krajina,
        "status": "schvalena", "vreckove_percent": 0})
    d0 = calc.dt.date.fromisoformat(od)
    for i, s in enumerate(dni_stravne):
        db.insert("business_trip_days", {
            "business_trip_id": bt, "datum": (d0 + calc.dt.timedelta(days=i)).isoformat(),
            "typ_dna": "plny_den", "pocet_hodin": 24, "stravne_den_eur": s})
    return bt


# auto: celá náhrada za vozidlo v jednom „nosnom" riadku (PHM + km)
jednodnova("2026-06-01", 199.14, 671.03, 0.0)
# tri samostatné jednodňové cesty so stravným
jednodnova("2026-06-07", 0.0, 0.0, 9.30)
jednodnova("2026-06-12", 0.0, 0.0, 12.38)
jednodnova("2026-06-13", 0.0, 0.0, 9.30)
# DUPLICITA: jednodňová 14.6. spadá do viacdňovej RFP -> stravné sa nesmie rátať
jednodnova("2026-06-14", 0.0, 0.0, 9.30)

# štyri viacdňové cesty (diéty po dňoch, súčty zo zadania)
viacdnova("Bratislava", "2026-05-28", "2026-05-31", "SK", [20.60, 20.60, 13.80, 9.30])
viacdnova("NovaRock 1", "2026-06-02", "2026-06-03", "AT", [45.00, 45.00])
viacdnova("NovaRock 2", "2026-06-09", "2026-06-10", "AT", [45.00, 45.00])
viacdnova("RFP", "2026-06-14", "2026-06-16", "CZ", [24.76, 24.76, 12.38])

trips = db.fetch_all("trips")
bts = db.fetch_all("business_trips")
t = calc.compute_totals(trips, bts)

print("=== PREHĽAD ===")
print(f"Jednodňové cesty:        {len(trips)}")
print(f"Viacdňové cesty:         {len(bts)}")
print(f"Súčet auto (PHM + km):   {t['auto']:.2f} €   (kontrola 870.17)")
print(f"Stravné viacdňové:       {t['stravne_viacdnove']:.2f} €   (kontrola 306.20)")
print(f"Stravné jednodňové:      {t['stravne_jednodnove']:.2f} €   (kontrola 30.98)")
print(f"Stravné spolu:           {t['stravne_spolu']:.2f} €   (kontrola 337.18)")
print(f"CELKOM:                  {t['celkom']:.2f} €   (kontrola 1207.35)")
print(f"Duplicitné (vylúčené) jednodňové stravné: {len(t['overlap_trip_ids'])} (14.6. RFP)")

assert t["auto"] == 870.17, t["auto"]
assert t["stravne_viacdnove"] == 306.20, t["stravne_viacdnove"]
assert t["stravne_jednodnove"] == 30.98, t["stravne_jednodnove"]
assert t["stravne_spolu"] == 337.18, t["stravne_spolu"]
assert t["celkom"] == 1207.35, t["celkom"]
assert len(t["overlap_trip_ids"]) == 1, t["overlap_trip_ids"]

# krížová kontrola: v hárku Cesty má 14.6. stravné 0 a Diéty ho majú v RFP
from core import exporters  # noqa: E402
for tr in trips:
    tr["zamestnanec"] = "Test Konateľ"
    tr["vozidlo"] = "Test"
cesty_df = exporters.trips_to_df(trips, t["covered_days"])
r146 = cesty_df[cesty_df["Dátum"] == "2026-06-14"].iloc[0]
assert r146["Stravné"] == 0.0, r146["Stravné"]
assert round(float(exporters.diety_to_df(bts).query("Cesta == 'RFP'")["Stravné"].sum()), 2) == 61.90
# stravné nie je nikde dvakrát: súčet Cesty.Stravné(EUR) + Diéty = stravné spolu
cesty_stravne = round(float(cesty_df["Stravné"].sum()), 2)
diety_stravne = round(float(exporters.diety_to_df(bts)["Stravné"].sum()), 2)
assert round(cesty_stravne + diety_stravne, 2) == 337.18, (cesty_stravne, diety_stravne)
print("Krížová kontrola Cesty × Diéty: žiadne stravné dvakrát ✓")

print("\nTOTALS SELF-TEST PRESIEL")
