"""test_verif_ui.py — VERIF-UI (encàrrec 2026-11-23): bloc «Verificació amb Geant4» de cada etapa.

Què es fixa
-----------
- **`_verificacio_g4` no calcula res**: aparella els bessons `_g4` pel hash (com `_encaixa_g4`) i serveix
  l'ε mitjà escrit per neudet a cada costat; la selecció és `seleccio.csv` tal com és (files dict per
  capçalera). Sense fitxer, `seleccio` és `None` — mai una llista buida feta d'invent.
- **El mirall node** (marcadors `VERIF-DEF-BEGIN/END`): `kVerificacio` pinta els candidats verificats amb
  els motius de neudet, els dos ε i els enllaços; sense dades de verificació, no pinta res; amb un hash que
  no és a `seleccio.csv`, ho diu. Amb dades brutes, tot escapats.
- **La taula de `comparacio_motors.json` enllaça on és**: `taula` és relatiu al directori d'etapa
  (neudet `src/neudet/disseny/comparacio_motors.py:269`) i `fitxer()` el resol contra l'arrel de la
  campanya — la pàgina hi posa el prefix, i un test amb dades reals verifica que el camí resultant existeix.
- **Test bessó** (CLAUDE.md): el capçalera del `seleccio.csv` que neudet escriu a `mb10b_anells` conté les
  columnes que el lector llegix; si neudet mou el format, aquest test ho avisa abans que la pàgina calli.
Sense neudet, els tests amb dades reals es salten.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simui import campanya_vista as V  # noqa: E402

SRC = ROOT / "src" / "simui"
INDEX = (SRC / "static" / "index.html").read_text(encoding="utf-8")


def _neudet_o_skip() -> Path:
    try:
        return V.neudet_root()
    except Exception as e:
        pytest.skip(f"neudet no és present: {e}")


# ── _verificacio_g4: aparellament pel hash i seleccio.csv tal com és ─────────

def _mini_campanya(tmp_path: Path, amb_seleccio: bool = True) -> Path:
    d = tmp_path / "camp"
    s1 = d / "etapes" / "S1"
    s1.mkdir(parents=True)
    g4 = d / "etapes" / "S1_g4"
    g4.mkdir()
    if amb_seleccio:
        sel = d / "etapes" / "S1_verificacio"
        sel.mkdir()
        (sel / "seleccio.csv").write_text(
            "nom,hash,etapes,motius,params\n"
            'guanyador_a,h1,S1,S1:guanyador;S1:frontera_robusta,"{}"\n'
            "altre_b,h2,S1,demanat (--noms),\"{}\"\n", encoding="utf-8")
    return d


def _etapes_mini() -> list[dict]:
    return [
        {"nom": "S1", "verifica": None, "fitxers": {"dir": "etapes/S1"},
         "candidats": [{"nom": "guanyador_a", "hash": "h1", "eps_mitja": 0.024},
                       {"nom": "altre_b", "hash": "h2", "eps_mitja": 0.029},
                       {"nom": "no_verificat", "hash": "h3", "eps_mitja": 0.031}]},
        {"nom": "S1_g4", "verifica": "S1",
         "fitxers": {"dir": "etapes/S1_g4", "candidats": "etapes/S1_g4/candidats.csv"},
         "candidats": [{"nom": "guanyador_a", "hash": "h1", "eps_mitja": 0.0238},
                       {"nom": "altre_b", "hash": "h2", "eps_mitja": 0.0288}]},
    ]


def test_verificacions_aparella_pel_hash_i_serveix_els_dos_eps(tmp_path):
    d = _mini_campanya(tmp_path)
    etapes = _etapes_mini()
    avisos: list[str] = []
    V._verificacio_g4(d, etapes, avisos)
    assert avisos == []
    vs = etapes[0]["verificacions"]
    assert [v["etapa"] for v in vs] == ["S1_g4"]
    assert vs[0]["n_candidats"] == 2
    assert vs[0]["candidats"] == [
        {"nom": "guanyador_a", "hash": "h1", "eps_xarxa": 0.024, "eps_g4": 0.0238},
        {"nom": "altre_b", "hash": "h2", "eps_xarxa": 0.029, "eps_g4": 0.0288}]
    assert etapes[1]["verificacions"] == []            # ningú no verifica el `_g4`


def test_seleccio_es_serveix_tal_com_es_i_sense_fitxer_es_none(tmp_path):
    d = _mini_campanya(tmp_path)
    etapes = _etapes_mini()
    V._verificacio_g4(d, etapes, [])
    sel = etapes[0]["seleccio"]
    assert sel["csv"] == "etapes/S1_verificacio/seleccio.csv"
    assert [r["motius"] for r in sel["files"]] == ["S1:guanyador;S1:frontera_robusta", "demanat (--noms)"]
    assert etapes[1]["seleccio"] is None               # no hi ha S1_g4_verificacio: None, no una llista


def test_un_etapa_buida_no_peta_i_un_g4_sense_objectiu_no_dona_res(tmp_path):
    d = _mini_campanya(tmp_path, amb_seleccio=False)
    etapes = [{"nom": "S9", "verifica": None, "fitxers": {}, "candidats": []},
              {"nom": "S9_g4", "verifica": "S9_inexistent", "fitxers": {}, "candidats": []}]
    V._verificacio_g4(d, etapes, [])                   # l'avís del destí inexistent és de `_encaixa_g4`
    assert etapes[0]["verificacions"] == [] and etapes[0]["seleccio"] is None


# ── el mirall node de kVerificacio ────────────────────────────────────────────

@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar les funcions pures de la UI")
def test_el_bloc_pinta_el_que_es_diu_amb_dades_reals_de_forma():
    escD = next(l for l in INDEX.splitlines() if l.startswith("const escD"))       # la real, no una còpia
    kEnc = next(l for l in INDEX.splitlines() if l.startswith("const kEnc"))
    kFit = next(l for l in INDEX.splitlines() if l.startswith("function kFit"))
    fmtNum = "function fmtNum(x){" + INDEX.split("function fmtNum(x){")[1].split("\n}")[0] + "\n}"
    kEnllac = next(l for l in INDEX.splitlines() if l.startswith("const kEnllacCand"))   # S10: l'enllaç al full
    dades = """
    const etapa = {nom: 'S1', verificacions: [{etapa: 'S1_g4', n_candidats: 2,
      fitxers: {candidats: 'etapes/S1_g4/candidats.csv', resultats_tub: 'etapes/S1_g4/resultats_tub.json'},
      candidats: [{nom: '2x7_cd0p667a360c0_8x21', hash: '9076caec067e', eps_xarxa: 0.0248127, eps_g4: 0.0243979},
                  {nom: 'h_u_a', hash: 'sense_seleccio', eps_xarxa: 0.02, eps_g4: 0.019}]}],
      seleccio: {csv: 'etapes/S1_verificacio/seleccio.csv', files: [
        {nom: '2x7_cd0p667a360c0_8x21', hash: '9076caec067e', motius: 'demanat (--noms)'},
        {nom: 'x', hash: 'y', motius: 'S1/motors/B1:frontera_robusta;S1/motors/salts:eps_restriccio_c=1.25'}]}};
    const sense = kVerificacio({nom: 'S2', verificacions: [], seleccio: null});
    const brutes = kVerificacio({nom: 'S1', verificacions: [{etapa: '"><s', n_candidats: 1, fitxers: {},
      candidats: [{nom: '"><s', hash: '"><s', eps_xarxa: 0.02, eps_g4: 0.02}]}], seleccio: null});
    console.log(JSON.stringify([kVerificacio(etapa), sense, brutes]));"""
    js = (INDEX.split("// VERIF-DEF-BEGIN")[1].split("\n", 1)[1].split("// VERIF-DEF-END")[0] +
          "\n" + escD + "\n" + kEnc + "\n" + kFit + "\n" + fmtNum + "\n" + kEnllac + "\nconst KC = {id: 'c'};\n" + dades)
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    bloc, sense, brutes = json.loads(r.stdout)

    assert "Verificació amb Geant4" in bloc
    assert "2x7_cd0p667a360c0_8x21" in bloc and "demanat (--noms)" in bloc
    assert "0,02481" not in bloc and "0.02481" in bloc and "0.0244" in bloc   # els dos ε, passats per `fmtNum`
    assert "frontera_robusta" not in bloc                        # els motius són per hash, no barrejats
    assert "no en diu el motiu" in bloc                          # un hash sense fila a seleccio.csv, ho diu
    assert "etapes%2FS1_g4%2Fcandidats.csv" in bloc               # l'enllaç, codificat per `kFit`/`kEnc`
    assert ">etapes/S1_verificacio/seleccio.csv</code>" in bloc   # el camí, llegible a sobre
    assert "la UI no el calcula" in bloc                         # cel·les fora/biaix: on haurien d'estar escrits
    # S10 (encàrrec 24-11): el candidat verificat té el mateix enllaç al full que la taula de l'etapa
    assert '<a href="#" data-full="9076caec067e">2x7_cd0p667a360c0_8x21</a>' in bloc

    assert sense == ""                                           # sense dades de verificació, no pinta res
    assert '&quot;&gt;&lt;s' in brutes   # S10: dins l'enllaç; l'escapament segueix sent d'`escD`, per les dues bandes
    assert '<b><a href="#" data-full="&quot;&gt;&lt;s">&quot;&gt;&lt;s</a></b>' in brutes


# ── els punts de la pantalla, pins de text ────────────────────────────────────

def test_el_bloc_es_pinta_a_la_tarjeta_i_la_taula_enllaca_des_del_directori_detapa():
    assert "${kComparacio(e)}\n    ${kVerificacio(e)}" in INDEX      # just després de la comparació de motors
    assert "encara no ha corregut</span></header>${kVerificacio(e)}" in INDEX   # i també a la targeta no-executada
    assert "e.fitxers.dir + '/' : '') + gm.taula" in INDEX           # `taula` és relatiu al directori d'etapa


def test_el_definidor_de_kverificacio_es_pure_i_mira_no_decl():
    cos = INDEX.split("// VERIF-DEF-BEGIN")[1].split("// VERIF-DEF-END")[0]
    assert "fetch(" not in cos and "KC." not in cos                 # ni crides ni estat global: mirable a node


# ── dades reals: mb10b_anells (S1_g4, 2 candidats) ────────────────────────────

def test_mb10b_anells_la_vista_dona_qui_verifica_i_per_que():
    _neudet_o_skip()
    if not (V.dir_de("mb10b_anells") / "campanya.yaml").is_file():
        pytest.skip("mb10b_anells no és a l'arbre de neudet")
    v = V.vista(V.dir_de("mb10b_anells"))
    s1 = next(e for e in v["etapes"] if e["nom"] == "S1")
    vs = s1["verificacions"]
    assert [x["etapa"] for x in vs] == ["S1_g4"]
    assert len(vs[0]["candidats"]) == 2
    for c in vs[0]["candidats"]:                                    # els dos ε existeixen, no inventats
        assert c["eps_xarxa"] is not None and c["eps_g4"] is not None
    assert s1["seleccio"] and all("motius" in r for r in s1["seleccio"]["files"])


def test_mb10b_anells_test_besso_el_seleccio_csv_de_neudet_te_el_format_que_llegim():
    root = _neudet_o_skip()
    sel = root / "disseny" / "campanyes" / "mb10b_anells" / "etapes" / "S1_verificacio" / "seleccio.csv"
    if not sel.is_file():
        pytest.skip("mb10b_anells no té S1_verificacio a l'arbre de neudet")
    header, rows = V._csv(sel)
    assert {"nom", "hash", "motius"} <= set(header)                 # el que llegeix `kVerificacio`
    assert rows and all(r["hash"] for r in rows)                    # cada candidat verificat, amb hash


def test_mb10b_cd_la_coral_multi_motor_es_servida_i_la_divergencia_queda_tancada():
    """Divergència TANCADA 23-11 (MAN-FORAT, neudet `6d06c41b`). El 23-11 al matí l'endreç `821a06b6` declarava
    l'`S1` d'mb10b_cd `executada: false` (el seu criteri no reconeixia la coral: sense `candidats.csv` a l'arrel)
    mentre les dades eren a `motors/<m>/` —ho vam escriure aquí. MAN-FORAT ho resol des de la font: `S1` surt
    com a execució amb `motors: [B1, salts]` (24-11: `openmc_gpu` s'hi afegeix a la mateixa etapa, COORDINACIO §6), `comparacio_motors` i `n_candidats` = la unió avaluada (25), i la
    vista la pinta amb el Geant4 per motor. Aquest test fixa el costat tancat; si algú torna a declarar l'etapa
    no-executada amb les dades al disc, peta aquí."""
    _neudet_o_skip()
    d = V.dir_de("mb10b_cd")
    if not (d / "etapes" / "S1" / "comparacio_motors.json").is_file():
        pytest.skip("l'arbre local de neudet no té les sortides SALTS-B d'mb10b_cd")
    man = json.loads((d / "campanya_ui.json").read_text(encoding="utf-8"))
    s1m = next(e for e in man["etapes"] if e["nom"] == "S1")
    assert "executada" not in s1m                                        # ja no és una CONF-PLA: és l'execució
    assert s1m["candidats_csv"] is None and s1m["comparacio_motors"] == "etapes/S1/comparacio_motors.json"
    assert [m["nom"] for m in s1m["motors"]] == ["B1", "openmc_gpu", "salts"]   # ordre del manifest, mirall fac3d329
    cm = json.loads((d / "etapes" / "S1" / "comparacio_motors.json").read_text(encoding="utf-8"))
    assert s1m["n_candidats"] == len(cm["nomes_candidats"]) == 25        # la unió avaluada, verbatim de neudet
    v = V.vista(d)
    s1 = next(e for e in v["etapes"] if e["nom"] == "S1")
    assert "executada" not in s1 and s1["fitxers"]["dir"] == "etapes/S1"
    assert s1["fitxers"]["candidats"] is None and s1["n_candidats"] == 25 and s1["citable"] is True
    assert s1["comparacio"] is not None                                  # la comparació de motors, tal com és
    per = s1["comparacio"]["g4"]["per_motor"]
    assert set(per) == {"B1", "salts", "openmc_gpu"}
    for m, gm in per.items():
        rel = f"etapes/S1/{gm['taula']}"                                  # el mateix prefix que posa la pàgina
        assert V.fitxer(d, rel).is_file(), f"{m}: la taula no és a {rel}"
    assert [mm["motor"] for mm in s1["motors"]] == ["B1", "salts", "openmc_gpu"]   # les targetes per motor, amb les seves dades
    assert s1["seleccio"] and len(s1["seleccio"]["files"]) == 4
