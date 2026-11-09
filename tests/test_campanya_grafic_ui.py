"""REAVALUA-UI pas 3: el gràfic ε̄–cv de l'etapa. La part JS (escales, punts, c i restriccions movibles) s'executa amb node sobre el que torna
`reselecciona` de veritat; el gràfic no calcula res: frontera, robustesa, guanyadors i verificat/nou són els que dona neudet."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from simui import campanya_reselecciona as R
from simphy.mcgen import design as DES

INDEX = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="cal node")


def _js(expr: str, dades: dict) -> object:
    a = INDEX.index("const kGW = ")
    b = INDEX.index("function kReavGrafHtml")
    kd = INDEX[INDEX.index("function kReavDescr"):INDEX.index("function kReavRes")]
    js = ("const escD = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');"
          "const kRvNum = x => x == null ? '—' : (+x).toPrecision(4).replace(/\\.?0+$/, '');" + kd + INDEX[a:b] +
          "const D = " + json.dumps(dades) + "; console.log(JSON.stringify(" + expr + "));")
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)


def _r(camp="c01_8tubs_30x30x80", etapa="S0", crit=None):
    try:
        DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(str(e))
    return R.reselecciona(camp, etapa, crit)


def _crit(r):
    return {**r["criteris"]}


def test_el_grafic_pinta_un_punt_per_candidat_amb_la_frontera_i_els_guanyadors_de_neudet():
    r = _r(crit={"c": [0.15, 0.4]})
    crit = _crit(r)
    h = _js("(()=>{const E = kGEsc(D.r, D.c, D.r.punts); return kReavGraf(D.r, D.c, E) + kReavGrafPeu(D.r, D.c)})()", {"r": r, "c": crit})
    n_f = len(r["frontera"])
    assert h.count('class="kc"') == len(r["punts"]) or h.count("data-h=") == len(r["punts"])
    assert h.count("gp gw") >= len([g for g in r["guanyadors"] if not g["cap"]])                  # guanyadors marcats
    assert h.count("gp gf") >= n_f                                                                  # frontera de neudet
    assert h.count('data-rvd="c"') == 2 and "c=0.15" in h and "c=0.4" in h                          # una c movible per cada c
    assert "Criteris aplicats" in h and "ja avaluats" in h and "Arrossega" in h
    assert "null" not in h and "NaN" not in h
    for m in (r["criteris"]["sobre"], r["criteris"]["maxim"]):
        assert r["formules"][m].replace("&", "&amp;")[:20] in h.replace("&lt;", "<").replace("&gt;", ">") or r["formules"][m][:20] in h


def test_les_marques_de_verificat_nou_i_no_es_sap_vénen_del_camp_g4_i_no_s_inventen():
    r = _r()                                                                                         # c01 S0: sense S0_g4 → no es sap
    assert all(p["g4"] is None for p in r["punts"])
    h = _js("kReavGrafPunts(D.r, kGEsc(D.r, D.c, D.r.punts))", {"r": r, "c": _crit(r)})
    assert "<rect" in h and "<polygon" not in h and "<circle" not in h and "no es sap si és verificat" in h
    r["punts"][0]["g4"] = True
    r["punts"][1]["g4"] = False
    h = _js("kReavGrafPunts(D.r, kGEsc(D.r, D.c, D.r.punts))", {"r": r, "c": _crit(r)})
    assert h.count("<circle") == 1 and h.count("<polygon") == 1 and "verificat a Geant4" in h and "nou (no verificat" in h


def test_el_peu_diu_si_falten_les_sig_i_els_candidats_de_cribratge():
    r = _r()
    r["te_sig"] = False
    r["n_cribratge"] = 7
    p = _js("kReavGrafPeu(D.r, D.c)", {"r": r, "c": _crit(r)})
    assert "Falten les columnes" in p and "<code>_sig</code>" in p and "7 de cribratge" in p


def test_una_restriccio_sobre_un_eix_es_movible_i_les_altres_nomes_s_anomenen():
    r = _r(crit={"restriccions": [["eps_min", ">=", 0.055]]})
    crit = _crit(r)
    crit["restriccions"] = [[r["criteris"]["maxim"], ">=", 0.1], [r["criteris"]["sobre"], "<=", 0.4], ["eps_min", ">=", 0.05]]
    d = {"r": r, "c": crit}
    m = _js("kReavGrafMans(D.r, D.c, kGEsc(D.r, D.c, D.r.punts))", d)
    assert m.count('data-rvd="rs"') == 2 and 'data-ax="y"' in m and 'data-ax="x"' in m
    p = _js("kReavGrafPeu(D.r, D.c)", d)
    assert "eps_min &gt;= 0.05" in p or "eps_min >= 0.05" in p


def test_les_escales_son_inverses_per_arrossegar():
    r = _r()
    d = {"r": r, "c": _crit(r)}
    v = _js("(()=>{const E = kGEsc(D.r, D.c, D.r.punts); const x = D.r.punts[0][D.c.sobre], y = D.r.punts[0][D.c.maxim];"
            "return [x, kGVx(E, kGX(E, x)), y, kGVy(E, kGY(E, y))]})()", d)
    assert v[0] == pytest.approx(v[1]) and v[2] == pytest.approx(v[3])


def test_la_pagina_connecta_el_grafic_al_panell():
    for t in ('data-rvp="g"', "kReavGrafPinta", "setPointerCapture", "/api/campanya/reselecciona", "kGEsc"):
        assert t in INDEX, t


def test_el_triangle_de_nou_te_coordenades_numeriques_i_dins_del_gràfic():
    r = _r()
    for p in r["punts"]:
        p["g4"] = False
    h = _js("kReavGrafPunts(D.r, kGEsc(D.r, D.c, D.r.punts))", {"r": r, "c": _crit(r)})
    import re
    for pts in re.findall(r'points="([^"]+)"', h):
        xs = [float(v) for pr in pts.split() for v in pr.split(",")]
        assert len(xs) == 6 and all(0 <= v <= 600 for v in xs), pts
