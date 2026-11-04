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

import copy
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


def _tongada(posicions, **atrs):
    t = {"nom": "t", "posicions": posicions, "tipus": ["lnd_252285"], "cd": {"fraction": 0}, "eix": "z", "seleccio": "exhaustiu"}
    t.update(atrs)
    return t


def _form(tongades, mides=(80.0, 40.0, 90.0), n_tubs=2):
    f = CF.defaults()
    f["domini"]["bloc"]["mides_cm"] = list(mides)
    f["domini"]["tipus_tub"] = ["lnd_252285", "lnd_252248"]
    f["domini"]["restriccions"]["n_tubs"] = n_tubs
    f["etapes"]["S1"].pop("generador", None)
    f["etapes"]["S1"]["tongades"] = tongades
    return f


def _mixt():
    """Dos punts: el 1 vertical amb ventall de tipus i de Cd; el 2 horitzontal."""
    return _tongada({"font": "punts", "punts": [
        {"x": -6, "y": 0, "z": 0, "tipus": ["lnd_252285", "lnd_252248"], "cd": {"fraction": [0, 1]}, "eix": "z"},
        {"x": 0, "y": 8, "z": 10, "tipus": ["lnd_252248"], "cd": {"fraction": 0}, "eix": "x"}]})


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

def test_el_formulari_ofereix_les_fonts_de_neudet():
    """Test bessó: les fonts i els lligams del formulari són els de neudet (generadors.py)."""
    _neudet_o_skip()
    _, G = DES._neudet()
    s = CF.schema()["tongades"]
    assert [f["valor"] for f in s["fonts"]] == list(G.FONTS)
    assert [l["valor"] for l in s["lligams"]] == list(G.LLIGAMS)
    assert tuple(CF.FONTS_TEXT) == tuple(G.FONTS) and tuple(CF.LLIGAMS_TEXT) == tuple(G.LLIGAMS)


def test_defaults_i_camps_antics_es_tradueixen_a_tongades_sense_camps_interns():
    """Un campanya.yaml amb `generador` s'obre com a `tongades`, i el yaml que en surt no porta els camps propis de la traducció."""
    root = _neudet_o_skip()
    for c in ("c01_8tubs_30x30x80", "c02_cd_2grups", "c03_3anells_grups", "c04_draft"):
        f = CF.de_fitxer(root / "disseny" / "campanyes" / c / "campanya.yaml")
        txt = CF.to_yaml(f)
        assert "_antic" not in txt and "nom_candidat" not in txt and "generador:" not in txt, c
        assert not any("generador" in e for e in f["etapes"].values()), c


def test_les_tongades_traduides_donen_els_mateixos_candidats_que_el_generador_antic():
    """La traducció de la UI (amb els valors explícits que demana la fitxa) no canvia el que neudet genera."""
    root = _neudet_o_skip()
    from neudet.disseny.campanya import Campanya
    for c in ("c01_8tubs_30x30x80", "c04_draft"):
        orig = Campanya(root / "disseny" / "campanyes" / c)
        f = CF.de_fitxer(root / "disseny" / "campanyes" / c / "campanya.yaml")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "campanya.yaml").write_text(CF.to_yaml(f))
            nou = Campanya(Path(tmp))
            for etapa, e in orig.cfg["etapes"].items():
                if "generador" not in e:
                    continue
                a = sorted(x.hash() for x, _ in orig.candidats(etapa)[0])
                b = sorted(x.hash() for x, _ in nou.candidats(etapa)[0])
                assert a == b, (c, etapa)


@pytest.mark.parametrize("tipus", ["punts", "malla", "anells"])
def test_la_plantilla_de_cada_font_es_valida_i_passa_fitxa(tipus):
    """Test bessó: la plantilla que el formulari posa en triar una font satisfà el formulari i la fitxa de neudet."""
    _neudet_o_skip()
    from neudet.disseny import fitxa
    f = CF.defaults()
    tub = f["domini"]["tipus_tub"][0]
    f["etapes"]["S1"]["tongades"] = [json.loads(json.dumps(CF.schema()["plantilles"][tipus]).replace("__TUB__", tub))]
    cfg = yaml.safe_load(CF.to_yaml(f))
    assert [x for x in fitxa.falten(cfg) if x.startswith("etapes.S1.tongades")] == []


def test_la_pagina_porta_les_accions_i_els_editors_de_tongades():
    for act in ("tg+", "tg-", "pt+", "pt-", "anell+", "anell-", "tp+", "tp-"):
        assert f"act === '{act}'" in INDEX, act
    for f in ("cTongadaHtml", "cPuntsHtml", "cMallaHtml", "cAnellsHtml", "cAtrsHtml", "cNormLligams", "cTubsVista"):
        assert f"function {f}" in INDEX, f
    assert "el.dataset.lig" in INDEX and "el.dataset.tfont" in INDEX


def test_el_formulari_accepta_un_ventall_amb_eixos():
    _neudet_o_skip()
    cfg = yaml.safe_load(CF.to_yaml(_form([_mixt()])))
    assert cfg["etapes"]["S1"]["tongades"][0]["posicions"]["punts"][1]["eix"] == "x"


@pytest.mark.parametrize("canvi,missatge", [
    (lambda t: t["posicions"]["punts"][0].__setitem__("eix", "w"), "eix"),
    (lambda t: t["posicions"]["punts"][0].pop("y"), "falta «y»"),
    (lambda t: t.__setitem__("tipus", []), "tipus"),
    (lambda t: t.__setitem__("cd", {"fraction": 2}), "cd"),
    (lambda t: t.__setitem__("seleccio", {"mostres": 0}), "seleccio"),
    (lambda t: t.__setitem__("eix", {"valors": ["z", "x"], "lligam": "cap"}), "lligam"),
])
def test_el_formulari_refusa_tongades_que_neudet_no_llegiria(canvi, missatge):
    _neudet_o_skip()
    t = _tongada({"font": "punts", "punts": [{"x": 0, "y": 0, "z": 0}]})
    canvi(t)
    with pytest.raises(CF.FormError) as exc:
        CF.to_yaml(_form([t], n_tubs=1))
    assert missatge in str(exc.value)


def test_una_tongada_dat_no_porta_atributs_i_els_noms_son_unics():
    _neudet_o_skip()
    with pytest.raises(CF.FormError) as exc:
        CF.to_yaml(_form([{"nom": "d", "posicions": {"font": "dat", "dat": "x.dat"}, "tipus": ["lnd_252285"]}]))
    assert "dat" in str(exc.value)
    t1 = _tongada({"font": "punts", "punts": [{"x": 0, "y": 0, "z": 0}]})
    with pytest.raises(CF.FormError) as exc:
        CF.to_yaml(_form([t1, copy.deepcopy(t1)]))
    assert "ja és el d'una altra tongada" in str(exc.value)


def test_cd_parcial_en_un_tub_vertical_es_valid():
    _neudet_o_skip()
    CF.to_yaml(_form([_tongada({"font": "punts", "punts": [{"x": 0, "y": 0, "z": 0}]}, cd={"fraction": 1, "arc": 180})], n_tubs=1))


def test_compta_diu_quants_surten_per_tongada_i_comprova_dibuixa_el_tub_horitzontal():
    """Punt 1: 2 tipus × (Cd 0 | Cd 1) = 4 candidats; el punt 2 és fix. El recompte és el de neudet, per tongada."""
    _neudet_o_skip()
    txt = CF.to_yaml(_form([_mixt()]))
    c = CC.compta(txt, "S1")
    assert c["tongades"] == [{"nom": "t", "recompte": 4}] and c["n"] == 4
    r = CC.comprova(txt, "S1")
    assert r["n_valids"] + r["n_invalids"] == 4 and r["n_valids"] >= 1
    assert any("<rect" in x["xy_svg"] and "lnd_252248" in x["nom"] for x in r["candidats"])


def test_diverses_tongades_se_sumen_i_es_compten_una_a_una():
    """La idea d'Albert: malla i anells a la mateixa etapa. Cada tongada té el seu recompte."""
    _neudet_o_skip()
    malla = _tongada({"font": "malla", "forma": "quadrada", "k": 1, "z": 0, "x": [-6, 6], "y": [0]}, nom="malla")
    anells = _tongada({"font": "anells", "anells": [{"r": 6, "n": {"de": 1, "a": 2}, "phi": 0}]}, nom="anells")
    c = CC.compta(CF.to_yaml(_form([malla, anells], n_tubs=1)), "S1")
    assert [(t["nom"], t["recompte"]) for t in c["tongades"]] == [("malla", 2), ("anells", 2)] and c["n"] == 4


def test_la_vista_dels_tubs_cobreix_totes_les_fonts():
    """Test bessó: cada font que el formulari ofereix té el seu cas a `cTubsVista`, i es pinta al bloc."""
    vista = INDEX.split("function cTubsVista")[1].split("function cBlocSvg")[0]
    for f in CF.FONTS_TEXT:
        if f != "dat":                                             # un .dat no té posicions al formulari
            assert f"pos.font === '{f}'" in vista, f
    assert "cTubsVista()" in INDEX and "data-drag" in INDEX and "pointerdown" in INDEX


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


def test_comprova_porta_els_numeros_per_tongada_de_neudet():
    """Per tongada: recompte, generats, repetits, vàlids i descartats (els del `meta` de neudet); sumen els vàlids i invàlids de l'etapa."""
    _neudet_o_skip()
    malla = _tongada({"font": "malla", "forma": "quadrada", "k": 1, "z": 0, "x": [-6, 6], "y": [0]}, nom="malla")
    anells = _tongada({"font": "anells", "anells": [{"r": 6, "n": {"de": 1, "a": 2}, "phi": 0}]}, nom="anells")
    r = CC.comprova(CF.to_yaml(_form([malla, anells], n_tubs=1)), "S1")
    assert [t["nom"] for t in r["tongades"]] == ["malla", "anells"]
    assert sum(t["valids"] for t in r["tongades"]) == r["n_valids"]
    assert sum(t["descartats"] for t in r["tongades"]) == r["n_invalids"]


def test_un_ventall_dins_d_un_anell_no_demana_lligam_i_neudet_el_genera():
    """Dins d'un anell, tot el que es posa és d'aquell anell: el ventall no porta `lligam`, passa la fitxa i es compta."""
    _neudet_o_skip()
    from neudet.disseny import fitxa
    anells = {"font": "anells", "anells": [
        {"r": 4, "n": 2, "phi": 0, "tipus": ["lnd_252285", "lnd_252248"], "cd": {"fraction": 0}, "eix": "z"},
        {"r": 9, "n": 2, "phi": 0, "tipus": ["lnd_252248"], "cd": {"fraction": [0, 1]}, "eix": "z"}]}
    t = {"nom": "a", "posicions": anells, "seleccio": "exhaustiu"}          # sense atributs a la tongada
    f = _form([t], mides=(40.0, 40.0, 90.0), n_tubs=4)
    cfg = yaml.safe_load(CF.to_yaml(f))
    assert [x for x in fitxa.falten(cfg) if x.startswith("etapes.S1.tongades")] == []
    assert CC.compta(CF.to_yaml(f), "S1")["n"] == 2 * 1 * 1 * 2          # anell 1: 2 tipus; anell 2: 2 Cd


def test_la_pagina_porta_els_atributs_dins_de_cada_anell_i_punt():
    anells = INDEX.split("function cAnellsHtml")[1].split("function cTongadaHtml")[0]
    punts = INDEX.split("function cPuntsHtml")[1].split("function cMallaHtml")[0]
    assert "cAtrsHtml(ap, a, true)" in anells and "Filtres sobre els anells" in anells
    assert "cAtrsHtml(qp, q, true)" in punts
    assert anells.index("anell+") < anells.index("n_total")             # els filtres, sota tots els anells


def test_la_vista_dels_anells_usa_el_pas_per_defecte_de_neudet_i_el_n_total():
    """Un rang sense `pas` val 1 a neudet (`valors`): si la vista no ho fes, un rang com {de: 0, a: 8} no dibuixaria cap tub."""
    vista = INDEX.split("function cVals")[1].split("function cBlocSvg")[0]
    assert "v.pas === undefined" in vista and "pos.n_total" in vista
