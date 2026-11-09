"""DIAG-UI (contracte neudet simphy_ui.md §18): la casella «Diagnòstic», les energies per sobre del màxim, els ckpts per material
(la llista és de neudet/simnet, no de la UI) i l'avís «diagnòstic, no citable» a tot arreu on surt una xifra."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from simui import campanya_form as CF
from simui import campanya_vista as CV
from simphy.mcgen import design as DES
from simphy.mcgen import mc_sources as MS
from simphy.mcgen import results_tub as RT

INDEX = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")


def _form():
    try:
        DES.neudet_root()
        DES._neudet()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")
    f = copy.deepcopy(CF.defaults())
    f["objectius"]["energies_MeV"] = "totes"
    return f


@pytest.fixture
def simnet(tmp_path, monkeypatch):
    for m, noms in {"PE": ["BASELINE", "seed1_E12_ft1"], "He3": ["seed1_E12_ft1", "BASELINE", "seed2_R200"]}.items():
        for n in noms:
            d = tmp_path / "data" / "material" / m / "ckpt" / "neutro" / n
            d.mkdir(parents=True)
            (d / "ckpt_final.pt").write_bytes(b"x")
    (tmp_path / "data" / "material" / "Cd" / "ckpt" / "neutro" / "buit").mkdir(parents=True)     # sense ckpt_final.pt: no compta
    real = MS.owner_root
    monkeypatch.setattr(MS, "owner_root", lambda repo, root=None: tmp_path if repo == "simnet" else real(repo, root))
    return tmp_path


def test_els_ckpts_disponibles_son_els_directoris_de_simnet_amb_ckpt_final_baseline_primer(simnet):
    d = CF.ckpts_disponibles()
    assert d == {"He3": ["BASELINE", "seed1_E12_ft1", "seed2_R200"], "PE": ["BASELINE", "seed1_E12_ft1"]}


def test_sense_simnet_no_s_inventa_cap_llista(monkeypatch):
    monkeypatch.setattr(MS, "owner_root", lambda repo, root=None: None)
    assert CF.ckpts_disponibles() is None


def _domini(monkeypatch, **kw):
    g = {"min": 2.5e-08, "max": 5.0, "max_diagnostic": 12.0, "validat_PE_min": 2.5e-08, "per_defecte": [1.0], "nota": None, "font": "t"}
    g.update(kw)
    monkeypatch.setattr(CF, "energies_domini", lambda: g)
    return g


def test_energies_per_sobre_del_maxim_nomes_amb_diagnostic_i_fins_a_max_diagnostic(monkeypatch):
    """DIAG-UI2: el límit (12 MeV) és el que publica neudet a validacions.json; per sobre, prohibit també en diagnòstic."""
    _domini(monkeypatch)
    f = _form()
    f["domini"]["energies_MeV"] = [1.0, 12.0]
    with pytest.raises(CF.FormError, match="fora del domini permès"):
        CF.to_yaml(f)
    f["domini"]["diagnostic"] = True
    assert yaml.safe_load(CF.to_yaml(f))["domini"]["diagnostic"] is True        # 12 MeV: el límit mateix passa
    f["domini"]["energies_MeV"] = [1.0, 12.5]
    with pytest.raises(CF.FormError, match="fins a 12 MeV"):
        CF.to_yaml(f)
    f["domini"]["energies_MeV"] = [1e-9, 1.0]                                   # per sota del mínim, neudet encara ho prohibeix
    with pytest.raises(CF.FormError, match="fora del domini permès"):
        CF.to_yaml(f)


def test_sense_max_diagnostic_de_neudet_no_s_inventa_cap_limit(monkeypatch):
    _domini(monkeypatch, max_diagnostic=None)
    f = _form()
    f["domini"].update(diagnostic=True, energies_MeV=[1.0, 8.0])
    with pytest.raises(CF.FormError, match="no publica `max_diagnostic`"):
        CF.to_yaml(f)


def test_l_esquema_porta_el_max_diagnostic_del_registre_de_neudet(monkeypatch):
    g = _domini(monkeypatch)
    assert CF.schema()["diagnostic"]["max_diagnostic"] == g["max_diagnostic"] == 12.0
    assert CF.energies_domini is not None


def test_el_registre_real_de_neudet_si_publica_max_diagnostic_es_llegeix():
    _form()
    g = CF.energies_domini()
    if g is None or g.get("max_diagnostic") is None:
        pytest.skip("el validacions.json de neudet d'aquesta còpia encara no porta max_diagnostic (neudet ad8664b)")
    assert g["max_diagnostic"] > g["max"]


def test_diagnostic_ha_de_ser_booleà():
    f = _form()
    f["domini"]["diagnostic"] = "sí"
    with pytest.raises(CF.FormError, match="domini.diagnostic"):
        CF.to_yaml(f)


def test_ckpts_nomes_amb_diagnostic_i_de_la_llista_de_neudet(simnet):
    f = _form()
    f["avaluacio"] = {"ckpts": {"PE": "seed1_E12_ft1"}}
    with pytest.raises(CF.FormError, match="només amb domini.diagnostic"):
        CF.to_yaml(f)
    f["domini"]["diagnostic"] = True
    assert yaml.safe_load(CF.to_yaml(f))["avaluacio"]["ckpts"] == {"PE": "seed1_E12_ft1"}
    f["avaluacio"]["ckpts"] = {"PE": "no_existeix"}
    with pytest.raises(CF.FormError, match="neudet no el troba"):
        CF.to_yaml(f)


def test_bessó_la_plantilla_no_porta_diagnostic_ni_ckpts():
    """Regla del test bessó: cap check nou no pot bloquejar la plantilla tal com s'ensenya."""
    f = _form()
    assert "diagnostic" not in f["domini"] and "ckpts" not in (f.get("avaluacio") or {})
    assert CF.to_yaml(f)


def test_la_vista_de_la_campanya_diu_que_es_diagnostic(tmp_path):
    d = tmp_path / "c"
    d.mkdir()
    (d / "campanya.yaml").write_text("id: c\ndomini: {diagnostic: true}\navaluacio: {ckpts: {PE: seed1_E12_ft1}}\n")
    y = yaml.safe_load((d / "campanya.yaml").read_text())
    r = CV._diagnostic(d, {"certificacio": None}, y)
    assert r == {"actiu": True, "text": "diagnòstic, no citable", "ckpts": {"PE": "seed1_E12_ft1"}}
    assert CV._diagnostic(d, {"certificacio": None, "diagnostic": True}, {})["actiu"] is True       # manifest de neudet
    assert CV._diagnostic(d, {"certificacio": None}, {"domini": {}})["actiu"] is False


def test_el_text_de_neudet_guanya_al_del_contracte(tmp_path):
    (tmp_path / "comprova.json").write_text(json.dumps({"diagnostic": True, "diagnostic_text": "diagnòstic, no citable (neudet)"}))
    r = CV._diagnostic(tmp_path, {"certificacio": "comprova.json"}, {})
    assert r["actiu"] and r["text"] == "diagnòstic, no citable (neudet)"


def test_una_etapa_es_diagnostic_pel_meta_o_pel_yaml_de_la_campanya(tmp_path):
    et = tmp_path / "c" / "etapes" / "E1"
    et.mkdir(parents=True)
    assert RT.diagnostic_de(et, {"meta": "meta.json"}) is False
    (et / "meta.json").write_text(json.dumps({"extra": {"diagnostic": True}}))
    assert RT.diagnostic_de(et, {"meta": "meta.json"}) is True
    (et / "meta.json").write_text("{}")
    (tmp_path / "c" / "campanya.yaml").write_text("domini: {diagnostic: true}\n")
    assert RT.diagnostic_de(et, {"meta": "meta.json"}) is True


def test_la_pagina_porta_l_avis_a_tots_els_llocs():
    for tok in ("data-diag-av", "data-diag-tag", "data-diag-xifres", "function cDiagHtml", "domini.diagnostic", "avaluacio.ckpts.",
                "diagAv(v.diagnostic)", "e.diagnostic", "G.max_diagnostic"):
        assert tok in INDEX, tok
    assert INDEX.count("data-diag-xifres") >= 2          # taula de la campanya i dels resultats
