# UI-COSSOS — 2026-11-12/13

El que es veu, primer; els tests després (ordre manat pel coordinador). Cap fitxer de neudet ni de simnet escrit des d'aquí.

## 1. El formulari

- **Forma del bloc** (`domini.bloc.forma`): selector `cub | cilindre` (§22; **absent = cub**, els yaml vells no el porten i els seus hashos no canvien). Amb `cilindre` apareixen `radi_cm` i `alzada_cm` **buits**: no hi ha valor per defecte, i si tries de desar sense haver-los escrit, la UI ho diu. Amb `cilindre` el camp `mides_cm` es esborra del model (abans de l'esmena, la UI rebutjava el seu propi yaml: «`domini.bloc.mides_cm`: només amb forma: cub» mentre el camp era ocult).
- **Taula de cossos** (`domini.cossos`, §24): `nom`, `material`, `forma` (`box|cilindre|esfera|con|semiespai`), `pos_cm`, les mides segons la forma (`dx_cm/dy_cm/dz_cm`, `radi_cm`+`alzada_cm`+`eix`, `radi_cm`, `radi_base_cm`+`alzada_cm`+`eix`, `punt_cm`+`normal`), `densitat_gcm3`, `transport` (per defecte `false`) i `regio`. **Cap fila ni valor per defecte**: en obrir la campanya no hi ha cap cos; «+ afegeix un cos» insereix una fila **buida**; la taula buida torna a ser `domini.cossos` absent. Un camp d'una altra forma, absent (la UI diu «no toca amb forma: X»).
- S'hi afegeix el `domini.mon.transport` (§22) amb el seu avís: mentre sigui absent o `false`, els cossos fora del bloc no els transporta el motor de la xarxa — el que es mesura allà és a Geant4.

## 2. El visor

Quatre vistes (dalt, lateral x–z, lateral y–z, 3D) amb la forma del bloc i els cossos:

- bloc **cilíndric** (planta: cercle Ø 2·`radi_cm`; laterals: secció) i, si falten `radi_cm`/`alzada_cm`, un retol que diu que el dibuix és orientatiu i no la geometria escrita (§22: aquestes mides no tenen valor per defecte);
- **cossos en secció** a les dues vistes laterals (`cCosPlan`) i contorns a la planta;
- **3D** amb el bloc, els cossos i els tubs: contorn **sòlid** = al motor (`transport: true`), contorn de **ratlles** = només a Geant4. Llegenda amb el material al costat (`Pb · box · només Geant4`, `He3 · cilindre · al motor`) i peu: «Cossos (§24): 3 amb contorn sòlit = al motor (transport: true); 1 amb contorn de ratlles = només a Geant4 (§22…)»;
- **font col·locable** (`mou la font` / arrossegar) i «posa-la a fora (per defecte)», que amb `forma: cilindre` calcula −(`alzada_cm`/2 + 5) (§6 E) i, si no hi ha alçada escrita, **no inventa res**: dona l'error i la font es queda on és.

Captures (la pantalla real, amb el visor a 420 px):

- [visor-3d-i-cossos.png](visor-3d-i-cossos.png) — bloc cilíndric + `plom_lateral` (Pb, fora del bloc, ratlles) + els dos tubs dins del PE + la font a (0, 0, −65) cm, i a sota el `campanya.yaml` en viu amb `forma: cilindre, radi_cm: 25, alzada_cm: 80`;
- [taula-cossos-i-mides.png](taula-cossos-i-mides.png) — la taula amb els quatre cossos i les mides per forma;
- [escenari-simphy.png](escenari-simphy.png) — el panell «Escenaris §24 que simphy ja té» amb `cilindre_plom_dos_tubs` (4 cossos, vocabulari 1.21) i el seu `_pendent` tal com el va escriure simphy.

## 3. El cercle tancat amb la dada de simphy

`~/projects/simphy/data/mcgen/escenarios/cilindre_plom_dos_tubs.json` (GEOM-BASE de l'Albert, §24 v1.21) es llegeix des de la UI: `/api/campanya/schema` en llista els que hi ha (`escenaris`, amb els errors que donaria amb les regles de §24) i «carrega a la taula» (/api/campanya/escenari, només lectura) en omple la taula sencera i diu de quin fitxer ve. **No és cap valor per defecte**: és una acció de l'usuari; el que l'escenari no porta s'ha d'escriure a mà. L'escenari de simphy passa les regles de §24 de la UI amb **zero errors** i no hi ha cap camp fora del vocabulari — els dos costats diuen el mateix.

## 4. Què valida neudet avui (i què no)

La UI no ho decideix: ho llegeix del codi de neudet (`estat_geometria_neudet()`) i ho posa al costat de cada camp.

- `domini.bloc.forma`: **sí**. Retol a la pantalla: «neudet ja valida «domini.bloc.forma» (fitxa.py:80): «cub|cilindre», i amb cilindre `radi_cm` i `alzada_cm` són obligatoris — cap valor implícit». La línia és la real (el test bessó la llegeix i hi busca `domini.bloc.forma`).
- `domini.cossos`: **no**. Retol, tal com mana el coordinador: «**neudet encara no valida aquests camps**: neudet no llegeix `domini.cossos` del campanya.yaml; el que té és el vocabulari intern del sidecar de Geant4 (disseny/cossos.py: caixa|cilindre|tub amb alzada_cm, mides_cm, radi_cm, radi_ext_cm, radi_int_cm, materials Pb). La divergència amb §24 la tanca el coordinador.» **La taula es munta i es pinta; no se serveix com si validés.** No s'ha aturat cap pantalla per això.
- **La divergència, escrita i fixada per un test**: §24 diu `box|cilindre|esfera|con|semiespai` amb `dx_cm`/`radi_base_cm`/`punt_cm`/`normal`; el sidecar de neudet (`neudet.disseny.cossos`) diu `caixa|cilindre|tub` amb `mides_cm`/`radi_int_cm`/`radi_ext_cm` i materials `Pb`. Són llistes diferents: `test_neudet_no_llegeix_domini_cossos_i_la_divergència_queda_escrita` la fixa, i a la pantalla queda dit qui la tanca.

## 5. El con (θ_max i f)

`θ_max` i `f` **de la geometria que hi ha al formulari** ja surten a la pantalla: els calcula neudet (`neudet.disseny/font.py:343`, `avis_text`) i la UI els reprodueix tal com són — canviar la forma del bloc els canvia. La comparació cilindre contra caixa del mateix volum (l'argument de per què el selector importa) és una **mesura de neudet**: a la UI hi ha la referència a `docs/site/proves/2026-11-12_CIL_F_A012/resultat.md`, i **no se'n copia cap número** (el principi del repo: les dades de neudet no es copien aquí).

Per avisar: el text que imprimeix neudet avui diu «s'emeten només direccions dins d'un con de θ_max = …°» — a `neudet/disseny/font.py` no hi ha cap menció a *oblic* ni a la forma del bloc en aquell text (buscat: res). La UI no pot posar una paraula que neudet no diu; si cal distinguir oblic/cilíndric, és a neudet.

## 6. Un camp que deixava de funcionar (i ara torna)

Amb `forma: cilindre`, l'avís §19 «font dins del bloc / sobre la cara del bloc» (`font_avis`, i el seu mirall JS `cFontAvis`) **només mirava `mides_cm`**: amb el bloc cilíndric l'avís desapareixia en silenci. Ara mesura a la cara cilíndrica (`hypot(x, y) − radi`) i a les dues bases (`|z| − alzada/2`); sense `radi_cm`/`alzada_cm` no diu res (no n'inventa). Fixat amb `test_lavís_de_la_font_funciona_amb_cub_i_amb_cilindre`.

## 7. Assaig: el que no s'ha pogut mostrar

- `disseny/campanyes/cil_test_a012/campanya.yaml` (feta avui per un agent de neudet, amb `forma: cilindre, radi_cm: 15, alzada_cm: 80`) **no s'obre a la UI**: neudet la rebutja amb «`objectius.pareto` ha de ser dos parells [metrica, max|min]». És un error del seu yaml, no de la UI; no s'ha tocat neudet. Per això la pantalla s'ha fet amb una campanya nova (`+ Nova campanya` = els valors de neudet de c04_draft, id `ui_cossos_demo`) i l'escenari de simphy a sobre: el yaml que genera la UI és [campanya.yaml](campanya.yaml) (`CF._errors` = [].)
- La campanya **no s'ha desat ni l'ha executada neudet** (com mana l'Albert): només el yaml en viu i el visor.

## 8. Després: els tests bessons

`tests/test_cossos_ui.py` (17 proves, totes en verd; la suite sencera no s'ha trencat):

- §22: llista tancada `cub|cilindre`; amb `cilindre`, `radi_cm`/`alzada_cm` obligatoris i `mides_cm` prohibit; amb `cub`, `radi_cm`/`alzada_cm` prohibits; absent = cub i el yaml **no escriu `forma`** (els hashos no canvien); el yaml de la UI no porta res implícit.
- §24: les cinc formes i les mides de cadascuna; un camp d'altra forma → «no toca amb forma: X»; un camp que no és de §24 → ho diu; `absent = cap cos`; `defecte_files = 0` i `transport_defecte = false`; treure qualsevol obligatori dóna «obligatori i sense valor per defecte»; els `nom` són únics.
- Mirall JS executat amb node (`COSSOS-DEF-BEGIN/END`): `cBlocExt`, `cCossosEscena` i `cCosMal` donen el mateix que el Python per a cub, cilindre i cilindre sense mides, i marquen la fila sense forma ni mides.
- Neudet: la línia que cita la UI per a `domini.bloc.forma` és la real de `fitxa.py`; per a `domini.cossos` diu que **no** el valida i enllaça el vocabulari del sidecar (divergència fixada).
- Simphy: l'escenari real `cilindre_plom_dos_tubs` passa les regles de §24 i no té cap camp fora del vocabulari; demanar un escenari que no hi ha peta dient on mirar (no se n'inventa cap).
