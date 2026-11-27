"""test_verif_energies_ui.py — VER-24E (neudet, contracte §31 v1.30): `verificacio.energies_MeV` editable a la UI (27-11).

La UI no calcula res: valida cridant `neudet.disseny.verif_energies.violacions` i `fitxa.falten` (la contenció del domini), i
ofereix com a botó la graella de 24 E del paper que neudet escriu a `objectius.py` (la mateixa del botó del domini).

Test bessó: la plantilla (`c04_draft`) sense la clau és vàlida als dos llocs i el viatge UI és idèntic; amb la clau (domini + les
del paper) també; els casos erronis donen a la UI el mateix que a neudet; i `mb_01`, que ja porta les 24 E, les conserva.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simui import campanya_form as CF  # noqa: E402
from simphy.mcgen import design as DES  # noqa: E402


def _neudet() -> Path:
    try:
        return DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def _camp(nom: str) -> Path:
    p = _neudet() / "disseny" / "campanyes" / nom / "campanya.yaml"
    if not p.is_file():
        pytest.skip(f"{p} no existeix: neudet ha mogut la campanya")
    return p


def _ve():
    _neudet()
    m = CF._mod_verif_energies()
    if m is None:
        pytest.skip("neudet no té verif_energies.py (anterior a v1.30, §31)")
    return m


def _form(retoc=None):
    f = CF.de_fitxer(_camp("c04_draft"), marca=True)
    if retoc:
        retoc(f)
    return f


def _graella_paper():
    return list(CF.schema()["objectius"]["paper"]["graella_MeV"])


def _falten_neudet(f) -> list:
    """El veredicte de neudet sobre el yaml que la UI escriuria (la part de verificacio.energies_MeV)."""
    _ve()
    from neudet.disseny import fitxa
    cfg = copy.deepcopy(f)
    for k in CF.CLAUS_FORMULARI:
        cfg.pop(k, None)
    return [x for x in fitxa.falten(cfg) if "verificacio.energies_MeV" in x]


def _amb(valor):
    def r(f):
        f.setdefault("verificacio", {})["energies_MeV"] = valor
    return r


def _sense_una_del_domini(f):
    g = _domini_mes_paper(f)
    g.remove(float(f["domini"]["energies_MeV"][0]))
    return g


def _domini_mes_paper(f):
    dom = [float(e) for e in f["domini"]["energies_MeV"]]
    return sorted(set(dom) | set(_graella_paper()))


# ── la clau és coneguda: editable, no «no editable» ─────────────────────────────────────────────────────────────────
def test_la_clau_es_a_l_esquema_i_llegida_per_neudet():
    _ve()
    s = CF.schema()["verificacio"]["energies_MeV"]
    assert s["llegit"] is True and s["fitxer"] == CF.VERIF_ENERGIES_PY
    assert s["linia"] != "?"


def test_la_linia_del_pin_es_la_real():
    """`def violacions` és a la línia que la UI diu (si neudet es mou, el pin el segueix)."""
    _ve()
    p = _neudet() / "src" / "neudet" / "disseny" / CF.VERIF_ENERGIES_PY
    n = CF.schema()["verificacio"]["energies_MeV"]["linia"]
    assert "def violacions" in p.read_text().splitlines()[int(n) - 1]


def test_la_graella_del_paper_son_24_energies_de_neudet():
    g = _graella_paper()
    assert len(g) == 24 and g == sorted(set(g))
    assert CF.schema()["objectius"]["paper"]["linia"] == CF.GRAELLA_PAPER_LINIA


# ── bessó: sense la clau res no canvia ──────────────────────────────────────────────────────────────────────────────
def test_la_plantilla_sense_la_clau_es_valida_i_el_viatge_no_la_afegeix():
    _ve()
    f = _form()
    assert "energies_MeV" not in (f.get("verificacio") or {})
    assert CF._errors(f) == [], CF._errors(f)
    assert _falten_neudet(f) == []
    text, _ = CF.to_yaml_i_avisos(f)
    assert "energies_MeV" not in yaml.safe_load(text)["verificacio"]


def test_el_viatge_sense_la_clau_es_identic_bit_a_bit():
    """Obrir i desar la plantilla sense tocar-la no canvia res (la clau nova no apareix ni com a `null`)."""
    _ve()
    p = _camp("c04_draft")
    a = CF.to_yaml_i_avisos(CF.de_fitxer(p, marca=True))[0]
    b = CF.to_yaml_i_avisos(CF.de_fitxer(p, marca=True))[0]
    assert a == b and "energies_MeV: null" not in a
    assert yaml.safe_load(a)["verificacio"] == yaml.safe_load(p.read_text())["verificacio"]


# ── bessó: amb la clau (domini + les del paper) és vàlid als dos llocs i fa round trip ─────────────────────────────
def test_amb_les_del_domini_mes_el_paper_es_valid_als_dos_llocs_i_fa_round_trip():
    _ve()
    f = _form()
    g = _domini_mes_paper(f)
    _amb(g)(f)
    assert CF._errors(f) == [], CF._errors(f)
    assert _falten_neudet(f) == []
    text, avisos = CF.to_yaml_i_avisos(f)
    assert not [a for a in avisos if "energies_MeV" in a], avisos
    assert yaml.safe_load(text)["verificacio"]["energies_MeV"] == g
    assert "verificacio.energies_MeV" not in " ".join(f.get("_no_editables") or [])


def test_canviar_la_clau_no_toca_la_resta_de_verificacio():
    _ve()
    f = _form()
    abans = copy.deepcopy(f["verificacio"])
    _amb(_domini_mes_paper(f))(f)
    text, _ = CF.to_yaml_i_avisos(f)
    v = yaml.safe_load(text)["verificacio"]
    v.pop("energies_MeV")
    assert v == yaml.safe_load(CF.to_yaml_i_avisos(CF.de_fitxer(_camp("c04_draft"), marca=True))[0])["verificacio"]
    assert {k: x for k, x in f["verificacio"].items() if k != "energies_MeV"} == abans


# ── bessó: els casos erronis, el mateix que neudet ──────────────────────────────────────────────────────────────────
CASOS = {
    "buida": lambda f: [],
    "no_llista": lambda f: 5,
    "text": lambda f: ["a", "b"],
    "zero": lambda f: [0] + _domini_mes_paper(f),
    "negativa": lambda f: [-1.0] + _domini_mes_paper(f),
    "no_creixent": lambda f: list(reversed(_domini_mes_paper(f))),
    "repetida": lambda f: _domini_mes_paper(f) + [_domini_mes_paper(f)[-1]],
    "bool": lambda f: [True] + _domini_mes_paper(f)[1:],
    "falta_una_del_domini": lambda f: _sense_una_del_domini(f),
}


@pytest.mark.parametrize("cas", sorted(CASOS))
def test_cas_erroni_la_ui_diu_el_mateix_que_neudet(cas):
    _ve()
    f = _form()
    _amb(CASOS[cas](f))(f)
    ui = [e for e in CF._errors(f) if "verificacio.energies_MeV" in e]
    nd = _falten_neudet(f)
    assert nd, f"neudet hauria de refusar {cas}"
    assert ui == nd, (ui, nd)


def test_la_contencio_del_domini_diu_quines_en_falten():
    _ve()
    f = _form()
    _amb(_sense_una_del_domini(f))(f)
    ui = [e for e in CF._errors(f) if "verificacio.energies_MeV" in e]
    assert ui and "en falten" in ui[0] and ("%g" % float(f["domini"]["energies_MeV"][0])) in ui[0]


# ── mb_01 ja porta les 24 E: la UI les conserva ────────────────────────────────────────────────────────────────────
def test_mb_01_porta_les_24_E_i_la_ui_les_conserva():
    _ve()
    p = _camp("mb_01")
    orig = yaml.safe_load(p.read_text())["verificacio"].get("energies_MeV")
    if orig is None:
        pytest.skip("mb_01 ja no porta verificacio.energies_MeV")
    f = CF.de_fitxer(p, marca=True)
    assert f["verificacio"]["energies_MeV"] == orig
    assert not [e for e in CF._errors(f) if "verificacio.energies_MeV" in e], CF._errors(f)
    assert yaml.safe_load(CF.to_yaml_i_avisos(f)[0])["verificacio"]["energies_MeV"] == orig
    assert orig == _graella_paper()                    # la del paper: la mateixa que ofereix el botó
