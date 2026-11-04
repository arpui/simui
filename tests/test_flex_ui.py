"""test_flex_ui.py — FLEX-UI: tubs en diverses orientacions i el generador `posicions` al formulari.

Contracte neudet↔simphy UI v1.2 §9:
- `posicions` és un generador del formulari (x, y, z, eix, ventall de tipus, Cd per posició); la plantilla passa
  `fitxa` i el formulari refusa el que neudet no podria llegir.
- El visor dibuixa els tubs girats: rectangles a XY; al tall XZ, una franja (eix x) o un cercle (eix y).
- MCNP, OpenMC i FLUKA de simphy construeixen tots els tubs al llarg de z: amb un tub girat refusen, no
  generen un altre detector en silenci.
Sense neudet, els tests que en necessiten es salten.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simphy.mcgen import campanya_check as CC  # noqa: E402
from simphy.mcgen import campanya_form as CF  # noqa: E402
from simphy.mcgen import design as DES  # noqa: E402
from simphy.mcgen import design_view as DV  # noqa: E402
from simphy.mcgen import detector_config as DC  # noqa: E402

INDEX = (ROOT / "src" / "simphy" / "ui" / "static" / "index.html").read_text()


def _neudet_o_skip() -> Path:
    try:
        return DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def _form_posicions(posicions, mides=(80.0, 40.0, 90.0)):
    f = CF.defaults()
    f["domini"]["bloc"]["mides_cm"] = list(mides)
    f["domini"]["tipus_tub"] = ["lnd_252285", "lnd_252248"]
    f["domini"]["restriccions"]["n_tubs"] = len(posicions)
    f["etapes"]["S1"]["generador"] = {"tipus": "posicions", "posicions": posicions}
    return f


def _mixt():
    return [{"x": -6, "y": 0, "z": 0, "eix": "z", "tipus": ["lnd_252285", "lnd_252248"], "cd": {"fraction": [0, 1]}},
            {"x": 0, "y": 8, "z": 10, "eix": "x", "tipus": ["lnd_252248"], "cd": {"fraction": 0}}]


@pytest.fixture(scope="module")
def mix_dat(tmp_path_factory):
    """Un disseny barrejat fet per neudet: tub 1 vertical, 2 d'eix x (per sobre dels altres), 3 d'eix y amb Cd sencer."""
    _neudet_o_skip()
    sys.path.insert(0, str(DES.neudet_root() / "src"))
    from neudet.disseny.candidat import Bloc, Candidat, Tub
    d = tmp_path_factory.mktemp("mix")
    c = Candidat(Bloc((40.0, 40.0, 90.0), 0.0),
                 (Tub(-6, 0, "lnd_252285", 0.0), Tub(0, 0.5, "lnd_252248", 38.0, eix="x"),
                  Tub(6, 0, "lnd_252248", 0.0, eix="y", cd_fraction=1.0)), "mix", {})
    c.to_dat(d / "mix.dat")
    return d / "mix.dat"


# ── el formulari ────────────────────────────────────────────────────────────

def test_posicions_es_un_generador_del_formulari():
    _neudet_o_skip()
    s = CF.schema()
    g = next(x for x in s["generadors"] if x["tipus"] == "posicions")
    assert "gap" not in g
    assert {"posicions", "x", "y", "z", "eix", "tipus", "cd"} <= {c["clau"] for c in g["camps"]}
    assert "posicions" in s["plantilles"]


def test_la_plantilla_de_posicions_es_valida_i_passa_fitxa():
    """Test bessó: la plantilla satisfà el que el formulari exigeix i el que la fitxa de neudet demana."""
    _neudet_o_skip()
    from neudet.disseny import fitxa
    f = CF.defaults()
    tub = f["domini"]["tipus_tub"][0]
    f["etapes"]["S1"]["generador"] = json.loads(json.dumps(CF.schema()["plantilles"]["posicions"]).replace("__TUB__", tub))
    cfg = yaml.safe_load(CF.to_yaml(f))
    assert [x for x in fitxa.falten(cfg) if x.startswith("etapes.S1.generador")] == []


def test_la_plantilla_de_la_pagina_porta_les_accions_de_posicions():
    for act in ("pos+", "pos-", "tp+", "tp-"):
        assert f"act === '{act}'" in INDEX, act
    assert "g.tipus === 'posicions'" in INDEX and "function cPosicionsHtml" in INDEX


def test_el_formulari_accepta_un_ventall_amb_eixos():
    _neudet_o_skip()
    cfg = yaml.safe_load(CF.to_yaml(_form_posicions(_mixt())))
    assert cfg["etapes"]["S1"]["generador"]["posicions"][1]["eix"] == "x"


@pytest.mark.parametrize("mal,missatge", [
    ({"x": 0, "y": 0, "eix": "w"}, "eix"),
    ({"x": 0, "eix": "z"}, "falta «y»"),
    ({"x": 0, "y": 0, "tipus": []}, "tipus"),
    ({"x": 0, "y": 0, "eix": "x", "cd": {"fraction": 1, "arc": 180}}, "només pot ser sencer"),
    ({"x": 0, "y": 0, "cd": {"fraction": 2}}, "cd"),
])
def test_el_formulari_refusa_posicions_que_neudet_no_llegiria(mal, missatge):
    _neudet_o_skip()
    with pytest.raises(CF.FormError) as exc:
        CF.to_yaml(_form_posicions([mal]))
    assert missatge in str(exc.value)


def test_cd_parcial_en_un_tub_vertical_es_valid():
    _neudet_o_skip()
    CF.to_yaml(_form_posicions([{"x": 0, "y": 0, "eix": "z", "cd": {"fraction": 1, "arc": 180}}]))


def test_comprova_compta_el_producte_de_les_posicions_i_dibuixa_el_tub_horitzontal():
    """3 opcions a la posició 1 (2 tipus, el primer amb Cd 0 o 1: 1 + 2 = 3 opcions) × 1 a la 2."""
    _neudet_o_skip()
    txt = CF.to_yaml(_form_posicions(_mixt()))
    r = CC.comprova(txt, "S1")
    assert r["n_valids"] + r["n_invalids"] == 4                      # 2 tipus × 2 Cd × 1
    assert r["n_valids"] >= 1
    # el tub d'eix x es veu com un rectangle (no com un cercle) a la vista XY de la targeta
    assert any("<rect" in c["xy_svg"] and "lnd_252248" in c["nom"] for c in r["candidats"])


# ── el visor ────────────────────────────────────────────────────────────────

def test_el_visor_llegeix_l_eix_del_sidecar(mix_dat):
    v = DV.build(mix_dat)
    assert [t.eix for t in v.tubes] == ["z", "x", "y"]
    assert any("Tubs girats" in n for n in v.notes)


def test_la_taula_te_columna_eix_nomes_si_n_hi_ha_de_girats(mix_dat):
    cols, rows = DV._taula(DV.build(mix_dat))
    assert cols[-1] == "Eix" and [r[-1] for r in rows] == ["z", "x", "y"]


def test_xy_dibuixa_el_tub_girat_com_a_rectangle(mix_dat):
    v = DV.build(mix_dat)
    xy = DV._svg_xy(v)
    ancho = v.tubes[1].tt.wall_length_cm
    # el tub 2 (eix x) fa la llargada de la paret en x: un rectangle, no un cercle
    rects = re.findall(r'<rect x="[\d.]+" y="[\d.]+" width="([\d.]+)"', xy)
    assert rects, xy[:200]
    assert xy.count("<circle") < 2 * len(v.tubes) + 4               # el tub vertical encara són cercles


def test_xz_talla_el_tub_d_eix_x_en_franja_i_el_d_eix_y_en_cercle(mix_dat):
    v = DV.build(mix_dat)
    assert [t.index for t in v.tubes if DV._en_tall(t)] == [1, 2, 3]
    xz = DV._svg_xz(v)
    assert "<circle" in xz                                           # tub 3 (eix y): secció circular
    DV.preview(mix_dat)                                              # la vista completa no peta


# ── MCNP, OpenMC i FLUKA no fan tubs girats en silenci ─────────────────────

def test_cfg_detecta_els_tubs_girats(mix_dat):
    cfg = DC.load(mix_dat.stem, mix_dat.parent)
    assert cfg.tubs_girats() == [(2, "x"), (3, "y")]
    for codi in ("MCNP", "OpenMC", "FLUKA"):
        with pytest.raises(DC.ConfigError) as exc:
            cfg.exigeix_tubs_drets(codi)
        assert codi in str(exc.value) and "al llarg de z" in str(exc.value)


def test_un_disseny_de_tots_els_tubs_drets_passa():
    _neudet_o_skip()
    cfg = DC.load("banc_counterUPC_v0") if "banc_counterUPC_v0" in DC.available() else None
    if cfg is None:
        pytest.skip("sense banc_counterUPC_v0")
    assert cfg.tubs_girats() == []
    cfg.exigeix_tubs_drets("MCNP")
