#!/usr/bin/env python3
"""serve.py — consola web de simphy: un formulari (o un prompt) → els quatre codis.

    python scripts/ui/serve.py                 # http://127.0.0.1:8765
    python scripts/ui/serve.py --port 9000

**Què és i què no és.** És una capa PRIMA sobre el que ja fa `gen.py`: la pàgina
omple un `SimRequest`, el servidor el passa per `parse` → `validate` → `render` de
cada backend i en retorna el deck o el rebuig, i `lint_files` per a cada deck. No
executa cap simulació, no escriu cap fitxer i no carrega receptes generades (això
voldria dir executar codi d'un model dins del servidor).

**La regla que la manté prima.** Aquest fitxer IMPORTA, no implementa:

  · les opcions dels desplegables són les tuples de `core.py` (`PARTICLES`,
    `GEOMETRY_KINDS`…), els materials els dona `materials.available()`, els
    detectors `detector_config.available()`, les receptes `factory.capabilities()`;
  · el resultat surt de `factory.validate()` / `factory.render()`, com a `gen.py`.

Si algun dia cal escriure aquí una línia de física, és el senyal que ha crescut
malament: aquella lògica va a `src/` amb el seu test.

**Sense dependències.** `http.server` de la stdlib, com el camí determinista del
paquet (`pyproject.toml`: cap dependència obligatòria). El prompt parla amb el
model local per `agent.llm.LocalLLM`, que també és stdlib (`urllib`); amb
`pydantic` instal·lat hi ha decodificació guiada, sense, el model va a cegues i
l'agent ho diu.

**Una sola regla per canviar de codi.** Portar un spec a un altre backend
(buscar la recepta del mateix cas: mateix nom o mateixa `family`) és
`factory.retarget()`, la mateixa funció que fa servir el `--backend` de `gen.py`.
`tests/test_ui_serve.py` segueix comprovant, exemple per exemple i codi per codi,
que la pàgina i `gen.py` donen el mateix resultat.
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from simphy.mcgen import core, factory                       # noqa: E402
from simphy.mcgen import detector_config as D                # noqa: E402
from simphy.mcgen import materials as M                      # noqa: E402
from simphy.mcgen.backends.base import RenderError           # noqa: E402
from simphy.mcgen.core import SpecError                      # noqa: E402
from simphy.mcgen.schema import parse                        # noqa: E402

EXAMPLES = ROOT / "src" / "simphy" / "mcgen" / "examples"


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

class Handler(BaseHTTPRequestHandler):
    server_version = "simphy-ui"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def _body(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self) -> None:                                  # noqa: N802
        # La query (`/?ex=un_perp_detector`) la llegeix la pàgina, no el servidor.
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/api/meta":
            self._json(meta())
        elif path == "/api/llm":
            self._json(llm_status())
        else:
            self._json({"error": f"no hi ha {path}"}, 404)

    def do_POST(self) -> None:                                 # noqa: N802
        try:
            body = self._body()
        except json.JSONDecodeError as exc:
            self._json({"error": f"el cos no és JSON: {exc}"}, 400)
            return
        path = urlsplit(self.path).path
        if path == "/api/render":
            self._json({"results": render_all(body.get("spec") or {})})
        elif path == "/api/ask":
            self._json(ask(str(body.get("prompt") or ""), body.get("backend")))
        else:
            self._json({"error": f"no hi ha {path}"}, 404)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[ui] {self.address_string()} {fmt % args}\n")


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def main(argv=None) -> int:
    from simphy.mcgen.paths import load_env
    load_env()                  # MCGEN_LLM_* del `.env`, com `gen.py`
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1",
                    help="per defecte només aquesta màquina")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    srv = make_server(args.host, args.port)
    print(f"[ui] simphy a http://{args.host}:{srv.server_address[1]}  (Ctrl+C per aturar)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


# ── la pàgina ────────────────────────────────────────────────────────────────
# Un sol fitxer a posta: res a construir, res a instal·lar. Els colors i la
# tipografia són els de `docs/site/presentacio/theme.css`, perquè les captures
# encaixin a la presentació.

PAGE = r"""<!doctype html>
<html lang="ca"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>simphy · consola</title>
<style>
:root{--ink:#16191d;--muted:#5f6a75;--line:#ddd9d2;--bg:#fdfcfa;--accent:#2b6b86;
--warn:#9a6a1e;--bad:#9c3a2e;--good:#2c6b4c;--panel:#f4f1ec}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.45 "DejaVu Sans","Liberation Sans",Arial,Helvetica,sans-serif}
code,pre,textarea.json{font-family:"DejaVu Sans Mono","Liberation Mono",Consolas,monospace}
header.top{padding:18px 28px 14px;border-bottom:1px solid var(--line);display:flex;
align-items:baseline;gap:18px;flex-wrap:wrap}
header.top h1{margin:0;font-size:22px;letter-spacing:-.01em}
header.top .kick{font-size:11px;letter-spacing:.13em;text-transform:uppercase;
color:var(--accent);font-weight:700}
header.top .sub{color:var(--muted);font-size:13px}
main{display:grid;grid-template-columns:minmax(330px,420px) 1fr;gap:0;min-height:calc(100vh - 62px)}
@media (max-width:900px){main{grid-template-columns:1fr}}
aside{border-right:1px solid var(--line);padding:18px 22px 40px;overflow:auto}
section.out{padding:18px 24px 40px;min-width:0}
h2{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);
margin:20px 0 8px;font-weight:700}
h2:first-child{margin-top:0}
label{display:block;font-size:12px;color:var(--muted);margin:8px 0 3px}
input,select,textarea{width:100%;font:inherit;padding:6px 8px;border:1px solid var(--line);
border-radius:4px;background:#fff;color:var(--ink)}
input:focus,select:focus,textarea:focus{outline:2px solid #2b6b8633;border-color:var(--accent)}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
.mat{display:grid;grid-template-columns:1.1fr 1fr .8fr 26px;gap:6px;margin-bottom:6px}
.mat input,.mat select{padding:5px 6px}
button{font:inherit;border:1px solid var(--accent);background:var(--accent);color:#fff;
padding:7px 14px;border-radius:4px;cursor:pointer;font-weight:700}
button.ghost{background:#fff;color:var(--accent)}
button.x{background:none;border:none;color:var(--muted);padding:0;font-size:16px;font-weight:400}
button:disabled{opacity:.45;cursor:not-allowed}
.hint{font-size:11.5px;color:var(--muted);margin-top:4px}
.panel{background:var(--panel);border-left:3px solid var(--accent);padding:10px 12px;
font-size:13px;margin:8px 0}
.panel.warn{border-left-color:var(--warn)}
textarea.json{min-height:220px;font-size:12px;line-height:1.35;white-space:pre}
textarea.prompt{min-height:62px}
.err{color:var(--bad);font-size:12px;margin-top:4px}
details summary{cursor:pointer;color:var(--accent);font-size:12.5px;margin-top:14px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;align-items:start}
@media (max-width:1300px){.grid{grid-template-columns:1fr}}
article.card{border:1px solid var(--line);border-radius:6px;background:#fff;min-width:0;
display:flex;flex-direction:column}
article.card>header{display:flex;align-items:center;gap:10px;padding:10px 14px;
border-bottom:1px solid var(--line)}
article.card h3{margin:0;font-size:15px}
.meta{color:var(--muted);font-size:12px;margin-left:auto;text-align:right}
.msgs{margin:0;padding:10px 14px 0 30px;font-size:12.5px}
.note-r{margin:10px 14px 0;padding:6px 10px;background:var(--panel);border-left:3px solid var(--accent);font-size:12.5px}
.msgs li{margin-bottom:6px}
.here{margin:10px 14px 0;font-size:12.5px;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.here code{font-size:11.5px;background:#f7f6f3;padding:2px 6px;border-radius:3px;word-break:break-all}
.here .why{color:var(--muted)}
.lint{padding:8px 14px 0;font-size:12px;color:var(--muted)}
.lint .f{margin:3px 0}.lint code{font-size:11.5px}
.tabs{display:flex;gap:4px;padding:10px 14px 0;flex-wrap:wrap}
.tabs button{background:#fff;color:var(--muted);border:1px solid var(--line);
padding:3px 9px;font-size:12px;font-weight:400}
.tabs button.on{color:var(--accent);border-color:var(--accent)}
pre.deck{margin:10px 14px 14px;padding:10px 12px;background:#f7f6f3;border:1px solid var(--line);
border-radius:4px;font-size:11.5px;line-height:1.4;overflow:auto;max-height:340px;white-space:pre}
.tag{display:inline-block;font-size:11.5px;font-weight:700;padding:2px 8px;border-radius:4px;white-space:nowrap}
.t-ok{background:#e2efe7;color:var(--good)}.t-wa{background:#f6ecd9;color:var(--warn)}
.t-no{background:#f4e2df;color:var(--bad)}.t-nt{background:var(--panel);color:var(--muted)}
.bar{display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.bar .note{color:var(--muted);font-size:12.5px}
.empty{color:var(--muted);padding:40px 0}
</style></head><body>

<header class="top">
  <span class="kick">simphy</span>
  <h1>Una petició, quatre codis</h1>
  <span class="sub">Genera els fitxers d'entrada de FLUKA, MCNP, OpenMC i Geant4 des d'un mateix spec. No executa cap simulació.</span>
</header>

<main>
<aside>
  <h2>Demana-ho en text</h2>
  <textarea class="prompt" id="prompt" placeholder="p.ex. esfera de PE de 30 cm amb 1e5 neutrons de 2,5 MeV"></textarea>
  <div class="bar" style="margin:8px 0 0">
    <button id="askBtn" class="ghost" disabled>Proposa l'spec</button>
    <span class="note" id="llmNote">comprovant el model local…</span>
  </div>

  <h2>O parteix d'un exemple</h2>
  <select id="example"></select>

  <h2>Font</h2>
  <div class="row">
    <div><label>partícula</label><select data-path="source.particle" data-vocab="particles"></select></div>
    <div><label>tipus</label><select data-path="source.kind" data-vocab="source_kinds"></select></div>
  </div>
  <div class="row">
    <div><label>energia (MeV) <span class="hint">· només amb «mono»</span></label><input data-path="source.energy_mev" data-kind="num"></div>
    <div><label>posició (cm) <span class="hint">· x, y, z</span></label><input data-path="source.position_cm" data-kind="vec" placeholder="0, 0, 0"></div>
  </div>
  <label>direcció <span class="hint">· buit = isòtropa</span></label>
  <input data-path="source.direction" data-kind="vec" placeholder="isòtropa">

  <h2>Geometria</h2>
  <div class="row">
    <div><label>tipus</label><select data-path="geometry.kind" data-vocab="geometry_kinds"></select></div>
    <div id="cfgBox"><label>detector (<code>.dat</code>)</label><select data-path="geometry.config" data-vocab="configs"></select></div>
  </div>
  <div class="row3">
    <div><label>radi (cm)</label><input data-path="geometry.radius_cm" data-kind="num"></div>
    <div><label>llargada (cm)</label><input data-path="geometry.length_cm" data-kind="num"></div>
    <div><label>eix</label><select data-path="geometry.axis" data-vocab="axes"></select></div>
  </div>
  <div class="row">
    <div><label>caixa: arestes (cm)</label><input data-path="geometry.size_cm" data-kind="vec" placeholder="x, y, z"></div>
    <div><label>radi del món (cm)</label><input data-path="geometry.world_radius_cm" data-kind="num"></div>
  </div>

  <h2>Materials</h2>
  <div id="mats"></div>
  <button class="ghost" id="addMat" style="padding:4px 10px;font-size:12px">+ material</button>
  <div class="hint">El material es tria pel seu <b>rol</b>, no per l'ordre. Densitat buida = la de la taula (o la del comptador, pel gas).</div>
  <datalist id="rolesList"></datalist>

  <h2>Mesura i tanda</h2>
  <div class="row">
    <div><label>bolcat / puntuació</label><select data-path="scoring.kind" data-vocab="scoring_kinds"></select></div>
    <div><label>recepta</label><input data-path="legacy_recipe" list="recipesList" placeholder="la del backend"></div>
  </div>
  <datalist id="recipesList"></datalist>
  <div class="row">
    <div><label>primàries</label><input data-path="run.n_primaries" data-kind="int"></div>
    <div><label>llavor</label><input data-path="run.seed" data-kind="int"></div>
  </div>
  <div id="tubeBox" class="row">
    <div><label>model de tub</label><select data-path="legacy_params.tube_model" data-vocab="tube_models"></select></div>
    <div><label>eix del tub</label><select data-path="legacy_params.tube_axis" data-vocab="axes"></select></div>
  </div>

  <details id="jsonBox"><summary>Spec JSON complet (mana sobre el formulari)</summary>
    <textarea class="json" id="json" spellcheck="false"></textarea>
    <div class="err" id="jsonErr"></div>
    <div class="hint">Els <code>tallies</code> i la resta de camps s'editen aquí. El formulari en toca només una part i conserva la resta.</div>
  </details>

  <div class="bar" style="margin-top:18px">
    <button id="go">Genera als quatre codis</button>
  </div>
</aside>

<section class="out">
  <div class="bar"><span class="note" id="status"></span></div>
  <div class="grid" id="results"><div class="empty">Tria un exemple o omple el formulari.</div></div>
</section>
</main>

<script>
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
let META = null, SPEC = {};
const NAMES = {fluka:"FLUKA", mcnp:"MCNP", openmc:"OpenMC", geant4:"Geant4"};
const STATUS = {ok:["escrit","t-ok"], rejected:["rebutjat","t-no"],
                invalid:["spec invàlid","t-wa"], error:["error intern","t-wa"]};

function getP(o,p){return p.split('.').reduce((a,k)=>a==null?undefined:a[k],o)}
function setP(o,p,v){
  const ks=p.split('.'), chain=[o]; let a=o;
  for(let i=0;i<ks.length-1;i++){
    if(a[ks[i]]==null||typeof a[ks[i]]!=='object') a[ks[i]]={};
    a=a[ks[i]]; chain.push(a);
  }
  const k=ks[ks.length-1];
  if(v===undefined) delete a[k]; else a[k]=v;
  // Un objecte que queda buit se'n va, de baix a dalt: així actuen els
  // defectes de l'esquema en comptes d'un `{}` que diu una altra cosa.
  for(let i=ks.length-2;i>=0;i--){
    const obj=chain[i][ks[i]];
    if(obj&&typeof obj==='object'&&!Array.isArray(obj)&&!Object.keys(obj).length) delete chain[i][ks[i]];
    else break;
  }
}
const esc = s => String(s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

function fillSelect(sel, values, withDefault=true){
  sel.innerHTML = (withDefault?'<option value="">— (per defecte)</option>':'') +
    values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');
}
function readField(el){
  const v = el.value.trim(), k = el.dataset.kind;
  if(v==="") return undefined;
  if(k==="num"){const n=Number(v.replace(',','.'));return isNaN(n)?v:n}
  if(k==="int"){const n=parseInt(v,10);return isNaN(n)?v:n}
  if(k==="vec") return v.split(/[\s;,]+/).filter(Boolean).map(x=>Number(x));
  return v;
}
function writeField(el,v){
  if(v===undefined||v===null){el.value="";return}
  el.value = Array.isArray(v) ? v.join(', ') : String(v);
}

function syncForm(){
  $$('[data-path]').forEach(el=>writeField(el,getP(SPEC,el.dataset.path)));
  const mats = $('#mats'); mats.innerHTML = '';
  (SPEC.materials||[]).forEach((m,i)=>mats.appendChild(matRow(m,i)));
  const kind = getP(SPEC,'geometry.kind');
  $('#cfgBox').style.opacity = kind==='config' ? 1 : .45;
  $('#tubeBox').style.display = SPEC.legacy_recipe==='un_perp_beam' ? '' : 'none';
  $('#json').value = JSON.stringify(SPEC,null,2); $('#jsonErr').textContent='';
}
function matRow(m,i){
  const d = document.createElement('div'); d.className='mat';
  d.innerHTML = `<select>${META.materials.map(n=>`<option ${n===m.name?'selected':''}>${esc(n)}</option>`).join('')}
    ${META.materials.includes(m.name)?'':`<option selected>${esc(m.name||'')}</option>`}</select>
    <input list="rolesList" placeholder="rol" value="${esc(m.role||'')}">
    <input placeholder="g/cm³" value="${m.density_g_cm3??''}">
    <button class="x" title="treu">×</button>`;
  const [s,r,dn] = d.querySelectorAll('select,input');
  const upd = ()=>{const o=SPEC.materials[i]; o.name=s.value; o.role=r.value||undefined;
    const x=dn.value.trim(); if(x==="") delete o.density_g_cm3; else o.density_g_cm3=Number(x.replace(',','.'));
    if(!o.role) delete o.role; syncJson()};
  s.onchange=upd; r.oninput=upd; dn.oninput=upd;
  d.querySelector('button').onclick=()=>{SPEC.materials.splice(i,1);syncForm()};
  return d;
}
function syncJson(){$('#json').value = JSON.stringify(SPEC,null,2)}

function onField(e){
  const el=e.target; if(!el.dataset.path) return;
  setP(SPEC, el.dataset.path, readField(el));
  if(el.dataset.path==='geometry.kind'||el.dataset.path==='legacy_recipe') syncForm(); else syncJson();
}

async function render(){
  $('#go').disabled=true; $('#status').textContent='generant…';
  const t0=performance.now();
  const r = await fetch('/api/render',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({spec:SPEC})}).then(x=>x.json());
  const ms=Math.round(performance.now()-t0);
  const n = r.results.filter(x=>x.status==='ok').length;
  const cnt={}; r.results.forEach(x=>{const c=(x.verdict||{}).category||'?'; cnt[c]=(cnt[c]||0)+1});
  const resum=Object.entries(cnt).map(([c,k])=>`${k} ${esc(c)}`).join(' · ');
  $('#status').innerHTML = `<b>${n} de 4</b> codis han escrit el deck · resposta dels codis: <b>${resum}</b> · ${ms} ms · spec «${esc(SPEC.name||'sim')}»`;
  $('#results').innerHTML=''; r.results.forEach(x=>$('#results').appendChild(card(x)));
  $('#go').disabled=false;
}
// El mateix avís a cinc línies és UNA troballa: s'agrupa per codi i es diuen les línies.
function lintHtml(lint){
  const g = new Map();
  lint.filter(f=>f.level!=='info').forEach(f=>{
    const k=f.level+'|'+f.code+'|'+f.message;
    if(!g.has(k)) g.set(k,{...f,lines:[]});
    if(f.line_no) g.get(k).lines.push(f.line_no);
  });
  if(!g.size) return '';
  return `<div class="lint">${[...g.values()].map(f=>`<div class="f"><span class="tag ${f.level==='error'?'t-no':'t-wa'}">${esc(f.code)}</span>
    ${f.lines.length>1?`<b>×${f.lines.length}</b> `:''}${esc(f.message)}${f.lines.length?` <code>l. ${f.lines.join(', ')}</code>`:''}</div>`).join('')}</div>`;
}
// La resposta del codi: fet / entorn / cal / límit / spec, i què fer
// (`agent/assess.py`). Tenir deck ≠ poder-lo córrer, i no tenir-ne ≠ impossible.
const VERDICT={'fet':['fet','t-ok'],'entorn':['entorn: falta aquí','t-wa'],
  'cal':['cal desenvolupar','t-wa'],'límit':['límit del codi','t-no'],'spec':['a la petició li falta','t-no']};
function hereHtml(x){
  const v=x.verdict; if(!v) return '';
  const [lab,cls]=VERDICT[v.category]||[v.category,'t-nt'];
  let act='';
  if(v.category==='fet'){
    const ex=$('#example').value, same=ex&&JSON.stringify(SPEC)===JSON.stringify(META.examples[ex]);
    const spec=same?`src/simphy/mcgen/examples/${ex}.json`:'EL_TEU_SPEC.json';
    act=`<code>python scripts/mcgen/gen.py --spec ${esc(spec)} --backend ${x.backend} --run -o tmp/${esc(SPEC.name||'sim')}_${x.backend}</code>`+
      (same?'':'<span class="why">(desa abans el JSON de l\'esquerra)</span>');
  } else if(v.action){ act=v.action.startsWith('python ')?`<code>${esc(v.action)}</code>`:`<span class="why">→ ${esc(v.action)}</span>`; }
  return `<div class="here"><span class="tag ${cls}">${esc(lab)}</span><span>${esc(v.what)}</span>${act}</div>`;
}
function card(x){
  const a=document.createElement('article'); a.className='card';
  const [lab,cls]=STATUS[x.status]||[x.status,'t-nt'];
  const files=Object.keys(x.files||{});
  const lines=files.reduce((s,f)=>s+x.files[f].split('\n').length-1,0);
  const nE=(x.lint||[]).filter(f=>f.level==='error').length, nW=(x.lint||[]).filter(f=>f.level==='warning').length;
  const meta=[x.recipe?`recepta <code>${esc(x.recipe)}</code>`:'recepta per defecte',
              files.length?`${lines} línies`:'', x.status==='ok'?`lint ${nE} E · ${nW} W`:''].filter(Boolean).join(' · ');
  a.innerHTML=`<header><h3>${NAMES[x.backend]||x.backend}</h3><span class="tag ${cls}">${lab}</span>
    <span class="meta">${meta}</span></header>
    ${x.note?`<div class="note-r">↪ ${esc(x.note)}</div>`:''}
    ${hereHtml(x)}
    ${x.messages.length?`<ul class="msgs">${x.messages.map(m=>`<li>${esc(m)}</li>`).join('')}</ul>`:''}
    ${lintHtml(x.lint||[])}
    ${files.length>1?`<div class="tabs">${files.map((f,i)=>`<button class="${i?'':'on'}" data-f="${esc(f)}">${esc(f)}</button>`).join('')}</div>`:''}
    ${files.length?`<pre class="deck">${esc(x.files[files[0]])}</pre>`:''}`;
  a.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{
    a.querySelectorAll('.tabs button').forEach(z=>z.classList.remove('on')); b.classList.add('on');
    a.querySelector('pre.deck').textContent=x.files[b.dataset.f]});
  return a;
}

async function ask(){
  const p=$('#prompt').value.trim(); if(!p) return;
  $('#askBtn').disabled=true; $('#llmNote').textContent='demanant al model… (pot trigar)';
  const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({prompt:p})}).then(x=>x.json());
  $('#askBtn').disabled=false;
  if(r.ok){SPEC=r.spec; syncForm();
    $('#llmNote').textContent=`spec proposat en ${r.attempts} intent(s)`+(r.grammar?'':' · ⚠ sense gramàtica: ha encertat pel prompt, no per construcció');
    render();}
  else{$('#llmNote').innerHTML=`<span class="err">no ha convergit (${r.attempts} intents)${r.reason?': '+esc(r.reason):''}</span>`+
    (r.errors&&r.errors.length?'<ul class="msgs">'+r.errors.map(e=>`<li>${esc(e)}</li>`).join('')+'</ul>':'');}
}

async function boot(){
  META = await fetch('/api/meta').then(r=>r.json());
  $$('[data-vocab]').forEach(s=>{const k=s.dataset.vocab; fillSelect(s, k==='configs'?META.configs:META.vocab[k])});
  $('#rolesList').innerHTML = META.vocab.roles.map(r=>`<option value="${r}">`).join('');
  const recs=[]; for(const [b,rs] of Object.entries(META.recipes)) for(const [n,d] of Object.entries(rs)) recs.push([n,b,d]);
  $('#recipesList').innerHTML = recs.map(([n,b,d])=>`<option value="${esc(n)}">${esc(b)} — ${esc(d.slice(0,90))}</option>`).join('');
  const ex=$('#example'); ex.innerHTML='<option value="">—</option>'+Object.keys(META.examples).map(k=>`<option>${k}</option>`).join('');
  ex.onchange=()=>{if(!ex.value)return; SPEC=structuredClone(META.examples[ex.value]); syncForm(); render()};
  document.addEventListener('input',onField); document.addEventListener('change',onField);
  $('#addMat').onclick=()=>{(SPEC.materials=SPEC.materials||[]).push({name:META.materials[0],role:'bulk'});syncForm()};
  $('#json').addEventListener('input',()=>{try{SPEC=JSON.parse($('#json').value);$('#jsonErr').textContent='';
    const keep=$('#json').value; syncForm(); $('#json').value=keep}catch(e){$('#jsonErr').textContent='JSON invàlid: '+e.message}});
  $('#go').onclick=render; $('#askBtn').onclick=ask;
  const first = new URLSearchParams(location.search).get('ex') || 'un_perp_detector';
  if(META.examples[first]){ex.value=first; SPEC=structuredClone(META.examples[first]); syncForm(); render()}
  fetch('/api/llm').then(r=>r.json()).then(s=>{
    if(s.ok){$('#askBtn').disabled=false; $('#llmNote').textContent=`model local: ${s.model} a ${s.base_url}`+(s.guided?'':' · sense pydantic, sense gramàtica')}
    else $('#llmNote').textContent='model local no disponible — el formulari funciona igual';
  });
}
boot();
</script>
</body></html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
