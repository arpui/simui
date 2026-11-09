"""campanya_form.py — el formulari de «Definició de campanya» (contracte simphy_ui.md §4, C1).

Què és i què no
---------------
- `defaults()` és el `campanya.yaml` de **c04_draft**, llegit de neudet (no es copia).
- `schema()` és el que el formulari necessita saber, i ve de neudet:
    · els tipus de generador: el registre `GENERADORS` de `neudet.disseny.generadors`, i la seva
      ajuda: el paràgraf del docstring del mòdul (`generadors.py`), llegit en temps d'execució;
    · els camps de cada tipus: la taula `CAMPS` d'aquí, on cada clau porta la línia de
      `generadors.py` on neudet la llegeix. El test bessó comprova que la clau hi és, a aquella
      línia, i que no n'hi falta cap tipus;
    · les mètriques, sentits, pesos, cerca i xarxa: LLISTES TANCADES. Cada valor porta la línia de
      neudet on es llegeix (`METRIQUES_LINIA`, `CERQUES_LINIA`, …). `schema()` comprova que el
      registre de neudet diu exactament això, i si no ho diu, peta dient quin fitxer cal mirar;
    · els tubs: `tubs.json` (el catàleg de neudet), amb la marca de validat només si hi ha
      `validacions.json`. Si no n'hi ha, es diu «sense registre de validació (CAMP-1 pendent)».
- `to_yaml(form)` escriu el `campanya.yaml` d'esborrany amb les claus de neudet, en el mateix
  ordre. Valida la FORMA (que neudet la pugui llegir) i els valors dins de les llistes tancades
  (`FormError` amb el camp). Si un candidat és vàlid o no, ho diu neudet (`Campanya(dir).candidats`).
  `to_yaml` no necessita neudet: les llistes tancades estan aquí, amb les seves línies, i el test
  bessó comprova que són les de neudet.

El YAML, quan és una data (`creada: 2026-10-26`), es llegeix com a data: el formulari la porta com
a text ISO i `to_yaml` l'escriu sense cometes perquè neudet la llegeixi com a data.
"""
from __future__ import annotations

import ast
import copy
import datetime as _dt
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from simphy.mcgen import design as DES
from simphy.mcgen import mc_sources as MS
from simphy.mcgen import detector_config as DC

#: el campanya.yaml de referència, relatiu a l'arrel de neudet
C04_YAML = "disseny/campanyes/c04_draft/campanya.yaml"
#: fitxers de neudet d'on es llegeixen les llistes: només el nom; el directori és `_DIS` (el paquet)
#: o `_SCRIPTS` (els scripts). Els noms van així perquè l'auditoria de referències no els confongui
#: amb rutes d'aquest repo.
_DIS = ("src", "neudet", "disseny")
_SCRIPTS = ("scripts", "disseny")
GENERADORS_PY = "generadors.py"
OBJECTIUS_PY = "objectius.py"
CERCA_PY = "cerca.py"
CAMPANYA_PY = "campanya.py"
AVALUADOR_PY = "avaluador.py"
CANDIDAT_PY = "candidat.py"
FITXA_PY = "fitxa.py"
VERIFICA_G4_PY = "verifica_g4.py"
#: contracte §4: fraccions axials d'exemple (NO és una llista de neudet: neudet accepta qualsevol (0, 1])
CD_FRACCIONS = [0, 0.25, 0.5, 0.75, 1]
CD_ARCS_DEG = [360, 180]
SENSE_REGISTRE = "sense registre de validació (CAMP-1 pendent)"
_ID = re.compile(r"^[A-Za-z0-9_\-]+$")
_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ENTRADA = re.compile(r"^    ([a-z_]+)\s+·\s*(.*)$")          # «    nom  · text» dins d'un docstring de neudet
TUB = "__TUB__"                                                 # marca de la plantilla: el tub triat

# ── llistes tancades: cada valor és on neudet el diu ─────────────────────────
# Clau = valor acceptat; valor = línia (1-based) del fitxer on hi ha el valor. El test bessó comprova
# que la línia el conté; `schema()` comprova que els registres de neudet són exactament aquestes claus.

#: mètriques (objectius.py): el nom entre cometes, dins del registre
METRIQUES_LINIA: Dict[str, int] = {
    "eps_mitja": 33, "cv": 34, "rang": 35, "eps_min": 37, "cd_cm2": 38,            # METRIQUES
    "q_rang": 46, "q_monoton": 47, "res_E": 48,                                    # METRIQUES_GRUP (MET2)
    "N_obj": 75, "sE_N": 76, "n_ef": 77,                                           # METRIQUES_GRUP2 (IND)
    "res_E_k": 116, "err_grups": 117,                                              # METRIQUES_GRUP3 (MET3)
}
#: les mètriques que neudet afegeix soles al Pareto o a la restricció (objectius.py:240-242)
AUTO_LINIA = 240
#: sentit (objectius.py:399: `1 if s == "max" else -1`): «max»; qualsevol altra cosa és min
SENTITS = ("max", "min")
SENTITS_LINIA = 399
#: les mètriques que neudet afegeix soles (objectius.py: GEOMETRIQUES, GRUP, GRUP2, GRUP3)
AUTO_NOMS = {"cd_cm2", "q_rang", "q_monoton", "res_E", "N_obj", "sE_N", "n_ef", "res_E_k", "err_grups"}
#: les mètriques per defecte de l'objectiu (objectius.py:228): totes les que no són geomètriques
DEFECTE_NOMS = ("eps_mitja", "cv", "rang", "eps_min")
#: pesos (objectius.py): `cfg.get("pesos", "uniforme")` i el `elif` de letargia
PESOS_LINIA: Dict[str, int] = {"uniforme": 217, "letargia": 219}
PESOS_DEFECTE_LINIA = 215
#: energies: «totes» (objectius.py:209); subconjunt dins de la graella (objectius.py:214)
ENERGIES_LINIA = 209
GRAELLA_LINIA = 214
K_SIGMA_LINIA = 243
ERR_GRUPS_CAL_LINIA = 159        # «err_grups: cal objectius.grups_MeV» (és l'única mètrica que en vol)
#: ε-restricció per defecte (objectius.py:238)
RESTRICCIO_LINIA = 238
#: valors de la mètrica per defecte de l'objectiu, i què fa neudet si el camp manca
DEFECTE_NOMS_LINIA = 228
#: OBJ (contracte §14, cicle nou): la taula de neudet (`objectius.taula_objectius`) i les llistes tancades que en llegeix el formulari.
#: `schema()` comprova que la taula de neudet diu exactament això; `to_yaml` les fa servir sense neudet.
FINALITATS_LINIA = 473                       # FINALITATS = {"comptador": …, "espectrometre": …}
TAULA_LINIA = 813                            # def taula_objectius()
FINALITAT_METRIQUES: Dict[str, Tuple[str, ...]] = {
    "comptador": ("eps_mitja", "cv", "rang", "eps_min", "cd_cm2"),
    "espectrometre": ("eps_mitja", "res_E", "err_grups", "q_rang", "q_monoton", "n_ef", "N_obj", "sE_N", "cv", "cd_cm2"),
}
ALIES_OBJ = {"res_E_k": "res_E"}
OPERADORS = (">=", "<=", ">", "<")
PESOS_NOUS = ("letargia", "uniforme")         # i {espectre: <fitxer>}
CLAUS_NOVES = ("finalitat", "objectius", "informatives", "preferencia", "restriccions")
CLAUS_VELLES = ("metriques", "pareto", "restriccio", "c_cv")
#: cerca (cerca.py): el registre `@registra("…")` i el camp que llegeix
CERQUES_LINIA: Dict[str, int] = {"exhaustiva": 37, "aleatoria": 42, "halving": 49}
CERCA_DEFECTE_LINIA = 31                       # tipus = spec.get("tipus", "exhaustiva")
CERCA_EXEC_DEFECTE_LINIA = 175                 # campanya.py: e.get("cerca", {"tipus": "exhaustiva"})
#: camps de cada tipus de cerca: (clau, tipus, mínim, obligatori, línia, descripció)
CERCA_CAMPS: Dict[str, List[Dict[str, Any]]] = {
    "exhaustiva": [
        {"clau": "n", "tipus": "enter", "minim": 1, "obligatori": False, "linia": 39,
         "descripcio": "neutrons per candidat; per defecte avaluacio.n_cribratge (campanya.py:141)"},
    ],
    "aleatoria": [
        {"clau": "mostres", "tipus": "enter", "minim": 1, "obligatori": True, "linia": 45,
         "descripcio": "candidats a l'atzar; sense ell, neudet falla (spec[\"mostres\"])"},
        {"clau": "llavor", "tipus": "enter", "minim": None, "obligatori": False, "linia": 44,
         "descripcio": "llavor del sorteig (per defecte 0)"},
        {"clau": "n", "tipus": "enter", "minim": 1, "obligatori": False, "linia": 46,
         "descripcio": "neutrons per candidat; per defecte avaluacio.n_cribratge"},
    ],
    "halving": [
        {"clau": "n_inicial", "tipus": "enter", "minim": 1, "obligatori": False, "linia": 51,
         "descripcio": "neutrons del cribratge; per defecte avaluacio.n_cribratge"},
        {"clau": "n_final", "tipus": "enter", "minim": 1, "obligatori": False, "linia": 51,
         "descripcio": "neutrons de la ronda final; per defecte avaluacio.n_final"},
        {"clau": "fraccio", "tipus": "num", "minim": 0, "maxim": 1, "exclou_minim": True, "obligatori": False, "linia": 54,
         "descripcio": "fracció dels candidats que passen (per defecte 0,1). neudet no en comprova el rang"},
        {"clau": "min_finalistes", "tipus": "enter", "minim": 1, "obligatori": False, "linia": 54,
         "descripcio": "mínim de finalistes, encara que la fracció en doni menys (per defecte 5)"},
    ],
}
#: avaluació (campanya.py / avaluador.py)
XARXES_LINIA: Dict[str, int] = {"A": 233, "B1": 233}
XARXA_DEFECTE_LINIA = 119
MODES_LINIA: Dict[str, int] = {"lots": 189, "per_energia": 189, "continu": 189}
MODE_DEFECTE_LINIA = 118
CD_MODE_REGLA_LINIA = 121                      # «Cd: cal mode continu i xarxa B1»
#: camps numèrics d'avaluació: (clau, línia de campanya.py que els llegeix, mínim, descripció)
AVALUACIO_CAMPS: Dict[str, Dict[str, Any]] = {
    "n_cribratge": {"linia": 141, "minim": 1, "defecte": 200000,
                    "descripcio": "neutrons per candidat al cribratge (la cerca els usa com a N per defecte)"},
    "n_final": {"linia": 142, "minim": 1, "defecte": 2000000,
                "descripcio": "neutrons per candidat a la ronda final (halving)"},
    "lot": {"linia": 135, "minim": 1, "defecte": 500000,
            "descripcio": "primaris per lot de GPU; per sobre, neudet els parteix en lots (avaluador.py:182)"},
}
GEOM_VECT_LINIA = 136
GEOM_VECT_DEFECTE = True

#: Cd (candidat.py): fracció 0 = sense Cd; si no, (0, 1]. Arc (0, 360] (candidat.py:219-224)
CD_FRACCIO_LINIA = 221
CD_ARC_LINIA = 224
#: font (candidat.py:256 docstring)
FONT_LINIA = 256
FONT_TIPUS = ["iso", "feix"]
EIXOS = ["x", "y", "z"]
#: l'eix per defecte del feix (candidat.py:289)
EIX_DEFECTE_LINIA = 289
#: la nota ("**Què:**") que neudet copia al resum (campanya.py:245)
NOTA_LINIA = 245
#: la graella de slots (generadors.py): pas no nul, i ocupats
SLOTS_PAS_LINIA = 184

#: Les tongades (GEN-U, contracte UI v1.3 §10): FONTS, LLIGAMS i ATRIBUTS són els de `neudet.disseny.generadors`.
#: Les descripcions són el text del formulari (no una dada de neudet).
FONTS_TEXT = {
    "punts": "posicions fixes (x, y, z) que escrius una a una",
    "malla": "una malla de posicions permeses: se'n trien k per candidat (k = 1: un tub a cada punt)",
    "anells": "anells (radi r, n tubs, angle φ); r, n i φ poden ser un valor, una llista o un rang",
    "dat": "un candidat fix d'un fitxer .dat",
}
LLIGAMS_TEXT = {
    "global": "tots els tubs de la tongada iguals (un valor per candidat)",
    "grup": "igual dins de cada grup (anell o grup de punts); cada grup pot ser diferent",
    "tub": "cada tub pot ser diferent",
}
MALLA_FORMES = ["quadrada", "hexagonal", "polar"]
INTERN_TRADUCCIO = ("_antic",)              # camps que neudet afegeix en traduir un `generador` antic; la UI no els escriu


class FormError(ValueError):
    """Un formulari que no es pot escriure com a campanya.yaml. El missatge diu què cal canviar."""


# ── neudet: els valors per defecte i els tipus ──────────────────────────────

def _jsonable(x: Any) -> Any:
    """Dates de YAML → text ISO, recursivament (el formulari és JSON)."""
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_jsonable(v) for v in x]
    if isinstance(x, (_dt.date, _dt.datetime)):
        return x.isoformat()
    return x


def de_fitxer(f: Path) -> Dict[str, Any]:
    """Un `campanya.yaml` de neudet com a dict per al formulari (dates com a text ISO). Mai no l'escriu."""
    f = Path(f)
    if not f.exists():
        raise DES.DesignError(f"no trobo {f}: cal un campanya.yaml de neudet")
    data = yaml.safe_load(f.read_text())
    if not isinstance(data, dict):
        raise DES.DesignError(f"{f}: el campanya.yaml no és un diccionari")
    return a_inventari(_jsonable(_a_tongades(data)))


# ── INV (contracte UI §10c): el formulari és «primer els tubs disponibles, després on van» ──
#: clau del formulari (no del yaml) amb la nota de conversió d'una campanya antiga: {convertida: [...], nomes_lectura: motiu|None}
CONVERSIO = "_conversio"


def _lletra(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _un(v: Any) -> Tuple[bool, Any]:
    """(és un sol valor, el valor) d'un atribut: valor, llista d'un element o {valors: [un]}."""
    if isinstance(v, dict) and "valors" in v:
        v = v["valors"]
    if isinstance(v, list):
        return (len(v) == 1, v[0] if len(v) == 1 else v)
    return (True, v)


def _cd_simple(cd: Any) -> Tuple[bool, Dict[str, Any]]:
    """(és un sol valor, el Cd normalitzat {fraction[, arc, centre]}). Fracció 0 = sense Cd (arc i centre no compten)."""
    cd = cd if isinstance(cd, dict) else {"fraction": 0}
    vals = {}
    for k in ("fraction", "arc", "centre"):
        if k in cd:
            ok, v = _un(cd[k]) if not isinstance(cd[k], dict) else (False, cd[k])
            if not ok:
                return False, cd
            vals[k] = v
    if not vals.get("fraction"):
        return True, {"fraction": 0}
    return True, {k: vals[k] for k in ("fraction", "arc", "centre") if k in vals}


def _cd_trivial(cd: Any) -> bool:
    ok, c = _cd_simple(cd)
    return ok and not c.get("fraction")


def _n_fix(n: Any) -> Optional[int]:
    """L'n d'un anell si és un sol enter (valor, llista d'un, rang de == a); si no, None."""
    if isinstance(n, dict) and {"de", "a"} <= set(n):
        return int(n["de"]) if n["de"] == n["a"] else None
    ok, v = _un(n)
    return int(v) if ok and isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _converteix_tongada(t: Dict[str, Any], tub0: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Una tongada d'abans (`tipus` per tongada, anell o punt) → la mateixa amb `inventari` de recursos (els mateixos tubs a cada
    candidat). (tongada nova, None) o (None, per què no es pot)."""
    t = copy.deepcopy(t)
    pos = t.get("posicions") or {}
    font = pos.get("font")
    sel = t.get("seleccio", "exhaustiu")
    if sel not in (None, "exhaustiu"):
        return None, "fa servir «mostres»: amb un inventari el sorteig seria un altre"
    ok_t, tp_t = _un(t.get("tipus", tub0))
    cd_t = t.get("cd")
    llig_t = (cd_t or {}).get("lligam", "global") if isinstance(cd_t, dict) else "global"
    ok_cdt, cdn_t = _cd_simple(cd_t)
    for k in ("tipus", "cd"):
        t.pop(k, None)
    if font == "malla":
        if not ok_t or not tp_t:
            return None, "la malla prova un ventall de tipus (cada tub, un dels tipus): no és un inventari fix"
        k = pos.get("k", 1)
        if not isinstance(k, int) or k < 1:
            return None, "la malla no diu quants tubs (k)"
        if not ok_cdt and llig_t not in ("global", "tub"):
            return None, "el Cd en ventall té lligam «%s»" % llig_t
        cd = cdn_t if ok_cdt else dict(cd_t)
        t["inventari"] = [{"nom": "A", "tipus": tp_t, "quantitat": k, "cd": cd}]
        return t, None
    if font not in ("anells", "punts"):
        return None, "font %r" % font
    its = pos.get("anells") if font == "anells" else pos.get("punts")
    claus, ns = [], []
    for i, q in enumerate(its or []):
        ok, tp = _un(q.get("tipus", tp_t))
        if not ok or not tp:
            return None, "%s %d prova un ventall de tipus" % ("l'anell" if font == "anells" else "el punt", i + 1)
        cdq = q.get("cd", cd_t)
        okc, cdn = _cd_simple(cdq)
        if not okc:
            if q.get("cd") is not None:
                return None, "%s %d té un ventall de Cd propi" % ("l'anell" if font == "anells" else "el punt", i + 1)
            cdn = None                                   # el ventall de la tongada: només amb un sol recurs (es mira a sota)
        claus.append((tp, json.dumps(cdn, sort_keys=True)))
        ns.append(1 if font == "punts" else _n_fix(q.get("n")))
    unics = list(dict.fromkeys(claus))
    if not ok_cdt and (len(unics) > 1 or llig_t not in ("global", "tub")):
        return None, "el Cd de la tongada és un ventall i hi ha més d'un tipus de tub (o lligam «%s»)" % llig_t
    noms = {k: _lletra(i) for i, k in enumerate(unics)}
    if font == "anells":
        nt = pos.get("n_total")
        if len(unics) == 1:
            tot = nt if isinstance(nt, int) else (sum(ns) if all(n is not None for n in ns) else None)
            if tot is None:
                return None, "els anells tenen n variable i cap n_total: no hi ha un nombre de tubs fix"
            quant = {unics[0]: tot}
        else:
            if any(n is None for n in ns):
                return None, ("hi ha anells de tipus diferents amb n variable (p. ex. c02 S3): un inventari fix no ho pot dir en "
                              "una sola tongada")
            if isinstance(nt, int) and nt != sum(ns):
                return None, "n_total %d no és la suma dels anells (%d): cap candidat" % (nt, sum(ns))
            quant = {}
            for k, n in zip(claus, ns):
                quant[k] = quant.get(k, 0) + n
        if not sum(quant.values()):
            return None, "cap tub"
        for q, k, n in zip(its, claus, ns):
            q.pop("tipus", None); q.pop("cd", None)
            if len(unics) > 1:
                q["n"] = n
                if n:
                    q["fixats"] = {noms[k]: n}
        pos.pop("n_total", None)
    else:
        quant = {}
        for k in claus:
            quant[k] = quant.get(k, 0) + 1
        for q, k in zip(its, claus):
            q.pop("tipus", None); q.pop("cd", None)
            if len(unics) > 1:
                q["tipus_permesos"] = [noms[k]]
    inv = []
    for k in unics:
        if not quant.get(k):
            continue
        cd = json.loads(k[1]) if k[1] != "null" else dict(cd_t)
        inv.append({"nom": noms[k], "tipus": k[0], "quantitat": quant[k], "cd": cd})
    t["inventari"] = inv
    return t, None


def a_inventari(form: Dict[str, Any]) -> Dict[str, Any]:
    """INV: cada tongada del formulari en la forma nova (inventari de recursos `[{nom, tipus, quantitat, cd}]`, sense `tipus` ni
    `cd` per anell, punt o tongada). Una tongada d'abans es converteix (els mateixos tubs a cada candidat; ho comprova el test
    contra neudet) i ho diu a `_conversio.convertida`; si no es pot, la campanya s'obre en **només lectura** i
    `_conversio.nomes_lectura` diu per què. `{tipus: n}` (INV-T) passa a llista amb nom = tipus."""
    form = copy.deepcopy(form)
    et = form.get("etapes") if isinstance(form, dict) else None
    if not isinstance(et, dict):
        return form
    dom = form.get("domini") or {}
    tub0 = (dom.get("tipus_tub") or [None])[0]
    conv, ro = [], []
    for nom, e in et.items():
        ts = (e or {}).get("tongades") if isinstance(e, dict) else None
        if not isinstance(ts, list):
            continue
        for i, t in enumerate(ts):
            if not isinstance(t, dict):
                continue
            font = (t.get("posicions") or {}).get("font")
            on = "etapa %s, tongada «%s»" % (nom, t.get("nom", i))
            if font == "dat":
                continue
            inv = t.get("inventari")
            if isinstance(inv, list):
                continue
            if isinstance(inv, dict):                       # INV-T: {tipus: n} → recursos amb nom = tipus
                its = (t.get("posicions") or {}).get("anells") or (t.get("posicions") or {}).get("punts") or []
                if not all(_cd_trivial(x.get("cd")) for x in [t] + list(its)):
                    ro.append("%s: inventari amb Cd per tongada o per anell (el Cd ara és del recurs)" % on)
                    continue
                t["inventari"] = [{"nom": k, "tipus": k, "quantitat": q, "cd": {"fraction": 0}} for k, q in inv.items()]
                for x in [t] + list(its):
                    x.pop("cd", None)
                conv.append("%s: inventari {tipus: n} → recursos (nom = tipus)" % on)
                continue
            nou, motiu = _converteix_tongada(t, tub0)
            if nou is None:
                ro.append("%s: %s" % (on, motiu))
                continue
            ts[i] = nou
            conv.append("%s: %s" % (on, ", ".join("%s = %d × %s" % (r["nom"], r["quantitat"], r["tipus"]) for r in nou["inventari"])))
    if conv or ro:
        form[CONVERSIO] = {"convertida": conv, "nomes_lectura": "; ".join(ro) or None}
    return form


def _neteja_traduccio(x: Any) -> Any:
    """Treu els camps propis de la traducció (`_antic`, `nom_candidat`, `params` de la tongada de `punts`): no són al contracte."""
    if isinstance(x, dict):
        return {k: _neteja_traduccio(v) for k, v in x.items() if k not in INTERN_TRADUCCIO and k not in ("nom_candidat", "params")}
    if isinstance(x, list):
        return [_neteja_traduccio(v) for v in x]
    return x


def _explicita(t: Dict[str, Any]) -> Dict[str, Any]:
    """Els valors que la fitxa (`fitxa: 1`) exigeix explícits i que la traducció deixa per defecte: `seleccio`, `z`, `phi` i
    `eix`. Cap no canvia el candidat: són els valors per defecte de neudet (exhaustiu, z = 0, φ = 0, eix z)."""
    t.setdefault("seleccio", "exhaustiu")
    pos = t.get("posicions") or {}
    f = pos.get("font")
    if f == "malla":
        pos.setdefault("z", 0)
    if f == "punts":
        for q in pos.get("punts") or []:
            q.setdefault("z", 0)
    if f == "anells":
        for a in pos.get("anells") or []:
            a.setdefault("phi", 0)
    if f in ("punts", "anells", "malla") and "eix" not in t:
        its = pos.get("punts") if f == "punts" else pos.get("anells") if f == "anells" else []
        if not its or any("eix" not in q for q in its):
            t["eix"] = "z"
    return t


def _a_tongades(data: Dict[str, Any]) -> Dict[str, Any]:
    """Un campanya.yaml amb `generador` (antic) → el mateix amb `tongades` (GEN-U), traduït per neudet
    (`generadors.tradueix_antic`): els mateixos candidats i hashes. No toca el que ja porta `tongades`."""
    et = data.get("etapes") if isinstance(data, dict) else None
    if not isinstance(et, dict) or not any(isinstance(e, dict) and "generador" in e for e in et.values()):
        return data
    _, gen = DES._neudet()
    dom = data.get("domini") or {}
    restr = dom.get("restriccions") or {}
    out = copy.deepcopy(data)
    for nom, e in out["etapes"].items():
        if isinstance(e, dict) and "generador" in e and "tongades" not in e:
            ctx = dict(tipus=list(dom.get("tipus_tub") or []), n_tubs=e.get("n_tubs", restr.get("n_tubs")),
                       restriccions=restr, arrel=".")
            ts = [_explicita(t) for t in _neteja_traduccio(gen.tradueix_antic(e["generador"], ctx))]
            e2 = {}
            for k, v in e.items():                           # `tongades` al lloc de `generador`
                e2["tongades" if k == "generador" else k] = ts if k == "generador" else v
            out["etapes"][nom] = e2
    return out


def defaults() -> Dict[str, Any]:
    """El `campanya.yaml` de c04_draft tal com és a neudet (dict, dates com a text ISO)."""
    return de_fitxer(DES.neudet_root() / C04_YAML)


# Contracte UI §19 (font per defecte d'una campanya nova): font isòtropa sobre l'eix, a 5 cm de la cara z− del bloc, entre = buit.
# El 5 cm és del contracte (no és a neudet); la UI només l'aplica, neudet jutja la font (FONT-A/B).
FONT_CARA_CM = 5
FONT_CARA_MM_ERROR = 0.1                    # §19: neudet dona error si la font és a menys d'1 mm d'una cara (en cm)


def font_defecte(mides_cm) -> Dict[str, Any]:
    """§19: `{tipus: iso, pos_cm: [0, 0, −(mides_cm[2]/2 + 5)]}`."""
    if not _llista_de(mides_cm, _pos, 3):
        raise DES.DesignError("font per defecte: calen les tres mides del bloc (domini.bloc.mides_cm), en cm")
    z = -(float(mides_cm[2]) / 2 + FONT_CARA_CM)
    return {"tipus": "iso", "pos_cm": [0, 0, int(z) if z == int(z) else z]}


def font_avis(domini: Dict[str, Any]) -> Optional[str]:
    """`dins` | `cara` | None: la font iso és dins del bloc o a menys d'1 mm d'una cara (§19; neudet FONT-A/B). Només avís."""
    f = domini.get("font") or {}
    m = (domini.get("bloc") or {}).get("mides_cm")
    if f.get("tipus") != "iso" or not _llista_de(m, _pos, 3) or not _llista_de(f.get("pos_cm"), _num, 3):
        return None
    d = [abs(float(p)) - float(h) / 2 for p, h in zip(f["pos_cm"], m)]       # <0: dins de la franja d'aquell eix
    if all(x < -FONT_CARA_MM_ERROR for x in d):
        return "dins"
    if all(x <= FONT_CARA_MM_ERROR for x in d):
        return "cara"
    return None


def _fitxa():
    """`neudet.disseny.fitxa` (registre i regla de validació de neudet), o None si no hi és."""
    try:
        DES._neudet()
        from neudet.disseny import fitxa
        return fitxa
    except Exception:                                            # noqa: BLE001
        return None


#: contracte §18: el text que neudet posa a tot arreu on surt una xifra d'una campanya de diagnòstic
DIAGNOSTIC_TEXT = "diagnòstic, no citable"
CKPT_BASE = "BASELINE"


def ckpts_disponibles() -> Optional[Dict[str, List[str]]]:
    """DIAG-UI (contracte §18): els ckpts que neudet sap resoldre per material, `{material: [nom, …]}`: els directoris de
    `<simnet>/data/material/<M>/ckpt/neutro/` amb `ckpt_final.pt` (el mateix lloc on `Campanya.ckpts_yaml` els busca; no se'n fa còpia).
    BASELINE primer. None si simnet no és trobable."""
    root = MS.owner_root("simnet")
    if root is None:
        return None
    out: Dict[str, List[str]] = {}
    for mat in sorted((root / "data" / "material").glob("*")):
        noms = sorted(p.parent.name for p in (mat / "ckpt" / "neutro").glob("*/ckpt_final.pt"))
        if noms:
            out[mat.name] = sorted(noms, key=lambda n: (n != CKPT_BASE, n))
    return out


def energies_domini() -> Optional[Dict[str, Any]]:
    """El domini d'energies de neudet (validacions.json, secció `domini`, CAMP-2): {min, max, per_defecte}.
    La campanya tria les energies que vulgui; neudet certifica que siguin dins de min–max (fitxa.py).
    `per_defecte` és la graella de sempre (11 energies). None si el registre no hi és."""
    reg = _validacions()
    d = ((reg or {}).get("domini") or {}).get("energies_MeV")
    if not (isinstance(d, dict) and isinstance(d.get("per_defecte"), list) and d["per_defecte"]):
        return None
    return {"min": d.get("min"), "max": d.get("max"), "max_diagnostic": d.get("max_diagnostic"), "validat_PE_min": d.get("validat_PE_min"),
            "per_defecte": [float(x) for x in d["per_defecte"]], "nota": d.get("nota"),
            "font": "validacions.json · domini.energies_MeV"}


def _validacions() -> Optional[Dict[str, Any]]:
    """`validacions.json` del config de neudet, si existeix (CAMP-1). Si no, None: no hi ha registre."""
    f = DC.config_dir() / "validacions.json"
    if not f.exists():
        return None
    data = json.loads(f.read_text())
    return data if isinstance(data, dict) else {}


def cd_avis() -> str:
    """El límit del Cd que declara neudet (`validacions.json`, secció `cd`: el «Límit: …» de CERT-Cd), o «» si no
    n'hi ha. Cd és validat a tots els tubs genèrics del catàleg: no hi ha avís general. Qui no el té validat (counterGSI,
    lnd300_v0_*) surt a la certificació de neudet (`comprova_campanya`: Cd no validat). Sense registre, no hi ha límit."""
    cd = (_validacions() or {}).get("cd")
    for e in (cd.values() if isinstance(cd, dict) else []):
        m = re.search(r"Límit:\s*(.+)$", str(e.get("motiu", "")) if isinstance(e, dict) else "")
        if m:
            return f"Límit del Cd (CERT-Cd, validacions.json): {m.group(1).strip()}"
    return ""


# ── neudet: les llistes i les explicacions, llegides del codi ────────────────

def _neudet_path(fitxer: str, dir_=_DIS) -> Path:
    f = DES.neudet_root().joinpath(*dir_, fitxer)
    if not f.exists():
        raise DES.DesignError(f"no trobo {fitxer} a neudet ({f})")
    return f


def _troba(fitxer: str, linia: int, token: str, dir_=_DIS) -> int:
    """La línia de `fitxer` de neudet que conté `token`: la citada si encara el conté; si neudet ha mogut el
    codi, la més propera que el contingui. Només peta si el text ja no hi és enlloc (llavors sí que ha canviat
    el que simphy llegeix). Un número de línia exacte trencava la UI a cada edició de neudet (2026-10-26)."""
    lines = _neudet_path(fitxer, dir_).read_text(encoding="utf-8").splitlines()
    if 1 <= linia <= len(lines) and token in lines[linia - 1]:
        return linia
    hits = [i + 1 for i, l in enumerate(lines) if token in l]
    if not hits:
        raise DES.DesignError(
            f"neudet ha canviat: {fitxer} ja no conté «{token}» (era a la línia {linia}). Cal revisar la llista "
            f"a campanya_form.py")
    return min(hits, key=lambda n: abs(n - linia))


def _linia(fitxer: str, linia: int, token: str, dir_=_DIS) -> str:
    """El text de la línia de `fitxer` de neudet que conté `token` (vegeu `_troba`)."""
    lines = _neudet_path(fitxer, dir_).read_text(encoding="utf-8").splitlines()
    return lines[_troba(fitxer, linia, token, dir_) - 1]


def _comentari(fitxer: str, linia: int, dir_=_DIS, token: Optional[str] = None) -> str:
    """El comentari `# …` de la línia de neudet (la que conté `token`, si se'n dona); «» si no n'hi ha."""
    l = _linia(fitxer, linia, token, dir_) if token else \
        _neudet_path(fitxer, dir_).read_text(encoding="utf-8").splitlines()[linia - 1]
    return l.split("#", 1)[1].strip() if "#" in l else ""


def _entrades_docstring(fitxer: str, dir_=_DIS) -> Dict[str, Dict[str, Any]]:
    """Les entrades «    nom  · text» del docstring del mòdul de neudet: {nom: {text, linia}}.
    El paràgraf és el text de l'entrada i les seves línies de continuació (més indentades)."""
    mod = ast.parse(_neudet_path(fitxer, dir_).read_text(encoding="utf-8"))
    doc = mod.body[0] if mod.body else None
    if not (isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant) and isinstance(doc.value.value, str)):
        raise DES.DesignError(f"{fitxer}: el mòdul no té docstring: no hi ha on llegir l'ajuda")
    out: Dict[str, Dict[str, Any]] = {}
    actual = None
    for k, l in enumerate(doc.value.value.splitlines()):
        m = _ENTRADA.match(l)
        if m:
            actual = m.group(1)
            out[actual] = {"parts": [m.group(2).strip()], "linia": doc.lineno + k}
        elif actual and l.startswith(" " * 10) and l.strip():
            out[actual]["parts"].append(l.strip())
        else:
            actual = None
    return {n: {"text": " ".join(v["parts"]), "linia": v["linia"]} for n, v in out.items()}


def _metriques_neudet(obj) -> Dict[str, Dict[str, Any]]:
    """Els registres de mètriques de neudet, en una sola taula: {nom: {familia, sentit, descripcio}}."""
    out: Dict[str, Dict[str, Any]] = {}
    for familia, reg in (("base", obj.METRIQUES), ("grup MET2", obj.METRIQUES_GRUP),
                         ("IND", obj.METRIQUES_GRUP2), ("MET3", obj.METRIQUES_GRUP3)):
        for nom, v in reg.items():
            if familia == "base":
                sentit, desc = v[1], v[2]
            else:
                sentit, desc = v[0], v[1]
            if nom in obj.GEOMETRIQUES:
                familia = "geomètrica (x03)"
            out[nom] = {"familia": familia, "sentit": sentit, "descripcio": desc}
    return out


def _comprova_llista(nom: str, neudet_noms, pinned) -> None:
    """La llista tancada de neudet és la que hi ha aquí. Si no, peta dient què ha canviat."""
    if set(neudet_noms) != set(pinned):
        raise DES.DesignError(
            f"neudet ha canviat {nom}: té {sorted(neudet_noms)} i simphy {sorted(pinned)}. "
            f"Cal revisar campanya_form.py ({nom}_LINIA) i els tests")


def _mods_neudet():
    """(objectius, cerca) de neudet, importats de NEUDET_ROOT/src."""
    DES._neudet()
    from neudet.disseny import cerca, objectius
    return objectius, cerca


def _schema_objectius(obj) -> Dict[str, Any]:
    met = _metriques_neudet(obj)
    _comprova_llista("metriques", met, METRIQUES_LINIA)
    for nom, linia in METRIQUES_LINIA.items():
        _linia(OBJECTIUS_PY, linia, f'"{nom}"')
    if not all(m["sentit"] in SENTITS for m in met.values()):
        raise DES.DesignError(f"neudet ha canviat els sentits de les mètriques ({OBJECTIUS_PY}): cal revisar SENTITS")
    _linia(OBJECTIUS_PY, SENTITS_LINIA, '"max"')
    _linia(OBJECTIUS_PY, ERR_GRUPS_CAL_LINIA, "err_grups: cal objectius.grups_MeV")
    _linia(OBJECTIUS_PY, AUTO_LINIA, "for n in [p[0] for p in self.pareto]")
    _linia(OBJECTIUS_PY, PESOS_DEFECTE_LINIA, 'cfg.get("pesos", "uniforme")')
    _linia(OBJECTIUS_PY, PESOS_LINIA["letargia"], 'w == "letargia"')
    _linia(OBJECTIUS_PY, PESOS_LINIA["uniforme"], 'w == "uniforme"')
    _linia(OBJECTIUS_PY, K_SIGMA_LINIA, 'pareto_k_sigma')
    _linia(OBJECTIUS_PY, ENERGIES_LINIA, 'sel == "totes"')
    _linia(OBJECTIUS_PY, RESTRICCIO_LINIA, 'cfg.get("restriccio")')
    _linia(OBJECTIUS_PY, DEFECTE_NOMS_LINIA, 'cfg.get("metriques"')
    _linia(CAMPANYA_PY, NOTA_LINIA, '"**Què:**')
    _linia(FITXA_PY, 35, '"objectius.pesos"')
    _linia(OBJECTIUS_PY, FINALITATS_LINIA, "FINALITATS: Dict[str, dict] = {")
    _linia(OBJECTIUS_PY, TAULA_LINIA, "def taula_objectius()")
    taula = obj.taula_objectius()                          # OBJ: la font única (contracte §14)
    nous = {k: tuple(v["metriques"]) for k, v in taula["finalitats"].items()}
    if nous != FINALITAT_METRIQUES or taula["alies"] != ALIES_OBJ or tuple(taula["operadors"]) != OPERADORS:
        raise DES.DesignError(f"neudet ha canviat la taula d'objectius ({OBJECTIUS_PY}, taula_objectius): té {nous}, "
                              f"{taula['alies']}, {taula['operadors']}; cal revisar FINALITAT_METRIQUES a campanya_form.py")
    d = obj.Objectiu({}, [1.0])                             # els defaults, llegits de neudet (no copiats)
    metriques = []
    for nom, linia in METRIQUES_LINIA.items():
        m = met[nom]
        metriques.append({"nom": nom, "familia": m["familia"], "sentit": m["sentit"],
                          "descripcio": m["descripcio"], "fitxer": OBJECTIUS_PY, "linia": linia,
                          "requereix": ({"clau": "objectius.grups_MeV", "fitxer": OBJECTIUS_PY,
                                         "linia": ERR_GRUPS_CAL_LINIA} if nom == "err_grups" else None)})
    pes_doc = (obj.pesos_letargia.__doc__ or "").strip().split("\n")[0]
    return {
        "metriques": metriques,
        "metriques_defecte": {"valors": list(DEFECTE_NOMS), "fitxer": OBJECTIUS_PY, "linia": DEFECTE_NOMS_LINIA},
        "sentits": [{"valor": s, "fitxer": OBJECTIUS_PY, "linia": SENTITS_LINIA} for s in SENTITS],
        "energies": {"totes": {"fitxer": OBJECTIUS_PY, "linia": ENERGIES_LINIA},
                     "graella": {"fitxer": OBJECTIUS_PY, "linia": GRAELLA_LINIA}},
        "pesos": [
            {"valor": "uniforme", "descripcio": "pesos iguals per energia (objectius.py:209)",
             "fitxer": OBJECTIUS_PY, "linia": PESOS_LINIA["uniforme"]},
            {"valor": "letargia", "descripcio": pes_doc, "fitxer": OBJECTIUS_PY,
             "linia": PESOS_LINIA["letargia"]},
        ],
        "pesos_defecte": {"valor": "uniforme", "fitxer": OBJECTIUS_PY, "linia": PESOS_DEFECTE_LINIA,
                          "fitxa": {"fitxer": FITXA_PY, "linia": 35}},
        "pareto": {"n": 2, "defecte": [list(x) for x in d.pareto],
                   "motiu": "campanya.py: els gràfics usen ob.pareto[-1] i [0]",
                   "fitxer": CAMPANYA_PY, "linia": 295, "auto": {"fitxer": OBJECTIUS_PY, "linia": AUTO_LINIA}},
        "pareto_k_sigma": {"defecte": float(d.k_sigma), "minim": 0, "fitxer": OBJECTIUS_PY,
                           "linia": K_SIGMA_LINIA,
                           "descripcio": "frontera robusta: només domina qui guanya per més de k·σ. "
                                         "Amb k = 0 és la frontera de Pareto (objectius.py, frontera_robusta)"},
        "altres": [
            {"clau": "comptes_ref", "defecte": d.comptes_ref, "fitxer": OBJECTIUS_PY, "linia": 232,
             "descripcio": "comptes de referència de res_E, N_obj i sE_N (sense comentari a neudet)"},
            {"clau": "N_font", "defecte": d.N_font, "fitxer": OBJECTIUS_PY, "linia": 233,
             "descripcio": _comentari(OBJECTIUS_PY, 233, token='"N_font"')},
            {"clau": "sE_obj", "defecte": d.sE_obj, "fitxer": OBJECTIUS_PY, "linia": 234,
             "descripcio": _comentari(OBJECTIUS_PY, 234, token='"sE_obj"')},
            {"clau": "delta_q", "defecte": d.delta_q, "fitxer": OBJECTIUS_PY, "linia": 235,
             "descripcio": _comentari(OBJECTIUS_PY, 235, token='"delta_q"')},
            {"clau": "grups_MeV", "defecte": [], "fitxer": OBJECTIUS_PY, "linia": 236,
             "descripcio": _comentari(OBJECTIUS_PY, 236, token='"grups_MeV"') + " (cal per a err_grups)"},
            {"clau": "restriccio", "defecte": {"maxim": d.restriccio["maxim"], "sobre": d.restriccio["sobre"],
                                              "c": []}, "fitxer": OBJECTIUS_PY, "linia": RESTRICCIO_LINIA,
             "descripcio": "ε-restricció: maximitzar «maxim» amb «sobre» ≤ c; sense c, no n'hi ha"},
        ],
        # OBJ (contracte §14): el bloc del cicle nou, tal com el dona neudet (frases, preguntes, valors per defecte)
        "cicle_nou": dict(taula, fitxer=OBJECTIUS_PY, linia=TAULA_LINIA),
    }


def _schema_cerca(cer, ajudes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    _comprova_llista("cerca", cer.CERQUES, CERQUES_LINIA)
    _linia(CAMPANYA_PY, CERCA_EXEC_DEFECTE_LINIA, '"cerca"')
    for nom, linia in CERQUES_LINIA.items():
        _linia(CERCA_PY, linia, f'registra("{nom}")')
    _linia(CERCA_PY, CERCA_DEFECTE_LINIA, 'spec.get("tipus", "exhaustiva")')
    tipus = []
    for nom, linia in CERQUES_LINIA.items():
        a = ajudes.get(nom)
        if a is None:
            raise DES.DesignError(f"neudet: {CERCA_PY} no té l'entrada «{nom}» al docstring")
        tipus.append({"valor": nom, "ajuda": a["text"], "fitxer": CERCA_PY, "linia": linia,
                      "linia_ajuda": a["linia"]})
    for nom, camps in CERCA_CAMPS.items():
        for c in camps:
            _linia(CERCA_PY, c["linia"], f'"{c["clau"]}"')
    return {"fitxer": CERCA_PY, "tipus": tipus, "defecte": {"valor": "exhaustiva", "fitxer": CERCA_PY,
                                        "linia": CERCA_DEFECTE_LINIA,
                                        "exec_fitxer": CAMPANYA_PY, "exec_linia": CERCA_EXEC_DEFECTE_LINIA},
            "camps": CERCA_CAMPS}


def _schema_avaluacio() -> Dict[str, Any]:
    for nom, linia in XARXES_LINIA.items():
        _linia(AVALUADOR_PY, linia, f'"{nom}"')
    for nom, linia in MODES_LINIA.items():
        _linia(AVALUADOR_PY, linia, f'"{nom}"')
    _linia(CAMPANYA_PY, CD_MODE_REGLA_LINIA, 'mode != "continu"')
    _linia(CAMPANYA_PY, MODE_DEFECTE_LINIA, 'av_cfg.get("mode"')
    _linia(CAMPANYA_PY, XARXA_DEFECTE_LINIA, 'av_cfg.get("xarxa"')
    _linia(CAMPANYA_PY, GEOM_VECT_LINIA, 'geom_vect')
    _linia(CAMPANYA_PY, 137, 'gpus')
    for clau, c in AVALUACIO_CAMPS.items():
        _linia(CAMPANYA_PY, c["linia"], clau)
    return {
        "fitxer": CAMPANYA_PY,
        "xarxa": {"valors": [
            {"valor": "A", "descripcio": "xarxa fent tota la feina (valor per defecte)",
             "fitxer": AVALUADOR_PY, "linia": XARXES_LINIA["A"]},
            {"valor": "B1", "descripcio": "recorregut i grup de canal amb TAULES Σ del Geant4 de referència "
                                          "(obligatori amb Cd)", "fitxer": AVALUADOR_PY,
             "linia": XARXES_LINIA["B1"]}], "defecte": "A", "fitxer": CAMPANYA_PY,
            "linia": XARXA_DEFECTE_LINIA},
        "mode": {"valors": [
            {"valor": "lots", "descripcio": "totes les energies al mateix bucle de passos (per defecte)",
             "fitxer": AVALUADOR_PY, "linia": MODES_LINIA["lots"]},
            {"valor": "per_energia", "descripcio": "bit a bit el probe, una energia cada vegada",
             "fitxer": AVALUADOR_PY, "linia": MODES_LINIA["per_energia"]},
            {"valor": "continu", "descripcio": "motor continu: geometria per neutró; obligatori amb Cd",
             "fitxer": CAMPANYA_PY, "linia": CD_MODE_REGLA_LINIA}], "defecte": "lots",
            "fitxer": CAMPANYA_PY, "linia": MODE_DEFECTE_LINIA},
        "camps": {k: {"minim": c["minim"], "defecte": c["defecte"], "fitxer": CAMPANYA_PY,
                      "linia": c["linia"], "descripcio": c["descripcio"]} for k, c in AVALUACIO_CAMPS.items()},
        "geom_vect": {"defecte": GEOM_VECT_DEFECTE, "fitxer": CAMPANYA_PY, "linia": GEOM_VECT_LINIA,
                      "descripcio": "geometria vectoritzada: ×1,8 més ràpida, i idèntica (disseny/README.md, "
                                    "§13, línia 299)"},
        "motor": {"fitxer": CAMPANYA_PY, "descripcio": "neudet no el llegeix: el motor el tria «xarxa»"},
        "gpus": {"fitxer": CAMPANYA_PY, "linia": 137,
                 "descripcio": "GPUs i pesos de repartiment (treballador.py), només en mode continu"},
    }


def _schema_verificacio() -> Dict[str, Any]:
    _linia(VERIFICA_G4_PY, 398, '"--aleatoris"', _SCRIPTS)
    _linia(VERIFICA_G4_PY, 400, '"--n"', _SCRIPTS)
    _linia(FITXA_PY, 70, '"n_per_energia"')
    _linia(FITXA_PY, 105, '"n_per_energia"')
    _linia(FITXA_PY, 108, '"hits"')
    return {"quants": {"llegit": True, "fitxer": VERIFICA_G4_PY, "linia": 398,
                       "descripcio": "quants candidats van a Geant4 (verifica_g4.py el llegeix del yaml; --quants el "
                                     "sobreescriu i el meta ho diu, AFINA-N)"},
            "n_per_energia": {"llegit": True, "fitxer": VERIFICA_G4_PY, "linia": 400,
                              "descripcio": "primaris per energia a Geant4 (verifica_g4.py el llegeix del yaml; --n el "
                                            "sobreescriu i el meta ho diu, AFINA-N)"},
            "hits": {"llegit": True, "fitxer": FITXA_PY, "linia": 108,
                     "descripcio": "mode del bolcat de Geant4, obligatori (G4-COMPACT): «all» (tots els passos) o "
                                   "«detect» (només les files He3(n,p), ~60 vegades menys disc)"},
            "porta": {"llegit": False, "fitxer": FITXA_PY, "linia": 105,
                      "descripcio": "text lliure que neudet ja no exigeix (SIMPLIFICA, 2026-11-05); la porta que "
                                    "compta és la del PLA.md de la campanya"}}


def _schema_plantilles() -> Dict[str, Any]:
    """Les tongades que el formulari posa en triar una font. Cada una porta `tipus`, `cd.fraction` i `eix`
    explícits i `seleccio`: la fitxa de neudet ho exigeix (fitxa.py, GEN-U). `__TUB__` és el tipus de tub del domini."""
    base = {"tipus": [TUB], "cd": {"fraction": 0}, "eix": "z", "seleccio": "exhaustiu"}
    return {
        "punts": {"nom": "tongada", "posicions": {"font": "punts", "punts": [{"x": 0, "y": 0, "z": 0}]}, **copy.deepcopy(base)},
        "malla": {"nom": "tongada", "posicions": {"font": "malla", "forma": "quadrada", "k": 1, "z": 0,
                                                   "x": [0], "y": [0]}, **copy.deepcopy(base)},
        "anells": {"nom": "tongada", "posicions": {"font": "anells", "anells": [
            {"r": {"de": 5, "a": 5, "pas": 1}, "n": {"de": 4, "a": 4}, "phi": 0}]}, **copy.deepcopy(base)},
        "dat": {"nom": "tongada", "posicions": {"font": "dat", "dat": ""}, "seleccio": "exhaustiu"},
    }


def _mides_tub(e: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Les dimensions d'un tub del catàleg, llegides d'on les llegeixen Geant4 i neudet (res no es copia).
    Les que importen per saber si el tub CAP són les de `neudet.disseny.candidat.DIMS` (les que neudet fa servir per col·locar-lo:
    radi exterior i extensió en z de tot el tub, que no és la de la paret d'acer ni la del gas); el gas actiu, la paret i la pressió
    surten de `DC.TUBE_TYPES` (`tubs.json` i `tubGeneric.cc`). `None` si el tipus no es pot resoldre."""
    DES._neudet()
    from neudet.disseny import candidat as CAND
    for nom in (e.get("nom"), e.get("alies")):
        if not nom:
            continue
        try:
            tt = DC.TUBE_TYPES[nom]
        except Exception:                                   # noqa: BLE001 — sense mides, el selector no les mostra
            continue
        d = CAND.DIMS.get(nom)
        if d:
            r_ext, zlo, zhi = d["r_ext"], d.get("z_min", -d["mitja_llargada"]), d.get("z_max", d["mitja_llargada"])
        else:                                               # el forat del tub: el que ocupa dins del bloc
            r_ext, zlo, zhi = tt.hole_radius_cm, -tt.hole_length_cm / 2, tt.hole_length_cm / 2
        return {"diametre_cm": round(2 * r_ext, 3), "llargada_total_cm": round(zhi - zlo, 3),
                "z_min_cm": round(zlo, 3), "z_max_cm": round(zhi, 3),
                "llargada_activa_cm": round(tt.gas_length_cm, 3), "z_activa_cm": round(tt.gas_dz_cm, 3), "radi_gas_cm": round(tt.gas_radius_cm, 3),
                "llargada_paret_cm": round(tt.wall_length_cm, 3),
                "pressio_atm": (round(tt.gas_pressure_atm, 3) if tt.gas_pressure_atm else None),
                "paret": e.get("material_paret") or None}
    return None


def schema() -> Dict[str, Any]:
    """Les fonts de tongada i els seus camps, llistes tancades de neudet, tubs del catàleg i estat de la
    validació. Tot ve de neudet, amb la línia on es llegeix."""
    _, gen = DES._neudet()                             # importa neudet.disseny.generadors de NEUDET_ROOT
    obj, cer = _mods_neudet()
    tongades = {"fonts": [{"valor": f, "text": FONTS_TEXT[f]} for f in gen.FONTS if f in FONTS_TEXT],
                "lligams": [{"valor": l, "text": LLIGAMS_TEXT[l]} for l in gen.LLIGAMS if l in LLIGAMS_TEXT],
                "atributs": list(gen.ATRIBUTS), "formes": MALLA_FORMES,
                "max_candidats": gen.MAX_CANDIDATS, "fitxer": GENERADORS_PY}
    falta = [f for f in gen.FONTS if f not in FONTS_TEXT] + [l for l in gen.LLIGAMS if l not in LLIGAMS_TEXT]
    if falta:
        raise DES.DesignError(f"neudet té fonts o lligams que el formulari no coneix: {falta}")
    reg = _validacions()
    F = _fitxa()
    tubs = []
    for e in DC.read_catalog():
        nom = e.get("nom")
        if reg is None or F is None:
            validat, estat, motiu = None, SENSE_REGISTRE, ""
        else:
            # la regla de quina entrada val (àlies, patrons «lnd_sk*») és de neudet: `fitxa._entrada_tub`
            _, v = F._entrada_tub(reg, nom)
            estat = (v or {}).get("estat") or "no_validat"
            motiu = (v or {}).get("motiu") or ("no hi ha veredicte al registre" if v is None else "")
            validat = estat == "validat"
        tubs.append({"nom": nom, "alies": e.get("alies"), "validat": validat, "estat": estat,
                     "motiu": motiu, "mides": _mides_tub(e)})
    _linia(CANDIDAT_PY, FONT_LINIA, "feix")
    _linia(CANDIDAT_PY, EIX_DEFECTE_LINIA, 'eix')
    _linia(CANDIDAT_PY, CD_FRACCIO_LINIA, "cd_fraction fora de")
    _linia(CANDIDAT_PY, CD_ARC_LINIA, "cd_arc_deg fora de")
    _linia(GENERADORS_PY, SLOTS_PAS_LINIA, "pas")
    return {
        "neudet": str(DES.neudet_root()),
        "tongades": tongades,
        "plantilles": _schema_plantilles(),
        "tipus_tub": tubs,
        "energies_domini": energies_domini(),
        "diagnostic": {"text": DIAGNOSTIC_TEXT, "base": CKPT_BASE, "ckpts": ckpts_disponibles(),
                       "max_diagnostic": (energies_domini() or {}).get("max_diagnostic"),
                       "nota": "contracte §18: energies per sobre del màxim validat fins a `max_diagnostic` (de neudet, validacions.json) "
                               "i ckpts no BASELINE; els resultats no són citables"},
        "validacio": {"registre": reg is not None,
                      "motiu": "" if reg is not None else SENSE_REGISTRE},
        "cd": {"fraccio": {"minim": 0, "maxim": 1, "fitxer": CANDIDAT_PY, "linia": CD_FRACCIO_LINIA,
                           "descripcio": "fracció axial coberta: 0 = sense Cd; si no, (0, 1]"},
               "arc": {"minim": 0, "maxim": 360, "fitxer": CANDIDAT_PY, "linia": CD_ARC_LINIA,
                       "descripcio": "arc del Cd en graus, (0, 360] quan hi ha Cd"},
               "centre_deg": 0, "avis": cd_avis(), "exemples_contracte": CD_FRACCIONS},
        "font": {"tipus": [{"valor": t, "fitxer": CANDIDAT_PY, "linia": FONT_LINIA} for t in FONT_TIPUS],
                 "eixos": [{"valor": e, "fitxer": CANDIDAT_PY, "linia": FONT_LINIA} for e in EIXOS],
                 "eix_defecte": {"valor": "z", "fitxer": CANDIDAT_PY, "linia": EIX_DEFECTE_LINIA},
                 "defecte": {"cara_cm": FONT_CARA_CM, "tolerancia_cara_cm": FONT_CARA_MM_ERROR, "entre": "buit",
                             "font": "contracte UI §19 (2026-11-09)"}},
        "objectius": _schema_objectius(obj),
        "cerca": _schema_cerca(cer, _entrades_docstring(CERCA_PY)),
        "avaluacio": _schema_avaluacio(),
        "verificacio": _schema_verificacio(),
    }


# ── el formulari → campanya.yaml ────────────────────────────────────────────

def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _pos(x) -> bool:
    return _num(x) and x > 0


def _enter(x, minim: int = 1) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and x >= minim


def _llista_de(x, ok, n: Optional[int] = None) -> bool:
    """Una llista no buida (de `n` elements, si es diu) amb tots els elements que passen `ok`."""
    if not isinstance(x, list) or not x or (n is not None and len(x) != n):
        return False
    return all(ok(v) for v in x)


def _errors_domini(dom: Dict[str, Any]) -> List[str]:
    e: List[str] = []
    bloc = dom.get("bloc") if isinstance(dom.get("bloc"), dict) else {}
    if not isinstance(dom.get("bloc"), dict):
        e.append("domini.bloc: falta el bloc (material, mides_cm, forat_cm, densitat_gcm3)")
    if not _llista_de(bloc.get("mides_cm"), _pos, 3):
        e.append("domini.bloc.mides_cm: tres mides positives en cm, p. ex. [30, 30, 80]")
    if "forat_cm" in bloc and not (_num(bloc["forat_cm"]) and bloc["forat_cm"] >= 0):
        e.append("domini.bloc.forat_cm: un número ≥ 0 (cm)")
    if bloc.get("densitat_gcm3") is not None and not _pos(bloc.get("densitat_gcm3")):
        e.append("domini.bloc.densitat_gcm3: un número positiu (g/cm³) o null")
    font = dom.get("font") if isinstance(dom.get("font"), dict) else {}
    if font.get("tipus") not in FONT_TIPUS:
        e.append(f"domini.font.tipus: cal {' o '.join(FONT_TIPUS)} (candidat.py:{FONT_LINIA})")
    elif font["tipus"] == "iso":
        if not _llista_de(font.get("pos_cm"), _num, 3):
            e.append("domini.font.pos_cm: tres coordenades en cm, p. ex. [0, 0, 0]")
    else:
        if font.get("eix") not in EIXOS:
            e.append(f"domini.font.eix: cal {' o '.join(EIXOS)} (feix, candidat.py:{FONT_LINIA})")
        if not _llista_de(font.get("desplacament_cm"), _num, 2):
            e.append("domini.font.desplacament_cm: dues coordenades en cm (feix)")
    if not _llista_de(dom.get("energies_MeV"), _pos):
        e.append("domini.energies_MeV: una llista de energies positives en MeV")
    else:
        en = dom["energies_MeV"]
        if len(set(float(x) for x in en)) != len(en):
            e.append("domini.energies_MeV: hi ha energies repetides (neudet ho para: objectius.pesos_letargia)")
        # contracte §8: fora de min–max neudet ho certifica com a «prohibit» (atura sempre): el formulari ja no ho
        # deixa passar. Entre min i validat_PE_min és «no_validat» (només avisa en draft): ho decideix neudet.
        g = energies_domini()
        diag = dom.get("diagnostic") is True
        if g is not None and g.get("min") is not None and g.get("max") is not None:
            # DIAG-UI (§18): amb `domini.diagnostic: true` neudet deixa passar només les energies PER SOBRE del màxim (fitxa.py)
            # DIAG-UI2: el límit de diagnòstic el publica neudet (`max_diagnostic`); sense ell no se n'inventa cap: no es deixa passar res
            md = g.get("max_diagnostic")
            fora = [x for x in en if not (g["min"] <= float(x) <= g["max"])
                    and not (diag and md is not None and g["max"] < float(x) <= md)]
            if fora:
                if diag and md is None and any(float(x) > g["max"] for x in fora):
                    e.append(f"domini.energies_MeV: {', '.join('%g' % x for x in fora)} MeV: neudet no publica `max_diagnostic` a validacions.json "
                             f"(domini.energies_MeV); sense ell el diagnòstic no té límit conegut (contracte §18)")
                else:
                    lim = (f"; amb diagnòstic, fins a {md:g} MeV" if md is not None else "")
                    e.append(f"domini.energies_MeV: {', '.join('%g' % x for x in fora)} MeV fora del domini permès "
                             f"{g['min']:g}–{g['max']:g} MeV{lim} (validacions.json; contracte §8/§18: «prohibit»)")
    if "diagnostic" in dom and not isinstance(dom["diagnostic"], bool):
        e.append("domini.diagnostic: sí o no (contracte §18)")
    tt = dom.get("tipus_tub")                  # SIMPLIFICA: neudet el deriva dels tipus de les tongades; el formulari ja no l'escriu
    if tt is not None and not (isinstance(tt, list) and tt and all(isinstance(t, str) and t for t in tt)):
        e.append("domini.tipus_tub: una llista de noms de tub (del catàleg), o res (neudet el deriva de les tongades)")
    r = dom.get("restriccions") if isinstance(dom.get("restriccions"), dict) else {}
    nt = r.get("n_tubs")
    if not (isinstance(nt, int) and not isinstance(nt, bool) and nt >= 1):
        e.append("domini.restriccions.n_tubs: un enter ≥ 1")
    for k in ("marge_bloc_cm", "sep_min_cm", "r_min_font_cm"):
        if k in r and r[k] is not None and not (_num(r[k]) and r[k] >= 0):
            e.append(f"domini.restriccions.{k}: un número ≥ 0 (cm) o buit")
    return e


def _valor_o_rang(v: Any) -> bool:
    """Un número, una llista de números, o un rang {de, a, pas} (generadors.py: `valors`)."""
    if isinstance(v, dict):
        return _num(v.get("de")) and _num(v.get("a")) and (v.get("pas", 1) is None or _pos(v.get("pas", 1)))
    if isinstance(v, list):
        return bool(v) and all(_num(x) for x in v)
    return _num(v)


def _errors_rang(v: Any, ruta: str, nom: str, enter: bool = False, maxim: Optional[float] = None) -> List[str]:
    """Un valor, una llista o un rang {de, a, pas} amb sentit: de ≤ a, pas > 0 (neudet divideix pel pas a
    `generadors.valors`: amb pas 0 o buit peta amb ZeroDivisionError/TypeError, sense dir quin camp és).
    Per als tubs (`enter`): enters ≥ 0, pas enter ≥ 1 i, si hi ha `maxim` (n_total), a ≤ maxim.
    Cada missatge comença pel camp exacte (el `data-p` de la pàgina), perquè la pàgina el marqui."""
    ok = (lambda x: isinstance(x, int) and not isinstance(x, bool) and x >= 0) if enter else _num
    tipus = "un enter ≥ 0" if enter else "un número"
    if isinstance(v, dict):
        e = []
        for k in ("de", "a"):
            if not ok(v.get(k)):
                e.append(f"{ruta}.{k}: {nom} «{'de' if k == 'de' else 'a'}» ha de ser {tipus}")
        pas = v.get("pas", 1)
        if enter and not (isinstance(pas, int) and not isinstance(pas, bool) and pas >= 1):
            e.append(f"{ruta}.pas: el pas de {nom} ha de ser un enter ≥ 1 (en blanc = 1)")
        elif not enter and not _pos(pas):
            e.append(f"{ruta}.pas: el pas de {nom} ha de ser > 0 (en blanc = 1)")
        if not e:
            if v["de"] > v["a"]:
                e.append(f"{ruta}.a: {nom}: «a» ({v['a']:g}) ha de ser ≥ «de» ({v['de']:g})")
            elif v["a"] > v["de"] and pas > v["a"] - v["de"]:
                e.append(f"{ruta}.pas: el pas de {nom} ({pas:g}) és més gran que l'interval {v['de']:g}–{v['a']:g}")
            if maxim is not None and v["a"] > maxim:
                e.append(f"{ruta}.a: {nom}: «a» ({v['a']:g}) no pot passar de n_total ({maxim:g})")
        return e
    if isinstance(v, list):
        if not v or not all(ok(x) for x in v):
            return [f"{ruta}: {nom}: una llista no buida; cada element, {tipus}"]
        if maxim is not None and max(v) > maxim:
            return [f"{ruta}: {nom}: cap valor pot passar de n_total ({maxim:g})"]
        return []
    if not ok(v):
        return [f"{ruta}: {nom} ha de ser {tipus}, una llista o un rang de–a amb pas"]
    if maxim is not None and v > maxim:
        return [f"{ruta}: {nom} ({v:g}) no pot passar de n_total ({maxim:g})"]
    return []


def _punts_cd(v: Any, ruta: str) -> List[Tuple[str, float]]:
    """Els números que posa l'usuari (amb el camp on són) d'un valor, una llista o un rang {de, a, pas} de Cd.
    D'un rang només els extrems: si són dins del domini, tot el que hi ha entremig també ho és."""
    if isinstance(v, dict):
        return [(f"{ruta}.{k}", v[k]) for k in ("de", "a")]
    if isinstance(v, list):
        return [(f"{ruta}.{i}", x) for i, x in enumerate(v)]
    return [(ruta, v)]


def _errors_cd(cd: Any, ruta: str) -> List[str]:
    """Cd: `fraction`, `arc` i `centre` són un valor, una llista o un rang {de, a, pas} (`generadors._opcions_cd`
    els multiplica). Fracció 0 o (0, 1]; arc (0, 360] si hi ha Cd (candidat.py:219-224). Amb fracció 0 no hi ha
    Cd i l'arc i el centre no es miren (neudet no els multiplica)."""
    if not isinstance(cd, dict):
        return [f"{ruta}: cal {{fraction, arc, centre}}"]
    e: List[str] = []
    for k, nom in (("fraction", "la fracció de Cd"), ("arc", "l'arc de Cd"), ("centre", "el centre de Cd")):
        if k in cd:
            e += _errors_rang(cd[k], f"{ruta}.{k}", nom)
    if e:
        return e
    fr = _punts_cd(cd.get("fraction", 0), f"{ruta}.fraction")
    for camp, x in fr:
        if not 0 <= x <= 1:
            return [f"{camp}: un número entre 0 i 1 (0 = sense Cd; candidat.py:{CD_FRACCIO_LINIA})"]
    if all(x == 0 for _, x in fr):
        return []
    for camp, x in _punts_cd(cd.get("arc", 360), f"{ruta}.arc"):
        if not 0 < x <= 360:
            return [f"{camp}: un número en (0, 360] (candidat.py:{CD_ARC_LINIA})"]
    return []


def _llista_attr(v: Any) -> Any:
    """Els valors d'un atribut (`tipus`, `eix`): un valor, una llista o {valors, lligam} → la llista, o None si no és llegible."""
    if isinstance(v, dict):
        v = v.get("valors")
    if isinstance(v, list):
        return v if v else None
    return [v] if isinstance(v, str) and v else None


def _errors_atributs(a: Any, ruta: str, eixos_ok: bool = True) -> List[str]:
    """`tipus`, `cd` i `eix` d'una tongada, d'un punt o d'un anell (valor, llista o {valors, lligam})."""
    e: List[str] = []
    if not isinstance(a, dict):
        return e
    for k in ("tipus", "eix"):
        if k not in a:
            continue
        v = a[k]
        if isinstance(v, dict):
            if "lligam" in v and v["lligam"] not in tuple(LLIGAMS_TEXT):
                e.append(f"{ruta}.{k}.lligam: {v['lligam']!r} no és {', '.join(tuple(LLIGAMS_TEXT))}")
        ll = _llista_attr(v)
        if ll is None or not all(isinstance(x, str) and x for x in ll):
            e.append(f"{ruta}.{k}: un valor, una llista no buida, o {{valors, lligam}}")
        elif k == "eix":
            for x in ll:
                if x not in EIXOS:
                    e.append(f"{ruta}.eix: {x!r} no és x, y ni z")
    if "cd" in a:
        cd = a["cd"]
        if isinstance(cd, dict) and "lligam" in cd and cd["lligam"] not in tuple(LLIGAMS_TEXT):
            e.append(f"{ruta}.cd.lligam: {cd['lligam']!r} no és {', '.join(tuple(LLIGAMS_TEXT))}")
        e += _errors_cd(cd, f"{ruta}.cd")
    return e


def _errors_font(pos: Any, ruta: str, inventari: bool = False, total: Optional[int] = None) -> List[str]:
    if not isinstance(pos, dict):
        return [f"{ruta}: cal un diccionari amb `font`"]
    f = pos.get("font")
    if f not in tuple(FONTS_TEXT):
        return [f"{ruta}.font: {f!r} no és una font (n'hi ha: {', '.join(tuple(FONTS_TEXT))})"]
    e: List[str] = []
    if f == "punts":
        ps = pos.get("punts")
        if not isinstance(ps, list) or not ps:
            return [f"{ruta}.punts: una llista no buida de punts {{x, y, z}}"]
        for i, q in enumerate(ps):
            rp = f"{ruta}.punts.{i}"
            if not isinstance(q, dict):
                e.append(f"{rp}: cal un diccionari amb x i y")
                continue
            for k in ("x", "y", "z"):
                if k in q:                                    # PUNTS-V: un valor, una llista o un rang {de, a, pas}
                    e += _errors_rang(q[k], f"{rp}.{k}", f"{k} del punt {i + 1}")
                elif k != "z":
                    e.append(f"{rp}.{k}: falta «{k}» (punt {i + 1})")
            e += _errors_atributs(q, rp)
    elif f == "malla":
        forma = pos.get("forma")
        if forma not in MALLA_FORMES:
            e.append(f"{ruta}.forma: {forma!r} no és {', '.join(MALLA_FORMES)}")
        if not _enter(pos.get("k", 1)):
            e.append(f"{ruta}.k: un enter ≥ 1 (tubs per candidat)")
        if "z" in pos and not _num(pos["z"]):
            e.append(f"{ruta}.z: un número (cm)")
        if forma == "polar":
            for k in ("r", "theta"):
                if k not in pos:
                    e.append(f"{ruta}.{k}: falta «{k}» (malla polar)")
                elif not _valor_o_rang(pos[k]):
                    e.append(f"{ruta}.{k}: una llista de números, o un rang {{de, a, pas}}")
        elif forma in MALLA_FORMES:
            if "pas_cm" in pos:
                if not _pos(pos["pas_cm"]):
                    e.append(f"{ruta}.pas_cm: un número positiu (cm); generadors.py hi divideix")
            elif forma == "hexagonal":
                e.append(f"{ruta}.pas_cm: falta «pas_cm» (malla hexagonal)")
            else:
                for k in ("x", "y"):
                    if k not in pos:
                        e.append(f"{ruta}.{k}: falta «{k}» (o «pas_cm») a la malla quadrada")
                    elif not _valor_o_rang(pos[k]):
                        e.append(f"{ruta}.{k}: una llista de números (cm), o un rang {{de, a, pas}}")
    elif f == "anells":
        an = pos.get("anells")
        if not isinstance(an, list) or not an:
            return [f"{ruta}.anells: una llista no buida d'anells {{r, n, phi}}"]
        nt = pos.get("n_total")
        nt = nt if isinstance(nt, int) and not isinstance(nt, bool) else None
        if inventari and total:                        # INV: el total dels recursos fa de n_total
            nt = total
        for i, a in enumerate(an):
            ra = f"{ruta}.anells.{i}"
            if not isinstance(a, dict):
                e.append(f"{ra}: cal un diccionari amb r i n")
                continue
            for k in ("r", "n"):
                if k == "n" and inventari:                 # INV: amb inventari, sense `n` = lliure
                    continue
                if k not in a:
                    e.append(f"{ra}.{k}: falta «{k}» (anell {i + 1})")
            if "r" in a:
                e += _errors_rang(a["r"], f"{ra}.r", f"r de l'anell {i + 1}")
                if isinstance(a["r"], dict) and not e and a["r"]["de"] < 0:
                    e.append(f"{ra}.r.de: r de l'anell {i + 1} ha de ser ≥ 0")
            if "n" in a:
                e += _errors_rang(a["n"], f"{ra}.n", f"tubs de l'anell {i + 1}", enter=True, maxim=nt)
            if "phi" in a and a["phi"] != "mig_pas" and not _valor_o_rang(a["phi"]):
                e.append(f"{ra}.phi: graus (un valor, llista o rang) o «mig_pas»")
            e += _errors_atributs(a, ra)
    elif f == "dat":
        if not isinstance(pos.get("dat"), str) or not pos["dat"].strip():
            e.append(f"{ruta}.dat: el camí d'un fitxer .dat")
    return e


def _errors_inventari(t: Dict[str, Any], rt: str) -> List[str]:
    """INV-T / INV (contracte UI §10b–c): `inventari` (recursos `[{nom, tipus, quantitat, cd}]` o `{tipus: quantitat}`) en lloc de
    `tipus`; el total és el nombre de tubs. Les xifres (combinacions, simetria) i els impossibles de fixats les diu neudet, en
    paraules; aquí només la forma i el que neudet també refusa."""
    e: List[str] = []
    pos = t.get("posicions") if isinstance(t.get("posicions"), dict) else {}
    font = pos.get("font")
    inv = t.get("inventari")
    nomf = "punts" if font == "punts" else "anells"
    items = pos.get("punts") if font == "punts" else pos.get("anells") if font == "anells" else []
    items = [q for q in (items or []) if isinstance(q, dict)]
    if inv is None:
        for i, q in enumerate(items):
            for k in ("tipus_permesos", "fixats"):
                if k in q:
                    e.append(f"{rt}.posicions.{nomf}.{i}.{k}: només amb `inventari` a la tongada")
        return e
    if isinstance(inv, dict):
        if not (inv and all(isinstance(k, str) and k and _enter(v) for k, v in inv.items())):
            return [f"{rt}.inventari: {{tipus: quantitat (enter ≥ 1)}}, amb almenys un tipus"]
        disp = dict(inv)
    elif isinstance(inv, list):
        if not inv:
            return [f"{rt}.inventari: cal almenys un recurs (tipus i quantitat): els tubs que tens"]
        disp = {}
        for j, r in enumerate(inv):
            rr = f"{rt}.inventari.{j}"
            if not isinstance(r, dict):
                e.append(f"{rr}: cal {{tipus, quantitat, cd}}")
                continue
            nom = str(r.get("nom") or _lletra(j))
            if nom in disp:
                e.append(f"{rr}.nom: «{nom}» ja és el d'un altre recurs")
            if not isinstance(r.get("tipus"), str) or not r.get("tipus"):
                e.append(f"{rr}.tipus: quin tub és")
            if not _enter(r.get("quantitat")):
                e.append(f"{rr}.quantitat: un enter ≥ 1")
            if r.get("cd") is not None:
                e += _errors_cd(r["cd"], f"{rr}.cd")
                ll = r["cd"].get("lligam") if isinstance(r["cd"], dict) else None
                if ll not in (None, "global", "tub"):
                    e.append(f"{rr}.cd.lligam: global (tots els tubs del recurs igual) o tub (cada tub el seu)")
            disp[nom] = r.get("quantitat") if _enter(r.get("quantitat")) else 0
        if e:
            return e
    else:
        return [f"{rt}.inventari: una llista de recursos [{{tipus, quantitat, cd}}]"]
    total = sum(disp.values())
    if font == "dat":
        e.append(f"{rt}: una tongada «dat» no admet inventari")
    if "tipus" in t:
        e.append(f"{rt}.tipus: amb inventari el tipus el dona l'inventari (treu `tipus`)")
    for i, q in enumerate(items):
        rq = f"{rt}.posicions.{nomf}.{i}"
        if "tipus" in q:
            e.append(f"{rq}.tipus: amb inventari el tipus el dona l'inventari (treu `tipus`)")
        tp = q.get("tipus_permesos")
        if tp is not None:
            if not (isinstance(tp, list) and tp and all(isinstance(x, str) for x in tp)):
                e.append(f"{rq}.tipus_permesos: una llista de recursos de l'inventari")
            else:
                fora = [x for x in tp if x not in disp]
                if fora:
                    e.append(f"{rq}.tipus_permesos: {', '.join(fora)} no és a l'inventari ({', '.join(disp)})")
        fx = q.get("fixats")
        if fx is not None:
            if font != "anells":
                e.append(f"{rq}.fixats: només als anells (en un punt, `tipus_permesos`)")
            elif not (isinstance(fx, dict) and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in fx.values())):
                e.append(f"{rq}.fixats: {{recurs: quantitat}}")
            else:
                fora = [x for x in fx if x not in disp]
                if fora:
                    e.append(f"{rq}.fixats: {', '.join(fora)} no és a l'inventari ({', '.join(disp)})")
    if font == "punts" and len(items) != total:
        e.append(f"{rt}.posicions.punts: {len(items)} punts i l'inventari té {total} tubs (n'hi ha d'haver tants com tubs)")
    if font == "malla" and pos.get("k", 1) != total:
        e.append(f"{rt}.posicions.k: ha de ser el total de l'inventari ({total}); la UI el posa sola")
    nt = pos.get("n_total")
    if font == "anells" and nt is not None and nt != total:
        e.append(f"{rt}.posicions.n_total: {nt} no és el total de l'inventari ({total}); l'inventari fa de n_total")
    return e


def _errors_tongades(ts: Any, ruta: str) -> List[str]:
    if not isinstance(ts, list) or not ts:
        return [f"{ruta}: una llista no buida de tongades"]
    e: List[str] = []
    noms: List[str] = []
    for i, t in enumerate(ts):
        rt = f"{ruta}.{i}"
        if not isinstance(t, dict):
            e.append(f"{rt}: cal un diccionari amb nom i posicions")
            continue
        nom = t.get("nom")
        if not isinstance(nom, str) or not nom.strip():
            e.append(f"{rt}.nom: cal un nom (únic dins de l'etapa)")
        elif nom in noms:
            e.append(f"{rt}.nom: «{nom}» ja és el d'una altra tongada de l'etapa")
        else:
            noms.append(nom)
        pos = t.get("posicions")
        inv_t = t.get("inventari")
        tot_inv = (sum(r.get("quantitat") or 0 for r in inv_t if isinstance(r, dict) and _enter(r.get("quantitat")))
                   if isinstance(inv_t, list) else sum(v for v in inv_t.values() if _enter(v)) if isinstance(inv_t, dict) else None)
        e += _errors_font(pos, f"{rt}.posicions", inventari=inv_t is not None, total=tot_inv or None)
        if isinstance(pos, dict) and pos.get("font") == "dat" and any(k in t for k in ("tipus", "cd", "eix")):
            e.append(f"{rt}: una tongada «dat» és un candidat fix: no porta tipus, cd ni eix")
        e += _errors_atributs(t, rt)
        e += _errors_inventari(t, rt)
        sel = t.get("seleccio", "exhaustiu")
        if sel != "exhaustiu":
            if not isinstance(sel, dict) or not _enter(sel.get("mostres", 0)):
                e.append(f"{rt}.seleccio: «exhaustiu» o {{mostres: N (enter ≥ 1), llavor: s}}")
            elif "llavor" in sel and not isinstance(sel["llavor"], int):
                e.append(f"{rt}.seleccio.llavor: un enter")
        mc = t.get("max_candidats")
        if mc is not None and not _enter(mc, 0):
            e.append(f"{rt}.max_candidats: un enter ≥ 0 (0 = sense límit)")
    return e


def _metriques_valides() -> List[str]:
    return list(METRIQUES_LINIA)


def _errors_objectius(f: Dict[str, Any]) -> List[str]:
    """Llistes tancades d'objectius (objectius.py): mètriques, energies, pesos, Pareto, k·σ."""
    ob = f.get("objectius")
    if ob is None:
        return []
    if not isinstance(ob, dict):
        return ["objectius: cal un diccionari"]
    e: List[str] = []
    noms = set(_metriques_valides())
    dom = f.get("domini") if isinstance(f.get("domini"), dict) else {}
    graella = dom.get("energies_MeV") if isinstance(dom.get("energies_MeV"), list) else []
    if "finalitat" in ob or any(k in ob for k in CLAUS_NOVES):
        return _errors_objectius_nou(ob, graella)
    m = ob.get("metriques")
    if m is not None:
        if not isinstance(m, list) or not m:
            e.append("objectius.metriques: una llista (no buida) de mètriques de neudet")
        else:
            for x in m:
                if x not in noms:
                    e.append(f"objectius.metriques: «{x}» no és una mètrica de neudet "
                             f"(n'hi ha: {', '.join(sorted(noms))}; les llegeix {OBJECTIUS_PY})")
    en = ob.get("energies_MeV", "totes")
    if en != "totes":
        if not isinstance(en, list) or not en:
            e.append(f"objectius.energies_MeV: «totes» o una llista de energies de domini.energies_MeV "
                     f"(objectius.py:{ENERGIES_LINIA})")
        else:
            for x in en:
                if not (_num(x) and any(abs(x - g) < 1e-9 for g in graella)):
                    e.append(f"objectius.energies_MeV: {x!r} no és a domini.energies_MeV "
                             f"(objectius.py:{GRAELLA_LINIA}: ha d'estar dins de la graella)")
    pw = ob.get("pesos", "uniforme")
    if not (isinstance(pw, str) and pw in PESOS_LINIA):
        e.append(f"objectius.pesos: cal {' o '.join(PESOS_LINIA)} (objectius.py:{PESOS_DEFECTE_LINIA}-"
                 f"{PESOS_LINIA['letargia']})")
    k = ob.get("pareto_k_sigma")
    if k is not None and not (_num(k) and k >= 0):
        e.append(f"objectius.pareto_k_sigma: un número ≥ 0 (objectius.py:{K_SIGMA_LINIA})")
    pa = ob.get("pareto")
    if pa is not None:
        if not (isinstance(pa, list) and len(pa) == 2):
            e.append("objectius.pareto: dos parells [mètrica, max|min] (campanya.py:295 n'usa el primer i l'últim)")
        else:
            base = set(m) if isinstance(m, list) else set(DEFECTE_NOMS)
            for i, p in enumerate(pa):
                if not (isinstance(p, list) and len(p) == 2):
                    e.append(f"objectius.pareto[{i}]: cal [mètrica, max|min]")
                    continue
                nom, sentit = p
                if nom not in noms:
                    e.append(f"objectius.pareto[{i}]: «{nom}» no és una mètrica de neudet")
                elif nom not in base and nom not in AUTO_NOMS:
                    e.append(f"objectius.pareto[{i}]: «{nom}» no és a objectius.metriques: neudet no la "
                             f"calcularia (objectius.py:{AUTO_LINIA})")
                if sentit not in SENTITS:
                    e.append(f"objectius.pareto[{i}]: el sentit ha de ser max o min (objectius.py:{SENTITS_LINIA})")
    return e


def _nom_obj(x: Any) -> Any:
    return ALIES_OBJ.get(x, x) if isinstance(x, str) else x


def _errors_objectius_nou(ob: Dict[str, Any], graella: List[Any]) -> List[str]:
    """OBJ (contracte §14): la FORMA del bloc del cicle nou (finalitat → objectius → informatives → preferència →
    restriccions → pesos), amb les llistes de la taula de neudet (FINALITAT_METRIQUES). Què vol dir i si es pot calcular
    (un sol canal, grups sense energia…) ho diu neudet (`comprova.json.objectius.avisos`)."""
    e: List[str] = []
    fin = ob.get("finalitat")
    if fin not in FINALITAT_METRIQUES:
        return [f"objectius.finalitat: cal {' o '.join(FINALITAT_METRIQUES)} (objectius.py:{FINALITATS_LINIA})"]
    perm = FINALITAT_METRIQUES[fin]
    vells = [k for k in CLAUS_VELLES if k in ob]
    if vells:
        e.append(f"objectius: amb finalitat, {', '.join(vells)} ja no es fan servir (els que decideixen són "
                 f"`objectius`, les que s'informen `informatives` i la tria `preferencia`)")
    of = lambda x, on: (None if _nom_obj(x) in perm else
                        f"objectius.{on}: «{x}» no és de la finalitat {fin} (n'hi ha: {', '.join(perm)})")
    objs = ob.get("objectius")
    if objs is not None:
        if not (isinstance(objs, list) and 1 <= len(objs) <= 3):
            e.append("objectius.objectius: d'1 a 3 objectius, cadascun [mètrica, max|min]")
        else:
            vist = []
            for i, x in enumerate(objs):
                if isinstance(x, str):
                    nom, sentit = x, None
                elif isinstance(x, list) and len(x) == 2:
                    nom, sentit = x
                else:
                    e.append(f"objectius.objectius.{i}: cal [mètrica, max|min]")
                    continue
                if of(nom, f"objectius.{i}"):
                    e.append(of(nom, f"objectius.{i}"))
                if sentit is not None and sentit not in SENTITS:
                    e.append(f"objectius.objectius.{i}: el sentit ha de ser max o min")
                if _nom_obj(nom) in vist:
                    e.append(f"objectius.objectius.{i}: «{nom}» hi és dues vegades")
                vist.append(_nom_obj(nom))
    inf = ob.get("informatives", "auto")
    if inf != "auto":
        if not isinstance(inf, list):
            e.append("objectius.informatives: «auto» o una llista de mètriques de la finalitat")
        else:
            e += [x for x in (of(n, f"informatives.{i}") for i, n in enumerate(inf)) if x]
    pref = ob.get("preferencia")
    if pref is not None:
        if not isinstance(pref, dict) or set(pref) - {"maxim", "sobre", "c"}:
            e.append("objectius.preferencia: {maxim, sobre, c: [números]}")
        else:
            for k in ("maxim", "sobre"):
                if pref.get(k) is not None and of(pref[k], f"preferencia.{k}"):
                    e.append(of(pref[k], f"preferencia.{k}"))
            c = pref.get("c")
            if c is not None and not (isinstance(c, list) and all(_num(x) for x in c)):
                e.append("objectius.preferencia.c: una llista de números (p. ex. 0.1, 0.2)")
    rs = ob.get("restriccions")
    if rs is not None:
        if not isinstance(rs, list):
            e.append("objectius.restriccions: una llista de [mètrica, operador, valor]")
        else:
            for i, r in enumerate(rs):
                if not (isinstance(r, list) and len(r) == 3):
                    e.append(f"objectius.restriccions.{i}: cal [mètrica, {' | '.join(OPERADORS)}, valor]")
                    continue
                if of(r[0], f"restriccions.{i}.0"):
                    e.append(of(r[0], f"restriccions.{i}.0"))
                if r[1] not in OPERADORS:
                    e.append(f"objectius.restriccions.{i}.1: l'operador és {' | '.join(OPERADORS)}")
                if not _num(r[2]):
                    e.append(f"objectius.restriccions.{i}.2: el valor ha de ser un número")
    pw = ob.get("pesos", "letargia")
    if not (pw in PESOS_NOUS or (isinstance(pw, dict) and set(pw) == {"espectre"})):
        e.append("objectius.pesos: letargia, uniforme o {espectre: <fitxer>}")
    elif isinstance(pw, dict) and not (isinstance(pw["espectre"], str) and pw["espectre"].strip()):
        e.append("objectius.pesos.espectre: el camí del fitxer de l'espectre (relatiu a la campanya)")
    en = ob.get("energies_MeV", "totes")
    if en != "totes" and not (isinstance(en, list) and en and all(_num(x) and any(abs(x - g) < 1e-9 for g in graella) for x in en)):
        e.append(f"objectius.energies_MeV: «totes» o energies de domini.energies_MeV (objectius.py:{GRAELLA_LINIA})")
    k = ob.get("pareto_k_sigma")
    if k is not None and not (_num(k) and k >= 0):
        e.append(f"objectius.pareto_k_sigma: un número ≥ 0 (objectius.py:{K_SIGMA_LINIA})")
    g = ob.get("grups_MeV")
    if g is not None and not (isinstance(g, list) and all(isinstance(x, list) and len(x) == 2 and all(_num(y) for y in x)
                                                            and x[0] < x[1] for x in g)):
        e.append("objectius.grups_MeV: una llista de [E_min, E_max] (MeV), amb E_min < E_max")
    for kk in ("comptes_ref", "N_font", "sE_obj", "delta_q"):
        if ob.get(kk) is not None and not (_num(ob[kk]) and ob[kk] > 0):
            e.append(f"objectius.{kk}: un número > 0")
    return e


def _errors_avaluacio(f: Dict[str, Any]) -> List[str]:
    av = f.get("avaluacio")
    if av is None:
        return []
    if not isinstance(av, dict):
        return ["avaluacio: cal un diccionari"]
    e: List[str] = []
    if "xarxa" in av and av["xarxa"] not in XARXES_LINIA:
        e.append(f"avaluacio.xarxa: cal {' o '.join(XARXES_LINIA)} (avaluador.py:{XARXES_LINIA['A']})")
    if "mode" in av and av["mode"] not in MODES_LINIA:
        e.append(f"avaluacio.mode: cal {' o '.join(MODES_LINIA)} (avaluador.py:{MODES_LINIA['lots']})")
    for clau, c in AVALUACIO_CAMPS.items():
        if clau in av and not _enter(av[clau], c["minim"]):
            e.append(f"avaluacio.{clau}: un enter ≥ {c['minim']} (campanya.py:{c['linia']})")
    if "geom_vect" in av and not isinstance(av["geom_vect"], bool):
        e.append(f"avaluacio.geom_vect: sí o no (campanya.py:{GEOM_VECT_LINIA})")
    if "ckpts" in av:                                           # DIAG-UI (§18): un ckpt per material, de la llista de neudet
        ck = av["ckpts"]
        if not (isinstance(ck, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in ck.items())):
            e.append("avaluacio.ckpts: un diccionari {material: nom_de_ckpt} (campanya.py)")
        elif ck:
            if (f.get("domini") or {}).get("diagnostic") is not True:
                e.append("avaluacio.ckpts: només amb domini.diagnostic: true (contracte §18: els ckpts no BASELINE són de diagnòstic)")
            disp = ckpts_disponibles()
            for m, v in ck.items():
                if disp is not None and v not in (disp.get(m) or []):
                    e.append(f"avaluacio.ckpts.{m} = {v}: neudet no el troba (n'hi ha: {', '.join(disp.get(m) or []) or 'cap'})")
    return e


def _errors_cerca(f: Dict[str, Any]) -> List[str]:
    e: List[str] = []
    for nom, etapa in (f.get("etapes") or {}).items():
        if not isinstance(etapa, dict) or "cerca" not in etapa:
            continue
        ce = etapa["cerca"]
        ruta = f"etapes.{nom}.cerca"
        if not isinstance(ce, dict) or ce.get("tipus") not in CERQUES_LINIA:
            e.append(f"{ruta}.tipus: cal {' | '.join(CERQUES_LINIA)} (cerca.py:{CERQUES_LINIA['exhaustiva']}…)")
            continue
        for c in CERCA_CAMPS[ce["tipus"]]:
            clau = c["clau"]
            if clau not in ce:
                if c["obligatori"]:
                    e.append(f"{ruta}: falta «{clau}» (cerca {ce['tipus']}, cerca.py:{c['linia']})")
                continue
            v = ce[clau]
            if c["tipus"] == "enter":
                ok = _enter(v, c["minim"]) if c["minim"] is not None else (isinstance(v, int) and not isinstance(v, bool))
                cal = f"un enter ≥ {c['minim']}" if c["minim"] is not None else "un enter"
            else:
                ok = _num(v) and v > c["minim"] and v <= c["maxim"]
                cal = f"un número en ({c['minim']}, {c['maxim']}]"
            if not ok:
                e.append(f"{ruta}.{clau}: {cal} (cerca.py:{c['linia']})")
    return e


def _errors(f: Any) -> List[str]:
    if not isinstance(f, dict):
        return ["el formulari no és un diccionari"]
    e: List[str] = []
    if not isinstance(f.get("id"), str) or not _ID.match(f.get("id") or ""):
        e.append("id: cal un identificador amb lletres, xifres, «_» o «-» (p. ex. c05_prova)")
    if not isinstance(f.get("domini"), dict):
        e.append("falta el bloc domini")
    else:
        e += _errors_domini(f["domini"])
    et = f.get("etapes")
    if not isinstance(et, dict) or not et:
        e.append("etapes: cal almenys una etapa")
    else:
        for nom, etapa in et.items():
            if isinstance(etapa, dict) and "generador" in etapa and "tongades" in etapa:
                e.append(f"etapes.{nom}: porta `generador` i `tongades`; només una de les dues")
            if isinstance(etapa, dict) and "tongades" in etapa:
                e += _errors_tongades(etapa["tongades"], f"etapes.{nom}.tongades")
    if "draft" in f and not isinstance(f["draft"], bool):
        e.append("draft: sí o no (fitxa.py: decideix)")
    e += _errors_objectius(f)
    e += _errors_avaluacio(f)
    e += _errors_cerca(f)
    return e


class _Dumper(yaml.SafeDumper):
    """Les dates ISO que són text es escriuen sense cometes: neudet les llegirà com a data."""


def _repr_str(dumper, s: str):
    if _DATA_ISO.match(s):
        return dumper.represent_scalar("tag:yaml.org,2002:timestamp", s)
    return dumper.represent_scalar("tag:yaml.org,2002:str", s)


_Dumper.add_representer(str, _repr_str)

CAPSALERA = ("# Esborrany generat per simphy («Definició de campanya», C1). La validesa dels candidats\n"
             "# la dona neudet: Campanya(dir).candidats(etapa). Vegeu docs/site/contractes/simphy_ui.md §4.\n")


def _sense_pas_buit(x: Any) -> Any:
    """Un rang amb `pas` buit (el camp de la pàgina en blanc) és el pas per defecte de neudet (1,
    `generadors.valors`): la clau no s'escriu. Amb `pas: null` neudet peta (TypeError)."""
    if isinstance(x, dict):
        if {"de", "a"} <= set(x) and "pas" in x and x["pas"] is None:
            x = {k: v for k, v in x.items() if k != "pas"}
        return {k: _sense_pas_buit(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_sense_pas_buit(v) for v in x]
    return x


def _tipus_explicits(form: Dict[str, Any]) -> bool:
    """Cada tongada de cada etapa diu els seus tipus (a la tongada, a tots els seus punts/anells, o amb `inventari`; `dat` no en
    porta). Només llavors `domini.tipus_tub` sobra: neudet el deriva dels tipus de les tongades (SIMPLIFICA). Si alguna tongada
    deixa el tipus al domini (un yaml antic traduït), la clau es manté: treure-la canviaria el tipus per defecte i els hashes."""
    for e in (form.get("etapes") or {}).values():
        for t in (e.get("tongades") or []) if isinstance(e, dict) else []:
            pos = t.get("posicions") or {}
            if pos.get("font") == "dat" or "tipus" in t or "inventari" in t:
                continue
            its = pos.get("punts") if pos.get("font") == "punts" else pos.get("anells") if pos.get("font") == "anells" else None
            if not its or not all(isinstance(q, dict) and "tipus" in q for q in its):
                return False
    return True


def to_yaml(form: Dict[str, Any]) -> str:
    """El `campanya.yaml` d'esborrany (text). Llança `FormError` amb tots els motius si la forma no
    és llegible per neudet, o si un valor és fora d'una llista tancada. No modifica `form`."""
    form = _sense_pas_buit(copy.deepcopy(form))
    if isinstance(form, dict):
        form.pop(CONVERSIO, None)                  # INV: la nota de conversió és del formulari, no del yaml
    errs = _errors(form)
    if errs:
        raise FormError("formulari no vàlid:\n- " + "\n- ".join(errs))
    if isinstance(form.get("domini"), dict) and _tipus_explicits(form):
        form["domini"].pop("tipus_tub", None)      # derivat per neudet dels tipus (o inventaris) de les tongades (SIMPLIFICA)
    return CAPSALERA + yaml.dump(form, Dumper=_Dumper, sort_keys=False,
                                 allow_unicode=True, default_flow_style=None, width=110)
