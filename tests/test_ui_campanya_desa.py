"""test_ui_campanya_desa.py — les rutes de «Desa la proposta», «Tanteja» i la llista, amb un servidor real.

Què es fixa
-----------
- `POST /api/campanya/desa` escriu els dos fitxers a un NEUDET_ROOT temporal, i refusa (400, amb el motiu)
  un id dolent, una campanya que no és proposta, i una certificació no disponible (aquí, sense `torch` ni
  script: el camí real, sense simular res).
- `POST /api/campanya/yaml` ja no desa res: amb `desa` és un 400 que envia a `/api/campanya/desa`.
- `POST /api/campanya/tanteig` (de campanya, i de candidat amb neudet real) no escriu res.
- `GET /api/campanyes` dona `estat_yaml` i `grup` per a cada campanya.
- La pàgina té els botons i els contenidors que el JS usa, i no torna a citar l'esborrany de simphy.
Els tests que necessiten neudet real (c04_draft i un candidat) es salten sense ell.
"""
from __future__ import annotations

import json
import shutil
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simphy.mcgen import design as D  # noqa: E402
from simui import campanya_form as CF  # noqa: E402
from simui import server  # noqa: E402

try:
    _REAL_NEUDET = D.neudet_root()
except D.DesignError:
    _REAL_NEUDET = None


@pytest.fixture(scope="module")
def url():
    srv = server.make_server("127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _req(url_base, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url_base + path, data=data, method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _json(url_base, path, body=None):
    code, raw = _req(url_base, path, body)
    return code, json.loads(raw)


@pytest.fixture
def neudet_tmp(tmp_path, monkeypatch):
    """NEUDET_ROOT temporal: `src/neudet/disseny` (per a `neudet_root()`), `disseny/campanyes/` amb c04 copiat."""
    root = tmp_path / "neudet"
    (root / "src" / "neudet" / "disseny").mkdir(parents=True)
    (root / "disseny" / "campanyes").mkdir(parents=True)
    if _REAL_NEUDET is not None and (_REAL_NEUDET / CF.C04_YAML).exists():
        d = root / "disseny" / "campanyes" / "c04_draft"
        d.mkdir()
        (d / "campanya.yaml").write_text(CF.to_yaml(_form("c04_draft")), encoding="utf-8")
    monkeypatch.setenv("NEUDET_ROOT", str(root))
    return root


def _arbre(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
            for p in sorted(root.rglob("*"))}


_FORM_C04: dict = {}
try:                                  # amb el neudet real, abans que cap fixture canviï NEUDET_ROOT (la traducció a tongades el necessita)
    if _REAL_NEUDET is not None and (_REAL_NEUDET / CF.C04_YAML).exists():
        _FORM_C04.update(CF.de_fitxer(_REAL_NEUDET / CF.C04_YAML))
except Exception:                     # noqa: BLE001
    pass


def _form(id_: str) -> dict:
    import copy
    f = copy.deepcopy(_FORM_C04)
    f["id"] = id_
    return f


# ── la pàgina ───────────────────────────────────────────────────────────────

def test_pagina_te_desa_tanteja_i_llista_amb_altres(url):
    code, raw = _req(url, "/")
    html = raw.decode()
    assert code == 200
    for ident in ('id="c-desa"', 'id="n-camps"', 'id="d-tanteja"'):
        assert ident in html, ident
    assert 'id="n-altres"' in html and "altres campanyes" in html   # les «altres» van plegades
    assert "Desa la proposta" in html and 'data-k="tanteja"' in html
    assert "/api/campanya/desa" in html and "/api/campanya/tanteig" in html
    assert "campanyes_esborrany" not in html and "esborrany desat" not in html


# ── desar ───────────────────────────────────────────────────────────────────

def test_desa_per_http_sense_certificacio_refusa_i_no_escriu(url, neudet_tmp):
    """Sense script de certificació a neudet (ni torch), la proposta no es desa: el motiu és el de neudet."""
    antes = _arbre(neudet_tmp)
    code, body = _json(url, "/api/campanya/desa", {"form": _form("c05_prova")})
    assert code == 400
    assert "no certifica" in body["error"] and "comprova_campanya.py" in body["error"]
    assert _arbre(neudet_tmp) == antes


@pytest.mark.parametrize("id_", ["../x", "C05", "c"])
def test_desa_per_http_id_dolent_es_400(url, neudet_tmp, id_):
    antes = _arbre(neudet_tmp)
    code, body = _json(url, "/api/campanya/desa", {"form": _form(id_)})
    assert code == 400 and "id de campanya no vàlid" in body["error"]
    assert _arbre(neudet_tmp) == antes


def test_desa_per_http_no_sobreescriu_una_campanya_que_no_es_proposta(url, neudet_tmp):
    d = neudet_tmp / "disseny" / "campanyes" / "c04_draft"
    antes = _arbre(neudet_tmp)
    code, body = _json(url, "/api/campanya/desa", {"form": _form("c04_draft")})
    assert code == 400 and "no es modifica mai una campanya existent" in body["error"]
    assert _arbre(neudet_tmp) == antes and d.exists()


def test_desa_per_http_amb_certificacio_escriu_els_dos_fitxers(url, neudet_tmp, monkeypatch):
    from simui import campanya_check as CC
    monkeypatch.setattr(CC, "certifica_proposta", lambda y, i: {
        "campanya": i, "fitxa": 1, "draft": True, "etapes": {}, "elements": [], "atura": False})
    code, r = _json(url, "/api/campanya/desa", {"form": _form("c05_prova")})
    assert code == 200, r
    assert r["missatge"] == "campanya `c05_prova` proposta" and r["estat"] == "proposta"
    d = neudet_tmp / "disseny" / "campanyes" / "c05_prova"
    assert sorted(p.name for p in d.iterdir()) == ["campanya.yaml", "comprova.json"]
    assert "estat: proposta" in (d / "campanya.yaml").read_text(encoding="utf-8")


def test_yaml_amb_desa_es_400_i_no_escriu(url, neudet_tmp):
    antes = _arbre(neudet_tmp)
    code, body = _json(url, "/api/campanya/yaml", {"form": _form("c05_prova"), "desa": True})
    assert code == 400 and "/api/campanya/desa" in body["error"]
    assert _arbre(neudet_tmp) == antes


def test_yaml_en_viu_retorna_el_text_i_no_escriu(url, neudet_tmp):
    antes = _arbre(neudet_tmp)
    code, body = _json(url, "/api/campanya/yaml", {"form": _form("c05_prova")})
    assert code == 200 and body["yaml"].startswith("# Esborrany generat per simphy")
    assert _arbre(neudet_tmp) == antes


# ── llista i tanteig ────────────────────────────────────────────────────────

def test_campanyes_per_http_donen_estat_yaml_i_grup(url, neudet_tmp):
    code, body = _json(url, "/api/campanyes")
    assert code == 200
    rows = {r["id"]: r for r in body["campanyes"]}
    assert "c04_draft" in rows
    assert rows["c04_draft"]["grup"] == "principal" and rows["c04_draft"]["estat_yaml"] == "jutjada"
    assert rows["c04_draft"]["estat_manifest"] == "draft"


def test_tanteig_de_campanya_per_http_no_escriu(url, neudet_tmp):
    if _REAL_NEUDET is None:
        pytest.skip("neudet no és present")
    antes = _arbre(neudet_tmp)
    code, r = _json(url, "/api/campanya/tanteig", {"de": "c04_draft"})
    assert code == 200, r
    assert r["id"] == "c04b_draft" and r["form"]["id"] == "c04b_draft" and r["form"]["estat"] == "proposta"
    assert _arbre(neudet_tmp) == antes


def test_tanteig_sense_de_es_400(url, neudet_tmp):
    code, body = _json(url, "/api/campanya/tanteig", {})
    assert code == 400 and "de" in body["error"]


def test_tanteig_de_campanya_inexistent_es_400(url, neudet_tmp):
    code, body = _json(url, "/api/campanya/tanteig", {"de": "c09_no"})
    assert code == 400 and "no trobo la campanya" in body["error"]


def test_tanteig_de_candidat_per_http_es_una_llista(url):
    """Amb neudet real (sense tocar-lo): un candidat vàlid de c04 S1 es torna com a etapa `llista`."""
    if _REAL_NEUDET is None:
        pytest.skip("neudet no és present")
    try:
        D._neudet()
        from neudet.disseny.campanya import Campanya
    except Exception as e:                       # noqa: BLE001
        pytest.skip(f"neudet no importable: {e}")
    h = Campanya(_REAL_NEUDET / "disseny" / "campanyes" / "c04_draft").candidats("S1")[0][0][0].hash()
    code, r = _json(url, "/api/campanya/tanteig", {"de": "c04_draft", "hash": h})
    assert code == 200, r
    assert r["etapa"] == "llista_S1" and r["candidat"]["hash"] == h
    assert r["form"]["etapes"]["llista_S1"]["tongades"][0]["posicions"]["font"] == "punts"
