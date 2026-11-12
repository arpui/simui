# UI-COST-AVIS — l'avís «massa gran per a un tanteig», amb dades provocades (2026-11-12)

**El que es comprovava:** UI-AFINA (4) deia que la UI havia de mostrar en vermell l'avís de cost quan neudet
posa `opcions_cost` al `comprova.json`. Mai s'havia vist amb dades reals: cap de les 9 campanyes de neudet
passa del llindar (`LLINDAR_GPU_H = 12.0` h de GPU, a `src/neudet/disseny/resum_peticio.py`), així que a
`comprova.json` hi ha `[]` o `null`.

**Com es va provocar** (còpia de feina, mai sobre dades reals — regla de `COORDINACIO.md` §6: còpia **sense
`data/` ni `mc/`**):

```
rsync -a --exclude data --exclude mc --exclude .git --exclude .claude ~/projects/neudet/ ~/projects/wt/neudet_UI-COST/
```

A la còpia, `disseny/campanyes/c0_2a0611/campanya.yaml` pujat ×10 ([`campanya.yaml.diff`](campanya.yaml.diff)), i:

```
SIMNET_ROOT=~/projects/simnet NEUDET_ROOT=$PWD ~/envs/simneu/bin/python \
  scripts/disseny/comprova_campanya.py disseny/campanyes/c0_2a0611 --json disseny/campanyes/c0_2a0611/comprova.json
```

Surt `opcions_cost` **ple** ([`opcions_cost.json`](opcions_cost.json)): **34,27 h de GPU** (> 12 h) i dues
opcions seves (`mostres: 140` → 11,66 h; `mostres: 190` + `cerca.n_inicial: 1.000.000` → 11,87 h).

## El que es va trobar: l'avís **no es pintava mai**

neudet dona el mateix camp en **dues formes**:

| on | forma |
|---|---|
| `peticio.cost.opcions_cost` d'una etapa (`resum_peticio.py`) | **llista** d'opcions |
| arrel del `comprova.json` (`scripts/disseny/comprova_campanya.py`: `informe["opcions_cost"] = {etapa: [...]}`) | **diccionari per etapa** |

La pàgina el llegia amb `c.opcions_cost.length`: amb el diccionari, `.length` és `undefined` → **fals** → cap
panell. Comprovat en viu amb la còpia (servidor amb `NEUDET_ROOT` a la còpia, `127.0.0.1:8767`):
`comprova.json` ple i **zero** elements `[data-cost-gran]` a la pàgina de la campanya.

## Arregl (simui `6309a42`)

`cCostBlocks()` entén les dues formes; amb el diccionari pinta **un panell per etapa** amb la clau de neudet al
títol, i l'avís es pinta **també a la pàgina de la campanya** (`kCert`), no només després de desar. Cap número
ni frase pròpia: la frase i els números són els de neudet.

Després de l'arregl, el que es veia a la pantalla (`[data-cost-gran]`, text exacte de la pàgina):

```
Massa gran per a un tanteig (etapa S1). neudet proposa aquestes opcions, amb el seu cost (és un avís, no
bloqueja res; la UI no n'aplica cap: si en tries una, canvia-la tu al formulari):
  mostres = 140 (per les hores de GPU) — Avaluar només 140 candidats a l'atzar dels 413 vàlids
    (`mostres: 140`): GPU 11.7 h en lloc de 34.3 h; durada prevista 12.1 h. — 11.66 h GPU · 2.24 GB de disc ·
    3.36 GB de disc a tenir lliure (porta) · 5.8 h CPU Geant4 · 12.1 h de durada
```

## Proves que ho fixen

`tests/test_cost_ui.py`: `test_neudet_ho_dona_en_dues_formes_i_ahi_queda_escrit` (llegeix el codi de neudet:
si canvien la forma, es fa vermell), `test_el_diccionari_per_etapa_també_es_pinta_amb_la_frase_de_neudet`,
`test_cap_lloc_llegeix_el_diccionari_com_si_fos_una_llista` i
`test_l_avís_de_cost_es_veu_també_a_la_pàgina_de_la_campanya`.

## Què passa amb la còpia

Esborrada per l'Albert el 2026-11-12. Per refer-la: la comanda de dalt (395 MB si no s'exclou `mc/`;
60–80 MB amb `mc/` exclòs).
