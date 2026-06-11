"""Smoke test výpočtov a exportov (spúšťa sa mimo Streamlitu)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core import calc, db, exporters, holidays_sk  # noqa: E402

db.init_db()

# --- sadzby ---
r = calc.get_rates("2026-05-12")
assert r["zakladna_nahrada"]["osobne_auto"] == 0.313, r
assert r["ceny_phm"]["benzin"] == 1.70
print("OK sadzby:", r["platne_od"])

# --- jednodňová cesta (príklad z README) ---
voz = {"typ": "osobne_auto", "typ_paliva": "benzin", "spotreba_l_100km": 6.1}
trip = {"datum": "2026-05-12", "typ_dopravy": "sukromne_auto",
        "cas_odchodu": "07:30", "cas_prichodu": "17:30",
        "vzdialenost_km": 180, "vedlajsie_vydavky_eur": 4.50,
        "zahranicna": 0, "cielova_krajina": "SK"}
v = calc.vypocitaj_jednodnovu(trip, voz)
assert v["vypocitana_phm_nahrada"] == 18.67, v
assert v["vypocitana_zakladna_nahrada"] == 56.34, v
assert v["vypocitane_stravne"] == 9.30, v
assert v["nahrada_spolu"] == 88.81, v
print("OK jednodnova:", v["nahrada_spolu"], "EUR")

# --- cena z dokladu (§7 ods. 5) ---
trip2 = dict(trip, cena_phm_z_dokladu_eur_l=1.80)
v2 = calc.vypocitaj_jednodnovu(trip2, voz)
assert v2["vypocitana_phm_nahrada"] == round(1.8 * 6.1 * 1.80, 2), v2
print("OK cena z dokladu:", v2["vypocitana_phm_nahrada"])

# --- motocykel ---
moto = {"typ": "motocykel", "typ_paliva": "benzin", "spotreba_l_100km": 4.0}
v3 = calc.vypocitaj_jednodnovu(dict(trip, vzdialenost_km=100), moto)
assert v3["vypocitana_zakladna_nahrada"] == 9.00, v3
print("OK motocykel: 0.09 EUR/km")

# --- stravné pásma SK ---
assert calc.stravne_pre_hodiny(4.9, "SK")[0] == 0
assert calc.stravne_pre_hodiny(5, "SK")[0] == 9.30
assert calc.stravne_pre_hodiny(12.5, "SK")[0] == 13.80
assert calc.stravne_pre_hodiny(19, "SK")[0] == 20.60
# --- CZ bez kurzu ostáva v CZK ---
bez_kurzu = {"kurz_czk_eur": None}
assert calc.stravne_pre_hodiny(5, "CZ", bez_kurzu) == (150.0, "CZK", "do 6 h")
assert calc.stravne_pre_hodiny(8, "CZ", bez_kurzu)[0] == 300.0
assert calc.stravne_pre_hodiny(24, "CZ", bez_kurzu)[0] == 600.0
# --- CZ s predvoleným kurzom 24.231 (ECB/NBS) -> EUR ---
s, m, p = calc.stravne_pre_hodiny(8, "CZ")
assert (s, m) == (12.38, "EUR") and "300" in p, (s, m, p)
assert calc.stravne_pre_hodiny(24, "CZ")[0] == 24.76
assert calc.stravne_pre_hodiny(5, "CZ")[0] == 6.19
assert calc.stravne_pre_hodiny(3, "AT")[0] == 11.25
assert calc.stravne_pre_hodiny(11.9, "AT")[0] == 22.50
assert calc.stravne_pre_hodiny(12, "AT")[0] == 45.00
print("OK pasma SK/CZ/AT")

# --- krátenie jedál ---
assert calc.kratenie_jedal(45.0, True, False, False) == 33.75   # -25 %
assert calc.kratenie_jedal(45.0, False, True, False) == 27.00   # -40 %
assert calc.kratenie_jedal(45.0, True, True, True) == 0.00      # -100 %
assert calc.kratenie_jedal(20.60, False, False, True) == 13.39  # -35 %
print("OK kratenie jedal")

# --- viacdňový rozpis (AT, odchod 6:00, návrat o 2 dni 19:00) ---
bt = {"datum_zaciatku": "2026-05-18", "datum_konca": "2026-05-20",
      "zahranicna": 1, "cielova_krajina": "AT", "vreckove_percent": 40,
      "ubytovanie_eur": 240.0, "kilometrovne_eur": 178.0, "navstevy_rodiny_eur": 0}
dni = calc.rozpis_dni(bt["datum_zaciatku"], bt["datum_konca"], "06:00", "19:00")
assert [d["typ_dna"] for d in dni] == ["odchod", "plny_den", "navrat"]
assert dni[0]["pocet_hodin"] == 18.0 and dni[2]["pocet_hodin"] == 19.0
dni = calc.prepocitaj_dni(bt, dni)
assert dni[0]["stravne_den_eur"] == 45.00      # 18 h -> 12-24 h
assert dni[1]["stravne_den_eur"] == 45.00      # plný deň
dni[1]["ranajky_poskytnute"] = 1
dni = calc.prepocitaj_dni(bt, dni)
assert dni[1]["stravne_den_eur"] == 33.75
s = calc.suhrn_viacdnovej(bt, dni)
assert s["trvanie_dni"] == 3 and s["mena"] == "EUR"
assert s["stravne"] == 123.75 and s["vreckove"] == 49.50
assert s["spolu_eur"] == round(240 + 178 + 123.75 + 49.50, 2)
print("OK viacdnova AT:", s)

# --- CZ viacdňová: diéty prepočítané na EUR predvoleným kurzom ---
bt_cz = dict(bt, cielova_krajina="CZ")
dni_cz = calc.prepocitaj_dni(bt_cz, calc.rozpis_dni(
    bt["datum_zaciatku"], bt["datum_konca"], "06:00", "19:00"))
s_cz = calc.suhrn_viacdnovej(bt_cz, dni_cz)
assert s_cz["mena"] == "EUR", s_cz
assert s_cz["stravne"] == 74.28, s_cz          # 3 × 600 CZK / 24.231
assert s_cz["vreckove"] == 29.71               # 40 %
assert s_cz["spolu_eur"] == round(240 + 178 + 74.28 + 29.71, 2)
print("OK viacdnova CZ (kurz 24.231):", s_cz["stravne"], "EUR")

# --- sviatky ---
sv = holidays_sk.sviatky_sk(2026)
import datetime as dt
assert dt.date(2026, 4, 3) in sv      # Veľký piatok 2026
assert dt.date(2026, 4, 6) in sv      # Veľkonočný pondelok 2026
assert dt.date(2026, 9, 1) not in sv  # 1.9. už nie je deň prac. pokoja
dni_maj = holidays_sk.pracovne_dni(dt.date(2026, 5, 1), dt.date(2026, 5, 31))
assert dt.date(2026, 5, 1) not in dni_maj and dt.date(2026, 5, 8) not in dni_maj
print("OK sviatky 2026, prac. dni maj:", len(dni_maj))

# --- haversine ---
d = calc.haversine_km(48.1486, 17.1077, 49.2194, 18.7408)  # BA -> ZA
assert 160 < d < 180, d
print("OK haversine BA-ZA:", d, "km")

# --- exporty ---
trips = db.fetch_all("trips")
bts = db.fetch_all("business_trips")
for t in trips:
    t["zamestnanec"] = "Ján Vzorový"
    t["vozidlo"] = "Škoda Octavia (ZA123BC)"
for b in bts:
    b["zamestnanec"] = "Ján Vzorový"
tdf = exporters.trips_to_df(trips)
ddf = exporters.diety_to_df(bts)
suhrn = {"Obdobie": "2026", "Počet ciest": len(trips)}
profil = {"nazov": "Ján Vzorový", "adresa": "Hlavná 1, Žilina", "ico": "12345678"}

xlsx = exporters.export_xlsx(tdf, ddf, suhrn)
assert xlsx[:2] == b"PK" and len(xlsx) > 4000
csv_1250 = exporters.export_csv(tdf, ";", "cp1250")
assert ";".encode() in csv_1250 and "Dátum".encode("cp1250") in csv_1250
csv_utf = exporters.export_csv(tdf, ";", "utf-8")
assert csv_utf.startswith("﻿".encode("utf-8"))
dni_map = {b["id"]: db.fetch_all("business_trip_days", "business_trip_id = ?", (b["id"],))
           for b in bts}
xml = exporters.export_xml(trips, bts, dni_map)
assert b"<cestovne_prikazy" in xml and b"<cesta" in xml and b"<diety>" in xml
emp = db.fetch_all("employees")[0]
pdf1 = exporters.pdf_cestovny_prikaz(bts[0], emp, profil)
dni_bt = dni_map[bts[0]["id"]]
s0 = calc.suhrn_viacdnovej(bts[0], dni_bt)
pdf2 = exporters.pdf_vyuctovanie(bts[0], emp, profil, dni_bt, s0)
pdf3 = exporters.pdf_prehlad(tdf, ddf, suhrn, profil, "Cestovné príkazy 2026")
for p in (pdf1, pdf2, pdf3):
    assert p[:5] == b"%PDF-" and len(p) > 1000
print("OK exporty: XLSX", len(xlsx), "B | CSV", len(csv_1250), "B | XML",
      len(xml), "B | PDF", len(pdf1), len(pdf2), len(pdf3), "B")

# --- záloha/obnova DB ---
zaloha = db.export_db_json()
db.import_db_json(zaloha)
assert len(db.fetch_all("trips")) == len(trips)
print("OK zaloha/obnova DB JSON")

print("\nVSETKY TESTY PRESLI")
