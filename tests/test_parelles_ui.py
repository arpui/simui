"""test_parelles_ui.py — MB01-PARELLES (coordinador 2026-11-28).

Què es fixa
-----------
La UI dibuixa un PARET (cada forat = 2 tubs coaxials invertits) així:

- Un punt per FORAT (mai un punt per tub) als dos branches d'anells (inv i no-inv):
  `parella: true` i la primera `sep_parella_cm` de l'anell.
- `cTubsPunt` expandix cada punt parell en DOS tubs (sentit ±1): z = ±zc, zc = sep/2 + Lactive/2 − dZav
  (`z_centre_parella` de neudet), zlo/zhi i za emmirallats.
- `cEscena`, `cVistaDims` i `cBlocLateral` consumeixen `cTubsPunt` (els dos tubs del parell).
- L'exemple s'valida per TUB (2 per forat); els rebutjats es comproven per forat.
- La llegenda diu «forat N · parella · sep X cm».
- Els comptadors (n, inventari, fixats, k) compten FORATS; amb parella, l'inventari mostra
  «N forats (2N tubs)».
- `_mides_tub` consumeix `L_total_cm` del catàleg (longitud física total, connectors inclòs).

Si neudet es mou, el test se n'assabenta (l'aspecte funcional el marca el catàleg real).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

INDEX = (ROOT / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")
CAMPANYA = (ROOT / "src" / "simui" / "campanya_form.py").read_text(encoding="utf-8")


# ── el punt és un FORAT, mai un tub ─────────────────────────────────────────────

def test_els_punts_es_creen_per_forat_amb_parella():
    """Als dos branches d'anells (inventari i una combinació), un anell amb `parella` crea un punt per FORAT."""
    assert INDEX.count("if(a.parella){ punt.parella = true;") >= 2  # inv + no-inv
    assert "punt.sep = sp.length ? Number(sp[0]) : undefined;" in INDEX


def test_cTubsPunt_expandeix_el_parell_en_dos_tubs():
    """Un parell es dibuixa com dos tubs (sentit ±1), amb z = ±zc i el parell emmirallat."""
    assert "const cTubsPunt = p => {" in INDEX
    assert "if(!p.parella) return [{z, sentit: 1," in INDEX
    assert "const zc = sep / 2 + mm.lactive_cm / 2 - mm.dZav_cm;" in INDEX
    assert "{z: -zc, sentit: -1," in INDEX
    assert "zlo: -q.zhi, zhi: -q.zlo, za: -q.za" in INDEX


# ── les vistes consumeixen cTubsPunt ──────────────────────────────────────────────

def test_les_vistes_consumixen_cTubsPunt():
    assert "tubs: V.punts.flatMap(p => cTubsPunt(p).map(t =>" in INDEX
    assert "const ts = cTubsPunt(p), q = cDimTub(p.tipus);" in INDEX                      # cVistaDims
    assert "return cTubsPunt(p).map(t => {" in INDEX                                     # cBlocLateral
    assert "const perTub = tubs.flatMap(p => cTubsPunt(p).map(t =>" in INDEX              # cBlocSvg


def test_lexSig_es_valida_per_tub_i_el_rebutjat_per_forat():
    """L'exemple s'envia per TUB (2 per forat); els rebutjats es comproven per FORAT (qualsevol tub rebutjat)."""
    assert "const perTub = tubs.flatMap(" in INDEX
    assert "ixs.includes(x)" in INDEX and "res.rebutjats.some(x =>" in INDEX


def test_la_llegenda_diu_el_forat_i_la_separacio():
    assert "forat ${p.num} · parella · sep ${p.sep} cm" in INDEX


# ── els comptadors compten FORATS ────────────────────────────────────────────────

def test_l_inventari_mostra_forats_i_tubs_amb_parella():
    """Amb parella, l'inventari mostra 'N forats (2N tubs)' als tres llocs dels comptadors."""
    assert "forats (${2 * cInvTotal(t.inventari)} tubs)" in INDEX
    assert "forats (${2 * cInvTotal(inv)} tubs)" in INDEX
    assert "quantitat (forats)" in INDEX
    assert "nombre de forats" in INDEX
    assert "${a.parella ? 'forats' : 'tubs'} fixats" in INDEX


def test_n_total_i_n_els_diuen_forats_amb_parella():
    assert "n (${a.parella ? 'forats' : 'tubs'}; 0 = anell buit)" in INDEX
    assert "la suma de ${parella ? 'forats' : 'tubs'} de tots els anells" in INDEX


# ── _mides_tub: la longitud física total ────────────────────────────────────────

def test_mides_tub_consumeix_L_total_cm():
    """`_mides_tub` llegeix `L_total_cm` del catàleg (longitud física total, connectors inclòs)."""
    assert 'l_total = e.get("L_total_cm")' in CAMPANYA
    assert "llargada_total_cm = l_total" in CAMPANYA
    assert "z_min_cm" in CAMPANYA and "z_max_cm" in CAMPANYA


def test_mides_tub_llega_la_longitud_fisica_total_del_cataleg():
    """Funcional (neudet present): lnd_252399 declara L_total_cm → el total són 37.62 cm (no 40.9)."""
    from simphy.mcgen import detector_config as DC

    try:
        entries = DC.read_catalog()
    except Exception:
        import pytest
        pytest.skip("el catàleg de tubs no es llegeix")
    e = next((x for x in entries if x.get("nom") == "lnd_252399"), None)
    if e is None:
        import pytest
        pytest.skip("el tipus lnd_252399 no hi és al catàleg")
    from simphy.mcgen import design as DES
    try:
        DES._neudet()
    except DES.DesignError:
        import pytest
        pytest.skip("neudet no és present")
    from simui import campanya_form as CF  # noqa: E402

    m = CF._mides_tub(e)
    assert m is not None
    assert m["llargada_total_cm"] == 37.62           # el físic, no l'envolupant de DIMS (40.9)
    assert m["z_min_cm"] == -17.22                    # dZpv − (Lpassive/2 + ZwallD)
    assert m["z_max_cm"] == 20.40                     # -17.22 + 37.62
    assert m["lactive_cm"] == 30.0 and m["dZav_cm"] == 0.0
    assert m["radi_gas_cm"] is not None and m["radi_gas_cm"] > 0


# ── sentit a /api/campanya/exemple i cBlocSvg ───────────────────────────────────

def test_cBlocSvg_passa_sentit_a_perTub_exSig_i_cExempleValida():
    """cBlocSvg envia `sentit` (per defecte 1) a perTub, V.exSig i cExempleValida."""
    bloc_svg = INDEX.split("function cBlocSvg(")[1].split("function cExempleHtml")[0] if "function cExempleHtml" in INDEX.split("function cBlocSvg(")[1] else INDEX.split("function cBlocSvg(")[1].split("// ── Visor 3D")[0]
    assert "sentit: t.sentit ?? 1" in bloc_svg
    assert "[t.x, t.y, t.z, t.eix || 'z', t.tipus, t.sentit]" in bloc_svg
    assert "cExempleValida(V.exSig, perTub.map(t => ({x: t.x, y: t.y, z: t.z || 0, eix: t.eix || 'z', tipus: t.tipus, sentit: t.sentit})))" in bloc_svg


def test_exemple_valida_parella_amb_sentit_a_mb_01():
    """Funcional (neudet present): amb sentit ±1 una parella coaxial lnd_252399 a mb_01 és vàlida; sense sentit es rebutja."""
    import math
    import os
    import pytest
    from simphy.mcgen import design as DES

    try:
        DES._neudet()
    except DES.DesignError:
        pytest.skip("neudet no és present")

    mb_01_yaml = Path(os.environ.get("NEUDET_ROOT", Path.home() / "projects" / "neudet")) / "disseny" / "campanyes" / "mb_01" / "campanya.yaml"
    if not mb_01_yaml.is_file():
        pytest.skip("mb_01/campanya.yaml no hi és a NEUDET_ROOT")

    from neudet.disseny.candidat import z_centre_parella
    from simui import campanya_check as CC

    yaml_text = mb_01_yaml.read_text(encoding="utf-8")
    zc = z_centre_parella("lnd_252399", 4.44)

    # Una parella coaxial a (12, 0) amb sentit +1 i -1
    r_parella = CC.exemple(
        yaml_text,
        [
            {"x": 12.0, "y": 0.0, "z": zc, "eix": "z", "tipus": "lnd_252399", "sentit": 1},
            {"x": 12.0, "y": 0.0, "z": -zc, "eix": "z", "tipus": "lnd_252399", "sentit": -1},
        ],
    )
    assert r_parella["violacions"] == []
    assert r_parella["rebutjats"] == []

    # Un anell complet de 8 forats (16 tubs coaxials invertits a r=12, sep=4.44)
    tubs_anell = []
    for k in range(8):
        ang = 2.0 * math.pi * k / 8.0
        x = 12.0 * math.cos(ang)
        y = 12.0 * math.sin(ang)
        tubs_anell.append({"x": x, "y": y, "z": zc, "eix": "z", "tipus": "lnd_252399", "sentit": 1})
        tubs_anell.append({"x": x, "y": y, "z": -zc, "eix": "z", "tipus": "lnd_252399", "sentit": -1})
    r_anell = CC.exemple(yaml_text, tubs_anell)
    assert r_anell["violacions"] == []
    assert r_anell["rebutjats"] == []

    # Control negatiu: mateixos 2 tubs sense sentit / amb sentit=1 → fals rebot
    for tubs_sense in (
        [
            {"x": 12.0, "y": 0.0, "z": zc, "eix": "z", "tipus": "lnd_252399"},
            {"x": 12.0, "y": 0.0, "z": -zc, "eix": "z", "tipus": "lnd_252399"},
        ],
        [
            {"x": 12.0, "y": 0.0, "z": zc, "eix": "z", "tipus": "lnd_252399", "sentit": 1},
            {"x": 12.0, "y": 0.0, "z": -zc, "eix": "z", "tipus": "lnd_252399", "sentit": 1},
        ],
    ):
        r_ctrl = CC.exemple(yaml_text, tubs_sense)
        assert r_ctrl["violacions"]
        assert r_ctrl["rebutjats"] == [1, 2]

    # Control d'entrada invàlida: sentit=0 o sentit=True → ValueError
    with pytest.raises(ValueError):
        CC.exemple(yaml_text, [{"x": 12.0, "y": 0.0, "z": zc, "eix": "z", "tipus": "lnd_252399", "sentit": 0}])
    with pytest.raises(ValueError):
        CC.exemple(yaml_text, [{"x": 12.0, "y": 0.0, "z": zc, "eix": "z", "tipus": "lnd_252399", "sentit": True}])
