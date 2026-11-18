# MOTORS-UI — resultat (2026-11-18)

Encàrrec: `~/projects/neudet/docs/site/encarrecs/2026-11-18_MOTORS_UI.md` (del coordinador, aprovat per Albert).
Contracte: `simphy_ui.md` **§26** (v1.23). La UI no calcula res: llegir `avaluacio.motors` (form),
`comprova.json → avisos_en_paraules` (límits en paraules) i `etapes/<E>/comparacio_motors.json` (comparació), i servir-ho tal com és.

## ⚠️ Les dades d'aquesta prova són **fixtures**, no execucions reals de neudet

**SALTS-B encara no ha escrit cap `comparacio_motors.json` de veritat** (a `~/projects/neudet` no n'hi ha cap).
Per provar la vista he muntat un arrel de neudet de prova a `/tmp/motors_proves/neudet` (còpia d'hardlinks
de `~/projects/neudet`, amb les campanyes reals com a symlinks — mai escric a neudet) i ** dues campanyes
fixture** que segueixen §26 al peu de la lletra:

- `m04_motors_prop` — yaml amb `avaluacio.motors: [B1, salts, openmc_gpu]` i un `comprova.json` amb dos
  `avisos_en_paraules` (un amb el sufix « Atura la campanya.», un d'informatiu).
- `m04_motors_view` — etapa declarada `S1_draft` amb `comparacio_motors.json` (3 motors: `salts`
  **no aplicable** amb motiu; `coincideix_guanyador: false`; `g4.per_motor` amb `err_rel_max` i `taula`)
  i les carpetes `etapes/S1_draft/motors/B1/` i `…/openmc_gpu/` amb `candidats.csv` (còpia de l'execució real de c04).

Els fitxers de la fixture són a prop: `fixture-comparacio_motors.json`, `fixture-comprova.json`.
Quan neudet (SALTS-B) escrigui el primer `comparacio_motors.json` real, la vista el mostrarà sense canvis —
els tests bessó són sobre fixture precisa per no dependre d'ells.

## Com es va mirar

Servidor `scripts/serve.py` a `127.0.0.1:8799` amb `NEUDET_ROOT=/tmp/motors_proves/neudet`, pàgines
obertes amb **Chrome headless** (`--virtual-time-budget`, precedent UI-COSSOS; no hi ha Playwright a la
màquina). Les captures senceres: `pagina-completa-formulari.png`, `pagina-completa-etapa.png` (1500×4400).
El text exacte que la pàgina va produir, del DOM (`--dump-dom`):

Formulari (`#neudet/m04_motors_prop`):
- Selector amb una casella per motor del contracte: `data-motor="B1"`, `data-motor="salts"`, `data-motor="openmc_gpu"`; totes tres marcades.
- Pista: «Marcats: B1 · salts · openmc_gpu — un cop executada la campanya, la comparació surt a la pàgina de l'etapa.»
- Panell vermell amb els avisos de neudet **en paraules**, amb ⛔ el de parada:
  «⛔ motor «salts»: el nucli salts només cobreix PE 0,94 amb E ≤ 5 MeV; la graella de la campanya arriba a 6 MeV. Atura la campanya.»
  i l'informatiu «motor openmc_gpu: aquesta màquina no té GPU per a OpenMC: a la comparació sortirà «no aplicable».».

Vista d'etapa (`#neudet/m04_motors_view`):
- Veredicte: «Els motors NO coincideixen en el guanyador» (panell vermell, perquè `coincideix_guanyador: false`).
- El motor no aplicable **no desapareix**: surt la seva columna amb «no aplicable» i el motiu de la fixture
  («…el nucli salts no cobreix PE 0,94 per sobre de 5 MeV»).
- Columnes per motor amb temps (s), FOM mitjana, Pareto i error contra G4; cada columna enllaça la vista
  normal de `motors/<motor>/` (`data-kvopen="S1_draft · B1"`, `…· openmc_gpu`).
- Sense `comparacio_motors.json`, l'etapa es pinta com la vista d'avui (encàrrec, punt 3).

## Tests bessons

`tests/test_motors_ui.py` — 12 proves: la vista serveix `comparacio_motors.json` **tal com és**; una variant
per motor amb `candidats.csv`; motor declarat sense carpeta ⇒ avís amb el camí; json malformat ⇒ avís, no error;
el cens no declarats no rep variants; el selector ve del contracte (bessó: `_troba`/`_linia` sobre
`simphy_ui.md:856` — si neudet mou o canvia §26, el test ho diu); `to_yaml` conserva `avaluacio.motors` i
sense la clau dona el yaml d'avui; noms fora de llista rebutjats; el sufix « Atura la campanya. » bessó de
`scripts/disseny/comprova_campanya.py:149`; guards de l'INDEX (selector, escriptura només amb ≥2 marcats,
comparació a la pàgina d'etapa).

Suite completa: **541 passed** (`python -m pytest -q`, 2026-11-18).

## Pendent deixat al coordinador

- La convenció de `g4.per_motor.<motor>.taula` (he assumit camí **relatiu a la carpeta de campanya**) i el
  text dels avisos de límit per motor (els escriurà neudet amb SALTS-B) s'han de fixar a COORDINACIO §5;
  mentre no hi siguin, la UI no n'inventa cap.
