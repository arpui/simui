"""test_ui_design.py — les rutes de la pestanya Disseny i de Resultats, amb un servidor real.

Què es fixa
-----------
- Cada ruta nova (`/api/design/{meta,load,check,view,export,ask}`, `/api/results`) respon, i els
  errors d'entrada són un 400 amb el motiu (no un forat).
- Cada disseny per defecte es carrega, es verifica sense violacions i es visualitza.
- Un disseny de neudet SENSE editar s'exporta amb els BYTES originals del `.dat`/`.json` (no es
  regenera). Un d'editat sí es regenera i ja no porta els bytes originals.
- Els resultats de c03 i x06 surten amb la procedència i l'avís de counterUPC_v0 (només c03).
- La pàgina té les tres pestanyes i els identificadors que el JS usa.
Sense neudet, els tests amb dades reals es salten; els de rutes d'entrada, no.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
import zipfile
import io
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _simphy_resultats_aillats(tmp_path, monkeypatch):
    """Els tests d'aquest fitxer parlen de les dades de neudet: els resultats de simphy
    (`data/resultats`, o `SIMPHY_RESULTATS`) no s'hi barregen. Els de simphy tenen els seus tests."""
    monkeypatch.setenv("SIMPHY_RESULTATS", str(tmp_path / "sense_simphy"))
sys.path.insert(0, str(ROOT / "src"))

from simphy.mcgen import design as D  # noqa: E402
from simphy.ui import server  # noqa: E402

C03 = "campanyes/c03_3anells_grups/1x3_4x6_3x12"
C02 = "campanyes/c02_cd_2grups/4x3_4x7_cd0p5a360c0"
X06 = "experiments/x06_vtub/banc_pe_lnd252285/r4_t0"
X06_R8 = "experiments/x06_vtub/banc_pe_lnd252285/r8_t0"
DEFAULTS = {C03: "e9039f26ad68", C02: "2aee8f7663d5", X06: "8ccdf856d356",
            X06_R8: "b5c90774def8", "campanyes/c01_8tubs_30x30x80/4x3_4x7": "d75ab372366e"}


@pytest.fixture(scope="module")
def url():
    srv = server.make_server("127.0.0.1", 0)          # port efímer
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _neudet_o_skip() -> Path:
    try:
        return D.neudet_root()
    except D.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def _get(url_base: str, path: str):
    try:
        with urllib.request.urlopen(url_base + path, timeout=60) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def _post(url_base: str, path: str, body: dict):
    req = urllib.request.Request(url_base + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def _json(status_and_body):
    status, _, data = status_and_body
    return status, json.loads(data)


def _load(url_base: str, id_: str) -> dict:
    status, body = _json(_post(url_base, "/api/design/load", {"id": id_}))
    assert status == 200, body
    return body


def _ruta_inexistent_o_pagina(url_base: str):
    return _get(url_base, "/api/design/inexistent")


# ── la pàgina i les rutes sense neudet ─────────────────────────────────────
def test_la_pagina_te_les_tres_pestanyes_i_els_ids_del_js(url):
    status, _, data = _get(url, "/")
    txt = data.decode()
    assert status == 200
    for tab in ("sim", "disseny", "resultats"):
        assert f'data-tab="{tab}"' in txt
    for ident in ("d-def", "d-anells", "d-json", "d-xy", "d-xz", "d-baixa", "d-fix", "d-cmp",
                  "r-stage", "r-energia", "r-etapes", "r-xy", "r-taula"):
        assert f'id="{ident}"' in txt, ident


def test_ruta_desconeguda_dona_404(url):
    status, _, _ = _ruta_inexistent_o_pagina(url)
    assert status == 404


def test_load_sense_id_ni_dat_dona_400(url):
    status, body = _json(_post(url, "/api/design/load", {}))
    assert status == 400 and "cal un" in body["error"]


def test_load_id_inexistent_dona_400_amb_el_motiu(url):
    _neudet_o_skip()
    status, body = _json(_post(url, "/api/design/load", {"id": "campanyes/no/existeix"}))
    assert status == 400 and "no hi ha cap disseny per defecte" in body["error"]


def test_results_sense_hash_no_es_un_forat(url):
    status, body = _json(_get(url, "/api/results?hash="))
    assert status == 400 and "cal un hash" in body["error"]


def test_export_d_un_disseny_buit_dona_400(url):
    status, body = _json(_post(url, "/api/design/export", {"design": {}}))
    assert status == 400 and body.get("error")


def test_ask_amb_prompt_buit_dona_400(url):
    status, body = _json(_post(url, "/api/design/ask", {"prompt": "  "}))
    assert status == 400 and "buit" in body["error"]


def test_ask_amb_un_model_fals_proposa_un_disseny_verificat(url, monkeypatch):
    """La ruta usa `design_prompt.generate` (el mateix bucle que la CLI): amb un model que
    retorna la plantilla, el disseny és vàlid i surt com a JSON de disseny."""
    _neudet_o_skip()
    from simphy.mcgen.agent import llm as L

    exemple = json.loads((ROOT / "src/simphy/mcgen/examples/design/design_c03_1x3_4x6_3x12.json").read_text())

    class FakeLLM:
        last_mode, had_grammar, mode_log = "json_schema", True, []

        def __init__(self, *a, **k):
            pass

        def complete_json(self, messages, schema=None, max_tokens=0):
            return exemple

    monkeypatch.setattr(L, "LocalLLM", FakeLLM)
    status, body = _json(_post(url, "/api/design/ask", {"prompt": "tres anells de PE", "campanya": "c03_3anells_grups"}))
    assert status == 200 and body["ok"] is True, body
    assert body["design"]["bloc"]["material"] == "PE" and len(body["design"]["anells"]) == 3


# ── per defecte: cada disseny de neudet es carrega, es verifica i es visualitza ──────────
@pytest.mark.parametrize("id_", list(DEFAULTS))
def test_cada_default_es_carrega_i_no_es_editat(url, id_):
    _neudet_o_skip()
    body = _load(url, id_)
    assert body["editat"] is False and body["origen"]["id"] == id_
    assert body["origen"]["hash"] == DEFAULTS[id_]
    assert body["design"]["anells"]


@pytest.mark.parametrize("id_", list(DEFAULTS))
def test_cada_default_es_verifica_sense_violacions(url, id_):
    _neudet_o_skip()
    d = _load(url, id_)
    status, body = _json(_post(url, "/api/design/check", {"design": d["design"], "editat": False, "id": id_}))
    assert status == 200
    assert body["verificat"] is True and body["violations"] == []
    assert body["hash"] == DEFAULTS[id_]


@pytest.mark.parametrize("id_", list(DEFAULTS))
def test_cada_default_es_visualitza_amb_la_taula_i_els_svg(url, id_):
    _neudet_o_skip()
    d = _load(url, id_)
    status, body = _json(_post(url, "/api/design/view", {"design": d["design"], "editat": False, "id": id_}))
    assert status == 200
    assert body["xy_svg"].startswith("<svg") and body["xz_svg"].startswith("<svg")
    assert len(body["rows"]) == sum(a["n"] for a in d["design"]["anells"])   # un tub per fila
    assert body["hash"] == DEFAULTS[id_]


def test_un_default_no_editat_s_exporta_amb_els_bytes_originals(url):
    """La regla d'U4: un disseny carregat i no editat es baixa tal com és, sense regenerar."""
    root = _neudet_o_skip()
    status, _, data = _post(url, "/api/design/export", {"design": _load(url, C02)["design"],
                                                       "editat": False, "id": C02})
    assert status == 200
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    dat0 = root / "disseny/campanyes/c02_cd_2grups/export/4x3_4x7_cd0p5a360c0.dat"
    js0 = dat0.with_suffix(".json")
    base = "4x3_4x7_cd0p5a360c0/config/4x3_4x7_cd0p5a360c0"
    assert z.read(base + ".dat") == dat0.read_bytes()
    assert z.read(base + ".json") == js0.read_bytes()
    assert any(n.endswith("README.md") for n in names)
    assert not any("/decks/mcnp/" in n for n in names)              # sense energia: sense decks
    assert any(n.endswith("_xy.svg") for n in names)                # el visor també va al zip


def test_x06_no_editat_conserva_el_nom_de_neudet(url):
    """r4_t0 no ve d'anells: el zip porta el seu nom de neudet (no el regenerat `1x4`)."""
    root = _neudet_o_skip()
    status, _, data = _post(url, "/api/design/export", {"design": _load(url, X06)["design"],
                                                       "editat": False, "id": X06, "energia_mev": 1.0})
    assert status == 200
    z = zipfile.ZipFile(io.BytesIO(data))
    dat0 = root / "disseny/experiments/x06_vtub/banc_pe_lnd252285/export/r4_t0.dat"
    assert z.read("r4_t0/config/r4_t0.dat") == dat0.read_bytes()
    assert any(n.startswith("r4_t0/decks/mcnp/") for n in z.namelist())


def test_un_editat_es_regenera_i_no_porta_els_bytes_originals(url):
    _neudet_o_skip()
    d = _load(url, C02)["design"]
    d["anells"][0]["r"] = 6.5                                      # editat: candidat nou
    status, _, data = _post(url, "/api/design/export", {"design": d, "editat": True, "id": C02,
                                                       "energia_mev": 1.0})
    assert status == 200
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert not any(n.endswith("config/4x3_4x7_cd0p5a360c0.dat") for n in names)   # no els originals
    assert any("/config/" in n and n.endswith(".dat") for n in names)


def test_campanya_c03_fa_un_conjunt_de_decks_per_energia(url):
    _neudet_o_skip()
    d = _load(url, C03)["design"]
    status, _, data = _post(url, "/api/design/export", {"design": d, "editat": False, "id": C03,
                                                       "campanya": "c03_3anells_grups"})
    assert status == 200
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    for e in ("E_0.001MeV", "E_1MeV", "E_5MeV"):
        assert any(f"/decks/{e}/mcnp/" in n for n in names), e
    notes = [n for n in names if n.endswith("/notes.txt")]
    assert notes and "CAMPANYA c03_3anells_grups" in zipfile.ZipFile(io.BytesIO(data)).read(notes[0]).decode()


def test_visor_de_l_original_diu_que_la_font_es_assumida(url):
    """El .dat no porta la font: l'original la diu com a assumida (centre), no com a dada."""
    _neudet_o_skip()
    d = _load(url, C03)["design"]
    status, body = _json(_post(url, "/api/design/view", {"design": d, "editat": False, "id": C03}))
    assert status == 200 and body["valors"] is None
    assert body["font"]["origen"].startswith("per defecte")


def test_editar_l_anell_canvia_el_hash_i_diu_que_es_candidat_nou(url):
    _neudet_o_skip()
    d = _load(url, C03)["design"]
    d["anells"][2]["r"] = 13.0
    status, body = _json(_post(url, "/api/design/check", {"design": d, "editat": True, "id": C03}))
    assert status == 200 and body["editat"] is True
    assert body["hash"] != DEFAULTS[C03]


def test_check_fora_del_bloc_ho_diu(url):
    _neudet_o_skip()
    d = _load(url, C03)["design"]
    d["anells"][0]["r"] = 40.0
    status, body = _json(_post(url, "/api/design/check", {"design": d, "editat": True, "id": C03}))
    assert status == 200 and body["verificat"] is True
    assert any("fora del bloc" in v for v in body["violations"])


def test_x06_sense_restriccions_s_avisa_no_verificat(url):
    """Un disseny sense restriccions no es mostra com a vàlid: es diu que no es verifica."""
    _neudet_o_skip()
    d = _load(url, X06)["design"]
    d["restriccions"] = None
    status, body = _json(_post(url, "/api/design/check", {"design": d, "editat": True}))
    assert status == 200 and body["verificat"] is False and "restriccions" in body["motiu"]


# ── pujat: el .dat i el .json de neudet ─────────────────────────────────────
def test_load_pujat_de_c03_es_com_el_default(url):
    root = _neudet_o_skip()
    base = root / "disseny/campanyes/c03_3anells_grups/export"
    body = _json(_post(url, "/api/design/load", {"dat_text": (base / "1x3_4x6_3x12.dat").read_text(),
                                                "json_text": (base / "1x3_4x6_3x12.json").read_text()}))[1]
    assert body["origen"]["origen"] == "pujat" and body["editat"] is False
    assert body["design"]["restriccions"] == {"campanya": "c03_3anells_grups"}


# ── resultats ───────────────────────────────────────────────────────────────
def test_results_c03_te_s3_amb_dades_i_s3_g4_sense(url):
    _neudet_o_skip()
    status, body = _json(_get(url, "/api/results?hash=e9039f26ad68"))
    assert status == 200 and body["hash"] == "e9039f26ad68"
    by = {e["etapa"]: e for e in body["entries"]}
    assert by["S3"]["status"] == "ok" and by["S3"]["provenance"]["citable"] is True
    assert len(by["S3"]["tubs"]) == 8 and len(by["S3"]["tubs"][0]["eps"]) == 11
    assert by["S3_g4"]["status"] == "sense resultats per tub de Geant4"
    assert any("counterUPC_v0" in w for w in by["S3"]["warnings"])
    assert body["vista"] is None                                   # sense energia, sense vista


def test_results_x06_te_s0_i_s0_g4_sense_avis_counterupc(url):
    _neudet_o_skip()
    status, body = _json(_get(url, "/api/results?hash=8ccdf856d356"))
    assert status == 200
    assert [e["etapa"] for e in body["entries"]] == ["S0", "S0_g4"]
    assert all(e["warnings"] == [] and e["status"] == "ok" for e in body["entries"])


def test_results_amb_energia_pinta_el_xy_per_eps(url):
    root = _neudet_o_skip()
    from urllib.parse import urlencode
    stage = str(root / "disseny/campanyes/c03_3anells_grups/etapes/S3")   # la clau és el camí absolut
    status, body = _json(_get(url, "/api/results?" + urlencode({"hash": "e9039f26ad68", "stage": stage, "energia": 1})))
    assert status == 200
    vista = body["vista"]
    assert vista is not None and vista["stage"].endswith("etapes/S3")
    assert sorted(int(k) for k in vista["valors"]) == list(range(1, 9))
    assert vista["valors"]["1"] == pytest.approx(0.092611)
    assert "ε per tub (color)" in vista["xy_svg"]                  # la llegenda de la escala


def test_results_hash_sense_etapes_es_buit_i_no_es_error(url):
    _neudet_o_skip()
    status, body = _json(_get(url, "/api/results?hash=000000000000&energia=1"))
    assert status == 200 and body["entries"] == [] and body["vista"] is None


# ── resultats de simphy a la comparativa (B3): fixture SINTÈTIC a un directori temporal ───────
C03_HASH = "e9039f26ad68"


def _simphy_sintetic(root: Path, neudet: Path, factor: float = 1.05) -> None:
    """Un `resultats_tub.json` v1.1 de MCNP, SINTÈTIC, per al disseny de c03: les mateixes posicions
    de tub que l'S3 de neudet i una taxa `factor` × la de neudet (només per provar la comparativa)."""
    from simphy.mcgen import results_simphy as RS
    s3 = json.loads((neudet / "disseny/campanyes/c03_3anells_grups/etapes/S3/resultats_tub.json").read_text())
    k = s3["energies_MeV"].index(1.0)
    tubs = [{"i": t["i"], "x": t["x"], "y": t["y"], "z": t["z"], "tipus": t["tipus"],
             "comptes": [factor * t["eps"][k] * 1e6], "eps": [factor * t["eps"][k]],
             "sig": [0.02 * factor * t["eps"][k]]}
            for t in s3["candidats"][C03_HASH]["tubs"]]
    doc = {"versio": "1.1", "etapa": "simphy", "campanya": "c03_3anells_grups", "motor": "mcnp",
           "energies_MeV": [1.0], "font": {"tipus": "iso", "pos_cm": [0, 0, 0]}, "meta": "meta.json",
           "deteccio": "np_taxa_tally", "sig_tipus": "tally",
           "candidats": {C03_HASH: {"nom": "1x3_4x6_3x12", "ronda": "simphy", "n": 1000000,
                                    "pareto_rang": None, "robusta": None, "tubs": tubs}}}
    meta = {"schema": 1, "git": {"simphy": {"repo": "/sintetic", "commit": "0123456789ab", "dirty": False,
                                            "dirty_files": [], "exclos": "data/resultats"}},
            "inputs": {"tubs_cells": "0" * 64, "decks": {"E_1MeV/x.py": "1" * 64}}, "warnings": []}
    RS.escriu(doc, meta, root / "campanyes" / "c03_3anells_grups" / "1x3_4x6_3x12" / "mcnp")


@pytest.fixture
def simphy_sintetic(tmp_path, monkeypatch):
    root = _neudet_o_skip()
    res = tmp_path / "resultats"
    _simphy_sintetic(res, root)
    monkeypatch.setenv("SIMPHY_RESULTATS", str(res))
    return res


def test_results_amb_simphy_surt_com_a_font_simphy_amb_la_seva_provenance(url, simphy_sintetic):
    status, body = _json(_get(url, f"/api/results?hash={C03_HASH}"))
    assert status == 200
    sim = [e for e in body["entries"] if e["font"] == "simphy"]
    assert len(sim) == 1 and sim[0]["motor"] == "mcnp" and sim[0]["status"] == "ok"
    assert sim[0]["provenance"]["citable"] is True
    assert sim[0]["deteccio"] == "np_taxa_tally" and sim[0]["sig_tipus"] == "tally"
    # les de neudet segueixen primer, com sempre
    assert body["entries"][0]["font"] == "neudet"


def test_comparativa_per_tub_entre_xarxa_i_simphy_amb_el_quocient(url, simphy_sintetic):
    from urllib.parse import urlencode
    status, body = _json(_get(url, "/api/results?" + urlencode({"hash": C03_HASH, "energia": 1})))
    assert status == 200
    comp = body["comparativa"]
    assert comp is not None and comp["energia"] == 1.0
    assert [c["motor"] for c in comp["columnes"]] == ["xarxa B1", "mcnp"]
    assert comp["referencia"].startswith("xarxa B1")                 # sense Geant4: a la xarxa B1
    assert len(comp["files"]) == 8
    x0 = comp["files"][0]["cols"]
    assert x0[0]["ratio"] == pytest.approx(1.0)
    assert x0[1]["ratio"] == pytest.approx(1.05)                     # el sintètic és 1,05 × la xarxa
    assert comp["nota_deteccio"] and "≪ 0,1 %" in comp["nota_deteccio"]   # deteccio diferent: es diu


def test_comparativa_sense_energia_no_es_calcula(url, simphy_sintetic):
    status, body = _json(_get(url, f"/api/results?hash={C03_HASH}"))
    assert status == 200 and body["comparativa"] is None


def test_la_pagina_te_el_bloc_de_la_comparativa(url):
    status, _, data = _get(url, "/")
    assert status == 200 and 'id="r-comp"' in data.decode()
