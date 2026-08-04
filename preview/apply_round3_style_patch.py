#!/usr/bin/env python3
from pathlib import Path
import re


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"Anchor not found in {path}: {old[:80]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


styles = Path("assets/styles.css")
replace_once(styles, "letter-spacing: -.065em;", "letter-spacing: -.018em;")
replace_once(styles, "  width: 3.8rem;\n  height: 3.8rem;", "  width: 7.8rem;\n  height: 7.8rem;")
replace_once(styles, "  border: .38rem double #8a342e;", "  border: .58rem double #8a342e;")
replace_once(styles, ".cover__seal span { transform: translateY(-1px); }", ".cover__seal span { font-size: 3.15rem; transform: translateY(-2px); }")

media = Path("assets/media.css")
media_text = media.read_text(encoding="utf-8")
marker = "/* Round 3: Live Photo controls live below metadata instead of covering it. */"
if marker not in media_text:
    media_text = media_text.rstrip() + """

/* Round 3: Live Photo controls live below metadata instead of covering it. */
.lightbox__figure {
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: minmax(0, auto) auto auto;
  row-gap: .5rem;
}
.lightbox__image,
.lightbox__video {
  grid-column: 1;
  grid-row: 1;
  max-height: 68vh;
}
.lightbox__caption {
  grid-column: 1;
  grid-row: 2;
  margin-top: .2rem;
}
.lightbox__live {
  position: static;
  grid-column: 1;
  grid-row: 3;
  justify-self: center;
  left: auto;
  bottom: auto;
  margin: .15rem 0 0;
  transform: none;
}
@media (max-width: 600px) {
  .lightbox__image,
  .lightbox__video { max-height: 61vh; }
}
""" + "\n"
    media.write_text(media_text, encoding="utf-8")

cursor = Path("assets/cursor-scrapbook-pencil-final-v19.css")
text = cursor.read_text(encoding="utf-8")
text = text.replace(
    "/* Three aligned cursor states from scrapbook-pencil-cursors-aligned.zip.\n   Every state uses a 64×64 canvas and the same graphite-tip hotspot: 12 48. */",
    "/* Two-state pencil cursor: basic + active. Hover intentionally keeps basic.\n   Both states use a 64×64 canvas and the same graphite-tip hotspot: 12 48. */",
    1,
)
pattern = re.compile(
    r"\n  a,\n  button,\n  summary,\n  \[role=\"button\"\],\n  \[data-clickable\],\n  input\[type=\"button\"\],\n  input\[type=\"submit\"\],\n  label\[for\] \{\n    cursor:[\s\S]*?\n  \}\n\n  a:active,",
)
text, count = pattern.subn("\n\n  a:active,", text, count=1)
if count == 0 and "hover-aligned.svg" in text:
    raise SystemExit("Could not remove hover cursor rule")
cursor.write_text(text, encoding="utf-8")

studio = Path("tools/telegram_studio.html")
studio_text = studio.read_text(encoding="utf-8")
if "article.innerHTML+=" in studio_text:
    studio_text, count = re.subn(
        r"article\.innerHTML\+=(`[^\n]*`);",
        r'article.insertAdjacentHTML("beforeend", \1);',
        studio_text,
    )
    if count != 2:
        raise SystemExit(f"Expected to patch two Telegram Studio renderers, patched {count}")
    studio.write_text(studio_text, encoding="utf-8")

print("Round 3 style and Studio patch applied")
