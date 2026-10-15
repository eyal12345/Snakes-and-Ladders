"""Build-time helper: draws the snake icon and saves it as snake.ico (needs Pillow)."""

import math
import sys

from PIL import Image, ImageDraw

SIZE = 256
SCALE = 4  # draw large, then downsample for smooth edges
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def snake_path(size):
    """Points of an S-shaped snake body from tail (bottom-left) to head (top-right)."""
    points = []
    steps = 200
    for i in range(steps + 1):
        t = i / steps
        x = size * (0.20 + 0.60 * t)
        y = size * (0.80 - 0.60 * t) + size * 0.17 * math.sin(t * 2 * math.pi)
        points.append((x, y))
    return points


def draw_icon(path):
    big = SIZE * SCALE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Rounded square background
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=big // 5, fill="#fff3c4",
                           outline="#8d6e63", width=big // 40)

    # Body: overlapping circles that thicken from tail to head, with an outline pass first
    points = snake_path(big)
    for outline, color in ((True, "#1b5e20"), (False, "#43a047")):
        for i, (x, y) in enumerate(points):
            t = i / (len(points) - 1)
            r = big * (0.035 + 0.045 * t) + (big * 0.012 if outline else 0)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color)

    # Belly stripes
    for i in range(12, len(points) - 20, 16):
        x, y = points[i]
        r = big * 0.018
        draw.ellipse((x - r, y - r, x + r, y + r), fill="#c5e1a5")

    # Head
    hx, hy = points[-1]
    hr = big * 0.11
    draw.ellipse((hx - hr - big * 0.012, hy - hr - big * 0.012, hx + hr + big * 0.012, hy + hr + big * 0.012),
                 fill="#1b5e20")
    draw.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill="#43a047")

    # Eyes
    for dx in (-0.45, 0.45):
        ex, ey = hx + dx * hr, hy - 0.25 * hr
        er = hr * 0.28
        draw.ellipse((ex - er, ey - er, ex + er, ey + er), fill="white")
        pr = er * 0.5
        draw.ellipse((ex - pr, ey - pr + er * 0.2, ex + pr, ey + pr + er * 0.2), fill="black")

    # Forked tongue
    tongue_w = big // 60
    tx, ty = hx, hy + hr * 0.9
    draw.line((tx, ty, tx, ty + hr * 0.6), fill="#d32f2f", width=tongue_w)
    draw.line((tx, ty + hr * 0.6, tx - hr * 0.25, ty + hr * 0.85), fill="#d32f2f", width=tongue_w)
    draw.line((tx, ty + hr * 0.6, tx + hr * 0.25, ty + hr * 0.85), fill="#d32f2f", width=tongue_w)

    icon = image.resize((SIZE, SIZE), Image.LANCZOS)
    icon.save(path, format="ICO", sizes=ICON_SIZES)
    icon.save(path.rsplit(".", 1)[0] + ".png")


if __name__ == "__main__":
    draw_icon(sys.argv[1] if len(sys.argv) > 1 else "snake.ico")
    print("Icon written.")
