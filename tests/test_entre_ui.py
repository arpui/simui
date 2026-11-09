"""ENTRE-UI (contracte UI §17): domini.entre, humitat i temperatura; el que dona neudet es mostra tal com ve."""
from __future__ import annotations

import copy
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


def _dom(**kw):
    d = {"bloc": {"mides_cm": [30, 30, 80]}, "font": CF.font_defecte([30, 30, 80])}
    d.update(kw)
    return d


def test_entre_per_defecte_es_buit_i_no_demana_res():
    assert CF._errors_entre(_dom()) == [] and CF._errors_entre(_dom(entre="buit")) == []


def test_aire_no_porta_humitat_ni_temperatura():
    assert CF._errors_entre(_dom(entre="aire")) == []
    assert CF._errors_entre(_dom(entre="aire", humitat_relativa_pct=50))                   # només amb aire_humit


def test_aire_humit_demana_hr_i_t_dins_dels_rangs_del_contracte():
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=50, temperatura_C=20)) == []
    assert len(CF._errors_entre(_dom(entre="aire_humit"))) == 2                            # sense valor implícit
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=101, temperatura_C=20))
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=-1, temperatura_C=20))
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=50, temperatura_C=51))
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=50, temperatura_C=-41))
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=0, temperatura_C=-40)) == []
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=100, temperatura_C=50)) == []


def test_un_entre_desconegut_es_error():
    assert CF._errors_entre(_dom(entre="sala"))


def test_mon_mig_cm_opcional_i_positiu():
    f = {"verificacio": {"mon_mig_cm": 0}}
    assert any("mon_mig_cm" in x for x in CF._errors({**f, "domini": {}}))
    assert not any("mon_mig_cm" in x for x in CF._errors({"verificacio": {"mon_mig_cm": 110}, "domini": {}}))
    assert not any("mon_mig_cm" in x for x in CF._errors({"verificacio": {}, "domini": {}}))


def test_entre_info_diu_d_on_ve_cada_valor():
    i = CF.entre_info()
    assert set(i["valids"]) >= {"buit"} and i["font_valids"]
    assert i["humitat_relativa_pct"]["defecte"] == 50 and i["temperatura_C"]["defecte"] == 20
    assert (i["humitat_relativa_pct"]["min"], i["humitat_relativa_pct"]["max"]) == (0, 100)


def test_divergencia_neudet_contracte_en_els_rangs_i_valors():
    """Quan neudet publica ENTRE_VALIDS i el rang de T, han de dir el mateix que el contracte §17."""
    _neudet()
    i = CF.entre_info()
    if i["font_valids"] == CF.ENTRE_FONT_CONTRACTE:
        pytest.skip("neudet no publica ENTRE_VALIDS: espera el pull de neudet")
    assert tuple(i["valids"]) == CF.ENTRE_CONTRACTE
    if "constants_mf" in i["temperatura_C"]["font"]:
        assert (i["temperatura_C"]["min"], i["temperatura_C"]["max"]) == (CF.ENTRE_T["min"], CF.ENTRE_T["max"])


def test_el_yaml_porta_entre_i_humitat_a_domini():
    _neudet()
    f = copy.deepcopy(CF.defaults())
    f["domini"].update(entre="aire_humit", humitat_relativa_pct=50, temperatura_C=20)
    y = CF.to_yaml(f)
    assert "entre: aire_humit" in y and "humitat_relativa_pct: 50" in y and "temperatura_C: 20" in y


def test_la_ui_mostra_el_selector_i_els_camps_nomes_amb_la_font_a_fora():
    assert "function cEntreHtml" in INDEX and "cFontAvis(d" in INDEX.split("function cEntreHtml")[1].split("function cEntreCanvi")[0]
    assert "domini.humitat_relativa_pct" in INDEX and "domini.temperatura_C" in INDEX and "'aire_humit': 'aire humit'" not in INDEX
    assert "aire_humit: 'aire humit'" in INDEX and "cEntreCanvi(v)" in INDEX


def test_la_ui_no_escriu_l_avis_de_dispersio_el_filtra_del_resum_de_neudet():
    assert "dispersió a l'aire" in INDEX and INDEX.count("l'aire no és la sala") == 0


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node")
def test_kEntreHtml_mostra_els_valors_de_neudet_tal_com_venen_i_l_avis_del_resum():
    f = INDEX.split("function kEntreHtml(v){")[1].split("\nfunction cFontHtml")[0]
    js = ("const escD = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;'); const ENTRE_TXT = {buit: 'buit', aire: 'aire', aire_humit: 'aire humit'};"
          "function kEntreHtml(v){" + f + "\nconst v = __V__; console.log(JSON.stringify([kEntreHtml(v), kEntreHtml({entre: {entre: 'buit'}}), kEntreHtml({entre: null})]));")
    v = {"entre": {"entre": "aire_humit", "humitat_relativa_pct": 50, "temperatura_C": 20, "fraccio_h2o_massa": 0.00731, "rho_gcm3": 0.001199},
         "certificacio": {"resum_text": "Altres línies\nNota: la dispersió a l'aire es negligeix (≤ 0,9 % a 1 MeV en 50 cm); l'aire no és la sala.\nfi"}}
    r = subprocess.run(["node", "-e", js.replace("__V__", json.dumps(v))], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    h, buit, res = json.loads(r.stdout)
    assert "0.00731" in h and "0.001199" in h and "aire humit" in h and "HR" not in h
    assert "la dispersió a l'aire es negligeix (≤ 0,9 % a 1 MeV en 50 cm); l'aire no és la sala." in h
    assert buit == "" and res == ""
    # sense l'avís al resum, no se n'escriu cap
    v["certificacio"] = {"resum_text": "res"}
    h2 = json.loads(subprocess.run(["node", "-e", js.replace("__V__", json.dumps(v))], capture_output=True, text=True).stdout)[0]
    assert "negligeix" not in h2
