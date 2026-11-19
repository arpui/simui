# MINIBELEN · dubtes (2026-11-19, planificador de simui)

De l'execució de la secció **simui** de l'encàrrec `2026-11-18_MINIBELEN_cas.md`. L'esborrany de neudet encara no existeix
(feina 1: `disseny/campanyes/mb10b_ref/` no és ni a l'arbre de neudet `3d6d2bd` ni a `origin/main` `c5be77f`), així que simui
s'ha provat amb una **fixta seva**, marcada com a tal: `simui/docs/proves/2026-11-18_MINIBELEN/fixta-mb10b_ref.yaml`
(faithful als §5 i §6 de la fitxa). Res decidit aquí: els punts 1–4 són per definir-los a la feina de neudet.

1. **Format del marcat PENDENT (feina 1 de neudet — és vostre; proposta, no decisió).** Mesurat al formulari:
   - Clau `mides_cm` **absent** o valor **`~` (null)**: l'esborrany s'obri, els tres camps es posen **en vermell** amb el motiu del
     `to_yaml` de neudet («tres mides positives en cm, p. ex. [30, 30, 80]») i el dibuix avisa «el dibuix és orientatiu, no és la teva
     geometria (§22)». Albert el completa i es desbloqueja. ✓
   - Valor **text** (`mides_cm: "PENDENT: …"`): `to_yaml` el refusa en paraules (bé) i el formulari ja no cessa (arreglat el 19-11),
     però el text **no es pot llegir als inputs** (són numèrics).
   ⇒ Proposta: marcar amb absent o null i posar el motiu en un **comentari del yaml** (es veu al bloc «campanya.yaml (en viu)»);
   el text com a valor només seria útil com a missatge d'error, no com a dada.
2. **Forat de 7 × 7.** `domini.bloc.forat_cm` és un cercle (fitxa §3). A la fixta he expressat el forat com un **cos de `cossos`**:
   `{nom: forat, material: Air, forma: caixa, mides_cm: [7, 7, 70], densitat_gcm3: 0.0012, pos_cm: [0, 0, 0]}` (ρ lliure per contracte
   COSSOS-MAT v1.28; 0,0012 és el valor NIST de l'aire, citable). És aquesta la representació de l'`mb10b_ref`, o cal un forat quadrat
   nou? (L'encàrrec demana a simphy que comprovi la generació Geant4/OpenMC amb forat quadrat de 7 × 7.)
3. **Font en cavitat (feina 2 de neudet).** Amb la fixta faithful, el `comprova` d'avui respon
   «⛔ mb10b_ref: font dins del bloc: el bloc envolta la font; el cas d'ús és font a fora (posa-la a fora del bloc, amb
   `domini.entre: buit`)`» (evidència: `simui/docs/proves/2026-11-18_MINIBELEN/comprova-font-cavitat.txt`). Fins a la feina 2, la
   referència 10B (paper [3],[8]: font puntual al centre del forat) **no passa `comprova`**. simui no ha canviat cap regla ni ho
   reinterpretarà.
4. **`rang` que decideix (feina 4).** El formulari ja accepta `rang` com a mètrica de comptador a `objectius.objectius` sense rebotar-lo,
   i la fixta fa `[[eps_mitja, max], [rang, min]]` (ε_av i F del paper, eq. 1–2). La fórmula visible és a la banda de neudet.
5. **Diferència §6 declarada:** la fixta conserva les posicions mesurades (r 20,5 en x · 21,1 en y) amb la diferència escrita a
   l'apartat; si preferiu unificar a r = 21, ho dic i ho canvio (a la UI també ho pot fer l'Albert ell mateix).
