"""Les respostes de la consola web: un formulari (o un prompt) → els quatre codis.

**Què és i què no és.** És una capa PRIMA sobre el que ja fa `gen.py`: la pàgina
omple un `SimRequest`, el servidor el passa per `parse` → `validate` → `render` de
cada backend i en retorna el deck o el rebuig, i `lint_files` per a cada deck. No
executa cap simulació, no escriu cap fitxer i no carrega receptes generades.

**La regla que la manté prima.** Aquest mòdul IMPORTA, no implementa: les opcions
són les tuples de `core.py`, els materials `materials.available()`, els detectors
`detector_config.available()`, les receptes `factory.capabilities()`; el resultat
surt de `factory.retarget()` / `validate()` / `render()`, com a `gen.py`. Si algun
dia cal escriure aquí una línia de física, aquella lògica va a `mcgen/` amb el seu test.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..mcgen import core, factory
from ..mcgen import detector_config as D
from ..mcgen import materials as M
from ..mcgen.backends.base import RenderError
from ..mcgen.core import SpecError
from ..mcgen.schema import parse

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


# ── HTTP ─────────────────────────────────────────────────────────────────────
