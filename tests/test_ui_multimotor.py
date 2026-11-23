"""test_ui_multimotor.py — UI-MULTIMOTOR (encàrrec 2026-11-23, `docs/site/encarrecs/2026-11-23_UI_MULTIMOTOR.md`).

Què es fixa (només el que no depèn dels punts N de neudet)
----------------------------------------------------------
- **S1 — l'etiqueta de la targeta és la de cada motor**: quan l'etapa té `comparacio_motors.json`,
  `kMotorsEtiqueta` pinta els noms dels motors aplicables (`B1 · salts` a mb10b_cd), no el
  `motor: "xarxa"` genèric del manifest; sense comparació (mb10b_anells), el `motor` de neudet tal com ve.
- **S2 — regla del temps amb `avis_cache` de neudet**: si avisa que les respostes venen de la cache,
  la cel·la diu «no mesurat» amb l'avís i no pinta el temps cru; si no, temps amb unitats (s, transport s)
  i FOM amb s⁻¹ citant `comparacio_motors.py`. Aquí no es calcula res: l'avís és text de neudet.
- **S3 — «vista normal» obre el plegat del motor**: l'enllaç duu `data-kvopen` i el controlador obre el
  `<details data-kv>` corresponent (no deixa un `href="#"` mort). La captura fa la prova del clic.
- **S7 — intents apartats plegats sota la seva etapa**: `kEtapesAmbIntents` agrupa els que neudet marca
  `anterior: true` pel camp `etapa_pla` (mai el nom de la carpeta — UI-X06); sense targeta principal,
  plegat a part; les no declarades van al plegat «Proves» del cens. mb10b_anells (cap apartat) no canvia.
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
NODE = pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar les funcions pures de la UI")

ESCD = "const escD = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');"
LABEL = "const kMotorsEtiqueta" + INDEX.split("const kMotorsEtiqueta")[1].split("function kComparacio")[0]
COMPARACIO = ("function kComparacio(e){" + INDEX.split("function kComparacio(e){")[1].split("// ── VERIF-UI")[0])
INTENTS = INDEX.split("// INTENTS-DEF-BEGIN")[1].split("\n", 1)[1].split("// INTENTS-DEF-END")[0]
PURE = INDEX.split("// NO-DECL-DEF-BEGIN")[1].split("\n", 1)[1].split("// NO-DECL-DEF-END")[0]


def _node(js: str):
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _node_dades(pre: str, func: str, dades):
    """`func(dades)` amb node, amb les dades per stdin: la vista completa de mb10b_cd no cap a l'argv."""
    js = pre + f"console.log(JSON.stringify(({func})(JSON.parse(require('fs').readFileSync(0, 'utf8')))));"
    r = subprocess.run(["node", "-e", js], input=json.dumps(dades, ensure_ascii=False),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _vista(campanya: str):
    d = V.dir_de(campanya)
    if not (d / "campanya.yaml").is_file():
        pytest.skip(f"la campanya {campanya} no és a aquest mirall de neudet")
    return d, V.vista(d)


def _etapa(v, nom):
    return next(e for e in v["etapes"] if e["nom"] == nom)


# ── S1: l'etiqueta de la capçalera ───────────────────────────────────────────

@NODE
def test_s1_a_mb10b_cd_letiqueta_son_els_motors_i_no_xarxa():
    _, v = _vista("mb10b_cd")
    sortida = _node_dades(ESCD + LABEL, "es => es.map(kMotorsEtiqueta)", v["etapes"])
    s1 = next((et, etq) for et, etq in zip(v["etapes"], sortida) if et["nom"] == "S1")
    assert s1[1] == "B1 · salts", s1
    assert "xarxa" not in s1[1]
    for et, etq in zip(v["etapes"], sortida):
        ms = [str(m["nom"]) for m in (et.get("comparacio") or {}).get("motors", []) if m.get("aplicable") is not False and m.get("nom")]
        assert etq == (" · ".join(ms) if ms else (et.get("motor") or "motor desconegut")), et["nom"]


@NODE
def test_s1_a_mb10b_anells_un_motor_no_canvia_res():
    _, v = _vista("mb10b_anells")
    sortida = _node_dades(ESCD + LABEL, "es => es.map(kMotorsEtiqueta)", v["etapes"])
    for et, etq in zip(v["etapes"], sortida):
        assert not (et.get("comparacio") or {}).get("motors"), f"{et['nom']} té comparació de motors; l'encàrrec diu que anells en té un"
        assert etq == et["motor"], (et["nom"], etq, et["motor"])   # el `motor` del manifest, tal com ve


def test_s1_les_dues_capcaleres_usen_kMotorsEtiqueta():
    assert INDEX.count("${escD(kMotorsEtiqueta(e))}") == 2   # targeta executada i «encara no ha corregut»
    assert "escD(e.motor || 'motor desconegut')" not in INDEX   # cap capçalera no pintava ja l'etiqueta per la seva


# ── S2: temps i FOM amb `avis_cache` ─────────────────────────────────────────

def _taula(e):
    return _node_dades(ESCD + "const kFit = s => 'fit:' + s;" + COMPARACIO, "kComparacio", e)


@NODE
def test_s2_cache_diu_no_mesurat_i_temps_real_porta_unitats():
    e = {"nom": "S1", "fitxers": {"dir": "etapes/S1"}, "motors": [], "comparacio": {"motors": [
        {"nom": "B1", "aplicable": True, "guanyador": "aa", "pareto": ["aa"], "temps_s": 0.2, "t_transport_s": None,
         "gpu": "cuda:2", "n_hist": 27500000, "fom_mitja": 1.4e10,
         "avis_cache": "26 respostes venen de la cache: el temps no és de transport complet"},
        {"nom": "openmc", "aplicable": True, "guanyador": "bb", "pareto": ["bb"], "temps_s": 120, "t_transport_s": 95.5,
         "n_hist": 1000, "fom_mitja": 2.3e9}], "g4": {}}}
    h = _taula(e)
    assert "no mesurat" in h and "el temps no és de transport complet" in h   # l'avís de neudet, text seu
    assert "0.2 s" not in h and "14000000000" not in h   # ni temps ni FOM del motor en cache (String(1.4e10))
    assert "120 s" in h and "transport 95.5 s" in h                            # temps i transport amb unitats
    assert "2300000000" in h and "s⁻¹" in h and "FOM = 1/(σ²·T)" in h          # FOM amb unitat i citant neudet


@NODE
def test_s2_a_mb10b_cd_el_temps_de_cache_no_es_pinta():
    d, v = _vista("mb10b_cd")
    s1 = _etapa(v, "S1")
    h = _taula(s1)
    aplicables = [m for m in s1["comparacio"]["motors"] if m.get("aplicable") is not False]
    assert aplicables and all(m.get("avis_cache") for m in aplicables), \
        "neudet ja va regenerar la comparació sense cache? actualitza aquest bessó (encàrrec N1)"
    for m in aplicables:
        assert f"{m['temps_s']} s" not in h, f"{m['nom']}: pinta el temps cru malgrat l'avís de cache"
    assert h.count("no mesurat") == 2 * len(aplicables)   # cel·la de temps i FOM per motor


# ── S3: «vista normal» obre el plegat del motor ──────────────────────────────

def test_s3_enllaca_i_el_controlador_obre_el_plegat():
    assert 'data-kvopen="${escD(v.nom)}"' in INDEX                       # l'enllaç porta el nom de la variant
    assert '`details[data-kv="${CSS.escape(a.dataset.kvopen)}"]`' in INDEX   # i el controlador troba aquell plegat
    assert "d.open = true" in INDEX                                      # l'obre, no deixa el `href="#"` mort


# ── S7: intents apartats i proves plegats ────────────────────────────────────

def test_s7_la_vista_passa_etapa_pla_del_manifest_sense_tocar_lo():
    d, v = _vista("mb10b_cd")
    manifest = json.loads((d / "campanya_ui.json").read_text(encoding="utf-8"))["etapes"]
    per_nom = {e["nom"]: e for e in manifest}
    for et in v["etapes"]:
        assert "etapa_pla" in et, f"{et['nom']}: la vista no propaga l'`etapa_pla` del manifest"
        assert et["etapa_pla"] == per_nom[et["nom"]].get("etapa_pla")   # tal com l'escriu neudet


K_ETAPA_STUB = "const kEtapa = e => '|' + e.nom + (e.anterior === true ? 'A' : 'M') + '|';"


@NODE
def test_s7_a_mb10b_cd_els_intents_es_pleguen_sota_S1():
    _, v = _vista("mb10b_cd")
    out = _node_dades(ESCD + K_ETAPA_STUB + INTENTS, "kEtapesAmbIntents", v["etapes"])
    apartats = [e["nom"] for e in v["etapes"] if e.get("anterior") is True]
    assert apartats, "mb10b_cd ja no té intents apartats? actualitza aquest bessó"
    assert 'data-intents="S1"' in out and f"Intents anteriors ({len(apartats)})" in out
    Inici = out.index('<details class="fold" data-intents="S1">')
    assert out.index("|S1M|") < Inici, "el plegat surt abans de la targeta S1"
    for nom in apartats:
        assert out.index("|" + nom + "A|") > Inici, f"{nom} es pinta fora del plegat"
    assert out.index("</details>") > max(out.index("|" + n + "A|") for n in apartats), "el plegat es tanca abans dels intents"


@NODE
def test_s7_a_mb10b_anells_no_canvia_res():
    _, v = _vista("mb10b_anells")
    out = _node_dades(ESCD + K_ETAPA_STUB + INTENTS, "kEtapesAmbIntents", v["etapes"])
    assert "data-intents" not in out and "<details" not in out
    assert out == "".join("|" + e["nom"] + ("A" if e.get("anterior") is True else "M") + "|" for e in v["etapes"])


@NODE
def test_s7_un_intent_sense_targeta_principal_forma_plegat_a_part():
    etapes = [{"nom": "E2", "anterior": True, "etapa_pla": "E1"}, {"nom": "E3", "anterior": True, "etapa_pla": None}]
    out = _node(ESCD + K_ETAPA_STUB + INTENTS + "console.log(JSON.stringify(kEtapesAmbIntents(%s)));" % json.dumps(etapes))
    assert 'data-intents="E1"' in out and "|E2A|" in out
    assert 'data-intents="sense etapa declarada"' in out and "|E3A|" in out
    assert "undefined" not in out and "null" not in out


@NODE
def test_s7_les_no_declarades_van_al_plegat_proves_del_cens():
    v = {"etapes_no_declarades": [{"nom": "S1_prova10k"}, {"nom": "X_test"}]}
    out = _node(ESCD + PURE + "console.log(JSON.stringify(kSeccioNoDecl(%s, e => '[' + e.nom + ']')));" % json.dumps(v, ensure_ascii=False))
    assert 'data-proves' in out and "Proves (2)" in out and "[S1_prova10k]" in out and "[X_test]" in out
    assert "<h2>Etapes no declarades al yaml</h2>" in out and "_es_execucio" in out   # el cens es continua explicant fora del plegat


def test_s7_kPinta_usa_kEtapesAmbIntents_i_no_torna_al_map_directe():
    assert "kEtapesAmbIntents(v.etapes)" in INDEX
    assert "v.etapes.map(e => kEtapa(e)).join('')" not in INDEX
    assert "out.push(kSeccioNoDecl(v, e => kEtapa(e, true)));" in INDEX   # la línia que fixa test_etiq_no_decl.py, intacta
