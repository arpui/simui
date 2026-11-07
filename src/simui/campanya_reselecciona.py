"""REAVALUA-UI, pas 1: tornar a presentar els candidats d'una etapa amb altres criteris, SENSE simular ni escriure res.

Els números (mètriques, σ) ja són al `candidats.csv` de l'etapa; aquí només es reordenen. La selecció és de neudet i no es copia:
`rang_pareto`, `frontera_robusta` i `epsilon_restriccio` (`neudet.disseny.objectius`), i `Objectiu.compleix` per a les restriccions
dures, amb el mateix filtre que `campanya.py` (finals amb les objectius finites i que compleixen les restriccions).

Només compten els candidats que la cerca va avaluar: els de cribratge que el halving va descartar amb els criteris d'origen no hi són,
i si es canvia què decideix, un candidat que els nous haurien posat a la frontera pot faltar. El resultat ho diu (`avisos`).
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import campanya_vista as CV
from . import design as DES

#: rondes que entren a la frontera (el mateix que `campanya.py` i `recalcula_objectiu.py`; verifica_g4 escriu «verificat»)
FINALS = ("única", "final", "verificat")


def _f(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _net(x: Any) -> Any:
    """JSON no admet nan: es dona com a `None`."""
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def _energies(cols: List[str]) -> List[float]:
    return [float(c[len("eps_"):-len("MeV")]) for c in cols if c.startswith("eps_") and c.endswith("MeV")]


def _etapa_dir(camp: Path, etapa: str) -> Path:
    if not etapa or "/" in etapa or "\\" in etapa or etapa.startswith("."):
        raise ValueError(f"etapa {etapa!r}: cal el nom d'una carpeta de `etapes/`")
    d = camp / "etapes" / etapa
    if not (d / "candidats.csv").is_file():
        have = sorted(p.parent.name for p in (camp / "etapes").glob("*/candidats.csv")) if (camp / "etapes").is_dir() else []
        raise ValueError(f"l'etapa {etapa!r} no té candidats.csv a {camp.name}/etapes/ (n'hi ha: {', '.join(have) or 'cap'})")
    return d


def reselecciona(id_: str, etapa: str, criteris: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Els guanyadors, la frontera i els recomptes d'una etapa amb els criteris de la campanya, o amb els que es donin.

    `criteris` (tot opcional; el que falta és el de la campanya): `objectius` [[mètrica, max|min], …] (els eixos de Pareto),
    `k_sigma`, `maxim` i `sobre` (l'ε-restricció: guanya el de més `maxim` amb `sobre` ≤ c), `c` [valors], `restriccions`
    [[mètrica, operador, valor], …] (dures). Un error de neudet o de la forma arriba com a `ValueError`."""
    camp = CV.dir_de(id_)
    d = _etapa_dir(camp, etapa)
    try:
        DES._neudet()
        import yaml
        from neudet.disseny.objectius import Objectiu, epsilon_restriccio, frontera_robusta, rang_pareto
    except DES.DesignError as exc:
        raise ValueError(str(exc)) from None
    with (d / "candidats.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"{etapa}/candidats.csv és buit")
    cols = list(rows[0])
    cfg = yaml.safe_load((camp / "campanya.yaml").read_text(encoding="utf-8")) or {}
    try:
        ob = Objectiu(dict(cfg.get("objectius", {})), _energies(cols), arrel=camp)
    except SystemExit as exc:                                   # neudet diu els errors amb SystemExit
        raise ValueError(str(exc)) from None
    cr = criteris or {}
    pareto = [tuple(x) for x in cr["objectius"]] if cr.get("objectius") else [tuple(x) for x in ob.pareto]
    k_sigma = float(cr["k_sigma"]) if cr.get("k_sigma") is not None else float(ob.k_sigma)
    rest = dict(ob.restriccio)
    for k in ("maxim", "sobre"):
        if cr.get(k):
            rest[k] = cr[k]
    cs = [float(c) for c in (cr["c"] if "c" in cr and cr["c"] is not None else rest.get("c") or [])]
    ob.restriccions = [tuple(r) for r in cr["restriccions"]] if cr.get("restriccions") is not None else ob.restriccions
    ob.restriccions = [(n, op, float(v)) for n, op, v in ob.restriccions]
    usades = [n for n, _ in pareto] + ([rest["maxim"], rest["sobre"]] if cs else []) + [r[0] for r in ob.restriccions]
    falten = sorted({n for n in usades if n not in cols})
    if falten:
        raise ValueError(f"{etapa}/candidats.csv no té la mètrica {', '.join(falten)} (n'hi ha: "
                         f"{', '.join(c for c in cols if not c.startswith(('eps_', 'sig_', 'eps0_', 'eps1_', 'sig0_', 'sig1_')) and not c.endswith('_sig'))})")
    for n, op, _ in ob.restriccions:
        if op not in ("<=", ">=", "<", ">", "=="):
            raise ValueError(f"restricció amb operador {op!r}: cal <=, >=, <, > o ==")
    # les files finals, amb les mètriques com a números (les `_sig` també)
    mets = sorted(set(usades) | {n + "_sig" for n in usades if n + "_sig" in cols})
    def fila(r):
        o = {"nom": r["nom"], "hash": r["hash"], "ronda": r.get("ronda", "única")}
        o.update({m: _f(r.get(m)) for m in mets})
        return o
    totes = [fila(r) for r in rows]
    finals = [f for f in totes if f["ronda"] in FINALS]
    obj_ok = [f for f in finals if all(math.isfinite(f[n]) for n, _ in pareto)]
    ok = [f for f in obj_ok if ob.compleix(f)]                 # el mateix filtre que `campanya.py`
    n_restr = len(obj_ok) - len(ok)
    rang, rob = [], []
    if ok:
        rang = rang_pareto(ok, pareto)
        rob = frontera_robusta(ok, pareto, k_sigma)
    tria = ok                                                  # les restriccions dures també valen per a la tria
    guanyadors = []
    for c in cs:
        i = epsilon_restriccio(tria, c, rest["maxim"], rest["sobre"]) if tria else -1
        g = {"c": c, "cap": i < 0}
        if i >= 0:
            g.update({"nom": tria[i]["nom"], "hash": tria[i]["hash"], "maxim": tria[i][rest["maxim"]], "sobre": tria[i][rest["sobre"]]})
        guanyadors.append(g)
    metr = lambda f: {m: _net(f[m]) for m in mets}
    frontera = [dict(nom=f["nom"], hash=f["hash"], robusta=bool(rb), **metr(f)) for f, rg, rb in zip(ok, rang, rob) if rg == 0]
    frontera.sort(key=lambda f: -(f[pareto[0][0]] or 0) if pareto[0][1] == "max" else (f[pareto[0][0]] or 0))
    punts = [dict(nom=f["nom"], hash=f["hash"], rang=int(rg), robusta=bool(rb), **metr(f)) for f, rg, rb in zip(ok, rang, rob)]
    avisos = []
    n_crib = len(totes) - len(finals)
    if n_crib:
        avisos.append(f"{n_crib} candidats de cribratge no hi són: la cerca els va descartar amb els criteris d'origen, i un candidat que "
                      "els criteris nous haurien posat a la frontera pot faltar. Només compta el que s'ha avaluat fins al final.")
    sense_sig = [n for n, _ in pareto if n + "_sig" not in cols]
    if sense_sig:
        avisos.append(f"el CSV no porta la σ de {', '.join(sense_sig)} (`_sig`): la frontera robusta no té soroll i és la de Pareto.")
    if n_restr:
        avisos.append(f"{n_restr} de {len(obj_ok)} finals no compleixen les restriccions dures: fora de la frontera i de la tria.")
    if len(finals) - len(obj_ok):
        avisos.append(f"{len(finals) - len(obj_ok)} finals tenen alguna de les objectius sense valor (nan) i no entren a la frontera.")
    return {"id": id_, "etapa": etapa,
            "criteris": {"objectius": [list(p) for p in pareto], "k_sigma": k_sigma, "maxim": rest.get("maxim"), "sobre": rest.get("sobre"),
                         "c": cs, "restriccions": [list(r) for r in ob.restriccions]},
            "n_finals": len(finals), "n_valids": len(ok), "n_fora_restriccions": n_restr, "n_cribratge": n_crib,
            "te_sig": not sense_sig, "frontera": frontera, "guanyadors": guanyadors, "punts": punts, "avisos": avisos}
