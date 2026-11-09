"""INV (neudet `docs/site/encarrecs/2026-11-05_INV_tubs_disponibles.md`, contracte UI §10c): el formulari és «primer els tubs
disponibles (recursos), després on van». Les campanyes antigues s'obren convertides (els mateixos candidats que dona neudet) o,
si no es pot, en només lectura amb el motiu."""
import contextlib
import copy
import io
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

from simui import campanya_form as CF
from simphy.mcgen import design as DES

INDEX = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text()


def _neudet():
    try:
        root = DES.neudet_root()
    except DES.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")
    DES._neudet()
    return root


def _cands(d, nom):
    from neudet.disseny.campanya import Campanya
    with contextlib.redirect_stdout(io.StringIO()):
        C = Campanya(d)
        v, i = C.candidats(nom)
    return sorted(c.hash() for c, _ in v), sorted((c.hash(), tuple(m)) for c, m in i)


@pytest.mark.parametrize("id_,etapa", [("c04_draft", "S1"), ("c03_3anells_grups", "S3"), ("c0_2a0511", "S1")])
def test_conversio_dona_els_mateixos_candidats(id_, etapa):
    """Oberta al formulari (convertida a recursos) i tornada a escriure, la campanya dona a neudet els mateixos candidats
    vàlids i invàlids (hashes i motius) que el yaml d'un tipus per anell."""
    root = _neudet()
    d = root / "disseny" / "campanyes" / id_
    f = CF.de_fitxer(d / "campanya.yaml")
    cv = f[CF.CONVERSIO]
    assert cv["nomes_lectura"] is None and cv["convertida"]
    for t in f["etapes"][etapa]["tongades"]:
        assert isinstance(t["inventari"], list) and "tipus" not in t and "cd" not in t
        for a in t["posicions"].get("anells", []):
            assert "tipus" not in a and "cd" not in a
    with tempfile.TemporaryDirectory() as tmp:
        dn = Path(tmp) / id_
        dn.mkdir()
        (dn / "campanya.yaml").write_text(CF.to_yaml(f))
        if (d / "PLA.md").exists():
            (dn / "PLA.md").write_text((d / "PLA.md").read_text())
        assert _cands(dn, etapa) == _cands(d, etapa)


def test_c0_2a0511_es_converteix_amb_fixats():
    root = _neudet()
    f = CF.de_fitxer(root / "disseny" / "campanyes" / "c0_2a0511" / "campanya.yaml")
    t = f["etapes"]["S1"]["tongades"][0]
    assert [(r["nom"], r["tipus"], r["quantitat"]) for r in t["inventari"]] == [("A", "lnd_sk03410", 4), ("B", "lnd_sk03412", 4)]
    assert [(a["n"], a["fixats"]) for a in t["posicions"]["anells"]] == [(4, {"A": 4}), (4, {"B": 4})]


@pytest.mark.parametrize("id_,motiu", [("c02_cd_2grups", "n variable"), ("c0_2anells", "ventall de tipus"),
                                       ("c01_8tubs_30x30x80", "mostres")])
def test_no_convertible_en_nomes_lectura_i_diu_per_que(id_, motiu):
    root = _neudet()
    f = CF.de_fitxer(root / "disseny" / "campanyes" / id_ / "campanya.yaml")
    assert motiu in f[CF.CONVERSIO]["nomes_lectura"]


def test_la_nota_de_conversio_no_va_al_yaml():
    _neudet()
    f = CF.defaults()
    assert CF.CONVERSIO in f and CF.CONVERSIO not in CF.to_yaml(f)


def _f_inv(**anell2):
    _neudet()
    f = copy.deepcopy(CF.defaults())
    t = f["etapes"]["S1"]["tongades"][0]
    t["inventari"] = [{"nom": "A", "tipus": "lnd_sk03410", "quantitat": 4, "cd": {"fraction": 0}},
                      {"nom": "B", "tipus": "lnd_sk03412", "quantitat": 4, "cd": {"fraction": [0.5, 1], "arc": 360, "lligam": "global"}}]
    t["posicions"]["anells"] = [{"r": {"de": 3, "a": 5, "pas": 1}, "phi": 0},
                                dict({"r": {"de": 6, "a": 9, "pas": 1}, "phi": "mig_pas"}, **anell2)]
    return f


def test_recursos_n_lliure_i_fixats_passen_la_forma():
    y = yaml.safe_load(CF.to_yaml(_f_inv(n=4, fixats={"B": 4})))
    a1, a2 = y["etapes"]["S1"]["tongades"][0]["posicions"]["anells"]
    assert "n" not in a1 and a2["fixats"] == {"B": 4}


@pytest.mark.parametrize("kw,camp", [
    ({"fixats": {"C": 1}}, "anells.1.fixats: C no és a l'inventari"),
    ({"tipus_permesos": ["Z"]}, "anells.1.tipus_permesos: Z no és a l'inventari"),
    ({"n": {"de": 0, "a": 9}}, "anells.1.n.a"),                  # el total dels recursos (8) fa de n_total
])
def test_errors_de_forma_amb_recursos(kw, camp):
    with pytest.raises(CF.FormError) as e:
        CF.to_yaml(_f_inv(**kw))
    assert camp in str(e.value)


def test_inventari_buit_diu_que_cal_un_recurs():
    f = _f_inv()
    f["etapes"]["S1"]["tongades"][0]["inventari"] = []
    with pytest.raises(CF.FormError, match="cal almenys un recurs"):
        CF.to_yaml(f)


def test_la_pagina_diu_els_impossibles_en_paraules():
    q = INDEX.split("function cInvQuadra")[1].split("function cInvCompte")[0]
    for tros in ("se'n fixen", "en sobren", "en falten", "Deixa algun anell lliure", "punts i"):
        assert tros in q, tros
    assert "panel bad" in INDEX.split("function cInvCompte")[1].split("function cSyncInv")[0]
    # fins que no hi ha cap recurs, l'estructura i l'assignació no s'activen
    assert "fins aleshores, l'estructura i l'assignació no s'activen" in INDEX


@pytest.mark.parametrize("n", [{"de": 2, "a": 6, "pas": 2}, [2, 4, 6], 4])
def test_n_dels_anells_amb_recursos_pot_ser_valor_llista_o_rang(n):
    """§10c «Per anell: n absent = lliure; enter = fix; rang = com abans»: el formulari ho escriu tal com és (mentre no passi del total)."""
    y = yaml.safe_load(CF.to_yaml(_f_inv(n=n)))
    assert y["etapes"]["S1"]["tongades"][0]["posicions"]["anells"][1]["n"] == n


def test_n_en_rang_dona_a_neudet_mes_candidats_que_n_fix():
    """Test bessó amb neudet: un rang d'n a l'anell d'un inventari és acceptat i genera candidats (no es redueix a un valor)."""
    root = _neudet()
    pla = root / "disseny" / "campanyes" / "c0_2a0511" / "PLA.md"
    res = {}
    for clau, n in (("fix", 4), ("rang", {"de": 2, "a": 6, "pas": 2})):
        with tempfile.TemporaryDirectory() as tmp:
            dn = Path(tmp) / "c0_2a0511"
            dn.mkdir()
            (dn / "campanya.yaml").write_text(CF.to_yaml(_f_inv(n=n)))
            if pla.exists():
                (dn / "PLA.md").write_text(pla.read_text())
            res[clau] = _cands(dn, "S1")
    assert res["fix"][0] and len(res["rang"][0]) > len(res["fix"][0]), {k: (len(v[0]), len(v[1])) for k, v in res.items()}
