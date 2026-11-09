"""Font per defecte (contracte UI §19): una campanya nova porta la font a fora; les plantilles velles, l'avís «font dins del bloc»."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from simui import campanya_form as CF
from simphy.mcgen import design as DES

INDEX = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")


def _neudet():
    try:
        DES.neudet_root()
        DES._neudet()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def test_font_per_defecte_es_la_del_contracte_19():
    assert CF.font_defecte([30, 30, 80]) == {"tipus": "iso", "pos_cm": [0, 0, -45]}         # −(80/2 + 5)
    assert CF.font_defecte([30, 30, 21])["pos_cm"] == [0, 0, -15.5]


def test_sense_mides_no_s_inventa_res():
    with pytest.raises(DES.DesignError):
        CF.font_defecte([30, 30])


def test_avis_dins_i_sobre_la_cara():
    d = {"bloc": {"mides_cm": [30, 30, 80]}, "font": {"tipus": "iso", "pos_cm": [0, 0, 0]}}
    assert CF.font_avis(d) == "dins"
    d["font"]["pos_cm"] = [0, 0, -40]
    assert CF.font_avis(d) == "cara"
    d["font"]["pos_cm"] = [0, 0, -40.05]
    assert CF.font_avis(d) == "cara"
    d["font"]["pos_cm"] = [0, 0, -45]
    assert CF.font_avis(d) is None
    assert CF.font_avis({**d, "font": {"tipus": "feix"}}) is None


def test_la_plantilla_per_defecte_a_fora_no_te_avis():
    d = {"bloc": {"mides_cm": [30, 30, 80]}, "font": CF.font_defecte([30, 30, 80])}
    assert CF.font_avis(d) is None


def test_la_plantilla_antiga_c04_draft_obre_amb_avis_font_dins():
    _neudet()
    dom = CF.defaults()["domini"]
    if dom["font"].get("tipus") != "iso" or CF.font_avis(dom) != "dins":
        pytest.skip(f"la font de c04_draft ja no és dins del bloc: {dom['font']}")
    assert CF.font_avis(dom) == "dins"


def test_el_schema_porta_la_distancia_del_contracte():
    _neudet()
    d = CF.schema()["font"]["defecte"]
    assert d["cara_cm"] == 5 and d["entre"] == "buit"


def test_la_ui_porta_el_boto_i_no_toca_una_font_moguda():
    assert 'data-act="fontfora"' in INDEX and "posa-la a fora (per defecte)" in INDEX
    assert "!CP.fontMoguda" in INDEX                                  # el recalcul amb les mides només si l'usuari no l'ha moguda
    assert "CP.fontMoguda = true" in INDEX


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar les funcions pures de la UI")
def test_les_funcions_js_donen_el_mateix_que_les_python():
    src = INDEX.split("// FONT-DEF-BEGIN")[1].split("\n", 1)[1].split("// FONT-DEF-END")[0]
    casos = [([30, 30, 80], [0, 0, 0]), ([30, 30, 80], [0, 0, -40]), ([30, 30, 80], [0, 0, -45]), ([10, 20, 30], [4, 9, 14]),
             ([30, 30, 80], [16, 0, 0])]
    js = src + "const out = " + json.dumps(casos) + ".map(([m, p]) => [cFontDefecte(m, 5).pos_cm, cFontAvis({bloc: {mides_cm: m}, font: {tipus: 'iso', pos_cm: p}}, 0.1)]); console.log(JSON.stringify(out));"
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    for (m, p), (pos, av) in zip(casos, json.loads(r.stdout)):
        assert pos == CF.font_defecte(m)["pos_cm"]
        assert av == CF.font_avis({"bloc": {"mides_cm": m}, "font": {"tipus": "iso", "pos_cm": p}})
