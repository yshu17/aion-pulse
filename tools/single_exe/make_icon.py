"""Temporary icon of Pulse+.exe: a dark rounded tile with the orange pulse line of Pulse's accent.

Draws at 1024 px and scales down, so the small sizes stay smooth. Writes pulse.ico (16 to 256 px) next to this file.
Usage: python tools/single_exe/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
S = 1024
TOP, BOTTOM = (34, 40, 58), (10, 12, 17)  # the tile's gradient, top to bottom
ORANGE, HOT = (255, 138, 31), (255, 196, 110)  # the accent of Pulse and its lit core
PULSE = [(150, 540), (352, 540), (420, 420), (488, 652), (566, 286), (640, 604), (704, 540), (874, 540)]


def tile() -> Image.Image:
    grad = Image.new("RGBA", (S, S))
    draw = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / (S - 1)
        draw.line([(0, y), (S, y)], fill=tuple(round(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3)) + (255,))
    return grad


def main() -> None:
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([36, 36, S - 36, S - 36], radius=232, fill=255)

    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    base.paste(tile(), (0, 0), mask)

    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).line(PULSE, fill=ORANGE + (255,), width=84, joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(34))
    base = Image.alpha_composite(base, glow)

    line = ImageDraw.Draw(base)
    line.line(PULSE, fill=ORANGE + (255,), width=44, joint="curve")
    for x, y in (PULSE[0], PULSE[-1]):
        line.ellipse([x - 22, y - 22, x + 22, y + 22], fill=ORANGE + (255,))
    cx, cy = PULSE[4]
    line.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], fill=HOT + (255,))  # the peak glows

    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
    final = out.resize((256, 256), Image.LANCZOS)
    final.save(HERE / "pulse.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    final.save(HERE / "pulse_preview.png")
    print("wrote", HERE / "pulse.ico")


if __name__ == "__main__":
    main()
