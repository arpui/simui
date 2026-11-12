# UI-X06 — les etapes apartades per neudet, marcades (2026-11-12)

**Decisió de l'Albert:** «Marca-les» (no amagar-les). **Commit:** `5e3339e` (marcar pel camp) i `6309a42`
(retolador separat de la provenança).

**De on es treu:** el camp **`etapes[].anterior`** del `campanya_ui.json` de neudet. Mai el nom de la carpeta:
la pàgina no conté cap literal `_anterior_`/`_aturada_` (fixat per test).

**Comprovació en viu** (preview amb `NEUDET_ROOT=~/projects/neudet`, campanya real `c0b_2t0611`): el que va
donar la pàgina, element per element (capçalera de cada targeta d'etapa):

```
S1                        :: xarxa | citable
S1_anterior_2026-11-08    :: xarxa | intent anterior (apartat; no l’useu com a resultat) | provenança: citable
S1_anterior_2026-11-08_2  :: xarxa | intent anterior (apartat; no l’useu com a resultat) | provenança: citable
S1_g4                     :: geant4 | no citable
```

i la línia de dades de `S1`: `7 candidats · 9 energies · 2 intents anteriors apartats`.

Sota `S1_anterior_2026-11-08` hi surt **el motiu de neudet** (`aturada.text`), text literal:

> La font iso era a z = -40 cm, exactament sobre la cara del bloc (mig bloc = 40 cm). El 100 % dels primaris
> queden vius en esgotar els passos (200 000) i les eficiències no són físiques. Aturada a posteriori: la porta
> de vius (FONT-A) encara no existia.

`S1_anterior_2026-11-08_2` no en diu res de nou: el seu `aturada` és `null` i la UI no n'inventa cap.

**Dos eixos, no un:** el manifest posa `citable: true` a les dues apartades (a neudet `citable` és
*provenança neta*, `provenance.is_clean`), mentre `anterior: true` vol dir *apartat com a intent*. Per això la
pàgina pinta el retol de l'intent apartat i, a part, «provenança: citable». La vista no reescriu cap dada de
neudet.

**Captura:** [`etapes-apartades.jpg`](etapes-apartades.jpg) — la targeta de `S1_anterior_2026-11-08` amb el
retol vermell i, a sota, el motiu de neudet.

**Proves:** `tests/test_ui_etapes_anteriors.py` (6). Inclou executar amb node el `kEtapa` de la pàgina sobre
les quatre etapes reals, que una `anterior: true` mai surti sense retolador, que cap apartada quedi marcada
com a citable, i que **sense el camp** (campanya sense manifest o neudet vell) no es marqui res — encara que
la carpeta se digui `…_anterior_<data>`.

**El que queda esperant:** a **F2** (llista d'etapes d'un mateix hash) les entrades vénen de
`results_tub.for_design` de simphy i no porten `anterior`; el coordinador ho ha encarregat a simphy (claus
`anterior` i `motiu_aturada`, contracte **v1.20**). Quan sigui a `main` es fa el retolador d'F2 amb el seu bessó.
