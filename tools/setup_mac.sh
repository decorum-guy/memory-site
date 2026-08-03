#!/bin/zsh
set -e
cd "${0:A:h}/.."

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew не найден. Установи его с brew.sh, затем запусти этот файл снова."
  exit 1
fi

brew list exiftool >/dev/null 2>&1 || brew install exiftool
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
python3 -m venv .memory-venv
source .memory-venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r tools/requirements.txt

echo ""
echo "Готово. Теперь запускай:"
echo "  source .memory-venv/bin/activate"
echo "  python3 tools/import_memories.py /путь/к/экспорту"
