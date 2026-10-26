"""campanya_form.py — el formulari de «Definició de campanya» (contracte simphy_ui.md §4, C1).

Què és i què no
---------------
- `defaults()` és el `campanya.yaml` de **c04_draft**, llegit de neudet (no es copia).
- `schema()` és el que el formulari necessita saber, i ve de neudet:
    · els tipus de generador: el registre `GENERADORS` de `neudet.disseny.generadors`;
    · els camps de cada tipus: la taula `CAMPS` d'aquí, on cada clau porta la línia de
      `generadors.py` on neudet la llegeix. El test bessó comprova que la clau hi és, a aquella
      línia, i que no n'hi falta cap tipus;
    · els tubs: `tubs.json` (el catàleg de neudet), amb la marca de validat només si hi ha
      `validacions.json`. Si no n'hi ha, es diu «sense registre de validació (CAMP-1 pendent)».
- `to_yaml(form)` escriu el `campanya.yaml` d'esborrany amb les claus de neudet, en el mateix
  ordre. **Només valida la FORMA** (que neudet el pugui llegir: tipus, llistes, nombres). Si un
  candidat és vàlid o no, ho diu neudet (`Campanya(dir).candidats(etapa)`), no aquí.

El YAML, quan és una data (`creada: 2026-10-26`), es llegeix com a data: el formulari la porta com
a text ISO i `to_yaml` l'escriu sense cometes perquè neudet la llegeixi com a data.
"""
from __future__ import annotations

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
#: contracte §4: fraccions axials i arcs del Cd per anell
CD_FRACCIONS = [0, 0.25, 0.5, 0.75, 1]
CD_ARCS_DEG = [360, 180]
CD_AVIS = ("Cd només validat sobre counterUPC_v0 fins a TUB-4 (contracte simphy_ui.md §4): "
           "amb lnd_252285 cal l'encàrrec TUB-4 abans.")
FONT_TIPUS = ["iso", "feix"]
EIXOS = ["x", "y", "z"]
SENSE_REGISTRE = "sense registre de validació (CAMP-1 pendent)"
_ID = re.compile(r"^[A-Za-z0-9_\-]+$")
_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Camps de cada generador, tal com els llegeix neudet. `linia` és la línia (1-based) de
#: `neudet/disseny/generadors.py` on hi ha la clau entre cometes; `ambit` diu on va dins del
#: generador. El test `test_campanya_form` comprova cada línia.
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


def defaults() -> Dict[str, Any]:
    """El `campanya.yaml` de c04_draft tal com és a neudet (dict, dates com a text ISO)."""
    f = DES.neudet_root() / C04_YAML
    if not f.exists():
        raise DES.DesignError(f"no trobo {f}: la campanya de referència de neudet (c04_draft) falta")
    data = yaml.safe_load(f.read_text())
    if not isinstance(data, dict):
        raise DES.DesignError(f"{f}: el campanya.yaml no és un diccionari")
    return _jsonable(data)


def _validacions() -> Optional[Dict[str, Any]]:
    """`validacions.json` del config de neudet, si existeix (CAMP-1). Si no, None: no hi ha registre."""
    f = DC.config_dir() / "validacions.json"
    if not f.exists():
        return None
    data = json.loads(f.read_text())
    return data if isinstance(data, dict) else {}


def schema() -> Dict[str, Any]:
    """Tipus de generador i els seus camps, tubs del catàleg i estat de la validació. Ve de neudet."""
    _, gen = DES._neudet()                             # importa neudet.disseny.generadors de NEUDET_ROOT
    registre = sorted(gen.GENERADORS)
    generadors = []
    for t in registre:
        if t in CAMPS:
            generadors.append({"tipus": t, **CAMPS[t]})
        else:
            generadors.append({"tipus": t, "linies": None, "camps": [],
                               "gap": "neudet té aquest generador però simphy no té els seus camps: "
                                      "cal afegir-los a campanya_form.CAMPS"})
    reg = _validacions()
    tubs = []
    for e in DC.read_catalog():
        nom = e.get("nom")
        if reg is None:
            validat, estat = None, SENSE_REGISTRE
        elif nom not in reg or not isinstance(reg[nom], dict) or not isinstance(reg[nom].get("validat"), bool):
            validat, estat = None, "no és al registre de validacions"
        else:
            validat = reg[nom]["validat"]
            estat = "validat per a la xarxa" if validat else "no validat"
        tubs.append({"nom": nom, "alies": e.get("alies"), "validat": validat, "estat": estat})
    return {
        "neudet": str(DES.neudet_root()),
        "generadors": generadors,
        "tipus_tub": tubs,
        "validacio": {"registre": reg is not None,
                      "motiu": "" if reg is not None else SENSE_REGISTRE},
        "cd": {"fraccions": CD_FRACCIONS, "arcs_deg": CD_ARCS_DEG, "centre_deg": 0, "avis": CD_AVIS},
        "font": {"tipus": FONT_TIPUS, "eixos": EIXOS},
    }


# ── el formulari → campanya.yaml ────────────────────────────────────────────

def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _pos(x) -> bool:
    return _num(x) and x > 0


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
        e.append(f"domini.font.tipus: cal {' o '.join(FONT_TIPUS)}")
    elif font["tipus"] == "iso":
        if not _llista_de(font.get("pos_cm"), _num, 3):
            e.append("domini.font.pos_cm: tres coordenades en cm, p. ex. [0, 0, 0]")
    else:
        if font.get("eix") not in EIXOS:
            e.append(f"domini.font.eix: cal {' o '.join(EIXOS)} (feix)")
        if not _llista_de(font.get("desplacament_cm"), _num, 2):
            e.append("domini.font.desplacament_cm: dues coordenades en cm (feix)")
    if not _llista_de(dom.get("energies_MeV"), _pos):
        e.append("domini.energies_MeV: una llista de energies positives en MeV")
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
                        e.append(f"{ruta}.anells[{i}]: falta «{k}»")
                if "cd" in a and not isinstance(a["cd"], dict):
                    e.append(f"{ruta}.anells[{i}].cd: cal {{fraction, arc, centre}}")
    elif t == "mapa_un_tub":
        if "polar" not in g and not ("x" in g and "y" in g):
            e.append(f"{ruta}: cal «polar» o bé «x» i «y»")
    elif t == "llista":
        for i, c in enumerate(g.get("candidats") or []):
            if not isinstance(c, dict) or ("dat" not in c and "tubs" not in c):
                e.append(f"{ruta}.candidats[{i}]: cal «dat» o «tubs»")
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


def to_yaml(form: Dict[str, Any]) -> str:
    """El `campanya.yaml` d'esborrany (text). Llança `FormError` amb tots els motius si la forma no
    és llegible per neudet. No modifica `form`."""
    errs = _errors(form)
    if errs:
        raise FormError("formulari no vàlid:\n- " + "\n- ".join(errs))
    return CAPSALERA + yaml.dump(copy.deepcopy(form), Dumper=_Dumper, sort_keys=False,
                                 allow_unicode=True, default_flow_style=None, width=110)
