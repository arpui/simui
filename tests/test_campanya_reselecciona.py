"""REAVALUA-UI, pas 1: `campanya_reselecciona.reselecciona` torna a presentar els candidats d'una etapa amb altres criteris, sense simular.

Test bessó: amb els criteris de la campanya, la frontera i els guanyadors de l'ε-restricció són EXACTAMENT els del `resum.md` que va escriure
neudet quan va córrer l'etapa."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from simui import campanya_reselecciona as R
from simui import campanya_vista as CV
from simphy.mcgen import design as DES


def _arrel():
    try:
        return DES.neudet_root() / "disseny" / "campanyes"
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def _parseja(txt: str):
    fr, gu = [], {}
    i = txt.find("## Frontera de Pareto")
    if i >= 0:
        tab = []
        for l in txt[i:].splitlines()[1:]:
            if l.startswith("|"):
                tab.append(l)
            elif tab:
                break
        fr = [[x.strip() for x in l.strip("|").split("|")][0] for l in tab[2:]]
    m = re.search(r"## ε-restricció.*?\n\n(.*?)(?:\n\n|$)", txt, re.S)
    if m:
        for l in m.group(1).splitlines()[2:]:
            c = [x.strip() for x in l.strip("|").split("|")]
            gu[float(c[0])] = None if c[1] == "cap" else c[1]
    return fr, gu


def test_amb_els_criteris_de_la_campanya_surt_el_mateix_que_va_escriure_neudet():
    arrel = _arrel()
    n = 0
    for rs in sorted(arrel.glob("*/etapes/*/resum.md")):
        camp, et = rs.parts[-4], rs.parts[-2]
        if not (rs.parent / "candidats.csv").is_file():
            continue
        fr, gu = _parseja(rs.read_text(encoding="utf-8"))
        if not gu or not fr:
            continue
        try:
            r = R.reselecciona(camp, et)
        except ValueError:                                    # una etapa d'abans amb altres mètriques (res_E a c02 S0): no comparable
            continue
        n += 1
        assert {f["nom"] for f in r["frontera"]} == set(fr), (camp, et)
        assert {g["c"]: (None if g["cap"] else g["nom"]) for g in r["guanyadors"]} == gu, (camp, et)
    if not n:
        pytest.skip("no hi ha cap etapa amb resum.md i candidats.csv")


def test_canviar_c_i_afegir_una_restriccio_dura_reordena_sense_escriure_res():
    arrel = _arrel()
    if not (arrel / "c01_8tubs_30x30x80" / "etapes" / "S0" / "candidats.csv").is_file():
        pytest.skip("no hi ha c01 S0")
    abans = sorted(p.stat().st_mtime for p in (arrel / "c01_8tubs_30x30x80" / "etapes" / "S0").iterdir())
    base = R.reselecciona("c01_8tubs_30x30x80", "S0")
    nou = R.reselecciona("c01_8tubs_30x30x80", "S0", {"c": [0.15, 0.4]})
    assert [g["c"] for g in nou["guanyadors"]] == [0.15, 0.4]
    assert nou["guanyadors"][0]["nom"] == "S0_r7_t45" and nou["guanyadors"][1]["nom"] == "S0_r3_t0"     # el de més ε̄ amb cv ≤ c
    amb = R.reselecciona("c01_8tubs_30x30x80", "S0", {"restriccions": [["eps_min", ">=", 0.055]]})
    assert amb["n_fora_restriccions"] > 0 and amb["n_valids"] == base["n_valids"] - amb["n_fora_restriccions"]
    assert any("restriccions dures" in a for a in amb["avisos"])
    assert sorted(p.stat().st_mtime for p in (arrel / "c01_8tubs_30x30x80" / "etapes" / "S0").iterdir()) == abans


def test_diu_en_paraules_el_que_no_es_pot_fer():
    _arrel()
    with pytest.raises(ValueError, match="no té candidats.csv"):
        R.reselecciona("c01_8tubs_30x30x80", "no_existeix")
    with pytest.raises(ValueError, match="no té la mètrica"):
        R.reselecciona("c01_8tubs_30x30x80", "S0", {"objectius": [["eps_mitja", "max"], ["inventada", "min"]]})
    with pytest.raises(ValueError):
        R.reselecciona("c01_8tubs_30x30x80", "../S0")


def test_les_etapes_amb_cribratge_ho_diuen():
    arrel = _arrel()
    if not (arrel / "c03_3anells_grups" / "etapes" / "S3" / "candidats.csv").is_file():
        pytest.skip("no hi ha c03 S3")
    r = R.reselecciona("c03_3anells_grups", "S3")
    assert r["n_cribratge"] > 0 and any("cribratge" in a for a in r["avisos"])


def test_l_endpoint_i_la_pagina_porten_el_panell_de_criteris():
    from simui import api
    from simui import server as S
    _arrel()
    r = api.campanya_reselecciona({"id": "c01_8tubs_30x30x80", "etapa": "S0", "criteris": {"c": [0.25]}})
    assert [g["c"] for g in r["guanyadors"]] == [0.25] and r["frontera"]
    assert "/api/campanya/reselecciona" in Path(S.__file__).read_text(encoding="utf-8")
    pagina = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")
    for tros in ("function kReavHtml", "function kReavForm", "function kReavRes", "/api/campanya/reselecciona", "només lectura: no simula ni escriu res",
                 "Criteris aplicats", "(modificats respecte als de la campanya)", "torna als criteris de la campanya", "Només <code>hits</code>"[:0] or "restriccions dures"):
        assert tros in pagina, tros
