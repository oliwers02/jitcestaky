"""Štátne sviatky a dni pracovného pokoja v SR.

Pozn.: 1. september (Deň Ústavy SR) od roku 2024 nie je dňom pracovného
pokoja, preto sa do zoznamu voľných dní nezahŕňa.
"""
from __future__ import annotations

import datetime as dt


def _velka_noc(rok: int) -> dt.date:
    """Veľkonočná nedeľa — anonymný gregoriánsky algoritmus."""
    a = rok % 19
    b, c = divmod(rok, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mesiac = (h + l - 7 * m + 114) // 31
    den = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(rok, mesiac, den)


def sviatky_sk(rok: int) -> dict[dt.date, str]:
    """Vráti dni pracovného pokoja v SR pre daný rok (dátum -> názov)."""
    vn = _velka_noc(rok)
    sviatky = {
        dt.date(rok, 1, 1): "Deň vzniku Slovenskej republiky",
        dt.date(rok, 1, 6): "Zjavenie Pána (Traja králi)",
        vn - dt.timedelta(days=2): "Veľký piatok",
        vn + dt.timedelta(days=1): "Veľkonočný pondelok",
        dt.date(rok, 5, 1): "Sviatok práce",
        dt.date(rok, 5, 8): "Deň víťazstva nad fašizmom",
        dt.date(rok, 7, 5): "Sviatok sv. Cyrila a Metoda",
        dt.date(rok, 8, 29): "Výročie SNP",
        dt.date(rok, 9, 15): "Sedembolestná Panna Mária",
        dt.date(rok, 11, 1): "Sviatok všetkých svätých",
        dt.date(rok, 11, 17): "Deň boja za slobodu a demokraciu",
        dt.date(rok, 12, 24): "Štedrý deň",
        dt.date(rok, 12, 25): "Prvý sviatok vianočný",
        dt.date(rok, 12, 26): "Druhý sviatok vianočný",
    }
    return sviatky


def je_sviatok(datum: dt.date) -> bool:
    return datum in sviatky_sk(datum.year)


def je_vikend(datum: dt.date) -> bool:
    return datum.weekday() >= 5


def pracovne_dni(od: dt.date, do: dt.date,
                 vratane_vikendov: bool = False,
                 vratane_sviatkov: bool = False) -> list[dt.date]:
    """Zoznam dní v intervale <od, do> podľa zvolených pravidiel."""
    dni = []
    d = od
    while d <= do:
        if (vratane_vikendov or not je_vikend(d)) and \
           (vratane_sviatkov or not je_sviatok(d)):
            dni.append(d)
        d += dt.timedelta(days=1)
    return dni
