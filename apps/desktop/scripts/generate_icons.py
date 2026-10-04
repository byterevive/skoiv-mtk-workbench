#!/usr/bin/env python3
"""Generate the Skoiv MTK Workbench app icons from a single vector-ish design.

Requires Pillow. Run from anywhere:
    python3 apps/desktop/scripts/generate_icons.py
Outputs into apps/desktop/src-tauri/icons/.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src-tauri", "icons")

BG = (15, 23, 42, 255)  # slate-900
CHIP = (34, 211, 238, 255)  # cyan-400
DIE = (14, 116, 144, 255)  # cyan-700
PAD = (56, 189, 248, 255)  # sky-400


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 128.0

    # Rounded background
    radius = int(28 * s)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)

    # Chip body
    chip = [int(28 * s), int(28 * s), int(100 * s), int(100 * s)]
    d.rounded_rectangle(chip, radius=int(10 * s), outline=CHIP, width=max(2, int(5 * s)))

    # Chip pins (3 per side)
    pin_len = int(12 * s)
    pin_w = max(2, int(5 * s))
    for i in range(3):
        t = int((42 + i * 14) * s)
        # left/right pins
        d.rectangle([chip[0] - pin_len, t, chip[0] - 1, t + pin_w], fill=PAD)
        d.rectangle([chip[2] + 1, t, chip[2] + pin_len, t + pin_w], fill=PAD)
        # top/bottom pins
        d.rectangle([t, chip[1] - pin_len, t + pin_w, chip[1] - 1], fill=PAD)
        d.rectangle([t, chip[3] + 1, t + pin_w, chip[3] + pin_len], fill=PAD)

    # Inner die + evidence "check" mark
    die = [int(44 * s), int(44 * s), int(84 * s), int(84 * s)]
    d.rounded_rectangle(die, radius=int(6 * s), fill=DIE)
    check = [
        (int(52 * s), int(65 * s)),
        (int(61 * s), int(74 * s)),
        (int(77 * s), int(55 * s)),
    ]
    d.line(check, fill=CHIP, width=max(2, int(6 * s)), joint="curve")

    return img


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    base = draw_icon(512)
    base.resize((32, 32), Image.LANCZOS).save(os.path.join(OUT, "32x32.png"), format="PNG")
    base.resize((128, 128), Image.LANCZOS).save(os.path.join(OUT, "128x128.png"), format="PNG")
    base.resize((256, 256), Image.LANCZOS).save(
        os.path.join(OUT, "henry.w@example.net"), format="PNG"
    )
    base.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "icon.png"), format="PNG")
    # Multi-size Windows ICO
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base.resize((256, 256), Image.LANCZOS).save(
        os.path.join(OUT, "icon.ico"), format="ICO", sizes=ico_sizes
    )
    print(f"icons written to {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
