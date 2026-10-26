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
            if f'"{c["clau"]}"' not in linies[c["linia"] - 1]:
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
