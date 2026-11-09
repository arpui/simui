"""REAVALUA-UI, pas 4: desar un criteri (VER-INC) i veure el pla de verificació a Geant4. La UI no calcula ni escriu res de neudet pel seu compte:

- `desa`: crida `neudet.disseny.criteris.desa_criteri` (neudet escriu `etapes/<e>/criteris.json`). Els errors (`ValueError`) van verbatim.
- `llista`: `criteris_de` + `guanyadors` de neudet, amb la marca de verificat/nou (`verificats`). Només lectura.
- `pla`: `pla_verificacio` (pura) amb els paràmetres que `verifica_g4.py --criteris` agafa (el meta de la verificació existent o 30/0 per als
  aleatoris, `verificacio.*` del campanya.yaml per a n, quants i hits, el `truth` a `data/geant4/detector/verificacio`). NO LLANÇA RES: torna
  el pla i l'ordre que executa Albert.
"""
from __future__ import annotations

import contextlib
import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import campanya_vista as CV
from simphy.mcgen import design as DES


def _neudet():
    try:
        DES._neudet()
    except DES.DesignError as exc:
        raise ValueError(str(exc)) from None
    from neudet.disseny.campanya import Campanya
    from neudet.disseny import criteris as CR
    return Campanya, CR


def _camp(Campanya, id_: str):
    d = CV.dir_de(id_)
    try:
        with contextlib.redirect_stdout(io.StringIO()):          # Campanya() escriu a stdout
            return Campanya(d)
    except SystemExit as exc:                                   # neudet diu els errors amb SystemExit
        raise ValueError(str(exc)) from None


def _etapa(C, etapa: str) -> Path:
    if not etapa or "/" in etapa or "\\" in etapa or etapa.startswith("."):
        raise ValueError(f"etapa {etapa!r}: cal el nom d'una carpeta de `etapes/`")
    d = Path(C.dir) / "etapes" / etapa
    if not (d / "candidats.csv").is_file():
        raise ValueError(f"l'etapa {etapa!r} no té candidats.csv a {Path(C.dir).name}/etapes/")
    return d


def _rows(d: Path) -> Dict[str, dict]:
    with (d / "candidats.csv").open(newline="", encoding="utf-8") as fh:
        return {r["hash"]: r for r in csv.DictReader(fh)}


def desa(id_: str, etapa: str, criteri: Any) -> Dict[str, Any]:
    """«Desa aquest criteri»: `desa_criteri` de neudet tal qual; torna el seu `{path, criteri, avis}` i la llista refeta."""
    Campanya, CR = _neudet()
    C = _camp(Campanya, id_)
    _etapa(C, etapa)
    try:
        r = CR.desa_criteri(C, etapa, criteri)
    except SystemExit as exc:
        raise ValueError(str(exc)) from None
    return {"path": r["path"], "criteri": r["criteri"], "avis": r["avis"], "criteris": llista(id_, etapa)["criteris"]}


def llista(id_: str, etapa: str) -> Dict[str, Any]:
    """Els criteris de l'etapa (`criteris_de`: l'inicial de campanya.yaml i els desats), cadascun amb els seus guanyadors (`guanyadors`)."""
    Campanya, CR = _neudet()
    C = _camp(Campanya, id_)
    d = _etapa(C, etapa)
    rows = _rows(d)
    ja = CR.verificats(C, etapa) if (Path(C.dir) / "etapes" / f"{etapa}_g4" / "candidats.csv").is_file() else None
    out = []
    for cr in CR.criteris_de(C, etapa):
        g = CR.guanyadors(C, etapa, cr)
        pref = {**(C.objectiu.restriccio or {}), **{k: v for k, v in (cr.get("preferencia") or {}).items() if v is not None}}
        gs = []
        for h, motius in g.items():
            r = rows.get(h, {})
            gs.append({"hash": h, "nom": r.get("nom", h), "motius": motius, "g4": None if ja is None else h in ja,
                       "maxim": r.get(pref.get("maxim")), "sobre": r.get(pref.get("sobre"))})
        out.append({**cr, "inicial": cr["nom"] == CR.NOM_INICIAL, "preferencia": pref, "guanyadors": gs,
                    "avis": CR.avis_objectius(cr, C.objectiu.pareto)})
    return {"id": id_, "etapa": etapa, "etapa_g4": f"{etapa}_g4" if ja is not None else None, "criteris": out}


def pla(id_: str, etapa: str) -> Dict[str, Any]:
    """El pla de `verifica_g4.py --etapes <etapa> --criteris` (`pla_verificacio` de neudet, pura) i l'ordre per córrer-ho. No llança ni escriu res."""
    Campanya, CR = _neudet()
    from neudet.disseny.seleccio import ekey
    from neudet.disseny import resum_peticio as RP
    C = _camp(Campanya, id_)
    d = _etapa(C, etapa)
    ver = (C.cfg.get("verificacio") or {})
    # els mateixos orígens que verifica_g4.py: n i quants del campanya.yaml (n: 100000 per defecte), hits del campanya.yaml sense defecte
    n = int(ver.get("n_per_energia") if ver.get("n_per_energia") is not None else 100_000)
    quants = ver.get("quants")
    hits = ver.get("hits")
    if hits not in ("all", "detect"):
        raise ValueError("cal verificacio.hits (all | detect) al campanya.yaml de la campanya: el mode del bolcat no té defecte "
                         f"(ara: {hits!r}); verifica_g4.py ho demana igual")
    meta = CR.meta_g4(C, etapa)
    pa = ((meta or {}).get("args") or {})
    k_al = int(pa.get("aleatoris", 30))
    llavor = int(pa.get("llavor", 0))
    avisos_ui: List[str] = []
    if meta and CR.verificats(C, etapa) and (int(pa.get("n", n)) != n or pa.get("hits") not in (None, hits)):
        avisos_ui.append(f"⛔ {etapa}_g4 ja existeix amb n={pa.get('n')} hits={pa.get('hits')}; el campanya.yaml demana n={n} hits={hits}: "
                         "verifica_g4.py --criteris ho refusa (no es barregen)")
    truth = DES.neudet_root() / "data" / "geant4" / "detector" / "verificacio"
    cell_dir = lambda h, E: truth / h / ("E" + ekey(E))
    taxa = RP.taxa_g4(sorted(RP.CAMPANYES.glob("*/etapes/*/meta.json")))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            p = CR.pla_verificacio(C, [etapa], k_al, llavor, (), quants, n, hits, cell_dir=cell_dir, taxa=taxa)
    except SystemExit as exc:
        raise ValueError(str(exc)) from None
    rows = _rows(d)
    nom = lambda h: (p["sel"].get(h) or {}).get("nom") or rows.get(h, {}).get("nom") or h
    c = p["cost"]
    formules = None
    if c:
        nE = len(C.energies)
        formules = {"cel_les": f"cel·les = candidats × energies = {c['candidats']} × {nE}",
                    "disc_gb": (f"disc = cel·les × n × bytes/event ({c['bytes_event']}, {c['taula_disc']}) × {RP.MARGE_DISC} / 1e9 "
                                f"(n = {n}, hits = {hits})"),
                    "cpu_h": (f"CPU = cel·les × n / 1e6 × {taxa['core_h_per_cel_1e6']} core·h per cel·la de 1e6 (taxa de {c.get('taxa_de')})"
                              if taxa else "no hi ha cap verificació anterior amb temps (`t_truth_s`) per estimar la CPU: neudet no la dona"),
                    "durada_h": (f"durada = CPU / {taxa['jobs']} places" if taxa else "idem: sense taxa"),
                    "font": "neudet.disseny.resum_peticio.cost_g4"}
    gan = {k: [{"hash": h, "nom": nom(h), "motius": m, "nou": h in p["nous"]} for h, m in g.items()] for k, g in p["per_criteri"].items()}
    cmd = (f"cd ~/projects/neudet && python3 scripts/disseny/verifica_g4.py --etapes {etapa} "
           f"--campanya disseny/campanyes/{id_} --criteris")
    return {"id": id_, "etapa": etapa, "etapa_g4": f"{etapa}_g4" if CR.verificats(C, etapa) else None,
            "parametres": {"aleatoris": k_al, "llavor": llavor, "n": n, "hits": hits, "quants": quants,
                           "origen": "aleatoris i llavor: " + (f"el meta de {etapa}_g4" if meta else "per defecte de verifica_g4.py (30 i 0)")
                                     + "; n, quants i hits: verificacio.* del campanya.yaml"},
            "nous": [{"hash": h, "nom": nom(h)} for h in p["nous"]],
            "verificats_ja": [{"hash": h, "nom": nom(h)} for h in p["verificats_ja"]],
            "per_criteri": gan, "avisos": list(p["avisos"]) + avisos_ui, "cost": c, "formules_cost": formules,
            "sense_truth": [{"hash": h, "nom": nom(h)} for h in p["sense_truth"]], "cel_les_a_correr": p["cel_les_a_correr"],
            "n_energies": len(C.energies),
            "ordre": cmd,
            "frase": ("Això NO es llança des de la UI: ho executa Albert. L'ordre corre el que falta a Geant4 i reescriu "
                      f"{etapa}_g4 sencer (verificats + nous). Afegint --seleccion només mostra el pla i escriu seleccio.csv, sense Geant4.")}
