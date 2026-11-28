"""§26 (MB10A): reflectors i barres del bloc — la UI i neudet es llegeixen vius.

Com és un test bessó: el que diu la UI de `reflectors` i `barres` es confronta amb el codi real de neudet
(`neudet/disseny/caixa_10a.py`: claus, materials, cares, davants) i amb la línia de `fitxa.py` que valida
`domini.bloc.reflectors` i `domini.bloc.barres`. Si neudet es mou, el test se n'assabenta; la divergència queda
escriptura, no corregida.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from simui import campanya_form as CF
from simphy.mcgen import design as DES

INDEX = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")


def _neudet():
    try:
        DES.neudet_root()
        DES._neudet()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def _r(**extra):
    r = {"material": "PE", "densitat_gcm3": 0.94, "gruix_cm": 0.5, "llarg_cm": 30,
         "descobert_davant_cm": 0, "davant": "-z", "cares": ["+x", "-x"], "font": "paper"}
    r.update(extra)
    return r


def _b(**extra):
    b = {"material": "Steel", "densitat_gcm3": 7.85, "radi_cm": 1.5, "alzada_cm": 40,
         "posicions_cm": [[0, 0], [10, 10]], "font": "Fig. 6"}
    b.update(extra)
    return b


# ── neudet valida reflectors i barres ────────────────────────────────────────

def test_neudet_valida_reflectors_i_barres_a_les_linies_que_diu_i_els_claus_i_materials_venen_del_seu_codi():
    _neudet()
    import importlib
    c = importlib.import_module("neudet.disseny.caixa_10a")
    info = CF.caixa_10a_info()
    for key in ("reflectors", "barres"):
        e = info[key]
        assert e["validat"] is True, e
        fitxer, linia = e["on"].split(":")
        assert fitxer == CF.FITXA_PY
        text = (DES.neudet_root() / "src" / "neudet" / "disseny" / fitxer).read_text(encoding="utf-8").splitlines()
        assert ("domini.bloc.reflectors" if key == "reflectors" else "domini.bloc.barres") in text[int(linia) - 1], (e["on"], text[int(linia) - 1])
    sidecar = info["reflectors"]["sidecar"]
    assert set(sidecar["claus_reflectors"]) == set(c.CLAUS_REFLECTORS)
    assert set(sidecar["claus_barres"]) == set(c.CLAUS_BARRES)
    assert sidecar["cares"] == list(c.CARES)
    assert sidecar["davants"] == list(c.DAVANTS)
    assert sidecar["materials_reflectors"] == list(c.MATERIAL_REFLECTORS)
    assert sidecar["materials_barres"] == list(c.materials_barres())
    assert sidecar["material_barres_defecte"] == c.MATERIAL_BARRES_DEFECTE


def test_materials_de_la_ui_surten_de_neudet_i_no_són_escrits_a_index_html():
    _neudet()
    import importlib
    c = importlib.import_module("neudet.disseny.caixa_10a")
    S = CF.caixa_10a_info_ui()
    assert S["materials_barres"] == list(c.materials_barres())
    assert S["materials_reflectors"] == list(c.MATERIAL_REFLECTORS)
    # la UI només dibuixa les llistes del schema: cap defecte ni material escrit al codi de la pàgina
    assert 'S.materials_reflectors' in INDEX and 'S.materials_barres' in INDEX
    assert 'S.cares' in INDEX and 'S.davants' in INDEX
    # les barres porten el defecte de neudet quan neixen (Steel), mai inventat aquí
    assert 'material_barres_defecte' in INDEX
    assert 'Steel' not in INDEX and 'SST_PC' not in INDEX
    assert 'data-act="refl+"' in INDEX and 'data-act="refl-"' in INDEX
    assert 'data-act="barr+"' in INDEX and 'data-act="barr-"' in INDEX
    assert 'data-act="barres+"' in INDEX and 'data-act="barres-"' in INDEX


def test_el_schema_porta_les_claus_de_neudet():
    _neudet()
    s = CF.schema()
    assert "caixa_10a" in s
    S = s["caixa_10a"]
    for k in ("claus_reflectors", "claus_barres", "cares", "davants",
              "materials_reflectors", "materials_barres", "material_barres_defecte"):
        assert k in S and S[k] is not None, k
    assert S["fitxer"] == "disseny/caixa_10a.py"
    assert S["neudet"]["reflectors"]["validat"] is True


# ── la UI i neudet reboten el mateix ──────────────────────────────────────────

def test_la_ui_rebota_el_que_rebota_neudet_pels_mateixos_motius():
    _neudet()
    import importlib
    c = importlib.import_module("neudet.disseny.caixa_10a")
    probes_r = [
        _r(),                                    # vàlid
        _r(material="Aluminio"),                 # material no conegut
        _r(cares=["+x", "+x"]),                 # care repetit
        _r(davant="+x"),                         # davant no conegut
        _r(font=""),                             # font buida
        _r(llarg_cm=0),                          # mida no positiva
        _r(descobert_davant_cm=-1),             # descobert negatiu
    ]
    for r in probes_r:
        assert bool(CF._errors_caixa_10a({"reflectors": r})) == bool(c.violacions_reflectors(r)), r
    probes_b = [
        _b(),                                    # vàlid
        _b(material="Fe"),                       # barra fora del registre
        _b(posicions_cm=[[0, 0], [0.5, 0.5]]),   # barres solapades
        _b(posicions_cm=[]),                     # llista buida
        _b(font=""),                             # font buida
        _b(radi_cm=0),                           # radi no positiu
        _b(alzada_cm=-1),                        # alzada no positiva
        _b(posicions_cm=[[0, 0], [1]]),          # fila de posició mal formada
    ]
    for b in probes_b:
        assert bool(CF._errors_caixa_10a({"barres": b})) == bool(c.violacions_barres(b)), b


def test_absent_no_inventa_cap_fila():
    _neudet()
    assert CF._errors_caixa_10a({"material": "PE"}) == []
    assert CF._errors_caixa_10a({"reflectors": None, "barres": None}) == []
    import importlib
    c = importlib.import_module("neudet.disseny.caixa_10a")
    info = CF.caixa_10a_info()
    assert info["reflectors"]["sidecar"]["materials_reflectors"] == list(c.MATERIAL_REFLECTORS)
    assert info["barres"]["sidecar"]["materials_barres"] == list(c.materials_barres())


# ── el formulari no escriu res implícit ────────────────────────────────────────

def test_c_edita_no_pot_escriure_claus_desconegudes():
    _neudet()
    import importlib
    c = importlib.import_module("neudet.disseny.caixa_10a")
    reflectors_claus = CF._EDITABLE["domini"]["bloc"]["reflectors"]
    barres_claus = CF._EDITABLE["domini"]["bloc"]["barres"]
    assert set(reflectors_claus) == set(c.CLAUS_REFLECTORS)
    assert set(barres_claus) == set(c.CLAUS_BARRES)
    assert barres_claus["posicions_cm"] == [[None, None]]


def test_yaml_escrit_per_la_ui_queda_idèntic_si_no_ha_canviat():
    _neudet()
    f = CF.defaults()
    f["domini"]["bloc"]["reflectors"] = _r()
    f["domini"]["bloc"]["barres"] = _b()
    y = CF.to_yaml(f)
    assert "reflectors:" in y and "barres:" in y and "material: PE" in y and "material: Steel" in y
    f2 = CF.defaults()                                      # sense reflectors ni barres: no s'escriu res
    y2 = CF.to_yaml(f2)
    assert "reflectors:" not in y2 and "barres:" not in y2


def test_el_yaml_no_porta_colors_implícits_i_errors_surten():
    _neudet()
    f = CF.defaults()
    f["domini"]["bloc"] = {"material": "PE", "mides_cm": [30, 30, 80],
                            "reflectors": _r(font=""), "barres": _b(font="")}
    with pytest.raises(CF.FormError) as exc:
        CF.to_yaml(f)
    msg = str(exc.value)
    assert "font" in msg
