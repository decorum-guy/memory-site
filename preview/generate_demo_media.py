#!/usr/bin/env python3
"""Generate deterministic temporary media for design screenshots.

These are intentionally synthetic placeholders, not real memories and not AI-generated
photographs. They exist only so Chromium can render every layout in GitHub Actions.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import math
import random

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "preview" / "demo-media"
TG = ROOT / "media" / "telegram"
OUT.mkdir(parents=True, exist_ok=True)
TG.mkdir(parents=True, exist_ok=True)
random.seed(2408)

PALETTES = [
    ((48, 62, 80), (220, 166, 126), (245, 225, 190)),
    ((38, 78, 92), (143, 190, 183), (235, 205, 164)),
    ((71, 47, 52), (181, 91, 91), (234, 190, 155)),
    ((53, 65, 48), (133, 156, 104), (230, 216, 174)),
    ((42, 43, 49), (105, 118, 145), (225, 190, 148)),
]

try:
    FONT = ImageFont.truetype("DejaVuSans.ttf", 42)
    SMALL = ImageFont.truetype("DejaVuSans.ttf", 24)
except OSError:
    FONT = ImageFont.load_default()
    SMALL = ImageFont.load_default()


def lerp(a, b, t):
    return int(a + (b - a) * t)


def gradient(size, top, bottom):
    width, height = size
    image = Image.new("RGB", size)
    px = image.load()
    for y in range(height):
        t = y / max(1, height - 1)
        for x in range(width):
            vignette = 1 - 0.12 * abs((x / width) - 0.5)
            px[x, y] = tuple(max(0, min(255, int(lerp(top[i], bottom[i], t) * vignette))) for i in range(3))
    return image


def make_scene(index):
    portrait = index in {1, 4, 7, 10, 11, 15}
    size = (900, 1200) if portrait else (1400, 950)
    dark, mid, light = PALETTES[index % len(PALETTES)]
    image = gradient(size, dark, light)
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = size

    # Soft skyline / landscape shapes.
    horizon = int(height * (0.54 + 0.08 * math.sin(index)))
    draw.rectangle((0, horizon, width, height), fill=(*dark, 155))
    for block in range(12):
        x = int(block * width / 11 - width * 0.03)
        bw = int(width * random.uniform(0.06, 0.13))
        bh = int(height * random.uniform(0.07, 0.26))
        draw.rounded_rectangle((x, horizon - bh, x + bw, horizon + 10), radius=8, fill=(*mid, 95))

    # A pair of abstract people-like silhouettes, deliberately non-photorealistic.
    centers = [(width * 0.42, height * 0.58), (width * 0.57, height * 0.59)]
    for person, (cx, cy) in enumerate(centers):
        radius = width * (0.045 if portrait else 0.035)
        draw.ellipse((cx-radius, cy-radius*3.1, cx+radius, cy-radius*1.1), fill=(28, 27, 27, 190))
        body_w = radius * 2.6
        body_h = height * 0.22
        draw.rounded_rectangle((cx-body_w/2, cy-radius*1.3, cx+body_w/2, cy+body_h), radius=radius, fill=(22, 23, 25, 190))

    # Lights and film-like grain.
    for _ in range(26):
        r = random.randint(4, 18)
        x = random.randint(0, width)
        y = random.randint(int(height * .15), int(height * .75))
        draw.ellipse((x-r, y-r, x+r, y+r), fill=(*light, random.randint(25, 90)))
    for _ in range(int(width * height / 900)):
        x = random.randrange(width)
        y = random.randrange(height)
        alpha = random.randint(4, 13)
        draw.point((x, y), fill=(255, 255, 255, alpha))

    label = f"DEMO · {index:02d}"
    draw.rounded_rectangle((30, 28, 245, 82), radius=10, fill=(18, 17, 16, 105))
    draw.text((48, 41), label, font=SMALL, fill=(255,255,255,205))
    return image.filter(ImageFilter.GaussianBlur(radius=.18))


for index in range(1, 16):
    make_scene(index).save(OUT / f"photo-{index:02d}.jpg", quality=90, optimize=True, progressive=True)

# Video poster uses the same visual language.
make_scene(9).save(OUT / "video-poster.jpg", quality=90, optimize=True)


def make_chat(number, outgoing_first=False):
    width, height = 900, 1500
    image = Image.new("RGB", (width, height), (225, 233, 238))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, width, 112), fill=(76, 120, 151, 255))
    draw.text((42, 32), "Соня", font=FONT, fill="white")
    draw.text((42, 82), "демонстрационный скриншот", font=SMALL, fill=(225,240,250))
    messages = [
        "Ты дома?",
        "Да, только зашла",
        "Сегодня было очень хорошо",
        "Мне тоже. Даже несмотря на дождь",
        "Тогда повторим?",
    ]
    y = 170
    for idx, text in enumerate(messages):
        outgoing = (idx % 2 == 0) ^ outgoing_first
        box_w = 600 if len(text) > 24 else 410
        x = width - box_w - 38 if outgoing else 38
        fill = (204, 241, 192, 255) if outgoing else (255, 255, 255, 255)
        draw.rounded_rectangle((x, y, x + box_w, y + 122), radius=28, fill=fill, outline=(0,0,0,18))
        draw.text((x + 26, y + 25), text, font=SMALL, fill=(38,43,46))
        draw.text((x + box_w - 88, y + 88), f"2{number}:{idx}0", font=SMALL, fill=(100,112,117))
        y += 152
    draw.text((38, height - 70), "ВРЕМЕННЫЙ МАКЕТ · НЕ РЕАЛЬНАЯ ПЕРЕПИСКА", font=SMALL, fill=(90,100,105))
    return image


for index in range(1, 5):
    make_chat(index, outgoing_first=index % 2 == 0).save(TG / f"chat-{index:02d}.jpg", quality=90, optimize=True)

print(f"Created demo media in {OUT}")
