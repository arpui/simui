# simui

La consola web de **simphy** i **neudet**: el formulari de «Definició de campanya», la vista de campanyes i
candidats, el visor de dissenys i la pestanya «Genera» (un JSON → FLUKA, MCNP, OpenMC i Geant4).

Ve de `simphy` (`src/simphy/ui/`, `scripts/ui/serve.py` i `src/simphy/mcgen/campanya_*.py`), extret amb la seva
història (`git filter-repo`, UI-REPO-F2, 2026-11-09). Es va moure tal com era: només han canviat imports i camins.

## La regla

**La UI no calcula res: crida neudet i simphy.** Les geometries, els materials, la validesa dels candidats, els
objectius, la certificació i els resultats són de neudet o de simphy; aquí només es demanen i es mostren (els
errors de neudet arriben verbatim).

## Instal·lació

```bash
pip install -e ~/projects/simphy        # editable: obligatori (simphy.mcgen.paths.repo_root() n'ha de ser l'arrel)
pip install -e ~/projects/simui
export NEUDET_ROOT=~/projects/neudet    # neudet es llegeix d'aquí (mai per còpia)
export SIMNET_ROOT=~/projects/simnet    # per llistar els ckpts (diagnòstic)
# opcional: NEUDET_PYTHON (el Python que corre comprova_campanya.py, amb torch)
```

## Arrencar i testejar

```bash
python scripts/serve.py                 # http://127.0.0.1:8765  (--host, --port, --restart)
python -m pytest -q                     # amb NEUDET_ROOT i SIMNET_ROOT definits
```

Història i decisions de la UI: `docs/ui.md` (escrit quan vivia a simphy: els camins que cita són els d'abans).
