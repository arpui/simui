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
from typing import Any, Dict, List, Optional

import yaml

from . import design as DES
from . import detector_config as DC

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
CD_AVIS = ("Cd només validat sobre counterUPC_v0 fins a TUB-4 (contracte simphy_ui.md §4). "
           "Avui Geant4 s'ATURA si un tub que no és counterUPC_v0 porta Cd (DetectorConstruction.cc, «el Cd "
           "només és a counterUPC_v0»): amb lnd_252285 la xarxa el pot avaluar, però la verificació a Geant4 no.")
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
    "eps_mitja": 29, "cv": 30, "rang": 31, "eps_min": 33, "cd_cm2": 34,            # METRIQUES
    "q_rang": 42, "q_monoton": 43, "res_E": 44,                                    # METRIQUES_GRUP (MET2)
    "N_obj": 71, "sE_N": 72, "n_ef": 73,                                           # METRIQUES_GRUP2 (IND)
    "res_E_k": 112, "err_grups": 113,                                              # METRIQUES_GRUP3 (MET3)
}
#: les mètriques que neudet afegeix soles al Pareto o a la restricció (objectius.py:228-230)
AUTO_LINIA = 228
#: sentit (objectius.py:350: `1 if s == "max" else -1`): «max»; qualsevol altra cosa és min
SENTITS = ("max", "min")
SENTITS_LINIA = 350
#: les mètriques que neudet afegeix soles (objectius.py: GEOMETRIQUES, GRUP, GRUP2, GRUP3)
AUTO_NOMS = {"cd_cm2", "q_rang", "q_monoton", "res_E", "N_obj", "sE_N", "n_ef", "res_E_k", "err_grups"}
#: les mètriques per defecte de l'objectiu (objectius.py:216): totes les que no són geomètriques
DEFECTE_NOMS = ("eps_mitja", "cv", "rang", "eps_min")
#: pesos (objectius.py): `cfg.get("pesos", "uniforme")` i el `elif` de letargia
PESOS_LINIA: Dict[str, int] = {"uniforme": 208, "letargia": 210}
PESOS_DEFECTE_LINIA = 206
#: energies: «totes» (objectius.py:200); subconjunt dins de la graella (objectius.py:205)
ENERGIES_LINIA = 200
GRAELLA_LINIA = 205
K_SIGMA_LINIA = 231
ERR_GRUPS_CAL_LINIA = 155        # «err_grups: cal objectius.grups_MeV» (és l'única mètrica que en vol)
#: ε-restricció per defecte (objectius.py:226)
RESTRICCIO_LINIA = 226
#: valors de la mètrica per defecte de l'objectiu, i què fa neudet si el camp manca
DEFECTE_NOMS_LINIA = 216
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

#: Camps de cada generador, tal com els llegeix neudet. `linia` és la línia (1-based) de
#: `neudet/disseny/generadors.py` on hi ha la clau entre cometes; `ambit` diu on va dins del
#: generador. El test `test_camps_citats_a_la_linia_de_generadors_py` comprova cada línia.
_G = "generadors.py"
CAMPS: Dict[str, Dict[str, Any]] = {
    "anells": {
        "linies": f"{_G}:106-130",
        "camps": [
            {"clau": "anells", "ambit": "generador", "obligatori": True, "linia": 110,
             "nota": "llista d'anells; cada anell és {r, n, phi?, tipus?, cd?}"},
            {"clau": "n_total", "ambit": "generador", "obligatori": False, "linia": 114,
             "nota": "filtre: suma de tubs de tots els anells"},
            {"clau": "ordenats", "ambit": "generador", "obligatori": False, "linia": 121,
             "nota": "radis creixents entre anells no buits"},
            {"clau": "r", "ambit": "anell", "obligatori": True, "linia": 111,
             "nota": "radi (cm): número, llista o rang {de, a, pas}"},
            {"clau": "n", "ambit": "anell", "obligatori": True, "linia": 111,
             "nota": "tubs per anell: número, llista o rang {de, a, pas}; 0 = anell buit"},
            {"clau": "phi", "ambit": "anell", "obligatori": False, "linia": 112,
             "nota": "angle inicial (graus), o «mig_pas» (180/n)"},
            {"clau": "tipus", "ambit": "anell", "obligatori": False, "linia": 112,
             "nota": "tipus de tub; per defecte el primer de domini.tipus_tub"},
            {"clau": "cd", "ambit": "anell", "obligatori": False, "linia": 113,
             "nota": "Cd: {fraction, arc, centre}; fraction 0 = sense Cd"},
            {"clau": "fraction", "ambit": "cd", "obligatori": False, "linia": 81,
             "nota": "fracció axial coberta (0 a 1)"},
            {"clau": "arc", "ambit": "cd", "obligatori": False, "linia": 85,
             "nota": "arc en graus (per defecte 360)"},
            {"clau": "centre", "ambit": "cd", "obligatori": False, "linia": 86,
             "nota": "centre de l'arc en graus (0 = cap a l'eix del bloc)"},
        ],
    },
    "mapa_un_tub": {
        "linies": f"{_G}:133-145",
        "camps": [
            {"clau": "tipus_tub", "ambit": "generador", "obligatori": False, "linia": 135,
             "nota": "tipus del tub del mapa"},
            {"clau": "cd", "ambit": "generador", "obligatori": False, "linia": 135,
             "nota": "Cd {fraction, arc, centre} (llistes = totes les opcions)"},
            {"clau": "polar", "ambit": "generador", "obligatori": False, "linia": 136,
             "nota": "graella polar {r, theta}; alternativa a x i y"},
            {"clau": "r", "ambit": "polar", "obligatori": True, "linia": 138,
             "nota": "radis (cm)"},
            {"clau": "theta", "ambit": "polar", "obligatori": True, "linia": 138,
             "nota": "angles (graus)"},
            {"clau": "x", "ambit": "generador", "obligatori": False, "linia": 143,
             "nota": "graella cartesiana: x (cm); obligatori si no hi ha polar"},
            {"clau": "y", "ambit": "generador", "obligatori": False, "linia": 143,
             "nota": "graella cartesiana: y (cm); obligatori si no hi ha polar"},
        ],
    },
    "llista": {
        "linies": f"{_G}:148-167",
        "camps": [
            {"clau": "candidats", "ambit": "generador", "obligatori": True, "linia": 151,
             "nota": "candidats explícits"},
            {"clau": "nom", "ambit": "candidat", "obligatori": False, "linia": 167,
             "nota": "nom del candidat"},
            {"clau": "dat", "ambit": "candidat", "obligatori": False, "linia": 152,
             "nota": "camí a un .dat (alternativa a tubs)"},
            {"clau": "tubs", "ambit": "candidat", "obligatori": False, "linia": 160,
             "nota": "tubs: [x, y] o {x, y, tipus, z, cd_fraction, cd_arc_deg, cd_arc_centre_deg}"},
            {"clau": "x", "ambit": "tub", "obligatori": False, "linia": 166, "nota": "cm"},
            {"clau": "y", "ambit": "tub", "obligatori": False, "linia": 166, "nota": "cm"},
            {"clau": "tipus", "ambit": "tub", "obligatori": False, "linia": 166,
             "nota": "tipus del tub; per defecte el primer de domini.tipus_tub"},
            {"clau": "z", "ambit": "tub", "obligatori": False, "linia": 166, "nota": "cm"},
            {"clau": "cd_fraction", "ambit": "tub", "obligatori": False, "linia": 164,
             "nota": "fracció de Cd del tub"},
            {"clau": "cd_arc_deg", "ambit": "tub", "obligatori": False, "linia": 164,
             "nota": "arc de Cd (graus)"},
            {"clau": "cd_arc_centre_deg", "ambit": "tub", "obligatori": False, "linia": 165,
             "nota": "centre de l'arc de Cd (graus)"},
        ],
    },
    "slots": {
        "linies": f"{_G}:170-203",
        "camps": [
            {"clau": "tipus_tub", "ambit": "generador", "obligatori": False, "linia": 174,
             "nota": "tipus dels tubs de la malla"},
            {"clau": "pas_cm", "ambit": "generador", "obligatori": True, "linia": 175,
             "nota": "pas de la malla (cm)"},
            {"clau": "forma", "ambit": "generador", "obligatori": False, "linia": 175,
             "nota": "«quadrada» (per defecte) o «hexagonal»"},
            {"clau": "r_min_cm", "ambit": "generador", "obligatori": False, "linia": 178,
             "nota": "radi mínim de les posicions (cm)"},
            {"clau": "r_max_cm", "ambit": "generador", "obligatori": False, "linia": 178,
             "nota": "radi màxim de les posicions (cm)"},
            {"clau": "ocupats", "ambit": "generador", "obligatori": False, "linia": 191,
             "nota": "tubs a ocupar; per defecte n_tubs"},
            {"clau": "llavor", "ambit": "generador", "obligatori": False, "linia": 194,
             "nota": "llavor del sorteig (per defecte 0)"},
            {"clau": "intents", "ambit": "generador", "obligatori": False, "linia": 195,
             "nota": "intents de sorteig"},
            {"clau": "mostres", "ambit": "generador", "obligatori": False, "linia": 195,
             "nota": "candidats diferents a generar (per defecte 100)"},
        ],
    },
}


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
    return _jsonable(data)


def defaults() -> Dict[str, Any]:
    """El `campanya.yaml` de c04_draft tal com és a neudet (dict, dates com a text ISO)."""
    return de_fitxer(DES.neudet_root() / C04_YAML)


def _fitxa():
    """`neudet.disseny.fitxa` (registre i regla de validació de neudet), o None si no hi és."""
    try:
        DES._neudet()
        from neudet.disseny import fitxa
        return fitxa
    except Exception:                                            # noqa: BLE001
        return None


def energies_domini() -> Optional[Dict[str, Any]]:
    """La graella d'energies de neudet (validacions.json, secció `domini`, CAMP-2): {min, max, per_defecte}.
    None si el registre no la porta (llavors el formulari no la tanca)."""
    reg = _validacions()
    d = ((reg or {}).get("domini") or {}).get("energies_MeV")
    if not (isinstance(d, dict) and isinstance(d.get("per_defecte"), list) and d["per_defecte"]):
        return None
    return {"min": d.get("min"), "max": d.get("max"), "per_defecte": [float(x) for x in d["per_defecte"]],
            "font": "validacions.json · domini.energies_MeV"}


def _validacions() -> Optional[Dict[str, Any]]:
    """`validacions.json` del config de neudet, si existeix (CAMP-1). Si no, None: no hi ha registre."""
    f = DC.config_dir() / "validacions.json"
    if not f.exists():
        return None
    data = json.loads(f.read_text())
    return data if isinstance(data, dict) else {}


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
    _linia(FITXA_PY, 26, '"objectius.pesos"')
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
                          "fitxa": {"fitxer": FITXA_PY, "linia": 26}},
        "pareto": {"n": 2, "defecte": [list(x) for x in d.pareto],
                   "motiu": "campanya.py: els gràfics usen ob.pareto[-1] i [0]",
                   "fitxer": CAMPANYA_PY, "linia": 295, "auto": {"fitxer": OBJECTIUS_PY, "linia": AUTO_LINIA}},
        "pareto_k_sigma": {"defecte": float(d.k_sigma), "minim": 0, "fitxer": OBJECTIUS_PY,
                           "linia": K_SIGMA_LINIA,
                           "descripcio": "frontera robusta: només domina qui guanya per més de k·σ. "
                                         "Amb k = 0 és la frontera de Pareto (objectius.py, frontera_robusta)"},
        "altres": [
            {"clau": "comptes_ref", "defecte": d.comptes_ref, "fitxer": OBJECTIUS_PY, "linia": 220,
             "descripcio": "comptes de referència de res_E, N_obj i sE_N (sense comentari a neudet)"},
            {"clau": "N_font", "defecte": d.N_font, "fitxer": OBJECTIUS_PY, "linia": 221,
             "descripcio": _comentari(OBJECTIUS_PY, 221, token='"N_font"')},
            {"clau": "sE_obj", "defecte": d.sE_obj, "fitxer": OBJECTIUS_PY, "linia": 222,
             "descripcio": _comentari(OBJECTIUS_PY, 222, token='"sE_obj"')},
            {"clau": "delta_q", "defecte": d.delta_q, "fitxer": OBJECTIUS_PY, "linia": 223,
             "descripcio": _comentari(OBJECTIUS_PY, 223, token='"delta_q"')},
            {"clau": "grups_MeV", "defecte": [], "fitxer": OBJECTIUS_PY, "linia": 224,
             "descripcio": _comentari(OBJECTIUS_PY, 224, token='"grups_MeV"') + " (cal per a err_grups)"},
            {"clau": "restriccio", "defecte": {"maxim": d.restriccio["maxim"], "sobre": d.restriccio["sobre"],
                                              "c": []}, "fitxer": OBJECTIUS_PY, "linia": RESTRICCIO_LINIA,
             "descripcio": "ε-restricció: maximitzar «maxim» amb «sobre» ≤ c; sense c, no n'hi ha"},
        ],
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
    _linia(FITXA_PY, 72, 'get("porta")')
    return {"quants": {"llegit": False, "fitxer": VERIFICA_G4_PY, "linia": 398,
                       "descripcio": "neudet no llegeix aquest camp. La selecció de verifica_g4.py són les "
                                     "triades d'ε-restricció i la frontera robusta, més K candidats aleatoris "
                                     "(--aleatoris, per defecte 30; línies 11-12 i 398)"},
            "n_per_energia": {"llegit": False, "fitxer": VERIFICA_G4_PY, "linia": 400,
                              "descripcio": "neudet no el llegeix: la simulació de Geant4 usa --n (per defecte "
                                            "100000). La fitxa només exigeix que hi sigui (fitxa.py:70)"},
            "porta": {"llegit": False, "fitxer": FITXA_PY, "linia": 72,
                      "descripcio": "text lliure: neudet només comprova que no sigui buit (fitxa.py:72). "
                                    "La porta G1/G2 que neudet documenta és la de disseny/README.md §6"}}


def _schema_plantilles() -> Dict[str, Any]:
    """Les plantilles que el formulari posa en triar un generador. Cada una porta `cd` explícit: la fitxa
    de neudet ho exigeix (fitxa.py:91 i 98). `__TUB__` és el tipus de tub del domini."""
    return {
        "anells": {"tipus": "anells", "anells": [{"r": {"de": 5, "a": 5, "pas": 1}, "n": {"de": 4, "a": 4},
                                                  "tipus": TUB, "cd": {"fraction": 0}}]},
        "mapa_un_tub": {"tipus": "mapa_un_tub", "tipus_tub": TUB, "cd": {"fraction": 0}, "x": [0], "y": [0]},
        "llista": {"tipus": "llista", "candidats": [{"nom": "c0", "tubs": []}]},
        "slots": {"tipus": "slots", "tipus_tub": TUB, "cd": {"fraction": 0}, "pas_cm": 5},
    }


def schema() -> Dict[str, Any]:
    """Tipus de generador i els seus camps, llistes tancades de neudet, tubs del catàleg i estat de la
    validació. Tot ve de neudet, amb la línia on es llegeix."""
    _, gen = DES._neudet()                             # importa neudet.disseny.generadors de NEUDET_ROOT
    obj, cer = _mods_neudet()
    ajudes_gen = _entrades_docstring(GENERADORS_PY)
    generadors = []
    for t in sorted(gen.GENERADORS):
        ajuda = ajudes_gen.get(t)
        if ajuda is None:
            raise DES.DesignError(f"neudet: {GENERADORS_PY} no té l'entrada «{t}» al docstring del mòdul")
        ajuda = {"text": ajuda["text"], "fitxer": GENERADORS_PY, "linia": ajuda["linia"]}
        if t in CAMPS:
            generadors.append({"tipus": t, **CAMPS[t], "ajuda": ajuda})
        else:
            generadors.append({"tipus": t, "linies": None, "camps": [], "ajuda": ajuda,
                               "gap": "neudet té aquest generador però simphy no té els seus camps: "
                                      "cal afegir-los a campanya_form.CAMPS"})
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
                     "motiu": motiu})
    _linia(CANDIDAT_PY, FONT_LINIA, "feix")
    _linia(CANDIDAT_PY, EIX_DEFECTE_LINIA, 'eix')
    _linia(CANDIDAT_PY, CD_FRACCIO_LINIA, "cd_fraction fora de")
    _linia(CANDIDAT_PY, CD_ARC_LINIA, "cd_arc_deg fora de")
    _linia(GENERADORS_PY, SLOTS_PAS_LINIA, "pas")
    return {
        "neudet": str(DES.neudet_root()),
        "generadors": generadors,
        "plantilles": _schema_plantilles(),
        "tipus_tub": tubs,
        "energies_domini": energies_domini(),
        "validacio": {"registre": reg is not None,
                      "motiu": "" if reg is not None else SENSE_REGISTRE},
        "cd": {"fraccio": {"minim": 0, "maxim": 1, "fitxer": CANDIDAT_PY, "linia": CD_FRACCIO_LINIA,
                           "descripcio": "fracció axial coberta: 0 = sense Cd; si no, (0, 1]"},
               "arc": {"minim": 0, "maxim": 360, "fitxer": CANDIDAT_PY, "linia": CD_ARC_LINIA,
                       "descripcio": "arc del Cd en graus, (0, 360] quan hi ha Cd"},
               "centre_deg": 0, "avis": CD_AVIS, "exemples_contracte": CD_FRACCIONS},
        "font": {"tipus": [{"valor": t, "fitxer": CANDIDAT_PY, "linia": FONT_LINIA} for t in FONT_TIPUS],
                 "eixos": [{"valor": e, "fitxer": CANDIDAT_PY, "linia": FONT_LINIA} for e in EIXOS],
                 "eix_defecte": {"valor": "z", "fitxer": CANDIDAT_PY, "linia": EIX_DEFECTE_LINIA}},
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
        g = energies_domini()
        if g is not None:
            fora = [x for x in dom["energies_MeV"] if not any(abs(x - y) <= 1e-9 * max(1.0, y) for y in g["per_defecte"])]
            if fora:
                e.append(f"domini.energies_MeV: {', '.join('%g' % x for x in fora)} MeV no són a la graella de "
                         f"neudet (validacions.json · domini.energies_MeV)")
    tt = dom.get("tipus_tub")
    if not (isinstance(tt, list) and tt and all(isinstance(t, str) and t for t in tt)):
        e.append("domini.tipus_tub: una llista de noms de tub (del catàleg)")
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


def _errors_cd(cd: Any, ruta: str) -> List[str]:
    """Cd: fracció 0 o (0, 1]; arc (0, 360] si hi ha Cd (candidat.py:219-224)."""
    if not isinstance(cd, dict):
        return [f"{ruta}: cal {{fraction, arc, centre}}"]
    f = cd.get("fraction", 0)
    if not (isinstance(f, (int, float)) and not isinstance(f, bool) and 0 <= f <= 1):
        return [f"{ruta}.fraction: un número entre 0 i 1 (0 = sense Cd; candidat.py:{CD_FRACCIO_LINIA})"]
    if f == 0:
        return []
    arc = cd.get("arc", 360)
    if not (_num(arc) and 0 < arc <= 360):
        return [f"{ruta}.arc: un número en (0, 360] (candidat.py:{CD_ARC_LINIA})"]
    return []


def _errors_generador(g: Any, ruta: str) -> List[str]:
    if not isinstance(g, dict):
        return [f"{ruta}: cal un diccionari amb `tipus`"]
    t = g.get("tipus")
    if t not in CAMPS:
        return [f"{ruta}.tipus: {t!r} no és un generador conegut (n'hi ha: {', '.join(sorted(CAMPS))})"]
    e: List[str] = []
    for c in CAMPS[t]["camps"]:
        if c["ambit"] == "generador" and c["obligatori"] and c["clau"] not in g:
            e.append(f"{ruta}: falta «{c['clau']}» (generador {t})")
    if t == "anells":
        anells = g.get("anells")
        if isinstance(anells, list):
            for i, a in enumerate(anells):
                if not isinstance(a, dict):
                    e.append(f"{ruta}.anells[{i}]: cal un diccionari amb r i n")
                    continue
                for k in ("r", "n"):
                    if k not in a:
                        e.append(f"{ruta}.anells.{i}.{k}: falta «{k}» (anell {i + 1})")
                nt = g.get("n_total")
                nt = nt if isinstance(nt, int) and not isinstance(nt, bool) else None
                if "r" in a:
                    e += _errors_rang(a["r"], f"{ruta}.anells.{i}.r", f"r de l'anell {i + 1}")
                    if not e and isinstance(a["r"], dict) and a["r"]["de"] < 0:
                        e.append(f"{ruta}.anells.{i}.r.de: r de l'anell {i + 1} ha de ser ≥ 0")
                if "n" in a:
                    e += _errors_rang(a["n"], f"{ruta}.anells.{i}.n", f"tubs de l'anell {i + 1}", enter=True, maxim=nt)
                if "cd" in a:
                    e += _errors_cd(a["cd"], f"{ruta}.anells.{i}.cd")
    elif t == "mapa_un_tub":
        if "polar" not in g and not ("x" in g and "y" in g):
            e.append(f"{ruta}: cal «polar» o bé «x» i «y»")
        for camp in ("x", "y"):
            if camp in g and not _valor_o_rang(g[camp]):
                e.append(f"{ruta}.{camp}: una llista de números (cm), o un rang {{de, a, pas}}")
        if "polar" in g:
            p = g["polar"] if isinstance(g["polar"], dict) else {}
            for camp in ("r", "theta"):
                if camp in p and not _valor_o_rang(p[camp]):
                    e.append(f"{ruta}.polar.{camp}: una llista de números, o un rang {{de, a, pas}}")
        if "cd" in g:
            e += _errors_cd(g["cd"], f"{ruta}.cd")
    elif t == "llista":
        for i, c in enumerate(g.get("candidats") or []):
            if not isinstance(c, dict) or ("dat" not in c and "tubs" not in c):
                e.append(f"{ruta}.candidats[{i}]: cal «dat» o «tubs»")
    elif t == "slots":
        if "pas_cm" in g and not _pos(g["pas_cm"]):
            e.append(f"{ruta}.pas_cm: un número positiu (cm); generadors.py:{SLOTS_PAS_LINIA} hi divideix")
        if "cd" in g:
            e += _errors_cd(g["cd"], f"{ruta}.cd")
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
            if isinstance(etapa, dict) and "generador" in etapa:
                e += _errors_generador(etapa["generador"], f"etapes.{nom}.generador")
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


def to_yaml(form: Dict[str, Any]) -> str:
    """El `campanya.yaml` d'esborrany (text). Llança `FormError` amb tots els motius si la forma no
    és llegible per neudet, o si un valor és fora d'una llista tancada. No modifica `form`."""
    form = _sense_pas_buit(copy.deepcopy(form))
    errs = _errors(form)
    if errs:
        raise FormError("formulari no vàlid:\n- " + "\n- ".join(errs))
    return CAPSALERA + yaml.dump(form, Dumper=_Dumper, sort_keys=False,
                                 allow_unicode=True, default_flow_style=None, width=110)
