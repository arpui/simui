"""test_motors_ui.py — MOTORS-UI (contracte `simphy_ui.md` §26 v1.23, encàrrec 2026-11-18).

Què es fixa
-----------
- La vista d'una etapa declarada serveix `comparacio_motors.json` **tal com és** i una entrada de vista
  normal per cada motor amb `motors/<motor>/candidats.csv`; un motor «no aplicable» no hi té carpeta.
- Sense el fitxer, l'etapa queda com la vista d'avui (`comparacio` null, `motors` buit) —encàrrec, punt 3—.
- Un motor que el json declara i no té carpeta, i un json malformat, són `avisos` que diuen on mirar, no errors.
- El selector del formulari ve del contracte (`schema().avaluacio.motors`): la llista tancada i la seva línia
  (test bessó: si neudet mou §26, la línia el segueix; si en canvia els noms, el test peta).
- `to_yaml` conserva `avaluacio.motors`; un nom fora de la llista es rebutja; sense la clau, el yaml d'avui.
- El sufix « Atura la campanya.» amb què neudet distingeix els avisos de parada segueix a
  `scripts/disseny/comprova_campanya.py` (l'⛔ de la UI es basa en això) i a l'INDEX.
- Guards de l'INDEX: el selector, l'escriptura de `avaluacio.motors` només amb ≥2 marcats, i la comparació a la pàgina d'etapa.

Sense neudet, els tests que en necessiten es salten; els de l'INDEX no.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simui import campanya_form as CF  # noqa: E402
from simui import campanya_vista as V  # noqa: E402
from simphy.mcgen import design as DES  # noqa: E402

INDEX = (ROOT / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")

#: fixture §26: tres motors, un no aplicable (amb motiu), Geant4 per motor amb la taula (camí relatiu a la campanya)
CM = {
    "versio": 1,
    "motors": [
        {"nom": "B1", "aplicable": True, "motiu": None, "temps_s": 41.2, "gpu": "3090 idx0", "n_hist": 200000,
         "guanyador": "a1b2", "pareto": ["a1b2"], "fom_mitja": 0.83},
        {"nom": "salts", "aplicable": False, "motiu": "el nucli salts no cobreix PE 0,94 per sobre de 5 MeV",
         "temps_s": 0, "gpu": None, "n_hist": 0, "guanyador": None, "pareto": [], "fom_mitja": None},
        {"nom": "openmc_gpu", "aplicable": True, "motiu": None, "temps_s": 128.9, "gpu": None, "n_hist": 200000,
         "guanyador": "c3d4", "pareto": ["c3d4"], "fom_mitja": 0.61},
    ],
    "coincideix_guanyador": False,
    "g4": {"finalistes": ["a1b2", "c3d4"],
           "per_motor": {"B1": {"err_rel_max": 0.07, "dins_tol": True, "taula": "etapes/S1_draft/motors/B1/g4.md"},
                         "openmc_gpu": {"err_rel_max": 0.41, "dins_tol": False,
                                        "taula": "etapes/S1_draft/motors/openmc_gpu/g4.md"}}},
    "meta": {},
}


@pytest.fixture(scope="module")
def c04():
    try:
        DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")
    try:
        return V.dir_de("c04_draft")
    except V.CampanyaError as e:
        pytest.skip(str(e))


def _neudet_o_skip() -> Path:
    try:
        return DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def _copia(c04: Path, tmp_path: Path) -> Path:
    dst = tmp_path / "c04_draft"
    shutil.copytree(c04, dst)
    return dst


def _manifest_amb_etapa_executada(d: Path, c04: Path) -> None:
    """Manifest amb `S1_draft` (l'execució real de c04) com a etapa **declarada**: `_motors` només
    cobreix les declarades (encàrrec: la vista de l'etapa)."""
    m = {k: v for k, v in V.manifest_provisional(c04).items() if k not in ("provisional", "motiu")}
    s1 = [e for e in m["etapes_no_declarades"] if e["nom"] == "S1_draft"][0]
    m["etapes"] = [dict(s1)]
    m["etapes_no_declarades"] = [e for e in m["etapes_no_declarades"] if e["nom"] != "S1_draft"]
    (d / "campanya_ui.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")


def _poses_comparacio(d: Path, cm: dict = CM, omet: tuple = ()) -> None:
    """Escriu `comparacio_motors.json` i la carpeta d'etapa normal de cada motor aplicable, llevat dels d'`omet`."""
    (d / "etapes" / "S1_draft").joinpath("comparacio_motors.json").write_text(
        json.dumps(cm, ensure_ascii=False), encoding="utf-8")
    for m in cm["motors"]:
        if m.get("nom") and m.get("aplicable") is not False and m["nom"] not in omet:
                vd = d / "etapes" / "S1_draft" / "motors" / m["nom"]
                vd.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(d / "etapes" / "S1_draft" / "candidats.csv", vd / "candidats.csv")


# ── la vista (§26 punt 2 i 3) ───────────────────────────────────────────────

def test_sense_comparacio_l_etapa_queda_com_la_vista_davui(c04, tmp_path):
    d = _copia(c04, tmp_path)
    _manifest_amb_etapa_executada(d, c04)
    e = V.vista(d)["etapes"][0]
    assert e["nom"] == "S1_draft" and e["comparacio"] is None and e["motors"] == []


def test_comparacio_es_serveix_tal_com_es(c04, tmp_path):
    """Punt 3: aquí no es calcula res — el json de neudet surt igual com ha entrat."""
    d = _copia(c04, tmp_path)
    _manifest_amb_etapa_executada(d, c04)
    _poses_comparacio(d)
    v = V.vista(d)
    assert v["etapes"][0]["comparacio"] == CM


def test_una_variant_per_motor_aplicable(c04, tmp_path):
    d = _copia(c04, tmp_path)
    _manifest_amb_etapa_executada(d, c04)
    _poses_comparacio(d)
    v = V.vista(d)
    ev = v["etapes"][0]
    assert [x["nom"] for x in ev["motors"]] == ["S1_draft · B1", "S1_draft · openmc_gpu"]   # «salts» no aplicable: sense carpeta
    for x in ev["motors"]:
        nom = x["nom"].split(" · ")[1]
        assert x["motor"] == nom
        assert x["fitxers"]["dir"] == f"etapes/S1_draft/motors/{nom}"
        assert x["candidats"], f"{nom}: la vista normal ha de tenir candidats"
    assert not [a for a in v["avisos"] if "comparacio_motors" in a or "motors/" in a]


def test_motor_declarat_sense_carpeta_diu_on_falta(c04, tmp_path):
    """MAI INVENTIS: el json diu un motor i la carpeta no hi és → avís amb el camí, no una columna buida."""
    d = _copia(c04, tmp_path)
    _manifest_amb_etapa_executada(d, c04)
    cm = copy.deepcopy(CM)
    cm["motors"].append({"nom": "altre", "aplicable": True, "motiu": None, "temps_s": 1, "gpu": None,
                         "n_hist": 0, "guanyador": None, "pareto": [], "fom_mitja": None})
    _poses_comparacio(d, cm, omet=("altre",))      # la carpeta d'«altre» no es crea
    v = V.vista(d)
    assert [x["nom"] for x in v["etapes"][0]["motors"]] == ["S1_draft · B1", "S1_draft · openmc_gpu"]
    assert any("etapes/S1_draft/motors/altre/candidats.csv no hi és" in a for a in v["avisos"]), v["avisos"]


def test_comparacio_malformada_es_un_avis_no_un_error(c04, tmp_path):
    d = _copia(c04, tmp_path)
    _manifest_amb_etapa_executada(d, c04)
    (d / "etapes" / "S1_draft" / "comparacio_motors.json").write_text("{ no és json", encoding="utf-8")
    v = V.vista(d)
    assert v["etapes"][0]["comparacio"] is None and v["etapes"][0]["motors"] == []
    assert any("comparacio_motors.json" in a for a in v["avisos"]), v["avisos"]


def test_el_cens_no_declarat_no_rep_variants(c04, tmp_path):
    """L'encàrrec parla de «la vista de l'etapa» (les declarades al yaml): el cens no es compara."""
    d = _copia(c04, tmp_path)
    _poses_comparacio(d)                           # provisional: S1 declarada sense executació, S1_draft al cens
    v = V.vista(d)
    assert v["etapes"][0]["comparacio"] is None and v["etapes"][0]["motors"] == []    # S1 (executada: false)
    assert "comparacio" not in {e["nom"]: e for e in v["etapes_no_declarades"]}["S1_draft"]


# ── el formulari (§26 punt 1): la llista ve del contracte ───────────────────

def test_schema_motors_ve_del_contracte_i_el_besso_elsegueix():
    """El contracte §26 és la font mentre neudet no llegeix `avaluacio.motors` (SALTS-B pendent).
    Bessó: si neudet mou la mostra, `_troba` la segueix; si en canvia els noms, aquest test peta."""
    root = _neudet_o_skip()
    s = CF.schema()["avaluacio"]["motors"]
    assert [o["valor"] for o in s["valors"]] == list(CF.MOTORS_CONTRACTE) == ["B1", "salts", "openmc_gpu"]
    assert s["fitxer"] == "docs/site/contractes/simphy_ui.md"
    mostral = CF._linia("simphy_ui.md", 856, "openmc_gpu", CF._CONTRACTES)
    assert s["linia"] == CF._troba("simphy_ui.md", 856, "openmc_gpu", CF._CONTRACTES)
    assert "[" + ", ".join(CF.MOTORS_CONTRACTE) + "]" in mostral, f"§26 ha canviat la llista: {mostral!r}"
    assert (root / "docs" / "site" / "contractes" / "simphy_ui.md").is_file()


def test_to_yaml_conserva_motors_i_sense_clau_es_el_yaml_davui():
    _neudet_o_skip()
    f = CF.defaults()
    assert "motors:" not in CF.to_yaml(f)                       # c04 no en porta: compatibilitat (punt 1)
    f["avaluacio"]["motors"] = ["B1", "salts"]
    y = CF.to_yaml(f)
    assert yaml.safe_load(y)["avaluacio"]["motors"] == ["B1", "salts"]


def test_motor_fora_de_la_llista_es_rebutja_amb_el_motiu():
    _neudet_o_skip()
    f = CF.defaults()
    f["avaluacio"]["motors"] = ["B1", "gpt"]
    with pytest.raises(CF.FormError, match="gpt no són a la llista del contracte"):
        CF.to_yaml(f)
    f["avaluacio"]["motors"] = "B1"
    with pytest.raises(CF.FormError, match="avaluacio.motors: una llista de noms de motor"):
        CF.to_yaml(f)


# ── bessons dels avisos i guards de l'INDEX ──────────────────────────────────

def test_sufix_datura_es_de_neudet_i_la_ui_lusa():
    """L'⛔ de la UI es basa en el sufix que neudet escriu a `comprova.json`; si ells ho canvien, el test ho diu."""
    _neudet_o_skip()
    linia = CF._troba("comprova_campanya.py", 149, "Atura la campanya.", CF._SCRIPTS)
    assert 1 <= linia <= len((DES.neudet_root() / "scripts" / "disseny" / "comprova_campanya.py")
                             .read_text(encoding="utf-8").splitlines())
    assert "Atura la campanya." in INDEX


def test_formulari_ofereix_el_selector_i_escriu_motors_amb_dos_o_mes():
    assert 'data-motor="' in INDEX                              # checkboxes, una per motor del schema
    assert "cSet(CP.f, 'avaluacio.motors', ara)" in INDEX
    assert "ara.length >= 2" in INDEX                           # un sol motor (o cap): el yaml d'avui
    assert "'motors'" in INDEX                                  # a la llista `known` de cAvalHtml
    assert "schema().avaluacio.motors" in INDEX                 # sense la llista de neudet, el selector no s'ofereix


def test_la_pagina_deletapa_pinta_comparacio_i_variants():
    assert "kComparacio(e)" in INDEX and "kVariants(e)" in INDEX
    assert "no aplicable" in INDEX                              # el motor que no pot córrer no desapareix
    assert "coincideix_guanyador" in INDEX                      # «els motors coincideixen / no coincideixen»
    assert "data-kvopen" in INDEX                               # cada columna enllaça la vista normal
