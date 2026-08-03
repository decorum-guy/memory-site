#!/usr/bin/env python3
"""Generate QR and extra Telegram placeholders for the Chromium design preview."""
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "preview" / "demo-media"
TG = ROOT / "media" / "telegram"
DEMO.mkdir(parents=True, exist_ok=True)
TG.mkdir(parents=True, exist_ok=True)

try:
    FONT = ImageFont.truetype("DejaVuSans.ttf", 30)
    SMALL = ImageFont.truetype("DejaVuSans.ttf", 20)
except OSError:
    FONT = ImageFont.load_default()
    SMALL = ImageFont.load_default()

# A real QR code so its proportions and contrast are tested honestly.
qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=12, border=4)
qr.add_data("https://www.icloud.com/sharedalbum/#demo-memory")
qr.make(fit=True)
qr.make_image(fill_color="#342c25", back_color="#fffaf0").save(DEMO / "shared-album-qr.png")


def chat_page(index: int) -> Image.Image:
    width, height = 900, 1350
    image = Image.new("RGB", (width, height), (226, 234, 239))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, width, 105), fill=(73, 119, 151, 255))
    draw.text((36, 25), "Соня", font=FONT, fill="white")
    y = 155
    messages = [
        f"Фрагмент {index}: это временный макет",
        "Проверяем, как выглядит большая Telegram-глава",
        "И можно ли смешивать карточки с PNG-вырезками",
        "Да, это не настоящая переписка",
    ]
    for position, text in enumerate(messages):
        outgoing = (position + index) % 2 == 0
        box_width = 650
        x = width - box_width - 30 if outgoing else 30
        color = (205, 241, 194, 255) if outgoing else (255, 255, 255, 255)
        draw.rounded_rectangle((x, y, x + box_width, y + 130), radius=26, fill=color, outline=(0, 0, 0, 20))
        draw.text((x + 24, y + 26), text, font=SMALL, fill=(35, 41, 44))
        y += 160
    draw.text((30, height - 55), "ДЕМО · НЕ РЕАЛЬНАЯ ПЕРЕПИСКА", font=SMALL, fill=(92, 102, 107))
    return image


for index in range(5, 11):
    chat_page(index).save(TG / f"chat-{index:02d}.jpg", quality=90, optimize=True)


def cutout(index: int, color: tuple[int, int, int, int]) -> Image.Image:
    image = Image.new("RGBA", (980, 620), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    x = 45 if index == 1 else 210
    width = 720
    draw.rounded_rectangle((x, 75, x + width, 390), radius=58, fill=color, outline=(40, 45, 47, 35), width=3)
    draw.polygon([(x + 90, 390), (x + 135, 505), (x + 230, 390)], fill=color)
    draw.text((x + 48, 145), "Прозрачная PNG-вырезка", font=FONT, fill=(39, 43, 45, 255))
    draw.text((x + 48, 215), "Форма не обязана быть прямоугольной", font=SMALL, fill=(70, 76, 79, 255))
    return image


cutout(1, (205, 241, 194, 255)).save(TG / "chat-cutout-01.png")
cutout(2, (255, 255, 255, 255)).save(TG / "chat-cutout-02.png")
print("Created Shared Album QR and extended Telegram preview media")
