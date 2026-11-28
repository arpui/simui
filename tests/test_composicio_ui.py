"""test_composicio_ui.py — COMPOSICIO (neudet, contracte §30 v1.29): la part visible a la UI (27-11).

La UI no calcula res: valida cridant `neudet.disseny.composicio.falten_composicio`, llegeix les claus, els valors permesos i els
defectes de neudet (`schema()["composicio"]`) i mostra el que neudet n'ha escrit (`etapes/<nom>/composicio/`) amb el seu `avis`
i `informatiu` tal com són: la predicció és informativa i **no citable**; el que és citable és el pas final amb Cd real.

Test bessó: l'etapa de composició de l'exemple dels docs de neudet (`docs/site/detector/composicio.md`) sobre el `c04_draft` és
vàlida a la UI i a neudet (`fitxa.falten`); i els casos erronis donen a la UI el mateix que a neudet. Divergència fixada: neudet
(`campanya.py:548`) exigeix que `de` sigui una etapa de xarxa; la UI ho diu abans de desar.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simui import campanya_form as CF  # noqa: E402
from simui import campanya_vista as V  # noqa: E402
from simphy.mcgen import design as DES  # noqa: E402


def _neudet() -> Path:
    try:
        return DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def _c04() -> Path:
    p = _neudet() / "disseny" / "campanyes" / "c04_draft" / "campanya.yaml"
    if not p.is_file():
        pytest.skip(f"{p} no existeix: neudet ha mogut la plantilla")
    return p


def _comp():
    _neudet()
    try:
        return CF._mod_composicio()
    except Exception as e:  # neudet sense composicio.py (anterior a v1.29)
        pytest.skip(f"neudet no té composicio.py: {e}")


# L'exemple de docs/site/detector/composicio.md (etapa C1 sobre S1)
EXEMPLE = {"que": "composició", "composicio": {"de": "S1", "anells_cd": "tots", "filtre_cm": 2,
                                               "objectius": ["eps_av_10", "F_10"], "candidats": "tots"}}


def _form(retoc=None):
    f = CF.de_fitxer(_c04(), marca=True)
    f["etapes"]["C1"] = copy.deepcopy(EXEMPLE)
    if retoc:
        retoc(f["etapes"]["C1"]["composicio"])
    return f


def _falten_neudet(f) -> list:
    """El veredicte de neudet sobre el yaml que la UI escriuria (la part de composició)."""
    _comp()
    from neudet.disseny import fitxa
    cfg = copy.deepcopy(f)
    for k in CF.CLAUS_FORMULARI:                       # la nota de conversió i les marques no són del yaml
        cfg.pop(k, None)
    return [x for x in fitxa.falten(cfg) if "composicio" in x]


# ── bessó: la plantilla amb l'exemple dels docs és vàlida als dos llocs ──────────────────────────────────────────────
def test_la_plantilla_amb_l_etapa_de_composicio_dels_docs_es_valida_a_la_ui_i_a_neudet():
    f = _form()
    assert CF._errors(f) == [], CF._errors(f)
    assert _falten_neudet(f) == []


def test_la_plantilla_sola_no_canvia():
    """Sense etapa de composició res no canvia: la plantilla segueix sense errors."""
    assert CF._errors(CF.de_fitxer(_c04(), marca=True)) == []


def test_l_etapa_de_composicio_ja_no_es_una_clau_no_editable_i_fa_round_trip():
    f = _form()
    assert not [x for x in (f.get("_no_editables") or []) if "composicio" in str(x)]
    text, avisos = CF.to_yaml_i_avisos(f)
    assert not [a for a in avisos if "composicio" in a], avisos
    assert yaml.safe_load(text)["etapes"]["C1"]["composicio"] == EXEMPLE["composicio"]
    # i recarregat des del text, la mateixa etapa
    g = yaml.safe_load(text)
    assert g["etapes"]["C1"] == EXEMPLE


# ── bessó: els casos erronis, el mateix que neudet ──────────────────────────────────────────────────────────────────
CASOS = {
    "falta_de": lambda c: c.pop("de"),
    "falta_filtre": lambda c: c.pop("filtre_cm"),
    "filtre_negatiu": lambda c: c.update(filtre_cm=-1),
    "anells_negatiu": lambda c: c.update(anells_cd=[0, -1]),
    "candidats_dolent": lambda c: c.update(candidats="alguns"),
    "objectiu_dolent": lambda c: c.update(objectius=["eps_mitja", "F_10"]),
    "objectius_ordre": lambda c: c.update(objectius=["F_10", "eps_av_10"]),
    "k_zero": lambda c: c.update(k=0),
    "clau_desconeguda": lambda c: c.update(inventada=1),
}


@pytest.mark.parametrize("cas", sorted(CASOS))
def test_els_errors_de_composicio_son_els_de_neudet(cas):
    f = _form(CASOS[cas])
    mod = _comp()
    esperat = mod.falten_composicio("C1", f["etapes"]["C1"])
    assert esperat, f"{cas}: neudet ja no ho rebutja; el cas ja no és un error"
    ui = CF._errors(f)
    for frase in esperat:
        assert any(frase in x for x in ui), (cas, frase, ui)
    assert _falten_neudet(f), cas                                                   # i `fitxa.falten` també el rebutja


def test_composicio_amb_tongades_es_rebutjada_com_a_neudet():
    f = _form()
    f["etapes"]["C1"]["tongades"] = copy.deepcopy(f["etapes"]["S1"]["tongades"])
    ui = CF._errors(f)
    assert any("tongades" in x or "generador" in x for x in ui), ui
    assert _falten_neudet(f)


def test_de_ha_de_ser_una_etapa_de_xarxa_i_la_linia_de_neudet_es_la_real():
    """`campanya.py:548` (neudet): `de` no pot ser una altra composició. La UI ho diu abans de desar."""
    f = _form()
    f["etapes"]["C2"] = {"composicio": dict(EXEMPLE["composicio"], de="C1")}
    ui = [x for x in CF._errors(f) if "composicio.de" in x]
    assert ui and "xarxa" in ui[0] and f"campanya.py:{CF.COMPOSICIO_DE_LINIA}" in ui[0], ui
    linia = (_neudet() / "src" / "neudet" / "disseny" / "campanya.py").read_text().splitlines()[CF.COMPOSICIO_DE_LINIA - 1]
    assert '"composicio" in b' in linia, linia


# ── schema: tot ve de neudet, res es copia ──────────────────────────────────────────────────────────────────────────
def test_el_schema_de_composicio_es_el_de_neudet():
    c = _comp()
    from neudet.disseny import objectius as O
    s = CF.schema()["composicio"]
    assert s["k_defecte"] == c.K_DEFECTE
    assert s["avis"] == c.AVIS
    assert s["max_combinacions_defecte"] == 50_000_000
    assert set(s["obligades"]) == {"de", "anells_cd", "filtre_cm", "objectius", "candidats"}
    assert set(s["opcionals"]) == {"k", "max_combinacions", "de_motor"}
    eps = sorted(n for n, (t, _) in O.PAPER.items() if t == "av")
    F = sorted(n for n, (t, _) in O.PAPER.items() if t == "F")
    assert sorted(s["metriques_eps"]) == eps and sorted(s["metriques_F"]) == F
    # el que la UI ofereix com a objectiu ha de passar `falten_composicio`
    for e in eps:
        for g in F:
            assert c.falten_composicio("C1", dict(EXEMPLE["composicio"], objectius=[e, g]) and
                                       {"composicio": dict(EXEMPLE["composicio"], objectius=[e, g])}) == [], (e, g)


def test_els_defectes_k_i_max_combinacions_no_s_escriuen_si_l_usuari_no_els_posa():
    """MAI INVENTIS: el yaml no porta `k` ni `max_combinacions` si no els has escrit tu (neudet té el seu defecte)."""
    f = _form()
    cfg = yaml.safe_load(CF.to_yaml(f))["etapes"]["C1"]["composicio"]
    assert "k" not in cfg and "max_combinacions" not in cfg and "de_motor" not in cfg


# ── vista: el que neudet ha escrit, tal com és, i marcat com a no citable ─────────────────────────────────────────────
def _escriu_artefactes(d: Path, nom="C1"):
    sub = d / "etapes" / nom / "composicio"
    sub.mkdir(parents=True)
    avis = "PREDICCIÓ INFORMATIVA (eq. 3 del paper): … NO és citable."
    (sub / "composicio.json").write_text(json.dumps({
        "versio": 1, "etapa": nom, "estat": "prediccio", "informatiu": True, "avis": avis, "avisos": ["un avís de neudet"],
        "base": {"etapa": "S1", "fitxer": "etapes/S1/resultats_tub.json", "motor": "xarxa"}, "filtre_cm": 2,
        "config": dict(EXEMPLE["composicio"]), "mètriques": {"eps_av_10": ["av", 10], "F_10": ["F", 10]}, "combinacions_total": 100, "n_front": 2, "k": 5, "n_seleccionats": 1,
        "seleccio_posicions_front": [0],
        "candidats": [{"hash": "h1", "nom": "cand1", "n_combinacions": 100, "anells": [], "sense_cd": {"eps_av": 0.1, "F": 3.0}}],
        "front": [{"candidat": "h1", "nom": "cand1", "n_filtres": [1, 0], "f_lliure": [0.9, 1.0], "cd_cobert": [0.1, 0.0],
                   "eps_av_10": 0.2, "F_10": 2.0, "eps_E": [0.1, 0.2], "i_front": 0},
                  {"candidat": "h1", "nom": "cand1", "n_filtres": [0, 1], "f_lliure": [1.0, 0.9], "cd_cobert": [0.0, 0.1],
                   "eps_av_10": 0.3, "F_10": 2.5, "eps_E": [0.1, 0.2], "i_front": 1}]}))
    (sub / "seleccio.json").write_text(json.dumps({"informatiu": True, "avis": avis, "k": 5,
                                                   "seleccio": [{"candidat": "h1", "nom": "cand1", "n_filtres": [1, 0], "posicio_front": 0}]}))
    return sub


def test_la_vista_passa_la_prediccio_tal_com_es_amb_l_avis_i_informatiu(tmp_path):
    y = {"id": "t", "etapes": {"S1": {"tongades": []}, "C1": {"composicio": dict(EXEMPLE["composicio"])}}}
    _escriu_artefactes(tmp_path)
    avisos: list = []
    out = V._composicions(tmp_path, y, [], avisos)
    assert [c["nom"] for c in out] == ["C1"] and avisos == []
    c = out[0]
    assert c["config"] == EXEMPLE["composicio"] and c["final"] is None
    p = c["prediccio"]
    assert p["informatiu"] is True and p["avis"].startswith("PREDICCIÓ INFORMATIVA") and p["avisos"] == ["un avís de neudet"]
    assert p["metriques"] == {"eps_av_10": ["av", 10], "F_10": ["F", 10]} and p["base"]["etapa"] == "S1"
    assert [r["n_filtres"] for r in p["front"]] == [[1, 0], [0, 1]] and all("eps_E" not in r for r in p["front"])
    assert p["seleccionat"] == [True, False]


def test_el_pas_final_es_l_etapa_amb_cd_real(tmp_path):
    y = {"etapes": {"C1": {"composicio": dict(EXEMPLE["composicio"])}}}
    _escriu_artefactes(tmp_path)
    etapes = [{"nom": "C1", "n_candidats": 5, "citable": True}]
    out = V._composicions(tmp_path, y, etapes, [])
    assert out[0]["final"] == {"etapa": "C1", "n_candidats": 5, "citable": True}
    assert etapes[0]["composicio_final"] is True


def test_sense_artefactes_no_hi_ha_prediccio_ni_xifra(tmp_path):
    y = {"etapes": {"C1": {"composicio": dict(EXEMPLE["composicio"])}}}
    out = V._composicions(tmp_path, y, [], [])
    assert out[0]["prediccio"] is None and out[0]["final"] is None


def test_un_json_trencat_es_un_avis_no_una_xifra(tmp_path):
    y = {"etapes": {"C1": {"composicio": dict(EXEMPLE["composicio"])}}}
    sub = tmp_path / "etapes" / "C1" / "composicio"
    sub.mkdir(parents=True)
    (sub / "composicio.json").write_text("{no és json")
    avisos: list = []
    out = V._composicions(tmp_path, y, [], avisos)
    assert out[0]["prediccio"] is None and avisos and "composició" in avisos[0]


def test_les_etapes_de_xarxa_no_surten_a_composicions(tmp_path):
    y = {"etapes": {"S1": {"tongades": []}}}
    assert V._composicions(tmp_path, y, [], []) == []
