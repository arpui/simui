"""test_fitxers_ui.py — FITXERS-UI (encàrrec 2026-11-19): enllaços «veure» i visor de només lectura.

Què es fixa
-----------
- **Només el que hi és**: `_fitxers_veure` llista els fitxers arrel que existeixen (més el `resposta.md` i el
  `meta.json` de cada etapa que hi sigui), cadascun amb el camí absolut i la data; un document d'etapa que
  no és al disc simplement no surt (mai una fila buida ni un camí inventat).
- **El filtre de seguretat**: un rel amb `..` o absolut que, a sobre, apunti a un fitxer que EXISTEIX fora de la
  campanya, no entra a la llista. I el punt que els serveix, `/api/campanya/fitxer`, torna 403 (ja provat a
  `test_mcgen_campanya_vista.py`; aquí es fixa també per HTTP, amb un servidor real).
- **Camí i data que coincideixen**: el visor llegeix les capçaleres `X-Cam-i`/`X-Mtime` del servidor i la
  secció «Fitxers» de la pàgina, les mateixes dades per `fitxers_veure`: un sol formatador (`mtime_iso`).
- **«altres» ho diu**: `llista()` dona `motiu_altres` (els seus propis criteris, escrits) només a les campanyes
  del grup «altres»; la pàgina el pinta a l'apartat «Fitxers».
- **El mirall node** (marcadors `FITXERS-DEF-BEGIN/END`): `kFitxers` i `fxLlista` sobre dades reals — sense
  obrir la campanya només surten els enllaços dels fitxers que `llista()` diu que hi són, i tot queda escapats.
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
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simui import campanya_vista as V  # noqa: E402
from simui import server  # noqa: E402

SRC = ROOT / "src" / "simui"
INDEX = (SRC / "static" / "index.html").read_text(encoding="utf-8")
FORMAT_MTIME = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def _neudet_o_skip() -> Path:
    try:
        return V.neudet_root()
    except Exception as e:                                    # CampanyaError o DesignError segons quini falti
        pytest.skip(f"neudet no és present: {e}")


def _campanya_tmp(tmp_path: Path, yaml_: bool = True, pla: bool = False, comp: bool = False) -> Path:
    d = tmp_path / "camp"
    d.mkdir()
    if yaml_:
        (d / "campanya.yaml").write_text("id: camp\n", encoding="utf-8")
    if pla:
        (d / "PLA.md").write_text("# pla\n", encoding="utf-8")
    if comp:
        (d / "comprova.json").write_text("{}", encoding="utf-8")
    return d


# ── _fitxers_veure: només el que hi és, amb camí i data ──────────────────────

def test_fitxers_veure_llista_nomes_els_que_hi_son(tmp_path):
    d = _campanya_tmp(tmp_path, pla=True)                     # sense comprova.json ni manifest
    got = V._fitxers_veure(d, [])
    assert [x["rel"] for x in got] == ["campanya.yaml", "PLA.md"]
    for x in got:
        assert x["camí"] == str(d / x["rel"]) and FORMAT_MTIME.match(x["mtime"])
    assert x["mtime"] == V.mtime_iso(d / "PLA.md")            # el mateix formatador que la capçalera del servidor


def test_fitxers_veure_te_es_documents_detapa_que_hi_son_i_salta_els_que_no(tmp_path):
    d = _campanya_tmp(tmp_path)
    e = d / "etapes" / "S1_draft"
    e.mkdir(parents=True)
    (e / "meta.json").write_text("{}", encoding="utf-8")      # resposta.md NO hi és
    etapes = [{"nom": "S1", "resposta": {"md": "etapes/S1_draft/resposta.md"},
               "fitxers": {"meta": "etapes/S1_draft/meta.json"}}]
    rels = [x["rel"] for x in V._fitxers_veure(d, etapes)]
    assert "etapes/S1_draft/meta.json" in rels and "etapes/S1_draft/resposta.md" not in rels
    assert any(x["nom"] == "S1 · meta.json" for x in V._fitxers_veure(d, etapes))


@pytest.mark.parametrize("rel", ["../../secret.yaml", "/etc/hostname", "etapes/../../../secret.yaml"])
def test_fitxers_veure_filtra_un_rel_que_surtil_de_la_campanya_encara_que_el_fitxer_existeixi(tmp_path, rel):
    d = _campanya_tmp(tmp_path)
    (tmp_path / "secret.yaml").write_text("secrets\n", encoding="utf-8")
    got = V._fitxers_veure(d, [{"nom": "S1", "fitxers": {"meta": rel}}])
    assert [x["rel"] for x in got] == ["campanya.yaml"]       # el document brut no entra, mai


# ── llista(): motiu_altres i els booleans de fitxers ─────────────────────────

def test_llista_dona_motiu_altres_nomes_a_les_del_grup_altres(tmp_path, monkeypatch):
    root = tmp_path / "campanyes"
    p = root / "amb_manifest"
    p.mkdir(parents=True)
    (p / "campanya.yaml").write_text("id: amb_manifest\n", encoding="utf-8")
    (p / V.MANIFEST).write_text("{}", encoding="utf-8")
    a = root / "vella"
    a.mkdir()
    (a / "campanya.yaml").write_text("id: vella\nestat: jutjada\n", encoding="utf-8")
    (a / "PLA.md").write_text("# pla\n", encoding="utf-8")
    monkeypatch.setattr(V, "campanyes_root", lambda: root)
    per_id = {c["id"]: c for c in V.llista()}
    assert per_id["amb_manifest"]["grup"] == V.GRUP_PRINCIPAL and per_id["amb_manifest"]["motiu_altres"] is None
    v = per_id["vella"]
    assert v["grup"] == V.GRUP_ALTRES and "campanya_ui.json" in v["motiu_altres"] and "fitxa" in v["motiu_altres"]
    assert v["fitxers"] == {"pla": True, "comprova": False}   # el que hi ha al disc, tal com és


# ── per HTTP, amb un servidor real: capçaleres i refus ───────────────────────

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


def test_el_servidor_torna_cam_i_data_amb_el_fitxer(url):
    root = _neudet_o_skip()
    ids = [c["id"] for c in V.llista() if (V.dir_de(c["id"]) / "campanya.yaml").is_file()]
    assert ids, "neudet sense cap campanya llesta"
    id_ = ids[0]
    f = V.fitxer(V.dir_de(id_), "campanya.yaml")
    code, h, body = _get(url, f"/api/campanya/fitxer?id={id_}&rel=campanya.yaml")
    assert code == 200 and body == f.read_bytes()
    assert urllib.parse.unquote(h["X-Cam-i"]) == str(f)       # el camí absolut que el visor posa a dalt
    assert h["X-Mtime"] == V.mtime_iso(f)                     # la mateixa data que `fitxers_veure`


def test_un_intent_de_sortir_ne_torna_un_403_amb_el_motiu(url):
    root = _neudet_o_skip()
    id_ = V.llista()[0]["id"]
    code, _, body = _get(url, f"/api/campanya/fitxer?id={id_}&rel=../../campanyes")
    assert code == 403
    assert "error" in json.loads(body)                        # el motiu, tal com ho diu el filtre


# ── el mirall node del tros pur (kFitxers i fxLlista) ─────────────────────────

@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar les funcions pures de la UI")
def test_el_llistat_i_la_pagina_pinten_el_que_llista_es_diu():
    escD = next(l for l in INDEX.splitlines() if l.startswith("const escD"))   # la real, no una còpia
    dades = """
    KC.lista = [{id: 'c04_draft', grup: 'principal', manifest: true, fitxers: {pla: true, comprova: true}},
                {id: 'c01_vella', grup: 'altres', manifest: false, fitxers: {pla: false, comprova: false},
                 motiu_altres: 'no hi ha `campanya_ui.json`, l\\'`estat` del yaml no és `proposta` i no porta `fitxa: 1`'}];
    const fila = kFitxers({id: 'c04_draft', fitxers_veure: [
      {rel: 'campanya.yaml', nom: 'campanya.yaml', 'camí': 'X', mtime: '2026-11-20 09:00:00'},
      {rel: 'etapes/S1_draft/meta.json', nom: 'S1 · meta.json', 'camí': '/home/albert/projects/neudet/disseny/campanyes/c04_draft/etapes/S1_draft/meta.json', mtime: '2026-11-18 22:01:02'}]});
    const sense = kFitxers({id: 'c01_vella', fitxers_veure: [{rel: 'campanya.yaml', nom: 'campanya.yaml', 'camí': 'X', mtime: '2026-01-01 00:00:00'}]});
    const brutes = kFitxers({id: 'brutes', fitxers_veure: [{rel: '"><s', nom: '"><s', 'camí': '"><s', mtime: '2026-01-01 00:00:00'}]});
    const l1 = fxLlista(KC.lista[0]), l2 = fxLlista(KC.lista[1]);
    console.log(JSON.stringify([fila, sense, brutes, l1, l2]));"""
    js = (INDEX.split("// FITXERS-DEF-BEGIN")[1].split("\n", 1)[1].split("// FITXERS-DEF-END")[0] +
          "\n" + escD + "\nconst KC = {lista: []};\n" + dades)
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    fila, sense, brutes, l1, l2 = json.loads(r.stdout)

    assert "<h2>Fitxers</h2>" in fila
    assert 'data-fx-rel="etapes/S1_draft/meta.json"' in fila and "veure S1 · meta.json" in fila
    assert "/neudet/disseny/campanyes/c04_draft/etapes/S1_draft/meta.json" in fila   # el camí absolut, tal com ve
    assert "modificat 2026-11-18 22:01:02" in fila
    assert "«altres»" not in fila                                                    # principal: cap motiu

    assert "«altres»" in sense and "no hi ha" in sense and "fitxa" in sense          # el motiu de llista(), escrit
    assert '&quot;&gt;&lt;s' in brutes and 'data-fx-rel="&quot;&gt;&lt;s"' in brutes   # tot escapats, també als atributs
    assert l1.count("data-fx-id=") == 4 and "PLA.md" in l1 and "campanya_ui.json" in l1
    assert l2.count("data-fx-id=") == 1 and "PLA.md" not in l2 and "comprova" not in l2


# ── els punts de la pantalla, pins de text ────────────────────────────────────

def test_la_pagina_munta_la_seccio_i_el_lector():
    assert "out.push(kFitxers(v));" in INDEX                          # l'apartat «Fitxers» de la vista
    assert "fxLlista(c);" in INDEX                                    # els enllaços del llistat
    for ancora in ('id="fx"', 'id="fx-body"', 'id="fx-cru"', 'id="fx-form"', 'id="fx-tanca"'):
        assert ancora in INDEX, ancora
    assert INDEX.index('<div id="fx" hidden') < INDEX.index("async function fxObre")  # el markup, abans del script
    assert "fxObre(KC.id, fx.dataset.fxRel" in INDEX                   # clic a la pàgina
    assert "fxObre(fx.dataset.fxId, fx.dataset.fxRel)" in INDEX        # clic al llistat (id de la fila)
    assert "obre al formulari" in INDEX and "FX.rel !== 'campanya.yaml'" in INDEX


def test_campanya_real_el_que_torna_la_vista_son_fitxers_que_hi_son_i_complets():
    _neudet_o_skip()
    c = next((x for x in V.llista() if x["id"] == "c04_draft"), None) or V.llista()[0]
    v = V.vista(V.dir_de(c["id"]))
    esperats = {(p.relative_to(V.dir_de(c["id"]))).as_posix()
                for p in V.dir_de(c["id"]).rglob("*") if p.is_file() and p.suffix in V.TIPUS}
    donats = {x["rel"] for x in v["fitxers_veure"]}
    assert donats <= esperats                                          # cap inventat: tots existeixen
    assert {"campanya.yaml", "PLA.md"} <= donats                       # i els que hi són, hi surten
    for x in v["fitxers_veure"]:
        assert Path(x["camí"]).is_file() and FORMAT_MTIME.match(x["mtime"])
