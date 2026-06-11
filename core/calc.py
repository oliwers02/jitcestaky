"""Výpočty náhrad a stravného podľa zákona č. 283/2002 Z. z. (sadzby 2026).

Iba súkromné vozidlá: náhrada = základná náhrada za km + náhrada za PHM
(§7), plus stravné podľa trvania cesty (§5, §13) s krátením za poskytnuté
jedlá (raňajky −25 %, obed −40 %, večera −35 %).
"""
from __future__ import annotations

import datetime as dt
import json
import math

import pandas as pd

from core import db

KRAJINY = {"SK": "Slovensko (tuzemské)", "CZ": "Česká republika", "AT": "Rakúsko"}

TYP_DOPRAVY = {"sukromne_auto": "Súkromné auto / motocykel",
               "verejna_doprava": "Verejná doprava"}
TYP_TRASY = {"dialnica": "Diaľnica", "mimo_dialnic": "Mimo diaľnic",
             "zmiesana": "Zmiešaná"}
TYP_PALIVA = {"benzin": "Benzín 95", "diesel": "Diesel", "lpg": "LPG",
              "cng": "CNG", "elektrina": "Elektrina"}
TYP_VOZIDLA = {"osobne_auto": "Osobné auto", "motocykel": "Motocykel"}
STATUSY = {"koncept": "Koncept", "odoslana": "Odoslaná",
           "schvalena": "Schválená", "zamietnuta": "Zamietnutá"}
TYP_DNA = {"odchod": "Deň odchodu", "plny_den": "Plný deň", "navrat": "Deň návratu"}


# ----------------------------------------------------------------- sadzby ---

def get_rates(datum: dt.date | str | None = None) -> dict:
    """Sadzby platné k dátumu (najnovšia verzia s platne_od <= dátum)."""
    if datum is None:
        datum = dt.date.today()
    if isinstance(datum, dt.date):
        datum = datum.isoformat()
    rows = db.query(
        "SELECT * FROM settings WHERE platne_od <= ? ORDER BY platne_od DESC, id DESC LIMIT 1",
        (datum,))
    if not rows:  # cesta pred prvou verziou sadzieb — použi najstaršiu
        rows = db.query("SELECT * FROM settings ORDER BY platne_od ASC, id ASC LIMIT 1")
    rates = json.loads(rows[0]["rates_json"])
    rates["platne_od"] = rows[0]["platne_od"]
    return rates


def load_per_diems() -> pd.DataFrame:
    df = pd.read_csv(db.PER_DIEMS_CSV, sep=";", dtype={"kod_krajiny": str})
    return df


def save_per_diems(df: pd.DataFrame) -> None:
    df.to_csv(db.PER_DIEMS_CSV, sep=";", index=False)


def per_diem_row(krajina: str) -> dict:
    df = load_per_diems()
    m = df[df["kod_krajiny"] == krajina]
    if m.empty:
        raise ValueError(f"Neznáma krajina v číselníku diét: {krajina}")
    return m.iloc[0].to_dict()


# ------------------------------------------------------------------- časy ---

def hodiny_trvania(cas_od: str | None, cas_do: str | None) -> float:
    """Trvanie v hodinách medzi dvoma časmi HH:MM v ten istý deň."""
    if not cas_od or not cas_do:
        return 0.0
    t1 = dt.datetime.strptime(cas_od, "%H:%M")
    t2 = dt.datetime.strptime(cas_do, "%H:%M")
    return max(0.0, (t2 - t1).total_seconds() / 3600)


def hodiny_do_polnoci(cas_od: str) -> float:
    t = dt.datetime.strptime(cas_od, "%H:%M")
    return 24.0 - (t.hour + t.minute / 60)


def hodiny_od_polnoci(cas_do: str) -> float:
    t = dt.datetime.strptime(cas_do, "%H:%M")
    return t.hour + t.minute / 60


# ---------------------------------------------------------------- stravné ---

def stravne_pre_hodiny(hodiny: float, krajina: str,
                       rates: dict | None = None) -> tuple[float, str, str]:
    """(suma, mena, názov pásma) pre daný počet hodín a krajinu.

    SK (tuzemské, §5): nárok od 5 h; pásma 5–12 / 12–18 / nad 18 h.
    CZ a AT (zahraničné, §13): pásma do 6 h / 6–12 h / 12–24 h.
    České diéty (CZK) sa prepočítavajú na EUR kurzom z nastavení
    (ECB referenčný kurz publikovaný NBS); bez kurzu ostávajú v CZK.
    """
    if krajina == "SK":
        r = (rates or get_rates())["stravne_sk"]
        if hodiny < 5:
            return 0.0, "EUR", "menej ako 5 h — bez nároku"
        if hodiny <= 12:
            return float(r["pasmo_5_12"]), "EUR", "5 – 12 h"
        if hodiny <= 18:
            return float(r["pasmo_12_18"]), "EUR", "12 – 18 h"
        return float(r["pasmo_nad_18"]), "EUR", "nad 18 h"

    row = per_diem_row(krajina)
    mena = row["mena"]
    if hodiny <= 0:
        suma, pasmo = 0.0, "0 h — bez nároku"
    elif hodiny < 6:
        suma, pasmo = float(row["do_6h"]), "do 6 h"
    elif hodiny < 12:
        suma, pasmo = float(row["od_6_do_12h"]), "6 – 12 h"
    else:
        suma, pasmo = float(row["od_12_do_24h"]), "12 – 24 h"

    if mena == "CZK":
        kurz = (rates or get_rates()).get("kurz_czk_eur")
        if kurz:
            if suma > 0:
                pasmo = f"{pasmo} ({suma:.0f} Kč)"
            return round(suma / float(kurz), 2), "EUR", pasmo
    return suma, mena, pasmo


def mena_stravneho(krajina: str, rates: dict | None = None) -> str:
    """Mena, v ktorej vychádza stravné: EUR všade okrem CZ bez zadaného kurzu."""
    if krajina == "CZ" and not (rates or get_rates()).get("kurz_czk_eur"):
        return "CZK"
    return "EUR"


def kratenie_jedal(suma: float, ranajky: bool, obed: bool, vecera: bool,
                   rates: dict | None = None) -> float:
    """Krátenie denného stravného za poskytnuté jedlá (§5 ods. 6, §13 ods. 7)."""
    k = (rates or get_rates()).get(
        "kratenie_jedal", {"ranajky": 0.25, "obed": 0.40, "vecera": 0.35})
    faktor = 1.0
    if ranajky:
        faktor -= k["ranajky"]
    if obed:
        faktor -= k["obed"]
    if vecera:
        faktor -= k["vecera"]
    return round(suma * max(0.0, faktor), 2)


def prepocet_na_eur(suma: float, mena: str, rates: dict | None = None) -> float | None:
    """Prepočet na EUR; pre CZK podľa kurzu v nastaveniach (None = nezadaný)."""
    if mena == "EUR":
        return suma
    kurz = (rates or get_rates()).get("kurz_czk_eur")
    if mena == "CZK" and kurz:
        return round(suma / float(kurz), 2)
    return None


# ----------------------------------------------------- jednodňová cesta -----

def cena_paliva(vozidlo: dict, rates: dict,
                cena_z_dokladu: float | None = None) -> float:
    """Cena PHM: doklad podľa §7 ods. 5 má prednosť, inak priemer ŠÚ SR."""
    if cena_z_dokladu:
        return float(cena_z_dokladu)
    return float(rates["ceny_phm"].get(vozidlo.get("typ_paliva", "benzin"), 0))


def vypocitaj_jednodnovu(trip: dict, vozidlo: dict | None) -> dict:
    """Vypočíta náhrady jednodňovej cesty; vráti doplnené polia."""
    rates = get_rates(trip["datum"])
    km = float(trip.get("vzdialenost_km") or 0)
    phm = zakladna = 0.0

    if trip.get("typ_dopravy") == "sukromne_auto" and vozidlo:
        cena = cena_paliva(vozidlo, rates, trip.get("cena_phm_z_dokladu_eur_l"))
        spotreba = float(vozidlo.get("spotreba_l_100km") or 0)
        phm = round(km / 100 * spotreba * cena, 2)
        sadzba_km = rates["zakladna_nahrada"].get(
            vozidlo.get("typ", "osobne_auto"), 0.313)
        zakladna = round(km * float(sadzba_km), 2)

    krajina = trip.get("cielova_krajina") or "SK"
    if not trip.get("zahranicna"):
        krajina = "SK"
    hodiny = hodiny_trvania(trip.get("cas_odchodu"), trip.get("cas_prichodu"))
    stravne, mena, pasmo = stravne_pre_hodiny(hodiny, krajina, rates)

    vreckove = 0.0
    if trip.get("zahranicna") and stravne > 0:
        vreckove = round(stravne * float(trip.get("vreckove_percent") or 0) / 100, 2)

    vedlajsie = float(trip.get("vedlajsie_vydavky_eur") or 0)
    stravne_eur = prepocet_na_eur(stravne, mena, rates)
    vreckove_eur = prepocet_na_eur(vreckove, mena, rates)
    spolu = round(phm + zakladna + vedlajsie
                  + (stravne_eur or 0) + (vreckove_eur or 0), 2)

    return {
        "vypocitana_phm_nahrada": phm,
        "vypocitana_zakladna_nahrada": zakladna,
        "vypocitane_stravne": round(stravne, 2),
        "stravne_mena": mena,
        "vypocitane_vreckove": vreckove,
        "nahrada_spolu": spolu,
        "_hodiny": round(hodiny, 2),
        "_pasmo": pasmo,
        "_rates": rates,
        "_stravne_prepocitane": stravne_eur is not None,
    }


# ---------------------------------------------------- viacdňová cesta -------

def rozpis_dni(datum_zaciatku: str, datum_konca: str,
               cas_odchodu: str, cas_navratu: str) -> list[dict]:
    """Denný rozpis: prvý deň od odchodu do 24:00, stredné dni 24 h,
    posledný deň od 00:00 do návratu. Každý deň sa posudzuje samostatne."""
    d1 = dt.date.fromisoformat(str(datum_zaciatku))
    d2 = dt.date.fromisoformat(str(datum_konca))
    dni = []
    if d1 == d2:
        dni.append({"datum": d1.isoformat(), "typ_dna": "odchod",
                    "pocet_hodin": round(hodiny_trvania(cas_odchodu, cas_navratu), 2)})
        return dni
    d = d1
    while d <= d2:
        if d == d1:
            typ, hod = "odchod", hodiny_do_polnoci(cas_odchodu or "00:00")
        elif d == d2:
            typ, hod = "navrat", hodiny_od_polnoci(cas_navratu or "23:59")
        else:
            typ, hod = "plny_den", 24.0
        dni.append({"datum": d.isoformat(), "typ_dna": typ,
                    "pocet_hodin": round(hod, 2)})
        d += dt.timedelta(days=1)
    return dni


def prepocitaj_dni(bt: dict, dni: list[dict]) -> list[dict]:
    """Doplní stravné každého dňa podľa pásma a krátenia za jedlá."""
    krajina = bt.get("cielova_krajina") or "SK"
    if not bt.get("zahranicna"):
        krajina = "SK"
    for d in dni:
        rates = get_rates(d["datum"])
        zaklad, mena, pasmo = stravne_pre_hodiny(d["pocet_hodin"], krajina, rates)
        d["stravne_den_eur"] = kratenie_jedal(
            zaklad, bool(d.get("ranajky_poskytnute")),
            bool(d.get("obed_poskytnuty")), bool(d.get("vecera_poskytnuta")), rates)
        d["_mena"] = mena
        d["_pasmo"] = pasmo
        d["_zaklad"] = zaklad
    return dni


def suhrn_viacdnovej(bt: dict, dni: list[dict]) -> dict:
    """KPI súhrn viacdňovej cesty (stravné v mene krajiny, ostatné v EUR)."""
    krajina = bt.get("cielova_krajina") or "SK"
    if not bt.get("zahranicna"):
        krajina = "SK"
    rates_bt = get_rates(bt["datum_zaciatku"])
    mena = mena_stravneho(krajina, rates_bt)
    stravne = round(sum(float(d.get("stravne_den_eur") or 0) for d in dni), 2)
    vreckove = round(stravne * float(bt.get("vreckove_percent") or 0) / 100, 2)
    stravne_eur = prepocet_na_eur(stravne, mena, rates_bt)
    vreckove_eur = prepocet_na_eur(vreckove, mena, rates_bt)
    ostatne = (float(bt.get("ubytovanie_eur") or 0)
               + float(bt.get("kilometrovne_eur") or 0)
               + float(bt.get("navstevy_rodiny_eur") or 0))
    spolu_eur = None
    if stravne_eur is not None and vreckove_eur is not None:
        spolu_eur = round(ostatne + stravne_eur + vreckove_eur, 2)
    d1 = dt.date.fromisoformat(str(bt["datum_zaciatku"]))
    d2 = dt.date.fromisoformat(str(bt["datum_konca"]))
    return {
        "trvanie_dni": (d2 - d1).days + 1,
        "stravne": stravne, "mena": mena,
        "vreckove": vreckove,
        "stravne_eur": stravne_eur, "vreckove_eur": vreckove_eur,
        "ostatne_eur": round(ostatne, 2),
        "spolu_eur": spolu_eur,
    }


# ------------------------------------------------------------- haversine ----

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Vzdušná vzdialenosť dvoch bodov v km (offline, bez API)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)
