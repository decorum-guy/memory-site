# Проверка импортёра перед загрузкой всего архива

Этот сценарий нужен, чтобы сначала проверить 50 тестовых файлов, не затрагивая финальную книгу.

## Что добавлено

У безопасного импортёра есть четыре режима:

1. `dry-run` — только проверка исходников и окружения. Ничего не записывает в проект.
2. `test` — полноценный импорт в отдельную папку `.memory-test/site`.
3. `reset test` — удаляет только тестовую область.
4. `import` — полный production-импорт в основной сайт.

Дополнительно существует `reset production`, но он требует явного `--yes`, создаёт резервную копию и нужен только в экстренном случае.

---

## 1. Клонировать репозиторий

```bash
cd ~/Desktop
git clone https://github.com/decorum-guy/memory-site.git
cd memory-site
```

Если папка уже существует:

```bash
cd ~/Desktop/memory-site
git pull
```

---

## 2. Установить инструменты

```bash
zsh tools/setup_mac.sh
source .memory-venv/bin/activate
```

В новом окне Terminal окружение нужно активировать заново:

```bash
cd ~/Desktop/memory-site
source .memory-venv/bin/activate
```

---

## 3. Подготовить тестовую папку

Положи 50 тестовых фото и видео в отдельную папку, например:

```text
~/Desktop/memory-test-input
```

Внутри могут быть:

- HEIC/HEIF;
- JPG/JPEG;
- PNG/WEBP;
- MOV/MP4/M4V;
- пары HEIC + MOV для Live Photo.

Лучше использовать неизменённые оригиналы из приложения «Фото».

---

## 4. Запустить dry-run

```bash
python3 tools/import_workflow.py dry-run \
  "$HOME/Desktop/memory-test-input"
```

Dry-run:

- проверяет наличие ExifTool, FFmpeg и FFprobe;
- проверяет Pillow и поддержку HEIC;
- пытается открыть каждое изображение;
- проверяет каждый видеоролик через FFprobe;
- считает фото, видео и предполагаемые Live Photo;
- проверяет, у скольких файлов читается дата и GPS;
- оценивает необходимое свободное место;
- показывает неподдерживаемые файлы;
- не создаёт `media/generated`;
- не меняет `content/memories.js`;
- не создаёт резервные копии.

Успешный результат заканчивается строкой:

```text
РЕЗУЛЬТАТ: ГОТОВО К ТЕСТОВОМУ ИМПОРТУ.
```

Если есть ошибки, тестовый и production-импорт автоматически не запускаются.

### Необязательный JSON-отчёт

```bash
python3 tools/import_workflow.py dry-run \
  "$HOME/Desktop/memory-test-input" \
  --json-report "$HOME/Desktop/memory-dry-run.json"
```

Без `--json-report` dry-run вообще ничего не записывает.

---

## 5. Запустить тестовый импорт

```bash
python3 tools/import_workflow.py test \
  "$HOME/Desktop/memory-test-input" \
  --open
```

Режим `test` сначала сам повторяет dry-run. Если проверка успешна, он:

1. создаёт изолированную копию сайта в `.memory-test/site`;
2. импортирует туда все 50 тестовых файлов;
3. конвертирует HEIC, видео и Live Photos;
4. создаёт тестовый `memories.js` и `import-report.json`;
5. проверяет, что все пути к фото, превью, видео, постерам и Live-компонентам существуют;
6. проверяет, что тестовый `memories.js` читается;
7. открывает тестовый сайт в браузере.

Основные файлы проекта при этом не изменяются:

```text
content/memories.js          не изменяется
media/generated/             не изменяется
```

Тестовый результат находится здесь:

```text
.memory-test/site/index.html
.memory-test/site/content/import-report.json
.memory-test/site/media/generated/
```

Успешный тест заканчивается строкой:

```text
РЕЗУЛЬТАТ: ТЕСТ ПРОЙДЕН. Production-файлы не изменены.
```

Если не использовать `--open`, тестовый сайт можно открыть вручную:

```bash
open .memory-test/site/index.html
```

---

## 6. Что проверить глазами на 50 файлах

После успешного автоматического теста проверь:

1. Все 50 исходных файлов учтены с поправкой на Live Photo: HEIC + MOV считаются одним элементом.
2. Фото открываются крупно.
3. HEIC отображаются как JPEG-копии без неправильного поворота.
4. Видео запускаются со звуком и перематываются.
5. Вертикальные и горизонтальные видео имеют правильную ориентацию.
6. Live Photo получают отметку `LIVE` и кнопку «Оживить фото».
7. Даты выглядят правдоподобно.
8. Файлы одного события в основном находятся рядом.
9. В `.memory-test/site/content/import-report.json` поле `errors` пустое.
10. В Terminal нет строки `ТЕСТ НЕ ПРОЙДЕН`.

Ошибочная группировка не означает поломку импортёра — её потом можно исправлять в Memory Studio. Критические ошибки — битые файлы, отсутствующие превью, неработающие видео и записи в `errors`.

---

## 7. Сбросить тест и повторить

Обычный безопасный сброс:

```bash
python3 tools/import_workflow.py reset test --yes
```

Он удаляет только:

```text
.memory-test/
```

Основной сайт, фотографии и production-импорт не затрагиваются.

После сброса можно изменить тестовую выборку и снова выполнить:

```bash
python3 tools/import_workflow.py dry-run "$HOME/Desktop/memory-test-input"
python3 tools/import_workflow.py test "$HOME/Desktop/memory-test-input" --open
```

Повторный `test` также автоматически заменяет старую тестовую копию новой.

---

## 8. Полный импорт после успешного теста

Когда тест на 50 файлах полностью прошёл, подготовь папку со всем архивом и сначала снова сделай dry-run:

```bash
python3 tools/import_workflow.py dry-run \
  "$HOME/Desktop/Sonya-originals"
```

Затем production-импорт:

```bash
python3 tools/import_workflow.py import \
  "$HOME/Desktop/Sonya-originals"
```

Перед записью программа спросит подтверждение.

Для запуска без вопроса:

```bash
python3 tools/import_workflow.py import \
  "$HOME/Desktop/Sonya-originals" \
  --yes
```

Production-режим использует прежний движок `tools/import_memories.py`, но сначала обязательно выполняет полный preflight.

---

## 9. Ограничить число файлов

Можно проверить только первые 20 файлов из папки:

```bash
python3 tools/import_workflow.py dry-run \
  "$HOME/Desktop/memory-test-input" \
  --limit 20
```

И импортировать эти же первые 20 в тестовую область:

```bash
python3 tools/import_workflow.py test \
  "$HOME/Desktop/memory-test-input" \
  --limit 20 \
  --open
```

Для твоей отдельной папки из 50 файлов `--limit` не нужен.

---

## 10. Production-reset

Использовать только когда действительно нужно полностью убрать уже выполненный основной импорт:

```bash
python3 tools/import_workflow.py reset production --yes
```

Перед сбросом скрипт сохраняет:

- текущий `content/memories.js`;
- `content/import-report.json`;
- всю папку `media/generated`.

Резервная копия появится здесь:

```text
.memory-backups/reset-YYYYMMDD-HHMMSS/
```

После этого основной `memories.js` заменяется чистой заглушкой. Обычный тестовый цикл не требует production-reset.

---

## Рекомендуемая последовательность прямо сейчас

```bash
cd ~/Desktop
git clone https://github.com/decorum-guy/memory-site.git
cd memory-site
zsh tools/setup_mac.sh
source .memory-venv/bin/activate

python3 tools/import_workflow.py dry-run \
  "$HOME/Desktop/memory-test-input"

python3 tools/import_workflow.py test \
  "$HOME/Desktop/memory-test-input" \
  --open
```

Не запускай полный `import`, пока тестовый режим не напишет:

```text
РЕЗУЛЬТАТ: ТЕСТ ПРОЙДЕН.
```
