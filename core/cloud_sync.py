"""Perzistencia dát cez GitHub Gist (zadarmo, bez reštartu appky).

Streamlit Community Cloud má dočasné úložisko — SQLite sa pri reštarte zmaže.
Tento modul po každej zmene uloží celú DB (JSON) do súkromného gistu a pri
spustení appky ju načíta späť. Gist (na rozdiel od commitu do nasadeného
repozitára) NEspúšťa redeploy appky.

Konfigurácia v Streamlit secrets (App → Settings → Secrets):

    github_token = "github_pat_..."     # token so scope 'gist'

Voliteľne:

    gist_id = "abc123..."               # ak chcete konkrétny gist
    gist_filename = "cestaky_backup.json"

Ak token nie je nastavený, sync je vypnutý a appka funguje ako predtým
(manuálna záloha cez Nastavenia).
"""
from __future__ import annotations

import streamlit as st

from core import db

API = "https://api.github.com"
MARKER = "MojeCestaky-Lite — automatická záloha (neupravovať ručne)"
DEFAULT_FILENAME = "cestaky_backup.json"
_TIMEOUT = 20


# ------------------------------------------------------------- konfigurácia ---

def _secret(*keys):
    # Prístup k st.secrets vyhodí výnimku, ak súbor secrets neexistuje
    # (lokálny beh bez konfigurácie) — preto obalíme celé čítanie.
    try:
        s = st.secrets
        for k in keys:
            if k in s and str(s[k]).strip():
                return str(s[k]).strip()
    except Exception:
        return None
    return None


def token() -> str | None:
    return _secret("github_token", "GITHUB_TOKEN")


def filename() -> str:
    return _secret("gist_filename", "GIST_FILENAME") or DEFAULT_FILENAME


def enabled() -> bool:
    return token() is not None


def _headers(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def _requests():
    import requests  # lokálny import — requests je súčasť streamlitu
    return requests


# -------------------------------------------------------------- gist lookup ---

def _resolve_gist_id(tok: str):
    """Nájde (alebo vytvorí) gist na zálohu. ID si zapamätá v session."""
    if st.session_state.get("_gist_id"):
        return st.session_state["_gist_id"]

    gid = _secret("gist_id", "GIST_ID")
    requests = _requests()
    fname = filename()

    if not gid:
        # nájdi existujúci gist podľa markeru / názvu súboru
        try:
            r = requests.get(f"{API}/gists?per_page=100",
                             headers=_headers(tok), timeout=_TIMEOUT)
            if r.ok:
                for g in r.json():
                    if g.get("description") == MARKER or fname in (g.get("files") or {}):
                        gid = g["id"]
                        break
        except Exception:
            return None

    if not gid:
        # vytvor nový súkromný gist
        try:
            r = requests.post(
                f"{API}/gists", headers=_headers(tok), timeout=_TIMEOUT,
                json={"description": MARKER, "public": False,
                      "files": {fname: {"content": "{}"}}})
            if r.ok:
                gid = r.json()["id"]
            else:
                return None
        except Exception:
            return None

    st.session_state["_gist_id"] = gid
    return gid


# -------------------------------------------------------------- push / pull ---

def push() -> bool:
    """Uloží aktuálnu DB do gistu. Vráti True pri úspechu."""
    tok = token()
    if not tok:
        return False
    gid = _resolve_gist_id(tok)
    if not gid:
        st.session_state["_sync_error"] = "Nepodarilo sa nájsť/vytvoriť gist."
        return False
    requests = _requests()
    try:
        r = requests.patch(
            f"{API}/gists/{gid}", headers=_headers(tok), timeout=_TIMEOUT,
            json={"files": {filename(): {"content": db.export_db_json()}}})
        if r.ok:
            st.session_state["_sync_error"] = None
            return True
        st.session_state["_sync_error"] = f"GitHub odpovedal {r.status_code}."
        return False
    except Exception as e:
        st.session_state["_sync_error"] = f"Chyba siete: {e}"
        return False


def pull() -> bool:
    """Načíta DB z gistu (prepíše lokálnu). Vráti True ak boli načítané dáta."""
    tok = token()
    if not tok:
        return False
    gid = _resolve_gist_id(tok)
    if not gid:
        return False
    requests = _requests()
    try:
        r = requests.get(f"{API}/gists/{gid}", headers=_headers(tok),
                         timeout=_TIMEOUT)
        if not r.ok:
            st.session_state["_sync_error"] = f"GitHub odpovedal {r.status_code}."
            return False
        files = r.json().get("files") or {}
        f = files.get(filename())
        if not f:
            return False
        content = f.get("content") or ""
        if f.get("truncated") and f.get("raw_url"):
            content = requests.get(f["raw_url"], timeout=_TIMEOUT).text
        if not content.strip() or content.strip() == "{}":
            return False
        db.import_db_json(content, fire=False)  # bez spätného push
        st.session_state["_sync_error"] = None
        return True
    except Exception as e:
        st.session_state["_sync_error"] = f"Chyba siete: {e}"
        return False


# ------------------------------------------------------------- štart appky ---

def init_on_start() -> None:
    """Zaregistruje auto-zálohu a raz za session načíta dáta z cloudu."""
    if not enabled():
        return
    db.on_change = push  # každá zmena dát -> push do gistu
    if not st.session_state.get("_cloud_pulled"):
        pull()
        st.session_state["_cloud_pulled"] = True


def status_text() -> str:
    if not enabled():
        return "☁️ Cloud sync: **vypnutý** (nastavte `github_token` v secrets)"
    err = st.session_state.get("_sync_error")
    if err:
        return f"☁️ Cloud sync: ⚠️ {err}"
    return "☁️ Cloud sync: **zapnutý** (GitHub Gist)"
