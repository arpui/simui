# simui — instruccions de projecte

La consola web de simphy i neudet (abans `simphy.ui` + `simphy.mcgen.campanya_*`). Llegeix `README.md` i `docs/ui.md`.

## El principi

**La UI no calcula res: crida neudet i simphy.** Cap dada de neudet ni de simphy no es copia aquí: es llegeix (neudet
per `NEUDET_ROOT`, simnet per `SIMNET_ROOT`, simphy com a paquet instal·lat en editable). Si una cosa s'ha de calcular,
va a neudet o a simphy, no aquí. Els errors de neudet es mostren tal com són.

## Entorn

- `simphy` instal·lat amb `pip install -e ~/projects/simphy` (no una còpia): `simphy.mcgen.paths.repo_root()` ha de
  ser l'arrel de simphy, o `detector_config`, `mc_sources` i `results_simphy` busquen al lloc equivocat sense dir res.
- `NEUDET_ROOT=~/projects/neudet`, `SIMNET_ROOT=~/projects/simnet` (opcional `NEUDET_PYTHON`).
- Arrencar: `python scripts/serve.py` (http://127.0.0.1:8765). Tests: `python -m pytest -q`.

## Convencions (les de simphy)

- **MAI INVENTIS.** Si una dada no hi és, peta amb un missatge que digui on buscar-la.
- **Test bessó:** cada check bloquejant de la UI té un test que verifica que la plantilla (el c04_draft de neudet) el
  satisfà; les referències `fitxer:línia` a neudet han de ser les reals (si neudet es mou, el test les segueix).
- Quan dues fonts es contradiuen, la divergència queda escrita amb un test que la fixa.
- Tot en català. A neudet i simnet no s'hi escriu des d'aquí (només per les seves ordres, p. ex. `desa_proposta`).
