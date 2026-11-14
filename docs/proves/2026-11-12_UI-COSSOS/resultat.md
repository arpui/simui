# UI-COSSOS — 2026-11-12/13; refet amb §25 (v1.22) el 2026-11-14

El que es veu, primer; els tests després (ordre manat pel coordinador). Cap fitxer de neudet ni de simnet escrit des d'aquí.

El 2026-11-14 la UI s'ha migrat de §24 (v1.21) a **§25 (v1.22)** — la correcció del coordinador al vocabulari — i neudet ha fet `COSSOS-YAML`: **ja valida `domini.cossos`** (`fitxa.py:130`). Tot això va refer les captures i el yaml d'aquí; el §24 (i l'època en què neudet no validava res) queda explicat als commits.

## 1. El formulari

- **Forma del bloc** (`domini.bloc.forma`): selector `cub | cilindre` (§22; **absent = cub**, els yaml vells no el porten i els seus hashos no canvien). Amb `cilindre` apareixen `radi_cm` i `alzada_cm` **buits**: no hi ha valor per defecte, i si tries de desar sense haver-los escrit, la UI ho diu. Amb `cilindre` el camp `mides_cm` es esborra del model.
- **Taula de cossos** (`domini.cossos`, §25 v1.22): `nom`, `material`, `forma` (**`caixa | cilindre | tub`**, les úniques acceptades per neudet), `pos_cm` (**centre del cos, per a totes les formes**; l'eix de revolució és z), les mides segons la forma (`mides_cm` = **costats TOTALS** per a caixa; `radi_cm`+`alzada_cm`; `radi_int_cm`<`radi_ext_cm`+`alzada_cm` per al tub) i `densitat_gcm3`. **Cap fila ni valor per defecte**: en obrir la campanya no hi ha cap cos; «+ afegeix un cos» insereix una fila **buida**; la taula buida torna a ser `domini.cossos` absent.
- **Reservat, en paraules** (§25): `esfera`, `con`, `semiespai` com a forma i els camps `eix`, `regio`, `transport` per cos **es rebotin amb un missatge** («camp reservat — encara no acceptat per neudet (§25); no s'ignora en silenci»), mai en silenci ni amb comportament inventat. Les semides velles de §24 (`dx_cm`/`dy_cm`/`dz_cm`) tampoc: un camp que no és de la forma dona error perquè «un typo donaria un cos amb les mides equivocades i la tanda seguiria». A la taula, cada fila amb reservats ho porta escrit a la vora.
- S'hi afegeix el `domini.mon.transport` (§22) amb el seu avís: mentre sigui absent o `false`, els cossos fora del bloc no els transporta el motor de la xarxa — el que es mesura allà és a Geant4. El `transport` **per cos** és reservat i la taula no l'edita.

## 2. El visor

Quatre vistes (dalt, lateral x–z, lateral y–z, 3D) amb la forma del bloc i els cossos:

- bloc **cilíndric** (planta: cercle Ø 2·`radi_cm`; laterals: secció) i, si falten `radi_cm`/`alzada_cm`, un retol que diu que el dibuix és orientatiu i no la geometria escrita (§22: aquestes mides no tenen valor per defecte);
- **cossos** a la planta (caixa, cercle cilindre, anell per al tub) i en secció a les dues vistes laterals; avui **tots de ratlles = només Geant4 (§25)** — el «cos al motor» dependria de `PLOM-F-B2` (món transportat), que encara no existeix; la llegenda ho diu: «plom_lateral Pb · caixa · només Geant4»;
- **3D** isomètric amb el bloc, els cossos i els tubs a mida real;
- **font col·locable** (`mou la font` / arrossegar) i «posa-la a fora (per defecte)», que amb `forma: cilindre` calcula −(`alzada_cm`/2 + 5) (§6 E) i, si no hi ha alçada escrita, **no inventa res**: dona l'error i la font es queda on és.

Captures (la pantalla real; Chrome headless sobre la UI servida per `scripts/serve.py`, la campanya muntada al formulari amb la taula de §25):

- [visor-3d-i-cossos.png](visor-3d-i-cossos.png) — bloc cilíndric Ø 50 × 80 + `plom_lateral` (Pb, caixa de 10 × 60 × 60 FORA del bloc, ratlles) + `colimador` (Pb, tub 3/6 × 10 sota el bloc) + els tubs dins del PE + la font moguda a (0, 0, −55) cm, a les quatre vistes;
- [taula-cossos-i-mides.png](taula-cossos-i-mides.png) — la taula amb les mides per forma (`mides_cm [x, y, z totals]` per a caixa, `3 · 6 · 10` per al tub) i `densitat_gcm3: 11.35`;
- [escenari-simphy.png](escenari-simphy.png) — el panell «Escenaris que simphy ja té»: `cilindre_plom_dos_tubs` (vocabulari **1.22**) rebotat només pel seu `regio` reservat, `formes_varieses` (vocabulari **1.21**) rebotat per `eix`, i el retol de l'estat de neudet (fitxa.py:130) llegit del seu codi.

## 3. El cercle tancat amb la dada de simphy

`~/projects/simphy/data/mcgen/escenarios/` es llegeix des de la UI: `/api/campanya/schema` en llista els que hi ha (`escenaris`, amb els errors que donarien amb les regles de §25 d'aquí) i «carrega a la taula» (/api/campanya/escenari, només lectura) en omple la taula sencera i diu de quin fitxer ve. **No és cap valor per defecte**: és una acció de l'usuari.

La divergència amb la dada de simphy **queda escrita, no corregida** (la dada és de simphy): `cilindre_plom_dos_tubs` ja és de vocabulari 1.22 però el seu `bloc_pe` porta `regio: 'bloc_pe - tub_a - tub_b'` → un sol rebot («camp reservat — encara no acceptat per neudet (§25); no s'ignora en silenci»); `formes_varieses` és de 1.21 (con/esfera/box, `eix`, `transport`, semides) → en rebota molts. Tots dos fixats per tests (§8).

## 4. Què valida neudet avui

La UI no ho decideix: ho llegeix del codi de neudet (`estat_geometria_neudet()`) i ho posa al costat de cada camp.

- `domini.bloc.forma`: **sí** — «neudet ja valida «domini.bloc.forma» (fitxa.py:80): «cub|cilindre», i amb cilindre `radi_cm` i `alzada_cm` són obligatoris — cap valor implícit». La línia és la real (el test bessó la llegeix).
- `domini.cossos`: **sí des de `COSSOS-YAML` (2026-11-13)** — «neudet valida `domini.cossos` (fitxa.py:130) amb el vocabulari de §25 (`disseny/cossos.py`: caixa|cilindre|tub)». El retol «neudet encara no valida aquests camps» que hi havia el 2026-11-12 ja no és cert i ha desaparegut. La UI fa el **mirall** de les regles estructurals i aritmètiques (reservats, obligatoris sense valor per defecte, camps fora de forma, mides > 0, `radi_int < radi_ext`, noms únics perquè el nom és el volum Geant4 `cos_<nom>`); el **veredicte del registre de materials** (avui només Pb amb el ρ únic 11.35) **no es copia aquí**: la taula el deixa passar i «Comprova» mostra el missatge de neudet tal com surt (fixat: `cosos_info()` no conté cap «11.3»). Un yaml sense `cossos` queda bit a bit com abans.

## 5. El con (θ_max i f)

`θ_max` i `f` **de la geometria que hi ha al formulari** ja surten a la pantalla: els calcula neudet (`neudet.disseny/font.py:343`, `avis_text`) i la UI els reprodueix tal com són — canviar la forma del bloc els canvia. La comparació cilindre contra caixa del mateix volum (l'argument de per què el selector importa) és una **mesura de neudet**: a la UI hi ha la referència a `docs/site/proves/2026-11-12_CIL_F_A012/resultat.md`, i **no se'n copia cap número** (el principi del repo: les dades de neudet no es copien aquí).

Per avisar: el text que imprimeix neudet avui diu «s'emeten només direccions dins d'un con de θ_max = …°» — a `neudet/disseny/font.py` no hi ha cap menció a *oblic* ni a la forma del bloc en aquell text (buscat: res). La UI no pot posar una paraula que neudet no diu; si cal distinguir oblic/cilíndric, és a neudet.

## 6. Un camp que deixava de funcionar (i ara torna)

Amb `forma: cilindre`, l'avís §19 «font dins del bloc / sobre la cara del bloc» (`font_avis`, i el seu mirall JS `cFontAvis`) **només mirava `mides_cm`**: amb el bloc cilíndric l'avís desapareixia en silenci. Ara mesura a la cara cilíndrica (`hypot(x, y) − radi`) i a les dues bases (`|z| − alzada/2`); sense `radi_cm`/`alzada_cm` no diu res (no n'inventa). Fixat amb `test_lavís_de_la_font_funciona_amb_cub_i_amb_cilindre`.

## 7. El recorregut real petit (2026-11-14)

Campanya nova des del formulari (`+ Nova campanya` = c04_draft de neudet, id `ui_cossos_25`): bloc PE **cilindre** r 25 × h 80, dos cossos de §25 (Pb caixa i Pb tub, ρ 11.35) i la font moguda a (0, 0, −55). El yaml que munta la UI (`/api/campanya/yaml`, `desa: false` — no escriu res) és [campanya.yaml](campanya.yaml), amb `CF._errors` = []; la UI l'accepta i neudet el validaria (és tot Pb del registre). **No s'ha desat ni executat a Geant4** (com mana l'Albert: això ja ho farà ell).

Del 2026-11-12 es manté l'assaig que no va poder ser: `disseny/campanyes/cil_test_a012/campanya.yaml` **no s'obre a la UI** perquè neudet la rebutja («`objectius.pareto` ha de ser dos parells [metrica, max|min]») — error del seu yaml, no de la UI.

## 8. Després: els tests bessons

`tests/test_cossos_ui.py` (21 proves, totes en verd; suite sencera: **502**):

- §22: llista tancada `cub|cilindre`; amb `cilindre`, `radi_cm`/`alzada_cm` obligatoris i `mides_cm` prohibit; amb `cub`, a l'inrevés; absent = cub i el yaml **no escriu `forma`** (els hashos no canvien).
- §25: les tres formes i les seves mides; reservats (`eix/regio/transport`, `esfera/con/semiespai`) rebotats **en paraules**; les semides de §24 fora i rebotades; `absent = cap cos`, `defecte_files = 0` i cap `transport_defecte`; camps d'una altra forma = error; aritmètica (mides > 0, `radi_int < radi_ext`); noms únics; `pos_cm` = centre per a totes les formes.
- **Bessó amb neudet viu**: `violacions_cossos` (importat de `neudet.disseny.cossos`) vs `_errors_cossos` de la UI — mateix veredicte (buid/NO buid) en 11 sondes i les mateixes frases compartides («reservat», «nom de cos repetit»). La línia real de `fitxa.py` que cita la UI conté `domini.cossos`; el costat de neudet (formes/mides del sidecar) és el que llegeix la UI, sense copiar números (cap «11.3» a `cosos_info()`).
- Divergència escrita: `cilindre_plom_dos_tubs` (1.22) rebotat només pel `regio` i `formes_varieses` (1.21) rebotat en bloc — la dada de simphy no es corregeix; demanar un escenari que no hi ha peta dient on mirar.
- Mirall JS executat amb node (`COSSOS-DEF-BEGIN/END`): `cBlocExt`, `cCossosEscena` i `cCosMal` donen el mateix veredicte que el Python per a caixa/tub/cilindre vàlids, el `eix` reservat, les semides velles i la fila buida; la fila nova de la taula no porta cap valor i la taula no edita cap `.transport` per cos.
