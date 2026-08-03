#!/bin/zsh
set -euo pipefail
cd "${0:A:h}/.."

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew не найден. Установи Homebrew с https://brew.sh и запусти этот файл снова."
  exit 1
fi

brew list exiftool >/dev/null 2>&1 || brew install exiftool
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12

PYTHON_BIN="$(brew --prefix python@3.12)/bin/python3.12"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Не найден Python 3.12 по ожидаемому пути: $PYTHON_BIN"
  exit 1
fi

if [[ -d .memory-venv ]]; then
  echo "Пересоздаю .memory-venv на Python 3.12…"
  rm -rf .memory-venv
fi

"$PYTHON_BIN" -m venv .memory-venv
source .memory-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r tools/requirements.txt

echo ""
echo "Готово. Окружение создано на: $(python --version)"
echo "Теперь запускай:"
echo "  source .memory-venv/bin/activate"
echo "  python3 tools/import_workflow.py dry-run /путь/к/экспорту"
