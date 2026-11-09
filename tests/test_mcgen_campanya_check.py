"""UI-DIB2: els tubs d'un dibuix d'exemple els jutja `candidat.violacions` de neudet (`campanya_check.exemple`)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from simui import campanya_check as CC



# ── UI-DIB2: l'exemple del dibuix passa per `violacions` de neudet ─────────────────────────────────────────

def _yaml_c0_2t0611():
    from simui import campanya_form as CF
    d = Path(os.environ.get("NEUDET_ROOT", Path.home() / "projects" / "neudet")) / "disseny" / "campanyes" / "c0_2t0611"
    if not (d / "campanya.yaml").is_file():
        pytest.skip("no hi ha c0_2t0611 a NEUDET")
    return CF.to_yaml(CF.de_fitxer(d / "campanya.yaml"))


def test_l_exemple_dibuixat_el_jutja_neudet_amb_els_numeros_a_1():
    y = _yaml_c0_2t0611()
    r = CC.exemple(y, [{"x": 0, "y": 0, "z": 0, "eix": "z", "tipus": "lnd_2523"}])
    assert r["rebutjats"] == [] and not [v for v in r["violacions"] if v["tubs"]]       # (neudet pot dir coses de la font: no són d'un tub)
    r = CC.exemple(y, [{"x": 0, "y": 0, "z": 0, "eix": "z", "tipus": "lnd_2523"}, {"x": 0.5, "y": 0, "z": 0, "eix": "z", "tipus": "lnd_2523"}])
    assert r["rebutjats"] == [1, 2] and any("tubs 1 i 2 se solapen" in v["motiu"] for v in r["violacions"])


def test_un_tub_mes_llarg_que_el_bloc_es_rebutja_amb_el_motiu_de_neudet():
    """El cas de la confusió: l'envolupant del catàleg (68 cm el LND-252285) en un bloc de 50 cm d'eix y no hi cap."""
    r = CC.exemple(_yaml_c0_2t0611(), [{"x": 0, "y": 0, "z": 0, "eix": "y", "tipus": "lnd_252285"}])
    assert r["rebutjats"] == [1] and any("més llarg que el bloc" in v["motiu"] for v in r["violacions"])
