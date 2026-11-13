"""§22 (forma del bloc) i §24 (la taula de cossos `domini.cossos`): llistes tancades, res per defecte, i el que fa neudet avui.

Com és un test bessó: el que diu la UI de `forma` i `cossos` es confronta amb el codi real de neudet (la línia de `fitxa.py`
que valida `domini.bloc.forma`, el vocabulari del sidecar de Geant4 de `disseny/cossos.py`) i amb la dada real de simphy
(`data/mcgen/escenarios/*.json`, que és §24). Si neudet o simphy es mouen, el test se n'assabenta; la divergència queda escrita.
"""
from __future__ import annotations

import json
import shutil
import subprocess
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


# ── §22: la forma del bloc ───────────────────────────────────────────────────

def test_forma_del_bloc_es_llista_tancada_i_absent_és_cub():
    assert CF.FORMA_BLOC == ("cub", "cilindre") and CF.FORMA_BLOC_DEFECTE == "cub"
    e = CF._errors_bloc({"mides_cm": [30, 30, 80], "forma": "esfera"})
    assert len(e) == 1 and "cub o cilindre" in e[0] and "absent = cub" in e[0]
    assert CF._errors_bloc({"mides_cm": [30, 30, 80]}) == []          # absent = cub: les campanyes velles no es trenquen


def test_amb_cilindre_radi_i_alzada_són_obligatoris_i_mides_cm_no_hi_va():
    e = CF._errors_bloc({"forma": "cilindre"})
    assert any("radi_cm" in x and "obligatori" in x and "sense valor per defecte" in x for x in e)
    assert any("alzada_cm" in x for x in e)
    e = CF._errors_bloc({"forma": "cilindre", "radi_cm": 25, "alzada_cm": 80, "mides_cm": [30, 30, 80]})
    assert e and "mides_cm" in e[0] and "només amb forma: cub" in e[0]


def test_amb_cub_radi_i_alzada_no_hi_va():
    for extra in ("radi_cm", "alzada_cm"):
        e = CF._errors_bloc({"mides_cm": [30, 30, 80], extra: 25})
        assert e and extra in e[0] and "només amb forma: cilindre" in e[0]
    assert CF._errors_bloc({"forma": "cub", "mides_cm": [30, 30, 80]}) == []


def test_el_yaml_que_escriu_la_ui_no_porta_res_implícit():
    f = CF.defaults()
    f["domini"]["bloc"] = {"material": "PE", "forma": "cilindre", "radi_cm": 25, "alzada_cm": 80, "forat_cm": 0}
    y = CF.to_yaml(f)
    assert "forma: cilindre" in y and "radi_cm: 25" in y and "mides_cm" not in y.split("cossos")[0]
    f2 = CF.defaults()                                            # cub: `forma` no s'escriu (§22: absent = cub, els hashos no canvien)
    assert "forma:" not in CF.to_yaml(f2).split("avaluacio:")[0].split("domini:")[1].split("font:")[0]


# ── §24: la taula de cossos ──────────────────────────────────────────────────

def test_formes_de_cos_són_cinc_i_cada_una_amb_les_seves_mides():
    assert CF.FORMES_COS == ("box", "cilindre", "esfera", "con", "semiespai")
    ok = {"box": {"dx_cm": 5, "dy_cm": 30, "dz_cm": 30},
          "cilindre": {"radi_cm": 1.27, "alzada_cm": 68, "eix": "z"},
          "esfera": {"radi_cm": 3},
          "con": {"radi_base_cm": 4, "alzada_cm": 10, "eix": "x"},
          "semiespai": {"punt_cm": [0, 0, -40], "normal": [0, 0, 1]}}
    for forma, mides in ok.items():
        c = dict(nom="a", material="Pb", forma=forma, pos_cm=[0, 0, 0], **mides)
        assert CF._errors_cossos([c]) == [], (forma, CF._errors_cossos([c]))
        e = CF._errors_cossos([dict(nom="b", material="Pb", forma=forma, pos_cm=[0, 0, 0])])
        assert e and all(k.split("_cm")[0] in " ".join(e) for k in mides if k.endswith("_cm")), (forma, e)
    e = CF._errors_cossos([{"nom": "x", "material": "Pb", "forma": "prisma", "pos_cm": [0, 0, 0]}])
    assert e and "box o cilindre o esfera o con o semiespai" in e[0]


def test_un_camp_que_no_toca_amb_aquella_forma_queda_fora():
    e = CF._errors_cossos([{"nom": "a", "material": "PE", "forma": "cilindre", "pos_cm": [0, 0, 0],
                            "radi_cm": 5, "alzada_cm": 10, "eix": "z", "dx_cm": 3}])
    assert e and "dx_cm" in e[0] and "no toca amb forma: cilindre" in e[0]
    e = CF._errors_cossos([{"nom": "a", "material": "PE", "forma": "box", "pos_cm": [0, 0, 0],
                            "dx_cm": 3, "dy_cm": 3, "dz_cm": 3, "radi_cm": 5}])
    assert e and "radi_cm" in e[0]
    assert CF._errors_cossos([{"nom": "a", "material": "PE", "forma": "box", "pos_cm": [0, 0, 0],
                               "dx_cm": 3, "dy_cm": 3, "dz_cm": 3, "color": "vermell"}])[0].startswith("domini.cossos[0].color:")


def test_sense_cossos_no_gha_res_i_camp_per_defecte_no_nhi_ha():
    assert CF._errors_cossos(None) == []                                  # §24 regla 1: absent = cap cos
    assert CF._errors_cossos([]) == []
    i = CF.cosos_info()
    assert i["defecte_files"] == 0 and i["transport_defecte"] is False    # la UI no afegeix files ni valors
    assert i["mides"] == {k: list(v) for k, v in CF.MIDES_COS.items()}
    sencer = {"nom": "a", "material": "Pb", "forma": "box", "pos_cm": [0, 0, 0], "dx_cm": 1, "dy_cm": 1, "dz_cm": 1}
    assert CF._errors_cossos([sencer]) == []                              # amb tot escrit, no es queixa de res
    for k in CF.COS_OBLIGATORIS:
        c = dict(sencer)
        del c[k]
        e = CF._errors_cossos([c])
        assert any(k in x and "sense valor per defecte" in x for x in e), (k, e)


def test_el_transport_és_fals_per_defecte_i_els_noms_únics():
    c = {"nom": "a", "material": "Pb", "forma": "box", "pos_cm": [0, 0, 0], "dx_cm": 1, "dy_cm": 1, "dz_cm": 1}
    assert CF._errors_cossos([c]) == []                                   # `transport` escrit o no: §24 el dona per fals
    e = CF._errors_cossos([c, dict(c)])
    assert e and "es repeteix" in e[0]
    e = CF._errors_cossos([dict(c, transport="sí")])
    assert e and "cert o fals" in e[0] and "per defecte fals" in e[0]


# ── el que fa neudet AVUI (es llegeix el seu codi; no es copia res) ───────────

def test_neudet_valida_la_forma_del_bloc_a_la_línia_que_diu():
    _neudet()
    e = CF.estat_geometria_neudet()
    assert e["bloc"]["validat"] is True
    fitxer, linia = e["bloc"]["on"].split(":")
    assert fitxer == CF.FITXA_PY.split("/")[-1]
    nom = Path(CF.__file__).parent                                      # la ruta real és la de neudet, no la d'aquí
    text = (DES.neudet_root() / "src" / "neudet" / "disseny" / fitxer).read_text(encoding="utf-8").split("\n")
    assert "domini.bloc.forma" in text[int(linia) - 1], (e["bloc"]["on"], text[int(linia) - 1])
    assert "domini.bloc.forma" in e["bloc"]["text"]


def test_neudet_no_llegeix_domini_cossos_i_la_divergència_queda_escrita():
    _neudet()
    e = CF.estat_geometria_neudet()["cossos"]
    assert e["validat"] is False
    assert "neudet encara no valida" in e["text"] and "domini.cossos" in e["text"]
    costat = e["sidecar"]
    assert costat and costat["formes"] and set(costat["formes"]).isdisjoint({"box", "esfera", "con", "semiespai"})
    # §24 diu `box|cilindre|esfera|con|semiespai`; el sidecar de Geant4 de neudet diu les seves. La divergència és del coordinador.
    assert set(costat["formes"]) != set(CF.FORMES_COS)
    assert "La divergència amb §24 la tanca el coordinador." in e["text"]
    assert CF.AVIS_NEUDET_CAMPS in e["text"]


def test_la_ui_diu_a_cada_camp_què_valida_neudet():
    _neudet()
    s = CF.schema()
    assert s["bloc"]["neudet"]["validat"] is True and "fitxa.py" in s["bloc"]["neudet"]["text"]
    assert s["cossos"]["neudet"]["validat"] is False and CF.AVIS_NEUDET_CAMPS in s["cossos"]["avis_neudet"]
    assert "mesura" in s["bloc"] and "2026-11-12_CIL_F_A012" in s["bloc"]["mesura"]   # la mesura és de neudet: no se'n copia cap número


# ── la dada real de simphy (vocabulari §24) ──────────────────────────────────

def test_lesceneri_real_de_simphy_passa_les_regles_de_24():
    es = CF.escenaris_simphy()
    if not es["disponible"]:
        pytest.skip(f"simphy no porta escenaris: {es['motiu']}")
    assert es["escenaris"], es
    for e in es["escenaris"]:
        assert "error" not in e, e
        assert e["errors"] == [], (e["nom"], e["errors"])
        c = CF.escenari_cossos(e["nom"])
        assert c["cossos"], e
        assert c["camps_fora_de_24"] == [], c["camps_fora_de_24"]
        claus = set(CF.COS_OBLIGATORIS) | set(CF.COS_OPCIONALS) | set(CF.MIDES_COS_TOTES) | {CF.COS_DENSITAT}
        for cos in c["cossos"]:
            assert set(cos) <= claus, sorted(set(cos) - claus)
            assert cos["forma"] in CF.FORMES_COS


def test_sense_lesceneri_no_s_inventa_res():
    with pytest.raises(Exception) as ex:
        CF.escenari_cossos("no_hi_es_camps")
    assert "no inventa escenaris" in str(ex.value)


# ── §19 + §22: la font i la forma del bloc (el camí combinat) ─────────────────

def test_lavís_de_la_font_funciona_amb_cub_i_amb_cilindre():
    cil = lambda p: {"bloc": {"forma": "cilindre", "radi_cm": 25, "alzada_cm": 80}, "font": {"tipus": "iso", "pos_cm": p}}
    cub = lambda p: {"bloc": {"mides_cm": [30, 30, 80]}, "font": {"tipus": "iso", "pos_cm": p}}
    assert CF.font_avis(cil([10, 0, 0])) == "dins"
    assert CF.font_avis(cil([25, 0, 0])) == "cara" and CF.font_avis(cil([0, 0, -40])) == "cara"
    assert CF.font_avis(cil([0, 0, -65])) is None and CF.font_avis(cil([26, 0, 0])) is None
    assert CF.font_avis(cub([10, 0, 0])) == "dins" and CF.font_avis(cub([0, 0, -65])) is None
    # §22: sense `radi_cm`/`alzada_cm` no hi ha bloc per comparar i no se n'inventa cap
    assert CF.font_avis({"bloc": {"forma": "cilindre"}, "font": {"tipus": "iso", "pos_cm": [0, 0, -65]}}) is None


def test_la_font_per_defecte_amb_cilindre_usa_alzada_i_no_inventa_res():
    assert CF.font_defecte_bloc({"forma": "cilindre", "alzada_cm": 80}) == {"tipus": "iso", "pos_cm": [0, 0, -45]}
    with pytest.raises(DES.DesignError) as ex:
        CF.font_defecte_bloc({"forma": "cilindre"})
    assert "alzada_cm" in str(ex.value)


# ── el JS de la UI (mateix resultat que el Python) ───────────────────────────

@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar les funcions pures de la UI")
def test_el_js_del_bloc_i_els_cossos_dona_el_mateix_que_el_python():
    src = INDEX.split("// COSSOS-DEF-BEGIN")[1].split("\n", 1)[1].split("// COSSOS-DEF-END")[0]
    dominis = [{"bloc": {"mides_cm": [30, 30, 80]}},
               {"bloc": {"forma": "cilindre", "radi_cm": 25, "alzada_cm": 80}},
               {"bloc": {"forma": "cilindre"}},
               {"bloc": {"forma": "cilindre", "radi_cm": 25, "alzada_cm": 80},
                "cossos": [{"nom": "plom", "material": "Pb", "forma": "box", "pos_cm": [30, 0, 0],
                            "dx_cm": 5, "dy_cm": 30, "dz_cm": 30},
                           {"nom": "tub_a", "material": "He3", "forma": "cilindre", "pos_cm": [-8, 0, 0],
                            "radi_cm": 1.27, "alzada_cm": 68, "eix": "z"},
                           {"nom": "", "material": "", "forma": "", "pos_cm": []}]}]
    js = (src + "\nconst D = " + json.dumps(dominis) + ";\n"
          "const out = D.map(d => [cBlocExt(d).forma, cBlocExt(d).m, cBlocExt(d).sense, "
          "cCossosEscena(d).map(c => [c.nom, c.forma, c.transport, cCosMal(c)])]);\n"
          "console.log(JSON.stringify(out));")
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    for d, (forma, m, sense, cossos) in zip(dominis, json.loads(r.stdout)):
        b = d["bloc"]
        if b.get("forma") == "cilindre":
            assert forma == "cilindre" and m == [2 * b.get("radi_cm", 0) or 30, 2 * b.get("radi_cm", 0) or 30, b.get("alzada_cm", 0) or 80]
            assert sense == (not (b.get("radi_cm", 0) > 0 and b.get("alzada_cm", 0) > 0))
        else:
            assert forma == "cub" and m == b.get("mides_cm")
        esperats = [(c.get("nom") or f"cos {k + 1}", c.get("forma") or "", c.get("transport") is True)
                    for k, c in enumerate(d.get("cossos", []))]              # sense `nom`, el dibuix en posa un de *visual* (no al yaml)
        assert [(n, f, t) for n, f, t, _ in cossos] == esperats
        if cossos:
            assert not cossos[0][3] and not cossos[1][3]                      # les que quadren, no les marca
            assert cossos[-1][3]                                             # la fila sense forma ni mides: el visor la marca


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar les funcions pures de la UI")
def test_la_fila_nova_de_la_taula_no_porta_cap_valor():
    assert 'data-act="cos+"' in INDEX and "push({})" in INDEX
    assert "// §24: la fila nova és buida, cap valor per defecte" in INDEX
    assert 'data-act="cos-"' in INDEX
    # la taula buida torna a ser `domini.cossos` absent (§24 regla 1), no una llista buida
    assert "delete CP.f.domini.cossos" in INDEX
