"""test_roundtrip_ui.py — MB01-UI: el formulari MAI no perd una clau en desar (coordinador, 27-11).

Les claus que la UI no sap editar es conserven tal com són (round-trip) i es llisten amb l'avís
«clau no editable des de la UI: es conserva». Test bessó: desar el yaml de mb_01 (i un amb forat) sense tocar res
deixa el fitxer idèntic (les dades llegides, no els bytes: el yaml es torna a escriure amb la capçalera de la UI).

Divergències fixades (docs/ui.md): la UI exigia exactament 2 parells al pareto; neudet n'accepta ≥ 1
(`campanya.py:923`). Sense neudet, els tests que en necessiten es salten.
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


def _yaml_neudet(rel: str) -> Path:
    p = _neudet() / "disseny" / rel / "campanya.yaml"
    if not p.is_file():
        pytest.skip(f"{p} no existeix: neudet ha mogut l'exemple")
    return p


def _desa(path: Path, retoc=None) -> dict:
    """El que fa la UI: obre (amb marques), (retoca), desa; retorna el yaml tornat a llegir."""
    form = CF.de_fitxer(path, marca=True)
    if retoc:
        retoc(form)
    return yaml.safe_load(CF.to_yaml(form))


def _sense_dates(x):
    """neudet escriu `confirmacio.data` amb cometes; la UI escriu les dates ISO sense (`_Dumper`): divergència declarada."""
    if isinstance(x, dict):
        return {k: _sense_dates(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_sense_dates(v) for v in x]
    return str(x) if hasattr(x, "isoformat") else x


@pytest.mark.parametrize("rel", ["campanyes/mb_01", "exemples/forat_quadrat"])
def test_desar_sense_tocar_res_deixa_el_yaml_identic(rel):
    p = _yaml_neudet(rel)
    orig, nou = yaml.safe_load(p.read_text()), _desa(p)
    if "generador" in str(orig.get("etapes")):
        # yaml antic: el generador passa a tongades (conversió declarada, `tradueix_antic` de neudet); la resta no canvia
        orig.pop("etapes"), nou.pop("etapes")
    assert _sense_dates(nou) == _sense_dates(orig)


def test_mb01_amb_forat_quadrat_sense_tocar_res():
    """mb_01 amb `forat: {forma: quadrat, costat_cm: 7}` en lloc de `forat_cm` (MB01-PARELLES P3)."""
    orig = yaml.safe_load(_yaml_neudet("campanyes/mb_01").read_text())
    bloc = orig["domini"]["bloc"]
    bloc.pop("forat_cm")
    bloc["forat"] = {"forma": "quadrat", "costat_cm": 7}
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        q = Path(d) / "campanya.yaml"
        q.write_text(yaml.safe_dump(orig, allow_unicode=True, sort_keys=False))
        assert _sense_dates(_desa(q)) == _sense_dates(yaml.safe_load(q.read_text()))


def test_claus_desconegudes_sobreviuen_i_es_llisten():
    """Una clau que la UI no coneix, a qualsevol nivell, no es perd en desar i apareix a `_no_editables`."""
    p = _yaml_neudet("campanyes/mb_01")
    orig = yaml.safe_load(p.read_text())

    def retoc(f):
        f["clau_nova_top"] = {"a": 1}
        f["domini"]["clau_nova_domini"] = [1, 2]
        f["domini"]["bloc"]["clau_nova_bloc"] = "x"
        f["etapes"]["S1"]["clau_nova_etapa"] = True
        f["etapes"]["S1"]["tongades"][0]["clau_nova_tongada"] = 3

    form = CF.de_fitxer(p, marca=True)
    retoc(form)
    nou = yaml.safe_load(CF.to_yaml(form))
    assert nou["clau_nova_top"] == {"a": 1}
    assert nou["domini"]["clau_nova_domini"] == [1, 2]
    assert nou["domini"]["bloc"]["clau_nova_bloc"] == "x"
    assert nou["etapes"]["S1"]["clau_nova_etapa"] is True
    assert nou["etapes"]["S1"]["tongades"][0]["clau_nova_tongada"] == 3
    llistes = CF.claus_no_editables(form)
    for r in ("clau_nova_top", "domini.clau_nova_domini", "domini.bloc.clau_nova_bloc", "etapes.S1.clau_nova_etapa",
              "etapes.S1.tongades[0].clau_nova_tongada"):
        assert r in llistes, (r, llistes)
    # el que no s'ha tocat segueix igual
    assert nou["avaluacio"] == orig["avaluacio"]


def test_claus_del_formulari_no_arriben_al_yaml():
    form = CF.de_fitxer(_yaml_neudet("campanyes/mb_01"), marca=True)
    assert CF.NO_EDITABLES in form          # mb_01 porta motors, verificacio.quants, …
    y = yaml.safe_load(CF.to_yaml(form))
    assert not [k for k in y if k.startswith("_")]


def test_les_claus_no_editables_de_mb01_son_les_que_neudet_llegeix():
    """Les rutes no editables de mb_01 (avaluacio.motors, verificacio.quants, etapes.X.motors) són al fitxer d'origen."""
    p = _yaml_neudet("campanyes/mb_01")
    orig = yaml.safe_load(p.read_text())
    form = CF.de_fitxer(p, marca=True)
    for r in form[CF.NO_EDITABLES]:
        d = orig
        for k in r.replace("]", "").replace("[", ".").split("."):
            d = d[int(k)] if isinstance(d, list) else d[k]


def test_tipus_tub_explicit_es_conserva():
    """`domini.tipus_tub` que ja és al yaml no el treu SIMPLIFICA (és seu); un que la UI deriva, sí."""
    d = {"id": "t", "domini": {"tipus_tub": ["lnd_a"]}}
    f = CF.marca_no_editables(copy.deepcopy(d))
    assert f[CF.CONSERVA] == ["domini.tipus_tub"]
    f2 = CF.marca_no_editables({"id": "t", "domini": {}})
    assert CF.CONSERVA not in f2


def test_pareto_d_un_parell_es_valid_a_neudet_i_a_la_ui():
    """Divergència fixada: neudet carrega qualsevol llista de parells (`objectius.py:293`, `campanya.py:923`)."""
    _neudet()
    f = CF.defaults()
    f["objectius"] = {"metriques": ["eps_mitja", "cv"], "pareto": [["eps_mitja", "max"]]}
    yaml.safe_load(CF.to_yaml(f))                                    # un de sol val (eix X i Y alhora)
    f["objectius"]["pareto"] = []
    with pytest.raises(CF.FormError, match="objectius.pareto"):
        CF.to_yaml(f)


# ---- forat i parella: el bessó de la validació de neudet --------------------------------------------------------------

def _bloc_errors(bloc):
    return CF._errors_forat(bloc, "domini.bloc")


@pytest.mark.parametrize("forat,ok", [
    ({"forma": "quadrat", "costat_cm": 7}, True),
    ({"forma": "cilindre", "radi_cm": 3.95}, True),
    ({"forma": "quadrat"}, False),
    ({"forma": "quadrat", "radi_cm": 3}, False),
    ({"forma": "triangle", "costat_cm": 3}, False),
    ({"costat_cm": 7}, False),
    ({"forma": "quadrat", "costat_cm": 0}, False),
])
def test_forat_la_ui_diu_el_mateix_que_neudet(forat, ok):
    ui_ok = not _bloc_errors({"forat": forat})
    assert ui_ok == ok
    try:
        from neudet.disseny import candidat as C   # noqa: F401
    except Exception:
        return
    # neudet: mateixa conclusió (violacions_forat és el seu veredicte)
    fn = getattr(C, "violacions_forat", None)
    if fn is not None:
        try:
            viol = fn({"forat": forat})
        except TypeError:
            return
        assert (not viol) == ok


def test_forat_i_forat_cm_alhora_es_refusa():
    assert _bloc_errors({"forat": {"forma": "quadrat", "costat_cm": 7}, "forat_cm": 3.95})


@pytest.mark.parametrize("a,ok", [
    ({"parella": True, "sep_parella_cm": 2}, True),
    ({"parella": True, "sep_parella_cm": [2, 4]}, True),
    ({"parella": True, "sep_parella_cm": {"de": 1, "a": 5, "pas": 2}}, True),
    ({"parella": True}, False),                                   # sense separació: cap valor per defecte
    ({"parella": True, "sep_parella_cm": 2, "z": 0}, False),      # la z surt de la separació
    ({"parella": True, "sep_parella_cm": -1}, False),
    ({"sep_parella_cm": 2}, False),                               # separació sense parella
    ({"parella": "si", "sep_parella_cm": 2}, False),
    ({"parella": False}, True),
    ({}, True),
])
def test_parella(a, ok):
    assert (not CF._errors_parella(a, "anells[0]", 0)) == ok


def test_les_referencies_a_neudet_son_les_reals():
    """Les línies citades als missatges són les de neudet avui (si neudet es mou, el test les segueix)."""
    n = _neudet() / "src"
    cand = next(n.rglob("candidat.py"), None)
    gen = next(n.rglob("generadors.py"), None)
    fit = next(n.rglob("fitxa.py"), None)
    cam = next(n.rglob("campanya.py"), None)
    if not all((cand, gen, fit, cam)):
        pytest.skip("estructura de neudet diferent")

    def linia(p, n_):
        return p.read_text().splitlines()[n_ - 1]

    assert "violacions_forat" in linia(cand, CF.FORAT_LINIA)
    assert "FORMES_FORAT" in linia(cand, CF.FORMES_FORAT_LINIA)
    assert "FORAT_ALTERNATIVA" in linia(fit, CF.FORAT_ALT_LINIA)
    assert "_parella_anell" in linia(gen, CF.PARELLA_LINIA)
    assert "pareto" in linia(cam, CF.PARETO_ARRELS_LINIA)
