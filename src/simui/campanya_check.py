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
        if isinstance(e, dict) and ("generador" in e or "tongades" in e):
            return str(nom)
    raise ValueError("el yaml no té cap etapa amb `tongades` (o `generador`): una etapa de xarxa")


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
            # GEN-U: per tongada, els números que neudet porta al meta (`extra.tongades`): recompte, generats, repetits, vàlids, descartats
            "tongades": [dict(t) for t in (getattr(camp, "tongades_info", None) or {}).get("tongades", [])],
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
                                        if isinstance(e, dict) and ("generador" in e or "tongades" in e)]
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


def dat_de_candidat(dir_: Path, hash_: str, etapa: Optional[str] = None) -> Dict[str, Any]:
    """El parell `.dat`/`.json` de neudet (`Candidat.to_dat`) del candidat vàlid de la campanya amb aquest hash.
    Els candidats d'una campanya no tenen `.dat` al disc: neudet els genera, i el mateix `candidat_de` que fa
    servir el tanteig els troba. Llegeix la campanya; no n'escriu res (el `.dat` surt d'un directori temporal)."""
    nom_etapa, cand = candidat_de(dir_, hash_, etapa)
    with tempfile.TemporaryDirectory(prefix="simphy_candidat_") as tmp:
        try:
            dat = cand.to_dat(Path(tmp) / f"{cand.nom}.dat")
            dat_text = Path(dat).read_text()
            json_text = Path(dat).with_suffix(".json").read_text()
        except (SystemExit, Exception) as exc:          # noqa: BLE001 — el missatge de neudet, verbatim
            raise ValueError(_motiu_de(exc)) from None
    return {"etapa": nom_etapa, "nom": cand.nom, "hash": hash_, "dat_text": dat_text, "json_text": json_text}


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


def _amb_simetria(C, etapa: str, e: Dict[str, Any], ts: List[Dict[str, Any]]) -> None:
    """INV-T: a les tongades amb `inventari`, neudet treu els candidats equivalents per gir o reflexió. El recompte d'abans és
    el de `recompte_etapa`; el d'després només el sap l'expansió de neudet (`Campanya.candidats`), que es fa aquí només si
    hi ha inventari i cap tongada passa de `max_candidats`. `simetria` és el de neudet tal com és (`abans`, `despres`,
    `aplicada`, `motiu`, `en_paraules`); si no s'expandeix, `simetria_motiu` diu per què. No inventa res."""
    amb = {t.get("nom") for t in (e.get("tongades") or []) if isinstance(t, dict) and t.get("inventari") is not None}
    if not amb:
        return
    if any(t.get("avis") for t in ts):
        for t in ts:
            if t["nom"] in amb:
                t["simetria_motiu"] = "no s'expandeix: el recompte passa de max_candidats (cal triar mostres)"
        return
    import contextlib
    import io
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            C.candidats(etapa)
    except (SystemExit, Exception) as exc:                  # noqa: BLE001 — el motiu de neudet, verbatim
        for t in ts:
            if t["nom"] in amb:
                t["simetria_motiu"] = "no s'ha pogut expandir: " + _motiu_de(exc)
        return
    info = {t["nom"]: t for t in C.tongades_info["tongades"]}
    for t in ts:
        sim = (info.get(t["nom"]) or {}).get("simetria")
        if sim:
            t["simetria"] = sim


def compta(yaml_text: str, etapa: Optional[str] = None) -> Dict[str, Any]:
    """Quants candidats donen les tongades de l'etapa, ABANS de treure repetits i de les restriccions: és
    `generadors.recompte_etapa` de neudet (la UI no expandeix ni compta). `tongades` és [{nom, recompte}]; `n` és la suma.
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
            from neudet.disseny.generadors import recompte_etapa
            C = Campanya(dir_)
            e = C.etapa(etapa)
            ctx = dict(tipus=C.tipus, n_tubs=e.get("n_tubs", C.restr.get("n_tubs")), restriccions=C.restr, arrel=C.dir)
            ts = recompte_etapa(e, C.bloc, ctx, etapa)
            _amb_simetria(C, etapa, e, ts)
            return {"etapa": etapa, "n": sum(t["recompte"] for t in ts), "tongades": ts}
        except (SystemExit, Exception) as exc:              # noqa: BLE001 — el missatge de neudet, verbatim
            raise ValueError(_motiu_de(exc)) from None


def exemple(yaml_text: str, tubs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """UI-DIB2: els tubs d'un dibuix d'exemple (`[{x, y, z, eix, tipus}]`, a l'ordre del dibuix) passats per `candidat.violacions`
    de neudet, amb el bloc, les restriccions i la font de la campanya: la UI no calcula res d'això. → `violacions` [{tubs, motiu}]
    (els números de tub, a 1; el motiu és el de neudet), `rebutjats` (els números de tub que en tenen) i `n`.
    Un error de neudet arriba tal com és (`ValueError`)."""
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
            from neudet.disseny.campanya import Campanya
            from neudet.disseny.candidat import Candidat, Tub, violacions
            C = Campanya(dir_)
            ts = tuple(Tub(float(t["x"]), float(t["y"]), str(t["tipus"]), float(t.get("z") or 0), eix=t.get("eix") or "z") for t in tubs)
            mots = violacions(Candidat(C.bloc, ts), C.restr, C.tipus, C.font)
        except (SystemExit, Exception) as exc:              # noqa: BLE001 — el missatge de neudet, verbatim
            raise ValueError(_motiu_de(exc)) from None
    out, rebutjats = [], set()
    for m in mots:
        idx = sorted({int(n) + 1 for grup in re.findall(r"\btubs? (\d+)(?: i (\d+))?", m) for n in grup if n != ""})
        txt = re.sub(r"\btubs? (\d+) i (\d+)", lambda g: f"tubs {int(g.group(1)) + 1} i {int(g.group(2)) + 1}", m)
        txt = re.sub(r"\btub (\d+)", lambda g: f"tub {int(g.group(1)) + 1}", txt)
        out.append({"tubs": idx, "motiu": txt})
        rebutjats.update(idx)
    return {"n": len(ts), "violacions": out, "rebutjats": sorted(rebutjats)}


def objectius(yaml_text: str, etapa: Optional[str] = None) -> Dict[str, Any]:
    """OBJ (contracte §14): el bloc d'objectius tal com l'entén neudet, sense desar ni simular: `cicle` (nou | llegat),
    `finalitat`, `en_paraules` i `avisos` [{nivell, codi, etapa, text}] (`neudet.disseny.objectius.avisos`). A l'espectròmetre,
    neudet compta els canals dels candidats vàlids de l'etapa (`campanya.n_canals`): amb un sol canal, l'avís és seu.
    Qualsevol error de neudet arriba tal com és (`ValueError`)."""
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
            from neudet.disseny.campanya import Campanya, n_canals     # neudet importat de NEUDET_ROOT/src
            from neudet.disseny.objectius import avisos, en_paraules
            C = Campanya(dir_)
            ob = C.objectiu
            canals, grups_cd = {}, {}
            if ob.finalitat == "espectrometre":
                if etapa is None:
                    etapa = _primera_etapa_de_xarxa(yaml_text)
                valids, _ = C.candidats(etapa)
                canals[etapa] = [n_canals(c) for c, _ in valids]
                # OBJ·espectre: q_rang, q_monoton i sE_N només amb tubs amb Cd i sense Cd alhora («no aplica», no bloqueja)
                grups_cd[etapa] = [any(t.te_cd for t in c.tubs) and not all(t.te_cd for t in c.tubs) for c, _ in valids]
            return {"cicle": ob.info["cicle"], "finalitat": ob.finalitat, "etapa": etapa,
                    "objectius": [list(p) for p in ob.pareto], "metriques": list(ob.noms),
                    "preferencia": ob.restriccio, "restriccions": [list(r) for r in ob.restriccions],
                    "canals": {k: dict(min=min(v), max=max(v), un_sol_canal=sum(1 for x in v if x < 2), candidats=len(v))
                               for k, v in canals.items() if v} or None,
                    "en_paraules": en_paraules(ob.info), "avisos": avisos(ob.info, C.energies, canals, grups_cd)}
        except (SystemExit, Exception) as exc:              # noqa: BLE001 — el missatge de neudet, verbatim
            raise ValueError(_motiu_de(exc)) from None
