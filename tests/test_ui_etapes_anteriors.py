"""test_ui_etapes_anteriors.py — UI-X06: les etapes que neudet ha apartat es continuen llistant, retolades.

Què es fixa
-----------
- Mana el camp **`etapes[].anterior`** del `campanya_ui.json` de neudet, **mai el nom de la carpeta**
  (la regex `APARTAT` és d'ells, a `confirmacio.py`; la UI no la reimplementa: la pàgina no conté
  cap literal `_anterior_` ni `_aturada_`).
- La vista passa `anterior`, `aturada` i `intents_anteriors` tal com venen; si el camp no hi és,
  `anterior` és `null` (= no es pot saber), mai `false` per defecte.
- Tria d'Albert (2026-11-12, «Marca-les»): les etapes apartades **no s'amaguen**.
- Divergència escrita: el manifest de `c0b_2t0611` posa `citable: true` a nivell d'etapa en les dues
  apartades (`S1_anterior_2026-11-08`, amb `aturada.citable: false`, i `S1_anterior_2026-11-08_2`, amb
  `aturada: null`). La vista no reescriu el que diu neudet; és la pàgina qui no les marca mai com a
  citables. Si neudet corregeix el manifest, la prova de la divergència ho dirà.
- El motiu que es llegeix sota l'etapa apartada és el text de neudet (`aturada.text`), no un de propi.
Sense neudet (o sense node) els tests es salten.
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

from simphy.mcgen import design as D  # noqa: E402
from simui import campanya_vista as V  # noqa: E402

INDEX = (ROOT / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")
CAMP = "c0b_2t0611"                       # l'única campanya real amb etapes apartades
APARTADES = {"S1_anterior_2026-11-08", "S1_anterior_2026-11-08_2"}
RETOLADOR = "intent anterior (no citable)"

# `kEtapa` crida els altres retoladors d'una etapa; aquí només ens interessa la capçalera i els motius.
BUIDES = ("const escD = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');"
          "const KC = {v: {pareto: {eixos: null}, diagnostic: null}}, buits = () => '';"
          "const kPla = buits, kResposta = buits, kTaula = buits, kFormMetr = buits, kFormEtapaHtml = buits,"
          " kReavHtml = buits, kPareto = buits, kGaleria = buits, diagTxt = () => '';"
          "function kEtapa(e){" + INDEX.split("function kEtapa(e){")[1].split("// El relat de l'etapa")[0])


def _pinta(etapes):
    """Els HTML que la pàgina produïria per a aquestes etapes, en ordre, executant-ne el `kEtapa` amb node."""
    r = subprocess.run(["node", "-e", BUIDES + "console.log(JSON.stringify(%s.map(kEtapa)));" % json.dumps(etapes)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return dict(zip([e["nom"] for e in etapes], json.loads(r.stdout)))


def _per_nom(llista):
    return {e["nom"]: e for e in llista}


@pytest.fixture(scope="module")
def dades():
    """(manifest de neudet tal qual, vista de la UI) per a `c0b_2t0611`."""
    try:
        d = V.dir_de(CAMP)
    except (V.CampanyaError, D.DesignError) as e:
        pytest.skip(f"neudet no és present o no té la campanya: {e}")
    man = json.loads((d / "campanya_ui.json").read_text(encoding="utf-8"))
    return man, V.vista(d)


def test_el_manifest_de_neudet_marca_les_apartades_per_camp(dades):
    """La premissa del costat de neudet: `anterior: true` a les dues apartades, `false` a les altres."""
    man, _ = dades
    et = _per_nom(man["etapes"])
    assert {n for n, e in et.items() if e.get("anterior") is True} == APARTADES
    assert et["S1"].get("anterior") is False and et["S1_g4"].get("anterior") is False
    assert sorted(et["S1"]["intents_anteriors"]) == sorted(APARTADES)


def test_la_vista_passa_el_camp_sense_inventar_res(dades):
    """`anterior`, `aturada` i `intents_anteriors` arriben iguals que al manifest; cap etapa amagada."""
    man, v = dades
    mv, mne = _per_nom(v["etapes"]), _per_nom(man["etapes"])
    assert set(mv) == set(mne)                                        # Albert: marcar-les, no amagar-les
    for nom, e in mv.items():
        assert e["anterior"] is mne[nom].get("anterior")
        assert e["intents_anteriors"] == mne[nom].get("intents_anteriors")
        assert e["aturada"] == mne[nom].get("aturada")
    assert mv["S1_anterior_2026-11-08_2"]["aturada"] is None          # no n'hi havia: no se'n inventa cap


def test_la_divergencia_de_citable_queda_escrita(dades):
    """neudet diu `citable: true` per a una etapa apartada; la vista ho manté (és la dada d'ells) i la pàgina
    és qui no la pinta com a citable. Si neudet ho corregeix, aquesta prova es torna vermella i ho diu."""
    man, v = dades
    mv, mne = _per_nom(v["etapes"]), _per_nom(man["etapes"])
    for nom in APARTADES:
        assert (mne[nom]["citable"], mne[nom]["anterior"]) == (True, True)
        assert mv[nom]["citable"] is True
    assert mne["S1_anterior_2026-11-08"]["aturada"]["citable"] is False


def test_la_pagina_no_dedueix_res_del_nom_de_la_carpeta():
    for pat in ("_anterior_", "_aturada_"):
        assert pat not in INDEX, f"la pàgina conté {pat}: hauria de mirar el camp `etapes[].anterior`"
    assert "e.anterior === true" in INDEX


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node")
def test_kEtapa_marca_sempre_les_apartades_i_mai_com_a_citables(dades):
    """Amb les etapes reals de la campanya: tota `anterior: true` surt amb el retolador, sense etiqueta
    verda ni la de «no citable» a seces, i amb el motiu de neudet; les altres es pinten com sempre."""
    man, v = dades
    h = _pinta(v["etapes"])
    assert set(h) == APARTADES | {"S1", "S1_g4"}
    for nom in APARTADES:
        cap = h[nom].split("</header>")[0]
        assert RETOLADOR in cap, f"{nom} surt sense el retolador"
        for etiqueta in ('class="tag t-ok">citable<', 'class="tag t-no">no citable<'):
            assert etiqueta not in cap, f"{nom} surt marcada amb {etiqueta}"
        assert "null" not in cap and "undefined" not in cap
    assert RETOLADOR not in h["S1"] and RETOLADOR not in h["S1_g4"]
    assert 'class="tag t-ok">citable<' in h["S1"]                     # l'etapa bona continua citable
    assert "2 intents anteriors apartats" in h["S1"]
    assert _per_nom(man["etapes"])["S1_anterior_2026-11-08"]["aturada"]["text"] in h["S1_anterior_2026-11-08"]


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node")
def test_sense_el_camp_no_es_marca_res():
    """Un neudet vell o una campanya sense manifest: una etapa amb nom d'apartada es pinta com qualsevol
    altra. La UI no endevina; si volgués endevinar, aquesta prova i la de l'absència de `_anterior_` ho veuen."""
    base = {"motor": "xarxa B1", "citable": True, "motius": [], "figures": [],
            "n_candidats": 3, "n_csv": 3, "columnes": [], "candidats": [], "energies_MeV": None}
    h = _pinta([dict(base, nom="S1_anterior_2026-11-08"), dict(base, nom="S1", anterior=False)])
    assert set(h) == {"S1_anterior_2026-11-08", "S1"}
    for x in h.values():
        assert RETOLADOR not in x and 'class="tag t-ok">citable<' in x
