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


def _cost_html(opc):
    f = INDEX.split("function cCostHtml(opc){")[1].split("\n}\n")[0]
    js = ("const escD = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');"
          "function cCostHtml(opc){" + f + "\n}\nconsole.log(JSON.stringify(cCostHtml(" + json.dumps(opc) + ")));")
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
