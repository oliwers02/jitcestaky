# 🚗 MojeCestaky-Lite

Webová aplikácia na evidenciu **cestovných príkazov** podľa slovenskej
legislatívy pre rok **2026** (zákon č. 283/2002 Z. z. o cestovných náhradách),
postavená na **Streamlit** — beží lokálne aj na **Streamlit Community Cloud
(free tier)** bez akýchkoľvek platených služieb a API kľúčov.

> Aplikácia je určená pre prípad, keď sa na pracovné cesty používajú
> **výhradne súkromné vozidlá** (osobné auto / motocykel). Firemné vozidlá
> sa neevidujú.

## Funkcie

- **Jednodňové cesty** — automatický výpočet PHM náhrady, základnej náhrady
  (0,313 €/km osobné auto, 0,09 €/km motocykel) a stravného podľa
  odpracovaných hodín; podpora ceny PHM z dokladu (§7 ods. 5).
- **Viacdňové cesty** — denný rozpis stravného (deň odchodu / plné dni / deň
  návratu), krátenie za poskytnuté jedlá (raňajky −25 %, obed −40 %,
  večera −35 %), vreckové pri zahraničných cestách (do 40 %), statusy
  (koncept → odoslaná → schválená/zamietnutá) s povinným súhlasom
  zamestnanca (§3).
- **Diéty SK / CZ / AT** — editovateľný číselník pásiem
  (`data/per_diems_2026.csv`); české diéty (v CZK) sa automaticky
  prepočítavajú na EUR predvoleným kurzom **24,231 CZK/EUR** (ECB referenčný
  kurz publikovaný NBS, jún 2026 — editovateľný v Nastaveniach), AT v EUR.
- **Kopírovanie ciest** — jednodňovú cestu skopírujete tlačidlom
  „📋 Kopírovať" (predvyplní trasu, km, vozidlo aj účel — stačí zmeniť dátum
  a čas); viacdňovú cestu cez „Kopírovať cestu s novým termínom" v detaile.
- **Generátor ciest** — hromadné vytvorenie ciest za obdobie s rešpektovaním
  víkendov a slovenských štátnych sviatkov, viac trás s percentuálnym
  rozdelením dní.
- **Exporty pre účtovníctvo** — XLSX (hárky Súhrn / Cesty / Diéty),
  PDF (Cestovný príkaz, Vyúčtovanie pracovnej cesty, súhrnný report),
  CSV (oddeľovač `;`, kódovanie Windows-1250 alebo UTF-8 — vhodné pre MRP,
  Money S3, Pohoda) a XML.
- **Reporty** — ročné a mesačné prehľady, tuzemské vs zahraničné, štatistiky
  podľa vozidiel.
- **Nastavenia** — všetky sadzby editovateľné s verzovaním „platné od";
  fakturačné údaje do hlavičky PDF; svetlý/tmavý režim; záloha dát.

## Predvolené sadzby (platné od 1. 1. 2026)

| Položka | Hodnota |
|---|---|
| Základná náhrada — osobné auto | 0,313 €/km |
| Základná náhrada — motocykel | 0,09 €/km |
| Benzín 95 / Diesel / LPG | 1,70 / 1,63 / 0,87 €/l |
| Stravné SK 5–12 h / 12–18 h / nad 18 h | 9,30 / 13,80 / 20,60 € |
| Diéty CZ do 6 h / 6–12 h / 12–24 h | 150 / 300 / 600 CZK |
| Kurz CZK → EUR (ECB/NBS) | 24,231 CZK za 1 € |
| Diéty AT do 6 h / 6–12 h / 12–24 h | 11,25 / 22,50 / 45,00 € |

> ⚠️ Hodnoty skontrolujte podľa platného opatrenia MF SR pre rok 2026 —
> všetky sú editovateľné v **Nastaveniach**.

## Overenie výpočtu na príklade

Jednodňová cesta 180 km (tam a späť), Škoda Octavia benzín so spotrebou
6,1 l/100 km, trvanie 10 h, vedľajšie výdavky 4,50 €:

```
PHM náhrada       = 180 / 100 × 6,1 × 1,70 = 18,67 €
Základná náhrada  = 180 × 0,313            = 56,34 €
Stravné (5–12 h)  =                           9,30 €
Vedľajšie výdavky =                           4,50 €
SPOLU             =                          88,81 €
```

Viacdňová cesta do Rakúska (odchod 6:00, návrat o dva dni 19:00):
deň odchodu 18 h → 45,00 €; plný deň 24 h → 45,00 €, s poskytnutými
raňajkami −25 % → 33,75 €; deň návratu 19 h → pásmo 12–24 h.

## Lokálne spustenie

```bash
pip install -r requirements.txt
streamlit run app.py
```

Aplikácia sa otvorí na <http://localhost:8501>. Pri prvom spustení sa
vytvorí SQLite databáza `data/cestaky.db` s ukážkovými dátami.

## Nasadenie na Streamlit Community Cloud (zadarmo)

1. Nahrajte projekt do verejného (alebo súkromného) GitHub repozitára.
2. Na <https://share.streamlit.io> kliknite **New app**, vyberte repozitár,
   vetvu a ako hlavný súbor `app.py`.
3. Deploy — žiadne API kľúče ani secrets nie sú potrebné.

### ⚠️ Dôležité: perzistencia dát na free tieri

Streamlit Community Cloud má **dočasné (ephemeral) úložisko** — súborový
systém sa resetuje pri každom reštarte kontajnera, novom nasadení alebo po
dlhšej neaktivite appky. **SQLite databáza sa pri tom zmaže.**

Sú dve riešenia:

#### A) Automatická záloha do GitHub Gistu (odporúčané)

Appka vie po každej zmene automaticky uložiť celú databázu do **súkromného
GitHub Gistu** a pri otvorení si ju načítať späť. Gist (na rozdiel od commitu
do nasadeného repozitára) **nereštartuje** appku, je zadarmo a stačí naň jeden
token.

Nastavenie (jednorazovo, ~3 min):

1. GitHub → *Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token*.
2. **Account permissions → Gists → Read and write**. Token skopírujte
   (`github_pat_…`).
3. V Streamlit Cloude: *App → ⋮ → Settings → Secrets* vložte:
   ```toml
   github_token = "github_pat_VAS_TOKEN"
   ```
4. Uložte — appka sa reštartuje, sync sa zapne a gist na zálohu sa vytvorí
   automaticky. Stav vidíte v **Nastavenia → ☁️ Cloud sync** aj v bočnom paneli.

Od tej chvíle sa každá pridaná/upravená cesta uloží sama a po reštarte sa
dáta načítajú späť. Voliteľne viete určiť konkrétny gist cez
`gist_id = "…"` v secrets.

#### B) Manuálna záloha (bez tokenu)

1. **Nastavenia → 💾 Záloha dát → Stiahnuť zálohu celej databázy (JSON)**.
2. Po reštarte: **Obnoviť databázu zo zálohy**.

Pri lokálnom behu sa dáta ukladajú trvalo do `data/cestaky.db`, takže záloha
ani token nie sú potrebné. Ukážkové dáta sa už nevkladajú automaticky —
načítate ich tlačidlom v **Nastavenia → Záloha dát**.

## Štruktúra projektu

```
app.py                    # vstupný bod (st.navigation)
pages/                    # stránky aplikácie (10 stránok, celé UI v SK)
core/
  calc.py                 # výpočty náhrad, stravného, diét, haversine
  db.py                   # SQLite vrstva + JSON záloha/obnova + change-hook
  cloud_sync.py           # automatická záloha do GitHub Gistu
  exporters.py            # XLSX / PDF / CSV / XML exporty
  holidays_sk.py          # slovenské štátne sviatky (vrátane Veľkej noci)
  ui.py                   # spoločné UI pomôcky
data/
  cestaky.db              # SQLite databáza (vytvorí sa automaticky)
  per_diems_2026.csv      # číselník diét SK/CZ/AT (editovateľný v UI)
  rates_2026.json         # predvolené sadzby 2026 (seed pre DB)
requirements.txt
```

## Právne poznámky

- **§3** — zamestnanca možno vyslať na pracovnú cestu len s jeho súhlasom;
  aplikácia nedovolí schváliť viacdňovú cestu bez zaškrtnutého súhlasu.
- **§5, §13** — stravné podľa časových pásiem; každý deň viacdňovej cesty sa
  posudzuje samostatne; krátenie za bezplatne poskytnuté jedlá
  25 / 40 / 35 %.
- **§7** — náhrada za použitie súkromného vozidla = základná náhrada za km
  + náhrada za PHM; cenu PHM možno preukázať dokladom (ods. 5), inak sa
  použije priemerná cena ŠÚ SR.
- **§14** — vreckové pri zahraničnej ceste (voliteľné, do 40 % stravného).
- Aplikácia je pomôcka, nie právne poradenstvo — sadzby a výpočty si overte
  u svojho účtovníka.
