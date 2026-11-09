"""test_mcgen_campanya_desa.py — «Desa la proposta» i «Tanteja» (contracte simphy_ui.md §7; flux _flux_campanya.md).

Què es fixa
-----------
- `desa_proposta` escriu EXACTAMENT dos fitxers a `disseny/campanyes/<id>/` (campanya.yaml amb `estat: proposta`
  i comprova.json), i res més de neudet. Tot en un NEUDET_ROOT temporal: mai a /home/user/neudet.
- Refusa: un id que no és un nom de carpeta, un traversal, una campanya existent que no és proposta, una carpeta
  sense campanya.yaml, una forma que neudet no llegeix, i una certificació no disponible (sense script, sense
  JSON, JSON d'una altra campanya, o amb `camps_falten`). Cap refús deixa res escrit.
- Un veredicte d'aturada (`atura`) NO és una certificació no disponible: es desa i es diu.
- `id_derivat`: c04_draft → c04b_draft → c04c_draft…; el prefix amb lletra es reemplaça.
- `llista()`: `estat_yaml` i `estat_manifest` són dos camps; els grups principal / altres; un estat desconegut
  no fa caure res.
- Tanteig: de campanya (formulari amb id nou, original intacta) i de candidat (etapa `llista` amb els tubs de
  neudet, que torna el mateix hash). El de candidat necessita neudet real (sense escriure res).

Certificació: `torch` no és aquí, així que `comprova_campanya.py` no certifica. Els tests de desar substitueixen
`CC.certifica_proposta` per un informe fixat; els dos tests de `certifica_proposta` corren el script real però
fals (sense torch), i comproven que els refusos són els esperats.
Sense neudet real (c04_draft), els tests que la necessiten es salten.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simui import campanya_check as CC  # noqa: E402
from simui import campanya_desa as CD  # noqa: E402
from simui import campanya_form as CF  # noqa: E402
from simui import campanya_vista as CV  # noqa: E402
from simphy.mcgen import design as D  # noqa: E402


# el neudet real es mira UNA vegada, abans que cap fixture canviï NEUDET_ROOT
try:
    _REAL_NEUDET = D.neudet_root()
except D.DesignError as _e:                        # noqa: N816
    _REAL_NEUDET = None
    _MOTIU_REAL = str(_e)


def _real_c04() -> Path:
    if _REAL_NEUDET is None:
        pytest.skip(f"neudet no és present: {_MOTIU_REAL}")
    f = _REAL_NEUDET / CF.C04_YAML
    if not f.exists():
        pytest.skip(f"no hi ha {f}")
    return f


def _informe(id_: str, atura: bool = False) -> dict:
    """Un `comprova.json` com el de neudet (la forma que `certifica_proposta` accepta)."""
    return {"campanya": id_, "fitxa": 1, "draft": True, "etapes": {"S1": {"valids": 3, "invalids": 0, "motius": {}}},
            "elements": [{"element": "tub lnd_252285", "estat": "validat", "motiu": "", "document": "V-TUB"}],
            "atura": atura}


@pytest.fixture
def neudet_tmp(tmp_path, monkeypatch):
    """Un NEUDET_ROOT temporal amb `src/neudet/disseny` (perquè `neudet_root()` el reconegui) i `disseny/campanyes/`."""
    root = tmp_path / "neudet"
    (root / "src" / "neudet" / "disseny").mkdir(parents=True)
    (root / "disseny" / "campanyes").mkdir(parents=True)
    monkeypatch.setenv("NEUDET_ROOT", str(root))
    return root


def _camp(root: Path, id_: str, yaml_text: str) -> Path:
    d = root / "disseny" / "campanyes" / id_
    d.mkdir(parents=True)
    (d / "campanya.yaml").write_text(yaml_text, encoding="utf-8")
    return d


def _arbre(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
            for p in sorted(root.rglob("*"))}


_FORM_C04: dict = {}
try:
    if _REAL_NEUDET is not None and (_REAL_NEUDET / CF.C04_YAML).exists():
        _FORM_C04.update(CF.de_fitxer(_REAL_NEUDET / CF.C04_YAML))
except Exception:                                  # noqa: BLE001 — sense neudet importable, els tests es salten
    pass


def _form_c04(id_: str = "c05_prova") -> dict:
    """El c04 de neudet com a formulari (amb `tongades`). Es llegeix amb el neudet real, abans de les fixtures que
    canvien NEUDET_ROOT (traduir `generador` a `tongades` necessita el codi de neudet)."""
    if not _FORM_C04:
        pytest.skip("neudet no és present: no es pot llegir el c04")
    f = copy.deepcopy(_FORM_C04)
    f["id"] = id_
    return f


@pytest.fixture
def cert_ok(monkeypatch):
    """Certificació fixada (sense torch): `certifica_proposta` torna un informe per al yaml i l'id que li arriben."""
    cridades = []

    def fals(yaml_text, id_):
        cridades.append((yaml_text, id_))
        return _informe(id_)

    monkeypatch.setattr(CC, "certifica_proposta", fals)
    return cridades


# ── ids ─────────────────────────────────────────────────────────────────────

def test_id_derivat_seqüencia_de_c04():
    assert CD.id_derivat("c04_draft", []) == "c04b_draft"
    assert CD.id_derivat("c04_draft", ["c04_draft", "c04b_draft"]) == "c04c_draft"
    assert CD.id_derivat("c04_draft", ["c04_draft", "c04b_draft", "c04c_draft"]) == "c04d_draft"


def test_id_derivat_des_d_un_tanteig_reemplaca_la_lletra():
    """Un tanteig de c04b_draft no fa c04bb_draft: la família és c04*."""
    assert CD.id_derivat("c04b_draft", ["c04_draft", "c04b_draft"]) == "c04c_draft"


def test_id_derivat_sense_guio_i_sense_prefix_numeric():
    assert CD.id_derivat("c04", []) == "c04b"
    assert CD.id_derivat("prova_draft", []) == "provab_draft"


@pytest.mark.parametrize("bo", ["../c05", "c05/../../x", "C05_prova", "c", "x y", ".", "..", "c05_prova/", "", None, 7])
def test_valida_id_refusa_el_que_no_es_nom_de_carpeta(bo):
    with pytest.raises(CD.DesaError):
        CD.valida_id(bo)
    with pytest.raises(CD.DesaError):
        CD.id_derivat(bo if isinstance(bo, str) else "x", [])


def test_valida_id_accepta_els_de_la_fitxa():
    assert CD.valida_id("c05_prova") == "c05_prova"
    assert CD.valida_id("c04_draft") == "c04_draft"


# ── desar la proposta ───────────────────────────────────────────────────────

def test_desa_escriu_exactament_dos_fitxers_i_estat_proposta(neudet_tmp, cert_ok):
    _real_c04()
    form = _form_c04("c05_prova")
    antes = _arbre(neudet_tmp)
    r = CD.desa_proposta(form)
    despres = _arbre(neudet_tmp)
    nous = sorted(set(despres) - set(antes))
    assert nous == ["disseny/campanyes/c05_prova", "disseny/campanyes/c05_prova/campanya.yaml",
                    "disseny/campanyes/c05_prova/comprova.json"]
    assert sorted(p for p in despres if p not in antes) == nous
    assert all(despres[k] == antes[k] for k in antes), "res de neudet existent no s'ha tocat"
    d = neudet_tmp / "disseny" / "campanyes" / "c05_prova"
    assert sorted(x.name for x in d.iterdir()) == ["campanya.yaml", "comprova.json"]
    y = yaml.safe_load((d / "campanya.yaml").read_text(encoding="utf-8"))
    assert y["estat"] == "proposta" and y["id"] == "c05_prova"
    assert json.loads((d / "comprova.json").read_text(encoding="utf-8")) == _informe("c05_prova")
    assert r["escrit"] == [str(d / "campanya.yaml"), str(d / "comprova.json")]
    assert r["missatge"] == "campanya `c05_prova` proposta"
    assert r["sobreescrita"] is False and r["atura"] is False


def test_la_certificacio_es_fa_sobre_el_mateix_yaml_que_es_desa(neudet_tmp, cert_ok):
    _real_c04()
    CD.desa_proposta(_form_c04("c05_prova"))
    text_certificat, id_cert = cert_ok[0]
    d = neudet_tmp / "disseny" / "campanyes" / "c05_prova"
    assert text_certificat == (d / "campanya.yaml").read_text(encoding="utf-8")
    assert id_cert == "c05_prova"


def test_desa_no_modifica_el_formulari_que_rep(neudet_tmp, cert_ok):
    _real_c04()
    form = _form_c04("c05_prova")
    antes = json.dumps(form, sort_keys=True, default=str)
    CD.desa_proposta(form)
    assert json.dumps(form, sort_keys=True, default=str) == antes


def test_desa_refusa_una_campanya_existent_que_no_es_proposta(neudet_tmp, cert_ok):
    _real_c04()
    d = _camp(neudet_tmp, "c05_prova", "id: c05_prova\nestat: jutjada\n")
    antes = _arbre(neudet_tmp)
    with pytest.raises(CD.DesaError) as exc:
        CD.desa_proposta(_form_c04("c05_prova"))
    assert "no es modifica mai una campanya existent: fes un tanteig amb un id nou" in str(exc.value)
    assert _arbre(neudet_tmp) == antes and (d / "campanya.yaml").read_text().endswith("jutjada\n")
    assert cert_ok == [], "ni tan sols es certifica si es refusa"


def test_desa_refusa_una_carpeta_sense_campanya_yaml(neudet_tmp, cert_ok):
    _real_c04()
    (neudet_tmp / "disseny" / "campanyes" / "c05_prova").mkdir()
    with pytest.raises(CD.DesaError, match="no té campanya.yaml"):
        CD.desa_proposta(_form_c04("c05_prova"))
    assert list((neudet_tmp / "disseny" / "campanyes" / "c05_prova").iterdir()) == []


def test_desa_sobreescriu_la_proposta_propia(neudet_tmp, cert_ok):
    _real_c04()
    _camp(neudet_tmp, "c05_prova", "id: c05_prova\nestat: proposta\n")
    r = CD.desa_proposta(_form_c04("c05_prova"))
    assert r["sobreescrita"] is True
    y = yaml.safe_load((neudet_tmp / "disseny" / "campanyes" / "c05_prova" / "campanya.yaml").read_text())
    assert y["estat"] == "proposta" and "tipus_tub" not in y["domini"]   # SIMPLIFICA: neudet el deriva dels tipus de les tongades


@pytest.mark.parametrize("bo", ["../c05", "c05/../../x", "C05_prova", "c", "x y", "."])
def test_desa_refusa_ids_dolents_i_no_escriu_res(neudet_tmp, cert_ok, bo):
    _real_c04()
    antes = _arbre(neudet_tmp)
    form = _form_c04("c05_prova")
    form["id"] = bo
    with pytest.raises(CD.DesaError):
        CD.desa_proposta(form)
    assert _arbre(neudet_tmp) == antes and cert_ok == []


def test_desa_refusa_una_forma_que_neudet_no_llegeix(neudet_tmp, cert_ok):
    _real_c04()
    form = _form_c04("c05_prova")
    form["etapes"] = {}
    antes = _arbre(neudet_tmp)
    with pytest.raises(CD.DesaError, match="no es desa"):
        CD.desa_proposta(form)
    assert _arbre(neudet_tmp) == antes


def test_desa_refusa_si_la_certificacio_no_es_disponible(neudet_tmp, monkeypatch):
    _real_c04()

    def sense(yaml_text, id_):
        raise ValueError("comprova_campanya.py no existeix a neudet (CAMP-1 pendent)")

    monkeypatch.setattr(CC, "certifica_proposta", sense)
    antes = _arbre(neudet_tmp)
    with pytest.raises(CD.DesaError, match="neudet no certifica la proposta"):
        CD.desa_proposta(_form_c04("c05_prova"))
    assert _arbre(neudet_tmp) == antes


def test_desa_amb_aturada_es_desa_i_ho_diu(neudet_tmp, monkeypatch):
    _real_c04()
    monkeypatch.setattr(CC, "certifica_proposta", lambda y, i: _informe(i, atura=True))
    r = CD.desa_proposta(_form_c04("c05_prova"))
    assert r["atura"] is True
    assert (neudet_tmp / "disseny" / "campanyes" / "c05_prova" / "comprova.json").is_file()


def _script_fals(root: Path, cos: str) -> None:
    """Un `comprova_campanya.py` de mentida al lloc on el busca simphy (per al camí real, sense torch)."""
    s = root / "scripts" / "disseny"
    s.mkdir(parents=True, exist_ok=True)
    (s / "comprova_campanya.py").write_text(cos, encoding="utf-8")


def test_certifica_proposta_sense_script_diu_que_no_certifica(neudet_tmp):
    with pytest.raises(ValueError, match="no existeix a neudet"):
        CC.certifica_proposta("id: c05_prova\n", "c05_prova")


def test_certifica_proposta_sense_json_es_no_disponible(neudet_tmp):
    """El camí real: el script corre i peta sense escriure res (com fa sense torch). Refusa, amb la sortida."""
    _script_fals(neudet_tmp, "import sys\nprint('x')\nsys.exit(1)\n")
    with pytest.raises(ValueError, match="no ha escrit la certificació"):
        CC.certifica_proposta("id: c05_prova\n", "c05_prova")
    antes = _arbre(neudet_tmp)
    with pytest.raises(CD.DesaError):
        CD.desa_proposta(_form_c04("c05_prova"))
    assert _arbre(neudet_tmp) == antes


def test_certifica_proposta_refusa_el_json_d_una_altra_campanya(neudet_tmp):
    _script_fals(neudet_tmp, "import json, sys\na = sys.argv\nj = a[a.index('--json') + 1]\n"
                             "open(j, 'w').write(json.dumps({'campanya': 'altra', 'atura': False, 'elements': []}))\n")
    with pytest.raises(ValueError, match="no de «c05_prova»"):
        CC.certifica_proposta("id: c05_prova\n", "c05_prova")


def test_certifica_proposta_refusa_camps_falten(neudet_tmp):
    _script_fals(neudet_tmp, "import json, sys\na = sys.argv\nj = a[a.index('--json') + 1]\n"
                             "open(j, 'w').write(json.dumps({'camps_falten': 'falta domini', 'atura': True}))\n")
    with pytest.raises(ValueError, match="neudet no pot llegir la campanya: falta domini"):
        CC.certifica_proposta("id: c05_prova\n", "c05_prova")


def test_certifica_proposta_amb_script_que_certifica_es_desa(neudet_tmp):
    """Camí real complet (sense torch al mig): el script escriu l'informe i la proposta es desa amb ell."""
    _real_c04()
    _script_fals(neudet_tmp, "import json, sys\na = sys.argv\nj = a[a.index('--json') + 1]\n"
                             "open(j, 'w').write(json.dumps({'campanya': 'c05_prova', 'fitxa': 1, 'draft': True, "
                             "'etapes': {}, 'elements': [], 'atura': False}))\n")
    r = CD.desa_proposta(_form_c04("c05_prova"))
    assert json.loads((neudet_tmp / "disseny" / "campanyes" / "c05_prova" / "comprova.json").read_text())["campanya"] == "c05_prova"
    assert r["atura"] is False


# ── llista: estat del yaml i estat del manifest, dos camps ───────────────────

_MANIFEST_MIN = {"definicio": {"yaml": "campanya.yaml", "md": None}, "certificacio": None, "etapes": [],
                 "export": None, "judici": None, "report": [], "estat": "draft"}


def test_llista_separa_estat_del_yaml_i_del_manifest(neudet_tmp):
    _camp(neudet_tmp, "c01_x", "id: c01_x\nestat: tancada (2026-10-19; frontera)\n")
    _camp(neudet_tmp, "c02_y", "id: c02_y\nestat: S3\n")
    _camp(neudet_tmp, "c05_prova", "id: c05_prova\nestat: proposta\ndraft: true\n")
    d = _camp(neudet_tmp, "c06_man", "id: c06_man\nestat: jutjada\ndraft: false\n")
    (d / "campanya_ui.json").write_text(json.dumps(_MANIFEST_MIN))
    _camp(neudet_tmp, "c07_num", "id: c07_num\nestat: 42\n")
    _camp(neudet_tmp, "c08_trencat", "id: [sense_tancar\n")
    files = {r["id"]: r for r in CV.llista()}

    assert files["c01_x"]["estat_yaml"] == "tancada (2026-10-19; frontera)"
    assert files["c01_x"]["grup"] == "altres" and files["c01_x"]["estat_manifest"] == "desconegut"
    assert files["c02_y"]["estat_yaml"] == "S3" and files["c02_y"]["grup"] == "altres"
    assert files["c05_prova"]["proposta"] is True and files["c05_prova"]["grup"] == "principal"
    assert files["c05_prova"]["estat_yaml"] == "proposta" and files["c05_prova"]["estat_manifest"] == "draft"
    assert files["c06_man"]["manifest"] is True and files["c06_man"]["grup"] == "principal"
    assert files["c06_man"]["estat_yaml"] == "jutjada" and files["c06_man"]["estat_manifest"] == "definitiva"
    assert files["c07_num"]["estat_yaml"] == "42"
    assert files["c08_trencat"]["motiu"] and files["c08_trencat"]["grup"] == "altres"


def test_vista_de_proposta_sense_manifest_no_falla(neudet_tmp):
    _camp(neudet_tmp, "c05_prova", "id: c05_prova\nestat: proposta\ndraft: true\n")
    v = CV.vista(CV.dir_de("c05_prova"))
    assert v["estat_yaml"] == "proposta" and v["provisional"] is True and v["etapes"] == []


def test_vista_de_proposta_amb_pareto_pero_sense_etapes_no_falla(neudet_tmp):
    """Una proposta amb `objectius.pareto` (com la de c04) però sense etapes: no hi ha candidats.csv on
    comprovar les mètriques. La vista ho diu al motiu, no falla."""
    real = _real_c04()
    _camp(neudet_tmp, "c05_prova", real.read_text(encoding="utf-8").replace("id: c04_draft", "id: c05_prova")
          .replace("estat: jutjada", "estat: proposta"))
    v = CV.vista(CV.dir_de("c05_prova"))
    assert v["etapes"] == [] and v["estat_yaml"] == "proposta"
    assert v["pareto"]["eixos"] and "no es poden comprovar" in v["pareto"]["motiu"]


# ── tanteig de campanya: l'original no es toca ───────────────────────────────

def test_tanteig_de_campanya_porta_un_id_lliure_i_no_toca_loriginal(neudet_tmp, cert_ok):
    real = _real_c04()
    d = _camp(neudet_tmp, "c04_draft", CF.to_yaml(_form_c04("c04_draft")))
    antes = _arbre(neudet_tmp)
    t = CD.tanteig_de_campanya("c04_draft")
    assert _arbre(neudet_tmp) == antes, "tanteig no escriu res"
    assert t["id"] == "c04b_draft" and t["de"] == "c04_draft"
    assert t["form"]["id"] == "c04b_draft" and t["form"]["estat"] == "proposta"
    assert t["form"]["etapes"] == _form_c04()["etapes"], "el disseny és el de l'original"
    assert t["candidat"] is None and t["etapa"] == next(iter(t["form"]["etapes"]))


def test_tanteig_i_desa_fan_una_campanya_nova_sense_tocar_loriginal(neudet_tmp, cert_ok):
    real = _real_c04()
    d = _camp(neudet_tmp, "c04_draft", CF.to_yaml(_form_c04("c04_draft")))
    original = (d / "campanya.yaml").read_bytes()
    t = CD.tanteig_de_campanya("c04_draft")
    r = CD.desa_proposta(t["form"])
    assert r["id"] == "c04b_draft" and r["sobreescrita"] is False
    assert (d / "campanya.yaml").read_bytes() == original
    assert not (d / "comprova.json").exists()
    assert (neudet_tmp / "disseny" / "campanyes" / "c04b_draft" / "campanya.yaml").is_file()


def test_tanteig_de_campanya_inexistent_es_error_amb_el_motiu(neudet_tmp):
    with pytest.raises(CV.CampanyaError, match="no trobo la campanya"):
        CD.tanteig_de_campanya("c09_no")


# ── tanteig de candidat: etapa llista amb els tubs de neudet (neudet real) ───

def test_tanteig_de_candidat_es_un_llista_que_torna_el_mateix_hash():
    real = _real_c04()
    try:
        D._neudet()
        from neudet.disseny.campanya import Campanya
    except Exception as e:                       # noqa: BLE001
        pytest.skip(f"neudet no importable: {e}")
    C = Campanya(real.parent)
    valids, _ = C.candidats("S1")
    cand = valids[0][0]
    h = cand.hash()
    t = CD.tanteig_de_candidat("c04_draft", h)
    assert t["candidat"]["hash"] == h and t["candidat"]["etapa"] == "S1"
    assert t["etapa"] == "llista_S1" and list(t["form"]["etapes"]) == ["llista_S1"]
    ts = t["form"]["etapes"]["llista_S1"]["tongades"]
    assert len(ts) == 1 and ts[0]["posicions"]["font"] == "punts"
    assert len(ts[0]["posicions"]["punts"]) == len(cand.tubs)
    # el yaml que surt de les claus de neudet, llegit per neudet, dona el mateix candidat (mateix hash)
    text = CF.to_yaml(t["form"])
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        dd = Path(tmp) / "c04b_draft"
        dd.mkdir()
        (dd / "campanya.yaml").write_text(text, encoding="utf-8")
        valids2, _ = Campanya(dd).candidats("llista_S1")
    assert [c.hash() for c, _ in valids2] == [h]


def test_tanteig_de_candidat_que_no_hi_es_refusa():
    _real_c04()
    with pytest.raises(ValueError, match="cap candidat vàlid amb hash deadbeef"):
        CD.tanteig_de_candidat("c04_draft", "deadbeef")


def test_tanteig_de_campanya_amb_cd_com_a_llista_es_pot_fer():
    """c01 té Cd com a llista (contracte §4): el formulari la llegeix i el tanteig de la campanya sencera es
    pot desar. Abans es refusava dient el camp; el refús continua per a qualsevol forma que `to_yaml` no escrigui."""
    _real_c04()
    if not (_REAL_NEUDET / "disseny" / "campanyes" / "c01_8tubs_30x30x80").is_dir():
        pytest.skip("no hi ha c01 a neudet")
    r = CD.tanteig_de_campanya("c01_8tubs_30x30x80")
    CF.to_yaml(r["form"])


# ── CONF-UI: «Confirmar i congelar» (neudet escriu la confirmació; contracte UI §13) ──

@pytest.fixture
def camp_confirmable(tmp_path, monkeypatch):
    """Una campanya temporal; la carpeta és fora de neudet (no s'hi escriu mai) i `dir_de` hi apunta. Es fa servir el codi real de neudet."""
    root = _real_c04()
    d = tmp_path / "c07_prova"
    d.mkdir()
    (d / "campanya.yaml").write_text("id: c07_prova\nestat: interpretada\ndomini: {a: 1}\n", encoding="utf-8")
    (d / "PLA.md").write_text("# PLA\n", encoding="utf-8")
    monkeypatch.setattr(CD.CV, "dir_de", lambda i: d)
    return d


def test_confirma_escriu_confirmacio_i_estat_i_no_toca_el_pla(camp_confirmable):
    d = camp_confirmable
    pla = (d / "PLA.md").read_bytes()
    r = CD.confirma_campanya("c07_prova", "Albert")
    y = yaml.safe_load((d / "campanya.yaml").read_text())
    assert y["estat"] == "confirmada" and y["confirmacio"]["per"] == "Albert"
    assert y["confirmacio"]["hash_yaml"] == r["confirmacio"]["hash_yaml"] and len(r["confirmacio"]["hash_pla"]) == 64
    assert "Confirmada el" in r["text"] and (d / "PLA.md").read_bytes() == pla


def test_confirma_refusa_una_proposta_amb_el_motiu_de_neudet(camp_confirmable):
    d = camp_confirmable
    (d / "campanya.yaml").write_text("id: c07_prova\nestat: proposta\n", encoding="utf-8")
    with pytest.raises(CD.DesaError, match="només es pot confirmar una campanya `interpretada`"):
        CD.confirma_campanya("c07_prova", "Albert")
    assert "confirmacio" not in (d / "campanya.yaml").read_text()


def test_confirma_sense_nom_o_sense_pla_es_refusa(camp_confirmable):
    d = camp_confirmable
    with pytest.raises(CD.DesaError, match="qui confirma"):
        CD.confirma_campanya("c07_prova", "  ")
    (d / "PLA.md").unlink()
    with pytest.raises(CD.DesaError, match="no hi ha PLA.md"):
        CD.confirma_campanya("c07_prova", "Albert")


def test_desa_modifica_una_campanya_interpretada_i_la_torna_a_proposta(neudet_tmp, cert_ok):
    """Contracte UI §13: «Modifica la proposta» val fins a `interpretada` (no confirmada); torna l'estat a `proposta`."""
    _real_c04()
    _camp(neudet_tmp, "c06_prova", "id: c06_prova\nestat: interpretada\n")
    r = CD.desa_proposta(_form_c04("c06_prova"))
    assert r["estat"] == "proposta" and r["sobreescrita"]


def test_desa_modifica_una_campanya_confirmada_i_treu_la_confirmacio(neudet_tmp, cert_ok):
    """Sempre es pot tornar enrere mentre no ha corregut res: confirmada → proposta, sense confirmació."""
    _real_c04()
    d = _camp(neudet_tmp, "c07b_prova", "id: c07b_prova\nestat: confirmada\nconfirmacio: {data: '2026-11-06'}\n")
    r = CD.desa_proposta(_form_c04("c07b_prova"))
    assert r["estat"] == "proposta"
    import yaml as _y
    y = _y.safe_load((neudet_tmp / "disseny" / "campanyes" / "c07b_prova" / "campanya.yaml").read_text())
    assert y["estat"] == "proposta" and "confirmacio" not in y


def test_desa_modifica_una_campanya_aturada(neudet_tmp, cert_ok):
    """Una tanda aturada per una porta no ha donat cap resultat vàlid: es pot modificar (torna a proposta)."""
    _real_c04()
    _camp(neudet_tmp, "c07c_prova", "id: c07c_prova\nestat: aturada\n")
    assert CD.desa_proposta(_form_c04("c07c_prova"))["estat"] == "proposta"
