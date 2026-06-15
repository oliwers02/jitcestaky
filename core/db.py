"""SQLite vrstva — schéma, CRUD, záloha/obnova DB ako JSON."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "cestaky.db"
RATES_JSON = DATA_DIR / "rates_2026.json"
PER_DIEMS_CSV = DATA_DIR / "per_diems_2026.csv"

# Voliteľný hook volaný po každej zmene dát (insert/update/delete).
# Appková vrstva ho nastaví na cloudovú zálohu (core.cloud_sync.push).
# Jadro DB tým neimportuje streamlit ani requests — ostáva oddelené.
on_change = None
_suspend_change = False


def suspend_change(value: bool = True) -> None:
    """Dočasne pozastaví on_change (napr. počas hromadného generovania)."""
    global _suspend_change
    _suspend_change = value


def _fire_change() -> None:
    if on_change and not _suspend_change:
        try:
            on_change()
        except Exception:
            pass

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meno_priezvisko TEXT NOT NULL,
    pozicia TEXT,
    adresa_bydliska TEXT,
    email TEXT,
    telefon TEXT,
    aktivny INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    typ TEXT NOT NULL DEFAULT 'osobne_auto',
    znacka TEXT,
    model TEXT,
    rok_vyroby INTEGER,
    objem_motora_cm3 INTEGER,
    typ_paliva TEXT DEFAULT 'benzin',
    spotreba_l_100km REAL,
    spz TEXT,
    predvolene INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazov TEXT NOT NULL,
    adresa TEXT,
    lat REAL,
    lon REAL
);
CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER REFERENCES employees(id),
    vehicle_id INTEGER REFERENCES vehicles(id),
    typ_dopravy TEXT DEFAULT 'sukromne_auto',
    datum TEXT NOT NULL,
    cas_odchodu TEXT,
    cas_prichodu TEXT,
    miesto_zaciatku TEXT,
    ciel_cesty TEXT,
    typ_trasy TEXT DEFAULT 'zmiesana',
    ucel_cesty TEXT,
    vedlajsie_vydavky_eur REAL DEFAULT 0,
    vzdialenost_km REAL DEFAULT 0,
    zahranicna INTEGER DEFAULT 0,
    cielova_krajina TEXT DEFAULT 'SK',
    cena_phm_z_dokladu_eur_l REAL,
    suhlas_zamestnanca INTEGER DEFAULT 0,
    vreckove_percent REAL DEFAULT 0,
    vypocitana_phm_nahrada REAL DEFAULT 0,
    vypocitana_zakladna_nahrada REAL DEFAULT 0,
    vypocitane_stravne REAL DEFAULT 0,
    stravne_mena TEXT DEFAULT 'EUR',
    vypocitane_vreckove REAL DEFAULT 0,
    nahrada_spolu REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS business_trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER REFERENCES employees(id),
    nazov TEXT,
    ucel TEXT,
    datum_zaciatku TEXT NOT NULL,
    datum_konca TEXT NOT NULL,
    cas_odchodu_prvy_den TEXT,
    cas_navratu_posledny_den TEXT,
    zahranicna INTEGER DEFAULT 0,
    cielova_krajina TEXT DEFAULT 'SK',
    poznamky TEXT,
    suhlas_zamestnanca INTEGER DEFAULT 0,
    status TEXT DEFAULT 'koncept',
    ubytovanie_eur REAL DEFAULT 0,
    kilometrovne_eur REAL DEFAULT 0,
    navstevy_rodiny_eur REAL DEFAULT 0,
    vreckove_percent REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS business_trip_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_trip_id INTEGER REFERENCES business_trips(id) ON DELETE CASCADE,
    datum TEXT NOT NULL,
    typ_dna TEXT NOT NULL,
    pocet_hodin REAL DEFAULT 0,
    ranajky_poskytnute INTEGER DEFAULT 0,
    obed_poskytnuty INTEGER DEFAULT 0,
    vecera_poskytnuta INTEGER DEFAULT 0,
    stravne_den_eur REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platne_od TEXT NOT NULL,
    rates_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS app_config (
    kluc TEXT PRIMARY KEY,
    hodnota TEXT
);
CREATE TABLE IF NOT EXISTS payouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER REFERENCES employees(id),
    datum TEXT NOT NULL,
    suma_eur REAL DEFAULT 0,
    poznamka TEXT
);
"""

TABLES = ["employees", "vehicles", "locations", "trips",
          "business_trips", "business_trip_days", "settings", "app_config",
          "payouts"]


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(seed: bool = False) -> None:
    """Vytvorí schému a predvolené sadzby. Ukážkové dáta sa NEvkladajú
    automaticky (vkladajú sa len na požiadanie cez seed_sample_data)."""
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        # predvolené sadzby z rates_2026.json (verzia platná od 1. 1. 2026)
        if conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
            rates = json.loads(RATES_JSON.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO settings (platne_od, rates_json) VALUES (?, ?)",
                (rates.get("platne_od", "2026-01-01"),
                 json.dumps(rates, ensure_ascii=False)),
            )
        conn.commit()
        if seed and conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
            _seed_sample_data(conn)
    finally:
        conn.close()


def is_empty() -> bool:
    """Sú v DB nejaké používateľské dáta (cesty/zamestnanci/viacdňové)?"""
    conn = get_conn()
    try:
        for t in ("trips", "business_trips", "employees"):
            if conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] > 0:
                return False
        return True
    finally:
        conn.close()


def seed_sample_data() -> bool:
    """Vloží ukážkové dáta, ak je DB prázdna. Vráti True ak vložila."""
    conn = get_conn()
    try:
        if conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
            _seed_sample_data(conn)
            return True
        return False
    finally:
        conn.close()


# ------------------------------------------------------------------ CRUD ---

def fetch_all(table: str, where: str = "", params: tuple = (),
              order: str = "id") -> list[dict]:
    conn = get_conn()
    try:
        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {where}"
        sql += f" ORDER BY {order}"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def fetch_one(table: str, row_id: int) -> dict | None:
    conn = get_conn()
    try:
        r = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def insert(table: str, data: dict) -> int:
    conn = get_conn()
    try:
        cols = ", ".join(data)
        ph = ", ".join("?" * len(data))
        cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({ph})",
                           tuple(data.values()))
        conn.commit()
        rowid = cur.lastrowid
    finally:
        conn.close()
    _fire_change()
    return rowid


def update(table: str, row_id: int, data: dict) -> None:
    conn = get_conn()
    try:
        sets = ", ".join(f"{k} = ?" for k in data)
        conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?",
                     (*data.values(), row_id))
        conn.commit()
    finally:
        conn.close()
    _fire_change()


def delete(table: str, row_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        conn.commit()
    finally:
        conn.close()
    _fire_change()


def query(sql: str, params: tuple = ()) -> list[dict]:
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# ------------------------------------------------------------ app_config ---

def get_config(kluc: str, default=None):
    rows = fetch_all("app_config", "kluc = ?", (kluc,), order="kluc")
    if not rows:
        return default
    try:
        return json.loads(rows[0]["hodnota"])
    except (json.JSONDecodeError, TypeError):
        return rows[0]["hodnota"]


def set_config(kluc: str, hodnota) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO app_config (kluc, hodnota) VALUES (?, ?) "
            "ON CONFLICT(kluc) DO UPDATE SET hodnota = excluded.hodnota",
            (kluc, json.dumps(hodnota, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
    _fire_change()


# ------------------------------------------------------- záloha / obnova ---

def export_db_json() -> str:
    """Celá DB ako JSON — záloha pre ephemeral storage na Streamlit Cloud."""
    dump = {"_export": {"verzia": 1, "datum": dt.datetime.now().isoformat()}}
    for t in TABLES:
        dump[t] = fetch_all(t, order="rowid")
    return json.dumps(dump, ensure_ascii=False, indent=2)


def import_db_json(json_str: str, fire: bool = True) -> None:
    """Obnoví DB zo zálohy (prepíše existujúce dáta).

    fire=False pri automatickom načítaní z cloudu, aby sa hneď nespustila
    spätná záloha toho istého obsahu.
    """
    data = json.loads(json_str)
    conn = get_conn()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(SCHEMA)
        for t in TABLES:
            rows = data.get(t, [])
            conn.execute(f"DELETE FROM {t}")
            for row in rows:
                cols = ", ".join(row)
                ph = ", ".join("?" * len(row))
                conn.execute(f"INSERT INTO {t} ({cols}) VALUES ({ph})",
                             tuple(row.values()))
        conn.commit()
    finally:
        conn.close()
    if fire:
        _fire_change()


# ------------------------------------------------------- ukážkové dáta -----

def _seed_sample_data(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO employees (meno_priezvisko, pozicia, adresa_bydliska, email, telefon, aktivny) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        ("Ján Vzorový", "konateľ", "Hlavná 1, 010 01 Žilina",
         "jan.vzorovy@example.com", "+421 900 123 456"),
    )
    emp_id = cur.lastrowid
    cur.execute(
        "INSERT INTO vehicles (typ, znacka, model, rok_vyroby, objem_motora_cm3, "
        "typ_paliva, spotreba_l_100km, spz, predvolene) "
        "VALUES ('osobne_auto', 'Škoda', 'Octavia', 2021, 1498, 'benzin', 6.1, 'ZA123BC', 1)"
    )
    veh_id = cur.lastrowid
    cur.executemany(
        "INSERT INTO locations (nazov, adresa, lat, lon) VALUES (?, ?, ?, ?)",
        [
            ("Kancelária Bratislava", "Mlynské nivy 5, Bratislava", 48.1486, 17.1077),
            ("Klient Trenčín", "Mierové námestie 2, Trenčín", 48.8945, 18.0444),
            ("Sklad Žilina", "Kamenná 3, Žilina", 49.2194, 18.7408),
        ],
    )
    # ukážková jednodňová cesta (vypočítané hodnoty podľa sadzieb 2026):
    # 180 km, spotreba 6.1 l/100 km, benzín 1.70 €/l -> PHM 18.67 €
    # základná náhrada 180 * 0.313 = 56.34 €, stravné 10 h -> 9.30 €
    cur.execute(
        "INSERT INTO trips (employee_id, vehicle_id, typ_dopravy, datum, cas_odchodu, "
        "cas_prichodu, miesto_zaciatku, ciel_cesty, typ_trasy, ucel_cesty, "
        "vedlajsie_vydavky_eur, vzdialenost_km, zahranicna, cielova_krajina, "
        "suhlas_zamestnanca, vypocitana_phm_nahrada, vypocitana_zakladna_nahrada, "
        "vypocitane_stravne, stravne_mena, nahrada_spolu) "
        "VALUES (?, ?, 'sukromne_auto', '2026-05-12', '07:30', '17:30', "
        "'Hlavná 1, Žilina', 'Klient Trenčín', 'dialnica', 'obchodné rokovanie', "
        "4.50, 180, 0, 'SK', 1, 18.67, 56.34, 9.30, 'EUR', 88.81)",
        (emp_id, veh_id),
    )
    # ukážková viacdňová zahraničná cesta do Rakúska
    cur.execute(
        "INSERT INTO business_trips (employee_id, nazov, ucel, datum_zaciatku, "
        "datum_konca, cas_odchodu_prvy_den, cas_navratu_posledny_den, zahranicna, "
        "cielova_krajina, poznamky, suhlas_zamestnanca, status, ubytovanie_eur, "
        "kilometrovne_eur, vreckove_percent) "
        "VALUES (?, 'Veľtrh Viedeň', 'účasť na veľtrhu', '2026-05-18', '2026-05-20', "
        "'06:00', '19:00', 1, 'AT', 'ukážková cesta', 1, 'schvalena', 240.0, 178.0, 40)",
        (emp_id,),
    )
    bt_id = cur.lastrowid
    cur.executemany(
        "INSERT INTO business_trip_days (business_trip_id, datum, typ_dna, pocet_hodin, "
        "ranajky_poskytnute, obed_poskytnuty, vecera_poskytnuta, stravne_den_eur) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (bt_id, "2026-05-18", "odchod", 18.0, 0, 0, 0, 45.00),
            (bt_id, "2026-05-19", "plny_den", 24.0, 1, 0, 0, 33.75),
            (bt_id, "2026-05-20", "navrat", 19.0, 1, 0, 0, 33.75),
        ],
    )
    conn.commit()
