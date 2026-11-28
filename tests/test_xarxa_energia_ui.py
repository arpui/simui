"""test_xarxa_energia_ui.py — XARXA-PER-ENERGIA (coordinador 2026-11-28).

Què es fixa
-----------
La UI de `avaluacio.xarxa_per_energia` es confronta amb el codi real de neudet
(`campanya.py`: `xarxa_per_energia_cfg`; `xarxa_energia.py`: `REGLA`, `zona`, `CLAUS_BLOC`).
Si neudet es mou, el test se n'assabenta.

- El schema publica la regla de neudet (`REGLA`) i la línia de `campanya.py` on neudet la llegeix.
- La UI rebota el que rebota neudet (estructura, exclusivitat, llindar, braços).
- El formulari edita el que marca `_EDITABLE`.
- L'INDEX publica la regla i el bloc editable del braç.
"""
from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

import pytest
from simphy.mcgen import design as DES

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simui import campanya_form as CF  # noqa: E402

INDEX = (ROOT / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")


def _neudet():
    try:
        DES.neudet_root()
        DES._neudet()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def _xarxa(**kw):
    x = {"llindar_MeV": 5.0,
         "baix": {"ckpts": {"PE": "BASELINE"}, "elastic_kin_mode": "off"},
         "alt": {"ckpts": {"PE": "BASELINE"}, "elastic_kin_mode": "off"}}
    x.update(kw)
    return {"avaluacio": {"xarxa": "B1", "mode": "continu", "xarxa_per_energia": x}}


# ── el schema llegeix el que neudet publica ───────────────────────────────────

def test_el_schema_porta_la_regla_de_neudet():
    _neudet()
    X = import_module("neudet.disseny.xarxa_energia")
    s = CF.schema()
    R = s["avaluacio"]["xarxa_per_energia"]
    assert R["regla"] == X.REGLA
    assert R["fitxer"] == CF.CAMPANYA_PY


def test_els_pins_de_neudet_coincideixen():
    _neudet()
    neudet_root = DES.neudet_root()
    campanya = (neudet_root / "src" / "neudet" / "disseny" / "campanya.py").read_text(encoding="utf-8")
    xarxa = (neudet_root / "src" / "neudet" / "disseny" / "xarxa_energia.py").read_text(encoding="utf-8")
    assert "xarxa_per_energia_cfg" in campanya
    assert "REGLA" in xarxa
    X = import_module("neudet.disseny.xarxa_energia")
    assert X.REGLA == "E_font ≤ llindar_MeV → `baix`; E_font > llindar_MeV → `alt`"
    assert X.CLAUS_BLOC == ("ckpts", "elastic_kin_mode", "elastic_cm_taules")


# ── la UI rebota el que rebota neudet ─────────────────────────────────────────

def test_la_ui_rebota_el_que_rebota_neudet():
    _neudet()
    probes = [
        (_xarxa(), []),
        (_xarxa(baix={"ckpts": {"PE": "BASELINE"}, "elastic_kin_mode": "bogus"}), ["cal"]),
        (_xarxa(llindar_MeV=-1.0), ["cal > 0"]),
        (_xarxa(llindar_MeV="x"), ["cal un nombre"]),
        (_xarxa(baix={"elastic_kin_mode": "off"}), ["ckpts"]),
        (_xarxa(baix={"ckpts": {"PE": "BASELINE"}}), ["cal declarar-lo"]),
        (_xarxa(alt={"ckpts": {"PE": "BASELINE"}, "elastic_kin_mode": "off",
                              "elastic_cm_taules": {"H": "a.csv", "C": "b.csv"}}), ["off amb"]),
        (_xarxa(alt={"ckpts": {"PE": "BASELINE"}, "elastic_kin_mode": "table"}), ["table sense"]),
        ({"avaluacio": {"xarxa": "B1", "mode": "continu", "ckpts": {"PE": "BASELINE"},
                                                               "xarxa_per_energia": _xarxa()["avaluacio"]["xarxa_per_energia"]}},
         ["ckpts global"]),
    ]
    for f, msgs in probes:
        e = CF._errors_avaluacio(f)
        if msgs:
            assert any(m in x for x in e for m in msgs), (f, e)
        else:
            assert e == [], (f, e)


def test_absent_no_inventa_cap_fila():
    _neudet()
    assert CF._errors_avaluacio({"avaluacio": {"xarxa": "B1", "mode": "continu"}}) == []


# ── el formulari edita el que marca la UI ──────────────────────────────────────

def test_editable_keys():
    _neudet()
    assert "xarxa_per_energia" in CF._EDITABLE["avaluacio"]
    x = CF._EDITABLE["avaluacio"]["xarxa_per_energia"]
    assert set(x) == {"llindar_MeV", "baix", "alt"}
    assert set(x["baix"]) == {"ckpts", "elastic_kin_mode", "elastic_cm_taules"}
    assert set(x["alt"]) == {"ckpts", "elastic_kin_mode", "elastic_cm_taules"}


def test_index_html_publica_la_xarxa_per_energia():
    _neudet()
    assert "cXarxaPerEnergiaHtml" in INDEX
    assert "xarxa_per_energia.llindar_MeV" in INDEX
    assert "avaluacio.xarxa_per_energia." in INDEX
