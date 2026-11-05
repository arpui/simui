"""Les respostes de la consola web: un formulari (o un prompt) → els quatre codis, i els dissenys.

**Què és i què no és.** És una capa PRIMA sobre el que ja fa `gen.py`: la pàgina
omple un `SimRequest`, el servidor el passa per `parse` → `validate` → `render` de
cada backend i en retorna el deck o el rebuig, i `lint_files` per a cada deck. No
executa cap simulació, no escriu cap fitxer i no carrega receptes generades.

El full de disseny de Neudet (`design_*`, `results`) és el mateix patró:
llegeixen els dissenys de neudet (`design_catalog`), els verifiquen i els visualitzen
(`design`, `design_view`), exporten el paquet (`design_export`) i llegeixen els resultats
per tub (`results_tub`). Cap d'aquestes funcions no escriu res fora d'un directori temporal.

**La regla que la manté prima.** Aquest mòdul IMPORTA, no implementa: les opcions
són les tuples de `core.py`, els materials `materials.available()`, els detectors
`detector_config.available()`, les receptes `factory.capabilities()`; el resultat
surt de `factory.retarget()` / `validate()` / `render()`, com a `gen.py`. Si algun
dia cal escriure aquí una línia de física o de format, aquella lògica va a `mcgen/` amb el seu test.
"""
from __future__ import annotations

import json
import tempfile
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..mcgen import core, factory
from ..mcgen import detector_config as D
from ..mcgen import materials as M
from ..mcgen.backends.base import RenderError
from ..mcgen.core import SpecError
from ..mcgen.schema import parse
from ..mcgen import design as DES
from ..mcgen import design_catalog as CAT
from ..mcgen import design_export as EXP
from ..mcgen import design_view as VIEW
from ..mcgen import results_tub as RES
from ..mcgen import campanya_form as CF
from ..mcgen import campanya_check as CC
from ..mcgen import campanya_vista as CV
from ..mcgen import campanya_desa as CD

EXAMPLES = Path(__file__).resolve().parents[1] / "mcgen" / "examples"


# ── el que la pàgina necessita saber ─────────────────────────────────────────

def meta() -> Dict[str, Any]:
    """Vocabularis i catàlegs, llegits d'on ja són. Res escrit a mà aquí."""
    caps = factory.capabilities()
    return {
        "vocab": {
            "backends": list(core.BACKENDS),
            "particles": list(core.PARTICLES),
            "geometry_kinds": list(core.GEOMETRY_KINDS),
            "axes": list(core.AXES),
            "source_kinds": list(core.SOURCE_KINDS),
            "scoring_kinds": list(core.SCORING_KINDS),
            "tally_quantities": list(core.TALLY_QUANTITIES),
            # Els rols NO tenen tupla a `core.py`: el vocabulari que els backends
            # consumeixen és el de `detector_config.ROLE_OF`. Es fa servir com a
            # suggeriment (datalist), no com a llista tancada.
            "roles": sorted(set(D.ROLE_OF.values())),
            "tube_models": list(D.TUBE_MODELS),
        },
        "materials": M.available(),
        "configs": D.available(),
        "recipes": {b: {name: (r.get("description") or "")
                        for name, r in (c.get("recipes") or {}).items()}
                    for b, c in caps.items()},
        "examples": {p.stem: json.loads(p.read_text())
                     for p in sorted(EXAMPLES.glob("*.json"))},
    }


# ── generar: la mateixa seqüència que `gen.py --spec … --backend …` ──────────

def render_one(raw: Dict[str, Any], backend: str) -> Dict[str, Any]:
    """Un spec, un codi. Retorna el deck o el motiu del rebuig, mai una excepció.

    Estats: `ok` (deck escrit), `rejected` (el codi no pot fer aquest cas i ho
    diu), `invalid` (l'spec mateix és incorrecte), `error` (excepció no prevista:
    és un forat de simphy, no de l'spec, i es mostra com a tal).
    """
    out: Dict[str, Any] = {"backend": backend, "status": "", "recipe": None,
                           "note": "", "files": {}, "messages": [], "lint": [],
                           "here": None, "verdict": None}
    # La resposta d'aquest codi a la petició: fet / entorn / cal / límit / spec,
    # i què fer. És el que la pàgina ensenya primer (`agent/assess.py`).
    try:
        from simphy.mcgen.agent.assess import assess
        out["verdict"] = assess(raw, backend).as_dict()
    except Exception as exc:                                  # noqa: BLE001
        out["verdict"] = {"category": "spec", "what": f"{type(exc).__name__}: {exc}",
                          "action": "", "detail": ""}
    try:
        req = parse(json.dumps(raw))
    except SpecError as exc:
        out.update(status="invalid", messages=[str(exc)])
        return out

    try:
        out["note"] = factory.retarget(req, backend)
    except SpecError as exc:
        out.update(status="rejected", recipe=req.legacy_recipe, messages=[str(exc)])
        return out
    out["recipe"] = req.legacy_recipe

    errors = factory.validate(req)
    if errors:
        out.update(status="rejected", messages=list(errors))
        return out
    try:
        files = factory.render(req)
    # RenderError i els ValueError del paquet (SpecError, OpenmcError,
    # ConfigError) són rebuigs amb motiu escrit. KeyError ve de noms lògics
    # (`tallies[].where`) que la geometria no té, i també porta el seu motiu.
    except (RenderError, ValueError) as exc:
        out.update(status="rejected", messages=[str(exc)])
        return out
    except KeyError as exc:
        out.update(status="rejected", messages=[str(exc.args[0] if exc.args else exc)])
        return out
    except Exception as exc:                                  # noqa: BLE001
        out.update(status="error", messages=[f"{type(exc).__name__}: {exc}"])
        return out

    out.update(status="ok", files=files)
    # Tenir deck no vol dir poder-lo córrer: `readiness` munta el pla de
    # `gen.py --run` sense executar-lo i diu què falta en aquesta màquina.
    try:
        from simphy.mcgen import readiness
        out["here"] = readiness.check(req).as_dict()
    except Exception as exc:                                  # noqa: BLE001
        out["here"] = {"status": "blocked", "label": "no s'ha pogut comprovar",
                       "reasons": [f"{type(exc).__name__}: {exc}"], "steps": []}
    try:
        from simphy.mcgen.lint import lint_files
        out["lint"] = [{"level": f.level, "code": f.code, "message": f.message,
                        "line_no": f.line_no, "hint": f.hint}
                       for f in lint_files(files, backend)]
    except Exception as exc:                                  # noqa: BLE001
        out["lint"] = [{"level": "error", "code": "LINT-CRASH",
                        "message": f"{type(exc).__name__}: {exc}",
                        "line_no": None, "hint": ""}]
    return out


def render_all(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [render_one(raw, b) for b in core.BACKENDS]


# ── el prompt: el mateix `generate()` que `gen.py --ask` ─────────────────────

def llm_status(timeout: float = 2.0) -> Dict[str, Any]:
    from simphy.mcgen.agent.llm import LLMError, LocalLLM
    from simphy.mcgen.schema import HAVE_PYDANTIC
    llm = LocalLLM(timeout=timeout)
    try:
        info = llm.ping()
    except LLMError as exc:
        return {"ok": False, "base_url": llm.base_url, "reason": str(exc)}
    return {"ok": True, "base_url": info["base_url"], "models": info["models"],
            "model": info["configurat"], "guided": HAVE_PYDANTIC}


def ask(prompt: str, backend: Optional[str] = None) -> Dict[str, Any]:
    from simphy.mcgen.agent.llm import LLMError, LocalLLM
    from simphy.mcgen.agent.run import generate
    llm = LocalLLM()
    try:
        res = generate(prompt, llm=llm, max_attempts=3,
                       backend_hint=backend or None, render=False)
    except LLMError as exc:
        return {"ok": False, "reason": str(exc), "attempts": 0, "errors": []}
    body: Dict[str, Any] = {"ok": res.ok, "attempts": len(res.attempts),
                            "errors": list(res.errors), "mode": llm.last_mode,
                            "grammar": bool(llm.had_grammar)}
    if res.ok and res.request is not None:
        body["spec"] = json.loads(res.request.to_json())
    elif res.attempts:
        body["raw"] = res.attempts[-1].raw
    return body


# ── disseny (F1) i resultats (F2): la UI IMPORTA de mcgen, no hi calcula res ─────────────
#
# Cada cos porta `design` (el JSON de disseny) i, si ve d'un disseny de neudet, `editat`
# (false = sense tocar: el `.dat`/`.json` originals es donen tal com són), `id` (un
# `design_catalog.defaults()`) o `dat_text`/`json_text` (un parell pujat).

def _cos_original(body: Dict[str, Any], workdir: Path):
    """(dat, json) de l'original si el disseny ve de neudet i no s'ha editat; si no, None."""
    if body.get("editat") is not False:
        return None
    return CAT.original_files(workdir, id_=body.get("id"), dat_text=body.get("dat_text"),
                              json_text=body.get("json_text"))


def design_meta() -> Dict[str, Any]:
    """Els dissenys per defecte, les campanyes i el catàleg de tubs, de neudet i de simphy."""
    out: Dict[str, Any] = {"dissenys": [], "campanyes": [], "tipus_tub": [], "error": None}
    try:
        out["neudet"] = str(DES.neudet_root())
        out["dissenys"] = CAT.defaults()
        out["campanyes"] = CAT.campanyes()
    except DES.DesignError as exc:
        out["error"] = str(exc)
    out["tipus_tub"] = [{"nom": e.get("nom"), "alies": e.get("alies")} for e in D.read_catalog()]
    try:
        out["llm"] = llm_status()
    except Exception as exc:                                  # noqa: BLE001
        out["llm"] = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    return out


def design_load(body: Dict[str, Any]) -> Dict[str, Any]:
    """Un disseny per defecte (`id`) o un parell pujat (`dat_text`, `json_text`), sense editar."""
    if body.get("id"):
        d, e, notes = CAT.carrega(str(body["id"]))
        origen = {"id": e["id"], "nom": e["nom"], "origen": e["origen"], "hash": e["hash"]}
    elif body.get("dat_text"):
        d, notes = CAT.carrega_text(str(body["dat_text"]), body.get("json_text"))
        origen = {"id": None, "nom": d.nom, "origen": "pujat", "hash": None}
    else:
        raise ValueError("cal un `id` de disseny per defecte o un `dat_text`")
    return {"design": d.to_dict(), "editat": False, "origen": origen, "notes": notes}


def design_check(body: Dict[str, Any]) -> Dict[str, Any]:
    """Les violacions del disseny (les de neudet, amb les restriccions de la campanya), i el
    nom i el hash que tindria. Si no hi ha restriccions, ho diu: no es mostra com a vàlid."""
    d = DES.load(body["design"])
    orig = body.get("editat") is False
    with warnings.catch_warnings():
        # un disseny de neudet sense editar té el nom de neudet al .json; el regenerat el
        # reanomena (r4_t0 → 1x4). Aquí es mostra el de l'original, no cal el avís.
        warnings.simplefilter("ignore", UserWarning)
        if orig and (body.get("id") or body.get("dat_text")):
            nom, hash_ = CAT.identitat(body.get("id"), body.get("json_text"))
        else:
            c = DES.to_candidat(d)
            nom, hash_ = c.nom, c.hash()
        try:
            viol, motiu, verificat = DES.violations(d), "", True
        except DES.DesignError as exc:
            viol, motiu, verificat = [], str(exc), False
    return {"verificat": verificat, "violations": viol, "motiu": motiu,
            "nom": nom, "hash": hash_, "editat": not orig}


def design_view(body: Dict[str, Any]) -> Dict[str, Any]:
    """El visor (XY i XZ, taula, notes) com a dades. L'original de neudet es llegeix tal com és."""
    d = DES.load(body["design"])
    with tempfile.TemporaryDirectory() as tmp, warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return EXP.preview(d, original=_cos_original(body, Path(tmp) / "original"))


def design_export(body: Dict[str, Any]):
    """El paquet zip d'un disseny: visor, config, decks i README. Retorna (bytes, nom)."""
    d = DES.load(body["design"])
    energia = body.get("energia_mev")
    campanya = body.get("campanya") or None
    with tempfile.TemporaryDirectory() as tmp, warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        orig = _cos_original(body, Path(tmp) / "original")
        return EXP.bundle(d, Path(tmp), energia_mev=None if energia in (None, "") else energia,
                          campanya=campanya, original=orig)


def design_ask(body: Dict[str, Any]) -> Dict[str, Any]:
    """Un disseny a partir de text, amb el model local (`design_prompt.generate`, verificat)."""
    from simphy.mcgen.agent import design_prompt as P
    from simphy.mcgen.agent.llm import LLMError, LocalLLM
    text = str(body.get("prompt") or "").strip()
    if not text:
        raise ValueError("el prompt és buit")
    try:
        res = P.generate(text, LocalLLM(), campanya=body.get("campanya") or None, max_attempts=3)
    except LLMError as exc:
        return {"ok": False, "reason": str(exc), "attempts": 0, "errors": []}
    out: Dict[str, Any] = {"ok": res.ok, "attempts": len(res.attempts), "errors": list(res.errors)}
    if res.ok and res.design is not None:
        out["design"] = res.design.to_dict()
    return out


def results(hash_: str, stage: Optional[str] = None, energia: Optional[str] = None) -> Dict[str, Any]:
    """Les etapes de neudet amb aquest hash i el seu resultat per tub (totes les energies).

    Amb `energia` (MeV), a més, el visor XY de l'etapa (`stage`, o la primera amb dades) pintat
    per ε a aquella energia, i la `comparativa` per tub entre motors (`results_tub.comparativa`).
    Un hash sense cap etapa dona `entries: []`: no és un error.
    """
    entries = RES.for_design(hash_)
    out: Dict[str, Any] = {"hash": hash_, "entries": entries, "vista": None, "comparativa": None}
    if energia not in (None, ""):
        # la taula per tub entre motors (neudet i simphy): lectura i quocient, sense física
        out["comparativa"] = RES.comparativa(entries, float(energia))
        e = next((x for x in entries if x["status"] == RES.OK
                  and (stage is None or x["path"] == stage)), None)
        dat = CAT.per_hash(hash_)
        if e is not None and dat is not None:
            k = RES.index_of_energy(e["energies_MeV"], float(energia))
            out["vista"] = VIEW.preview(dat, valors_tubs=e["tubs"], camp="eps", k=k, unitat="ε")
            out["vista"]["stage"] = e["path"]
    return out


# ── HTTP ─────────────────────────────────────────────────────────────────────


# ── Definició de campanya (C1, C2): el formulari i la comprovació de neudet ──

def campanya_schema() -> Dict[str, Any]:
    """Els tipus de generador, els camps i els tubs (de neudet) per al formulari."""
    return CF.schema()


def campanya_defaults() -> Dict[str, Any]:
    """El `campanya.yaml` de c04_draft, tal com és a neudet."""
    return CF.defaults()


def campanya_yaml(body: Dict[str, Any]) -> Dict[str, Any]:
    """El yaml del formulari, en viu i per a «Descarrega»: no escriu res. Desar és `campanya_desa` (a neudet)."""
    if body.get("desa"):
        raise ValueError("desar una proposta és POST /api/campanya/desa (es desa a neudet, amb la certificació)")
    return {"yaml": CF.to_yaml(body.get("form"))}


def campanya_desa(body: Dict[str, Any]) -> Dict[str, Any]:
    """«Desa la proposta»: `campanya.yaml` (estat: proposta) i `comprova.json` a `disseny/campanyes/<id>/` de neudet.
    Vegeu `campanya_desa.desa_proposta`: només aquests dos fitxers, i mai una campanya que no sigui proposta."""
    return CD.desa_proposta(body.get("form"))


def campanya_confirma(body: Dict[str, Any]) -> Dict[str, Any]:
    """«Confirmar i congelar» una campanya `interpretada` (neudet escriu la confirmació; vegeu `campanya_desa.confirma_campanya`)."""
    return CD.confirma_campanya(body.get("id"), body.get("per"))


def campanya_tanteig(body: Dict[str, Any]) -> Dict[str, Any]:
    """«Tanteja»: el formulari d'una campanya (`de`) amb un id derivat lliure; o, amb `hash`, el candidat d'aquella
    campanya com a etapa `llista` (`etapa` opcional). No escriu res."""
    de = str(body.get("de") or "")
    if not de:
        raise ValueError("cal `de`: l'id de la campanya a tantejar")
    if body.get("hash"):
        return CD.tanteig_de_candidat(de, str(body["hash"]), body.get("etapa") or None)
    return CD.tanteig_de_campanya(de)


def campanya_comprova(body: Dict[str, Any]) -> Dict[str, Any]:
    """La comprovació de neudet del yaml (`yaml_text`, i `etapa` opcional). Vegeu `campanya_check`."""
    return CC.comprova(str(body.get("yaml_text") or ""), body.get("etapa") or None)


def campanya_compta(body: Dict[str, Any]) -> Dict[str, Any]:
    """Quants candidats genera la regla d'una etapa del formulari (`form`, `etapa`), abans de les
    restriccions. La forma la valida `to_yaml` (400 amb el motiu); el recompte i els errors són de neudet."""
    text = CF.to_yaml(body.get("form"))
    return CC.compta(text, body.get("etapa") or None)


# ── Campanyes (contracte §6, CAMP-2): la campanya com a conjunt, des de neudet ──

def campanyes() -> Dict[str, Any]:
    """Les campanyes de neudet (`disseny/campanyes/*/campanya.yaml`), amb estat i si tenen manifest."""
    return {"campanyes": CV.llista()}


def campanya_vista(id_: str) -> Dict[str, Any]:
    """La campanya com a dades: etapes, candidats, Pareto, certificació, judici i report (`campanya_vista.vista`).
    Sense `campanya_ui.json` és provisional, i ho diu."""
    return CV.vista(CV.dir_de(id_))


def campanya_carrega(id_: str) -> Dict[str, Any]:
    """El `campanya.yaml` de neudet com a formulari, per obrir-lo a la pestanya Campanya. No escriu res."""
    d = CV.dir_de(id_)
    cert = CV._certificacio(d, "comprova.json" if (d / "comprova.json").is_file() else None)
    return {"id": id_, "form": CF.de_fitxer(d / "campanya.yaml"),
            "resum_text": cert.get("resum_text"), "confirmacio": cert.get("confirmacio")}     # CONF-P: el que neudet entén que farà


def campanya_candidat(id_: str, hash_: str, etapa: Optional[str] = None) -> Dict[str, Any]:
    """El `.dat`/`.json` d'un candidat de la campanya `id_` (generat per neudet, `Candidat.to_dat`), perquè el
    full del disseny en mostri el visor i els inputs dels quatre codis. No escriu res."""
    return CC.dat_de_candidat(CV.dir_de(id_), hash_, etapa)


def campanya_fitxer(id_: str, rel: str) -> Path:
    """El fitxer `rel` de la campanya `id_` (o un report que llista el manifest). Un id que no és cap campanya és
    un 403: no hi ha res a servir fora de `disseny/campanyes/`."""
    try:
        d = CV.dir_de(id_)
    except CV.CampanyaError as exc:
        raise CV.Prohibit(str(exc)) from exc
    return CV.fitxer(d, rel)
