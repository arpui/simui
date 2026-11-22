"""test_a_punt_ui.py — A-PUNT (encàrrec 2026-11-20, contracte v1.28 §27): el bloc `a_punt` a dalt de la pàgina.

Què es fixa
-----------
- **La UI no calcula res**: `_certificacio` passa `a_punt` del `comprova.json` tal com ve; absent ⇒ `None`
  (mai `{}`, mai `False`), i la pantalla diu «encara sense bloc» en lloc d'inventar-se un verd o un vermell.
- **El mirall node** (marcadors `A-PUNT-DEF-BEGIN/END`): verd només amb `a_punt:true`; vermell amb les frases
  de `falta` tal com venen (amb els `⛔` i els backticks de neudet, escapats per `escD`); `null` en un recurs
  es diu «no mesurada», mai «0 h»; els números surten tal com neudet els escriu (`23.1`, no `23.10`).
- **El que la UI dona per fet del codi de neudet** (les seves línies reals, que el test segueix si es mouen):
  `a_punt = not falta and not atura` i, amb `atura` sense `falta`, hi afegeixen una frase genèrica
  ⇒ el vermell mai és buit; el bloc l'escriuen als dos camins de sortida del `comprova`; `a_punt` és sempre
  un booleà, per això a la UI un `null` només pot voler dir «bloc absent».
Sense neudet, els pins de línies es salten.
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

from simui import campanya_form as CF  # noqa: E402
from simui import campanya_vista as V  # noqa: E402

SRC = ROOT / "src" / "simui"
INDEX = (SRC / "static" / "index.html").read_text(encoding="utf-8")
COMPROVA = "comprova_campanya.py"      # scripts/disseny/


def _neudet():
    try:
        return V.neudet_root()
    except (V.CampanyaError, CF.DES.DesignError) as e:
        pytest.skip(f"neudet no és present: {e}")


BLOC = {
    "a_punt": True,
    "falta": [],
    "avisos": ["L'etapa S2 es pot estalviar: la xarxa ja ha corregut amb aquests paràmetres."],
    "recursos_estimats": {"gpu_h": 12.5, "cpu_h": 23.1, "gb": 2.24},
}
BLOC_NO = {
    "a_punt": False,
    "falta": ["⛔ Falta domini.bloc.mides_cm",
              "L'etapa S1 no té cap pregunta: mira `<a>dossier/cerques.yaml</a>`"],
    "avisos": [],
    "recursos_estimats": {"gpu_h": None, "cpu_h": None, "gb": None},
}


# ── el passava de darrere ───────────────────────────────────────────────────

def test_certificacio_passa_el_bloc_exactament_com_ve(tmp_path):
    (tmp_path / "comprova.json").write_text(json.dumps({"atura": False, "a_punt": BLOC}), encoding="utf-8")
    assert V._certificacio(tmp_path, "comprova.json")["a_punt"] == BLOC


def test_certificacio_sense_bloc_dona_None_i_mai_un_buit_fals(tmp_path):
    (tmp_path / "comprova.json").write_text(json.dumps({"atura": False}), encoding="utf-8")
    a = V._certificacio(tmp_path, "comprova.json")["a_punt"]
    assert a is None                      # absent ≠ buit: la UI ho distingeix i ho diu
    # sense comprova.json: el dic és `disponible:false` i `kAPunt` (mirall amunt) ho pinta igual de «sense bloc»
    assert V._certificacio(tmp_path, None)["disponible"] is False


# ── el tros pur de la pantalla, corregut amb node ───────────────────────────

@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar les funcions pures de la UI")
def test_kAPunt_es_pinta_com_cal_sobre_blocs_de_veritat():
    escD = next(l for l in INDEX.splitlines() if l.startswith("const escD"))   # la real, no una còpia
    js = (INDEX.split("// A-PUNT-DEF-BEGIN")[1].split("\n", 1)[1].split("// A-PUNT-DEF-END")[0] +
          "\n" + escD +
          "\nconst SI = {disponible: true, a_punt: " + json.dumps(BLOC) + "};"
          "\nconst NO = {disponible: true, a_punt: " + json.dumps(BLOC_NO) + "};"
          "\nconst SENSE = {disponible: true, a_punt: null};"
          "\nconst CAP = {disponible: false, motiu: 'no hi ha comprova.json a la campanya'};"
          "\nconsole.log(JSON.stringify([kAPunt(SI), kAPunt(NO), kAPunt(SENSE), kAPunt(CAP)]));")
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    verd, vermell, sense, cap = json.loads(r.stdout)

    assert 'data-a-punt="si"' in verd and '<b>A punt per córrer</b>' in verd
    assert "GPU 12.5 h · CPU 23.1 h · disc 2.24 GB" in verd     # els números de neudet, tal com (mai «23.10»)
    assert BLOC["avisos"][0] in verd and '<details' in verd      # avisos i recursos, plegats i plegats a sota

    assert 'data-a-punt="no"' in vermell and "<b>Falta:</b>" in vermell
    assert "⛔ Falta domini.bloc.mides_cm" in vermell            # les frases de neudet, literalment
    assert "&lt;a&gt;dossier/cerques.yaml&lt;/a&gt;" in vermell  # però escapades: no hi injegtem HTML
    assert "no mesurada" in vermell and "0 h" not in vermell and "0 GB" not in vermell
    assert "Cap avís de neudet." in vermell

    for s in (sense, cap):                                        # bloc absent o sense fitxer: mai verd ni vermell
        assert 'data-a-punt="sense"' in s and "encara sense bloc" in s
        assert 'data-a-punt="si"' not in s and 'data-a-punt="no"' not in s
        assert "0 h" not in s and "no mesurada" not in s          # sense bloc no hi ha recursos a dir


def test_la_pantina_crida_kAPunt_amb_la_certificacio():
    assert "out.push(kAPunt(v.certificacio));" in INDEX


# ── el que la UI dona per fet del codi de neudet (línies reals) ─────────────

def _linia(linia, token):
    _neudet()
    return CF._linia(COMPROVA, linia, token, dir_=CF._SCRIPTS)


def test_neudet_deriva_a_punt_del_mateix_veredicte_i_maig_deixa_el_vermell_buit():
    assert "a_punt = not falta and not informe.get(\"atura\")" in _linia(78, "a_punt = not falta")
    gen = _linia(80, "motiu d'aturada al veredicte")              # atura sense falta ⇒ frase, mai llista buida
    assert "falta.append" in gen


def test_neudet_escriu_el_bloc_als_dos_camins_de_sortida():
    assert 'inf["a_punt"] = _bloc_a_punt(inf)' in _linia(97, 'inf["a_punt"] = _bloc_a_punt')       # yaml invàlid
    assert 'informe["a_punt"] = _bloc_a_punt(informe, C.cfg)' in _linia(292, 'informe["a_punt"] = _bloc_a_punt')


def test_neudet_torna_a_punt_com_a_boole_i_la_clau_null_mes_vol_dir_absent():
    ret = _linia(81, "recursos_estimats=recursos")
    assert "a_punt=bool(a_punt)" in ret                           # per això a la UI null ⇒ bloc absent
    assert "recursos = dict(gpu_h=_suma(\"gpu_h\"), cpu_h=_suma(\"cpu_h\"), gb=_suma(\"disc_gb\"))" in \
        _linia(74, "recursos = dict(gpu_h=_suma")                 # les mateixes tres claus que llegeix la UI
