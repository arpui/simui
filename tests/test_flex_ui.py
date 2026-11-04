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


# ── vista aproximada dels tubs al formulari ────────────────────────────────

def test_la_vista_dels_tubs_cobreix_tots_els_generadors():
    """Test bessó: cada generador que el formulari ofereix té el seu cas a `cTubsVista`, i es pinta al bloc."""
    for tipus in CF.CAMPS:
        assert f"g.tipus === '{tipus}'" in INDEX.split("function cTubsVista")[1].split("function cBlocSvg")[0], tipus
    assert "cTubsVista()" in INDEX and "data-drag" in INDEX and "pointerdown" in INDEX


# ── un sol model: on són els tubs (A) i què són (B) ───────────────────────

def test_cada_generador_te_la_seva_fila_de_capacitats():
    _neudet_o_skip()
    s = CF.schema()
    assert set(s["capacitats"]) == {g["tipus"] for g in s["generadors"]}
    for t, c in s["capacitats"].items():
        assert {"etiqueta", "posicions", "tipus", "cd", "eix"} <= set(c), t


def test_les_capacitats_diuen_el_mateix_que_neudet_fa():
    """Test bessó de la taula: on diu «ventall» o «fix per…», neudet genera de debò aquelles opcions."""
    _neudet_o_skip()
    from neudet.disseny.candidat import Bloc
    from neudet.disseny.generadors import genera
    bloc = Bloc((80.0, 40.0, 90.0), 0.0)
    ctx = dict(tipus=["lnd_252285", "lnd_252248"], n_tubs=2, restriccions={}, arrel=".")
    mapa = genera({"tipus": "mapa_un_tub", "tipus_tub": ["lnd_252285", "lnd_252248"], "cd": {"fraction": [0, 1]},
                   "x": [0], "y": [0]}, bloc, ctx)
    assert len(mapa) == 4 and CF.CAPACITATS["mapa_un_tub"]["tipus"] == "ventall" == CF.CAPACITATS["mapa_un_tub"]["cd"]
    anells = genera({"tipus": "anells", "anells": [{"r": 5, "n": 2, "tipus": ["lnd_252285", "lnd_252248"],
                                                    "cd": {"fraction": 0}}]}, bloc, ctx)
    assert len(anells) == 2 and CF.CAPACITATS["anells"]["tipus"].startswith("ventall")
    llista = genera({"tipus": "llista", "candidats": [{"nom": "a", "tubs": [
        {"x": 0, "y": 0, "tipus": "lnd_252285", "cd_fraction": 1.0}]}]}, bloc, ctx)
    assert llista[0].tubs[0].cd_fraction == 1.0 and CF.CAPACITATS["llista"]["cd"].startswith("fix")
    slots = genera({"tipus": "slots", "pas_cm": 10, "mostres": 3, "cd": {"fraction": 1}}, bloc, ctx)
    assert all(not t.te_cd for c in slots for t in c.tubs) and CF.CAPACITATS["slots"]["cd"] == "—"


def test_el_formulari_accepta_tipus_en_ventall_a_anells_i_mapa():
    _neudet_o_skip()
    f = CF.defaults()
    f["domini"]["tipus_tub"] = ["lnd_252285", "lnd_252248"]
    f["etapes"]["S1"]["generador"] = {"tipus": "mapa_un_tub", "tipus_tub": ["lnd_252285", "lnd_252248"],
                                      "cd": {"fraction": 0}, "x": [0], "y": [0]}
    CF.to_yaml(f)
    f["etapes"]["S1"]["generador"] = {"tipus": "anells", "anells": [{"r": 5, "n": 3, "tipus": ["lnd_252285", "lnd_252248"],
                                                                      "cd": {"fraction": 0}}]}
    CF.to_yaml(f)


def test_la_pagina_porta_les_capacitats_i_el_ventall_de_tipus():
    for t in ("function cCapacitatsHtml", "function cTipusLlista", "cd_fraction", "S.capacitats"):
        assert t in INDEX, t
