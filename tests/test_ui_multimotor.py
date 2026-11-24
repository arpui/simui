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
- **S8/S9/S10/S11 (revisió 24-11)**: el full té adreça pròpia `#neudet/<camp>/full/<hash>` i s'obre en
  pestanya nova; `resultats_per_motor` dona una entrada per motor del manifest (i el seu Geant4, germà
  `germa`/`germa_g4`) amb `eps_totals` i `metrics` verbatim del `candidats.csv`; `g4_comparacio` són les
  files del csv (biaix i estat llegits); guanyador/Pareto/verificats enllacen al full; la divergència
  `motor: "xarxa B1 + salts"`/`"openmc_gpu"` (artefacte i §2 d'acord des de neudet `fac3d329`, el lector de
  simphy encara no) queda escrita amb el seu test.
Sense neudet, els tests amb dades reals es salten.
"""
from __future__ import annotations

import csv
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
DATES = INDEX.split("// DATES-DEF-BEGIN")[1].split("\n", 1)[1].split("// DATES-DEF-END")[0]
G4RESUM = INDEX.split("// G4RESUM-DEF-BEGIN")[1].split("\n", 1)[1].split("// G4RESUM-DEF-END")[0]
PARAMS = INDEX.split("// PARAMS-DEF-BEGIN")[1].split("\n", 1)[1].split("// PARAMS-DEF-END")[0]
KDOC = "function kDoc(p, titol){" + INDEX.split("function kDoc(p, titol){")[1].split("}\n")[0] + "}"
K_ENLLAC = next(l for l in INDEX.splitlines() if l.startswith("const kEnllacCand"))   # S10: enllaç al full del candidat
RTOTALS = INDEX.split("// RTOTALS-DEF-BEGIN")[1].split("\n", 1)[1].split("// RTOTALS-DEF-END")[0]
RG4VAL = INDEX.split("// RG4VAL-DEF-BEGIN")[1].split("\n", 1)[1].split("// RG4VAL-DEF-END")[0]
FMTNUM = "function fmtNum(x){" + INDEX.split("function fmtNum(x){")[1].split("\n}")[0] + "\n}"
K_MD_STUB = "const kMd = (t, b) => 'MD' + String(t).length + ':' + b;"   # el resum del `.md` és feina de kMd
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
    # 24-11: `openmc_gpu` s'ha afegit a la mateixa etapa (COORDINACIO §6, neudet `2da50d8e`/`fac3d329`) — l'etiqueta
    # segueix sent la llista de motors del manifest, mai la paraula «xarxa».
    assert s1[1] == "B1 · salts · openmc_gpu", s1
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
    # `kComparacio` usa kFit i kPct100/kPctFix (bloc DATES) a la cel·la «contra Geant4»
    return _node_dades(ESCD + "const kFit = s => 'fit:' + s;" + DATES + COMPARACIO, "kComparacio", e)


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
    amb_cache = [m for m in aplicables if m.get("avis_cache")]
    # 24-11: `openmc_gpu` corre a la mateixa etapa i porta temps real de transport (1945,9 s, sense avís);
    # els dos de xarxa segueixen amb el seu avís de cache. La regla no canvia: amb avís, ni temps ni FOM.
    assert {m["nom"] for m in amb_cache} == {"B1", "salts"}, [m["nom"] for m in aplicables]
    sense_cache = [m for m in aplicables if not m.get("avis_cache")]
    assert {m["nom"] for m in sense_cache} == {"openmc_gpu"} and sense_cache[0]["temps_s"] == 1945.9
    for m in amb_cache:
        assert f"{m['temps_s']} s" not in h, f"{m['nom']}: pinta el temps cru malgrat l'avís de cache"
    assert "1945" in h                                      # el temps que sí que és de transport, pintat (`f()` el formata)
    assert h.count("no mesurat") == 2 * len(amb_cache)      # cel·la de temps i FOM, només pels que tenen avís


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


# ── S7/S5/S4/S6 (python): el que la vista ha de propagar del manifest ────────

def test_vista_propaga_dates_judici_i_portes_tal_com_son():
    d, v = _vista("mb10b_cd")
    man = json.loads((d / "campanya_ui.json").read_text(encoding="utf-8"))["etapes"]
    per_nom = {e["nom"]: e for e in man}
    for et in v["etapes"]:
        m = per_nom[et["nom"]]
        for k in ("data_inici", "data_fi", "durada_cerca_s"):
            assert et[k] == m.get(k), f"{et['nom']}: `{k}` no és el que diu el manifest"
        if m.get("judici"):
            assert et["judici"]["text"] == (d / m["judici"]).read_text(encoding="utf-8")
        else:
            assert et["judici"] is None
        assert [p["md"] for p in et["portes"]] == list(m.get("portes") or [])


def test_vista_multi_motor_no_publica_durada_i_el_intent_llarg_s():
    _, v = _vista("mb10b_cd")
    s1 = _etapa(v, "S1")
    assert s1["data_inici"] and s1["data_fi"], "S1 sense finestres de data (N5 de neudet no hi és?)"
    assert s1["durada_cerca_s"] is None, "multi-motor: neudet publica null i la UI no suma res"
    i2 = _etapa(v, "S1_anterior_2026-11-21_2")
    assert i2["durada_cerca_s"] == 2693.9, "la corrida de 45 min: és la dada mesurada a l'encàrrec"
    assert i2["data_inici"] < i2["data_fi"]


def test_vista_un_motor_publica_durada():
    _, v = _vista("mb10b_anells")
    s1 = _etapa(v, "S1")
    assert isinstance(s1["durada_cerca_s"], (int, float)), "un sol meta: neudet publica la durada"


def test_vista_les_variants_rep_la_riquesa_del_manifest_per_motor():
    _, v = _vista("mb10b_cd")
    s1 = _etapa(v, "S1")
    assert s1["motors"], "mb10b_cd sense variants per motor? actualitza aquest bessó"
    man = next(e for e in json.loads(V.dir_de("mb10b_cd").joinpath("campanya_ui.json").read_text(encoding="utf-8"))["etapes"] if e["nom"] == "S1")
    for mv in s1["motors"]:
        mm = next(x for x in man["motors"] if x["nom"] == mv["motor"])
        assert mv["per_candidat"] == mm["per_candidat"], mv["motor"]   # params i metrices (N3), tal com venen
        assert mv["g4_resum"] == mm["g4_resum"], mv["motor"]            # resum Geant4 per candidat (N2)
        assert mv["resum"] and mv["resum"]["md"] == mm["resum"], mv["motor"]


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


# ── S7 (JS): la finestra de la cerca i la durada, a la meta de cada targeta ───

@NODE
def test_s7_b_mb10b_cd_finestra_tall_d_ISO_i_sense_durada_multi_motor():
    _, v = _vista("mb10b_cd")
    out = _node_dades(ESCD + DATES, "es => es.map(e => [kFinestra(e), kDurada(e)])", v["etapes"])
    per = {e["nom"]: s for e, s in zip(v["etapes"], out)}
    s1 = _etapa(v, "S1")
    assert per["S1"][0] == s1["data_inici"][11:19] + " → " + s1["data_fi"][11:19] + " UTC"   # retall de l'ISO, cap matemàtica de zona
    assert per["S1"][1] is None, "multi-motor: neudet publica null i la UI no suma res"
    assert per["S1_anterior_2026-11-21_2"][1] == "la cerca 2693.9 s", "la corrida de 45 min de l'encàrrec"
    for nom, (fin, dur) in per.items():
        assert fin is None or fin.endswith(" UTC"), nom
        assert dur is None or (dur.startswith("la cerca ") and dur.endswith(" s")), nom
    assert any(f is not None for f, _ in per.values()), "cap etapa amb finestra? (N5 de neudet no hi és?)"


@NODE
def test_s7_b_mb10b_cd_openmc_un_motor_pinta_la_durada_mesurada():
    """Divergència fixada (24-11): el neudet va escriure que S1 d'aquesta campanya porta `executada: false` i per
    tant cap data; el manifest regenerat a `e6e9aeac` (mirall e0d29747) no porta la clau `executada` (entrada de flux
    executada, neudet `test_v127_no_decl.py:64`) i porta les 3 claus d'N5 amb durada. La regla de la UI no canvia:
    pinta la finestra i la durada que el manifest publica, o res, mai una suma."""
    _, v = _vista("mb10b_cd_openmc")
    s1 = _etapa(v, "S1")
    assert "executada" not in s1 or s1["executada"] is not False
    out = _node_dades(ESCD + DATES, "es => es.map(e => [kFinestra(e), kDurada(e)])", [s1])[0]
    assert out[0] == "17:39:19 → 18:11:45 UTC"
    assert out[1] == "la cerca 1945.9 s", "un sol motor (openmc_gpu): neudet publica la durada"


def test_s7_kEtapa_crida_kFinestra_i_kDurada_a_la_meta():
    assert "kFinestra(e), kDurada(e)]" in INDEX


# ── S2 (JS): la cel·la «contra Geant4» pinta el veredicte de neudet ───────────

@NODE
def test_s2_b_g4cel_veredicte_de_neudet_i_mai_dins_tol():
    e = {"nom": "S1", "fitxers": {"dir": "etapes/S1"}, "motors": [], "comparacio": {"motors": [{"nom": "B1", "aplicable": True}],
        "g4": {"per_motor": {"B1": {   # les dades mesurades de mb10b_cd·S1·B1 (contracte §8)
            "veredicte": "PASSA", "motius": [], "dins_tol": False,
            "fora_tol_concloents": 28, "cel_les_concloents": 428, "pct_fora": 6.542056074766355,
            "biaix_mitja": 0.00568, "err_rel_max": 0.21, "taula": "motors/B1/g4_comparacio.csv"}}}}}
    h = _taula(e)
    assert '<span class="tag t-ok">PASSA</span>' in h
    assert "dins tolerància" not in h and "fora de tolerància" not in h   # mai `dins_tol` com a veredicte
    assert "28 de 428 cel·les concloents fora (6.54 %)" in h              # pct_fora ja ve en percentatge: només decimals
    assert "biaix +0.57 %" in h                                           # fracció ×100, signat (acord §8)
    assert "fit:etapes/S1/motors/B1/g4_comparacio.csv" in h               # l'enllaç de la taula, intacte
    e["comparacio"]["g4"]["per_motor"]["B1"].update({"veredicte": "NO CONCLOENT", "motius": ["pocs counts a (3, 180°)"]})
    h2 = _taula(e)
    assert '<span class="tag t-wa">NO CONCLOENT</span>' in h2 and "t-ok" not in h2
    assert "pocs counts a (3, 180°)" in h2   # `motius` buits només quan PASSA; si n'hi ha, es pinten


def test_s2_g4cel_no_llegeix_dins_tol():
    assert "gm.dins_tol" not in INDEX   # la regla sencera: dins_tol no és mai un veredicte a la UI


@NODE
def test_s2_b_mb10b_cd_el_veredicte_real_es_pinta():
    _, v = _vista("mb10b_cd")
    s1 = _etapa(v, "S1")
    pm = ((s1.get("comparacio") or {}).get("g4") or {}).get("per_motor") or {}
    assert pm, "neudet no publica `g4.per_motor`? actualitza aquest bessó (N2 fusionat)"
    h = _taula(s1)
    assert "dins tolerància" not in h and "fora de tolerància" not in h
    for nom, gm in pm.items():
        assert gm.get("veredicte") in {"PASSA", "NO PASSA", "NO CONCLOENT"}, (nom, gm.get("veredicte"))
        assert f">{gm['veredicte']}</span>" in h, f"{nom}: el veredicte de neudet no es pinta"


@NODE
def test_s2_b_mb10b_cd_openmc_el_resum_N2_es_pinta():
    """mb10b_cd_openmc (fusió b2ff74e0 + regeneració e6e9aeac): `comparacio_motors.json` porta el resum d'N2 amb
    veredicte PASSA 37/423 — fixat aquí amb el que hi ha al mirall, no amb el que diu cap missatge."""
    _, v = _vista("mb10b_cd_openmc")
    s1 = _etapa(v, "S1")
    gm = ((s1.get("comparacio") or {}).get("g4") or {}).get("per_motor", {}).get("openmc_gpu")
    assert gm and gm["veredicte"] == "PASSA" and gm["fora_tol_concloents"] == 37 and gm["cel_les_concloents"] == 423
    h = _taula(s1)
    assert "37 de 423 cel·les concloents fora (8.75 %)" in h   # pct_fora = 8.747044917257684, arrodonit a la presentació
    assert "biaix +0.00 %" in h                                 # biaix_mitja = 3.237742253265046e-05 → +0,00 % (com diu neudet)
    assert "dins tolerància" not in h


# ── S6 (JS): resum Geant4 per candidat a la variant ───────────────────────────

@NODE
def test_s6_b_g4_resum_real_una_fila_per_candidat_del_manifest():
    _, v = _vista("mb10b_cd")
    mv = _etapa(v, "S1")["motors"][0]
    h = _node_dades(ESCD + DATES + K_ENLLAC + G4RESUM, "kG4Resum", mv)
    r = mv["g4_resum"]
    assert r, "el manifest no porta `g4_resum`? (N2 fusionat a b2cd155a)"
    assert h.count("<tr>") - 1 == len(r), "una fila per candidat del manifest"
    hpc = {c["nom"]: c.get("hash") for c in (mv.get("per_candidat") or [])}
    for nom, g in r.items():
        if hpc.get(nom):   # S10: el manifest dona el hash → el mateix enllaç al full que a la taula
            assert f'<b><a href="#" data-full="{hpc[nom]}">{nom}</a></b>' in h
        else:              # sense hash a les dades, text pla: no se n'inventa cap
            assert f"<b>{nom}</b>" in h
        assert f"{g['fora_tol']} / {g['cel_les']}" in h
        assert f"{g['fora_tol_concloents']} / {g['cel_les_concloents']}" in h
        assert f"{g['pct_fora']:.2f} %" in h
        assert f"tub {g['pitjor_cel_la']['tub']} · {g['pitjor_cel_la']['E_MeV']} MeV" in h   # dict llegible, mai JSON cru
    assert "dins_tol" not in h and "[object" not in h


# ── S4 (JS): paràmetres del motor per candidat (manifest `per_candidat[]`) ────

@NODE
def test_s4_b_params_per_candidat_reals():
    _, v = _vista("mb10b_cd")
    mv = _etapa(v, "S1")["motors"][0]
    h = _node_dades(ESCD + DATES + PARAMS, "kParamsCandidats", mv)
    pcs = [c for c in mv["per_candidat"] if c.get("params")]
    assert pcs and h.count("<tr>") - 1 == len(pcs), f"{mv['motor']}: una fila per candidat del manifest"
    for k in ("a0", "a1", "moderator_density"):
        assert f"<th>{k}</th>" in h
    c = pcs[0]
    assert f"<b>{c['nom']}</b>" in h
    assert "r=6 n=2" in h   # `a0` és geometria anidada {r, n, phi, …}: es pinta clau=valor, mai JSON cru
    assert "[object" not in h


# ── S5 (JS): judici i portes de l'etapa, resum del motor ─────────────────────

def test_s5_kEtapa_i_kVariantCos_criden_kDoc():
    assert 'kDoc(e.judici, "Judici' in INDEX
    assert "kDoc(p, \"Portes" in INDEX
    assert 'kDoc(v.resum, "Resum del motor' in INDEX


@NODE
def test_s5_b_judici_portes_i_resum_es_pleguen_tal_com_ve():
    _, v = _vista("mb10b_cd")
    s1 = _etapa(v, "S1")
    assert s1["judici"], "S1 sense `judici` al manifest? (neudet l'escriu a etapes/S1/judici_S1.md)"
    mv = s1["motors"][0]
    js = "x => [kDoc(x.e.judici, 'Judici'), kDoc(null, 'Judici'), x.e.portes.map(p => kDoc(p, 'Portes')), kDoc(x.mv.resum, 'Resum')]"
    out = _node_dades(ESCD + K_MD_STUB + KDOC, js, {"e": s1, "mv": mv})
    assert "etapes/S1/judici_S1.md" in out[0]
    assert f"MD{len(s1['judici']['text'])}:{s1['judici']['base']}" in out[0]   # el text íntegre, amb la base per les figures
    assert out[1] == "", "sense manifest no es pinta res"
    assert out[2] and all("Portes" in p for p in out[2])
    assert mv["resum"]["md"] in out[3] and f"MD{len(mv['resum']['text'])}:{mv['resum']['base']}" in out[3]


# ── S10 (JS): candidats escollits clicables ───────────────────────────────────

@NODE
def test_s10_guanyador_i_pareto_enllacen_al_full_i_sense_hash_text_pla():
    """El guanyador i el Pareto de cada motor tenen el mateix enllaç que la taula de l'etapa (pestanya nova amb
    l'adreça `#neudet/<camp>/full/<hash>`, handler `data-full` de k-out). El hash ve de `e.candidats`; si no hi
    és, text pla — mai se n'inventa un."""
    e = {"nom": "S1", "fitxers": {"dir": "etapes/S1"}, "motors": [],
         "candidats": [{"nom": "aa", "hash": "aabbccddeeff"}],
         "comparacio": {"motors": [
             {"nom": "B1", "aplicable": True, "guanyador": "aa", "pareto": ["aa", "zz"]},
             {"nom": "openmc", "aplicable": True, "guanyador": "bb", "pareto": []}], "g4": {}}}
    h = _taula(e)
    assert h.count('<a href="#" data-full="aabbccddeeff">aa</a>') == 2   # guanyador i Pareto del B1
    assert ">bb</b>" in h and 'data-full="bb"' not in h                  # «bb» no és a les dades: text pla
    assert ", zz" in h and 'data-full="zz"' not in h                     # «zz» al Pareto, pla i sense hash


@NODE
def test_s10_a_mb10b_cd_el_guanyador_real_enllaca():
    """`guanyador`/`pareto` del manifest són hashos (mirall mb10b_cd): l'enllaç en porta el i el text, el nom
    del `per_candidat` — el mateix que pinta la taula de l'etapa."""
    _, v = _vista("mb10b_cd")
    s1 = _etapa(v, "S1")
    h = _taula(s1)
    pcs = {c["hash"]: c["nom"] for mvv in (s1.get("motors") or []) for c in (mvv.get("per_candidat") or [])}
    assert pcs, "els motors no porten `per_candidat`? (N3 de neudet no hi és?)"
    for m in s1["comparacio"]["motors"]:
        for val in [m.get("guanyador")] + list(m.get("pareto") or []):
            if val in pcs:
                assert f'data-full="{val}">{pcs[val]}</a>' in h, f"{m['nom']}: {val} no enllaça al seu full"
            else:   # no inventar: si el hash no és a les dades, no surt com a enllaç
                assert f'data-full="{val}"' not in h


# ── S9/S11: el full per motor, ε total per energia, motor contra Geant4 valor a valor ──

HASH_PROVA = "18f5eb0ba3c0"     # `2x6_cd0p667a360c0b2_8x13` d'mb10b_cd: verificat, amb `g4_comparacio.csv`
NOM_PROVA = "2x6_cd0p667a360c0b2_8x13"


def _per_motor(camp: str, hash_: str = HASH_PROVA):
    d = V.dir_de(camp)
    if not (d / "campanya.yaml").is_file():
        pytest.skip(f"{camp} no és a aquest mirall de neudet")
    return d, V.resultats_per_motor(camp, hash_)


def _ent(es, retol):
    return next(e for e in es if e["retol"] == retol)


def test_s9_una_entrada_per_motor_del_manifest_i_el_geant4_al_costat():
    d, es = _per_motor("mb10b_cd")
    man = json.loads((d / "campanya_ui.json").read_text(encoding="utf-8"))
    ms = [m for e in man["etapes"] if isinstance(e.get("motors"), list)
          for m in e["motors"] if isinstance(m, dict)]
    # una entrada per motor i, per a cada motor que declara `g4`, la del seu Geant4 (mirall mb10b_cd 24-11)
    assert len(es) == len(ms) + sum(1 for m in ms if isinstance(m.get("g4"), dict))
    # 24-11 (mirall `fac3d329`): `openmc_gpu` corre ara a la mateixa `S1` d'mb10b_cd i el manifest el declara,
    # sense Geant4 propi (`motors/openmc_gpu/` no té `_g4`) — per això no té entrada germana.
    assert [e["retol"] for e in es] == [
        "S1 · B1", "S1 · Geant4 (B1)", "S1 · openmc_gpu", "S1 · salts", "S1 · Geant4 (salts)",
        "S1_anterior_2026-11-21_2 · B1", "S1_anterior_2026-11-21_3 · salts"]
    assert all(e["font"] == "neudet" for e in es)                # els camins són els del manifest de neudet
    b1, g = _ent(es, "S1 · B1"), _ent(es, "S1 · Geant4 (B1)")
    assert g["es_g4"] is True and b1["es_g4"] is False
    assert g["germa"] == b1["path"] and b1["germa_g4"] == g["path"]   # el Geant4, al costat del seu motor


def test_s9_entrada_ok_porta_tubs_eps_total_i_metrics_que_són_de_neudet():
    _, es = _per_motor("mb10b_cd")
    b1 = _ent(es, "S1 · B1")
    assert b1["status"] == "ok"
    assert len(b1["tubs"]) == 10 and len(b1["eps_totals"]) == 11
    assert [t["E"] for t in b1["eps_totals"]] == sorted(t["E"] for t in b1["eps_totals"])
    with open(Path(b1["path"]) / "candidats.csv", newline="", encoding="utf-8") as fh:
        row = next(r for r in csv.DictReader(fh) if r["hash"] == HASH_PROVA)
    for t in b1["eps_totals"]:      # la ε total per energia = les columnes `eps_<E>MeV` del candidats.csv, verbatim
        assert t["eps"] == float(row[f"eps_{t['E']:g}MeV"])
        assert t["sig"] == float(row[f"sig_{t['E']:g}MeV"])
    assert b1["metrics"]["eps_mitja"] == 0.132529 and b1["metrics"]["planor_f"] == 1.44819


def test_s11_g4_comparacio_són_les_files_del_candidat_al_csv():
    d, es = _per_motor("mb10b_cd")
    b1 = _ent(es, "S1 · B1")
    assert len(b1["g4_comparacio"]) == 110
    with open(d / "etapes" / "S1" / "motors" / "B1" / "g4_comparacio.csv", newline="", encoding="utf-8") as fh:
        files = [r for r in csv.DictReader(fh) if r["id"] == NOM_PROVA]
    assert len(files) == 110
    per = {(int(r["tub"]), float(r["E_MeV"])): r for r in files}
    for f in b1["g4_comparacio"]:
        r = per[(f["tub"], f["E"])]
        assert f["eps_motor"] == float(r["eps_motor"]) and f["eps_g4"] == float(r["eps_g4"])
        assert f["biaix"] == float(r["biaix"])                   # biaix i estat: llegits, no recomposats
        assert f["concloent"] is (r["concloent"] == "True")
        assert f["dins_tol"] is (r["dins_tol"] == "True")
    # un intent apartat sense `g4_comparacio` escrit: buida, no inventada
    assert _ent(es, "S1_anterior_2026-11-21_2 · B1")["g4_comparacio"] == []


def test_divergencia_motor_fora_del_contracte_simphy_ui_seccio_2():
    """Divergència escrita 24-11 (refeta el mateix dia amb la decisió de l'Albert). El
    `resultats_tub.json` dels `salts` d'mb10b_cd declara `motor: "xarxa B1 + salts"` i el d'mb10b_cd_openmc
    `"openmc_gpu"`. Decisió (a) de l'Albert (24-11, neudet `fac3d329`): **no es reescriu cap artefacte**,
    s'amplia el vocabulari — §2 (`~/projects/neudet/docs/site/contractes/simphy_ui.md:65`) admet ara els set
    valors, amb aquests dos. Queda doncs una divergència **contra simphy**: la còpia del §2 que fa el lector
    (`src/simphy/mcgen/results_tub.py:54`, `MOTORS`) segueix amb cinc valors i rebutja a la càrrega
    (`:162-166`, que corre per a tot `versio != "1"`). La UI no calcula res ni relaxa res: les entrades surten
    `error de lectura` amb el motiu tal com és. Aquest bessó fixa les tres mesures alhora (l'artefacte, el §2
    ampliat i el rebuig de simphy); quan simphy hi afegeixi els dos valors, cauran les dues assertions
    d'`ERROR_LECTURA` i s'actualitza aquí amb data — no es queda mut."""
    from simphy.mcgen import results_tub as RES
    try:
        contracte = (V.neudet_root() / "docs/site/contractes/simphy_ui.md").read_text(encoding="utf-8")
    except Exception as e:
        pytest.skip(f"neudet no és present: {e}")
    linea = [l for l in contracte.splitlines() if l.startswith("| `motor` |")][0]
    assert "`xarxa B1 + salts`" in linea and "`openmc_gpu`" in linea      # §2 ampliat (decisió de l'Albert)
    assert RES.MOTORS == ("xarxa B1", "geant4", "mcnp", "openmc", "fluka")  # i simphy, encara amb cinc
    _, es = _per_motor("mb10b_cd")
    s = _ent(es, "S1 · salts")
    assert s["status"] == RES.ERROR_LECTURA
    assert "motor 'xarxa B1 + salts' no és cap de xarxa B1, geant4, mcnp, openmc, fluka" in s["motiu"]
    assert _ent(es, "S1_anterior_2026-11-21_3 · salts")["status"] == RES.ERROR_LECTURA
    # 24-11: `openmc_gpu` corre ara a la mateixa etapa (COORDINACIO §6) i el motiu és el mateix
    assert "motor 'openmc_gpu' no és cap de" in _ent(es, "S1 · openmc_gpu")["motiu"]
    assert _ent(es, "S1 · Geant4 (salts)")["status"] == RES.OK   # el Geant4 propi, en canvi, sí que llegeix
    _, eo = _per_motor("mb10b_cd_openmc")
    o = _ent(eo, "S1 · openmc_gpu")
    assert o["status"] == RES.ERROR_LECTURA and "motor 'openmc_gpu' no és cap de" in o["motiu"]
    assert _ent(eo, "S1 · Geant4 (openmc_gpu)")["status"] == RES.OK


@NODE
def test_s9_c_rtotals_pinta_taula_i_gràfic_amb_el_geant4_de_traç_discontínu():
    _, es = _per_motor("mb10b_cd")
    pre = ESCD + "\n" + FMTNUM + "\n" + RTOTALS
    h = _node_dades(pre, "rTotals", es)
    oks = [e for e in es if e["status"] == "ok" and e["eps_totals"]]
    assert "<h3>ε total per energia</h3>" in h and "<svg" in h
    assert h.count("<polyline") == len(oks)                      # una línia per font, cap calcul nou
    for e in oks:
        assert e["retol"] in h                                   # la llegenda, amb el nom de neudet
    assert 'stroke-dasharray="6 4"' in h                         # el Geant4, de traç discontínu
    assert "<th>eps_mitja</th><th>planor_f</th>" in h
    assert _node_dades(pre, "rTotals", [{"status": "error de lectura", "eps_totals": []}]) == ""


@NODE
def test_s11_c_una_columna_per_motor_contra_el_geant4_valors_reals():
    _, es = _per_motor("mb10b_cd")
    r = _node_dades(ESCD + "\n" + FMTNUM + "\n" + RG4VAL, "rG4Valor", es)
    assert r["avisos"] == []                                     # un sol motor amb files: cap divergència
    h = r["html"]
    assert "<h3>Motor contra Geant4, valor a valor</h3>" in h
    b1 = _ent(es, "S1 · B1")
    assert h.count("<tr>") - 1 == len(b1["g4_comparacio"]) == 110
    assert "<th>S1 · B1 ε ± σ</th><th>S1 · B1/G4 − 1</th><th>estat</th>" in h
    dins = sum(1 for f in b1["g4_comparacio"] if f["concloent"] and f["dins_tol"])
    fora = sum(1 for f in b1["g4_comparacio"] if f["concloent"] and not f["dins_tol"])
    assert h.count('<span class="tag t-ok">dins</span>') == dins == 102
    assert h.count('<span class="tag t-no">fora</span>') == fora == 8
    assert "-0.90 %" in h                                        # biaix de la primera fila, fmtPct del `biaix`


@NODE
def test_s11_c_no_concloent_i_geant4_divergent_queda_escrit():
    pre = ESCD + "\n" + FMTNUM + "\n" + RG4VAL

    def fil(p, tub, E, g4, conc=True, dins=True):
        return {"path": p, "tub": tub, "E": E, "eps_motor": 0.035, "sig_motor": 0.0005,
                "eps_g4": g4, "sig_g4": 0.0006, "biaix": 0.01, "err_rel": 0.02,
                "concloent": conc, "dins_tol": dins}
    r = _node_dades(pre, "rG4Valor", [
        {"status": "ok", "retol": "S1 · B1", "path": "/x/B1",
         "g4_comparacio": [fil("/x/B1", 0, 1.0, 0.035), fil("/x/B1", 0, 2.0, 0.03, conc=False)]},
        {"status": "ok", "retol": "S1 · salts", "path": "/x/salts",
         "g4_comparacio": [fil("/x/salts", 0, 1.0, 0.036), fil("/x/salts", 0, 2.0, 0.03, conc=False)]}])
    assert any("no coincideixen en el Geant4 del tub 1 a 1 MeV" in a for a in r["avisos"])
    assert '<td class="t-no">divergent</td>' in r["html"]        # un G4 en què no coincideixen, no pintat com si
    assert ">G4 " in r["html"]                                   # cada columna porta el seu G4 escrit
    assert '<span class="tag t-nt">NO CONCLOENT</span>' in r["html"]
    _, eo = _per_motor("mb10b_cd_openmc")                        # sens files: bloc buit, no una taula a zeros
    assert _node_dades(pre, "rG4Valor", eo) == {"avisos": [], "html": ""}


def test_s8_el_full_té_adreça_pròpia_i_sobre_en_pestanya_nova():
    assert "const en = e.target.closest('a[data-full]');" in INDEX
    assert "if(en){ e.preventDefault(); nzObrirPestanya(KC.id, en.dataset.full); return; }" in INDEX
    assert "if(tr){ nzObrirPestanya(KC.id, tr.dataset.h); return; }" in INDEX    # també des de la taula completa
    assert "if(s[1] === 'full' && s[2]) return nzFull(s[0], s[2]);" in INDEX     # ruta #neudet/<camp>/full/<hash>
    assert "if(camp && d.hash) return 'neudet/' + camp + '/full/' + d.hash;" in INDEX  # la pàgina reescriu la seva adreça
    assert ("window.open(location.pathname + '#neudet/' + encodeURIComponent(camp) + '/full/'"
            " + encodeURIComponent(hash), '_blank')") in INDEX
