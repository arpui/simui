"""opcions_cost (contracte UI §11b, AFINA-N) i impossibles d'INV (§10c): la UI mostra el que dona neudet, no n'aplica res."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from simui import campanya_form as CF
from simphy.mcgen import design as DES

INDEX = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")
OPCIO = {"camp": "cerca.n_inicial", "valor": 4000, "per_que": "gpu", "gpu_h": 6.5, "disc_gb": None, "porta_disc_gb": 12.0,
         "cpu_g4_h": 3.0, "durada_h": 7.1, "en_paraules": "Amb cerca.n_inicial 4000 la xarxa costa 6,5 h de GPU."}


_BLOC = ("const escD = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');"
         "function cCostBlocks(opc){"
         + INDEX.split("function cCostBlocks(opc){")[1].split("// Després de desar, neudet encara no ha respost")[0])


def _cost_html(opc):
    js = _BLOC + "console.log(JSON.stringify(cCostHtml(" + json.dumps(opc) + ")));"
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)


def _cost_blocs(opc):
    js = _BLOC + "console.log(JSON.stringify(cCostBlocks(" + json.dumps(opc) + ")));"
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node")
def test_opcions_cost_mostra_la_frase_i_els_numeros_de_neudet_i_diu_que_no_bloqueja():
    h = _cost_html([OPCIO])
    assert "Amb cerca.n_inicial 4000 la xarxa costa 6,5 h de GPU." in h
    assert "cerca.n_inicial" in h and "6.5 h GPU" in h and "12 GB de disc a tenir lliure" in h and "7.1 h de durada" in h
    assert "GB de disc</" not in h.replace("a tenir lliure (porta)", "")          # disc_gb és null: no s'escriu cap 0 ni «null»
    assert "null" not in h
    assert "no bloqueja res" in h and "no n'aplica cap" in h


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node")
def test_opcions_cost_sense_opcions_no_pinta_res():
    assert _cost_html([]) == "" and _cost_html(None) == ""
    assert _cost_blocs({}) == "" and _cost_blocs(None) == "" and _cost_blocs({"S1": []}) == ""


def test_neudet_ho_dona_en_dues_formes_i_ahi_queda_escrit():
    """Bessó (UI-COST-AVIS, 2026-11-12, amb dades provocades a `~/projects/wt/neudet_UI-COST`): a l'arrel del
    `comprova.json` neudet porta **un diccionari per etapa** (`{etapa: [opcions]}`) i a dins de cada etapa, una
    **llista**. La pàgina ha de entendre les dues; si ells canvien la forma, aquesta prova ho dirà."""
    try:
        root = DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")
    s = (root / "scripts" / "disseny" / "comprova_campanya.py").read_text(encoding="utf-8")
    rp = (root / "src" / "neudet" / "disseny" / "resum_peticio.py").read_text(encoding="utf-8")
    assert 'oc = {nom:' in s and 'informe["opcions_cost"] = oc' in s        # l'arrel: dict per etapa
    assert 'peticio["cost"]["opcions_cost"] = opcions_cost(' in rp          # l'etapa: llista


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node")
def test_el_diccionari_per_etapa_també_es_pinta_amb_la_frase_de_neudet():
    """Era el forat: amb el dict de l'arrel el `cCostHtml` de sempre no pintava res (no té `.length`)."""
    h = _cost_blocs({"S1": [OPCIO], "S2": []})
    assert "Massa gran per a un tanteig (etapa S1)" in h
    assert "Massa gran per a un tanteig (etapa S2)" not in h                # buida: cap panell
    assert OPCIO["en_paraules"] in h and "6.5 h GPU" in h and "no bloqueja res" in h
    assert _cost_blocs([OPCIO]) == _cost_html([OPCIO])                      # la forma llista, com abans


def test_cap_lloc_llegeix_el_diccionari_com_si_fos_una_llista():
    for crida in ("cCostHtml(c.opcions_cost)", "cCostHtml(r.opcions_cost)"):
        assert crida not in INDEX, f"{crida}: amb el dict per etapa de neudet no pinta res"
    assert INDEX.count("cCostBlocks(") >= 4                                 # definició + tres llocs on es pinta


def test_l_avís_de_cost_es_veu_també_a_la_pàgina_de_la_campanya():
    """UI-AFINA (4) volia veure'l; fins ara només sortia després de desar. La certificació de la campanya
    (`kCert`) és on hi ha el `comprova.json`: l'avís s'hi pinta igual, amb les opcions de neudet."""
    kcert = INDEX.split("function kCert(v){")[1].split("function kEtapa(e){")[0]
    assert "cCostBlocks(c.opcions_cost)" in kcert


def test_opcions_cost_no_s_aplica_sola():
    assert "opcions_cost.forEach" not in INDEX and "cSet(CP.f, o.camp" not in INDEX


def test_els_impossibles_d_inventari_es_mostren_amb_el_text_de_neudet():
    assert "e.error, e.en_paraules" in INDEX and "avisos_en_paraules" in INDEX


def test_verificacio_quants_i_n_per_energia_son_llegits_per_neudet_afina_n():
    try:
        DES.neudet_root()
        DES._neudet()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")
    v = CF._schema_verificacio()
    assert v["quants"]["llegit"] is True and v["n_per_energia"]["llegit"] is True and v["hits"]["llegit"] is True
    assert v["porta"]["llegit"] is False                                         # només una nota (§11b)
    assert "no el llegeix" not in json.dumps(v, ensure_ascii=False)
