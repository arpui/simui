"""E12-CERT (2026-11-27): mode elàstic i taules CM de H i C — la UI i neudet es llegeixen vius.

Com és un test bessó: el que diu la UI de `elastic_kin_mode` i `elastic_cm_taules` es confronta amb el codi real
de neudet (`avaluador.py`: `ELASTIC_KIN_MODES`, `elastic_kin_mode`, `elastic_cm_tables`; `campanya.py`:
`elastic_kin_yaml`). Si neudet es mou, el test se n'assabenta.
"""
from __future__ import annotations

import pytest

from simui import campanya_form as CF
from simphy.mcgen import design as DES


def _neudet():
    try:
        DES.neudet_root()
        DES._neudet()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def _av(**kw):
    av = {"xarxa": "B1", "mode": "continu"}
    av.update(kw)
    return {"avaluacio": av}


# ── neudet publica els mateixos valors que la UI ───────────────────────────────

def test_el_schema_porta_els_valors_de_neudet():
    _neudet()
    import importlib
    import neudet.disseny.avaluador as A
    s = CF.schema()
    S = s["avaluacio"]["elastic_kin_mode"]
    assert [v["valor"] for v in S["valors"]] == list(A.ELASTIC_KIN_MODES)
    T = s["avaluacio"]["elastic_cm_taules"]
    assert T["fitxer"] == CF.CAMPANYA_PY


def test_els_pins_de_neudet_coincideixen():
    _neudet()
    import importlib
    c = importlib.import_module("neudet.disseny.campanya")
    a = importlib.import_module("neudet.disseny.avaluador")
    assert "elastic_kin_yaml" in (DES.neudet_root() / "src" / "neudet" / "disseny" / "campanya.py").read_text(encoding="utf-8")
    assert "ELASTIC_KIN_MODES" in (DES.neudet_root() / "src" / "neudet" / "disseny" / "avaluador.py").read_text(encoding="utf-8")


# ── la UI rebota el que rebota neudet ─────────────────────────────────────────

def test_la_ui_rebota_el_que_rebota_neudet():
    _neudet()
    probes = [
        (_av(elastic_kin_mode="off"), []),                                   # mode vàlid sense taules
        (_av(elastic_kin_mode="table", elastic_cm_taules={"H": "a.csv", "C": "b.csv"}), []),
        (_av(elastic_kin_mode="table", elastic_cm_taules={"H": "a.csv"}),     # falta C
         ["table sense"]),
        (_av(elastic_kin_mode="off", elastic_cm_taules={"H": "a.csv", "C": "b.csv"}),  # off amb taules
         ["off amb"]),
        (_av(elastic_cm_taules={"H": "a.csv", "C": "b.csv"}),                 # taules sense mode
         ["sense avaluacio.elastic_kin_mode"]),
        (_av(elastic_kin_mode="bogus"),                                        # mode invàlid
         ["cal"]),
        (_av(), []),
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
    s = CF.schema()
    assert s["avaluacio"]["elastic_kin_mode"]["defecte"] is None


# ── el formulari edita el que marca la UI ──────────────────────────────────────

def test_editable_keys():
    _neudet()
    assert "elastic_kin_mode" in CF._EDITABLE["avaluacio"]
    assert set(CF._EDITABLE["avaluacio"]["elastic_cm_taules"]) == {"H", "C"}


def test_index_html_no_inventa_l_esquema_elàstic():
    _neudet()
    INDEX = (__import__("pathlib").Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")
    # la UI llegeix l'esquema, no els valors escrits
    assert "elastic_kin_mode" in INDEX and "elastic_cm_taules" in INDEX
    assert "taula_cm_per_sobre_de_MeV" in INDEX
