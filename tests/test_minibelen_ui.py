"""MINIBELEN (encàrrec 2026-11-18, secció simui.1): un esborrany amb un bloc PENDENT s'obri al formulari,
els camps queden marcats en vermell al lloc correcte i es pot completar per blocs. I la UI no s'inventa
les mides per dibuixar el bloc (§22, MAI INVENTIS).

Com és un test bessó: `cErr` és el JS de la UI executat amb node amb un DOM fals mínim (els mateixos
`data-p` que pinta el formulari); la carpeta del bloc es fa amb `de_fitxer`→`to_yaml`, el mateix camí que
el navegador quan obre l'esborrany i quan en tecleges les mides (l'equivalent python de `cSet`).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from simui import campanya_form as CF

INDEX = (Path(__file__).resolve().parents[1] / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")


# ── el JS: cErr marca el grup sencer dels camps d'un error de llista ─────────

def _js_cErr() -> str:
    ini = INDEX.index("function cErr(msg){")
    return INDEX[ini:INDEX.index("\n}\n", ini) + 3]


@pytest.mark.skipif(shutil.which("node") is None, reason="cal node per executar cErr")
def test_cErr_marca_el_grup_sencer_i_diu_el_motiu_una_sola_vegada():
    """Un error `-domini.bloc.mides_cm: motiu` és dels camps `…mides_cm.0/1/2`: els tres es marquen en vermell
    i el motiu es diu una sola vegada (MINIBELEN: el PENDENT del bloc ha de ser visible en vermell). Un camp
    dit nom per nom es marca sol, amb el seu motiu."""
    js = _js_cErr() + r"""
    // DOM fals mínim: inputs amb data-p (com els del formulari), sense <label>, i el panell #c-err
    const ELS = ["domini.bloc.mides_cm.0", "domini.bloc.mides_cm.1", "domini.bloc.mides_cm.2",
                 "objectius.pareto_k_sigma"].map(p => {
      const e = { dataset: {p}, _cls: [], closest: () => null, after(d) { (this._despres ||= []).push(d); } };
      e.classList = { add: c => e._cls.push(c), remove: c => {} };
      return e;
    });
    const PANEL = { innerHTML: "" };
    global.Q = () => PANEL;
    global.escD = s => s;
    global.document = {
      querySelectorAll: sel => sel === "#pg-neudet [data-p]" ? ELS : [],
      createElement: () => ({ className: "", textContent: "" }),
    };
    cErr("formulari no vàlid:\n- domini.bloc.mides_cm: tres mides positives en cm, p. ex. [30, 30, 80]"
       + "\n- objectius.pareto_k_sigma: ha de ser ≥ 0");
    console.log(JSON.stringify({
      marcats: ELS.filter(e => e._cls.includes("bad")).map(e => e.dataset.p),
      motius: ELS.filter(e => e._despres).flatMap(e => e._despres.map(d => [d.className, d.textContent])),
      panell: PANEL.innerHTML.includes("tres mides positives"),
    }));"""
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    surt = json.loads(r.stdout)
    assert surt["marcats"] == ["domini.bloc.mides_cm.0", "domini.bloc.mides_cm.1", "domini.bloc.mides_cm.2",
                               "objectius.pareto_k_sigma"]
    assert surt["motius"] == [["err camperr", "tres mides positives en cm, p. ex. [30, 30, 80]"],
                              ["err camperr", "ha de ser ≥ 0"]]           # un sol motiu per al grup de tres
    assert surt["panell"]


# ── el Python: l'esborrany PENDENT es carrega tal com és i es completa per blocs ──

_sense = object()                                     # clau `mides_cm` absent del tot

_BASE = {
    "id": "mb_pendent_prova",
    "domini": {
        "bloc": {"material": "PE", "forat_cm": 0},
        "font": {"tipus": "iso", "pos_cm": [0, 0, 0]},
        "energies_MeV": [0.001, 1.0],
        "tipus_tub": ["lnd_252285"],
        "restriccions": {"n_tubs": 2},
    },
    "etapes": {"S1": {"tongades": [{"nom": "t", "posicions": {"font": "anells", "anells": [{"r": 3, "n": 2, "phi": 0}]},
                                    "tipus": ["lnd_252285"], "cd": {"fraction": 0}, "eix": "z", "seleccio": "exhaustiu"}]}},
}


def _esborrany(tmp_path: Path, nom: str, mides=_sense) -> Path:
    bloc = dict(_BASE["domini"]["bloc"])
    if mides is not _sense:
        bloc["mides_cm"] = mides
    carpeta = tmp_path / nom
    carpeta.mkdir()
    d = carpeta / "campanya.yaml"
    d.write_text(yaml.safe_dump({"id": _BASE["id"], "domini": {**_BASE["domini"], "bloc": bloc},
                                 "etapes": _BASE["etapes"]}, allow_unicode=True), encoding="utf-8")
    return d


@pytest.mark.parametrize("mides", [_sense, None, "PENDENT: mida de la Fig. 6 (a confirmar)"],
                         ids=["absent", "null", "text"])
def test_esborrany_sense_mides_es_refusa_en_paraules_sense_inventar_res(tmp_path, mides):
    d = CF.de_fitxer(_esborrany(tmp_path, "refús", mides))
    if mides is _sense:
        assert "mides_cm" not in d["domini"]["bloc"]             # de_fitxer no omple cap per defecte
    else:
        assert d["domini"]["bloc"]["mides_cm"] == mides          # null o text: es llegeix tal com és
    with pytest.raises(ValueError) as ex:
        CF.to_yaml(d)
    motius = [l for l in str(ex.value).splitlines() if l.startswith("- ")]
    assert motius == ["- domini.bloc.mides_cm: tres mides positives en cm, p. ex. [30, 30, 80]"]


def _cset_bloc(d: dict, i: int, v) -> None:
    """El que fa `cSet` de l'index.html en teclejar `domini.bloc.mides_cm.{i}`: si el valor no és un objecte
    (absent, null o la string «PENDENT…») hi posa una llista, i després hi escriu la posició."""
    bloc = d["domini"]["bloc"]
    if not isinstance(bloc.get("mides_cm"), list):
        bloc["mides_cm"] = []
    while len(bloc["mides_cm"]) <= i:
        bloc["mides_cm"].append(None)
    bloc["mides_cm"][i] = v


def test_completar_el_bloc_per_blocs_desbloqueja_el_yaml(tmp_path):
    for id_, mides in [("absent", _sense), ("text", "PENDENT: mida de la Fig. 6 (a confirmar)")]:
        d = CF.de_fitxer(_esborrany(tmp_path, id_ + "_complet", mides))
        for i, v in enumerate([50, 50, 70]):
            _cset_bloc(d, i, v)
        escrit = yaml.safe_load(CF.to_yaml(d))
        assert escrit["domini"]["bloc"]["mides_cm"] == [50, 50, 70]
        assert escrit["domini"]["bloc"]["material"] == "PE" and escrit["domini"]["bloc"]["forat_cm"] == 0


# ── guards a la plantilla ─────────────────────────────────────────────────────

def test_el_dibuix_avis_quan_les_mides_no_son_escrites_i_un_text_no_entra_als_inputs():
    assert "el.dataset.p.startsWith(camp + '.')" in INDEX                 # cErr: el grup sencer es marca
    assert INDEX.count("d.className = 'err camperr'") == 1                # el motiu es crea un sol lloc (el grup el fa servir una vegada)
    # `sense` es calcula sobre el que HI HA ESCRIT, no sobre el valor de reemplac del dibuix (§22):
    assert "sense: !(Array.isArray(b.mides_cm) && b.mides_cm.length === 3" in INDEX
    assert "el dibuix és orientatiu, no és la teva geometria" in INDEX    # l'avís existeix i surt amb `sense`
    # un valor «PENDENT…» (string) no es vessa als tres inputs numèrics:
    assert "Array.isArray(d.bloc.mides_cm) ? d.bloc.mides_cm : [null, null, null]" in INDEX
