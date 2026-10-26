"""campanya_desa.py — «Desa la proposta» i «Tanteja» (contracte simphy_ui.md §7; flux runbooks/_flux_campanya.md).

Què escriu, i què no
--------------------
- `desa_proposta(form)` escriu NOMÉS dos fitxers, a `<NEUDET_ROOT>/disseny/campanyes/<id>/`:
  `campanya.yaml` (amb `estat: proposta`, que hi posa simphy) i `comprova.json` (la certificació de neudet
  d'aquell mateix yaml). Si neudet no pot certificar, no desa res i diu per què.
- Una campanya existent només es torna a escriure si és una proposta (`estat: proposta`): una proposta pròpia.
  Una campanya amb un altre estat no es modifica mai: el tanteig és una campanya nova amb un id derivat.
- `tanteig_de_campanya` i `tanteig_de_candidat` NO escriuen res: porten el formulari amb el yaml d'una campanya
  (o amb un candidat seu, com a etapa `llista`) i un id lliure. L'original no es toca.

Atomicitat: els dos fitxers es escriuen primer en temporals de la mateixa carpeta, i després es reanomenen.
"""
from __future__ import annotations

import copy
import datetime as _dt
import json
import os
import re
import string
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

from . import campanya_check as CC
from . import campanya_form as CF
from . import campanya_vista as CV

#: l'id d'una campanya: com a nom de carpeta, sense camins ni majúscules
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,63}$")
ESTAT = CV.ESTAT_PROPOSTA
FITXERS = ("campanya.yaml", "comprova.json")
#: el text que Albert envia al planificador (flux, «Missatges»)
MISSATGE = "campanya `{id}` proposta"


class DesaError(ValueError):
    """Una proposta que no es pot desar, o un tanteig que no es pot fer. El missatge diu per què."""


# ── ids ─────────────────────────────────────────────────────────────────────

def valida_id(id_: Any) -> str:
    if not isinstance(id_, str) or not ID_RE.match(id_):
        raise DesaError(f"id de campanya no vàlid: {id_!r} (cal ^[a-z0-9][a-z0-9_]{{1,63}}$, p. ex. c05_prova)")
    return id_


def id_derivat(id_: str, existents: Iterable[str] = ()) -> str:
    """El primer id lliure del tanteig de `id_`: s'insereix una lletra després del prefix abans del primer `_`.
    `c04_draft` → `c04b_draft` → `c04c_draft`… Si el prefix ja acaba en lletra (`c04b_draft`), la lletra es
    reemplaça: la família és sempre `c04*`. `existents` són els ids ja ocupats a `disseny/campanyes/`."""
    valida_id(id_)
    ocupats = set(existents)
    head, sep, tail = id_.partition("_")
    base = head[:-1] if re.fullmatch(r"[a-z0-9]*\d[a-z]", head) else head
    for lletra in string.ascii_lowercase[1:]:               # b, c, d…; la «a» és la de l'original
        cand = f"{base}{lletra}{sep}{tail}"
        if cand not in ocupats and ID_RE.match(cand):
            return cand
    raise DesaError(f"no queda cap lletra lliure per derivar de «{id_}»")


def _ids_existents(root: Path) -> List[str]:
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def _arrel(root: Optional[Path]) -> Path:
    r = CV.campanyes_root() if root is None else Path(root)
    if not r.is_dir():
        raise DesaError(f"no trobo {r}: neudet no té disseny/campanyes/")
    return r


def _dir_de_id(root: Path, id_: str) -> Path:
    """La carpeta `root/<id>`, i només si és un fill directe de `root` (sense camins ni enllaços fora)."""
    d = root / id_
    if d.resolve().parent != root.resolve():
        raise DesaError(f"«{id_}» no és una carpeta directa de disseny/campanyes")
    return d


# ── desar la proposta ───────────────────────────────────────────────────────

def _pot_sobreescriure(d: Path, id_: str) -> None:
    """Una carpeta existent només es toca si el seu campanya.yaml és una proposta."""
    yf = d / "campanya.yaml"
    if not yf.is_file():
        raise DesaError(f"la carpeta `{id_}` ja existeix i no té campanya.yaml: no es toca")
    try:
        y = yaml.safe_load(yf.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError) as exc:
        raise DesaError(f"el campanya.yaml de `{id_}` no es llegeix ({exc}): no es toca") from None
    estat = y.get("estat") if isinstance(y, dict) else None
    if estat != ESTAT:
        raise DesaError(f"la campanya `{id_}` ja existeix (estat: {estat!r}): no es modifica mai una campanya "
                        "existent: fes un tanteig amb un id nou")


def _tmp(dest: Path, text: str) -> Path:
    fd, nom = tempfile.mkstemp(dir=str(dest.parent), prefix="." + dest.name + ".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(nom, 0o644)
    return Path(nom)


def desa_proposta(form: Any, root: Optional[Path] = None) -> Dict[str, Any]:
    """Desa el formulari com a proposta: `campanya.yaml` (estat: proposta) i `comprova.json` (certificació de
    neudet d'aquell yaml). Retorna els camins escrits i el missatge per a Albert. Llança `DesaError` (400) si:
    l'id no és vàlid, la carpeta és una campanya que no és proposta, la forma no és llegible per neudet, o neudet
    no pot certificar."""
    if not isinstance(form, dict):
        raise DesaError("cal el formulari de la campanya (un diccionari)")
    id_ = valida_id(form.get("id"))
    base = _arrel(root)
    d = _dir_de_id(base, id_)
    existia = d.exists()
    if existia:
        if not d.is_dir():
            raise DesaError(f"`{id_}` existeix i no és una carpeta: no es toca")
        _pot_sobreescriure(d, id_)
    f = copy.deepcopy(form)
    f["estat"] = ESTAT
    try:
        text = CF.to_yaml(f)
    except CF.FormError as exc:
        raise DesaError(f"no es desa: {exc}") from None
    try:
        cert = CC.certifica_proposta(text, id_)
    except ValueError as exc:
        raise DesaError(f"no es desa: neudet no certifica la proposta. {exc}") from None
    comprova = json.dumps(cert, ensure_ascii=False, indent=1) + "\n"
    if not existia:
        d.mkdir()
    tmps: List[Path] = []
    try:
        tmps.append(_tmp(d / FITXERS[0], text))
        tmps.append(_tmp(d / FITXERS[1], comprova))
        for t, nom in zip(tmps, FITXERS):
            os.replace(t, d / nom)
    except BaseException:
        for t in tmps:
            if t.exists():
                t.unlink()
        raise
    return {"id": id_, "estat": ESTAT, "sobreescrita": existia,
            "escrit": [str(d / nom) for nom in FITXERS], "missatge": MISSATGE.format(id=id_),
            "atura": bool(cert.get("atura")), "draft": cert.get("draft"), "certificacio": cert}


# ── tanteig ─────────────────────────────────────────────────────────────────

def _form_tanteig(form: Dict[str, Any], nou: str) -> Dict[str, Any]:
    """El formulari de l'original, amb l'id nou i com a proposta nova (la data de creació és avui)."""
    f = copy.deepcopy(form)
    f["id"] = nou
    f["estat"] = ESTAT
    f["creada"] = _dt.date.today().isoformat()
    return f


def _ha_de_passar_el_formulari(f: Dict[str, Any], de: str) -> None:
    """Un tanteig que el formulari no pot escriure no s'ofereix: es diu per què, en lloc de deixar un formulari
    que no es pot desar. (Cd com a llista, p. ex., és el que el formulari encara no llegeix: c01 i c02.)"""
    try:
        CF.to_yaml(f)
    except CF.FormError as exc:
        raise DesaError(f"no es pot tantejar «{de}» al formulari: {exc}") from None


def tanteig_de_campanya(de: str) -> Dict[str, Any]:
    """El formulari de la campanya `de`, amb un id derivat lliure. No escriu res."""
    d = CV.dir_de(de)
    form = CF.de_fitxer(d / "campanya.yaml")
    nou = id_derivat(de, _ids_existents(CV.campanyes_root()))
    f = _form_tanteig(form, nou)
    _ha_de_passar_el_formulari(f, de)
    return {"de": de, "id": nou, "form": f, "etapa": next(iter(f.get("etapes") or {}), None),
            "candidat": None}


def _tub_yaml(t: Any) -> Dict[str, Any]:
    """Un tub de neudet com a tub de l'etapa `llista` (les claus que el generador llegeix, generadors.py)."""
    out: Dict[str, Any] = {"x": float(t.x), "y": float(t.y), "z": float(t.z), "tipus": t.tipus}
    if t.cd_fraction:
        out.update(cd_fraction=float(t.cd_fraction), cd_arc_deg=float(t.cd_arc_deg),
                   cd_arc_centre_deg=float(t.cd_arc_centre_deg))
    return out


def tanteig_de_candidat(de: str, hash_: str, etapa: Optional[str] = None) -> Dict[str, Any]:
    """El formulari de la campanya `de` amb UNA etapa `llista` que porta el candidat `hash_` (els seus tubs, tal
    com els genera neudet). L'etapa és la de l'original que el conté (o `etapa`), i les seves altres claus
    (cerca, etc.) es mantenen. No escriu res."""
    d = CV.dir_de(de)
    form = CF.de_fitxer(d / "campanya.yaml")
    nom_etapa, cand = CC.candidat_de(d, hash_, etapa)
    nou = id_derivat(de, _ids_existents(CV.campanyes_root()))
    f = _form_tanteig(form, nou)
    orig = form["etapes"][nom_etapa]
    nova = {k: v for k, v in orig.items() if k not in ("generador", "que")}
    nova = {"que": f"tanteig de {de}: candidat {cand.nom} (etapa {nom_etapa})", **nova}
    nova["generador"] = {"tipus": "llista",
                         "candidats": [{"nom": cand.nom, "tubs": [_tub_yaml(t) for t in cand.tubs]}]}
    f["etapes"] = {f"llista_{nom_etapa}": nova}
    _ha_de_passar_el_formulari(f, de)
    return {"de": de, "id": nou, "form": f, "etapa": f"llista_{nom_etapa}",
            "candidat": {"nom": cand.nom, "hash": hash_, "etapa": nom_etapa, "tubs_n": len(cand.tubs)}}
