#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  echo "Esegui prima ./install_mac.sh"
  exit 1
fi
.venv/bin/python -m unittest discover -s tests -v
PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-/private/tmp/kopia-pyinstaller}" .venv/bin/python -m PyInstaller --clean --noconfirm Kopia.spec
echo "Pronto: dist/Kopia.app"
