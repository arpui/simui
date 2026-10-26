"""campanya_vista.py — una campanya de neudet com a conjunt (contracte simphy_ui.md §6, encàrrec CAMP-2).

simphy LLEGEIX el que neudet escriu a `disseny/campanyes/<id>/`; no calcula cap rànquing ni cap
robustesa (són els del `candidats.csv`), no escriu res i no llança cap simulació.

Què fa
------
- `manifest(dir)`: el `campanya_ui.json` de la campanya si hi és (l'índex que escriu neudet), validat
  mínimament i tal qual, amb els camps que no coneix. Si no hi és, `manifest_provisional(dir)`: la
  mateixa estructura, construïda del directori seguint §6 literalment, amb `provisional: true` i el motiu.
- `vista(dir)`: la campanya com a dades per a la pàgina. Per a cada etapa, el `candidats.csv` (totes
  les columnes) i el `resultats_tub.json` (via `results_tub.load`) units pel `hash`. Els eixos de
  Pareto són `objectius.pareto` de `campanya.yaml`. El `pareto_rang` i la `robusta` són els del csv.
  Cada candidat de la xarxa diu en quines etapes `_g4` ha estat verificat (`g4`).
- `fitxer(dir, rel)`: el fitxer que es pot servir de la campanya: dins del seu directori, o un report
  que el manifest llista. Qualsevol altra cosa és `Prohibit` (403).

Claus del manifest
------------------
CAMP-2 (§6) fixa els noms de camp de primer nivel: `definicio`, `certificacio`, `etapes`, `export`,
`judici`, `report`, `estat`. Els camps de dins NO els fixa el text. SUPOSATS, a confirmar amb neudet
quan arribi CAMP-2:

- `definicio`: `{"yaml": "campanya.yaml", "md": "DEFINICIO.md" | null}`
- `certificacio`: `"comprova.json"` | null
- `etapes`: llista de `{nom, dir, motor, candidats, resultats_tub, meta, figures, n_candidats, n_csv,
  citable, motius, verifica}`. `candidats`, `resultats_tub`, `meta` i `figures/*` són camins relatius a
  la carpeta de la campanya. `motor` és el de `resultats_tub.json`; sense ell, el de `meta.json`
  (`args.argv` amb `--xarxa X` → `xarxa X`; `script` = `verifica_g4.py` → `geant4`). `n_candidats` són
  els del `resultats_tub.json` (els que tenen tubs); `n_csv` són totes les files del csv (les descartades
  a la cribratge hi són). `verifica` és el nom de l'etapa de xarxa que verifica una `_g4` (el mateix
  nom sense `_g4`), o null.
- `export`: `"export"` | null
- `judici`: text de la secció «## Judici» de `PLA.md` | null
- `report`: llista de camins **relatius al repo de neudet** (el `.md` i el `.pdf` de
  `docs/site/report/` que contenen l'id de la campanya)
- `estat`: `"draft"` | `"definitiva"` (de `campanya.yaml`: `draft: true` → draft)

Els camins de la campanya no poden ser absoluts ni tenir `..`. Un manifest que no els compleix es
rebutja amb un `CampanyaError` que diu quin camp.

Errors
------
`CampanyaError` (ValueError): entrada que no es pot llegir o validar; el missatge diu què cal arreglar.
`Prohibit` (PermissionError): un fitxer que no es pot servir; la ruta HTTP respon 403.
"""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from . import results_tub as RES
from .design import DesignError, neudet_root

PathLike = Union[str, Path]

MANIFEST = "campanya_ui.json"
MOTIU_PROVISIONAL = "campanya_ui.json encara no hi és (CAMP-2)"
CAMPS_MANIFEST = ("definicio", "certificacio", "etapes", "export", "judici", "report", "estat")
ESTATS = ("draft", "definitiva")
#: `estat:` del campanya.yaml (flux, _flux_campanya.md): informatiu; els altres valors es mostren tal com són
ESTAT_PROPOSTA = "proposta"
#: Tipus de fitxer que la pàgina pot demanar de la campanya, amb el seu Content-Type.
TIPUS = {
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".md": "text/plain; charset=utf-8",
    ".yaml": "text/plain; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}
#: Columnes del csv que són text (la resta es llegeixen com a números, si ho són).
_TEXT = ("nom", "hash", "ronda")


class CampanyaError(ValueError):
    """Una campanya o un manifest que no es pot llegir o validar. El missatge diu què cal fer."""


class Prohibit(PermissionError):
    """Un fitxer fora de la campanya (o un tipus que no es serveix). La ruta HTTP respon 403."""


# ── on són les campanyes ────────────────────────────────────────────────────

def campanyes_root() -> Path:
    """`disseny/campanyes` del repo de neudet (mai dins de simphy)."""
    return neudet_root() / "disseny" / "campanyes"


def dir_de(id_: str) -> Path:
    """La carpeta d'una campanya de neudet pel seu id (el nom de la carpeta, sense camins)."""
    if not isinstance(id_, str) or not id_ or Path(id_).name != id_ or id_ in (".", ".."):
        raise CampanyaError(f"id de campanya no vàlid: {id_!r}")
    root = campanyes_root()
    d = root / id_
    if not (d / "campanya.yaml").is_file():
        raise CampanyaError(f"no trobo la campanya «{id_}» a {root} (cal campanya.yaml)")
    return d


#: el grup de la llista de la pestanya: les que tenen manifest, són `proposta` o són del flux nou (`fitxa: 1`,
#: de c04 endavant; mentre no tinguin manifest es veuen amb el provisional) van a la vista principal;
#: la resta (c01–c03) són a «altres campanyes», plegades.
GRUP_PRINCIPAL, GRUP_ALTRES = "principal", "altres"


def llista() -> List[Dict[str, Any]]:
    """Les campanyes de neudet (carpetes amb `campanya.yaml`). Per a cada una, DUES coses que no són el mateix:
    `estat_yaml` (el camp `estat:` del campanya.yaml, tal com és: `proposta`, `jutjada`, `S3`, `tancada (…)`…;
    un valor desconegut no és un error) i `estat_manifest` (`draft` o `definitiva`, de `draft:` del yaml, el que
    diu CAMP-2). Un yaml il·legible no fa caure la llista: surt amb `motiu`."""
    out: List[Dict[str, Any]] = []
    root = campanyes_root()
    if not root.is_dir():
        raise CampanyaError(f"no trobo {root}: neudet no té disseny/campanyes/")
    for d in sorted(p for p in root.iterdir() if p.is_dir() and (p / "campanya.yaml").is_file()):
        motiu = None
        y: Dict[str, Any] = {}
        try:
            y = _yaml(d / "campanya.yaml")
            estat_manifest = _estat(y)
        except CampanyaError as exc:
            estat_manifest, motiu = "desconegut", str(exc)
        e_yaml = y.get("estat")
        estat_yaml = None if e_yaml is None else str(e_yaml)
        te_manifest = (d / MANIFEST).is_file()
        proposta = estat_yaml == ESTAT_PROPOSTA
        out.append({"id": d.name, "estat_yaml": estat_yaml, "estat_manifest": estat_manifest,
                    "manifest": te_manifest, "provisional": not te_manifest, "proposta": proposta,
                    "grup": GRUP_PRINCIPAL if (te_manifest or proposta or y.get("fitxa") == 1) else GRUP_ALTRES,
                    "motiu": motiu})
    return out


# ── lectors petits ──────────────────────────────────────────────────────────

def _yaml(f: Path) -> Dict[str, Any]:
    import yaml
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CampanyaError(f"{f}: YAML no vàlid ({exc})") from exc
    if not isinstance(data, dict):
        raise CampanyaError(f"{f}: l'arrel ha de ser un diccionari")
    return data


def _estat(y: Dict[str, Any]) -> str:
    """`draft: true` → draft; `draft: false` → definitiva; si no hi és, no s'endevina."""
    d = y.get("draft")
    if d is True:
        return "draft"
    if d is False:
        return "definitiva"
    return "desconegut"


def _json(f: Path) -> Dict[str, Any]:
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CampanyaError(f"{f}: JSON no vàlid ({exc})") from exc
    if not isinstance(doc, dict):
        raise CampanyaError(f"{f}: l'arrel ha de ser un objecte JSON")
    return doc


def _num(v: Any) -> Any:
    """Un valor de csv com a número si ho és (finit); si no, el text tal com és; buit → None."""
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        x = float(s)
    except ValueError:
        return s
    if not math.isfinite(x):
        return None
    if x.is_integer() and re.fullmatch(r"[+-]?\d+", s):
        return int(x)
    return x


def _csv(f: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with open(f, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        rows = list(rd)
        return list(rd.fieldnames or []), rows


def _rel(d: Path, p: Path) -> str:
    return p.relative_to(d).as_posix()


def _dins(d: Path, rel: Any, camp: str) -> Path:
    """Un camí del manifest, relatiu a la campanya. Absolut o amb `..` és un error."""
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in PurePosixPath(rel).parts:
        raise CampanyaError(f"{camp}: el camí {rel!r} ha de ser relatiu a la campanya, sense ..")
    return d / rel


def _iguals(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return float(a) == float(b)


def _motor(doc: Optional[Dict[str, Any]], meta: Optional[Dict[str, Any]]) -> Optional[str]:
    """El `motor` de `resultats_tub.json`; sense ell, el que diu `meta.json` (vegeu la docstring)."""
    if doc is not None:
        return doc.get("motor")
    if meta is None:
        return None
    argv = (meta.get("args") or {}).get("argv") or []
    if "--xarxa" in argv and argv.index("--xarxa") + 1 < len(argv):
        return f"xarxa {argv[argv.index('--xarxa') + 1]}"
    if meta.get("script") == "verifica_g4.py":
        return "geant4"
    return None


def _figures(d: Path, e: Path) -> List[str]:
    fd = e / "figures"
    if not fd.is_dir():
        return []
    return sorted(_rel(d, f) for f in fd.iterdir() if f.is_file() and f.suffix.lower() in (".png", ".svg"))


def _judici(pla: Path) -> Optional[str]:
    """El text de la secció «## Judici» de `PLA.md` (sense el títol), fins al següent «## »."""
    lines = pla.read_text(encoding="utf-8").splitlines()
    start = next((i for i, ln in enumerate(lines) if re.match(r"^##\s+Judici\b", ln)), None)
    if start is None:
        return None
    end = next((j for j in range(start + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
    return "\n".join(lines[start + 1:end]).strip() or None


def _report(campanya_id: str) -> List[str]:
    """El `.md` i el `.pdf` de `docs/site/report/` (repo de neudet) que contenen l'id de la campanya."""
    try:
        root = neudet_root()
    except DesignError:
        return []
    base = root / "docs" / "site" / "report"
    if not base.is_dir():
        return []
    fs = [f for f in base.iterdir() if f.is_file() and campanya_id in f.name and f.suffix in (".md", ".pdf")]
    fs.sort(key=lambda f: (f.suffix != ".md", f.name))
    return [f.relative_to(root).as_posix() for f in fs]


# ── manifest ────────────────────────────────────────────────────────────────

def _etapa_provisional(d: Path, e: Path) -> Dict[str, Any]:
    """Una etapa de `etapes/*` (amb `candidats.csv`), com la faria neudet (CAMP-2 §6)."""
    motius: List[str] = []
    rt = e / "resultats_tub.json"
    mp = e / "meta.json"
    doc = None
    if rt.is_file():
        try:
            doc = RES.load(rt)
        except RES.ResultsError as exc:
            motius.append(str(exc))
    meta = None
    if mp.is_file():
        try:
            meta = _json(mp)
        except CampanyaError as exc:
            motius.append(str(exc))
    n_csv = len(_csv(e / "candidats.csv")[1])
    if not rt.is_file():
        citable, motius = False, motius + ["no hi ha resultats_tub.json"]
    elif doc is None:
        citable = False
    else:
        pr = RES.provenance(rt)
        citable, motius = pr.citable, motius + list(pr.motius)
    verifica = e.name[:-3] if e.name.endswith("_g4") and (e.parent / e.name[:-3] / "candidats.csv").is_file() else None
    return {"nom": e.name, "dir": _rel(d, e), "motor": _motor(doc, meta),
            "candidats": _rel(d, e / "candidats.csv"),
            "resultats_tub": _rel(d, rt) if rt.is_file() else None,
            "meta": _rel(d, mp) if mp.is_file() else None,
            "figures": _figures(d, e),
            "n_candidats": len(doc["candidats"]) if doc is not None else n_csv,
            "n_csv": n_csv, "citable": citable, "motius": motius, "verifica": verifica}


def manifest_provisional(dir_: PathLike) -> Dict[str, Any]:
    """La mateixa estructura que `campanya_ui.json`, construïda del directori (CAMP-2 §6), amb `provisional`."""
    d = Path(dir_)
    y = _yaml(d / "campanya.yaml")
    etapes_dir = d / "etapes"
    etapes = [_etapa_provisional(d, e) for e in sorted(etapes_dir.iterdir())
              if e.is_dir() and (e / "candidats.csv").is_file()] if etapes_dir.is_dir() else []
    return {
        "provisional": True,
        "motiu": MOTIU_PROVISIONAL,
        "definicio": {"yaml": "campanya.yaml", "md": "DEFINICIO.md" if (d / "DEFINICIO.md").is_file() else None},
        "certificacio": "comprova.json" if (d / "comprova.json").is_file() else None,
        "etapes": etapes,
        "export": "export" if (d / "export").is_dir() else None,
        "judici": _judici(d / "PLA.md") if (d / "PLA.md").is_file() else None,
        "report": _report(d.name),
        "estat": _estat(y),
    }


def _valida_manifest(doc: Dict[str, Any], f: Path) -> None:
    for k in CAMPS_MANIFEST:
        if k not in doc:
            raise CampanyaError(f"{f}: falta el camp «{k}» (CAMP-2 §6)")
    if not isinstance(doc["etapes"], list):
        raise CampanyaError(f"{f}: «etapes» ha de ser una llista")
    for i, e in enumerate(doc["etapes"]):
        if not isinstance(e, dict):
            raise CampanyaError(f"{f}: etapes[{i}] ha de ser un objecte")
        for k in ("nom", "candidats"):
            if k not in e:
                raise CampanyaError(f"{f}: etapes[{i}] no té «{k}»")
    if not isinstance(doc["report"], list) or not all(isinstance(r, str) for r in doc["report"]):
        raise CampanyaError(f"{f}: «report» ha de ser una llista de camins")
    for k in ("certificacio", "export", "judici"):
        if doc[k] is not None and not isinstance(doc[k], str):
            raise CampanyaError(f"{f}: «{k}» ha de ser un text o null")
    if doc["estat"] not in ESTATS:
        raise CampanyaError(f"{f}: «estat» ha de ser {' o '.join(ESTATS)}, no {doc['estat']!r}")


def manifest(dir_: PathLike) -> Dict[str, Any]:
    """El `campanya_ui.json` si hi és (el que escriu neudet, validat i tal qual); si no, el provisional."""
    d = Path(dir_)
    f = d / MANIFEST
    if not f.is_file():
        return manifest_provisional(d)
    doc = _de_6b(_json(f), f)
    _valida_manifest(doc, f)
    return doc


def _de_6b(doc: Dict[str, Any], f: Path) -> Dict[str, Any]:
    """Les claus definitives del manifest (contracte §6b, neudet 711addf) → les de la vista. El fitxer de
    neudet mana; aquí només es tradueix (correspondència escrita al §6b):
    `candidats_csv` → `candidats`, `verificada_per` → `verifica`, `dir` = la carpeta de `candidats_csv`,
    `definicio.{campanya_yaml, definicio}` → `definicio.{yaml, md}`, `report.{md, pdf}` → llista, `flux` es manté."""
    if not isinstance(doc, dict):
        raise CampanyaError(f"{f}: l'arrel ha de ser un objecte")
    out = dict(doc)
    out.setdefault("provisional", False)
    etapes = []
    for i, e in enumerate(doc.get("etapes") or []):
        if not isinstance(e, dict):
            raise CampanyaError(f"{f}: etapes[{i}] ha de ser un objecte")
        e = dict(e)
        if "candidats_csv" in e:
            csv = e.pop("candidats_csv")
            e["candidats"] = csv
            e.setdefault("dir", str(PurePosixPath(csv).parent) if csv else None)
        if "verificada_per" in e:
            e["verifica"] = e.pop("verificada_per")
        fig = e.get("figures")
        if isinstance(fig, str):                          # §6b: la carpeta; la vista vol els fitxers
            fd = f.parent / fig
            e["figures"] = sorted(str(PurePosixPath(fig) / p.name) for p in fd.iterdir()
                                  if p.is_file() and p.suffix.lower() in (".png", ".svg", ".jpg", ".jpeg")) \
                if fd.is_dir() else []
        etapes.append(e)
    out["etapes"] = etapes
    dfn = doc.get("definicio")
    if isinstance(dfn, dict) and "campanya_yaml" in dfn:
        out["definicio"] = {"yaml": dfn.get("campanya_yaml"), "md": dfn.get("definicio")}
    rep = doc.get("report")
    if isinstance(rep, dict):
        out["report"] = [r for r in (rep.get("md"), rep.get("pdf")) if r]
    return out


# ── la vista ────────────────────────────────────────────────────────────────

def _candidats(nom: str, rows: Sequence[Dict[str, str]], doc: Optional[Dict[str, Any]]):
    """Les files del csv (totes les columnes) unides amb el `resultats_tub.json` pel hash."""
    tubs = doc["candidats"] if doc is not None else {}
    avisos: List[str] = []
    out: List[Dict[str, Any]] = []
    vistos = set()
    for r in rows:
        h = (r.get("hash") or "").strip()
        c: Dict[str, Any] = {k: (v if k in _TEXT else _num(v)) for k, v in r.items() if k is not None}
        c["hash"] = h
        jc = tubs.get(h)
        c["amb_tubs"] = jc is not None
        if jc is not None:
            vistos.add(h)
            c["tubs_n"] = len(jc["tubs"])
            for camp in ("pareto_rang", "robusta"):
                if not _iguals(jc[camp], c.get(camp)):
                    avisos.append(f"{nom} · {c.get('nom')}: {camp} del csv ({c.get(camp)}) i del json "
                                  f"({jc[camp]}) no coincideixen; es mostra el del csv")
        out.append(c)
    for h, jc in tubs.items():
        if h in vistos:
            continue
        avisos.append(f"{nom} · {jc['nom']}: al resultats_tub.json però no al candidats.csv")
        out.append({"nom": jc["nom"], "hash": h, "ronda": jc["ronda"], "n": jc["n"],
                    "pareto_rang": jc["pareto_rang"], "robusta": jc["robusta"],
                    "amb_tubs": True, "tubs_n": len(jc["tubs"])})
    return out, avisos


def _certificacio(d: Path, rel: Optional[str]) -> Dict[str, Any]:
    """`comprova.json` com el que `cPintaCert` espera (la forma de `campanya_check`), sense recalcular res."""
    if not rel:
        return {"disponible": False, "motiu": "no hi ha comprova.json a la campanya", "fitxer": None}
    doc = _json(_dins(d, rel, "certificacio"))
    return {"disponible": True, "motiu": "", "fitxer": rel, "atura": doc.get("atura"),
            "draft": doc.get("draft"), "elements": doc.get("elements") or [],
            "camps_falten": doc.get("camps_falten"), "etapes": doc.get("etapes") or {}}


def _eixos(y: Dict[str, Any], columnes: Sequence[str]) -> Tuple[Optional[List[Dict[str, str]]], Optional[str]]:
    """Els dos eixos de Pareto de `objectius.pareto` (`[[metrica, max|min], …]`), o el motiu que no n'hi ha."""
    par = (y.get("objectius") or {}).get("pareto")
    if par is None:
        return None, "campanya.yaml no té objectius.pareto"
    if not (isinstance(par, list) and len(par) == 2 and all(isinstance(p, list) and len(p) == 2 for p in par)):
        raise CampanyaError("campanya.yaml: objectius.pareto ha de ser dos parells [metrica, max|min]")
    eixos = []
    for m, s in par:
        if s not in ("max", "min"):
            raise CampanyaError(f"campanya.yaml: el sentit «{s}» de objectius.pareto no és max ni min")
        if columnes and m not in columnes:
            raise CampanyaError(f"campanya.yaml: la mètrica «{m}» de objectius.pareto no és a cap candidats.csv")
        eixos.append({"metrica": m, "sentit": s})
    if not columnes:       # una proposta sense etapes executades: no hi ha candidats.csv on comprovar-les
        return eixos, "encara no hi ha cap candidats.csv: les mètriques del Pareto no es poden comprovar"
    return eixos, None


def _encaixa_g4(etapes: List[Dict[str, Any]], avisos: List[str]) -> None:
    """Per a cada candidat de la xarxa: les etapes `_g4` que l'han verificat (i el seu ε mitjà)."""
    per_nom = {e["nom"]: e for e in etapes}
    for e in etapes:
        for c in e["candidats"]:
            c["g4"] = []
    for g in etapes:
        t = g.get("verifica")
        if not t:
            continue
        tgt = per_nom.get(t)
        if tgt is None:
            avisos.append(f"{g['nom']} diu que verifica {t}, que no és a la campanya")
            continue
        idx = {c["hash"]: c for c in tgt["candidats"]}
        for cg in g["candidats"]:
            c = idx.get(cg["hash"])
            if c is None:
                avisos.append(f"{g['nom']} · {cg.get('nom')}: verificat a Geant4 però no és a {t}")
                continue
            c["g4"].append({"etapa": g["nom"], "eps_mitja": cg.get("eps_mitja")})


def _etapa_vista(d: Path, e: Dict[str, Any], avisos: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    csvp = _dins(d, e["candidats"], e["nom"])
    if not csvp.is_file():
        raise CampanyaError(f"{e['nom']}: el manifest diu {e['candidats']} i no hi és")
    header, rows = _csv(csvp)
    doc = None
    if e.get("resultats_tub"):
        try:
            doc = RES.load(_dins(d, e["resultats_tub"], e["nom"]))
        except RES.ResultsError as exc:
            avisos.append(f"{e['nom']}: {exc}")
    cands, avs = _candidats(e["nom"], rows, doc)
    avisos.extend(avs)
    fit = {"dir": e.get("dir"), "candidats": e["candidats"], "resultats_tub": e.get("resultats_tub"),
           "meta": e.get("meta")}
    return ({"nom": e["nom"], "motor": e.get("motor"), "verifica": e.get("verifica"),
             "n_candidats": e.get("n_candidats"), "n_csv": e.get("n_csv"), "citable": bool(e.get("citable")),
             "motius": list(e.get("motius") or []), "figures": list(e.get("figures") or []),
             "fitxers": fit, "columnes": header,
             "energies_MeV": list(doc["energies_MeV"]) if doc is not None else None,
             "candidats": cands}, header)


def vista(dir_: PathLike) -> Dict[str, Any]:
    """La campanya com a dades: etapes i candidats (csv ⋈ json pel hash), Pareto, certificació, judici, report."""
    d = Path(dir_)
    m = manifest(d)
    y = _yaml(d / "campanya.yaml")
    avisos: List[str] = []
    avisos.extend(RES.warnings({"campanya": d.name}))
    etapes: List[Dict[str, Any]] = []
    columnes: List[str] = []
    for e in m["etapes"]:
        ev, header = _etapa_vista(d, e, avisos)
        etapes.append(ev)
        columnes.extend(c for c in header if c not in columnes)
    _encaixa_g4(etapes, avisos)
    eixos, motiu_p = _eixos(y, columnes)
    metriques = [x for x in ((y.get("objectius") or {}).get("metriques") or []) if isinstance(x, str)]
    return {
        "id": d.name,
        "provisional": bool(m.get("provisional")),
        "motiu": m.get("motiu"),
        "estat": m["estat"],
        "estat_yaml": None if y.get("estat") is None else str(y.get("estat")),
        "definicio": m["definicio"],
        "certificacio": _certificacio(d, m["certificacio"]),
        "pareto": {"eixos": eixos, "motiu": motiu_p},
        "metriques": metriques,
        "etapes": etapes,
        "judici": m["judici"],
        "report": list(m["report"]),
        "export": m["export"],
        "avisos": avisos,
    }


# ── fitxers que es serveixen ────────────────────────────────────────────────

def _reports(d: Path) -> List[str]:
    return [PurePosixPath(r).as_posix() for r in manifest(d)["report"]]


def fitxer(dir_: PathLike, rel: str) -> Path:
    """El fitxer de la campanya `rel` (relatiu a la carpeta), o un report que el manifest llista (relatiu
    al repo de neudet). Qualsevol altre camí, absolut, amb `..`, fora de la carpeta o d'un tipus no
    servible, és `Prohibit`. No comprova que el fitxer existeixi: això ho diu la ruta (404)."""
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel:
        raise Prohibit(f"camí no vàlid: {rel!r}")
    p = PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts:
        raise Prohibit(f"camí no permès: {rel!r}")
    if p.suffix.lower() not in TIPUS:
        raise Prohibit(f"tipus de fitxer no servible: {rel!r}")
    d = Path(dir_).resolve()
    if p.as_posix() in _reports(d):                  # primer els reports que el manifest llista
        root = neudet_root().resolve()
        rep = (root / p.as_posix()).resolve()
        if rep.is_relative_to(root / "docs" / "site" / "report"):
            return rep
        raise Prohibit(f"el report {rel!r} és fora de docs/site/report de neudet")
    f = (d / p).resolve()                            # després, un fitxer de la carpeta (sense enllaços fora)
    if f.is_relative_to(d) and f.is_file():
        return f
    raise Prohibit(f"fora de la campanya i no és un report que el manifest llisti: {rel!r}")


def tipus_de(f: Path) -> str:
    """El Content-Type d'un fitxer servible (vegeu `TIPUS`)."""
    return TIPUS.get(Path(f).suffix.lower(), "application/octet-stream")
