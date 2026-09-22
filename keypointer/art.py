import math

from PIL import Image, ImageChops, ImageDraw


def _parse_color(text):
    try:
        s = str(text).lstrip("#")
        if len(s) == 6:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        pass
    return (255, 102, 196)


def draw_cursor(cx, cy, radius, color, trail, pulse, disabled):
    r, g, b = _parse_color(color)
    if disabled:
        r = g = b = 128
    eff = float(radius) * (1.0 + 0.35 * max(0.0, float(pulse)))
    side = 2 * int(math.ceil(eff * 2.6)) + 1
    pad = side // 2
    left = int(round(cx)) - pad
    top = int(round(cy)) - pad
    img = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = side / 2.0
    if trail:
        tr = max(1, int(0.4 * eff))
        for px, py, a in trail:
            x = c + (float(px) - cx)
            y = c + (float(py) - cy)
            d.ellipse((x - tr, y - tr, x + tr, y + tr), fill=(r, g, b, int(a)))
    if not disabled:
        for i in range(8):
            rad = eff * (1.15 + 0.14 * i)
            alpha = int(120 * (1.0 - i / 8.0))
            if alpha <= 0:
                break
            width = max(1, int(eff * (0.09 - 0.008 * i)))
            d.ellipse((c - rad, c - rad, c + rad, c + rad), outline=(r, g, b, alpha), width=width)
    ring_r = eff * 0.85
    d.ellipse(
        (c - ring_r, c - ring_r, c + ring_r, c + ring_r),
        outline=(r, g, b, 255),
        width=max(1, int(ring_r * 0.08)),
    )
    if not disabled:
        d.arc(
            (c - ring_r, c - ring_r, c + ring_r, c + ring_r),
            -60, 30,
            fill=(255, 255, 255, 255),
            width=max(1, int(ring_r * 0.12)),
        )
    dot_r = max(1.0, ring_r * 0.18)
    d.ellipse((c - dot_r, c - dot_r, c + dot_r, c + dot_r), fill=(255, 255, 255, 255))
    ch_r, ch_g, ch_b, ch_a = img.split()
    ch_r = ImageChops.multiply(ch_r, ch_a)
    ch_g = ImageChops.multiply(ch_g, ch_a)
    ch_b = ImageChops.multiply(ch_b, ch_a)
    out = Image.merge("RGBA", (ch_b, ch_g, ch_r, ch_a))
    return out.tobytes("raw", "BGRA"), left, top, side


def draw_tray_icon(size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = max(3, size // 16)
    d.ellipse(
        (pad, pad, size - pad, size - pad),
        outline=(255, 255, 255, 255),
        width=max(3, size // 10),
    )
    dot = size // 6
    d.ellipse(
        (size / 2 - dot, size / 2 - dot, size / 2 + dot, size / 2 + dot),
        fill=(255, 255, 255, 255),
    )
    return img