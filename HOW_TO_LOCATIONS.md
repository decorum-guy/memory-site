# Местоположения фото и видео

Memory Site умеет один раз определить названия мест через системный геокодер macOS, сохранить их в `content/memories.js` и затем показывать полностью офлайн.

## Что сохраняется

Для каждого импортированного файла при наличии GPS:

```js
{
  gps: { lat: 55.7522, lon: 37.6156 },
  location: "Москва, Россия"
}
```

Координаты нужны для повторной обработки и ручной проверки, но посетителю книги они не показываются. В открытой карточке сверху отображается только строка `location`. Если она пустая, плашка отсутствует.

## Приватность и интернет

- ExifTool читает GPS локально.
- Готовые текстовые геотеги из HEIC/MOV используются без сетевого запроса.
- Для GPS без названия координата один раз передаётся геокодеру Apple/macOS.
- Результаты складываются в локальный `.memory-location-cache.json`.
- Финальная книга на флешке читает только готовый текст из `memories.js` и не обращается к геокодеру или интернету.

`.memory-location-cache.json` и собранный Swift-инструмент `.memory-tools/` исключены из Git.

## Рекомендуемый импорт

Из корня проекта:

```bash
cd ~/Projects/memory-site
source .memory-venv/bin/activate
SOURCE="$HOME/Projects/memory-source"
```

Dry run остаётся безопасным и ничего не записывает:

```bash
python tools/import_with_locations.py dry-run "$SOURCE"
```

Тестовая копия с автоматическими местами:

```bash
python tools/import_workflow.py reset test --yes
python tools/import_with_locations.py test "$SOURCE" --open
```

Production-импорт с автоматическими местами:

```bash
python tools/import_with_locations.py import "$SOURCE"
```

Обёртка сначала запускает обычный безопасный импорт, а затем `tools/location_enrichment.py` для получившейся книги.

## Если обычный импорт уже выполнен

Не нужно импортировать медиа повторно. Добавь места отдельной командой:

```bash
python tools/location_enrichment.py "$SOURCE"
```

Для тестовой копии:

```bash
python tools/location_enrichment.py "$SOURCE" --root .memory-test/site
```

Скрипт создаёт резервную копию `content/memories.js` перед записью и формирует отчёт:

```text
content/location-report.json
```

## Локальный кэш

Близкие координаты округляются примерно до уровня квартала и получают один результат. Это уменьшает число обращений к Apple и ускоряет повторные запуски.

При повторном запуске уже найденные места берутся из:

```text
.memory-location-cache.json
```

Чтобы полностью пересчитать названия, можно удалить этот файл. Ручные названия в `memories.js` по умолчанию сохраняются и не перезаписываются.

## Ручная редактура

В Memory Studio у каждого файла появляется поле:

```text
Местоположение в открытой карточке
```

Автоматическое значение можно заменить, например:

```text
Москва, Россия
```

на:

```text
Наш двор
```

Чтобы скрыть место, оставь поле пустым.

После правок действуют обычные правила сохранения:

1. Нажать `Экспортировать memories.js`.
2. Применить файл:

```bash
python tools/studio_workflow.py apply production "$HOME/Downloads/memories.js" --open
```

## Если геокодер не собирается

Проверь Command Line Tools:

```bash
xcode-select -p
xcrun --find swiftc
```

При отсутствии установи системным диалогом:

```bash
xcode-select --install
```

Можно временно импортировать только GPS и готовые текстовые metadata без обращения к Apple:

```bash
python tools/import_with_locations.py test "$SOURCE" --no-geocode
```

или:

```bash
python tools/location_enrichment.py "$SOURCE" --no-geocode
```
