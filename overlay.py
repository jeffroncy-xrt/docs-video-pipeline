"""Transparent caption/scrim overlay for footage beats (Veo / AI-still / stock).

Returns an RGBA 1920x1080 image: readability scrims + kicker + headline + caption,
all with soft shadows so they stay legible over moving footage. Composited on top
of the video by ffmpeg, so the footage keeps moving underneath.
"""
from PIL import Image, ImageDraw, ImageFilter
from viz import (W, H, GOLD, GOLD_BR, RED_BR, CREAM, MUTE,
                 body, body_b, disp, serif_i, wrap)

# Per-scene visual identity so scenes don't all look the same: distinct accent
# colour, kicker/headline position, and headline size.  (accent, kicker_y,
# headline_y, headline_size, align)  — align 'l' = left margin, 'c' = centred.
_TEAL = (70, 150, 130)
SCENE_STYLE = {
    "plain":  (GOLD,    150, 210,  72, "l"),
    "theory": (_TEAL,   140, 250,  82, "l"),
    "dna":    (_TEAL,   150, 210,  74, "l"),
    "fact":   (GOLD_BR, 170, 300,  96, "c"),
    "reveal": (RED_BR,  150, 300, 104, "c"),
    "map":    (GOLD,    150, 210,  72, "l"),
}

def scene_style(scene):
    """Pure lookup -> (accent_rgb, kicker_y, headline_y, headline_size, align)."""
    return SCENE_STYLE.get(scene, SCENE_STYLE["plain"])

def _spaced(d, xy, text, fnt, fill, ls=6):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + ls

def _text(img, xy, text, fnt, fill, anchor="la", shadow=(0, 0, 0, 210), sblur=7):
    """Alpha-safe text with a soft drop shadow (legible over bright footage)."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.text(xy, text, font=fnt, fill=shadow, anchor=anchor)
    layer = layer.filter(ImageFilter.GaussianBlur(sblur))
    img.alpha_composite(layer)
    ImageDraw.Draw(img).text(xy, text, font=fnt, fill=fill, anchor=anchor)

def _scrims(img):
    grad = Image.new("L", (1, H), 0)
    px = grad.load()
    for y in range(H):
        a = 0
        if y > H - 320:                       # bottom scrim for caption
            a = max(a, int(205 * ((y - (H - 320)) / 320) ** 1.2))
        if y < 240:                           # top scrim for kicker/headline
            a = max(a, int(150 * (1 - y / 240)))
        px[0, y] = a
    black = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    black.putalpha(grad.resize((W, H)))
    return Image.alpha_composite(img, black)

def _kicker(img, text, y=150, accent=GOLD):
    d = ImageDraw.Draw(img)
    d.rectangle([150, y + 16, 184, y + 19], fill=accent)
    # spaced caps with shadow
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _spaced(ImageDraw.Draw(layer), (200, y), text.upper(), body_b(28), (0, 0, 0, 210))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(6)))
    _spaced(ImageDraw.Draw(img), (200, y), text.upper(), body_b(28), accent)

def _headline(img, text, y=210, size=72, fill=CREAM, maxw=int(W * 0.62), align="l"):
    d = ImageDraw.Draw(img)
    fnt = disp(size)
    yy = y
    x, anchor = (W // 2, "ma") if align == "c" else (150, "la")
    mw = int(W * 0.82) if align == "c" else maxw
    for ln in wrap(d, text, fnt, mw):
        _text(img, (x, yy), ln, fnt, fill, anchor=anchor, sblur=9)
        yy += int(size * 0.92)
    return yy

def _caption(img, text):
    if not text:
        return
    d = ImageDraw.Draw(img)
    fnt = body(36)
    lines = wrap(d, text, fnt, W - 380)
    lh = 48
    y0 = H - lh * len(lines) - 90
    ImageDraw.Draw(img).rectangle([150, y0 + 6, 156, y0 + 6 + lh * len(lines)],
                                  fill=(*GOLD, 235))
    yy = y0 + 10
    for ln in lines:
        _text(img, (182, yy), ln, fnt, CREAM, sblur=6)
        yy += lh

def _credit(img, text):
    """Small muted source/attribution line, bottom-right.  Required for the CC-BY
    archival images (legal) and doubles as the on-screen source citation."""
    if not text:
        return
    _text(img, (W - 60, H - 38), text, body(16), (*MUTE, 235),
          anchor="rd", shadow=(0, 0, 0, 210), sblur=4)

def caption_overlay(beat, credit=""):
    """RGBA overlay for a footage beat (optional source-credit line)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img = _scrims(img)
    _credit(img, credit)
    s = beat["scene"]

    if s == "title":
        kick = beat.get("kicker", "THE FORGOTTEN PEOPLE")
        l1 = beat.get("line1", "MELUNGEON"); l2 = beat.get("line2", "MYSTERY")
        _spaced(ImageDraw.Draw(img), (W // 2 - 290, H // 2 - 220),
                kick, body_b(30), GOLD, ls=10)
        _text(img, (W // 2, H // 2 - 40), l1, disp(190), CREAM, anchor="ma", sblur=16)
        _text(img, (W // 2, H // 2 + 150), l2, disp(190), RED_BR, anchor="ma", sblur=18)
        return img

    if s == "outro":
        _text(img, (W // 2, H // 2 + 60), beat.get("headline", "Subscribe"),
              disp(110), CREAM, anchor="ma", sblur=14)
        if beat.get("sub"):
            _text(img, (W // 2, H // 2 + 190), beat["sub"], body(40), GOLD,
                  anchor="ma", sblur=8)
        return img

    accent, ky, hy, hsize, align = scene_style(s)
    if beat.get("kicker"):
        _kicker(img, beat["kicker"], y=ky, accent=accent)
    if beat.get("headline"):
        _headline(img, beat["headline"], y=hy, size=hsize, align=align)
    _caption(img, beat.get("cap", ""))
    return img

if __name__ == "__main__":
    from beats import BEATS
    for i in (0, 6, 14, 25, 37):
        caption_overlay(BEATS[i]).save(f"/tmp/ov_{i:02d}.png")
        print("wrote", i)
