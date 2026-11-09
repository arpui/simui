"""REAVALUA-UI pas 4: «Desa aquest criteri» (el desa `desa_criteri` de neudet) i el pla de verificació a Geant4 (`pla_verificacio`, només es mostra).
Els tests treballen sobre una CÒPIA temporària de la campanya (cap criteri de prova no es desa a neudet) i comparen amb les funcions de neudet cridades directament."""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from simui import api
from simui import campanya_criteris as X
from simui import campanya_vista as CV
from simui import server as S
from simphy.mcgen import design as DES

INDEX = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")
CAMP, ETAPA = "c04_draft", "S1_draft"
node = pytest.mark.skipif(shutil.which("node") is None, reason="cal node")


@pytest.fixture
def copia(tmp_path, monkeypatch):
    try:
        arrel = DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(str(e))
    DES._neudet()
    origen = arrel / "disseny" / "campanyes" / CAMP
    if not (origen / "etapes" / ETAPA / "candidats.csv").is_file():
        pytest.skip(f"neudet no té {CAMP}/{ETAPA}")
    dest = tmp_path / "campanyes"
    shutil.copytree(origen, dest / CAMP)
    monkeypatch.setattr(CV, "campanyes_root", lambda: dest)
    return dest / CAMP


def _C(d):
    from neudet.disseny.campanya import Campanya
    with contextlib.redirect_stdout(io.StringIO()):
        return Campanya(d)


def _criteri(**kw):
    c = {"nom": "planor", "preferencia": {"maxim": "eps_mitja", "sobre": "cv", "c": [0.5, 2.0]}, "restriccions": [], "objectius": None, "nota": "prova"}
    c.update(kw)
    return c


def test_desa_criteri_escriu_neudet_el_criteris_json_i_els_guanyadors_son_els_de_neudet(copia):
    from neudet.disseny import criteris as CR
    r = X.desa(CAMP, ETAPA, _criteri())
    p = copia / "etapes" / ETAPA / "criteris.json"
    assert r["path"] == str(p) and p.is_file()
    fitxer = json.loads(p.read_text(encoding="utf-8"))
    assert fitxer["etapa"] == ETAPA and [c["nom"] for c in fitxer["criteris"]] == ["planor"]
    assert fitxer["criteris"][0] == r["criteri"] and r["avis"] is None
    C = _C(copia)
    esperat = CR.guanyadors(C, ETAPA, fitxer["criteris"][0])
    ll = {c["nom"]: c for c in X.llista(CAMP, ETAPA)["criteris"]}
    assert set(ll) == {"inicial", "planor"}
    assert {g["hash"]: g["motius"] for g in ll["planor"]["guanyadors"]} == esperat
    assert {g["hash"]: g["motius"] for g in r["criteris"][1]["guanyadors"]} == esperat
    assert {g["hash"]: g["motius"] for g in ll["inicial"]["guanyadors"]} == CR.guanyadors(C, ETAPA, CR.criteri_inicial(C))
    # la llista i els criteris són els de `criteris_de`
    assert [c["nom"] for c in CR.criteris_de(C, ETAPA)] == ["inicial", "planor"]


def test_un_criteri_amb_el_mateix_nom_se_substitueix_i_neudet_diu_l_avis_dels_objectius(copia):
    X.desa(CAMP, ETAPA, _criteri())
    r = X.desa(CAMP, ETAPA, _criteri(preferencia={"maxim": "eps_mitja", "sobre": "cv", "c": [1.0]}, objectius=[["eps_mitja", "max"], ["eps_min", "max"]]))
    assert [c["nom"] for c in r["criteris"] if not c["inicial"]] == ["planor"]
    from neudet.disseny import criteris as CR
    assert r["avis"] and "cal una etapa nova" in r["avis"]
    assert r["avis"] == CR.avis_objectius(r["criteri"], _C(copia).objectiu.pareto)


@pytest.mark.parametrize("nom", ["", "   ", "inicial"])
def test_nom_buit_o_inicial_neudet_ho_refusa_i_el_missatge_arriba_verbatim(copia, nom):
    from neudet.disseny import criteris as CR
    with pytest.raises(ValueError) as ex:
        CR.desa_criteri(_C(copia), ETAPA, _criteri(nom=nom))
    with pytest.raises(ValueError) as ui:
        X.desa(CAMP, ETAPA, _criteri(nom=nom))
    assert str(ui.value) == str(ex.value) and str(ui.value)
    assert not (copia / "etapes" / ETAPA / "criteris.json").exists()                  # no s'ha escrit res


def test_metrica_inexistent_i_etapa_inexistent_son_errors_de_neudet_o_de_la_forma(copia):
    with pytest.raises(ValueError, match="no és cap mètrica|no és a candidats.csv"):
        X.desa(CAMP, ETAPA, _criteri(preferencia={"maxim": "eps_mitja", "sobre": "inventada", "c": [1]}))
    with pytest.raises(ValueError, match="no té candidats.csv"):
        X.desa(CAMP, "no_existeix", _criteri())


def test_el_pla_es_el_de_pla_verificacio_directe_amb_els_parametres_de_la_campanya(copia):
    from neudet.disseny import criteris as CR
    from neudet.disseny import resum_peticio as RP
    from neudet.disseny.seleccio import ekey
    X.desa(CAMP, ETAPA, _criteri())
    C = _C(copia)
    ver = C.cfg["verificacio"]
    meta = CR.meta_g4(C, ETAPA)
    args = (meta or {}).get("args") or {}
    truth = DES.neudet_root() / "data" / "geant4" / "detector" / "verificacio"
    taxa = RP.taxa_g4(sorted(RP.CAMPANYES.glob("*/etapes/*/meta.json")))
    with contextlib.redirect_stdout(io.StringIO()):
        d = CR.pla_verificacio(C, [ETAPA], int(args.get("aleatoris", 30)), int(args.get("llavor", 0)), (), ver.get("quants"),
                               int(ver.get("n_per_energia", 100_000)), ver["hits"], cell_dir=lambda h, E: truth / h / ("E" + ekey(E)), taxa=taxa)
    p = X.pla(CAMP, ETAPA)
    assert [x["hash"] for x in p["nous"]] == d["nous"] and [x["hash"] for x in p["verificats_ja"]] == d["verificats_ja"]
    assert p["cost"] == d["cost"] and p["cel_les_a_correr"] == d["cel_les_a_correr"]
    assert [x["hash"] for x in p["sense_truth"]] == d["sense_truth"]
    assert {k: [g["hash"] for g in v] for k, v in p["per_criteri"].items()} == {k: list(v) for k, v in d["per_criteri"].items()}
    assert set(p["per_criteri"]) == {"inicial", "planor"}
    assert all(x["nou"] == (x["hash"] in d["nous"]) for v in p["per_criteri"].values() for x in v)
    for a in d["avisos"]:
        assert a in p["avisos"]
    assert p["ordre"].endswith(f"verifica_g4.py --etapes {ETAPA} --campanya disseny/campanyes/{CAMP} --criteris")
    assert "Albert" in p["frase"] and "reescriu" in p["frase"] and f"{ETAPA}_g4 sencer" in p["frase"]
    if d["cost"]:
        assert p["formules_cost"]["font"].endswith("cost_g4") and str(RP.MARGE_DISC) in p["formules_cost"]["disc_gb"]


def test_el_pla_no_escriu_ni_crea_res(copia):
    abans = sorted(str(p.relative_to(copia)) for p in copia.rglob("*"))
    X.pla(CAMP, ETAPA)
    X.llista(CAMP, ETAPA)
    assert sorted(str(p.relative_to(copia)) for p in copia.rglob("*")) == abans


def test_sense_verificacio_hits_el_pla_peta_dient_on_buscar_ho(copia):
    y = copia / "campanya.yaml"
    import yaml
    cfg = yaml.safe_load(y.read_text(encoding="utf-8"))
    cfg["verificacio"].pop("hits")
    y.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="verificacio.hits"):
        X.pla(CAMP, ETAPA)


def test_les_rutes_nomes_el_desa_es_post_i_les_dues_de_lectura_son_get():
    src = Path(S.__file__).read_text(encoding="utf-8")
    get, post = src.split("def do_GET")[1].split("def do_POST")[0], src.split("def do_POST")[1]
    assert "/api/campanya/desa_criteri" in post and "/api/campanya/desa_criteri" not in get
    for r in ("/api/campanya/criteris", "/api/campanya/pla_verificacio"):
        assert r in get and r not in post
    assert callable(api.campanya_desa_criteri) and callable(api.campanya_pla_verificacio)


# ── la pàgina (JS) ──
def _js(expr: str, dades: dict):
    a = INDEX.index("const kCrPla = "), INDEX.index("async function kCrCarregaLlista")
    crit = INDEX[INDEX.index("function kReavCrit"):INDEX.index("async function kReavCalcula")]
    js = ("const escD = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');"
          "const kEnc = encodeURIComponent; const KC = {id: 'c'};" + crit + INDEX[a[0]:a[1]] + "const D = " + json.dumps(dades) +
          "; console.log(JSON.stringify(" + expr + "));")
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)


ORIG = {"objectius": [["eps_mitja", "max"], ["cv", "min"]], "k_sigma": 2, "maxim": "eps_mitja", "sobre": "cv", "c": [0.2], "restriccions": [["n_tubs", "<=", 8]]}


@node
def test_el_criteri_que_va_a_neudet_porta_nomes_les_restriccions_noves_i_els_objectius_si_canvien():
    st = {"orig": {"criteris": ORIG}, "crit": json.loads(json.dumps(ORIG)), "ctxt": "0.15, 0.3", "nomCrit": "planor", "notaCrit": "n"}
    assert _js("kCrCriteri(null, D.st)", {"st": st}) == {"nom": "planor", "preferencia": {"maxim": "eps_mitja", "sobre": "cv", "c": [0.15, 0.3]},
                                                       "restriccions": [], "objectius": None, "nota": "n"}
    st["crit"]["restriccions"].append(["eps_min", ">=", "0.05"])
    st["crit"]["objectius"] = [["eps_mitja", "max"], ["eps_min", "max"]]
    r = _js("kCrCriteri(null, D.st)", {"st": st})
    assert r["restriccions"] == [["eps_min", ">=", 0.05]] and r["objectius"] == [["eps_mitja", "max"], ["eps_min", "max"]]
    st["crit"]["k_sigma"] = 3
    st["crit"]["restriccions"] = []
    av = _js("kCrAvisosForma(null, D.st)", {"st": st})
    assert any("k·σ" in a and "no es desa" in a for a in av) and any("tret restriccions" in a for a in av) and any("objectius" in a for a in av)


@node
def test_el_panell_mostra_el_pla_nous_verificats_cost_formules_avisos_i_l_ordre_per_copiar():
    pla = {"etapa_g4": "S1_g4", "parametres": {"aleatoris": 0, "llavor": 0, "n": 1000000, "hits": "all", "quants": 3, "origen": "del campanya.yaml"},
           "nous": [{"hash": "h1", "nom": "cand_a"}], "verificats_ja": [{"hash": "h2", "nom": "cand_b"}],
           "per_criteri": {"inicial": [{"hash": "h2", "nom": "cand_b", "motius": [], "nou": False}], "planor": [{"hash": "h1", "nom": "cand_a", "motius": [], "nou": True}]},
           "avisos": ["aviso de neudet"], "cost": {"candidats": 1, "cel_les": 11, "cpu_h": 3.1, "durada_h": 0.2, "disc_gb": 68.6, "porta_disc_gb": 102.9},
           "formules_cost": {"cel_les": "cel·les = 1 × 11", "cpu_h": "CPU = f", "durada_h": "durada = g", "disc_gb": "disc = h"},
           "sense_truth": [{"hash": "h2", "nom": "cand_b"}], "cel_les_a_correr": 11,
           "ordre": "python3 scripts/disseny/verifica_g4.py --etapes S1 --criteris", "frase": "ho executa Albert; reescriu S1_g4 sencer"}
    h = _js("kCrPlaHtml({nom: 'S1'}, {pla: D.pla})", {"pla": pla})
    for t in ("cand_a", "cand_b", "aviso de neudet", "3.1", "0.2", "68.6", "cel·les = 1 × 11", "disc = h", "verifica_g4.py --etapes S1 --criteris",
              "ho executa Albert", "no s'ha llançat res", ">nou<", ">verificat<"):
        assert t in h, t
    assert "ja són verificats però no tenen el truth a disc" in h and "null" not in h and "undefined" not in h
    e = _js("kCrPlaHtml({nom: 'S1'}, {plaErr: 'error de neudet'})", {})
    assert "neudet diu" in e and "error de neudet" in e


def test_el_boto_de_verificacio_no_fa_cap_post_ni_executa_res():
    """`Verifica a Geant4 els nous` només crida kCrMostraPla, que fa un GET (api() sense cos) a pla_verificacio; l'única crida POST del bloc és «Desa»."""
    f = INDEX.split("async function kCrMostraPla")[1].split("\n}\n")[0]
    assert "api(kCrPla(nom))" in f and "{" not in f.split("api(kCrPla(nom))")[1].split(";")[0]          # api(url) sense cos → fetch GET
    assert "POST" not in f and "method" not in f and "desa_criteri" not in f
    assert "const kCrPla = nom => '/api/campanya/pla_verificacio?" in INDEX
    clic = INDEX.split("button[data-cr-act]")[1].split("});")[0]
    assert "kCrMostraPla(" in clic and clic.count("api(") == 0
    bloc = INDEX[INDEX.index("// ── REAVALUA-UI pas 4"):INDEX.index("function kReavCrit")]
    import re
    posts = re.findall(r"api\('/api/[^']*',\s*\{[^\n]*", bloc)                                          # api(url, cos) = POST; api(url) = GET
    assert len(posts) == 1 and "/api/campanya/desa_criteri" in posts[0]                                # l'únic POST és el de desar
    for prohibit in ("subprocess", "/api/run", "/api/campanya/verifica", "/api/campanya/llanca"):
        assert prohibit not in bloc
    assert "ho executa Albert" in bloc


def test_el_servidor_no_te_cap_ruta_que_llanci_la_verificacio():
    src = Path(S.__file__).read_text(encoding="utf-8") + Path(api.__file__).read_text(encoding="utf-8")
    assert "subprocess" not in Path(X.__file__).read_text(encoding="utf-8") and "Popen" not in Path(X.__file__).read_text(encoding="utf-8")
    assert "verifica_g4" not in src.replace("verifica_g4.py", "")


def test_la_pagina_connecta_el_desa_la_llista_i_el_pla():
    for t in ('data-rvp="d"', "kCrDesa", "kCrLlista", "kCrMostraPla", "/api/campanya/desa_criteri", "/api/campanya/criteris?id=", "Desa aquest criteri",
              "Verifica a Geant4 els nous", "kReavCalcula(nom, false)"):
        assert t in INDEX, t
