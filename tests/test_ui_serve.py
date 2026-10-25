"""La consola web (`scripts/ui/serve.py`) no pot dir una cosa diferent de `gen.py`.

Totes dues passen per `factory.retarget` → `validate` → `render`. Aquest fitxer
ho comprova igualment, exemple per exemple i codi per codi: si algun dia una de
les dues s'aparta del camí comú, salta aquí.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import threading
import urllib.request
from pathlib import Path

import pytest

from simphy.mcgen import core

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((ROOT / "src/simphy/mcgen/examples").glob("*.json"))


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ui():
    return _load("simphy_ui_serve", "scripts/ui/serve.py")


@pytest.fixture(scope="module")
def gen():
    return _load("simphy_gen_cli", "scripts/mcgen/gen.py")


def _gen_outcome(gen, path: Path, backend: str):
    """(True, fitxers) si `gen.py --print` escriu, (False, None) si rebutja.

    Un rebuig de `gen.py` és un codi de sortida != 0 o una excepció del paquet
    (`OpenmcError` hi arriba com a traceback: la pàgina la converteix en rebuig
    amb motiu, i aquí compta igual).
    """
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = gen.main(["--spec", str(path), "--backend", backend, "--print"])
    except (ValueError, RuntimeError, KeyError):
        return False, None
    if rc != 0:
        return False, None
    files, name, buf = {}, None, []
    for line in out.getvalue().splitlines(keepends=True):
        if line.startswith("===== ") and line.rstrip().endswith(" ====="):
            if name is not None:
                files[name] = "".join(buf)
            name, buf = line.strip()[6:-6], []
        else:
            buf.append(line)
    if name is not None:
        files[name] = "".join(buf)
    return True, files


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_la_pagina_i_gen_py_donen_el_mateix(ui, gen, path):
    raw = json.loads(path.read_text())
    for r in ui.render_all(raw):
        ok, files = _gen_outcome(gen, path, r["backend"])
        assert (r["status"] == "ok") == ok, (
            f"{path.stem} → {r['backend']}: la pàgina diu {r['status']!r} "
            f"i gen.py {'escriu' if ok else 'rebutja'}. {r['messages']}")
        if ok:
            assert r["files"] == files, f"{path.stem} → {r['backend']}: decks diferents"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_cap_rebuig_sense_motiu_ni_excepcio_no_prevista(ui, path):
    """Un rebuig sense motiu, o un `error` (excepció no prevista), és un forat."""
    for r in ui.render_all(json.loads(path.read_text())):
        assert r["status"] in ("ok", "rejected", "invalid"), (path.stem, r)
        if r["status"] != "ok":
            assert r["messages"] and all(m.strip() for m in r["messages"]), (path.stem, r)


def test_els_desplegables_son_les_tuples_de_core(ui):
    """Una definició: si algú escriu una llista a mà a la pàgina, això salta."""
    v = ui.meta()["vocab"]
    assert v["backends"] == list(core.BACKENDS)
    assert v["particles"] == list(core.PARTICLES)
    assert v["geometry_kinds"] == list(core.GEOMETRY_KINDS)
    assert v["axes"] == list(core.AXES)
    assert v["source_kinds"] == list(core.SOURCE_KINDS)
    assert v["scoring_kinds"] == list(core.SCORING_KINDS)
    assert v["tally_quantities"] == list(core.TALLY_QUANTITIES)


def test_el_detector_als_quatre_codis(ui):
    """El cas de la presentació: dos decks i dos rebuigs amb l'alternativa."""
    raw = json.loads((ROOT / "src/simphy/mcgen/examples/un_perp_detector.json").read_text())
    got = {r["backend"]: r for r in ui.render_all(raw)}
    assert got["mcnp"]["status"] == "ok" and got["fluka"]["status"] == "ok"
    assert got["openmc"]["status"] == "rejected"
    assert "MCNP (F8)" in got["openmc"]["messages"][0]
    assert got["geant4"]["status"] == "rejected"


def test_http_de_punta_a_punta(ui):
    srv = ui.make_server("127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{port}"
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "Una petició, quatre codis" in page
        # La query la llegeix la pàgina: el servidor no la pot confondre amb un camí.
        assert urllib.request.urlopen(base + "/?ex=pe_sphere").read().decode() == page
        m = json.loads(urllib.request.urlopen(base + "/api/meta").read())
        assert m["vocab"]["particles"] == list(core.PARTICLES)
        spec = m["examples"]["un_perp_detector"]
        req = urllib.request.Request(base + "/api/render", method="POST",
                                     data=json.dumps({"spec": spec}).encode(),
                                     headers={"Content-Type": "application/json"})
        res = json.loads(urllib.request.urlopen(req).read())["results"]
        assert [r["backend"] for r in res] == list(core.BACKENDS)
    finally:
        srv.shutdown()
        srv.server_close()
