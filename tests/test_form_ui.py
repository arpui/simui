"""FORM-UI (contracte §15): cada número amb la seva fórmula, i la fórmula és de neudet; la UI no en escriu cap."""
from __future__ import annotations

from pathlib import Path

import pytest

from simui import campanya_reselecciona as RES
from simui import campanya_vista as CV
from simphy.mcgen import design as DES
from simui import api

INDEX = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")


def _neudet():
    try:
        DES.neudet_root()
        DES._neudet()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")
    from neudet.disseny import objectius
    return objectius


def test_les_formules_de_les_metriques_son_les_de_taula_objectius_de_neudet():
    obj = _neudet()
    fm = CV.formules_metriques()
    assert fm and all(fm[n] == m["formula"] for n, m in obj.taula_objectius()["metriques"].items() if n in fm)
    assert "eps_mitja" in fm and "cv" in fm


def test_la_vista_i_el_reselecciona_porten_les_formules():
    _neudet()
    camp = DES.neudet_root() / "disseny" / "campanyes" / "c01_8tubs_30x30x80"
    if not (camp / "etapes" / "S0" / "candidats.csv").is_file():
        pytest.skip("no hi ha c01 S0")
    assert set(CV.formules_metriques()) >= {"eps_mitja", "cv"}
    r = RES.reselecciona("c01_8tubs_30x30x80", "S0")
    assert set(r["formules"]) == {"eps_mitja", "cv"} and r["formules"]["cv"] == CV.formules_metriques()["cv"]


def test_les_formules_d_una_etapa_amb_els_valors_de_la_tanda_son_les_de_neudet():
    _neudet()
    camp = DES.neudet_root() / "disseny" / "campanyes" / "c0_2anells" / "etapes" / "S1"
    if not (camp / "resultats_tub.json").is_file():
        pytest.skip("no hi ha c0_2anells S1")
    from neudet.disseny.formules import formules_etapa
    esperat = formules_etapa(camp, tubs=False)
    r = api.campanya_formules("c0_2anells", "S1", "")
    assert r["disponible"] and r["generals"] == esperat["generals"]
    fila = r["candidat"]["per_energia"][0]
    assert fila["eps"].startswith("ε = C/N = ") and str(fila["C"]) in fila["eps"] and str(fila["N"]) in fila["eps"]      # amb els números d'aquella tanda
    h = r["candidats"][-1]["hash"]
    assert api.campanya_formules("c0_2anells", "S1", h)["candidat"]["hash"] == h


def test_una_etapa_sense_resultats_ho_diu_i_no_peta():
    _neudet()
    camp = DES.neudet_root() / "disseny" / "campanyes" / "c01_8tubs_30x30x80" / "etapes" / "S0"
    if (camp / "resultats_tub.json").is_file():
        pytest.skip("c01 S0 té resultats_tub.json")
    r = api.campanya_formules("c01_8tubs_30x30x80", "S0", "")
    assert r["disponible"] is False and "resultats_tub" in r["motiu"]
    with pytest.raises(ValueError):
        api.campanya_formules("c01_8tubs_30x30x80", "../S0", "")


def test_la_pagina_mostra_la_formula_a_tot_arreu_sense_escriure_cap():
    for tros in ("function kFormMetr", "function kFormEtapaHtml", "Com s'han calculat les xifres", "/api/campanya/formules",
                 "formules_metriques", "Fórmules d'aquestes mètriques", "'ordena' + (c.formula ? ' · ' + c.formula : '')",
                 "(T.metriques[r[0]] || {}).formula"):
        assert tros in INDEX, tros
    assert "ε̄ = Σ" not in INDEX and "cv = √" not in INDEX            # cap fórmula escrita a la pàgina: totes vénen de neudet
