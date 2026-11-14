"""test_etiq_no_decl.py — UI-ETIQ-NO-DECL: el cens `etapes_no_declarades` (contracte UI **v1.27**, §13c; neudet `ec36a2d`).

Què es fixa
-----------
- **La UI no té cap còpia del criteri.** El repartiment entre `etapes[]` i `etapes_no_declarades` el fa
  `_al_flux` **de neudet**, carregat de `NEUDET_ROOT` per ruta com fan els seus propis tests
  (`neudet/tests/test_v127_no_decl.py:15`). A `src/simui` no hi ha cap `def _al_flux` ni `def _base` ni
  `def _apartats`, i cap literal `_anterior_`/`_aturada_`: si hi aparegués, la UI s'hauria escrit el criteri
  per la seva compte.
- **Test bessó, en dues parts.** (1) Sobre la mateixa fixture que ells (`test_v127_no_decl.py:46-73` i
  `:76-88`), el seu generador i el nostre `manifest_provisional` reparteixen igual; (2) sobre les campanyes
  reals amb `campanya_ui.json`, el nostre provisional diu el mateix flux i el mateix cens que el manifest
  que ells van escriure (regenerats l'última vegada a `06de072`).
- La forma del cens: `anterior: null` (mai `false`), `candidats` traduït de `candidats_csv`, `dir` la seva
  carpeta, cap predecessor ni número endevinat pel nom.
- **La forma del cens, mirall del seu `KEYS_ETAPA`.** La divergència que havíem escrit (4 claus al cens, sense
  `verificada_per` ni `figures`) la va tancar el coordinador per decret (`7585843`) i neudet la va publicar
  (`06de072`): l'entrada del cens surt de la **mateixa `_etapa()`** que la de flux
  (`neudet/scripts/disseny/manifest_campanya.py:165-169`). Aquí es fixa el mirall — el mateix joc de 16 claus,
  com a molt una de més (`motiu_aturada`), `anterior: null` — i que pels dos camins la UI arriba a la **mateixa**
  conclusió (`verifica` i els candidats marcats com a verificats). Si ells tornen a retallar el cens, peta aquí.
- Conseqüència mesurada: a `c04_draft` el que ha corregut de veritat és al cens, així que les columnes de
  Pareto (que es comparen contra els csv del flux) queden sense poder-se comprovar.
- Un neudet vell (sense `_al_flux`) peta dient on buscar-lo, en lloc de repartir com li sembla.
Sense neudet, els tests amb dades reals es salten.
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simui import campanya_vista as V  # noqa: E402
from simphy.mcgen import design as D  # noqa: E402

SRC = ROOT / "src" / "simui"
CENS = "etapes_no_declarades"
GEN = "scripts/disseny/manifest_campanya.py"          # el que escriu `campanya_ui.json`
MOTIU_SENSE_CSV = "encara no hi ha cap candidats.csv: les mètriques del Pareto no es poden comprovar"


def _neudet():
    try:
        return V.neudet_root()
    except (V.CampanyaError, D.DesignError) as e:
        pytest.skip(f"neudet no és present: {e}")


def _per_nom(llista):
    return {e["nom"]: e for e in llista}


@pytest.fixture(scope="module")
def c04():
    try:
        return V.dir_de("c04_draft")
    except (V.CampanyaError, D.DesignError) as e:
        pytest.skip(str(e))


# ── la UI no s'ha escrit el criteri ─────────────────────────────────────────

def test_a_src_simui_no_hi_ha_una_copia_del_criteri():
    for f in sorted(SRC.glob("*.py")):
        defnoms = {n.name for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))) if isinstance(n, ast.FunctionDef)}
        copiades = defnoms & {"_al_flux", "_base", "_apartats", "_json_aturada"}
        assert not copiades, f"{f}: redefineix el criteri de neudet ({sorted(copiades)})"
    text = "\n".join(f.read_text(encoding="utf-8") for f in sorted(SRC.glob("*.py")))
    text += (SRC / "static" / "index.html").read_text(encoding="utf-8")
    for pat in ("_anterior_", "_aturada_"):
        assert pat not in text, f"src/simui conté {pat}: la regex d'apartats (`APARTAT`) és de neudet"
    codi = (SRC / "campanya_vista.py").read_text(encoding="utf-8")
    assert codi.count("mn._al_flux(") == 1, "el criteri només es pot cridar com a atribut del mòdul de neudet"


def test_el_criteri_que_s_usa_es_el_fitxer_de_neudet():
    mn = V._manifest_neudet()
    assert Path(mn.__file__) == _neudet() / GEN
    # la taula de veritat que ells es fixen a si mateixos (`test_v127_no_decl.py:23-32`), sobre el mateix yaml
    et = {"S1": {}, "S1b": {}}
    assert [mn._al_flux(n, et) for n in
            ("S1", "S1_anterior_2026-11-01", "S1_aturada_2026-11-02_2", "S1_g4", "S1_g4_anterior_2026-11-03")] == [True] * 5
    assert [mn._al_flux(n, et) for n in
            ("S1_draft", "S1_draft_g4", "S1_v2", "S1_v2_anterior_2026-11-03", "S9_res")] == [False] * 5


# ── bessó 1: la mateixa fixture, els dos costats ────────────────────────────

def _fixture(d: Path, csv_a: list, pla: bool = False) -> Path:
    """La fixture de neudet (`test_v127_no_decl.py:46-56`): el yaml de `c0_2a0511` (declara `S1`) i directoris
    d'`etapes/`; `csv_a` són els que tenen `candidats.csv` (els altres no apareixen enlloc). `pla` és com el
    seu cas c04 (`:81`): CONF-PLA només existeix si hi ha PLA.md (`manifest_campanya.py:171`)."""
    d.mkdir(parents=True)
    shutil.copy(_neudet() / "disseny/campanyes/c0_2a0511/campanya.yaml", d / "campanya.yaml")
    if pla:
        (d / "PLA.md").write_text("# %s\n\n## S1 · prova\n\nPregunta: quina?\n" % d.name, encoding="utf-8")
    for e in csv_a:
        (d / "etapes" / e).mkdir(parents=True)
        (d / "etapes" / e / "candidats.csv").write_text("nom,hash\nr4_t0,c26e3ff49e11\nr1_t2,9f3ab21c00aa\n",
                                                        encoding="utf-8")
    (d / "etapes" / "S1_sense_csv").mkdir()
    return d


def _genera_ells(d: Path) -> dict:
    nd = _neudet()
    r = subprocess.run([sys.executable, str(nd / GEN), str(d)], capture_output=True, text=True, cwd=str(nd),
                       env={"PYTHONPATH": "%s:%s" % (nd / "src", Path.home() / "projects/simnet/src"),
                            "PATH": "/usr/bin:/bin", "HOME": str(Path.home())})
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads((d / "campanya_ui.json").read_text(encoding="utf-8"))


def _compareix(man: dict, prov: dict, d: Path) -> None:
    """El que diu el seu manifest i el que diu el nostre provisional, comparats nom per nom."""
    assert [e["nom"] for e in prov["etapes"]] == [e["nom"] for e in man["etapes"]], d
    assert [c["nom"] for c in prov[CENS]] == [c["nom"] for c in man[CENS]], d
    for c_ells, c_nostra in zip(man[CENS], prov[CENS]):
        assert c_ells["candidats_csv"] == c_nostra["candidats"] == "etapes/%s/candidats.csv" % c_ells["nom"]
        assert c_nostra["dir"] == "etapes/%s" % c_ells["nom"]
        # al cens d'ells `n_candidats` són les files del csv; al nostre provisional, `n_csv` (`n_candidats`
        # compta els candidats del `resultats_tub.json`, com a `etapes[]`: mateixa regla, mateixa asimetria)
        assert c_ells["n_candidats"] == c_nostra["n_csv"] == 2
        assert c_ells["anterior"] is None and c_nostra["anterior"] is None


TOTS = ["S1", "S1_anterior_2026-11-01", "S1_g4", "S1_draft", "S1_draft_g4", "S1_v2"]


def test_besso_a_la_fixture_de_ells_repartim_igual(tmp_path):
    d = _fixture(tmp_path / "cx", TOTS)
    man, prov = _genera_ells(d), V.manifest_provisional(d)
    assert {e["nom"] for e in man["etapes"]} == {"S1", "S1_anterior_2026-11-01", "S1_g4"}   # ells: :62
    assert {c["nom"] for c in man[CENS]} == {"S1_draft", "S1_draft_g4", "S1_v2"}            # ells: :70
    _compareix(man, prov, d)
    assert "executada" not in _per_nom(prov["etapes"])["S1"]      # S1 té execució pròpia: CONF-PLA no hi entra


def test_besso_cas_c04_etapa_declared_sense_execucio(tmp_path):
    """`test_v127_no_decl.py:76-88`: només corre una variant. L'etapa declarada surt a `etapes` amb
    `executada: false` i la variant al cens; el nostre provisional fa el mateix, i el `pla` és el text de
    neudet (`seccio_pla`), no res escrit aquí."""
    d = _fixture(tmp_path / "cy", ["S1_draft"], pla=True)
    man, prov = _genera_ells(d), V.manifest_provisional(d)
    assert [c["nom"] for c in man[CENS]] == ["S1_draft"]
    _compareix(man, prov, d)
    assert _per_nom(man["etapes"])["S1"]["executada"] is False
    nostra = _per_nom(prov["etapes"])["S1"]
    assert nostra["executada"] is False and nostra["candidats"] is None
    assert nostra["pla"] == _per_nom(man["etapes"])["S1"]["pla"]      # el mateix `seccio_pla` d'ells, secció sencera
    assert "Pregunta: quina?" in nostra["pla"]


def test_sense_PLA_md_NO_HI_HA_cap_entrada_executada_false(tmp_path):
    """CONF-PLA es nodreix de `PLA.md`: sense ell, l'etapa declarada que no ha corregut no surt a cap banda,
    ni a ells (`manifest_campanya.py:171`) ni aquí. La UI no l'inventa."""
    d = _fixture(tmp_path / "cw", ["S1_draft"])
    man, prov = _genera_ells(d), V.manifest_provisional(d)
    assert [e["nom"] for e in man["etapes"]] == [] and [c["nom"] for c in man[CENS]] == ["S1_draft"]
    _compareix(man, prov, d)


# ── bessó 2: les campanyes reals ────────────────────────────────────────────

def _la_llista_la_ui(id_: str) -> bool:
    try:
        V.dir_de(id_)
        return True
    except (V.CampanyaError, D.DesignError):
        return False


def test_besso_a_totes_les_campanyes_amb_manifest_repartim_igual():
    """Sobre els 30 manifests reals de neudet (`6559acd` els va regenerar), el nostre provisional diu el
    mateix flux i el mateix cens que ells. El cens no és buit a 9 (mesurat 2026-11-14); de les 9, la UI en
    llista 2 —`dir_de` mira `disseny/campanyes` i prou, i les altres set són a `disseny/certificacio` i a
    `disseny/experiments`. Que la UI les llisti és una altra fila, no aquesta."""
    nd = _neudet()
    ds = sorted(f.parent for f in nd.glob("disseny/**/campanya_ui.json") if ".claude" not in f.parts)
    assert len(ds) >= 30, f"només hi ha {len(ds)} manifests: neudet s'ha de remoure (6559acd)"
    amb_cens = []
    for d in ds:
        man = json.loads((d / "campanya_ui.json").read_text(encoding="utf-8"))
        prov = V.manifest_provisional(d)
        assert [e["nom"] for e in prov["etapes"]] == [e["nom"] for e in man["etapes"]], d
        assert [c["nom"] for c in prov[CENS]] == [c["nom"] for c in (man.get(CENS) or [])], d
        assert all(c["anterior"] is None for c in prov[CENS]), d
        if man.get(CENS):
            amb_cens.append(man["id"])
    assert sorted(amb_cens) == [
        "c04_draft", "c0_2anells",
        "cert_lnd_252248", "cert_lnd_252250", "cert_lnd_252285_E", "cert_lnd_252285_E12_sol_fin",
        "cert_lnd_2523_E12_sol_fin", "cert_rs_p4_1624_213", "x06_banc_pe_lnd252285",
    ], f"el cens ha canviat d'abast: {sorted(amb_cens)}. Cal reexplicar la fila: dues de les que la UI llista tenen un significat nou."
    assert sorted(i for i in amb_cens if _la_llista_la_ui(i)) == ["c04_draft", "c0_2anells"], \
        "la llista de la UI ha canviat; el que diu aquest test de les 9 és el que cal reescriure"


def test_a_c04_draft_el_que_ha_corregut_és_al_cens_i_no_al_flux(c04):
    """La conseqüència que no havíem vist: `c04_draft` declara `S1` i el que ha corregut són `S1_draft` i la
    seva `_g4`, que v1.27 posa al cens. Les dades hi són igualment —el que canvia és on cauen."""
    m = V.manifest(c04)
    assert m["provisional"] is False
    assert [e["nom"] for e in m["etapes"]] == ["S1"] and m["etapes"][0]["executada"] is False
    assert [c["nom"] for c in m[CENS]] == ["S1_draft", "S1_draft_g4"]
    v = V.vista(c04)
    assert {e["nom"] for e in v["etapes"]} == {"S1"}
    assert [c["nom"] for c in v[CENS]] == ["S1_draft", "S1_draft_g4"]
    assert [len(c["candidats"]) for c in v[CENS]] == [10, 2]              # les dades, com a qualsevol etapa
    assert _per_nom(v[CENS])["S1_draft"]["fitxers"]["dir"] == "etapes/S1_draft"
    assert all(c["anterior"] is None for c in v[CENS])


# ── el mirall de la forma del cens (decret `7585843`, neudet `06de072`) ──────

# el joc de claus que ells es fixen literalment a `tests/test_v127_no_decl.py:47-50`; si en reanomenen o en
# trellen una, peta aquí i a la vegada als seus — és el mateix pacte pels dos costats del contracte.
CLAUS_ETAPA = {"nom", "motor", "etapa_pla", "pla", "resposta", "candidats_csv", "resultats_tub",
               "meta", "figures", "n_candidats", "citable", "verificada_per", "anterior",
               "aturada", "intents_anteriors", "formules"}


def test_el_cens_porta_el_mateix_joc_de_claus_que_el_flux():
    """Divergència tancada: el cens ja no és minimal. Sobre els 30 manifests reals, cada entrada de cens porta
    el joc de 16 claus d'una entrada de flux — com a molt una de més, `motiu_aturada` (additiva, decret
    `7585843`) — i `anterior: null` sempre. Neudet se'n fixa el mateix a `test_v127_no_decl.py:52-66`."""
    ds = sorted(f.parent for f in _neudet().glob("disseny/**/campanya_ui.json") if ".claude" not in f.parts)
    assert len(ds) == 30, f"són {len(ds)} manifests, no 30: neudet (`06de072`) ha de tornar a estar sencer"
    n_cens = 0
    for d in ds:
        man = json.loads((d / "campanya_ui.json").read_text(encoding="utf-8"))
        for e in man["etapes"]:
            if "executada" not in e:                    # les CONF-PLA (`executada: false`) no surten d'`_etapa`
                assert set(e) == CLAUS_ETAPA, (d, e["nom"])
        for c in man[CENS]:
            assert set(c) - {"motiu_aturada"} == CLAUS_ETAPA, (d, c["nom"])
            assert c["anterior"] is None, (d, c["nom"])
            # §6b: qui publica, publica la **carpeta**; els fitxers els posa la vista.
            assert c["figures"] is None or isinstance(c["figures"], str), (d, c["nom"])
            n_cens += 1
    assert n_cens >= 20, f"el cens és buit a tot arreu ({n_cens} entrades): ells en tenen 24 a `06de072`"


def test_els_dos_camins_donen_el_mateix_cens_a_c04_draft(c04, tmp_path):
    """El que havíem escrit com a divergència —pel manifest una `_g4` del cens no podia dir quins candidats va
    verificar, i es veia sense figures— no passa amb el manifest de `06de072`: `_de_6b_entrada` tradueix el cens
    igual que el flux i els dos camins coincideixen. El que **sí** que segueix sent diferent és el compte
    `n_candidats`/`n_csv` (asimetria escrita a `_compareix`) i el text del `motor`."""
    man = json.loads((c04 / "campanya_ui.json").read_text(encoding="utf-8"))
    assert _per_nom(man[CENS])["S1_draft_g4"]["verificada_per"] == "S1_draft"      # l'ask (a), satisfeta

    amb = _per_nom(V.vista(c04)[CENS])
    sense = tmp_path / c04.name                       # el mateix directori, sense manifest: camí provisional
    shutil.copytree(c04, sense)
    (sense / "campanya_ui.json").unlink()
    prov = _per_nom(V.vista(sense)[CENS])

    for nom in ("S1_draft", "S1_draft_g4"):
        assert amb[nom]["verifica"] == prov[nom]["verifica"]
        assert amb[nom]["figures"] == prov[nom]["figures"]
        assert sorted((c["nom"], c["g4"]) for c in amb[nom]["candidats"]) == \
               sorted((c["nom"], c["g4"]) for c in prov[nom]["candidats"])
    assert amb["S1_draft_g4"]["verifica"] == "S1_draft"
    verificats = sorted(c["nom"] for c in amb["S1_draft"]["candidats"] if c["g4"])
    assert verificats == sorted(c["nom"] for c in amb["S1_draft_g4"]["candidats"])
    assert amb["S1_draft"]["figures"] == ["etapes/S1_draft/figures/eps_E.png",
                                          "etapes/S1_draft/figures/mapes_frontera.png",
                                          "etapes/S1_draft/figures/pareto.png"]      # l'ask (b), satisfeta


# ── el Pareto no absorbeix el cens (criteri que no és nostre) ───────────────

def test_les_columnes_de_pareto_sorten_només_del_flux(c04):
    """Les mètriques de `objectius.pareto` es comparen contra els `candidats.csv` de les etapes del flux. A
    `c04_draft` el flux ja no en té cap (les dues que han corregut són al cens), així que la pàgina diu el
    motiu i no pinta columnes. Que el cens hi entri seria canviar un criteri: és per a Albert, no per aquí."""
    p = V.vista(c04)["pareto"]
    assert p["eixos"] == [{"metrica": "eps_mitja", "sentit": "max"}, {"metrica": "cv", "sentit": "min"}]
    assert p["motiu"] == MOTIU_SENSE_CSV


# ── un neudet vell no pot fer que la UI endevini ────────────────────────────

def test_sense_el_criteri_de_neudet_peta_dient_on_buscar_lo(tmp_path, monkeypatch):
    nd = _neudet()
    guardat, V._MAN_NEUDET[:] = list(V._MAN_NEUDET), []
    try:
        monkeypatch.setattr(V, "neudet_root", lambda: tmp_path)
        with pytest.raises(V.CampanyaError, match=str(tmp_path / GEN)):
            V._manifest_neudet()
        (tmp_path / GEN).parent.mkdir(parents=True)
        (tmp_path / GEN).write_text("def res():\n    return 1\n", encoding="utf-8")
        V._MAN_NEUDET[:] = []
        with pytest.raises(V.CampanyaError, match="ec36a2d"):
            V._manifest_neudet()
    finally:
        V._MAN_NEUDET[:] = guardat
        V._manifest_neudet()                        # la resta de tests torna a tenir el de veritat


def test_una_campanya_sense_etapes_no_declarades_no_inventa_res(tmp_path):
    d = tmp_path / "cz"
    d.mkdir()
    (d / "campanya.yaml").write_text("id: cz\ndraft: true\netapes:\n  S1: {}\n", encoding="utf-8")
    m = V.manifest_provisional(d)
    assert m["etapes"] == [] and m[CENS] == []
