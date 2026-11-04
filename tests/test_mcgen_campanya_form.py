"""test_mcgen_campanya_form.py — el formulari de Definició de campanya (C1) i la comprovació (C2).

Què es fixa
-----------
- `defaults()` és el campanya.yaml de c04_draft llegit de neudet (les dates, com a text ISO).
- `to_yaml(defaults())` torna a llegir-se com el mateix diccionari que el c04 de neudet: el formulari
  no perd ni inventa cap clau.
- `schema()` ve de neudet: els tipus són els de `GENERADORS`, i cada clau que simphy en cita està
  a la línia de `generadors.py` que diu (el test bessó de la taula `CAMPS`).
- Sense `validacions.json` (CAMP-1), cap tub porta marca de validat: el registre no s'inventa.
- Un formulari que neudet no podria llegir es rebutja amb tots els motius, no amb un yaml trencat.
- Les agrupacions de motius de la comprovació compten candidats, i el script de certificació, si hi és,
  es corre i la seva sortida es torna sense interpretar.

Sense neudet, els tests que en necessiten es salten; els de forma (errors, agrupació) no.
"""
from __future__ import annotations

import json

import datetime as dt
import sys
from pathlib import Path

import copy

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simphy.mcgen import campanya_check as CC  # noqa: E402
from simphy.mcgen import campanya_form as CF  # noqa: E402
from simphy.mcgen import design as DES  # noqa: E402
from simphy.mcgen import detector_config as DC  # noqa: E402


def _neudet_o_skip() -> Path:
    try:
        return DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def _c04_text() -> str:
    return (_neudet_o_skip() / CF.C04_YAML).read_text()


def _c04_dict() -> dict:
    return yaml.safe_load(_c04_text())


def _sense_dates(x):
    """El c04 de neudet porta `creada` com a data; el formulari la porta com a text ISO."""
    if isinstance(x, dict):
        return {k: _sense_dates(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_sense_dates(v) for v in x]
    if isinstance(x, (dt.date, dt.datetime)):
        return x.isoformat()
    return x


# ── defaults i round trip ───────────────────────────────────────────────────

def test_defaults_es_el_c04_de_neudet():
    _neudet_o_skip()
    d = CF.defaults()
    assert d["id"] == "c04_draft"
    assert d["creada"] == "2026-10-26"                       # data → text ISO
    assert d == _sense_dates(_c04_dict())                    # ni una clau de més ni de menys


def test_to_yaml_round_trip_amb_c04():
    """defaults() → to_yaml → safe_load = el c04 de neudet, per a totes les claus."""
    _neudet_o_skip()
    torna = yaml.safe_load(CF.to_yaml(CF.defaults()))
    assert torna == _c04_dict()
    assert isinstance(torna["creada"], dt.date)              # neudet la llegirà com a data


def test_to_yaml_no_muta_el_formulari():
    _neudet_o_skip()
    d = CF.defaults()
    before = repr(d)
    CF.to_yaml(d)
    assert repr(d) == before


def test_to_yaml_no_posa_cometes_a_les_dates_ni_a_les_cadenes_normals():
    dom = {
        "bloc": {"material": "PE", "mides_cm": [30, 30, 80], "forat_cm": 0, "densitat_gcm3": 0.95},
        "font": {"tipus": "iso", "pos_cm": [0, 0, 0]},
        "energies_MeV": [0.001, 1.0],
        "tipus_tub": ["lnd_252285"],
        "restriccions": {"n_tubs": 1, "marge_bloc_cm": 1.0, "sep_min_cm": 0.1, "r_min_font_cm": 0.5},
    }
    etapes = {"S1": {"que": "prova", "generador": {"tipus": "mapa_un_tub", "x": [1], "y": [2]}}}
    f = {"id": "x1", "fitxa": 1, "draft": True, "estat": "definida", "creada": "2026-01-02",
         "domini": dom, "etapes": etapes}
    text = CF.to_yaml(f)
    assert "creada: 2026-01-02" in text                      # plana: neudet la llegeix com a data
    assert "material: PE" in text
    torna = yaml.safe_load(text)
    assert torna["creada"] == dt.date(2026, 1, 2)
    assert torna["domini"]["bloc"]["material"] == "PE"


# ── formulari invàlid: error clar amb tots els motius ───────────────────────

def _form_minim() -> dict:
    return {"id": "c05_prova", "domini": {
        "bloc": {"material": "PE", "mides_cm": [30, 30, 80], "forat_cm": 0},
        "font": {"tipus": "iso", "pos_cm": [0, 0, 0]}, "energies_MeV": [0.001, 1.0],
        "tipus_tub": ["lnd_252285"], "restriccions": {"n_tubs": 2}},
        "etapes": {"S1": {"generador": {"tipus": "anells", "anells": [{"r": 3, "n": 2}]}}}}


def test_formulari_minim_es_escriu():
    yaml.safe_load(CF.to_yaml(_form_minim()))                 # no llança


@pytest.mark.parametrize("canvi, missatge", [
    (lambda f: f.__setitem__("id", "mal id!"), "id:"),
    (lambda f: f["domini"].__setitem__("energies_MeV", []), "energies_MeV"),
    (lambda f: f["domini"]["energies_MeV"].__setitem__(0, -1), "energies_MeV"),
    (lambda f: f["domini"]["restriccions"].__setitem__("n_tubs", 0), "n_tubs"),
    (lambda f: f["domini"]["font"].__setitem__("tipus", "pla"), "font.tipus"),
    (lambda f: f["etapes"]["S1"]["generador"].__setitem__("tipus", "inventat"), "no és un generador conegut"),
    (lambda f: f["etapes"]["S1"]["generador"]["anells"][0].pop("r"), "falta «r»"),
    (lambda f: f["etapes"]["S1"]["generador"].pop("anells"), "falta «anells»"),
    (lambda f: f.pop("etapes"), "etapes"),
])
def test_formulari_invalid_diu_que_cal_canviar(canvi, missatge):
    f = _form_minim()
    canvi(f)
    with pytest.raises(CF.FormError) as exc:
        CF.to_yaml(f)
    assert missatge in str(exc.value)
    assert str(exc.value).startswith("formulari no vàlid")


def test_formulari_invalid_dona_tots_els_motius():
    f = _form_minim()
    f["id"] = ""
    f["domini"]["energies_MeV"] = []
    with pytest.raises(CF.FormError) as exc:
        CF.to_yaml(f)
    assert str(exc.value).count("\n- ") == 2


# ── schema: de neudet ───────────────────────────────────────────────────────

def test_schema_tipus_son_els_de_generadors_py():
    _neudet_o_skip()
    _, G = DES._neudet()                                       # importa neudet.disseny.generadors
    s = CF.schema()
    assert [g["tipus"] for g in s["generadors"]] == sorted(G.GENERADORS)
    assert set(CF.CAMPS) == set(G.GENERADORS), "cada generador de neudet ha de tenir els seus camps a simphy"
    assert not [g for g in s["generadors"] if "gap" in g]


def test_camps_citats_a_la_linia_de_generadors_py():
    """Test bessó de la taula CAMPS: la clau és entre cometes a la línia que la taula diu."""
    root = _neudet_o_skip()
    linies = (root / "src" / "neudet" / "disseny" / "generadors.py").read_text().splitlines()
    fallades = []
    for tipus, info in CF.CAMPS.items():
        for c in info["camps"]:
            if not any(f'"{c["clau"]}"' in l for l in linies):
                fallades.append(f'{tipus}.{c["clau"]} no és a generadors.py:{c["linia"]}')
    assert not fallades, "\n".join(fallades)


def test_tubs_del_catalog_sense_registre_de_validacio():
    _neudet_o_skip()
    s = CF.schema()
    noms = [t["nom"] for t in s["tipus_tub"]]
    assert "lnd_252285" in noms
    if not s["validacio"]["registre"]:
        assert all(t["validat"] is None for t in s["tipus_tub"])
        assert "CAMP-1" in s["validacio"]["motiu"]
        assert all("CAMP-1" in t["estat"] for t in s["tipus_tub"])


def test_registre_de_validacio_ve_de_neudet(tmp_path, monkeypatch):
    """La marca de cada tub la decideix neudet (`fitxa._entrada_tub`: àlies i patrons), del seu registre."""
    _neudet_o_skip()
    (tmp_path / "validacions.json").write_text(json.dumps({"versio": 1, "entrades": {
        "tub:lnd_252285": {"estat": "validat", "motiu": "V-TUB"},
        "tub:lnd_sk*": {"estat": "no_validat", "motiu": "cal banc"}}}))
    monkeypatch.setattr(DC, "config_dir", lambda: tmp_path)
    s = CF.schema()
    t = {x["nom"]: x for x in s["tipus_tub"]}
    assert t["lnd_252285"]["estat"] == "validat" and t["lnd_252285"]["validat"] is True
    sk = [n for n in t if n.startswith("lnd_sk")]
    assert sk and all(t[n]["estat"] == "no_validat" and t[n]["motiu"] == "cal banc" for n in sk)
    assert s["validacio"]["registre"] is True


def test_cd_opcions_del_contracte():
    assert CF.CD_FRACCIONS == [0, 0.25, 0.5, 0.75, 1]
    assert CF.CD_ARCS_DEG == [360, 180]


# ── comprovació: agrupació de motius i script ───────────────────────────────

class _Cand:
    def __init__(self, nom):
        self.nom = nom


def test_motius_agrupa_per_text_i_conta_candidats():
    invalids = [(_Cand("a"), ["tubs 0 i 1 se solapen", "tub 2 fora del bloc (marge 1)"]),
                (_Cand("b"), ["tubs 3 i 4 se solapen"]),
                (_Cand("c"), ["tub 0 fora del bloc (marge 1)", "tub 0 fora del bloc (marge 1)"])]
    m = {x["motiu"]: x for x in CC._motius(invalids)}
    assert m["tubs # i # se solapen"]["n_candidats"] == 2
    assert m["tubs # i # se solapen"]["exemple"] == "tubs 0 i 1 se solapen"
    assert m["tub # fora del bloc (marge #)"]["n_candidats"] == 2   # a «c» compta un cop, no dos
    assert CC._motius([]) == []


def _script(tmp_path, cos):
    script = tmp_path / "scripts" / "disseny" / "comprova_campanya.py"
    script.parent.mkdir(parents=True)
    script.write_text(cos)
    dir_ = tmp_path / "w" / "campanya"
    dir_.mkdir(parents=True)
    return script, dir_


def test_certificacio_es_el_json_de_neudet_tal_com_ve(tmp_path):
    """`comprova_campanya.py <dir> --json <fitxer>`: el que escriu és la certificació (sense reinterpretar)."""
    script, dir_ = _script(tmp_path, (
        "import json, sys\n"
        "assert sys.argv[2] == '--json'\n"
        "json.dump({'atura': False, 'draft': True, 'etapes': {'S1': {'valids': 3}},\n"
        "           'elements': [{'element': 'Cd sobre lnd_252285', 'estat': 'no_validat',\n"
        "                         'motiu': 'TUB-4', 'document': ''}]}, open(sys.argv[3], 'w'))\n"))
    c = CC._certifica(script, dir_)
    assert c["disponible"] is True and c["atura"] is False and c["draft"] is True
    assert c["elements"][0]["estat"] == "no_validat" and c["elements"][0]["motiu"] == "TUB-4"


def test_si_el_script_peta_es_mostra_el_seu_error(tmp_path):
    script, dir_ = _script(tmp_path, "raise ModuleNotFoundError(\"No module named 'torch'\")\n")
    c = CC._certifica(script, dir_)
    assert c["disponible"] is False and "torch" in c["error_sortida"]


def test_comprova_buit_es_rebutja():
    with pytest.raises(ValueError, match="buit"):
        CC.comprova("   ")


# ── comprovació amb neudet: c04 ─────────────────────────────────────────────

def test_comprova_c04_dona_259_valids():
    """DEFINICIO.md: 259 candidats vàlids a c04. Si no és això, es reporta, no s'ajusta."""
    _neudet_o_skip()
    r = CC.comprova(_c04_text(), "S1")
    assert r["via"] == "candidats"
    assert r["n_valids"] == 259, r["n_valids"]
    assert r["n_invalids"] == 28
    assert len(r["candidats"]) == CC.MOSTRA
    c0 = r["candidats"][0]
    assert len(c0["hash"]) == 12 and len(c0["tubs"]) == 8
    assert c0["xy_svg"].lstrip().startswith("<svg")
    assert "tubs # i # se solapen" in [m["motiu"] for m in r["motius"]]


def test_comprova_yaml_trencat_mostra_l_error_de_neudet():
    _neudet_o_skip()
    with pytest.raises(ValueError) as exc:
        CC.comprova("id: [sense_tancar\n", "S1")
    assert "Error" in str(exc.value)                         # tipus + missatge de l'analitzador


def test_comprova_etapa_que_no_hi_es_mostra_el_missatge_de_neudet():
    _neudet_o_skip()
    with pytest.raises(ValueError, match="no és a campanya.yaml"):
        CC.comprova(_c04_text(), "S9")


# ── llistes tancades: cada valor és on neudet el diu ────────────────────────

def _linies(fitxer: str, dir_=CF._DIS) -> list:
    """Les línies d'un fitxer de neudet (per defecte, el paquet src/neudet/disseny)."""
    return _neudet_o_skip().joinpath(*dir_, fitxer).read_text(encoding="utf-8").splitlines()


def test_metriques_citades_a_objectius_py():
    """Cada mètrica de la llista és a objectius.py, a la línia que diu, i la descripció és la del registre."""
    linies = _linies(CF.OBJECTIUS_PY)
    fallades = [f'{n} no és a objectius.py:{ln}' for n, ln in CF.METRIQUES_LINIA.items()
                if f'"{n}"' not in "\n".join(linies)]
    assert not fallades, "\n".join(fallades)
    DES._neudet()
    from neudet.disseny import objectius as O
    s = CF.schema()["objectius"]
    assert [m["nom"] for m in s["metriques"]] == list(CF.METRIQUES_LINIA)
    reg = {**O.METRIQUES, **O.METRIQUES_GRUP, **O.METRIQUES_GRUP2, **O.METRIQUES_GRUP3}
    for m in s["metriques"]:
        r = reg[m["nom"]]
        desc = r[2] if m["nom"] in O.METRIQUES else r[1]
        assert m["descripcio"] == desc, m["nom"]           # la frase és la de neudet, no una còpia
    err = [m for m in s["metriques"] if m["nom"] == "err_grups"][0]
    assert err["requereix"]["clau"] == "objectius.grups_MeV"


def test_sentits_pesos_energies_k_sigma_citats():
    _neudet_o_skip()
    lo = _linies(CF.OBJECTIUS_PY)
    assert '"max"' in "\n".join(lo)
    assert 'cfg.get("pesos", "uniforme")' in "\n".join(lo)
    assert 'w == "uniforme"' in "\n".join(lo)
    assert 'w == "letargia"' in "\n".join(lo)
    assert 'sel == "totes"' in "\n".join(lo)
    assert "pareto_k_sigma" in "\n".join(lo)
    assert "for n in [p[0] for p in self.pareto]" in "\n".join(lo)
    assert "err_grups: cal objectius.grups_MeV" in "\n".join(lo)
    assert 'cfg.get("restriccio")' in "\n".join(lo)
    s = CF.schema()["objectius"]
    assert [p["valor"] for p in s["pesos"]] == ["uniforme", "letargia"]           # neudet només accepta aquests
    assert s["pesos_defecte"]["valor"] == "uniforme"
    assert s["pareto"]["defecte"] == [["eps_mitja", "max"], ["cv", "min"]]
    assert s["pareto_k_sigma"]["defecte"] == 2.0 and s["pareto_k_sigma"]["minim"] == 0
    assert s["energies"]["totes"]["linia"] == CF.ENERGIES_LINIA


def test_cerca_i_avaluacio_citades():
    _neudet_o_skip()
    lc = _linies(CF.CERCA_PY)
    for nom, ln in CF.CERQUES_LINIA.items():
        assert f'registra("{nom}")' in "\n".join(lc), nom
    for tipus, camps in CF.CERCA_CAMPS.items():
        for c in camps:
            assert any(f'"{c["clau"]}"' in l for l in lc), f'{tipus}.{c["clau"]}'
    la = _linies(CF.AVALUADOR_PY)
    for nom, ln in {**CF.XARXES_LINIA, **CF.MODES_LINIA}.items():
        assert f'"{nom}"' in "\n".join(la), nom
    lcamp = _linies(CF.CAMPANYA_PY)
    for k, c in CF.AVALUACIO_CAMPS.items():
        assert any(k in l for l in lcamp), k
    assert 'mode != "continu"' in "\n".join(lcamp)
    assert "geom_vect" in "\n".join(lcamp)
    s = CF.schema()
    assert [t["valor"] for t in s["cerca"]["tipus"]] == ["exhaustiva", "aleatoria", "halving"]
    assert s["cerca"]["defecte"]["valor"] == "exhaustiva"
    halv = [t for t in s["cerca"]["tipus"] if t["valor"] == "halving"][0]["ajuda"]
    assert "Successive halving" in halv and "min_finalistes" in halv   # paràgraf de cerca.py (línies 9-10)
    assert [x["valor"] for x in s["avaluacio"]["xarxa"]["valors"]] == ["A", "B1"]
    assert [x["valor"] for x in s["avaluacio"]["mode"]["valors"]] == ["lots", "per_energia", "continu"]


def test_ajuda_del_generador_es_el_paragraf_del_docstring():
    """L'ajuda és el text de generadors.py: la línia citada és l'entrada del generador, i el paràgraf hi és."""
    _neudet_o_skip()
    lg = _linies(CF.GENERADORS_PY)
    for g in CF.schema()["generadors"]:
        a = g["ajuda"]
        assert lg[a["linia"] - 1].startswith("    " + g["tipus"]), g["tipus"]
        primer = lg[a["linia"] - 1].split("·", 1)[1].strip().split(" ")[0]
        assert a["text"].startswith(primer), g["tipus"]                 # el text comença per la frase de neudet
    anells = [g for g in CF.schema()["generadors"] if g["tipus"] == "anells"][0]["ajuda"]["text"]
    assert "producte cartesià" in anells and "mig_pas" in anells      # text de neudet


def test_objectius_valids_passen_to_yaml():
    _neudet_o_skip()
    f = CF.defaults()
    f["objectius"] = {"metriques": ["eps_mitja", "cv", "res_E"], "energies_MeV": [0.1, 1.0],
                      "pareto": [["res_E", "min"], ["eps_mitja", "max"]], "pesos": "uniforme", "pareto_k_sigma": 0}
    f["etapes"]["S1"]["cerca"] = {"tipus": "aleatoria", "mostres": 10}
    yaml.safe_load(CF.to_yaml(f))
    f["objectius"]["pareto"] = [["cd_cm2", "min"], ["eps_mitja", "max"]]     # geomètrica: neudet l'afegeix sola
    yaml.safe_load(CF.to_yaml(f))
    f["objectius"] = {"metriques": ["eps_mitja", "cv"], "pareto": [["res_E", "min"], ["eps_mitja", "max"]]}
    yaml.safe_load(CF.to_yaml(f))                                           # de grup: l'afegeix sola (objectius.py:228)


@pytest.mark.parametrize("canvi, camp", [
    (lambda f: f["objectius"].__setitem__("metriques", ["inventada"]), "objectius.metriques"),
    (lambda f: f["objectius"].__setitem__("metriques", []), "objectius.metriques"),
    (lambda f: f["objectius"].__setitem__("pesos", "trapezi"), "objectius.pesos"),
    (lambda f: f["objectius"].__setitem__("pesos", [0.5, 0.5]), "objectius.pesos"),
    (lambda f: f["objectius"].__setitem__("energies_MeV", [0.123]), "objectius.energies_MeV"),
    (lambda f: f["objectius"].__setitem__("pareto", [["eps_mitja", "maxim"], ["cv", "min"]]), "objectius.pareto"),
    (lambda f: f["objectius"].__setitem__("pareto", [["cv", "min"]]), "objectius.pareto"),
    (lambda f: (f["objectius"].__setitem__("metriques", ["eps_mitja", "cv"]),
                f["objectius"].__setitem__("pareto", [["eps_mitja", "max"], ["eps_min", "max"]])), "objectius.pareto"),
    (lambda f: f["objectius"].__setitem__("pareto_k_sigma", -1), "pareto_k_sigma"),
    (lambda f: f["avaluacio"].__setitem__("xarxa", "C"), "avaluacio.xarxa"),
    (lambda f: f["avaluacio"].__setitem__("mode", "lots2"), "avaluacio.mode"),
    (lambda f: f["avaluacio"].__setitem__("n_final", 0), "avaluacio.n_final"),
    (lambda f: f["avaluacio"].__setitem__("geom_vect", "si"), "avaluacio.geom_vect"),
    (lambda f: f["etapes"]["S1"].__setitem__("cerca", {"tipus": "recuit"}), "cerca.tipus"),
    (lambda f: f["etapes"]["S1"].__setitem__("cerca", {"tipus": "aleatoria"}), "mostres"),
    (lambda f: f["etapes"]["S1"].__setitem__("cerca", {"tipus": "halving", "fraccio": 0}), "fraccio"),
    (lambda f: f["etapes"]["S1"].__setitem__("cerca", {"tipus": "halving", "min_finalistes": 0}), "min_finalistes"),
    (lambda f: f["etapes"]["S1"]["generador"]["anells"][0].__setitem__("cd", {"fraction": 2}), "fraction"),
    (lambda f: f["etapes"]["S1"]["generador"]["anells"][0].__setitem__("cd", {"fraction": 0.5, "arc": 400}), "arc"),
])
def test_llista_tancada_fora_de_neudet_diu_el_camp(canvi, camp):
    """to_yaml no escriu un valor fora de les llistes de neudet, i diu quin camp és."""
    _neudet_o_skip()
    f = CF.defaults()
    canvi(f)
    with pytest.raises(CF.FormError) as exc:
        CF.to_yaml(f)
    assert camp in str(exc.value), str(exc.value)


def test_llistes_tancades_de_simphy_son_les_de_neudet():
    """Les llistes que to_yaml fa servir (les constants) són les que neudet té en els seus registres."""
    _neudet_o_skip()
    from neudet.disseny import cerca as C, objectius as O
    assert set(CF.CERQUES_LINIA) == set(C.CERQUES)
    assert set(CF.METRIQUES_LINIA) == set(O.METRIQUES) | set(O.METRIQUES_GRUP) | set(O.METRIQUES_GRUP2) | set(O.METRIQUES_GRUP3)
    assert set(CF.AUTO_NOMS) == O.GEOMETRIQUES | O.GRUP | O.GRUP2 | O.GRUP3
    assert set(CF.DEFECTE_NOMS) == {n for n in O.METRIQUES if n not in O.GEOMETRIQUES}


@pytest.mark.parametrize("tipus", ["anells", "mapa_un_tub", "llista", "slots"])
def test_plantilla_de_generador_passa_to_yaml_i_fitxa(tipus):
    """Les plantilles que el formulari posa en triar un generador: to_yaml les accepta, i neudet (fitxa)
    no en falta cap camp en aquella etapa."""
    _neudet_o_skip()
    from neudet.disseny import fitxa
    f = CF.defaults()
    tub = f["domini"]["tipus_tub"][0]
    f["etapes"]["S1"]["generador"] = json.loads(json.dumps(CF.schema()["plantilles"][tipus]).replace("__TUB__", tub))
    cfg = yaml.safe_load(CF.to_yaml(f))
    falten = [x for x in fitxa.falten(cfg) if x.startswith("etapes.S1.generador")]
    assert falten == [], falten


def test_compta_es_el_que_genera_neudet():
    """`compta` és el recompte de `generadors.genera` (valids + invalids de la campanya)."""
    neudet = _neudet_o_skip()
    from neudet.disseny.campanya import Campanya
    from neudet.disseny.generadors import genera
    import tempfile
    f = CF.defaults()
    txt = CF.to_yaml(f)
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "campanya.yaml").write_text(txt)
        c = Campanya(Path(tmp))
        e = c.etapa("S1")
        ctx = dict(tipus=c.tipus, n_tubs=e.get("n_tubs", c.restr.get("n_tubs")), restriccions=c.restr, arrel=c.dir)
        direct = len(genera(e["generador"], c.bloc, ctx))
    r = CC.compta(txt, "S1")
    assert r == {"etapa": "S1", "n": direct}
    assert r["n"] == 287                                       # 259 vàlids + 28 invàlids (DEFINICIO.md, comprova)
    assert r["n"] == CC.comprova(txt, "S1")["n_valids"] + CC.comprova(txt, "S1")["n_invalids"]


# ── rangs dels anells: l'error diu el camp (Albert, 2026-10-28: «ZeroDivisionError» sense saber on) ──

def _anell0(**kw):
    _neudet_o_skip()
    f = copy.deepcopy(CF.defaults())
    f["etapes"]["S1"]["generador"]["anells"][0].update(kw)
    return f


@pytest.mark.parametrize("kw,camp", [
    ({"n": {"de": 0, "a": 8, "pas": 0}}, "etapes.S1.generador.anells.0.n.pas"),
    ({"r": {"de": 3, "a": 9, "pas": 0}}, "etapes.S1.generador.anells.0.r.pas"),
    ({"n": {"de": 0, "a": 8, "pas": 0.5}}, "etapes.S1.generador.anells.0.n.pas"),
    ({"n": {"de": 8, "a": 0}}, "etapes.S1.generador.anells.0.n.a"),
    ({"n": {"de": 0, "a": 9}}, "etapes.S1.generador.anells.0.n.a"),     # n_total = 8
])
def test_rang_sense_sentit_diu_el_camp(kw, camp):
    with pytest.raises(CF.FormError) as e:
        CF.to_yaml(_anell0(**kw))
    assert f"- {camp}:" in str(e.value)


def test_pas_en_blanc_es_el_de_neudet_i_no_s_escriu():
    y = CF.to_yaml(_anell0(n={"de": 0, "a": 8, "pas": None}))
    assert "pas: null" not in y


def test_energies_del_domini_les_tria_la_campanya():
    """Qualsevol graella (nombre i valors); neudet certifica el domini min–max. Repetides: no."""
    f = _anell0()
    f["domini"]["energies_MeV"] = [0.002, 0.05, 1.5, 4.0]
    f["objectius"]["energies_MeV"] = "totes"
    assert "0.002" in CF.to_yaml(f)
    f["domini"]["energies_MeV"] = [1.0, 1.0]
    with pytest.raises(CF.FormError, match="domini.energies_MeV: hi ha energies repetides"):
        CF.to_yaml(f)


def test_energies_del_domini_contracte_8():
    """Contracte §8 (neudet c1655e0): permeses de min a max (25 meV–5 MeV); fora, el formulari les para (prohibit).
    Entre 25 meV i 1 keV passen: la certificació de neudet diu «no validat»."""
    g = CF.energies_domini()
    if g is None or g.get("validat_PE_min") is None:
        pytest.skip("validacions.json sense el domini del §8")
    f = _anell0()
    f["objectius"]["energies_MeV"] = "totes"
    f["domini"]["energies_MeV"] = [g["min"], 1e-6, 0.5, g["max"]]
    assert CF.to_yaml(f)
    f["domini"]["energies_MeV"] = [g["min"] / 2, 1.0]
    with pytest.raises(CF.FormError, match="fora del domini permès"):
        CF.to_yaml(f)
    f["domini"]["energies_MeV"] = [1.0, g["max"] * 2]
    with pytest.raises(CF.FormError, match="fora del domini permès"):
        CF.to_yaml(f)


# ── Cd com a llista de valors (contracte simphy_ui.md §4: «valor o llista») ──────────────────────────────

@pytest.mark.parametrize("cd, camp", [
    ({"fraction": [0, 0.5, 2], "arc": 360}, "cd.fraction.2"),
    ({"fraction": [0.5], "arc": [180, 400]}, "cd.arc.1"),
    ({"fraction": [], "arc": 360}, "cd.fraction"),
    ({"fraction": {"de": 0, "a": 2, "pas": 0.5}, "arc": 360}, "cd.fraction.a"),
    ({"fraction": 0.5, "arc": {"de": 0, "a": 180, "pas": 90}}, "cd.arc.de"),
    ({"fraction": [0.5], "arc": ["gran"]}, "cd.arc"),
])
def test_cd_llista_fora_del_domini_diu_el_camp(cd, camp):
    """Una llista o un rang de Cd amb un valor que neudet no accepta s'atura amb el camp exacte (el `data-p`)."""
    _neudet_o_skip()
    f = CF.defaults()
    f["etapes"]["S1"]["generador"]["anells"][0]["cd"] = cd
    with pytest.raises(CF.FormError) as exc:
        CF.to_yaml(f)
    assert camp in str(exc.value), str(exc.value)


def test_cd_llista_i_rang_passen_i_neudet_els_multiplica():
    """El que la UI deixa escriure (valors, llistes, rangs) és el que neudet multiplica: fracció × arc × centre.
    Amb fracció 0 l'arc i el centre no es multipliquen."""
    _neudet_o_skip()
    from neudet.disseny import generadors as G
    for cd, n in [({"fraction": [0, 0.5, 1], "arc": [180, 360], "centre": 0}, 1 + 2 + 2),
                  ({"fraction": {"de": 0.25, "a": 0.75, "pas": 0.25}, "arc": 360, "centre": [0, 90]}, 3 * 2),
                  ({"fraction": [0], "arc": 9999}, 1)]:
        assert CF._errors_cd(cd, "x") == [], (cd, CF._errors_cd(cd, "x"))
        assert len(G._opcions_cd(cd)) == n, cd


@pytest.mark.parametrize("camp", ["c01_8tubs_30x30x80", "c02_cd_2grups"])
def test_c01_i_c02_s_obren_sencers_al_formulari(camp):
    """Abans el Cd d'aquestes dues era una llista i el formulari ho refusava. Si neudet les treu o les
    canvia, es salta (⊇: no es fixa res de com són, només que el que hi ha es pot obrir)."""
    root = _neudet_o_skip()
    from simphy.mcgen import campanya_vista as CV
    d = root / "disseny" / "campanyes" / camp / "campanya.yaml"
    if not d.exists():
        pytest.skip(f"neudet no té {camp}")
    f = CF.de_fitxer(d)
    assert CF._errors(f) == []
    CF.to_yaml(f)


def test_la_pagina_deixa_editar_el_cd_com_a_llista():
    """La plantilla ensenya el que el check accepta: cada camp de Cd (fracció, arc, centre) té «+ valor» i,
    si ja és una llista, els seus valors editables (no només de lectura)."""
    html = (Path(__file__).resolve().parents[1] / "src/simphy/ui/static/index.html").read_text(encoding="utf-8")
    cd = html[html.index("function cCdHtml("):html.index("function cNumList(")]
    assert "cNumList(q, v, lab" in cd and 'data-act="nl+"' in cd
    assert "rang o llista: a neudet" not in html


# ── l'avís del Cd és el que diu neudet (validacions.json), no un text vell ───────────────────────────────

def test_l_avis_del_cd_diu_els_tubs_que_neudet_te_validats():
    """L'avís surt de `validacions.json` (secció `cd`): cita cada tub amb Cd validat, i no diu que el Cd només és a
    counterUPC_v0 «fins a TUB-4» ni que Geant4 s'atura amb lnd_252285 (TUB-4 i CERT-Cd ja són fets). ⊇: no es fixa
    quins tubs són."""
    _neudet_o_skip()
    reg = CF._validacions()
    validats = [n for n, e in (reg.get("cd") or {}).items() if e.get("estat") == "validat"]
    assert validats, "neudet no té cap tub amb Cd validat a validacions.json"
    avis = CF.cd_avis()
    for n in validats:
        assert n in avis, (n, avis)
    assert "fins a TUB-4" not in avis and "amb lnd_252285" not in avis
    assert CF.schema()["cd"]["avis"] == avis


def test_l_avis_del_cd_segueix_sent_cert_a_geant4():
    """L'avís diu que Geant4 només admet Cd a counterUPC_v0 i als tubs genèrics: és el text de neudet
    (`DetectorConstruction.cc`). Si neudet canvia la regla, aquest test s'atura i cal tornar a llegir-la."""
    root = _neudet_o_skip()
    f = root / "mc/geant4/detector/src/DetectorConstruction.cc"
    if not f.exists():
        pytest.skip("neudet no té DetectorConstruction.cc")
    assert "el Cd només és a counterUPC_v0 i als genèrics del catàleg" in f.read_text(encoding="utf-8")
