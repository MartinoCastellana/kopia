#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
if [[ -x dist/Kopia.app/Contents/MacOS/Kopia ]]; then
  open dist/Kopia.app
elif [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python main.py
else
  echo "Esegui prima ./install_mac.sh"
  exit 1
fi
