"""FORM-COPIA-UI (neudet `docs/site/encarrecs/2026-11-19_FORM_COPIA_UI.md`, punt 1): la validació d'objectius llegeix
la taula de neudet (`taula_objectius()`) en directe — a simui no se'n copia res: una mètrica nova a neudet
s'accepta sense tocar simui, i l'esborrany `mb10b_ref` surt vàlid."""
import copy

import pytest

from simui import campanya_form as CF


def _neudet():
    from simphy.mcgen import design as DES
    try:
        root = DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")
    DES._neudet()
    return root


def _form(objectius):
    f = copy.deepcopy(CF.defaults())
    f.pop(CF.CONVERSIO, None)
    f["objectius"] = objectius
    return f


def test_metrica_nova_a_neudet_s_accepta_sense_tocar_simui(monkeypatch):
    """Bessó del punt 1: la taula real, tal com si neudet hi hagués declarat una mètrica nova (`metrica_nova`):
    la validació l'accepta sense canviar res de simui. Sense la declaració, el refús segueix sent el mateix."""
    _neudet()
    from neudet.disseny import objectius as O
    real = O.taula_objectius()
    assert "metrica_nova" not in real["finalitats"]["comptador"]["metriques"]
    ob = {"finalitat": "comptador", "objectius": [["metrica_nova", "max"], ["cv", "min"]]}
    with pytest.raises(CF.FormError, match="no és de la finalitat comptador"):
        CF.to_yaml(_form(ob))

    def taula_con_una_mes():
        t = copy.deepcopy(real)
        t["finalitats"]["comptador"]["metriques"].append("metrica_nova")
        return t

    monkeypatch.setattr(O, "taula_objectius", taula_con_una_mes)
    assert "metrica_nova" in CF.to_yaml(_form(ob))


def test_mb10b_ref_surt_valid():
    """L'esborrany `mb10b_ref` de neudet (feina 1 de MINIBELEN): el formulari el llegeix i el torna a escriure vàlid
    — amb `planor_f` a l'objectiu, que és el que la còpia de `campanya_form.py` no tenia. El camí és el real: si
    neudet el mou, aquest test l'ha de seguir o dir on buscar-lo."""
    root = _neudet()
    f = root / "disseny" / "campanyes" / "mb10b_ref" / "campanya.yaml"
    if not f.is_file():
        pytest.fail(f"l'esborrany no hi és: {f} (neudet: disseny/campanyes/mb10b_ref/, feina 1 de MINIBELEN)")
    text = CF.to_yaml(CF.de_fitxer(f))
    assert "planor_f" in text
