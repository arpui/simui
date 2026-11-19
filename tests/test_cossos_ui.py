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
    assert CF._errors_cossos([_pb(densitat_gcm3=11.34)]) == []                    # el veredicte del registre (material, ρ) és de neudet:
    tot = json.dumps(CF.cosos_info())                                             # «Comprova» el torna tal com és; aquí no se'n copia cap número
    assert "11.3" not in tot and "11,3" not in tot
    estat = CF.estat_geometria_neudet()                                           # (test amb neudet present a l'entorn de proves)
    costat = (estat.get("cossos") or {}).get("sidecar")
    if costat:                                                                  # la llista de materials ve del codi de neudet, live
        assert CF.cosos_info(estat["cossos"])["materials"] == costat["materials"]


def test_els_noms_de_cos_són_únics_perquè_són_el_volum_geant4():
    e = CF._errors_cossos([_pb(), _pb(pos_cm=[5, 0, 0])])
    assert e and "nom de cos repetit: a (el nom és el volum Geant4 `cos_<nom>`)" in e[0]


# ── el material d'un cos: DOS registres, tots dos llegits live (cap nom escrit aquí) ────────────────
# (Albert, 2026-11-14: «el Material a escollir hauria de sortir d'una llista i no posar el nom»; només «els que tenim a
# la xarxa o projectats a la xarxa», i hi comptà Air, air humit, concrete i buit.)

def test_el_material_dun_cos_es_una_llista_i_no_un_camp_on_escriure():
    # la llista la munta `cSelMat` amb el registre de cossos de neudet (`S.materials`) i el de la xarxa (`S.materials_xarxa`)
    assert "cSelMat(p + '.material', c.material, S)" in INDEX
    assert "cIn(p + '.material'" not in INDEX                       # res de text lliure: el nom no s'escriu a mà
    assert "MATERIALS-DEF-BEGIN" in INDEX and "MATERIALS-DEF-END" in INDEX


def test_el_registre_de_materials_de_la_xarxa_es_llegeix_de_simnet_i_no_se_n_inventa_cap():
    X = CF.materials_xarxa()
    if not X["disponible"]:                                        # sense simnet a l'entorn la UI ho diu, no n'inventa cap
        assert "simnet" in X["motiu"] and "no inventa materials" in X["motiu"]
        pytest.skip(f"simnet no és a l'entorn: {X['motiu']}")
    assert X["on"] == "/".join(CF.MATERIALS_XARXA_FITXER)          # la nota de la pantalla cita el fitxer real
    ids = sorted(m["mat_id"] for m in X["materials"])
    assert ids == list(range(len(ids)))                            # ids contigus des de 0: és el que porta l'embedding
    assert len({m["nom"] for m in X["materials"]}) == len(ids)      # un nom, una sola fila
    noms = {m["nom"] for m in X["materials"]}
    for n in ("Air", "AirHumid", "Concrete"):                      # els que l'Albert va demanar explícitament
        assert n in noms, (n, sorted(noms))
    assert [m["mat_id"] for m in X["materials"] if m["nom"] == "Pb"] == [14]
    assert X["alias"] and all(v in noms for v in X["alias"].values())   # els àlies apunten a files del mateix registre
    # `N_GAMMA_MATERIALS` (16 avui) és MENYS que les files (18): ho diu el propi fitxer de simnet — SST (16) i
    # SSTaisi316 (17) queden fora del rang de les xarxes N=16, que es creen amb `--n-materials 17`. La UI només el pinta.
    assert isinstance(X["n_de_la_xarxa"], int) and X["n_de_la_xarxa"] <= len(X["materials"])
    tot = json.dumps(CF.cosos_info())
    assert "density" not in tot and "11.35" not in tot and "0.94" not in tot
    # ↑ la ρ de la taula de simnet NO travessa: §25 vol `densitat_gcm3` escrit per qui omple la taula, i des de v1.28
    # neudet tampoc no la iguala a cap ρ del registre («Comprova» el torna tal com és; aquí no se'n copia cap número)


def test_el_registre_de_cossos_de_neudet_i_el_de_la_xarxa_són_dos_cosos_distints():
    _neudet()
    info = CF.cosos_info(CF.estat_geometria_neudet()["cossos"])
    assert info["materials"], "neudet no dóna el seu registre de materials de cossos"
    assert not [n for n in info["materials"] if n.lower() in ("buit", "void", "vacuum")]
    X = CF.materials_xarxa()
    if X["disponible"]:
        xa = {m["nom"] for m in X["materials"]}
        assert "Pb" in xa and "SST" in xa
        fora = xa - set(info["materials"])                     # el que la xarxa té i neudet rebutja a `domini.cossos`
        assert {"AirHumid", "Concrete"} <= fora, sorted(fora)
        assert "Air" not in fora                               # des de `COSSOS-MAT` (v1.28), Air és també al registre de cossos
        assert not [m["nom"] for m in X["materials"] if m["nom"].lower() in ("buit", "void", "vacuum")]
    # «buit» no és un *nom* de material a cap dels dos registres (la UI no l'inventa): neudet el va registrar amb el nom
    # de l'app, `Galactic` (v1.28, `COSSOS-MAT`), i la xarxa no hi té `mat_id` — el buit no es transporta (§25)


def test_el_buit_ja_es_a_la_llista_com_a_Galactic_i_la_cua_del_contracte_es_buida_sola():
    """L'Albert (14-11 nit): «poder definir un cos sense material… aquest tub/cilindre s'ha de poder definir com a buit…
    no cal provar res, només que es pugui fer». §5 de COORDINACIO (v1.28) fixa el registre de cossos a Pb, PE, Air i
    `buit`, amb la decisió de la nit del 14-11 que el `buit` d'un cos és `Galactic` (el material del món, cap material
    nou). La fila `COSSOS-MAT` de neudet **ho ha executat**: és a `main` (mesurat aquí, 15-11) — el registre és
    `domini.materials_cossos` de `validacions.json`, llegit per `materials_cossos()`, i `Galactic` hi és. Per això la UI
    el pinta live i la cua del contracte («decidit i encara no registrat») **es buida sola**, com estava dissenyat."""
    _neudet()
    import importlib
    ma = importlib.import_module("neudet.detector.materials")
    viu = set(ma.materials_cossos())
    assert {"Pb", "PE", "Air", "Galactic"} <= viu, sorted(viu)     # els quatre del contracte, al registre viu de neudet
    info = CF.cosos_info(CF.estat_geometria_neudet()["cossos"])
    assert set(info["materials"]) == viu                           # la UI pinta el live i res més
    assert info["materials_contracte"] == []                       # l'entrada pendent es va buidar sola: no és llista nostra
    assert "Galactic" in info["materials_nota"]                    # i ho diu en paraules: el `buit` de §5 és `Galactic`
    # la UI continua sense validar-lo ni declarar-lo vàlid: el veredicte del registre és de neudet («Comprova»)
    NC = importlib.import_module("neudet.disseny.cossos")
    assert CF._errors_cossos([_pb(material="buit")]) == []         # aquí «buit» no rebot: no és un nom de material
    v = NC.violacions_cossos([_pb(material="buit")])
    assert v and any("material registrat per a cossos" in x and "domini.materials_cossos" in x for x in v), v


def test_la_densitat_dun_cos_es_un_camp_lliure_i_lunica_comprovacio_es_que_sigui_positiva():
    """§5 v1.28 (ordre directa de l'Albert, 14-11: «donat un material el tenim per qualsevol densitat… no estic parlant
    de certificar aquesta densitat»): `densitat_gcm3` és un paràmetre, no un certificat. Des que la fila `COSSOS-MAT`
    de neudet és a `main` (mesurat aquí, 15-11), la comprovació és la mateixa als dos costats —número > 0— i el bessó
    registra l'ACORD: la vella divergència (UI acceptava ρ lliure amb Pb, neudet la rebota amb «plom amb
    densitat_gcm3») va morir amb el pin del Pb. El que avui ens separa és el `Galactic` —el `buit` de l'app és UN sol
    material—: la UI no hi mira i neudet el refusa en paraules (i l'app Geant4, en FATAL)."""
    _neudet()
    import importlib
    NC = importlib.import_module("neudet.disseny.cossos")
    ma = importlib.import_module("neudet.detector.materials")
    for rho in (0.94, 11.34, 0.0012):                       # PE, plom fora del pacte, un gas: la UI no els posa ni els treu
        assert CF._errors_cossos([_pb(densitat_gcm3=rho)]) == [], rho
    for rho in (0, -2.5, "onze"):
        e = CF._errors_cossos([_pb(densitat_gcm3=rho)])
        assert any(CF.COS_DENSITAT in x and "> 0" in x for x in e), (rho, e)
    # bessó en l'acord d'avui: el ρ lliure que la UI accepta, neudet l'accepta (abans el rebotava: pin mort)
    for rho in (0.94, 11.34, 0.0012):
        assert bool(NC.violacions_cossos([_pb(densitat_gcm3=rho)])) is False, rho
    assert bool(CF._errors_cossos([_pb(densitat_gcm3=0)])) == bool(NC.violacions_cossos([_pb(densitat_gcm3=0)]))
    # i la divergència que queda escrita: `Galactic`, l'ÚNIC ρ del buit de l'app (bloc `BUIT` de `MaterialFactory.cc`)
    rho_buit = ma.constants_buit()["kVacuumRho_gcm3"]
    assert NC.violacions_cossos([_pb(material="Galactic", densitat_gcm3=rho_buit)]) == []          # el de l'app: vàlid
    assert CF._errors_cossos([_pb(material="Galactic", densitat_gcm3=rho_buit * 3)]) == []         # la UI no hi mira
    v = NC.violacions_cossos([_pb(material="Galactic", densitat_gcm3=rho_buit * 3)])
    assert any("el buit és UN sol material" in x for x in v), v    # neudet el refusa en paraules: «Comprova» el torna tal com és


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
    aritmètica); el veredicte del registre (material registrat, ρ) el dona «Comprova» amb la frase de neudet. Amb cossos
    de Pb, doncs, el que és buit per a neudet és buit per a la UI i el que rebot, rebot pels dos costats."""
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
def test_un_bloc_sense_mides_queda_declarat_no_inventat_i_no_cassa():
    """MINIBELEN (2026-11-19): amb `mides_cm` absent, null o un text «PENDENT…» (el marcat de l'esborrany),
    `cBlocExt` ha de marcar `sense` (la UI avisa «el dibuix és orientatiu, no és la teva geometria»), no pot
    passar el text com si fos una mida (§22: aquestes mides no tenen valor per defecte) i no pot cassar als
    consumidors que fan `m.map` (peu del dibuix i escena)."""
    src = INDEX.split("// COSSOS-DEF-BEGIN")[1].split("\n", 1)[1].split("// COSSOS-DEF-END")[0]
    casos = [{"bloc": {}},
             {"bloc": {"mides_cm": None}},
             {"bloc": {"mides_cm": "PENDENT: mida de la Fig. 6 (a confirmar)"}},
             {"bloc": {"mides_cm": [0, 50, 70]}},                 # escrita però no positiva: també és «sense»
             {"bloc": {"mides_cm": [50, 50, 70]}}]
    js = (src + "\nconst out = " + json.dumps(casos) +
          ".map(d => { const e = cBlocExt(d); return [e.sense, e.m, e.m.map(x => Number(x) > 0)]; });\n"
          "console.log(JSON.stringify(out));")
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    surt = json.loads(r.stdout)                                   # sense, m, i que `m` sigui una llista de 3 (abans cassava amb el text)
    assert [s for s, _, _ in surt] == [True, True, True, True, False]
    assert all(len(v) == 3 for _, _, v in surt)
    assert [m for _, m, _ in surt][0:3] == [[30, 30, 80]] * 3      # el reemplac del dibuix, sempre avisat (sense=true)
    assert [m for _, m, _ in surt][3:] == [[0, 50, 70], [50, 50, 70]]   # el que hi ha escrit es mostra tal com és


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


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar les funcions pures de la UI")
def test_el_selector_de_material_pinta_els_dos_registres_i_el_que_no_hi_és():
    """El mateix `cSelMat` de la pantalla, executat amb node: Pb marcat com a registrat per a cossos, Air marcat com a
    rebutjat per neudet (la UI no l'amaga) i un valor que no és enlloc pintat tal com és. La cua del contracte amb
    `buit` és un valor **sintètic** per provar el mecanisme: des de `COSSOS-MAT` (v1.28) la llista real
    (`MATERIALS_COSSOS_CONTRACTE`) és buida —es va buidar sola quan neudet va registrar `Galactic`—, però el marcat i la
    caiguda han de seguir funcionant per si algun dia falta un material decidit i encara no registrat."""
    src = INDEX.split("// MATERIALS-DEF-BEGIN")[1].split("\n", 1)[1].split("// MATERIALS-DEF-END")[0]
    S = {"materials": ["Pb"],
         "materials_xarxa": {"disponible": True, "materials": [{"nom": "PE", "mat_id": 0},
                                                              {"nom": "Air", "mat_id": 8},
                                                              {"nom": "Pb", "mat_id": 14}]},
         "materials_contracte": [{"nom": "buit", "on": "COORDINACIO §5 (v1.28)", "motiu": "cos sense material"}]}
    js = ("const escD = s => String(s);\n" + src + "\nconst S = " + json.dumps(S) + ";\n"
          "console.log(JSON.stringify(['', 'Pb', 'Air', 'buit', 'Ametlla'].map(v => "
          "cSelMat('domini.cossos.0.material', v, S))));")
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    buida, pb, air, buit, ametlla = json.loads(r.stdout)
    assert '<option value="">—</option>' in buida and "selected" not in buida          # cap material per defecte
    assert 'label="a la xarxa (simnet)"' in pb
    assert 'value="Pb" selected>Pb · mat_id 14 · registrat per a cossos' in pb          # als dos registres: una sola fila
    assert pb.count('value="Pb"') == 1
    assert 'value="Air"' in pb and "neudet el rebutja avui" in pb                      # no s'amaga: es pinta marcat
    assert 'value="Air" selected' in air and "mat_id 8 · neudet el rebutja avui" in air
    # cua del contracte (sintètica aquí): un material decidit i encara no registrat surt marcat, no amagat
    assert 'value="buit" selected' in buit and "decidit al contracte, neudet encara no el registra" in buit
    assert buit.count('value="buit"') == 1                                             # es pinta una vegada, tal com és
    assert 'value="Ametlla" selected' in ametlla and "no és al registre de neudet ni a la xarxa" in ametlla
    # i cau sol, sense tocar la UI, el dia que neudet el registra — és el que va fer `COSSOS-MAT` amb `buit`→`Galactic`:
    # la llista live manava abans
    registrat = subprocess.run(
        ["node", "-e", "const escD = s => String(s);\n" + src + "\nconsole.log(cSelMat('p', 'buit', " +
         json.dumps({**S, "materials": ["Pb", "buit"]}) + "));"],
        capture_output=True, text=True, check=True)
    assert registrat.stdout.count('value="buit"') == 1
    assert 'value="buit" selected>buit · registrat per a cossos (neudet)' in registrat.stdout
    # el que neudet registra i la xarxa no (avui no n'hi ha cap) surt abans del grup, marcat com a registre de neudet
    alt = subprocess.run(["node", "-e", "const escD = s => String(s);\n" + src +
                         "\nconsole.log(cSelMat('p', 'Ametlla', {materials: ['Pb', 'Ametlla'], materials_xarxa:"
                         " {disponible: true, materials: [{nom: 'Pb', mat_id: 14}]}}));"],
                        capture_output=True, text=True, check=True)
    assert 'value="Ametlla" selected>Ametlla · registrat per a cossos (neudet)' in alt.stdout
    assert 'value="Pb" >Pb · mat_id 14 · registrat per a cossos' in alt.stdout          # Pb, a la xarxa, sense seleccionar
    # sense simnet: l'única llista que ofereix la UI és el registre de neudet (la nota de sota en diu el motiu)
    sense = subprocess.run(
        ["node", "-e", "const escD = s => String(s);\n" + src +
         "\nconsole.log(cSelMat('p', 'Pb', {materials: ['Pb'], materials_xarxa:"
         " {disponible: false, materials: [], motiu: 'no es troba simnet'}}));"],
        capture_output=True, text=True, check=True)
    assert "a la xarxa" not in sense.stdout and "registrat per a cossos (neudet)" in sense.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar l'arrossegament de la 3D")
def test_arrossegar_a_la_3d_escriu_exactament_el_que_el_dibuix_mostra():
    """L'arrossegament 3D (l'Albert, 14-11 nit: «de la 3D vull el complet» — la font i cada cos). El bessó executa amb
    node la part pura del visor i la contrasta amb la seva pròpia projecció `v3dProj`: les tres direccions amb què es
    mou una peça són exactament les tres direccions del dibuix (dreta, amunt, fondària), i del moviment del ratolí en
    surten centímetres arrodonits a 0,01 — no un número de ratolí."""
    src = "function v3dProj" + INDEX.split("function v3dProj")[1].split("// V3D-DRAG-END")[0]  # projecció + escala + direccions + pas
    assert not [x for x in ("CP.", "document.", "cSet(", "domini.") if x in src], \
        "la part pura no pot tocar el formulari: és la que s'executa aquí"
    js = src + """
const dif = (p, st, b, t) => [0, 1, 2].map(j => v3dProj(p.map((v, i) => v + t * b[i]), st)[j] - v3dProj(p, st)[j]);
const st = {az: 0.8, el: 0.35}, p = [3.5, -7.25, 1.75], t = 0.01, B = v3dBases(st);
const les3 = ["dreta", "amunt", "fons"].map(k => [k, dif(p, st, B[k], t).map(v => +v.toFixed(7))]);
const Z = {az: 0, el: 0};
const pas = [v3dPas([0, 0, 0], 10, 0, Z, 10, false),      // 10 unitats de viewBox a la dreta, amb 10 u/cm: +1 cm de x
             v3dPas([0, 0, 0], 0, -20, Z, 10, false),     // estirar cap a dalt: +2 cm de z (el centre, §25)
             v3dPas([0, 0, 0], 0, 10, Z, 10, true),       // ⇧: per la fondària, +1 cm de y
             v3dPas([1.5, 0, 0], 5, 0, Z, 7, false),      // 5/7 = 0,714…: s'arrodoneix a 0,01
             v3dPas([0, 0, 0], 10, 0, Z, 10, false)];     // `ini` no s'ha modificat: la darrera és com la primera
const esc = {bloc: [30, 30, 30], tubs: [], cossos: [{pos: [0, 0, 0], mides: [10, 10, 10], radi: 0, rext: 0, alzada: 0}]};
const K = v3dEscala(esc, {}), K2 = v3dEscala(esc, {z: 2}), Kfix = v3dEscala(
  {bloc: esc.bloc, tubs: [], cossos: [{pos: [900, 0, 0], mides: [10, 10, 10], radi: 0, rext: 0, alzada: 0}]}, {kFix: K});
console.log(JSON.stringify({les3, pas, K, K2, Kfix}));
"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    # cada direcció desplaça exactament un eix del dibuix: moure pel pla de la vista no és una aproximació
    for k, esperat in zip(("dreta", "amunt", "fons"), ([0.01, 0.0, 0.0], [0.0, 0.01, 0.0], [0.0, 0.0, 0.01])):
        got = dict(d["les3"])[k]
        assert [round(v, 6) for v in got] == esperat, (k, got)
    assert d["pas"][0] == [1, 0, 0] and d["pas"][1] == [0, 0, 2] and d["pas"][2] == [0, 1, 0], d["pas"]
    assert d["pas"][3] == [2.21, 0, 0], d["pas"]                       # 1,5 + 5/7 = 2,214… → 2,21 cm
    assert d["pas"][4] == d["pas"][0], "no pot modificar la posició original"
    # el zoom només multiplica l'escala, i mentre s'arrossega la mateixa: si no, el dibuix es resumiria sota el dit
    assert round(d["K2"] / d["K"], 9) == 2 and d["Kfix"] == d["K"], (d["K"], d["K2"], d["Kfix"])


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar les funcions pures de la UI")
def test_un_cos_amb_material_de_la_xarxa_sense_transport_avisa_que_la_rho_que_escriu_no_es_la_de_la_xarxa():
    """L'avís «quan un cos tingui material ∈ xarxa i transport NO marcat» ve de la decisió (3) de COORDINACIO §5
    (contracte v1.28, 14-11 vespre: «xarxa: restrictiva + avís», regla `AVI_MON_PB`) i de §25 (transport per cos
    RESERVAT; avui els cossos no els transporta el motor, `cossos.py:11-15`). El mateix filtre de la pantalla,
    executat amb node: són NOMS de cossos, no un càlcul; amb `domini.mon.transport` marcat l'avís cau sol, i un
    material que no és a la xarxa no l'activa (la UI no inventa ni relacional dades)."""
    src = INDEX.split("// MATERIALS-DEF-BEGIN")[1].split("\n", 1)[1].split("// MATERIALS-DEF-END")[0]
    cs = json.dumps([{"nom": "tub_del_buit", "material": "buit"}, {"nom": "moderador", "material": "PE"},
                     {"nom": "cap_no", "material": "Ametlla"}, {"material": "Pb"}])
    xa = json.dumps([{"nom": "Pb", "mat_id": 14}, {"nom": "PE", "mat_id": 0}])
    js = ("const escD = s => String(s);\n" + src + "\nconsole.log(JSON.stringify(["
          "cCososRhoXarxa(" + cs + ", " + xa + ", false), cCososRhoXarxa(" + cs + ", " + xa + ", true), "
          "cCososRhoXarxa([], " + xa + ", false), cCososRhoXarxa(" + cs + ", [], false)]));")
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    sense, marcada, sense_cs, sense_xa = json.loads(r.stdout)
    assert sense == ["moderador", "(sense nom)"], sense              # PE i Pb, que SÓN a la xarxa; buit i Ametlla, no
    assert marcada == [] and sense_cs == [] and sense_xa == []        # amb el motor transportant, o sense dades: res a dir
    # la frase és la del contracte i surt del servidor: la UI només la pinta quan hi ha cossos afectats
    assert "cCososRhoXarxa(cs, (S.materials_xarxa || {}).materials" in INDEX and "S.avis_rho_xarxa" in INDEX
    av = CF.cosos_info()["avis_rho_xarxa"]
    # àncors REALS (mesurats a COORDINACIO §5 i al contracte): res de fantasma — el 14-11 la coordinació va desdir
    # una fila `COSSOS-RHO-TRANS`, un «§5 v1.29» i un «§49» que no existeixen; si tornessin a la frase, aquest test
    # para (cap cita de la UI pot apuntar a una línia que `git log --all --grep` no troba).
    assert "registre de simnet" in av and "§25" in av and "v1.28" in av
    for fantasma in ("v1.29", "RHO-TRANS", "§49"):
        assert fantasma not in av, fantasma
