"""test_inventari_tubs_ui.py — INVENTARI-UI (encàrrec del coordinador 2026-11-25): pestanya de només lectura.

Què es fixa
-----------
- **El que es llegeix és el JSON de neudet**: `inventari()` torna `tubs` i `resum` igualets als del fitxer
  (`disseny/inventari/inventari_tubs.json`, per `NEUDET_ROOT`) — cap recompte, cap reetiquetatge, cap còpia.
- **El JSON real dona el que la pantalla necessita**: cada fila porta `model_excel`, `lloc`, `serial_repetit`
  (booleà) i `cataleg_via`; sense aquests camps els filtres i les marques no podrien existir.
- **Els texts d'interpretació surten sencers**: cada `cataleg_via` que comença per «interpretat» és, a la
  resposta i a la pantalla, exactament el mateix text que al JSON (retallat per `escD`, res més).
- **La fitxa, on diu neudet**: la convenció és `docs/site/detector/certificacio_tubs.md:51` (es comprova que
  la línia 51 és aquesta); per tant la fitxa d'un tub del catàleg és `entrades["tub:<cataleg>"].document`, i
  només enllaça si el camí és un fitxer dins de neudet. Quan no hi enllaça, `motiu` ho diu.
- **El servidor no serveix el que no és una fitxa**: `/api/inventari/fitxa` dona 200 amb les mateixes
  capçaleres que el visor de campanyes per un camí donat per `fitxes()`, i 403 per qualsevol altre.
- **El mirall node** (marcadors `INVENTARI-DEF-BEGIN/END`): els filtres i les marques de la pàgina, sobre les
  dades reals de l'API, donen exactament les files que dona el JSON.
Sense neudet, els tests amb dades reals es salten.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simui import inventari as I  # noqa: E402
from simui import server  # noqa: E402

SRC = ROOT / "src" / "simui"
INDEX = (SRC / "static" / "index.html").read_text(encoding="utf-8")
SERVIDOR = (SRC / "server.py").read_text(encoding="utf-8")


def _esc(s) -> str:
    """El mateix que `escD` a la pàgina: una passada sobre `& < > "`."""
    return str("" if s is None else s).replace("&", "&amp;").replace("<", "&lt;") \
                                      .replace(">", "&gt;").replace('"', "&quot;")


def _neudet_o_skip() -> Path:
    try:
        return I.inventari_path()
    except Exception as e:                                    # RuntimeError: el mirall no té l'inventari
        pytest.skip(f"no hi ha inventari a neudet: {e}")


@pytest.fixture(scope="module")
def dades():
    """La resposta de l'API i el JSON de neudet, llegits alhora (és el bessó)."""
    _neudet_o_skip()
    return json.loads(I.inventari_path().read_text(encoding="utf-8")), I.inventari()


# ── el bessó: el que torna l'API és el JSON, tal com és ───────────────────────

def test_tubs_i_resum_són_les_files_del_json_sense_tocar(dades):
    j, d = dades
    assert d["tubs"] == j["tubs"] and d["resum"] == j["resum"]
    assert d["que"] == j["_que"] and d["regenera"] == j["_regenera"]
    assert d["font"] == str(I.inventari_path())


def test_el_json_dona_el_que_la_pantalla_necessita(dades):
    _, d = dades
    claus = {"fila_excel", "model_excel", "item", "serial", "lloc", "comentari",
             "propietari", "cataleg", "cataleg_via", "serial_repetit"}
    assert d["tubs"], "l'inventari és buit"
    for t in d["tubs"]:
        assert claus <= set(t), f"fila sense tots els camps: {t}"
        assert isinstance(t["serial_repetit"], bool)
        assert isinstance(t.get("cataleg_via"), str)
    # els filtres surten dels valors que hi ha, no d'una taula a part
    assert d["models"] == sorted({t["model_excel"] for t in d["tubs"] if t["model_excel"]})
    assert d["llocs"] == sorted({t["lloc"] for t in d["tubs"] if t["lloc"]})


def test_cada_interpretat_surta_sencer(dades):
    j, d = dades
    for tj, td in zip(j["tubs"], d["tubs"]):
        via = str(td.get("cataleg_via") or "")
        if via.startswith("interpretat"):
            assert via == tj["cataleg_via"] and "…" not in via
    assert any(str(t.get("cataleg_via", "")).startswith("interpretat") for t in d["tubs"]), \
        "l'inventari ja no té cap fila interpretada: aquest test ja no pinta res"


def test_el_resum_de_neudet_no_surt_inventat(dades):
    """Cada (tub del catàleg, lloc) del resum té files a la llista: si no, la xifra no té on agafar-se."""
    j, d = dades
    assert d["resum"] == j["resum"]
    files = d["tubs"]
    for fila in d["resum"]:
        n = sum(1 for t in files if t["cataleg"] == fila["cataleg"] and t["lloc"] == fila["lloc"])
        assert n == fila["n"], f"el resum de neudet diu {fila}, la llista en dona {n}"


# ── la fitxa: la convenció de neudet i el que en fa la UI ─────────────────────

def test_la_convenció_de_la_fitxa_és_la_línia_que_es_cita():
    neudet = I.DES.neudet_root()
    linia = (neudet / "docs/site/detector/certificacio_tubs.md").read_text(encoding="utf-8").splitlines()[50]
    assert "UI" in linia and "validacions.json" in linia and "document" in linia, linia


def test_cada_tub_del_catàleg_té_fitxa_o_un_motiu_escrit(dades):
    _, d = dades
    assert d["fitxes"], "cap tub del catàleg a l'inventari"
    for c, f in d["fitxes"].items():
        assert set(f) >= {"document", "rel", "motiu"}
        if f["rel"]:
            assert (I.DES.neudet_root() / f["rel"]).is_file()
        else:
            assert f["motiu"], f"a {c} no li passa res i no té enllaç: cal un motiu"


def test_un_document_abs_no_enllaça_però_diu_per_què(tmp_path, monkeypatch):
    monkeypatch.setattr(I, "_validacions",
                        lambda: {"entrades": {"tub:x": {"document": "docs/site/detector/no_hi_soc.md"}}})
    f = I._fitxa(I._validacions()["entrades"]["tub:x"])
    assert f["rel"] is None and "no és un fitxer dins de neudet" in f["motiu"]


@pytest.mark.parametrize("rel", ["", "/", "../README.md", "docs/site/detector/",
                                 "docs/site/detector/certificacio_tubs.md §CERT-P", "/etc/hostname",
                                 "docs/site/detector/certificacio_tubs.md/x"])
def test_fitxa_fitxer_refusa_qualsevol_camí_que_no_hagi_donat_fitxes(rel):
    _neudet_o_skip()
    with pytest.raises(PermissionError):
        I.fitxa_fitxer(rel)


# ── per HTTP, amb un servidor real ────────────────────────────────────────────

@pytest.fixture(scope="module")
def url():
    srv = server.make_server("127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _get(url_base: str, path: str):
    try:
        with urllib.request.urlopen(url_base + path, timeout=60) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def test_el_servidor_torna_l_inventari_i_la_fitxa_d_un_tub(url):
    _neudet_o_skip()
    code, _, body = _get(url, "/api/inventari/tubs")
    d = json.loads(body)
    assert code == 200 and d["tubs"] == I.inventari()["tubs"]
    amb = next((c, f) for c, f in d["fitxes"].items() if f["rel"])
    code, h, body = _get(url, f"/api/inventari/fitxa?rel={amb[1]['rel']}")
    assert code == 200 and body == (I.DES.neudet_root() / amb[1]["rel"]).read_bytes()
    assert h["X-Content-Type-Options"] == "nosniff"
    from urllib.parse import unquote
    assert unquote(h["X-Cam-i"]) == str((I.DES.neudet_root() / amb[1]["rel"]).resolve())
    assert h["X-Mtime"] == server.CV.mtime_iso(I.DES.neudet_root() / amb[1]["rel"])


@pytest.mark.parametrize("rel, codi", [("", 403), ("../../etc/hostname", 403),
                                       ("disseny/inventari/inventari_tubs.json", 403)])
def test_el_servidor_refusa_el_que_no_és_una_fitxa(url, rel, codi):
    _neudet_o_skip()
    code, _, body = _get(url, f"/api/inventari/fitxa?rel={rel}")
    assert code == codi and "error" in json.loads(body)


def test_sense_inventari_no_inventa_res(url, monkeypatch, tmp_path):
    """Si el mirall de neudet és vell, la pàgina diu on mirar: un 400 amb el camí, no una pantalla buida."""
    monkeypatch.setattr(I.DES, "neudet_root", lambda: tmp_path)      # un neudet sense `disseny/inventari/`
    srv = server.make_server("127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/inventari/tubs",
                                    timeout=30) as r:
            codi = r.status                                   # no hauria d'arribar mai aquí
    except urllib.error.HTTPError as e:
        codi, cos = e.code, json.loads(e.read())
        assert codi == 400 and "extreu_tubs.py" in cos["error"] and str(tmp_path) in cos["error"]
    else:
        raise AssertionError(f"un inventari absent hauria de ser un 400, ha tornat {codi}")
    finally:
        srv.shutdown()
        srv.server_close()


# ── la pantalla: punts fixos de text i res d'escriptura ───────────────────────

def test_la_pantalla_te_la_pestanya_i_les_ancores():
    assert '<button class="ptab" data-tab="inventari">Inventari de tubs</button>' in INDEX
    assert 'id="pg-inventari"' in INDEX and "inventari: ['Inventari de tubs'" in INDEX
    assert "else if(name === 'inventari')" in INDEX
    for ancora in ('id="i-font"', 'id="i-f-model"', 'id="i-f-lloc"', 'id="i-f-rep"',
                   'id="i-resum"', 'id="i-llista"', 'id="i-comte"'):
        assert ancora in INDEX, ancora
    assert INDEX.index('id="pg-inventari"') < INDEX.index("let INVT = null")   # el markup, abans del script
    assert "invEscolta();" in INDEX
    # les etiquetes de les columnes surten del JSON: la UI no en reetiqueta cap de nova
    assert "fila_excel:'fila Excel'" in INDEX and "com s'ha sabut el tub del catàleg" in INDEX


def test_és_només_lectura():
    assert 'elif path == "/api/inventari/tubs"' in SERVIDOR
    assert 'elif path == "/api/inventari/fitxa"' in SERVIDOR
    assert "/api/inventari" not in SERVIDOR.split("def do_POST")[1]           # cap POST d'inventari
    # la pàgina només demana les dues rutes de lectura; no n'hi ha cap per escriure
    assert set(re.findall(r"/api/inventari/[a-z]+", INDEX)) == {"/api/inventari/tubs",
                                                                "/api/inventari/fitxa"}


# ── el mirall node: els filtres i les marques, sobre les dades reals ──────────

@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar les funcions de la UI")
def test_la_pagina_filtra_i_marca_el_que_diu_l_api():
    _neudet_o_skip()
    d = I.inventari()
    model = next((t["model_excel"] for t in d["tubs"] if t["serial_repetit"]), None)
    lloc = d["llocs"][0]
    escD = next(l for l in INDEX.splitlines() if l.startswith("const escD"))   # la real, no una còpia
    # les dues funcions reals de la pàgina que el tros fa servir, no una còpia escrita aquí
    helpers = [next(l for l in INDEX.splitlines() if l.startswith(c))
               for c in ("const escD =", "const kEnc =")]
    tros = INDEX.split("// INVENTARI-DEF-BEGIN")[1].split("\n", 1)[1].split("// INVENTARI-DEF-END")[0]
    programa = f"""
const EL = {{}};
const Q = s => EL[s] || (EL[s] = {{innerHTML:'', value:'', checked:false,
                                  scrollIntoView(){{}}, addEventListener(){{}}, onclick:null}});
{chr(10).join(helpers)}
var fxCarrega;
{tros}
INVT = {json.dumps(d, ensure_ascii=False)};
const out = {{}};
invPinta();
out.totes = Q('#i-llista').innerHTML;
out.comte = Q('#i-comte').innerHTML;
out.resum = Q('#i-resum').innerHTML;
Q('#i-f-model').value = {json.dumps(model, ensure_ascii=False)}; invPinta();
out.per_model = invFiltrats().length;
Q('#i-f-rep').checked = true; invPinta();
out.per_model_i_rep = invFiltrats().length;
Q('#i-f-model').value = ''; Q('#i-f-rep').checked = false;
Q('#i-f-lloc').value = {json.dumps(lloc, ensure_ascii=False)}; invPinta();
out.per_lloc = invFiltrats().length;
Q('#i-f-lloc').value = ''; invSelCataleg({json.dumps(sorted(d['fitxes'])[0], ensure_ascii=False)});
out.per_cataleg = invFiltrats().length;
out.neteja = Q('#i-comte').innerHTML.includes('id="i-neteja"');
let ruta_fitxa = '';                                  // què demanaria un clic a «fitxa» (el visor, no aquí)
fxCarrega = u => {{ ruta_fitxa = u; return Promise.resolve(); }};
invFitxa('docs/site/detector/certificacio_tubs.md', 'lnd_252241');
out.fitxa = ruta_fitxa;
console.log(JSON.stringify(out));"""
    r = subprocess.run(["node", "-e", programa], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout)

    # 3. serial repetit: la ratlla a la fila i la marca a la cel·la, a totes i només a elles
    repetides = [t for t in d["tubs"] if t["serial_repetit"]]
    assert repetides, "l'inventari ja no té cap serial repetit"
    assert s["totes"].count('<tr class="i-rep">') == len(repetides)
    assert s["totes"].count('<span class="tag t-no">serial repetit</span>') == len(repetides)
    assert s["comte"] == f"{len(d['tubs'])} de {len(d['tubs'])} files"          # sense filtre: totes

    # 4. «interpretat»: la marca i el text sencer, tal com és al JSON
    interpretats = [t for t in d["tubs"] if str(t.get("cataleg_via", "")).startswith("interpretat")]
    assert s["totes"].count('<span class="tag t-wa">interpretat</span>') == len(interpretats)
    for t in interpretats:
        assert _esc(t["cataleg_via"]) in s["totes"], t["cataleg_via"]

    # 5. la fitxa només s'enllaça on `fitxes()` ha donat un camí; als altres, el motiu queda escrit
    amb_fitxa = sum(1 for t in d["tubs"] if (d["fitxes"].get(t["cataleg"]) or {}).get("rel"))
    assert s["totes"].count(">fitxa</a>") == amb_fitxa
    assert ("sense enllaç:" in s["totes"]) == any(not f["rel"] for f in d["fitxes"].values())

    # 2. els filtres: per model, per lloc, pels serials repetits i per tub del catàleg
    assert s["per_model"] == sum(1 for t in d["tubs"] if t["model_excel"] == model)
    assert s["per_model_i_rep"] == sum(1 for t in repetides if t["model_excel"] == model)
    assert s["per_lloc"] == sum(1 for t in d["tubs"] if t["lloc"] == lloc)
    assert s["per_cataleg"] == sum(1 for t in d["tubs"] if t["cataleg"] == sorted(d["fitxes"])[0])
    assert s["neteja"], "amb un tub del catàleg filtrat, la pantalla no dona manera de treure el filtre"

    # un clic a «fitxa» demana el fitxer que `fitxes()` ha donat, al visor de només lectura
    assert s["fitxa"] == "/api/inventari/fitxa?rel=docs%2Fsite%2Fdetector%2Fcertificacio_tubs.md"

    # 1. la taula «resum» de neudet, sencera (una fila per capçalera + una per línia)
    assert "tub del catàleg" in s["resum"] and "data-fitxa=" in s["resum"]
    assert s["resum"].count("<tr>") == len(d["resum"]) + 1
    for fila in d["resum"]:
        assert f'<td>{_esc(fila["lloc"])}</td><td>{_esc(fila["n"])}</td>' in s["resum"], fila
