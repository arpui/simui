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
    # INV: amb recursos, cada anell i punt només porta la geometria (eix); el format antic (només lectura), els seus atributs
    assert "cEixHtml(ap, a)" in anells and "cAtrsHtml(ap, a, true, false)" in anells and "Filtres sobre els anells" in anells
    assert "cEixHtml(qp, q)" in punts and "cAtrsHtml(qp, q, true, false)" in punts
    assert anells.index("anell+") < anells.index("n_total")             # els filtres, sota tots els anells


def test_la_vista_dels_anells_usa_el_pas_per_defecte_de_neudet_i_el_n_total():
    """Un rang sense `pas` val 1 a neudet (`valors`): si la vista no ho fes, un rang com {de: 0, a: 8} no dibuixaria cap tub."""
    vista = INDEX.split("function cVals")[1].split("function cBlocSvg")[0]
    assert "v.pas === undefined" in vista and "pos.n_total" in vista


def test_despres_de_desar_la_pagina_diu_que_es_fa_i_amb_quin_missatge():
    """Després de «Desa la proposta», la UI diu que s'atura, el missatge per al planificador i què ve després."""
    desa = INDEX.split("async function cDesa(){")[1].split("// Un formulari carregat")[0]
    for t in ("Ara et toca a tu", "r.missatge", "executada", "runbook-run", "no ha corregut cap simulació"):
        assert t in desa, t


# ── RESP-UI: resposta d'etapa i formulari congelat a la pàgina ──────────────

def test_pagina_mostra_resposta_d_etapa_i_formulari_congelat():
    html = (Path(__file__).resolve().parents[1] / "src/simphy/ui/static/index.html").read_text(encoding="utf-8")
    for tros in ("function kResposta", "function kPla", "Aquesta etapa encara no té <code>resposta.md</code>",
                 "Per què aquesta etapa", "function kCongela", 'data-k="congela"', "Definició congelada",
                 "function cCongela", "CP.congelat"):
        assert tros in html, tros
    # el Markdown de la resposta porta figures i taules; el congelat no deixa desar ni editar
    assert "<img loading=\"lazy\" style=\"max-width:100%\"" in html
    assert "if(!CP.congelat) cEdita" in html


def test_desa_mostra_en_vermell_errors_i_descartats():
    html = (Path(__file__).resolve().parents[1] / "src/simphy/ui/static/index.html").read_text(encoding="utf-8")
    assert "function cAvisosDesa" in html and "data-avis-desa" in html
    assert "${cAvisosDesa(r.certificacio)}" in html           # i és dins de la resposta de desar
    for tros in ("camps_falten", "candidats descartats", "e.motius", "'prohibit'"):
        assert tros in html, tros
    assert '<div class="panel bad" data-avis-desa>' in html     # vermell, com la resta d'errors


def test_pregunta_per_etapa_passa_pel_formulari_i_neudet_la_tolera():
    """CONF-UI (contracte UI §13): «Què vull saber» és `etapes.<e>.pregunta`; el formulari la conserva i neudet no la rebutja."""
    import os
    from simphy.mcgen import campanya_check as CC
    y = Path(os.path.expanduser("~/projects/neudet/disseny/campanyes/c0_2anells/campanya.yaml"))
    if not y.is_file():
        pytest.skip("neudet no és present")
    f = CF.de_fitxer(y)
    e = next(iter(f["etapes"]))
    f["etapes"][e]["pregunta"] = "Què canvia a la frontera?"
    text = CF.to_yaml(f)
    assert "Què canvia a la frontera?" in text
    assert CC.comprova(text).get("camps_falten") is None


def test_pagina_te_pregunta_i_boto_modifica():
    html = (Path(__file__).resolve().parents[1] / "src/simphy/ui/static/index.html").read_text(encoding="utf-8")
    assert "Què vull saber" in html and "etapes.${E}.pregunta" in html
    assert "Modifica la proposta" in html and "Desa la proposta" in html


# ── INV-UI: inventari de tubs (contracte UI §10b) ───────────────────────────

def _form_inv(inv=None, **pos):
    root = _neudet_o_skip()
    f = CF.de_fitxer(root / "disseny" / "campanyes" / "c04_draft" / "campanya.yaml")
    e = next(iter(f["etapes"]))
    base = {"font": "anells", "anells": [{"r": {"de": 4, "a": 4, "pas": 1}, "n": {"de": 0, "a": 4}, "phi": 0},
                                         {"r": {"de": 9, "a": 9, "pas": 1}, "n": {"de": 0, "a": 4}, "phi": "mig_pas"}]}
    base.update(pos)
    f["etapes"][e]["tongades"] = [{"nom": "inv", "inventari": inv or {"lnd_252285": 2, "lnd_sk03410": 2},
                                   "posicions": base, "cd": {"fraction": 0}, "eix": "z", "seleccio": "exhaustiu"}]
    return f, e


def test_inventari_passa_pel_formulari_i_neudet_compta_amb_simetria_i_no_escriu_tipus_tub():
    from simphy.mcgen import campanya_check as CC
    f, e = _form_inv()
    txt = CF.to_yaml(f)
    assert "inventari:" in txt and "tipus_tub" not in txt              # SIMPLIFICA: neudet el deriva dels tipus de les tongades
    r = CC.compta(txt, e)["tongades"][0]
    assert r["recompte"] == 30 and r["simetria"]["abans"] == 30 and r["simetria"]["despres"] == 15
    assert "en_paraules" in r["simetria"]


@pytest.mark.parametrize("canvi,motiu", [
    (lambda f, e: f["etapes"][e]["tongades"][0].update(tipus=["lnd_252285"]), "el tipus el dona l'inventari"),
    (lambda f, e: f["etapes"][e]["tongades"][0]["posicions"]["anells"][0].update(tipus_permesos=["altre"]), "no és a l'inventari"),
    (lambda f, e: f["etapes"][e]["tongades"][0]["posicions"].update(n_total=7), "inventari fa de n_total"),
    (lambda f, e: f["etapes"][e]["tongades"][0].update(inventari={"lnd_252285": 0}), "inventari"),
])
def test_inventari_incoherent_es_refusa_amb_el_motiu(canvi, motiu):
    f, e = _form_inv()
    canvi(f, e)
    with pytest.raises(CF.FormError, match=motiu):
        CF.to_yaml(f)


def test_inventari_punts_i_malla_han_de_sumar_el_total():
    f, e = _form_inv(font="punts", punts=[{"x": 0, "y": 5, "z": 0}])
    with pytest.raises(CF.FormError, match="1 punts i l'inventari té 4"):
        CF.to_yaml(f)
    f, e = _form_inv(font="malla", forma="quadrada", k=3, z=0, x=[0, 5], y=[0, 5])
    with pytest.raises(CF.FormError, match="ha de ser el total"):
        CF.to_yaml(f)


def test_tipus_permesos_sense_inventari_es_refusa():
    f, e = _form_inv()
    t = f["etapes"][e]["tongades"][0]
    del t["inventari"]
    t["posicions"]["anells"][0]["tipus_permesos"] = ["lnd_252285"]
    with pytest.raises(CF.FormError, match="només amb `inventari`"):
        CF.to_yaml(f)


def test_tipus_tub_es_manté_si_alguna_tongada_el_deixa_al_domini():
    """Un yaml antic traduït sense tipus a la tongada: treure `domini.tipus_tub` canviaria el tipus per defecte (i els hashes)."""
    root = _neudet_o_skip()
    f = CF.de_fitxer(root / "disseny" / "campanyes" / "c01_8tubs_30x30x80" / "campanya.yaml")
    assert "tipus_tub" in yaml.safe_load(CF.to_yaml(f))["domini"]


def test_la_pagina_porta_l_inventari_i_ja_no_el_selector_del_domini():
    # INV: els quatre passos (recursos → estructura → assignació → recompte) i fora el selector de mode
    for tros in ("function cRecursosHtml", "1 · Recursos i les seves variacions: tubs disponibles", "2 · Tipus d'estudi",
                 "3 · Assignació dels recursos", "4 · Recompte", "tipus permesos", "tubs fixats", "fixats i fixos: ",
                 "data-nmode", "data-reccd", "function cSyncInv", "abans de la simetria", "t.avis", "Convertida des del format antic"):
        assert tros in INDEX, tros
    assert "data-invmode" not in INDEX and "function cInvMode" not in INDEX
    assert "cSelTub('domini.tipus_tub.0'" not in INDEX and "tipus_tub[0]" not in INDEX


# ── VISTA-UI: vista lateral i dimensions del tub ────────────────────────────

def test_schema_porta_les_mides_dels_tubs_llegides_del_cataleg_de_neudet():
    _neudet_o_skip()
    tubs = {t["nom"]: t for t in CF.schema()["tipus_tub"]}
    m = tubs["lnd_252285"]["mides"]
    assert m["diametre_cm"] == 2.54 and m["llargada_activa_cm"] == 60.0 and m["pressio_atm"] == 8.0 and m["paret"] == "SST"
    assert m["llargada_total_cm"] > m["llargada_activa_cm"]
    assert all(t["mides"] is None or set(t["mides"]) == {"diametre_cm", "llargada_activa_cm", "llargada_total_cm", "pressio_atm", "paret"}
               for t in tubs.values())


def test_la_pagina_porta_la_vista_lateral_i_les_dimensions_al_selector():
    for tros in ("function cBlocLateral", "const cMidesTxt", "llargada_activa_cm"):
        assert tros in INDEX, tros


def test_les_tres_vistes_es_veuen_alhora_sense_desplegable():
    """VISTA-3: de dalt, lateral XZ i lateral YZ, una al costat de l'altra, al formulari i al full del candidat."""
    form = INDEX.split("function cBlocSvg")[1].split("function cBlocLateral")[0]
    assert "cBlocXY(id, V)" in form and "cBlocLateral(id + '-xz', 'xz', V)" in form and "cBlocLateral(id + '-yz', 'yz', V)" in form
    for ja_no in ("data-vista", 'id="d-lat"', "dPintaLateral", "CP.vista", "DS.lat"):
        assert ja_no not in INDEX, ja_no
    assert 'id="d-xy"' in INDEX and 'id="d-xz"' in INDEX and 'id="d-yz"' in INDEX
    assert "Q('#d-yz').innerHTML = v.yz_svg" in INDEX
    assert "grid-template-columns:1fr 1fr 1fr" in INDEX and ".tres{display:flex;flex-wrap:wrap" in INDEX     # alhora; estreta: una sota l'altra


def test_el_visor_de_candidats_dona_tambe_el_tall_yz():
    import glob
    from simphy.mcgen import design_view as DV
    root = _neudet_o_skip()
    dats = sorted(glob.glob(str(root / "disseny/campanyes/c01_8tubs_30x30x80/export/*.dat")))
    if not dats:
        pytest.skip("c01 sense export")
    r = DV.preview(Path(dats[0]))
    assert r["yz_svg"].startswith("<svg") and "x = 0" in r["yz_svg"] and "y (cm)" in r["yz_svg"]
    assert "y = 0" in r["xz_svg"] and "x (cm)" in r["xz_svg"]            # l'XZ de sempre no canvia
    assert r["caption_yz"][0].startswith("Tall a x = 0")


# ── CONF-UI: resum, interpretació i confirmació (contracte UI §13) ──────────

def test_la_vista_porta_resum_confirmacio_interpretacio_i_etapes_declarades():
    from simphy.mcgen import campanya_vista as CV
    root = _neudet_o_skip()
    if not (root / "disseny/campanyes/c0_2a0511/campanya_ui.json").is_file():
        pytest.skip("c0_2a0511 no és a neudet")
    v = CV.vista(CV.dir_de("c0_2a0511"))
    assert v["certificacio"]["resum_text"].startswith("Estat:") and v["certificacio"]["confirmacio"]["estat"]
    assert v["interpretacio"] and v["etapes"][0]["executada"] is False and v["etapes"][0]["candidats"] == []
    assert v["etapes"][0]["pla"]


def test_la_pagina_porta_el_resum_la_interpretacio_i_el_boto_de_confirmar_nomes_en_interpretada():
    for tros in ("function kConfirmaHtml", "Confirmar i congelar", "Confirma i congela", "/api/campanya/confirma",
                 "function kResumInterp", "Interpretació del planificador", "Què entén neudet que farà", "encara no ha corregut"):
        assert tros in INDEX, tros
    assert "v.estat_yaml !== 'interpretada'" in INDEX          # el botó només surt amb la campanya interpretada
    assert "interpretada" in INDEX.split('id="c-flux"')[1].split("</details>")[0]     # el flux explica el pas nou


# ── UI-AFINA ──
def test_afina_un_sol_dibuix_enganxat_amb_exemple_llegenda_i_boto():
    """Un sol dibuix (fora c-bloc2), a dalt del formulari i sempre visible; exemple a l'atzar, color per TIPUS, llegenda i «una altra»."""
    assert "c-bloc2" not in INDEX and "c-bloc-wrap2" not in INDEX
    assert INDEX.count('id="c-bloc-wrap"') == 1 and 'class="sticky-bloc"' in INDEX and ".sticky-bloc{position:sticky" in INDEX
    assert "function cAssigAnells" in INDEX and "function cRng" in INDEX and "const cColor = (V, tipus)" in INDEX
    assert 'data-act="altra"' in INDEX and "una altra" in INDEX and "no és cap candidat" in INDEX and 'class="legend"' in INDEX
    assert "PAL[(p.tong" not in INDEX                               # el color ja no és el de la tongada


def test_afina_la_font_nomes_es_mou_amb_el_boto_i_la_posicio_es_veu_en_numeros():
    clic = INDEX.split("function cClicBloc")[1].split("function cArr")[0]
    assert "!CP.movFont" in clic
    assert 'data-act="movfont"' in INDEX and "mou la font" in INDEX and "font a (" in INDEX


def test_afina_modifica_a_l_acte_espera_de_neudet_i_refresc():
    assert "CP.desat = r.id; Q('#c-desa').textContent = 'Modifica la proposta'" in INDEX
    assert "Esperant resposta de neudet" in INDEX and "setInterval(mira, 30000)" in INDEX
    assert "Veu la interpretació i confirma" in INDEX and 'id="c-espera"' in INDEX


def test_afina_hits_editable_i_la_nota_no_hereta_el_que_de_la_plantilla():
    ver = INDEX.split("function cVerifHtml")[1].split("function cCercaHtml")[0]
    assert "cSel('verificacio.hits', [{valor: 'all'}, {valor: 'detect'}]" in ver
    assert "function cSenseQue" in INDEX and INDEX.count("cSenseQue(d);") == 2
    assert "nota teva (opcional; NO és la pregunta)" in INDEX


def test_afina_punts_variables_i_cost_gran():
    f = INDEX.split("function cTubsVista")[1].split("const cRedibuixa")[0]
    assert "PUNTS-V" in f and "pv(q.x)" in f and "drag: fixa" in f             # x, y, z: valor, llista o rang; només s'arrossega un punt fix
    assert "function cCostHtml" in INDEX and "Massa gran per a un tanteig" in INDEX and "opcions_cost" in INDEX


def test_afina_opcions_cost_arriba_de_comprova_json(tmp_path):
    import json
    from simphy.mcgen import campanya_vista as CV
    d = tmp_path / "c"; d.mkdir()
    (d / "comprova.json").write_text(json.dumps({"atura": False, "opcions_cost": [{"opcio": "mostres: 200", "cost_h": 9}]}))
    c = CV._certificacio(d, "comprova.json")
    assert c["opcions_cost"] == [{"opcio": "mostres: 200", "cost_h": 9}]


def test_afina_punts_v_el_formulari_ofereix_valor_llista_o_rang():
    assert "function cCoordHtml" in INDEX and "data-coord=" in INDEX and "cCoordHtml(`${qp}.x`, q.x, 'x (cm)')" in INDEX
    assert "el.dataset.coord !== undefined" in INDEX and "{de: v0, a: v0, pas: 1}" in INDEX
