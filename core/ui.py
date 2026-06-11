"""Spoločné UI pomôcky pre stránky."""
from __future__ import annotations

import datetime as dt

import streamlit as st

from core import calc, db

MESIACE = ["Január", "Február", "Marec", "Apríl", "Máj", "Jún", "Júl",
           "August", "September", "Október", "November", "December"]


def eur(suma) -> str:
    return f"{float(suma or 0):,.2f} €".replace(",", " ").replace(".", ",")


def suma_mena(suma, mena: str) -> str:
    s = f"{float(suma or 0):,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} {'€' if mena == 'EUR' else mena}"


def vozidlo_label(v: dict) -> str:
    return (f"{v.get('znacka') or ''} {v.get('model') or ''} "
            f"({v.get('spz') or '—'})").strip()


def _default_index(rows: list[dict], default_id) -> int:
    return next((i for i, r in enumerate(rows) if r["id"] == default_id), 0)


def select_zamestnanec(key: str, len_aktivni: bool = True,
                       default_id: int | None = None) -> dict | None:
    where = "aktivny = 1" if len_aktivni else ""
    emps = db.fetch_all("employees", where, order="meno_priezvisko")
    if not emps:
        st.warning("Najprv pridajte zamestnanca na stránke **Zamestnanci**.")
        return None
    return st.selectbox("Zamestnanec", emps, key=key,
                        index=_default_index(emps, default_id),
                        format_func=lambda e: e["meno_priezvisko"])


def select_vozidlo(key: str, default_id: int | None = None) -> dict | None:
    vehs = db.fetch_all("vehicles", order="predvolene DESC, znacka")
    if not vehs:
        st.warning("Najprv pridajte vozidlo na stránke **Vozidlá**.")
        return None
    return st.selectbox("Vozidlo (súkromné)", vehs, key=key,
                        index=_default_index(vehs, default_id),
                        format_func=vozidlo_label)


def panel_pouzite_sadzby(datum, rates: dict, krajina: str = "SK") -> None:
    with st.expander(f"📋 Použité sadzby pre {datum} (platné od {rates['platne_od']})"):
        c1, c2, c3 = st.columns(3)
        c1.markdown(
            f"**Základná náhrada**\n\n"
            f"- osobné auto: {rates['zakladna_nahrada']['osobne_auto']:.3f} €/km\n"
            f"- motocykel: {rates['zakladna_nahrada']['motocykel']:.2f} €/km")
        phm = rates["ceny_phm"]
        c2.markdown(
            f"**Ceny PHM (ŠÚ SR)**\n\n"
            f"- benzín 95: {phm['benzin']:.2f} €/l\n"
            f"- diesel: {phm['diesel']:.2f} €/l\n"
            f"- LPG: {phm['lpg']:.2f} €/l\n"
            f"- CNG: {phm['cng']:.2f} €/kg")
        if krajina == "SK":
            s = rates["stravne_sk"]
            c3.markdown(
                f"**Stravné SK (§5)**\n\n"
                f"- 5 – 12 h: {s['pasmo_5_12']:.2f} €\n"
                f"- 12 – 18 h: {s['pasmo_12_18']:.2f} €\n"
                f"- nad 18 h: {s['pasmo_nad_18']:.2f} €")
        else:
            r = calc.per_diem_row(krajina)
            c3.markdown(
                f"**Diéty {krajina} ({r['mena']})**\n\n"
                f"- do 6 h: {float(r['do_6h']):.2f}\n"
                f"- 6 – 12 h: {float(r['od_6_do_12h']):.2f}\n"
                f"- 12 – 24 h: {float(r['od_12_do_24h']):.2f}")
        st.caption("Skontrolujte podľa platného opatrenia MF SR pre rok 2026. "
                   "Sadzby môžete upraviť v Nastaveniach.")


def get_profil() -> dict:
    return db.get_config("profil", {}) or {}


def cas_input(label: str, default: str, key: str) -> str:
    t = st.time_input(label, dt.time.fromisoformat(default), key=key, step=300)
    return t.strftime("%H:%M")
