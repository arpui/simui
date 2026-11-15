"""Guardó de sintaxi de la pàgina: cada bloc `<script>` d'`index.html` ha de ser JS vàlid.

El 15-11, amb la suite sencera en verd dues vegades, la pantalla de campanya sortia **en blanc** amb
«kEntreHtml is not defined»: un `<script>` sencer havia deixat de parsejar-se perquè un condicional
dins d'una plantilla anidada es tancava sense `: ''` (`${m3 ? `...`}`), i aleshores cap funció del
bloc existia a la pàgina. Els miralls de node (test_ui_etapes_anteriors, test_etiq_no_decl, test_cost_ui…)
tallen funcions concretes: no miren el bloc sencer, i un error fora del tros tallat passa **fluix**.
Aquest test no espera cap funció concreta: passa `node --check` a cada bloc, sencer, tal com el
llegirà el navegador.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "src" / "simui" / "static" / "index.html").read_text(encoding="utf-8")


def test_tots_els_blocs_script_de_index_html_són_javascript_vàlid(tmp_path):
    if shutil.which("node") is None:
        pytest.skip("cal node")
    blocs = re.findall(r"<script>(.*?)</script>", INDEX, flags=re.S)
    # que l'extracció no es quedi en silenci sense blocs: `<script>` amb atributs (src=…) no en tenim cap
    assert blocs, "l'extractor no troba cap bloc <script>: la pàgina ha canviat de forma"
    assert INDEX.count("<script") == len(blocs), (
        f"hi ha {INDEX.count('<script')} obertures de <script> però {len(blocs)} blocs agafats: "
        "l'extractor se'n deixa alguno (bloc amb atributs?)")
    for i, codi in enumerate(blocs, 1):
        f = tmp_path / f"bloc{i}.js"
        f.write_text(codi, encoding="utf-8")
        r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
        linia = INDEX[:INDEX.find(codi)].count("\n") + 1 if codi else 0
        assert r.returncode == 0, (
            f"el bloc <script> nº{i} de la pàgina (línia ~{linia}) no és JavaScript vàlid:\n{r.stderr}")
