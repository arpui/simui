#!/usr/bin/env bash
# puja.sh — l'única manera de pujar per als agents: integra el remot (merge, mai rebase) i fa push; fins a 3 intents.
# Ús: bash scripts/puja.sh [branca]   (per defecte, main)
set -u
B="${1:-main}"
for i in 1 2 3; do
  git pull --no-rebase --no-edit origin "$B" || { echo "⛔ conflicte en integrar origin/$B: resol-lo (sense descartar commits d'altres) i torna a córrer"; exit 1; }
  git push origin "HEAD:$B" && { echo "✅ pujat a $B"; exit 0; }
  sleep $((2 * i))
done
echo "⛔ push fallit 3 cops: anota-ho a la fila i deixa l'ordre a «Ordres pendents»"; exit 1
