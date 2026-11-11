"""ENTRE-UI (contracte UI §17): domini.entre, humitat i temperatura; el que dona neudet es mostra tal com ve."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from simui import campanya_form as CF
from simphy.mcgen import design as DES

INDEX = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")


def _neudet():
    try:
        DES.neudet_root()
        DES._neudet()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")


def _dom(**kw):
    d = {"bloc": {"mides_cm": [30, 30, 80]}, "font": CF.font_defecte([30, 30, 80])}
    d.update(kw)
    return d


def test_entre_per_defecte_es_buit_i_no_demana_res():
    assert CF._errors_entre(_dom()) == [] and CF._errors_entre(_dom(entre="buit")) == []


def test_aire_no_porta_humitat_ni_temperatura():
    assert CF._errors_entre(_dom(entre="aire")) == []
    assert CF._errors_entre(_dom(entre="aire", humitat_relativa_pct=50))                   # només amb aire_humit


def test_aire_humit_demana_hr_i_t_dins_dels_rangs_del_contracte():
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=50, temperatura_C=20)) == []
    assert len(CF._errors_entre(_dom(entre="aire_humit"))) == 2                            # sense valor implícit
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=101, temperatura_C=20))
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=-1, temperatura_C=20))
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=50, temperatura_C=51))
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=50, temperatura_C=-41))
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=0, temperatura_C=-40)) == []
    assert CF._errors_entre(_dom(entre="aire_humit", humitat_relativa_pct=100, temperatura_C=50)) == []


def test_un_entre_desconegut_es_error():
    assert CF._errors_entre(_dom(entre="sala"))


def test_mon_mig_cm_opcional_i_positiu():
    f = {"verificacio": {"mon_mig_cm": 0}}
    assert any("mon_mig_cm" in x for x in CF._errors({**f, "domini": {}}))
    assert not any("mon_mig_cm" in x for x in CF._errors({"verificacio": {"mon_mig_cm": 110}, "domini": {}}))
    assert not any("mon_mig_cm" in x for x in CF._errors({"verificacio": {}, "domini": {}}))


def test_entre_info_diu_d_on_ve_cada_valor():
    i = CF.entre_info()
    assert set(i["valids"]) >= {"buit"} and i["font_valids"]
    assert i["humitat_relativa_pct"]["defecte"] == 50 and i["temperatura_C"]["defecte"] == 20
    assert (i["humitat_relativa_pct"]["min"], i["humitat_relativa_pct"]["max"]) == (0, 100)


def test_divergencia_neudet_contracte_en_els_rangs_i_valors():
    """Quan neudet publica ENTRE_VALIDS i el rang de T, han de dir el mateix que el contracte §17."""
    _neudet()
    i = CF.entre_info()
    if i["font_valids"] == CF.ENTRE_FONT_CONTRACTE:
        pytest.skip("neudet no publica ENTRE_VALIDS: espera el pull de neudet")
    assert tuple(i["valids"]) == CF.ENTRE_CONTRACTE
    if "constants_mf" in i["temperatura_C"]["font"]:
        assert (i["temperatura_C"]["min"], i["temperatura_C"]["max"]) == (CF.ENTRE_T["min"], CF.ENTRE_T["max"])


def test_el_yaml_porta_entre_i_humitat_a_domini():
    _neudet()
    f = copy.deepcopy(CF.defaults())
    f["domini"].update(entre="aire_humit", humitat_relativa_pct=50, temperatura_C=20)
    y = CF.to_yaml(f)
    assert "entre: aire_humit" in y and "humitat_relativa_pct: 50" in y and "temperatura_C: 20" in y


# ── UI-ENTRE-FRAC (contracte §17b i §23, aprovat pel coordinador 2026-11-11) ────────────────────────────────────────────

def test_el_que_la_ui_ensenya_abans_de_desar_es_el_que_dona_neudet_i_el_que_van_al_manifest():
    """Bessó: `propietats_entre` (el que pinta la UI) i `composicio` (el bloc `entre` del `campanya_ui.json`) són el
    mateix número, exacte. Els valors de referència són els del banc ENTRE-MAT (contracte §17b)."""
    _neudet()
    from neudet.disseny import entre as NE
    for hr, t, fraccio, rho in ((50.0, 20.0, 7.1931e-3, 1.19955e-3), (100.0, 30.0, 2.6424e-2, 1.14663e-3)):
        p = CF.entre_propietats("aire_humit", hr, t)
        assert p["ok"] is True and p["font"] == "neudet.disseny.entre.propietats_entre()"
        assert {k: v for k, v in p.items() if k not in ("ok", "font")} == NE.propietats_entre("aire_humit", hr, t)
        comp = NE.composicio({"entre": "aire_humit", "humitat_relativa_pct": hr, "temperatura_C": t})
        assert p["fraccio_h2o_massa"] == comp["fraccio_h2o"] and p["rho_gcm3"] == comp["rho_gcm3"]
        assert p["sha_mf"] == comp["sha_mf"]
        assert p["fraccio_h2o_massa"] == pytest.approx(fraccio, rel=1e-5)
        assert p["rho_gcm3"] == pytest.approx(rho, rel=1e-5)
        assert p["formules"]["fraccio_h2o"] and p["valors"]["e_s_hPa"] > 0        # la fórmula ve amb els valors posats (§15)


def test_buit_i_aire_sense_valors_implícits():
    """§17b: amb `buit` no hi ha medi ⇒ cap número (null, no 0) i cap bloc al manifest; amb `aire`, fracció 0 i ρ de G4_AIR."""
    _neudet()
    b = CF.entre_propietats("buit")
    assert b["ok"] is True and b["fraccio_h2o_massa"] is None and b["rho_gcm3"] is None and b["material_g4"] is None
    a = CF.entre_propietats("aire")
    assert a["ok"] is True and a["fraccio_h2o_massa"] == 0.0 and a["rho_gcm3"] > 0
    assert a["humitat_relativa_pct"] is None and a["temperatura_C"] is None


def test_l_error_el_diu_neudet_i_la_ui_no_reinterpreta():
    """§6 de COORDINACIO («res en silenci»): HR que falta, T fora de la fórmula de Magnus o HR/T amb `aire` → el text
    de neudet, paraula per paraula. La UI no n'afegeix cap ni en treu."""
    _neudet()
    from neudet.disseny import entre as NE
    for args in (("aire_humit", 50.0, None), ("aire", None, 20.0), ("aire_humit", 150.0, 20.0)):
        p = CF.entre_propietats(*args)
        assert p["ok"] is False and p["error"]
        with pytest.raises(ValueError) as e:
            NE.propietats_entre(*args)
        assert p["error"] == str(e.value), args


def test_l_endpoint_entre_passa_el_payload_sense_tocar_lo():
    from simui import api
    p = api.campanya_entre({"entre": "aire_humit", "hr": "50", "t": "20"})
    assert p["ok"] is True and p["fraccio_h2o_massa"] == CF.entre_propietats("aire_humit", 50.0, 20.0)["fraccio_h2o_massa"]
    assert api.campanya_entre({"entre": "aire_humit"})["ok"] is False      # falta HR: la UI ho dirà amb el text de neudet
    assert api.campanya_entre({"entre": "buit", "hr": "", "t": ""})["fraccio_h2o_massa"] is None


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node")
def test_el_panell_pinta_els_numeros_de_neudet_i_no_en_calcula_cap():
    """Executa amb node el que pinta la pàgina, amb el payload real de neudet: els números i la fórmula són els que venen;
    amb `buit` no pinta res; amb error, el text de neudet. I la pàgina no té cap constant de la fórmula de Magnus."""
    _neudet()
    for k in ("6.1078", "17.27", "8.314", "273.15"):
        assert k not in INDEX, f"la pàgina té la constant {k}: la fracció la calcula neudet (§17b)"
    func = INDEX.split("function cEntrePropHtml(p){")[1].split("function cEntrePropCarrega()")[0]
    dades = [CF.entre_propietats("aire_humit", 50.0, 20.0), CF.entre_propietats("buit"),
             CF.entre_propietats("aire_humit", 50.0, None)]
    js = ("const escD = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');"
          "function cEntrePropHtml(p){" + func + "\n"
          "console.log(JSON.stringify(%s.map(cEntrePropHtml)));" % json.dumps(dades))
    h = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True).stdout)
    p = dades[0]
    assert str(p["fraccio_h2o_massa"]) in h[0] and str(p["rho_gcm3"]) in h[0]
    assert p["formules"]["fraccio_h2o"] in h[0] and p["sha_mf"] in h[0]
    assert h[1] == ""                                                      # buit: cap número, cap bloc
    assert dades[2]["error"] in h[2] and "neudet diu" in h[2]              # l'error és el text de neudet


def test_la_ui_mostra_el_selector_i_els_camps_nomes_amb_la_font_a_fora():
    assert "function cEntreHtml" in INDEX and "cFontAvis(d" in INDEX.split("function cEntreHtml")[1].split("function cEntreCanvi")[0]
    assert "domini.humitat_relativa_pct" in INDEX and "domini.temperatura_C" in INDEX and "'aire_humit': 'aire humit'" not in INDEX
    assert "aire_humit: 'aire humit'" in INDEX and "cEntreCanvi(v)" in INDEX


def test_la_ui_no_escriu_l_avis_de_dispersio_el_filtra_del_resum_de_neudet():
    assert "dispersió a l'aire" in INDEX and INDEX.count("l'aire no és la sala") == 0


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node")
def test_kEntreHtml_mostra_els_valors_de_neudet_tal_com_venen_i_l_avis_del_resum():
    f = INDEX.split("function kEntreHtml(v){")[1].split("\nfunction cFontHtml")[0]
    js = ("const escD = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;'); const ENTRE_TXT = {buit: 'buit', aire: 'aire', aire_humit: 'aire humit'};"
          "function kEntreHtml(v){" + f + "\nconst v = __V__; console.log(JSON.stringify([kEntreHtml(v), kEntreHtml({entre: {entre: 'buit'}}), kEntreHtml({entre: null})]));")
    v = {"entre": {"entre": "aire_humit", "humitat_relativa_pct": 50, "temperatura_C": 20, "fraccio_h2o_massa": 0.00731, "rho_gcm3": 0.001199},
         "certificacio": {"resum_text": "Altres línies\nNota: la dispersió a l'aire es negligeix (≤ 0,9 % a 1 MeV en 50 cm); l'aire no és la sala.\nfi"}}
    r = subprocess.run(["node", "-e", js.replace("__V__", json.dumps(v))], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    h, buit, res = json.loads(r.stdout)
    assert "0.00731" in h and "0.001199" in h and "aire humit" in h and "HR" not in h
    assert "la dispersió a l'aire es negligeix (≤ 0,9 % a 1 MeV en 50 cm); l'aire no és la sala." in h
    assert buit == "" and res == ""
    # sense l'avís al resum, no se n'escriu cap
    v["certificacio"] = {"resum_text": "res"}
    h2 = json.loads(subprocess.run(["node", "-e", js.replace("__V__", json.dumps(v))], capture_output=True, text=True).stdout)[0]
    assert "negligeix" not in h2
