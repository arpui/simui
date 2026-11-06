"""OBJ (neudet `docs/site/encarrecs/2026-11-06_OBJ_finalitat_objectius.md`, contracte UI §14): el bloc «Objectius» del formulari és
1 Finalitat · 2 Què decideix · 3 Què s'informa · 4 Com es tria · 5 Com es pondera l'energia. Les frases i els valors per defecte són de
neudet (`taula_objectius`); què vol dir i els avisos (un sol canal…), també (`/api/campanya/objectius`)."""
import copy
from pathlib import Path

import pytest
import yaml

from simphy.mcgen import campanya_check as CC
from simphy.mcgen import campanya_form as CF
from simphy.mcgen import design as DES

INDEX = (Path(__file__).resolve().parents[1] / "src" / "simphy" / "ui" / "static" / "index.html").read_text()


def _neudet():
    try:
        root = DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")
    DES._neudet()
    from neudet.disseny import objectius
    if not hasattr(objectius, "taula_objectius"):
        pytest.skip("aquest neudet encara no té OBJ (taula_objectius)")
    return root


def _form(objectius):
    f = copy.deepcopy(CF.defaults())
    f.pop(CF.CONVERSIO, None)
    f["objectius"] = objectius
    return f


# ── forma (to_yaml, sense neudet) ────────────────────────────────────────────
def test_cicle_nou_passa_la_forma_i_es_llegeix_igual():
    ob = {"finalitat": "comptador", "objectius": [["eps_mitja", "max"], ["cv", "min"]], "informatives": "auto",
          "preferencia": {"maxim": "eps_mitja", "sobre": "cv", "c": [0.1, 0.2]}, "restriccions": [["eps_min", ">=", 0.2]],
          "pesos": "letargia", "energies_MeV": "totes", "pareto_k_sigma": 2}
    y = yaml.safe_load(CF.to_yaml(_form(ob)))
    assert y["objectius"] == ob


@pytest.mark.parametrize("ob, frase", [
    ({"finalitat": "detector"}, "objectius.finalitat: cal comptador o espectrometre"),
    ({"finalitat": "comptador", "objectius": [["res_E", "min"]]}, "no és de la finalitat comptador"),
    ({"finalitat": "comptador", "metriques": ["cv"]}, "ja no es fan servir"),
    ({"finalitat": "comptador", "restriccions": [["eps_min", "=>", 0.2]]}, "l'operador és"),
    ({"finalitat": "comptador", "pesos": {"espectre": ""}}, "objectius.pesos.espectre"),
    ({"finalitat": "espectrometre", "grups_MeV": [[1, 0.1]]}, "objectius.grups_MeV"),
    ({"finalitat": "comptador", "preferencia": {"c": ["a"]}}, "objectius.preferencia.c"),
    ({"objectius": [["eps_mitja", "max"]]}, "objectius.finalitat"),
])
def test_errors_de_forma(ob, frase):
    with pytest.raises(CF.FormError, match=frase):
        CF.to_yaml(_form(ob))


def test_el_cicle_d_abans_es_valida_com_sempre():
    ob = {"metriques": ["eps_mitja", "cv"], "pareto": [["eps_mitja", "max"], ["cv", "min"]], "pesos": "letargia"}
    assert yaml.safe_load(CF.to_yaml(_form(ob)))["objectius"] == ob


# ── la taula és la de neudet ─────────────────────────────────────────────────
def test_schema_porta_la_taula_de_neudet():
    _neudet()
    from neudet.disseny.objectius import taula_objectius
    s = CF.schema()["objectius"]["cicle_nou"]
    t = taula_objectius()
    assert {k: v for k, v in s.items() if k not in ("fitxer", "linia")} == t
    assert {k: tuple(v["metriques"]) for k, v in t["finalitats"].items()} == CF.FINALITAT_METRIQUES
    assert s["fitxer"] == CF.OBJECTIUS_PY and "def taula_objectius()" in CF._linia(CF.OBJECTIUS_PY, s["linia"], "def taula_objectius()")


def test_les_linies_d_objectius_py_son_exactes():
    """Les línies citades contenen el que diuen (sense haver de buscar-les a prop)."""
    root = _neudet()
    L = (root / "src" / "neudet" / "disseny" / "objectius.py").read_text().splitlines()
    for nom, n in CF.METRIQUES_LINIA.items():
        assert f'"{nom}"' in L[n - 1], nom
    for n, tok in ((CF.AUTO_LINIA, "for n in [p[0] for p in self.pareto]"), (CF.SENTITS_LINIA, '"max"'),
                   (CF.PESOS_DEFECTE_LINIA, 'cfg.get("pesos", "uniforme")'), (CF.K_SIGMA_LINIA, "pareto_k_sigma"),
                   (CF.ENERGIES_LINIA, 'sel == "totes"'), (CF.RESTRICCIO_LINIA, 'cfg.get("restriccio")'),
                   (CF.FINALITATS_LINIA, "FINALITATS"), (CF.TAULA_LINIA, "def taula_objectius")):
        assert tok in L[n - 1], (n, tok)


# ── què n'entén neudet (en viu) ──────────────────────────────────────────────
def test_objectius_comptador_en_paraules():
    _neudet()
    r = CC.objectius(CF.to_yaml(_form({"finalitat": "comptador"})), "S1")
    assert r["cicle"] == "nou" and r["finalitat"] == "comptador" and r["avisos"] == []
    assert r["en_paraules"].startswith("Finalitat: comptador")
    assert r["objectius"] == [["eps_mitja", "max"], ["cv", "min"]]


def test_espectrometre_un_sol_anell_es_error_en_vermell():
    _neudet()
    f = _form({"finalitat": "espectrometre"})
    anells = f["etapes"]["S1"]["tongades"][0]["posicions"]["anells"]
    del anells[1:]
    r = CC.objectius(CF.to_yaml(f), "S1")
    e = [a for a in r["avisos"] if a["codi"] == "un_sol_canal"]
    assert e and e[0]["nivell"] == "error"
    assert "amb un sol canal no es pot dir l'energia: cal Cd en alguns tubs o tubs a radis diferents" in e[0]["text"]
    assert r["canals"]["S1"]["max"] == 1


def test_espectrometre_err_grups_sense_grups_proposa_els_de_c03():
    _neudet()
    r = CC.objectius(CF.to_yaml(_form({"finalitat": "espectrometre", "objectius": [["eps_mitja", "max"], ["err_grups", "min"]]})), "S1")
    a = next(x for x in r["avisos"] if x["codi"] == "err_grups_sense_grups")
    assert a["nivell"] == "error" and "els de c03" in a["text"]


def test_cicle_d_abans_sense_avisos():
    _neudet()
    r = CC.objectius(CF.to_yaml(_form({"metriques": ["eps_mitja", "cv"], "pareto": [["eps_mitja", "max"], ["cv", "min"]]})), "S1")
    assert r["cicle"] == "llegat" and r["finalitat"] is None and r["avisos"] == []


# ── la pàgina ────────────────────────────────────────────────────────────────
def test_la_pagina_te_el_bloc_numerat_i_no_la_llista_plana():
    for t in ("1 · Finalitat", "2 · Què decideix", "3 · Què s'informa", "4 · Com es tria", "5 · Com es pondera l'energia"):
        assert t in INDEX, t
    assert 'data-p="objectius.metriques"' not in INDEX                 # fora la llista plana de 14
    assert "/api/campanya/objectius" in INDEX and "data-fin=" in INDEX and "cObjNou('comptador'" in INDEX


def test_espectrometre_sense_cd_diu_no_aplica_sense_bloquejar():
    """OBJ·espectre (b): dos anells sense Cd → q_rang, q_monoton i sE_N «no aplica» (info), cap error."""
    _neudet()
    from neudet.disseny import objectius
    if not hasattr(objectius, "NO_APLICA"):
        pytest.skip("aquest neudet encara no té OBJ·espectre")
    r = CC.objectius(CF.to_yaml(_form({"finalitat": "espectrometre"})), "S1")
    na = [a for a in r["avisos"] if a["codi"] == "no_aplica"]
    assert na and na[0]["nivell"] == "info" and objectius.NO_APLICA_TEXT in na[0]["text"]
    assert not [a for a in r["avisos"] if a["nivell"] == "error"]
    assert "data-objavis=\"no_aplica\"" in INDEX
