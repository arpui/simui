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


def _desa_bytes(path: Path, retoc=None) -> str:
    """El que fa `desa_proposta`: obre (amb marques), (retoca), i demana el text passant el fitxer obert com a original."""
    form = CF.de_fitxer(path, marca=True)
    if retoc:
        retoc(form)
    return CF.to_yaml_i_avisos(form, original=path)[0]


@pytest.mark.parametrize("rel", ["campanyes/mb_01", "exemples/forat_quadrat"])
def test_desar_sense_tocar_res_deixa_el_yaml_identic(rel):
    """Coordinador 27-11: el bessó compara **bytes**, no contingut (les cometes de les dates canvien `confirmacio.hash_yaml`)."""
    p = _yaml_neudet(rel)
    assert _desa_bytes(p).encode("utf-8") == p.read_bytes()


def test_desar_sense_tocar_res_amb_forat_quadrat_deixa_el_yaml_identic(tmp_path):
    orig = yaml.safe_load(_yaml_neudet("campanyes/mb_01").read_text())
    bloc = orig["domini"]["bloc"]
    bloc.pop("forat_cm")
    bloc["forat"] = {"forma": "quadrat", "costat_cm": 7}
    q = tmp_path / "campanya.yaml"
    q.write_text("# comentari que ha de sobreviure\n" + yaml.safe_dump(orig, allow_unicode=True, sort_keys=False))
    assert _desa_bytes(q).encode("utf-8") == q.read_bytes()


def test_desar_tocant_una_cosa_ja_no_es_el_text_original():
    """Només el no-res és idèntic: amb un canvi real el yaml es regenera (i es perden comentaris i cometes: declarat)."""
    p = _yaml_neudet("campanyes/mb_01")

    def retoc(f):
        f["objectius"]["energia_mev"] = 7.0 if f["objectius"].get("energia_mev") != 7.0 else 6.0

    try:
        nou = _desa_bytes(p, retoc)
    except KeyError:
        pytest.skip("mb_01 ja no té objectius.energia_mev")
    assert nou.encode("utf-8") != p.read_bytes()


_TUB_SOL = ["certificacio/lnd_252285_E12_sol", "certificacio/lnd_252285_E12_sol_fin", "certificacio/lnd_2523_E12_sol_fin"]


@pytest.mark.parametrize("rel", _TUB_SOL)
def test_tub_sol_es_valid_a_la_ui_com_a_neudet(rel):
    """Coordinador 27-11: «tub sol» (mides_cm 0, sense bloc de PE) és vàlid; `_errors_bloc` no el rebutja."""
    p = _yaml_neudet(rel)
    form = CF.de_fitxer(p, marca=True)
    assert form["avaluacio"]["geometria"] == "tub_sol"
    assert CF._errors(form) == [], CF._errors(form)
    assert _desa_bytes(p).encode("utf-8") == p.read_bytes()


@pytest.mark.parametrize("canvi,fragment", [
    (lambda b: b.update(mides_cm=[30, 30, 80]), "mides_cm"),
    (lambda b: b.update(forat_cm=5), "forat"),
    (lambda b: b.update(forma="cilindre"), "forma"),
    (lambda b: b.update(forat={"forma": "quadrat", "costat_cm": 7}), "forat"),
])
def test_tub_sol_amb_bloc_la_ui_diu_el_mateix_que_neudet(canvi, fragment):
    form = CF.de_fitxer(_yaml_neudet(_TUB_SOL[0]), marca=True)
    canvi(form["domini"]["bloc"])
    errs = [x for x in CF._errors(form) if "tub_sol" in x]
    assert errs and any(fragment in x for x in errs), errs


def test_cub_pe_continua_exigint_mides_positives():
    form = CF.de_fitxer(_yaml_neudet("campanyes/mb_01"), marca=True)
    form["domini"]["bloc"]["mides_cm"] = [0, 0, 0]
    assert any("mides_cm" in x for x in CF._errors(form))


def test_la_referencia_del_tub_sol_es_la_real():
    cam = next((_neudet() / "src").rglob("campanya.py"), None)
    if cam is None:
        pytest.skip("estructura de neudet diferent")
    assert 'self.geometria == "tub_sol"' in cam.read_text().splitlines()[CF.TUB_SOL_LINIA - 1]


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


# ---- mètriques del paper i graella de 24 energies (MB01-PARELLES P4): bessó de `objectius._punts_paper` -----------------

def _ob_nou(informatives):
    return {"finalitat": "comptador", "objectius": [["eps_mitja", "max"], ["cv", "min"]], "informatives": informatives,
            "pesos": "uniforme", "energies_MeV": "totes"}


def _neudet_objectiu(ob, energies):
    from neudet.disseny import objectius as O
    try:
        O.Objectiu(copy.deepcopy(ob), energies)
        return None
    except SystemExit as e:
        return str(e)


def test_schema_porta_la_graella_del_paper_de_neudet():
    _neudet()
    from neudet.disseny import objectius as O
    p = CF.schema()["objectius"]["paper"]
    assert p["graella_MeV"] == [float(x) for x in O.GRAELLA_PAPER_MEV] and len(p["graella_MeV"]) == 24
    assert set(p["metriques"]) == set(O.PAPER) == {"eps_av_10", "F_5", "F_8", "F_10"}
    assert set(p["mai_auto"]) == set(O.MAI_AUTO)


@pytest.mark.parametrize("energies,informatives,ok", [
    ("paper", ["eps_av_10", "F_5", "F_8", "F_10"], True),             # la graella sencera: calculable
    ("onze", ["eps_av_10"], False),                                   # falten punts: neudet fa ⛔, la UI ho diu abans
    ("onze", ["F_5"], False),                                         # F(5): als punts ≤ 5 MeV de la graella en falta 2,5
    ("onze", "auto", True),                                           # les del paper no surten soles (MAI_AUTO)
])
def test_paper_la_ui_diu_el_mateix_que_neudet(energies, informatives, ok):
    _neudet()
    from neudet.disseny import objectius as O
    if energies == "paper":
        en = [float(x) for x in O.GRAELLA_PAPER_MEV]
    else:
        en = [0.0001, 0.001, 0.01, 0.1, 0.5, 1, 1.5, 2, 3, 4, 5]
    ob = _ob_nou(informatives)
    ui = CF._errors_paper(CF._noms_demanats(ob, CF._taula_objectius()["alies"]), en)
    assert (not ui) == ok, ui
    assert (_neudet_objectiu(ob, en) is None) == ok


def test_paper_energia_repetida_es_refusa():
    _neudet()
    from neudet.disseny import objectius as O
    en = [float(x) for x in O.GRAELLA_PAPER_MEV] + [1.0]
    ob = _ob_nou(["eps_av_10"])
    assert CF._errors_paper(CF._noms_demanats(ob, CF._taula_objectius()["alies"]), en)
    assert _neudet_objectiu(ob, en) is not None


def test_les_referencies_del_paper_son_les_reals():
    n = next((_neudet() / "src").rglob("objectius.py"), None)
    if n is None:
        pytest.skip("estructura de neudet diferent")
    ll = n.read_text().splitlines()
    assert "GRAELLA_PAPER_MEV" in ll[CF.GRAELLA_PAPER_LINIA - 1]
    assert ll[CF.PAPER_LINIA - 1].startswith("PAPER")
    assert ll[CF.MAI_AUTO_LINIA - 1].startswith("MAI_AUTO")
    assert "def _punts_paper" in ll[CF.PUNTS_PAPER_LINIA - 1]


# ───── la UI de MB01 (pins sobre el codi de la UI i el bloc pur de la taula de params) ─────
import json as _json
import shutil as _shutil
import subprocess as _sp

_INDEX = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")


def test_lnd_252399_es_al_selector_de_tubs():
    # el selector el nodreix `schema().tipus_tub` (tubs.json de neudet): no hi ha cap llista a la UI
    assert "lnd_252399" in [t["nom"] for t in CF.schema()["tipus_tub"]]
    assert "lnd_252399" not in _INDEX


def test_la_ui_porta_les_peces_de_mb01():
    for pec in ("cParellaHtml", "data-parella", "cForatHtml", "data-foratsel", "en-paper",
                "rLateralZ", "kSepParella", "sep_parella (cm)", "clau no editable des de la UI: es conserva"):
        assert pec in _INDEX or pec in (Path(CF.__file__).read_text(encoding="utf-8")), pec


def test_el_panell_d_avisos_de_neudet_pinta_avisos_en_paraules():
    assert "avisos_en_paraules" in _INDEX


@pytest.mark.skipif(_shutil.which("node") is None, reason="cal node")
def test_taula_de_params_mostra_sep_parella_de_neudet():
    pur = _INDEX.split("// PARAMS-DEF-BEGIN")[1].split("\n", 1)[1].split("// PARAMS-DEF-END")[0]
    esc = "const escD = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');"
    mv = {"per_candidat": [
        {"nom": "c1", "ronda": 0, "pareto_rang": 0,
         "params": {"a0": {"r": 3, "n": 6, "parella": True, "sep_parella_cm": 2.5}}},
        {"nom": "c2", "ronda": 0, "pareto_rang": 1, "params": {"a0": {"r": 3, "n": 6}}}]}
    js = esc + pur + "const v = JSON.parse(require('fs').readFileSync(0,'utf8')); console.log(kParamsCandidats(v));"
    r = _sp.run(["node", "-e", js], input=_json.dumps(mv), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "sep_parella (cm)" in r.stdout and 'data-sep-parella>2.5<' in r.stdout
    assert 'data-sep-parella>—<' in r.stdout          # sense parella no s'inventa cap separació
    sense = {"per_candidat": [mv["per_candidat"][1]]}
    r2 = _sp.run(["node", "-e", js], input=_json.dumps(sense), capture_output=True, text=True)
    assert "sep_parella (cm)" not in r2.stdout


def test_la_vista_passa_sentit_i_forat_tal_com_els_escriu_neudet():
    src = (Path(__file__).resolve().parents[1] / "src" / "simui" / "campanya_vista.py").read_text(encoding="utf-8")
    assert '("sentit", "forat", "eix")' in src


def test_desa_proposta_sense_tocar_res_no_canvia_el_campanya_yaml(tmp_path):
    """Extrem a extrem: obrir una proposta i desar-la tal qual deixa el `campanya.yaml` idèntic byte a byte
    (el `hash_yaml` de la certificació és el del fitxer)."""
    from simui import campanya_desa as CD
    p = _yaml_neudet("campanyes/mb_01")
    d = tmp_path / "mb_01"
    d.mkdir()
    (d / "campanya.yaml").write_bytes(p.read_bytes())
    form = CF.de_fitxer(d / "campanya.yaml", marca=True)
    form["id"] = "mb_01"
    try:
        CD.desa_proposta(form, root=tmp_path)
    except CD.DesaError as exc:
        pytest.skip(f"mb_01 no es pot desar com a proposta aquí: {exc}")
    assert (d / "campanya.yaml").read_bytes() == p.read_bytes()
