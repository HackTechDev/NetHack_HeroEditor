#!/usr/bin/env bash
# Lance l'éditeur de héros nhheroedit.
#
# Usage : ./nhheroedit.sh [projet.json] [--src DOSSIER_DES_SOURCES]
#         ./nhheroedit.sh --install   (lien dans ~/.local/bin/nhheroedit)
#
# Fonctionne aussi depuis un lien symbolique placé n'importe où.

set -euo pipefail

# dossier de l'éditeur, même si le script est appelé par un lien
DIR=$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")

if [[ ${1:-} == --install ]]; then
    BIN="$HOME/.local/bin"
    mkdir -p "$BIN"
    ln -sfn "$DIR/nhheroedit.sh" "$BIN/nhheroedit"
    echo "Lien créé : $BIN/nhheroedit -> $DIR/nhheroedit.sh"
    case ":$PATH:" in
        *":$BIN:"*) echo "Lancez l'éditeur avec : nhheroedit" ;;
        *) echo "Ajoutez $BIN à votre PATH pour lancer : nhheroedit" ;;
    esac
    exit 0
fi

PYTHON=${PYTHON:-python3}
if ! command -v "$PYTHON" >/dev/null; then
    echo "nhheroedit : $PYTHON introuvable (installez Python 3)." >&2
    exit 1
fi
if ! "$PYTHON" -c "import curses" 2>/dev/null; then
    echo "nhheroedit : le module curses de Python est absent." >&2
    exit 1
fi

exec "$PYTHON" "$DIR/nhheroedit.py" "$@"
