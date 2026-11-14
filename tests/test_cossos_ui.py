"""§22 (forma del bloc) i §25 (la taula de cossos `domini.cossos`; corregeix el §24): llistes tancades, res per defecte, i el que fa neudet avui.

Com és un test bessó: el que diu la UI de `forma` i `cossos` es confronta amb el codi real de neudet (la línia de `fitxa.py`
que valida `domini.bloc.forma` i `domini.cossos`, i `violacions_cossos` de `disseny/cossos.py`) i amb la dada real de simphy
(`data/mcgen/escenarios/*.json`). Si neudet o simphy es mouen, el test se n'assabenta; la divergència (escenaris de §24 que
§25 rebota) queda escrita, no corregida.
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

# un cos de Pb amb el ρ del registre: com que el registre és de neudet, la UI no l'ha de rebotar mai
def _pb(**extra):
    c = {"nom": "a", "material": "Pb", "forma": "caixa", "mides_cm": [10, 2, 2],
         "pos_cm": [0, 0, 0], "densitat_gcm3": 11.35}
    c.update(extra)
    return c


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


# ── §25: la taula de cossos ──────────────────────────────────────────────────

def test_formes_de_cos_són_tres_i_cada_una_amb_les_seves_mides():
    assert CF.FORMES_COS == ("caixa", "cilindre", "tub")
    ok = {"caixa": {"mides_cm": [10, 2, 2]},                                        # costats TOTALS (§25), no semides
          "cilindre": {"radi_cm": 1.27, "alzada_cm": 68},
          "tub": {"radi_int_cm": 3, "radi_ext_cm": 6, "alzada_cm": 60}}            # cilindre buidat
    for forma, mides in ok.items():
        c = dict(nom="a", material="Pb", forma=forma, pos_cm=[0, 0, 0], densitat_gcm3=11.35, **mides)
        assert CF._errors_cossos([c]) == [], (forma, CF._errors_cossos([c]))
        e = CF._errors_cossos([dict(nom="b", material="Pb", forma=forma, pos_cm=[0, 0, 0], densitat_gcm3=11.35)])
        assert e and all(k.split("_cm")[0] in " ".join(e) for k in mides), (forma, e)
    e = CF._errors_cossos([{"nom": "x", "material": "Pb", "forma": "prisma", "pos_cm": [0, 0, 0], "densitat_gcm3": 11.35}])
    assert e and "cal caixa | cilindre | tub" in e[0]


def test_formes_i_camps_reservats_reboten_en_paraules():
    assert CF.FORMES_RESERVADES == ("esfera", "con", "semiespai") and CF.CAMPS_RESERVATS == ("eix", "regio", "transport")
    for forma in CF.FORMES_RESERVADES:                                            # §25: mai ignorades en silenci
        e = CF._errors_cossos([{"nom": "a", "material": "Pb", "forma": forma, "pos_cm": [0, 0, 0],
                                "radi_cm": 5, "densitat_gcm3": 11.35}])
        assert any("forma reservada" in x and "encara no acceptada per neudet" in x for x in e), (forma, e)
        assert sum(".forma:" in x for x in e) == 1                                # un sol motiu: el del §25, no dos
    for camp in CF.CAMPS_RESERVATS:
        e = CF._errors_cossos([_pb(**{camp: "z"})])
        assert any(f".{camp}: camp reservat" in x and "no s'ignora en silenci" in x for x in e), (camp, e)


def test_les_semides_del_24_no_hi_són_i_es_reboten():
    assert CF.SEMIDES_FORA == ("dx_cm", "dy_cm", "dz_cm") and "mides_cm" in CF.MIDES_COS["caixa"]
    e = CF._errors_cossos([{"nom": "mur", "material": "Pb", "forma": "caixa", "pos_cm": [0, 25, 0],
                            "dx_cm": 40, "dy_cm": 10, "dz_cm": 40, "densitat_gcm3": 11.35}])
    assert e and "`dx_cm`" in e[0] and "no és un camp de la forma: caixa" in e[0]
    e = CF._errors_cossos([{"nom": "mur", "material": "Pb", "forma": "box", "pos_cm": [0, 25, 0],
                            "dx_cm": 40, "dy_cm": 10, "dz_cm": 40, "densitat_gcm3": 11.35}])
    assert any("box" in x and "no és vàlida" in x for x in e)                     # `box` ja no és vocabulari (§25)


def test_sense_cossos_no_gha_res_i_camp_per_defecte_no_nhi_ha():
    assert CF._errors_cossos(None) == []                                          # §25 regla 1: absent = cap cos
    assert CF._errors_cossos([]) == []
    i = CF.cosos_info()
    assert i["defecte_files"] == 0 and "transport_defecte" not in i               # la UI no afegeix files ni valors
    assert i["opcionals"] == []                                                   # §25: cap camp opcional acceptat
    assert i["mides"] == {k: list(v) for k, v in CF.MIDES_COS.items()}
    assert "centre" in i["pos_cm"]
    assert CF._errors_cossos([_pb()]) == []                                       # amb tot escrit, no es queixa de res
    for k in CF.COS_OBLIGATORIS:
        c = dict(_pb())
        del c[k]
        e = CF._errors_cossos([c])
        assert any(k in x and "obligatori, cap valor implícit" in x for x in e), (k, e)


def test_laritmètica_rebota_però_el_registre_de_materials_és_de_neudet():
    e = CF._errors_cossos([{"nom": "t", "material": "Pb", "forma": "tub", "pos_cm": [0, 0, 0],
                            "radi_int_cm": 6, "radi_ext_cm": 3, "alzada_cm": 60, "densitat_gcm3": 11.35}])
    assert e and "radi_int_cm 6 ≥ radi_ext_cm 3" in e[0]                          # cilindre buidat, no farcit
    e = CF._errors_cossos([_pb(mides_cm=[10, 0, 2])])
    assert e and "les mides han de ser números > 0" in e[0]
    assert CF._errors_cossos([_pb(densitat_gcm3=11.34)]) == []                    # el ρ ÚNIC del Pb és del registre de neudet:
    tot = json.dumps(CF.cosos_info())                                             # «Comprova» el torna tal com és; aquí no se'n copia cap número
    assert "11.3" not in tot and "11,3" not in tot
    estat = CF.estat_geometria_neudet()                                           # (test amb neudet present a l'entorn de proves)
    costat = (estat.get("cossos") or {}).get("sidecar")
    if costat:                                                                  # la llista de materials ve del codi de neudet, live
        assert CF.cosos_info(estat["cossos"])["materials"] == costat["materials"]


def test_els_noms_de_cos_són_únics_perquè_són_el_volum_geant4():
    e = CF._errors_cossos([_pb(), _pb(pos_cm=[5, 0, 0])])
    assert e and "nom de cos repetit: a (el nom és el volum Geant4 `cos_<nom>`)" in e[0]


# ── el que fa neudet AVUI (es llegeix el seu codi; no es copia res) ───────────

def test_neudet_valida_la_forma_del_bloc_a_la_línia_que_diu():
    _neudet()
    e = CF.estat_geometria_neudet()
    assert e["bloc"]["validat"] is True
    fitxer, linia = e["bloc"]["on"].split(":")
    assert fitxer == CF.FITXA_PY.split("/")[-1]
    text = (DES.neudet_root() / "src" / "neudet" / "disseny" / fitxer).read_text(encoding="utf-8").split("\n")
    assert "domini.bloc.forma" in text[int(linia) - 1], (e["bloc"]["on"], text[int(linia) - 1])
    assert "domini.bloc.forma" in e["bloc"]["text"]


def test_neudet_valida_domini_cossos_a_la_línia_que_diu_i_la_convergència_queda_fixada():
    _neudet()
    e = CF.estat_geometria_neudet()["cossos"]
    assert e["validat"] is True                                                   # COSSOS-YAML (neudet, 2026-11-13)
    fitxer, linia = e["on"].split(":")
    text = (DES.neudet_root() / "src" / "neudet" / "disseny" / fitxer).read_text(encoding="utf-8").split("\n")
    assert "domini.cossos" in text[int(linia) - 1], (e["on"], text[int(linia) - 1])
    assert "domini.cossos" in e["text"] and CF.AVIS_NEUDET_CAMPS not in e["text"]
    costat = e["sidecar"]
    assert set(costat["formes"]) == set(CF.FORMES_COS)                            # §25 va corregir el contracte cap al codi de neudet
    assert {k: v for k, v in costat["mides"].items()} == {k: list(v) for k, v in CF.MIDES_COS.items()}
    assert costat["materials"]                                                    # el registre és de neudet: la UI el llegeix, no l'inventa


def test_la_ui_diu_a_cada_camp_què_valida_neudet():
    _neudet()
    s = CF.schema()
    assert s["bloc"]["neudet"]["validat"] is True and "fitxa.py" in s["bloc"]["neudet"]["text"]
    assert s["cossos"]["neudet"]["validat"] is True and "domini.cossos" in s["cossos"]["avis_neudet"]
    assert "mesura" in s["bloc"] and "2026-11-12_CIL_F_A012" in s["bloc"]["mesura"]   # la mesura és de neudet: no se'n copia cap número


# ── test bessó: la UI i `violacions_cossos` de neudet coincideixen (estructural) ─

def test_la_ui_rebota_el_que_rebota_neudet_pel_mateix_motiu():
    """§25: la UI replica els passos estructurals de `violacions_cossos` (reservats, obligatoris, mides de la forma,
    aritmètica); el veredicte del registre (material, ρ del Pb) el dona «Comprova» amb la frase de neudet. Amb cossos de Pb
    al ρ del registre, doncs, el que és buit per a neudet és buit per a la UI i el que rebot, rebot pels dos costats."""
    _neudet()
    import importlib
    NC = importlib.import_module("neudet.disseny.cossos")
    cil = lambda **x: {**dict(nom="c", material="Pb", forma="cilindre", pos_cm=[0, 0, 0],
                              densitat_gcm3=11.35, radi_cm=1.27, alzada_cm=68), **x}
    tub = lambda **x: {**dict(nom="t", material="Pb", forma="tub", pos_cm=[0, 0, 0],
                              densitat_gcm3=11.35, radi_int_cm=3, radi_ext_cm=6, alzada_cm=60), **x}
    probes = [
        [_pb()],                                                                   # caixa vàlida
        [cil()],                                                                   # cilindre vàlid
        [tub()],                                                                   # tub vàlid (cilindre buidat)
        [_pb(forma="esfera")],                                                     # forma reservada
        [_pb(regio="a - b")],                                                      # camp reservat: el camí combinat
        [dict(_pb(), **{"dx_cm": 4, "dy_cm": 4, "dz_cm": 4})],                     # semides del §24
        [_pb(forma="prisma")],                                                     # fora de vocabulari
        [cil(alzada_cm=None)],                                                     # falta una mida de la forma
        [tub(radi_int_cm=6, radi_ext_cm=3)],                                       # tub al revés
        [_pb(), _pb(pos_cm=[9, 0, 0])],                                            # nom repetit
        [{"nom": "", "material": "", "forma": "", "pos_cm": []}],                  # fila buida del formulari
    ]
    for cossos in probes:
        ui, neu = CF._errors_cossos(cossos), NC.violacions_cossos(cossos)
        assert bool(ui) == bool(neu), (cossos, ui, neu)
    reservats = CF._errors_cossos([_pb(regio="a - b")])
    assert any("reservat" in x for x in reservats) and any("reservat" in x for x in NC.violacions_cossos([_pb(regio="a - b")]))
    assert any("nom de cos repetit" in x for x in CF._errors_cossos([_pb(), _pb()]))
    assert any("nom de cos repetit" in x for x in NC.violacions_cossos([_pb(), _pb()]))


# ── la dada real de simphy: els escenaris de §24 reboten amb §25 (divergència escrita) ──

def test_lesceneri_de_simphy_amb_regio_rebota_i_no_es_corregeix():
    """El camí combinat es converteix en el test: `cilindre_plom_dos_tubs` ja és de §25 (vocabulari 1.22) però el seu bloc
    porta `regio`, que §25 declara RESERVAT: la UI el rebota en paraules i la dada de simphy no s'escriu des d'aquí."""
    c = CF.escenari_cossos("cilindre_plom_dos_tubs")
    assert c["vocabulari"] == "1.22", c["vocabulari"]
    assert c["camps_fora"] == ["regio"], c["camps_fora"]
    assert c["errors"] and all("reservat" in e for e in c["errors"]), c["errors"]


def test_lesceneris_vells_de_24_reboten_i_la_divergència_queda_escrita():
    es = CF.escenaris_simphy()
    if not es["disponible"]:
        pytest.skip(f"simphy no porta escenaris: {es['motiu']}")
    assert es["escenaris"], es
    for e in es["escenaris"]:
        assert "error" not in e, e
        c = CF.escenari_cossos(e["nom"])
        assert c["cossos"], e
        if e.get("vocabulari") == "1.21":                                         # §24 (v1.21): box/semides/eix/esfera…
            assert c["errors"] and c["camps_fora"], (e["nom"], c["errors"], c["camps_fora"])
            assert any("reservat" in x for x in c["errors"]), (e["nom"], c["errors"])
        assert e["errors"] == c["errors"], e["nom"]                              # el que ve la llista i el que carrega la taula: el mateix rebot


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
                "cossos": [{"nom": "plom", "material": "Pb", "forma": "caixa", "pos_cm": [30, 0, 0],
                            "mides_cm": [10, 60, 60], "densitat_gcm3": 11.35},
                           {"nom": "tub_a", "material": "Pb", "forma": "cilindre", "pos_cm": [-8, 0, 0],
                            "radi_cm": 1.27, "alzada_cm": 68, "densitat_gcm3": 11.35},
                           {"nom": "col", "material": "Pb", "forma": "tub", "pos_cm": [0, 0, 45],
                            "radi_int_cm": 3, "radi_ext_cm": 6, "alzada_cm": 10, "densitat_gcm3": 11.35},
                           {"nom": "eixat", "material": "Pb", "forma": "cilindre", "pos_cm": [0, 0, 0],
                            "radi_cm": 2, "alzada_cm": 10, "eix": "z"},                 # reservat §25: rebotat
                           {"nom": "vell", "material": "Pb", "forma": "caixa", "pos_cm": [0, 0, 0],
                            "dx_cm": 4, "dy_cm": 4, "dz_cm": 4},                        # semides §24 fora de §25
                           {"nom": "", "material": "", "forma": "", "pos_cm": []}]}]
    js = (src + "\nconst D = " + json.dumps(dominis) + ";\n"
          "const out = D.map(d => [cBlocExt(d).forma, cBlocExt(d).m, cBlocExt(d).sense, "
          "cCossosEscena(d).map(c => [c.nom, c.forma, c.reservats.join('/'), c.semidesFora.join('/'), cCosMal(c)])]);\n"
          "console.log(JSON.stringify(out));")
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    for d, (forma, m, sense, cossos) in zip(dominis, json.loads(r.stdout)):
        b = d["bloc"]
        if b.get("forma") == "cilindre":
            assert forma == "cilindre" and m == [2 * b.get("radi_cm", 0) or 30, 2 * b.get("radi_cm", 0) or 30, b.get("alzada_cm", 0) or 80]
            assert sense == (not (b.get("radi_cm", 0) > 0 and b.get("alzada_cm", 0) > 0))
        else:
            assert forma == "cub" and m == b.get("mides_cm")
        esperats = [(c.get("nom") or f"cos {k + 1}", c.get("forma") or "",
                     "/".join(k for k in CF.CAMPS_RESERVATS if k in c),
                     "/".join(k for k in CF.SEMIDES_FORA if k in c))
                    for k, c in enumerate(d.get("cossos", []))]              # sense `nom`, el dibuix en posa un de *visual* (no al yaml)
        assert [(n, f, rs, sf) for n, f, rs, sf, _ in cossos] == esperats
        if cossos:                                                           # el quart domini: la taula de §25 sencera
            mal = [m for *_, m in cossos]
            assert mal == [False, False, False, True, True, True], cossos    # les bones no es marquen; reservat, semides i fila buida, sí
            cs = d["cossos"]
            assert [CF._errors_cossos(cs[i:i + 1]) == [] for i in range(3)] == [True, True, True]
            assert [CF._errors_cossos(cs[i:i + 1]) != [] for i in (3, 4, 5)] == [True, True, True]   # mateix veredicte, JS i Python


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar les funcions pures de la UI")
def test_la_fila_nova_de_la_taula_no_porta_cap_valor():
    assert 'data-act="cos+"' in INDEX and "push({})" in INDEX
    assert "// §25: la fila nova és buida, cap valor per defecte" in INDEX
    assert 'data-act="cos-"' in INDEX
    # la taula buida torna a ser `domini.cossos` absent (§25 regla 1), no una llista buida
    assert "delete CP.f.domini.cossos" in INDEX
    # el `transport` només és editable per al món (`domini.mon.transport`); el per cos és RESERVAT: no té input, rebota a la taula
    assert 'domini.cossos.${i}' in INDEX and 'data-p="domini.mon.transport"' in INDEX
    assert not [x for x in INDEX.split('"') if x.startswith("domini.cossos.") and x.endswith(".transport")]
