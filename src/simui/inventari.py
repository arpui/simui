"""Inventari de tubs d'He-3 (INVENTARI-UI, encàrrec del coordinador 2026-11-25): **només lectura**.

Llegeix `neudet/disseny/inventari/inventari_tubs.json` —el fa `scripts/inventari/extreu_tubs.py`
a partir de l'Excel; `disseny/inventari/README.md` n'explica les interpretacions— i el registre
`validacions.json` per saber on és la **fitxa** de cada tub del catàleg.

No copia res: es torna a llegir neudet a cada petició, i les files surten tal com són al JSON
(cap recompte, cap reetiquetatge, cap interpretació nova).

**La fitxa, d'on surt.** `docs/site/detector/certificacio_tubs.md:51` (neudet, pla de certificació):
«la marca de validat es llegeix sola de `validacions.json`, i el `document` hi enllaça». Per això la
fitxa d'un tub del catàleg és `entrades["tub:<cataleg>"].document`; si el camp no hi és o el camí no
és un fitxer dins de neudet, **no hi ha enllaç** i es diu per què (MAI INVENTIS).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from simphy.mcgen import design as DES
from simphy.mcgen import detector_config as DC

INVENTARI_REL = "disseny/inventari/inventari_tubs.json"


def inventari_path() -> Path:
    """El JSON de neudet. Si no hi és, es peta dient on mirar (el mirall pot ser vell)."""
    f = DES.neudet_root() / INVENTARI_REL
    if not f.is_file():
        raise RuntimeError(
            f"no hi ha inventari de tubs a {f} — a neudet es genera amb "
            "`python scripts/inventari/extreu_tubs.py` (vegeu disseny/inventari/README.md)")
    return f


def _llegeix() -> Dict[str, Any]:
    return json.loads(inventari_path().read_text(encoding="utf-8"))


def inventari() -> Dict[str, Any]:
    """L'inventari tal com l'ha deixat neudet, amb la fitxa de cada tub del catàleg.

    `tubs` i `resum` són les files del JSON, sense tocar-les. `models` i `llocs` són els valors
    que hi ha (per omplir els filtres): els que surten, no una taula a part.
    """
    d = _llegeix()
    tubs: List[Dict[str, Any]] = d.get("tubs") or []
    if not tubs:
        raise ValueError(f"{inventari_path()} no té cap fila a `tubs`")
    return {
        "font": str(inventari_path()),
        "que": d.get("_que"),
        "regenera": d.get("_regenera"),
        "resum": d.get("resum") or [],
        "tubs": tubs,
        "models": sorted({t.get("model_excel") for t in tubs if t.get("model_excel")}),
        "llocs": sorted({t.get("lloc") for t in tubs if t.get("lloc")}),
        "fitxes": _fitxes(_catalegs(tubs)),
    }


def _catalegs(tubs: List[Dict[str, Any]]) -> List[str]:
    return sorted({t["cataleg"] for t in tubs if t.get("cataleg")})


def _validacions() -> Dict[str, Any]:
    """El registre de neudet (`mc/geant4/detector/config/validacions.json`); buit si no hi és."""
    f = DC.config_dir() / "validacions.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def _camí_document(doc: str) -> str | None:
    """El camí del `document`, si és un fitxer dins de neudet.

    Pot anar amb el § de la secció (`…/certificacio_tubs.md §CERT-P`): la secció es mostra tal com
    és, l'enllaç és al fitxer. Una carpeta o una llista de camins no és un fitxer: sense enllaç.
    """
    neudet = DES.neudet_root().resolve()
    cap = doc.split(" §", 1)[0].strip()
    if not cap or "," in cap or cap.endswith("/"):
        return None
    f = (neudet / cap).resolve()
    return cap if f.is_file() and f.is_relative_to(neudet) else None


def _fitxa(e: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(e, dict):
        return {"document": None, "rel": None, "motiu": "a `validacions.json` no hi ha l'entrada"}
    doc = (e.get("document") or "").strip()
    if not doc:
        return {"document": None, "rel": None, "motiu": "l'entrada no porta `document`"}
    rel = _camí_document(doc)
    return {"document": doc, "estat": e.get("estat"), "data": e.get("data"), "rel": rel,
            "motiu": None if rel else "el camí del `document` no és un fitxer dins de neudet"}


def _fitxes(catalegs: List[str]) -> Dict[str, Dict[str, Any]]:
    entrades = _validacions().get("entrades") or {}
    return {c: _fitxa(entrades.get(f"tub:{c}")) for c in catalegs}


def fitxes() -> Dict[str, Dict[str, Any]]:
    """La fitxa de cada tub del catàleg que surt a l'inventari."""
    return _fitxes(_catalegs(_llegeix().get("tubs") or []))


def fitxa_fitxer(rel: str) -> Path:
    """El fitxer d'una fitxa: només un dels camins que `fitxes()` ha donat (res més, 403)."""
    if not rel or rel.startswith("/") or rel != rel.strip():
        raise PermissionError("el camí de la fitxa ha de ser relatiu a neudet")
    permesos = {x["rel"] for x in fitxes().values() if x["rel"]}
    f = (DES.neudet_root().resolve() / rel).resolve()
    if rel not in permesos or not f.is_file():
        raise PermissionError(f"{rel} no és la fitxa d'un tub del catàleg")
    return f
