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
