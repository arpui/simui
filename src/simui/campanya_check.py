"""campanya_check.py — la comprovació d'un `campanya.yaml` amb neudet (contracte simphy_ui.md §4, C2).

Qui decideix què
----------------
La validesa la dona NEUDET. Aquí no hi ha cap regla de validesa: només es passa el yaml a neudet
i es mostra el que diu.

- Si `scripts/disseny/comprova_campanya.py` existeix (CAMP-1), es corre com a subprocés amb
  `PYTHONPATH=<neudet>/src`, i la seva sortida es torna TAL COM és, marcada com a no llegible per
  màquina (el format no està fixat).
- Si no, `neudet.disseny.campanya.Campanya(dir).candidats(etapa)`: els vàlids i els invàlids amb els
  seus motius. Els motius s'agrupen per text amb els nombres substituïts per «#» (és només la
  presentació: el recompte és de neudet). Els primers candidats vàlids porten el `.dat`/`.json` de
  neudet (`Candidat.to_dat`) i el SVG XY del visor de simphy (`design_view`).

Qualsevol excepció de neudet arriba com a missatge: el de `SystemExit` tal com és (neudet fa servir
`raise SystemExit("⛔ …")` als seus errors), i la resta com a `Tipus: missatge`.
"""
from __future__ import annotations

import os
import re
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import design as DES
from . import design_view as VIEW

#: el script de certificació de neudet (CAMP-1); si no hi és, no es certifica res
SCRIPT_REL = "scripts/disseny/comprova_campanya.py"
#: quants candidats vàlids es mostren (amb el seu visor) per a la llista de C3
MOSTRA = 50
NO_CERTIFICAT = ("scripts/disseny/comprova_campanya.py no existeix a neudet (CAMP-1 pendent): "
                 "la comprovació no certifica res (ni «no validat», ni els avisos de Cd).")


def _primera_etapa_de_xarxa(yaml_text: str) -> str:
    """La primera etapa amb `generador` (o l'error de yaml, tal com el dona PyYAML)."""
    import yaml
    data = yaml.safe_load(yaml_text)
    etapes = (data or {}).get("etapes") if isinstance(data, dict) else None
    for nom, e in (etapes or {}).items():
        if isinstance(e, dict) and "generador" in e:
            return str(nom)
    raise ValueError("el yaml no té cap etapa amb `generador` (una etapa de xarxa)")


def _motiu_de(exc: BaseException) -> str:
    """El missatge de neudet, tal com és."""
    if isinstance(exc, SystemExit):
        return str(exc.code) if isinstance(exc.code, str) else f"SystemExit: {exc.code}"
    return f"{type(exc).__name__}: {exc}"


def _python_neudet() -> str:
    """El Python que corre neudet (cal `torch` per a la certificació): `NEUDET_PYTHON`, o el de la UI."""
    return os.environ.get("NEUDET_PYTHON") or sys.executable


def _executa_comprova(script: Path, dir_: Path, out: Path) -> subprocess.CompletedProcess:
    """`comprova_campanya.py <dir> --json <out>` amb el Python de neudet i `src` de neudet al path.
    Un veredicte d'aturada (codi 1) no és un error d'aquí: el decideix qui llegeix el `out`."""
    root = script.parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(root / "src"), env.get("PYTHONPATH", "")) if p)
    return subprocess.run([_python_neudet(), str(script), str(dir_), "--json", str(out)], cwd=str(root), env=env,
                          capture_output=True, text=True, timeout=600)


def _certifica(script: Path, dir_: Path) -> Dict[str, Any]:
    """`comprova_campanya.py <dir> --json <fitxer>` (contracte §5, pas 2). El veredicte és el de neudet:
    `atura`, els `elements` (validat / no_validat / prohibit, amb motiu) i, si falten camps, quins.
    Si el script peta abans d'escriure el JSON, es dona la seva sortida tal com és."""
    root = script.parents[2]
    out = dir_.parent / "certificacio.json"
    p = _executa_comprova(script, dir_, out)
    base = {"disponible": False, "ordre": f"PYTHONPATH=src python3 {SCRIPT_REL} <dir> --json <fitxer>",
            "codi_sortida": p.returncode, "sortida": p.stdout, "error_sortida": p.stderr[-4000:]}
    if not out.exists():
        base["motiu"] = "comprova_campanya.py no ha escrit el JSON: vegeu la sortida d'error de neudet"
        return base
    inf = json.loads(out.read_text(encoding="utf-8"))
    base.update(disponible=True, motiu="", atura=bool(inf.get("atura")), draft=inf.get("draft"),
                camps_falten=inf.get("camps_falten"), etapes=inf.get("etapes") or {},
                elements=inf.get("elements") or [])
    return base


def _motius(invalids) -> List[Dict[str, Any]]:
    """Agrupa els motius d'invàlids: per text amb els nombres per «#». Compta candidats, no motius."""
    per_motiu: Counter = Counter()
    exemple: Dict[str, str] = {}
    for _, vs in invalids:
        for clau in {re.sub(r"\d+(\.\d+)?", "#", v) for v in vs}:
            per_motiu[clau] += 1
        for v in vs:
            exemple.setdefault(re.sub(r"\d+(\.\d+)?", "#", v), v)
    return [{"motiu": m, "n_candidats": n, "exemple": exemple[m]} for m, n in per_motiu.most_common()]


def _visor(dat: Path, font: Optional[Dict[str, Any]]) -> str:
    f = None
    if font and font.get("tipus") == "iso":
        x, y, z = (float(v) for v in font["pos_cm"])
        f = VIEW.Font("iso", x, y, z, VIEW.ORIGIN_JSON)
    return VIEW.preview(dat, font=f)["xy_svg"]


def _candidats(valids, tmp: Path, font: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i, (c, _) in enumerate(valids[:MOSTRA]):
        dat = c.to_dat(tmp / f"v{i:03d}.dat")
        out.append({"nom": c.nom, "hash": c.hash(),
                    "xy": [[round(x, 6), round(y, 6)] for x, y in c.xy],
                    "tubs": [{"x": t.x, "y": t.y, "z": t.z, "tipus": t.tipus} for t in c.tubs],
                    "dat_text": dat.read_text(), "json_text": dat.with_suffix(".json").read_text(),
                    "xy_svg": _visor(dat, font)})
    return out


def _amb_candidats(dir_: Path, etapa: str, tmp: Path, script: Optional[Path] = None) -> Dict[str, Any]:
    from neudet.disseny.campanya import Campanya            # neudet importat de NEUDET_ROOT/src
    camp = Campanya(dir_)
    valids, invalids = camp.candidats(etapa)
    return {"via": "candidats", "etapa": etapa, "llegible_per_maquina": True,
            "n_valids": len(valids), "n_invalids": len(invalids), "motius": _motius(invalids),
            "candidats": _candidats(valids, tmp, camp.font),
            "certificacio": _certifica(script, dir_) if script is not None
                            else {"disponible": False, "motiu": NO_CERTIFICAT, "elements": []}}


def certifica_proposta(yaml_text: str, id_: str) -> Dict[str, Any]:
    """La certificació de neudet d'UN `campanya.yaml` (el que es vol desar): el mateix JSON que
    `comprova_campanya.py --json` (és el `comprova.json` de la campanya). Corre en un directori temporal i
    no escriu res a neudet. Un veredicte d'aturada (`atura`) és una certificació vàlida i es desa; el que
    llança `ValueError` (amb el motiu) és una certificació NO disponible: sense script, sense `torch`, sense
    JSON, sense la forma de certificació, o d'una altra campanya."""
    try:
        root = DES.neudet_root()
    except DES.DesignError as exc:
        raise ValueError(str(exc)) from None
    script = root / SCRIPT_REL
    if not script.exists():
        raise ValueError(NO_CERTIFICAT)
    with tempfile.TemporaryDirectory(prefix="simphy_certifica_") as tmp:
        dir_ = Path(tmp) / id_
        dir_.mkdir()
        (dir_ / "campanya.yaml").write_text(yaml_text, encoding="utf-8")
        out = Path(tmp) / "comprova.json"
        try:
            p = _executa_comprova(script, dir_, out)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError(f"no s'ha pogut córrer comprova_campanya.py: {exc}") from None
        if not out.exists():
            detall = (p.stderr or p.stdout or "").strip()[-1500:] or "sense sortida"
            raise ValueError(f"comprova_campanya.py no ha escrit la certificació (codi {p.returncode}): {detall}")
        try:
            rep = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"la certificació de neudet no és JSON: {exc}") from None
    if isinstance(rep, dict) and rep.get("camps_falten"):
        raise ValueError(f"neudet no pot llegir la campanya: {rep['camps_falten']}")
    if not isinstance(rep, dict) or "atura" not in rep or not isinstance(rep.get("elements"), list):
        raise ValueError("la certificació de neudet no té la forma esperada (falten `atura` o `elements`)")
    if rep.get("campanya") != id_:
        raise ValueError(f"la certificació és de «{rep.get('campanya')}», no de «{id_}»")
    return rep


def candidat_de(dir_: Path, hash_: str, etapa: Optional[str] = None) -> Tuple[str, Any]:
    """(etapa, candidat) de neudet: el candidat VÀLID de la campanya amb aquest hash, en `etapa` o en la
    primera etapa de xarxa que el té. Els tubs són els que neudet genera (`Campanya.candidats`). Llegeix la
    campanya; no n'escriu res."""
    try:
        DES._neudet()
    except DES.DesignError as exc:
        raise ValueError(str(exc)) from None
    trobat = None
    etapes: List[str] = []
    try:
        from neudet.disseny.campanya import Campanya     # neudet importat de NEUDET_ROOT/src
        C = Campanya(Path(dir_))
        etapes = [etapa] if etapa else [n for n, e in (C.cfg.get("etapes") or {}).items()
                                        if isinstance(e, dict) and "generador" in e]
        for nom in etapes:
            valids, _ = C.candidats(nom)
            for c, _v in valids:
                if c.hash() == hash_:
                    trobat = (nom, c)
                    break
            if trobat:
                break
    except (SystemExit, Exception) as exc:              # noqa: BLE001 — el missatge de neudet, verbatim
        raise ValueError(_motiu_de(exc)) from None
    if trobat is None:
        raise ValueError(f"cap candidat vàlid amb hash {hash_} a les etapes de xarxa "
                         f"({', '.join(etapes) or 'cap'}) d'aquesta campanya")
    return trobat


def comprova(yaml_text: str, etapa: Optional[str] = None) -> Dict[str, Any]:
    """Passa el `campanya.yaml` (text) a neudet i retorna el veredicte. Llança ValueError amb el
    missatge de neudet si no pot (yaml trencat, etapa que no hi és, neudet que no es pot importar)."""
    if not isinstance(yaml_text, str) or not yaml_text.strip():
        raise ValueError("el campanya.yaml és buit")
    try:
        root = DES.neudet_root()
        DES._neudet()                                       # comprova que neudet és el que corre
    except DES.DesignError as exc:
        raise ValueError(str(exc)) from None
    with tempfile.TemporaryDirectory(prefix="simphy_campanya_") as tmp:
        dir_ = Path(tmp) / "campanya"
        dir_.mkdir()
        (dir_ / "campanya.yaml").write_text(yaml_text)
        try:
            if etapa is None:
                etapa = _primera_etapa_de_xarxa(yaml_text)
            script = root / SCRIPT_REL
            # els candidats (per al visor) surten sempre de neudet; la certificació, del seu script
            return _amb_candidats(dir_, etapa, Path(tmp), script if script.exists() else None)
        except (SystemExit, Exception) as exc:              # noqa: BLE001 — el missatge de neudet, verbatim
            raise ValueError(_motiu_de(exc)) from None


def compta(yaml_text: str, etapa: Optional[str] = None) -> Dict[str, Any]:
    """Quants candidats genera la regla de l'etapa, ABANS de les restriccions. És `Campanya.candidats` de
    neudet (que crida `generadors.genera` amb el bloc i el context de la campanya): valids + invalids.
    Qualsevol error de neudet arriba tal com és (`ValueError` amb el seu missatge)."""
    if not isinstance(yaml_text, str) or not yaml_text.strip():
        raise ValueError("el campanya.yaml és buit")
    try:
        DES._neudet()
    except DES.DesignError as exc:
        raise ValueError(str(exc)) from None
    with tempfile.TemporaryDirectory(prefix="simphy_campanya_") as tmp:
        dir_ = Path(tmp) / "campanya"
        dir_.mkdir()
        (dir_ / "campanya.yaml").write_text(yaml_text)
        try:
            if etapa is None:
                etapa = _primera_etapa_de_xarxa(yaml_text)
            from neudet.disseny.campanya import Campanya     # neudet importat de NEUDET_ROOT/src
            valids, invalids = Campanya(dir_).candidats(etapa)
            return {"etapa": etapa, "n": len(valids) + len(invalids)}
        except (SystemExit, Exception) as exc:              # noqa: BLE001 — el missatge de neudet, verbatim
            raise ValueError(_motiu_de(exc)) from None
