"""test_mcgen_campanya_vista.py — la campanya com a conjunt (contracte simphy_ui.md §6, encàrrec CAMP-2).

Què es fixa
-----------
- Sense `campanya_ui.json`, el provisional de c04_draft: 2 etapes (xarxa B1 i geant4), 8 i 2 candidats,
  `_g4` verifica `S1_draft`, el judici no és buit i el report PDF hi és.
- Amb un manifest real a la carpeta, el manifest guanya (còpia temporal), i un manifest incomplet es
  rebutja dient quin camp falta.
- La vista uneix `candidats.csv` i `resultats_tub.json` pel hash; els eixos de Pareto són els de
  `campanya.yaml`; un Pareto que no quadra amb el csv és un error que diu què.
- `fitxer()` només serveix dins de la campanya o els reports llistats; la resta és `Prohibit`.
Sense neudet, els tests amb dades reals es salten.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simphy.mcgen import campanya_vista as V  # noqa: E402
from simphy.mcgen import design as D  # noqa: E402
from simphy.mcgen import results_tub as RES  # noqa: E402

MOTIU = "campanya_ui.json encara no hi és (CAMP-2)"


@pytest.fixture(scope="module")
def c04():
    try:
        D.neudet_root()
    except D.DesignError as e:
        pytest.skip(f"neudet no és present: {e}")
    try:
        return V.dir_de("c04_draft")
    except V.CampanyaError as e:
        pytest.skip(str(e))


def _copia(c04: Path, tmp_path: Path) -> Path:
    """Una còpia de c04_draft (el nom de la carpeta ha de ser el de la campanya, per als reports)."""
    dst = tmp_path / "c04_draft"
    shutil.copytree(c04, dst)
    return dst


def _provisional(c04: Path) -> dict:
    m = V.manifest_provisional(c04)
    return {k: v for k, v in m.items() if k not in ("provisional", "motiu")}


# ── el provisional, sobre c04 real ──────────────────────────────────────────

def test_provisional_de_c04_te_les_dues_etapes(c04):
    m = V.manifest_provisional(c04)
    assert m["provisional"] is True
    assert m["motiu"] == MOTIU
    assert [e["nom"] for e in m["etapes"]] == ["S1_draft", "S1_draft_g4"]


def test_provisional_motors_i_comptes(c04):
    et = {e["nom"]: e for e in V.manifest_provisional(c04)["etapes"]}
    assert et["S1_draft"]["motor"] == "xarxa B1"
    assert et["S1_draft_g4"]["motor"] == "geant4"
    assert et["S1_draft"]["n_candidats"] == 8
    assert et["S1_draft_g4"]["n_candidats"] == 2
    # el csv de la xarxa té 10 files: les 2 de la cribratge descartades hi són (n_csv), no als 8
    assert et["S1_draft"]["n_csv"] == 10


def test_provisional_g4_verifica_la_xarxa_del_mateix_nom(c04):
    et = {e["nom"]: e for e in V.manifest_provisional(c04)["etapes"]}
    assert et["S1_draft_g4"]["verifica"] == "S1_draft"
    assert et["S1_draft"]["verifica"] is None


def test_provisional_citable_i_figures(c04):
    et = {e["nom"]: e for e in V.manifest_provisional(c04)["etapes"]}
    assert et["S1_draft"]["citable"] is True
    assert et["S1_draft_g4"]["citable"] is True
    assert "etapes/S1_draft/figures/pareto.png" in et["S1_draft"]["figures"]


def test_provisional_judici_report_i_estat(c04):
    m = V.manifest_provisional(c04)
    assert m["estat"] == "draft"
    assert m["judici"] and "No és un resultat de disseny" in m["judici"]
    assert m["judici"].startswith("Flux provat")          # el títol «## Judici» no hi és
    assert m["definicio"] == {"yaml": "campanya.yaml", "md": "DEFINICIO.md"}
    assert m["certificacio"] == "comprova.json"
    pdfs = [r for r in m["report"] if r.endswith(".pdf")]
    assert pdfs == ["docs/site/report/2026-10-26_c04_draft.pdf"]
    assert (V.neudet_root() / pdfs[0]).is_file()


# ── el manifest real guanya ─────────────────────────────────────────────────

def test_el_manifest_real_guanya_i_conserva_camps_extra(c04, tmp_path):
    dst = _copia(c04, tmp_path)
    real = dict(_provisional(dst), generat_per="neudet-test")
    (dst / "campanya_ui.json").write_text(json.dumps(real, ensure_ascii=False), encoding="utf-8")
    m = V.manifest(dst)
    assert m["provisional"] is False
    assert m["generat_per"] == "neudet-test"
    assert V.vista(dst)["provisional"] is False


def test_manifest_sense_un_camp_obligatori_es_rebutja_dient_quin(c04, tmp_path):
    dst = _copia(c04, tmp_path)
    real = _provisional(dst)
    del real["judici"]
    (dst / "campanya_ui.json").write_text(json.dumps(real), encoding="utf-8")
    with pytest.raises(V.CampanyaError, match="judici"):
        V.manifest(dst)


def test_manifest_amb_una_etapa_sense_nom_es_rebutja(c04, tmp_path):
    dst = _copia(c04, tmp_path)
    real = _provisional(dst)
    real["etapes"][0].pop("nom")
    (dst / "campanya_ui.json").write_text(json.dumps(real), encoding="utf-8")
    with pytest.raises(V.CampanyaError, match="nom"):
        V.manifest(dst)


# ── la vista ────────────────────────────────────────────────────────────────

def _etapa(v: dict, nom: str) -> dict:
    return next(e for e in v["etapes"] if e["nom"] == nom)


def _cand(e: dict, nom: str) -> dict:
    return next(c for c in e["candidats"] if c["nom"] == nom)


def test_vista_uneix_csv_i_json_pel_hash(c04):
    v = V.vista(c04)
    s1 = _etapa(v, "S1_draft")
    assert len(s1["candidats"]) == 10
    amb = [c for c in s1["candidats"] if c["amb_tubs"]]
    assert len(amb) == 8
    doc = RES.load(c04 / "etapes" / "S1_draft" / "resultats_tub.json")
    for c in amb:
        assert c["tubs_n"] == len(doc["candidats"][c["hash"]]["tubs"])
    descartats = [c for c in s1["candidats"] if not c["amb_tubs"]]
    assert {c["nom"] for c in descartats} == {"8x11", "8x12"}
    assert all(c["ronda"].startswith("cribratge") for c in descartats)


def test_vista_valors_del_csv_i_rang_pareto(c04):
    s1 = _etapa(V.vista(c04), "S1_draft")
    c = _cand(s1, "8x6")
    assert c["hash"] == "bcc538a35690"
    assert c["eps_mitja"] == pytest.approx(0.402766)
    assert c["cv"] == pytest.approx(0.110407)
    assert c["pareto_rang"] == 0 and c["robusta"] == 1
    assert c["n"] == 2000000
    assert _cand(s1, "8x10")["pareto_rang"] == 4


def test_vista_marca_els_candidats_verificats_a_geant4(c04):
    v = V.vista(c04)
    s1 = _etapa(v, "S1_draft")
    g4 = [{"etapa": "S1_draft_g4", "eps_mitja": 0.463189}]
    assert _cand(s1, "1x3_7x6")["g4"] == g4
    assert _cand(s1, "1x3_7x8")["g4"][0]["etapa"] == "S1_draft_g4"
    assert _cand(s1, "8x6")["g4"] == []
    # els de Geant4 són candidats de la seva etapa, amb les seves dades per tub
    assert all(c["amb_tubs"] for c in _etapa(v, "S1_draft_g4")["candidats"])


def test_vista_no_avisa_de_divergencies_entre_csv_i_json(c04):
    assert not [a for a in V.vista(c04)["avisos"] if "no coincideixen" in a]


def test_pareto_eixos_vénen_de_campanya_yaml(c04):
    p = V.vista(c04)["pareto"]
    assert p["eixos"] == [{"metrica": "eps_mitja", "sentit": "max"}, {"metrica": "cv", "sentit": "min"}]
    assert p["motiu"] is None


def test_pareto_amb_sentit_desconegut_es_rebutja(c04, tmp_path):
    dst = _copia(c04, tmp_path)
    y = dst / "campanya.yaml"
    y.write_text(y.read_text().replace("pareto: [[eps_mitja, max], [cv, min]]",
                                       "pareto: [[eps_mitja, cap], [cv, min]]"))
    with pytest.raises(V.CampanyaError, match="cap"):
        V.vista(dst)


def test_pareto_amb_metrica_que_no_es_al_csv_es_rebutja(c04, tmp_path):
    dst = _copia(c04, tmp_path)
    y = dst / "campanya.yaml"
    y.write_text(y.read_text().replace("pareto: [[eps_mitja, max], [cv, min]]",
                                       "pareto: [[eps_inexistent, max], [cv, min]]"))
    with pytest.raises(V.CampanyaError, match="eps_inexistent"):
        V.vista(dst)


def test_vista_fa_servir_el_csv_si_json_i_csv_no_coincideixen(c04, tmp_path):
    dst = _copia(c04, tmp_path)
    jp = dst / "etapes" / "S1_draft" / "resultats_tub.json"
    doc = json.loads(jp.read_text())
    doc["candidats"]["bcc538a35690"]["pareto_rang"] = 3          # el json diu 3; el csv, 0
    jp.write_text(json.dumps(doc))
    v = V.vista(dst)
    assert _cand(_etapa(v, "S1_draft"), "8x6")["pareto_rang"] == 0
    assert any("pareto_rang" in a and "8x6" in a for a in v["avisos"])


def test_judici_de_pla_sense_seccio_es_null(c04, tmp_path):
    dst = _copia(c04, tmp_path)
    (dst / "PLA.md").write_text("# sense judici\n\n## Un altre\ntext\n")
    assert V.manifest_provisional(dst)["judici"] is None


# ── fitxers ─────────────────────────────────────────────────────────────────

def test_fitxer_dins_de_la_campanya_i_report_llistat(c04):
    assert V.fitxer(c04, "etapes/S1_draft/figures/pareto.png").is_file()
    pdf = V.fitxer(c04, "docs/site/report/2026-10-26_c04_draft.pdf")
    assert pdf.is_file() and pdf.suffix == ".pdf"
    assert V.tipus_de(pdf) == "application/pdf"


@pytest.mark.parametrize("rel", [
    "../../../../../etc/passwd",          # traversal
    "etapes/../../../../x.png",           # traversal dins del camí
    "/etc/passwd",                        # absolut
    "docs/site/report/2026-10-25_cataleg_tubs.pdf",   # report que el manifest no llista
    "campanya.py",                        # tipus no servible
    "",                                   # buit
    "etapes\\..\\..\\x.png",              # barra inversa
    "etapes/S1_draft/figures/nope.png",   # dins però inexistent
])
def test_fitxer_rebutja_el_que_no_es_permet(c04, rel):
    with pytest.raises(V.Prohibit):
        V.fitxer(c04, rel)


def test_fitxer_no_segueix_un_enllac_que_surt_de_la_campanya(c04, tmp_path):
    dst = _copia(c04, tmp_path)
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"\x89PNG")
    (dst / "enllac.png").symlink_to(secret)
    with pytest.raises(V.Prohibit):
        V.fitxer(dst, "enllac.png")


def test_el_manifest_real_de_c04_amb_les_claus_del_6b(c04):
    """neudet 711addf: c04 ja porta campanya_ui.json; les claus del §6b es tradueixen a les de la vista."""
    if not (c04 / "campanya_ui.json").is_file():
        pytest.skip("c04 sense campanya_ui.json")
    m = V.manifest(c04)
    assert m["provisional"] is False and m["flux"] == "jutjada"
    et = {e["nom"]: e for e in m["etapes"]}
    assert et["S1_draft"]["candidats"] == "etapes/S1_draft/candidats.csv" and et["S1_draft"]["dir"] == "etapes/S1_draft"
    assert et["S1_draft_g4"]["verifica"] == "S1_draft" and et["S1_draft"]["verifica"] is None
    assert all(f.startswith("etapes/S1_draft/figures/") for f in et["S1_draft"]["figures"]) and et["S1_draft"]["figures"]
    assert m["definicio"] == {"yaml": "campanya.yaml", "md": "DEFINICIO.md"}
    assert [r.rsplit(".", 1)[1] for r in m["report"]] == ["md", "pdf"]
    v = V.vista(c04)
    assert [len(e["candidats"]) for e in v["etapes"]] == [10, 2]


# ── RESP-UI: el relat de l'etapa (contracte UI §12) ─────────────────────────

def test_vista_etapa_sense_resposta_ho_diu_amb_none(c04, tmp_path):
    d = _copia(c04, tmp_path)
    (d / "etapes" / "S1_draft" / "resposta.md").unlink(missing_ok=True)
    for e in V.vista(d)["etapes"]:
        assert e["resposta"] is None and e["pla"] is None


def test_vista_etapa_amb_resposta_md_porta_el_text_i_la_base(c04, tmp_path):
    d = _copia(c04, tmp_path)
    (d / "etapes" / "S1_draft" / "resposta.md").write_text("# Resposta\n\n![x](resposta/a.png)\n", encoding="utf-8")
    et = {e["nom"]: e for e in V.vista(d)["etapes"]}
    r = et["S1_draft"]["resposta"]
    assert r["md"] == "etapes/S1_draft/resposta.md" and r["base"] == "etapes/S1_draft"
    assert r["text"].startswith("# Resposta")
    assert et["S1_draft_g4"]["resposta"] is None
    assert V.fitxer(d, r["md"]).is_file()


def test_manifest_amb_pla_i_resposta_els_passa_a_la_vista(c04, tmp_path):
    d = _copia(c04, tmp_path)
    m = _provisional(c04)
    (d / "notes.md").write_text("relat", encoding="utf-8")
    m["etapes"][0]["pla"] = "Per què: perquè sí"
    m["etapes"][0]["resposta"] = "notes.md"
    (d / "campanya_ui.json").write_text(json.dumps(m), encoding="utf-8")
    e = V.vista(d)["etapes"][0]
    assert e["pla"] == "Per què: perquè sí" and e["resposta"]["text"] == "relat"


def test_manifest_amb_resposta_que_no_hi_es_diu_quina_etapa(c04, tmp_path):
    d = _copia(c04, tmp_path)
    m = _provisional(c04)
    m["etapes"][0]["resposta"] = "no_hi_es.md"
    (d / "campanya_ui.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(V.CampanyaError, match=m["etapes"][0]["nom"]):
        V.vista(d)


def test_el_csv_de_l_etapa_es_servible(c04):
    assert V.fitxer(c04, "etapes/S1_draft/candidats.csv").is_file()
    assert V.tipus_de(Path("candidats.csv")).startswith("text/csv")
