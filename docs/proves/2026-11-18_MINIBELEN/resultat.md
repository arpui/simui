# MINIBELEN · resultat simui (2026-11-19)

Encàrrec: `~/projects/neudet/docs/site/encarrecs/2026-11-18_MINIBELEN_cas.md`, secció **simui** (del coordinador, aprovat per
Albert). Fitxa: `~/projects/neudet/disseny/casos/minibelen/README.md` (base 10B; els §5 i §6 manen). Campanya: `mb10b_ref`.

## Què demanava i com queda

1. **«Que l'esborrany `mb10b_ref` s'obri al formulari amb els PENDENT visibles (en vermell, amb el text de neudet) i es pugui
   completar per blocs.»** **No funcionava tal com estava**: tres defectes, trobats i corregits (avall). Ara provat al navegador
   (Chrome headless, DOM) i fixat amb bessons: `tests/test_minibelen_ui.py` (6 proves) i
   `test_un_bloc_sense_mides_queda_declarat_no_inventat_i_no_cassa` a `tests/test_cossos_ui.py`. Suite: **548 passed**.
   El «text de neudet» del vermell és literalment el motiu del seu `to_yaml` (la UI no en posa cap de seu).
2. **«Captura de cada pas del §4.»** Aquí avall, amb el matís honest: **la feina 1 de neudet (l'esborrany `mb10b_ref`) encara no
   s'ha executat** — no existeix ni a l'arbre de neudet (`3d6d2bd`) ni a `origin/main` (`c5be77f`). Les captures són sobre la
   **fixta de simui** (`fixta-mb10b_ref.yaml`, faithful als §5/§6 i marcada com a fixta dins seu). Quan l'esborrany real arribi,
   la prova es repeteix sense canvis de codi.

## Defectes trobats i corregits (`src/simui/static/index.html`)

1. **L'error de llista no marcava els camps.** `cErr` feia coincidència exacta: l'error `-domini.bloc.mides_cm: …` no
   arribava als inputs `domini.bloc.mides_cm.0/1/2` — només el panell de dalt es posava vermell i els camps pendents quedaven
   tranquils. Ara el grup sencer es marca (`el.dataset.p.startsWith(camp + '.')`) i el motiu es diu **una sola vegada**.
2. **Un valor de text feia cassar la pàgina sencera.** `mides_cm: "PENDENT…"` → `E.m.map is not a function` (peu del dibuix
   :1250 i escena :1431): el formulari no s'arribava a pintar. Ara `cBlocExt` només passa una llista al dibuix i els inputs
   numèrics no es vessen; `to_yaml` refusa el text en paraules i prou.
3. **El més greu: el dibuix s'inventava les mides.** Amb `mides_cm` absent o null es pintava «bloc cub 30 × 30 × 80 cm» com si
   fos la teva geometria, **sense cap avís**: `sense` es calculava sobre el valor de reemplac (sempre vàlid), no sobre l'escrit.
   Això trencava **MAI INVENTIS** pel §4.2. Ara `sense` llegeix el que hi ha escrit i surt l'avís de §22
   «el dibuix és orientatiu, no és la teva geometria (§22: aquestes mides no tenen valor per defecte)».

## Captures del §4 (fixta; com reproduir-ho, al final)

| Fitxer | Pas | Què s'hi veu |
|---|---|---|
| `pas1-recursos.png` | §4.1 recursos | inventari per anell: A 2 × `lnd_252285` amb Cd `fraction 0.667, arc 360°`, B 4, C 4 (§5: Cd només a l'anell 1) |
| `pas2-domini-i-cossos.png` | §4.2 estructura | caixa PE 50 × 50 × 70 ρ 0,95 (§5/§6, transversal = estimació a confirmar) i el forat 7 × 7 com a cos `Air` (§25; dubte 2) |
| `pas2-estructura-tongada.png` | §4.2 estructura | tongada única `referencia_10b`, eix z, els 10 punts de §6 amb recurs per punt (A/B/C), diferència r 20,5/21,1 declarada |
| `pas3-font-i-energies.png` | §4.3 font i energies | font puntual [0, 0, 0]; energies del paper aturades a 5 MeV (§3: límit dels salts) |
| `comprova-font-cavitat.txt` | §4.3 avís de `comprova` | **veredicte real de neudet d'avui: ⛔ «font dins del bloc»** — la font en cavitat (paper [3],[8]) encara no s'accepta: feina 2 de neudet. Text i com reproduir-ho, al fitxer |
| `pas4-objectius.png` | §4.4 resum d'objectius | finalitat comptador; `eps_mitja max` + `rang min` (ε_av i F del paper); pesos uniformes, energies totes |
| `pendent-mides-en-vermell.png` | punt 1 de l'encàrrec | variant `mides_cm: "PENDENT: mida de la Fig. 6 (a confirmar)"`: els tres camps en vermell, un motiu (el de neudet) i l'avís «orientatiu» |
| `formulari-sencer.png` | — | el formulari sencer de `mb10b_ref`, zero errors |
| `prova-complecio-per-blocs.txt` | punt 1 | `de_fitxer` (tal com és, sense omplir res) → refús en paraules → teclejar [50, 50, 70] (el que fa `cSet`) → `to_yaml` OK, tant si la clau hi era absent com si era el text «PENDENT…» |

Els passos **§4.5 i §4.6** (reproduir la 10B i l'estudi amb `motors: [B1, salts, openmc_gpu]`) necessiten execucions: és el torn
de l'Albert quan l'esborrany i les feines de neudet hi siguin (MOTORS-UI ja està preparat per mostrar la comparació).

## Què queda pendent (escriut, no inventat ni amagat)

- **Feines 1–4 de neudet**: l'esborrany `mb10b_ref` amb els PENDENT marcats, font en cavitat, SST als cossos (segon pas de les
  barres) i `rang` que decideix. Els dubtes i les propostes, escrits a
  `~/projects/neudet/docs/site/encarrecs/2026-11-18_MINIBELEN_dubtes.md` (fitxer creat a l'arbre de neudet **sense commatar**:
  l'arbre és seu; avisaré el coordinador).
- La **representació del forat quadrat** (cos `Air` vs concepte nou) és dubte 2 del mateix fitxer; la fixta l'expressa com a cos
  perquè és l'única via honesta d'avui (el formulari l'accepta i `to_yaml` hi round-tripa).

## Respostes del coordinador (2026-11-19, missatge de sessió) — comprobades aquí

- **Dubte 2 (forat 7 × 7):** confirmat, i és pitjor del que jo deia: `forat_cm` **és un radi** (surt com a `hole_radius_cm`
  a `candidat.py:359`, es dibuixa `plt.Circle((0, 0), bloc.forat_cm)` a `campanya.py:882`) i **a la xarxa el forat és
  `buit`, no aire** (`motor.py:44` `FONS_BUIT = 3`; docstring de `material()` :457: «3=buit (forat, anell d'aire…)»). Per tant
  el meu cos `Air` és només representació al formulari: **la xarxa no transporta els cossos §25** i, tal com va, es veuria PE
  on hi ha el forat. La representació serà la que decideixi la feina 1 entre les tres sortides de la fitxa §3 (cos / cercle
  r 3,95 amb la diferència declarada / forat quadrat nou amb codi); la fixta seguirà la decisió sense tocar res més.
- **Dubte 5:** el coordinador coincideix amb mi — es conserven les posicions mesurades **r 20,5 (x) / 21,1 (y)** amb la
  diferència escrita a l'apartat (unificar a 21 seria inventar una simetria que el paper no dona). Fixta sense canvis.
- **Dubte 1 (format del PENDENT):** la proposta (absent/null + motiu en un comentari del yaml) els arriba tal com — decisió
  del planificador de neudet a la feina 1.
- **Higiene:** el coordinador **s'ha pres els dubtes i els ha commatat** (neudet `4a1eef3`; comprobats aquí: sha256
  `13449483…` idèntic al de la còpia solta), i la còpia solta de l'arbre base del neudet s'ha esborrat (sha256 comprobats
  abans). **Segon missatge seu (19-11), error SEU:** en empendre la seva feina (`9e69ad3..ccad14d`), el `git push` de `main`
  **s'ha endut `4a1eef3`** — ell el volia retenir fins a la paraula de l'Albert. Comprobat aquí amb `fetch` (no `pull`):
  `4a1eef3` és a `origin/main`. Ho ha registrat (COORDINACIO §5 torn 99; neudet `daae3f2`) i té a la seva cua de l'Albert
  l'ordre per desfer-ho (`git revert --no-edit 4a1eef3`) — decisió de l'Albert, no nostra. El text queda **guardat aquí tal
  qual**: `dubtes-neudet.md` (mateix sha256), així que revertir o no costa el mateix. Llió apuntada: els dubtes s'escriuen
  al meu repo o es passen per missatge, **mai a l'arbre base d'una altra sessió**.

Comprobats al meu HEAD de neudet (`3d6d2bd`) tots els `fitxer:línia` que cita: el ⛔ de la font dins del bloc és
`TEXT_FONT_DINS` a `candidat.py:490` — regla seva (feina 2), no defecte de simui.

## Com reproduir

Els `.png` són de Chrome headless via CDP (script `/tmp/minibelen_proves/captures.mjs`, no versionat: les captures són
l'evidència). El servidor de proves:

```
cp -al ~/projects/neudet /tmp/minibelen_proves/neudet
# disseny/campanyes/mb10b_ref/campanya.yaml = fixta-mb10b_ref.yaml (aquest directori), i variants mb10b_pend_{falta,null,text}:
#   la mateixa fixta sense la clau mides_cm / amb `mides_cm: ~` / amb `mides_cm: "PENDENT: mida de la Fig. 6 (a confirmar)"`
NEUDET_ROOT=/tmp/minibelen_proves/neudet SIMNET_ROOT=~/projects/simnet ~/envs/simneu/bin/python scripts/serve.py --host 127.0.0.1 --port 8798
```

I les proves: `NEUDET_ROOT=… SIMNET_ROOT=… ~/envs/simneu/bin/python -m pytest -q tests/test_minibelen_ui.py tests/test_cossos_ui.py`
(la suite sencera: 548 passed).
