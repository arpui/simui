# La UI de simphy (consola web)

**Estat (2026-10-26):** dues pestanyes: **Simulació** (la de la demo) i **Neudet**. Neudet té tres
nivells dins la mateixa pantalla: campanyes (llista + formulari de proposta o vista), el full d'un
candidat (visor, resultats per tub, Tanteja, inputs dels quatre codis) i el disseny solt («Obre un
disseny»: fonts, editor d'anells, comparació). Els enllaços antics (`#campanya`, `#campanyes`,
`#disseny`, `#resultats`) obren el nivell que els tocava. Pendent: U6, la prova a railab amb el model local.

```bash
python scripts/ui/serve.py              # http://127.0.0.1:8765  (--host, --port)
# Agents: proveu sempre amb http://127.0.0.1:8765 (permès sense preguntar a .claude/settings.json); l'IP de la xarxa (192.168.…) és només per a Albert.
```

## D'on surt

Es va fer per a la demo del 2026-09-26 al checkout principal de railab i **no es va
pujar mai a git**. Es va recuperar tal com era en dos passos:

- `docs/site/proves/2026-10-26_recupera_ui.md`: `scripts/ui/serve.py`, copiat byte a byte.
- `docs/site/proves/2026-10-26_recupera_ui_2.md`: el que la UI necessitava i també era
  sense commit. Són 18 fitxers modificats i 15 de nous: `factory.retarget`,
  `agent/assess.py`, `readiness.py`, els seus tests i `tests/test_ui_serve.py`.

El pedaç s'aplica sense conflictes sobre la branca de desenvolupament. A railab, un test
de la UI fallava (`mcnp` rebutjava `un_perp_detector`); aquí passa. Si torna a fallar
a railab, el sospitós és l'entorn (biblioteques de MCNP), no la UI.

## Com està feta

| peça | què fa |
|---|---|
| `src/simphy/ui/api.py` | el que la pàgina demana: `meta`, `render_one`, `render_all`, `llm_status`, `ask` |
| `src/simphy/ui/server.py` | `http.server` de la stdlib; rutes `/`, `/api/meta`, `/api/llm`, `/api/render`, `/api/ask` |
| `src/simphy/ui/static/index.html` | la pàgina, sense passos de construcció |
| `scripts/ui/serve.py` | només l'arrenca |
| `tests/test_ui_serve.py` | la pàgina i `gen.py` donen el mateix, exemple per exemple i codi per codi |

**La regla que la manté prima:** la UI **importa, no implementa**. Les opcions, els
materials, els detectors i el resultat surten de `mcgen`. Si cal escriure una línia de
física, va a `src/simphy/mcgen/` amb el seu test. Sense dependències externes.
No executa simulacions ni escriu fitxers.

## Pestanyes

```
 ┌──────────────┬──────────────────────────────────────────────────────────┐
 │ Simulació    │ Neudet: campanyes · full del candidat · disseny solt     │
 └──────────────┴──────────────────────────────────────────────────────────┘
```

### 1 · Simulació (la consola actual)

Un formulari o un prompt genera un `SimRequest` i en surten els decks dels quatre codis,
amb el `lint` i, quan cal, el rebuig amb el motiu. No canvia.

### 2 · Disseny de detectors (F1)

Les tres entrades porten al mateix **JSON de disseny** (`src/simphy/mcgen/design.py`):

- **prompt** en paraules (`agent/design_prompt.py`, el que es va provar a P4);
- **per defecte o de campanya**: es carrega c03 o el `campanya.yaml` de neudet, i es pot
  editar amb el formulari dels anells (r, n, φ, tipus, z, Cd) o directament el JSON;
- **un `.dat` de neudet** (`design.from_neudet`).

A cada canvi:

1. es verifica (`design.violations`, que crida `neudet.disseny`) i es veuen els errors;
2. es redibuixa el visor XY/XZ (`design_view`);
3. es poden baixar el `.dat` i el `.json` de neudet (bit a bit) i els decks dels 4 codis.

**«Tantejar»** vol dir partir d'un disseny, retocar-lo (moure un anell, canviar un tub)
i veure'l al costat de l'original: les dues geometries i les violacions de cadascun.

Rutes previstes: `/api/design/meta` (campanyes i tipus de tub del catàleg),
`/api/design/check`, `/api/design/view`, `/api/design/export`, `/api/design/ask`.

**Abans cal un pas:** la lògica de decks del disseny és a `scripts/mcgen/design.py`. Ha
de passar a `src/simphy/mcgen/` perquè la UI la pugui importar.

### 3 · Resultats (F2)

Es llegeixen els resultats d'un disseny, **sense calcular-los ni copiar-los**:

- de **neudet**: comptes i ε per tub, Pareto de la campanya, fitxes de referència;
- de **simphy**: les tirades dels quatre codis, quan n'hi hagi, en el format comú de F2.

Al visor, cada tub es pinta pel seu valor (ε o comptes). Al costat hi ha la taula per
tub i per codi, amb la provenance de cada xifra. **Una xifra sense provenance no es mostra.**

Dependència: **F2 és el format comú de resultats per tub**, i l'ha de fixar neudet. Fins
llavors, aquesta pestanya només pot llegir el que neudet ja publica.

### 4 · Estructura de l'etapa: tongades (GEN-U-UI, contracte v1.3 §10)
Una etapa és una o més **tongades**; cada una és **on són els tubs × què són els tubs → quins candidats es proven**.
- **On són els tubs** (font): `punts` (posicions fixes x, y, z), `malla` (quadrada, hexagonal o polar; `k` tubs per candidat, k = 1 és un tub a cada punt),
  `anells` (r, n, φ: valor, llista o rang) o `dat` (un candidat fix). Un punt o un anell pot tenir «atributs propis» que sobreescriuen els de la tongada.
- **Què són** (tipus, Cd, eix): un valor o un ventall; amb ventall, el `lligam` (global, grup o tub) diu com varia dins del candidat. La UI posa «global» quan un
  atribut passa a tenir diversos valors (la fitxa l'exigeix explícit).
- **Quins es proven:** exhaustiu, o `mostres` a l'atzar amb llavor; `max_candidats` (0 = sense límit).
- Diverses tongades per etapa (p. ex. una malla i uns anells): se sumen. El recompte de cada una és el de neudet (`generadors.recompte_etapa`): la UI no
  expandeix ni compta. «Comprova» afegeix, per tongada, generats, repetits, vàlids i descartats.
- **Yaml antics:** un `generador` (c01–c04) s'obre com a `tongades`, traduït per neudet (`tradueix_antic`): mateixos candidats i hashes (proves a `tests/test_flex_ui.py`).
  El yaml que s'hi desa porta `tongades`, sense els camps interns de la traducció.
- **Vista dels tubs:** el bloc de PE amb la font i, per cada tongada (un color), una combinació dels tubs; a `punts` es poden arrossegar. Orientativa (mida dels
  tubs no a escala); no valida res: ho fa «Comprova».
- **Tubs girats** (`eix` x o y): el visor els dibuixa com a rectangle a XY i, al tall XZ, com a franja (eix x) o cercle (eix y); la taula afegeix la columna «Eix».
  MCNP, OpenMC i FLUKA de simphy **refusen** els tubs girats (`exigeix_tubs_drets`); els fan Geant4 (app `detector`) i el motor de neudet.
- Proves: `tests/test_flex_ui.py`.

## Fora d'abast, de moment

- **Llançar simulacions des de la UI.** Les tirades llargues passen per runbooks a
  railab. Una cua des de la UI és una decisió a part (cost, seguretat).
- **Accés compartit.** Per defecte només la màquina local (`--host 127.0.0.1`). Obrir-la
  a la xarxa demana autenticació, i no n'hi ha.

## Resposta d'etapa i formulari congelat (RESP-UI, contracte v1.4 §11b i §12)
A la pàgina d'una campanya que no és proposta, cada etapa mostra: el `pla` del manifest («Per què aquesta etapa»), la resposta
(`resposta` del manifest o, si no hi és, `etapes/<etapa>/resposta.md`) renderitzada amb figures i taules, i enllaços a
`candidats.csv`, `resultats_tub.json` i `meta.json`. Si l'etapa no té resposta, ho diu. «Veu el formulari (congelat)» obre
el `campanya.yaml` amb el mateix formulari de definició, sense editar ni desar (només es pot triar l'etapa), i la certificació
de neudet al costat. La UI no en calcula res. El resum de la petició (§11b) hi surt quan neudet l'afegeixi al `comprova.json`.

## Inventari de tubs (INV-UI, contracte v1.6 §10b)
Cada tongada de punts, malla o anells tria «Quins tubs hi ha»: **cada anell o punt diu el seu tipus** (com fins ara) o **un inventari de
tubs disponibles** (`inventari: {tipus: quantitat}`; tots s'hi fan servir, el total és el nombre de tubs). Amb inventari, a cada anell
o punt hi ha «tipus permesos» (tots marcats = sense restricció), la malla té `k` = total i els anells no porten `n_total`. El comptador
«assignats / total» avisa quan no quadra. El recompte surt de neudet; a les tongades amb inventari porta també la simetria
(abans → després, en paraules) i l'`avis` de `max_candidats` si cal triar `mostres`. El formulari ja no escriu `domini.tipus_tub`
(neudet el deriva dels tipus de les tongades), excepte en un yaml antic on alguna tongada deixa el tipus al domini: treure'l canviaria
els hashes.

## Vista lateral i dimensions del tub (VISTA-UI)
El visor del formulari mostra **alhora** (VISTA-3, sense desplegable) **de dalt (x, y) · lateral (x, z) · lateral (y, z)**, una al costat de l'altra (en pantalla estreta, una sota l'altra). Les vistes laterals dibuixen el bloc, el forat,
la font i cada tub (llargada total, clar, i zona activa, fosc) a la seva z; un tub d'eix horitzontal és un rectangle si és al pla de la
vista i un cercle si el travessa. Al full d'un candidat, el selector tria entre el tall XZ (y = 0) i el YZ (x = 0), que genera el
servidor (`design_view._svg_xz(v, "yz")`, girant x↔y). Al costat de cada selector de tub surten les mides aproximades
(Ø, llargada activa / total, pressió, paret), llegides de `tubs.json` i `tubGeneric.cc` per `campanya_form._mides_tub`.

## Resum, interpretació i confirmació (CONF-UI, contracte §13)
- **Formulari:** «Què vull saber» per etapa (`etapes.<e>.pregunta`) i el botó «Desa la proposta» / «Modifica la proposta».
- **Després de desar, i a la pàgina de la campanya:** el `resum_text` de neudet (pregunta, candidats per tongada, cribratge, frontera, Geant4, cost, avisos), tal com és.
- **Pàgina de campanya:** l'estat que diu neudet (`comprova.json.confirmacio`: si es pot córrer o no), el resum, la interpretació del planificador
  (`interpretacio` del manifest, el `PLA.md`) i, per a cada etapa declarada que encara no ha corregut, el seu «Per què».
- **Confirmar i congelar:** només amb l'estat `interpretada`. `POST /api/campanya/confirma {id, per}` crida `neudet.disseny.confirmacio.confirma`
  (escriu `confirmacio` amb hash del yaml i del PLA i `estat: confirmada`); la UI no calcula cap hash. El motiu d'un refús és el de neudet.
  Si després es toca el yaml o el PLA, neudet exigeix reinterpretar i reconfirmar.

## Afinar el formulari (UI-AFINA)

- **Un sol dibuix, sempre visible.** Les tres vistes (XY · XZ · YZ) són a dalt del formulari i s'hi queden mentre es baixa (`position: sticky`); ja no n'hi ha un segon dins de l'etapa. Amb recursos, dibuixa una **configuració d'exemple a l'atzar** (llavor `CP.llavor`): primer els tubs **fixats** de cada anell, després els anells de n fix, i els que queden van a anells lliures respectant els **tipus permesos**; a «punts» un tub per punt, a la malla k llocs triats. El color és del **tipus** de tub (el mateix a les tres vistes i a la llegenda), hi ha el text «exemple, no és cap candidat» i el botó **una altra**. Es refà a cada canvi del formulari. Un lloc sense tub (els possibles d'una malla) es dibuixa tènue.
- **La font no es mou per accident:** només s'arrossega amb el botó **mou la font** (queda marcat en vermell mentre és actiu); la posició es veu sempre en números.
- **Després de desar:** el botó passa a «Modifica la proposta» a l'acte, surt l'avís **⏳ Esperant resposta de neudet…** i la llista es refresca sola cada 30 s; quan la campanya deixa de ser `proposta`, apareix «Veu la interpretació i confirma». També passa en obrir una proposta que encara no ha estat interpretada.
- **`verificacio.hits`** és editable (`all` / `detect`): és l'únic camp de verificació que neudet llegeix. `quants` i `n_per_energia` segueixen de lectura (veure AFINA-N de neudet).
- **`que:`** és una nota de l'usuari, no la pregunta: una proposta nova no hereta el `que:` de la plantilla (`cSenseQue`), i el camp es diu «nota teva (opcional; NO és la pregunta)».
- **Punts amb posició variable (PUNTS-V de neudet):** a cada punt, x, y i z són **un valor, una llista o un rang** (de–a amb pas); l'eix és per punt. El dibuix en tria una combinació; només s'arrossega un punt amb x, y, z fixos. El formulari valida amb `_errors_rang`, com els anells.
- **Cost gran (AFINA-N):** si `comprova.json` porta `opcions_cost`, es mostra en vermell «massa gran per a un tanteig» amb les opcions tal com les dona neudet. **Encara no n'hi ha cap a neudet** (el format no està escrit al contracte): la UI mostra el que arribi, sense inventar-ne les claus.

### Dibuix a escala i mides reals dels tubs
- **Mides reals:** la llargada total d'un tub és la que neudet fa servir per col·locar-lo (`candidat.DIMS`: radi exterior i extensió en z de TOT el tub; 68 cm el LND-252285), no la de la paret d'acer (63,72) ni la del gas actiu (60). El selector diu «TUB SENCER Ø × L cm (el que ha de cabre) · gas actiu · paret · pressió» i la llegenda del dibuix porta les mateixes mides.
- **Una escala:** XY, XZ i YZ es dibuixen amb els mateixos px per cm (`cVistaDims`: `D.k`), i cada una porta les cotes del bloc. El text sota els dibuixos diu «1 cm = X px». El full del candidat (dibuix del servidor, `design_view.py`) encara té l'escala de cada vista pel seu compte.

### Escala comuna al full del candidat i visor 3D (VISTA-3D)
- **Full del candidat:** XY, XZ i YZ surten amb els mateixos px per cm (`design_view.escala_comuna`, la mínima de les tres), amb el bloc escrit a cada vista («bloc 30 × 30 × 80 cm · 1 cm = 5,66 px») i les cotes de sempre (eixos amb marques i barra de 10 cm). La pàgina les encongeix TOTES amb un sol factor si no hi caben (`dEscalaComuna`).
- **Visor 3D isomètric** (formulari i full, el mateix codi `v3dSvg`, SVG pla sense llibreries): bloc, forat, font, eixos x/y/z i cada tub com a cilindre a mida real (clar: el volum que ocupa; fosc: el gas actiu), amb el seu eix. Es gira arrossegant i el doble clic restableix. L'escena és dades: `cEscena` al formulari i `design_view.escena` al servidor (`escena` al `preview`).
- **El dibuix enganxat a dalt** només s'enganxa en finestres grans (≥ 1000 × 760 px); en una de petita, les vistes apilades taparien el formulari.
