#!/usr/bin/env python3
"""mkart.py - Lamplight's pictures, drawn in code: TITLE, CAVE, LAMPROOM.

TITLE and CAVE are 128 x 96 in 16 colours (the fat-pixel format: each
pixel is two screen pixels wide); LAMPROOM is 256 x 96 in 4 colours (the
full-resolution format).  Run it to remake the PNGs beside it."""
import math, os, random
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
B4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]   # ordered dither

def hexc(s):
    return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))

def title():
    pal = [hexc(c) for c in ['#0b0c22', '#1d1a44', '#3a2a66', '#6a3a78', '#b0506a', '#e8804a',
                             '#f8c060', '#fff0c0', '#0a1830', '#123050', '#2a5070', '#06080e',
                             '#202430', '#e8e8e0', '#b03030', '#8890a0']]
    w, h = 128, 96
    im = Image.new('RGB', (w, h)); px = im.load()
    sky = [0, 1, 2, 3, 4, 5, 6]                 # top to horizon
    horizon = 58
    for y in range(horizon):
        t = y / (horizon - 1) * (len(sky) - 1)
        a, f = int(t), t - int(t)
        b = min(a + 1, len(sky) - 1)
        for x in range(w):
            px[x, y] = pal[sky[b] if f * 16 > B4[y % 4][x % 4] else sky[a]]
    random.seed(7)
    for _ in range(18):                          # a few early stars
        x, y = random.randrange(w), random.randrange(18)
        px[x, y] = pal[15]
    d = ImageDraw.Draw(im)
    d.ellipse([84, 50, 100, 66], fill=pal[6])    # the sun, half set
    d.ellipse([86, 52, 98, 64], fill=pal[7])
    for y in range(horizon, h):                  # the sea, darkening toward us
        t = (y - horizon) / (h - horizon)
        for x in range(w):
            c = 10 if t < 0.25 else 9 if t < 0.6 else 8
            if t >= 0.25 and t < 0.32 and B4[y % 4][x % 4] < 6: c = 10
            px[x, y] = pal[c]
    for y in range(horizon, h, 2):               # the sun's path on the water
        spread = 2 + (y - horizon) // 3
        for x in range(92 - spread, 92 + spread):
            if (x + y) % 3 == 0 and 0 <= x < w:
                px[x, y] = pal[6 if y < horizon + 12 else 5]
    pts = [(96, horizon)] + [(x, horizon - 3 - int(4 * math.sin((x - 96) / 9))) for x in range(96, 129, 2)] + [(128, horizon)]
    d.polygon(pts, fill=pal[11])                 # a far headland
    d.polygon([(10, 80), (18, 70), (34, 68), (46, 74), (52, 82), (52, 96), (6, 96)], fill=pal[11])   # the rock
    d.polygon([(12, 82), (20, 73), (33, 71), (44, 76)], fill=pal[12])
    tx = 30                                      # the lighthouse
    d.polygon([(tx - 4, 71), (tx - 3, 34), (tx + 3, 34), (tx + 4, 71)], fill=pal[13])
    for yb in (44, 56):
        d.rectangle([tx - 4, yb, tx + 4, yb + 4], fill=pal[14])
    d.rectangle([tx - 5, 31, tx + 5, 33], fill=pal[12])           # the gallery
    d.rectangle([tx - 3, 25, tx + 3, 30], fill=pal[1])            # the dark lamp room
    d.line([tx - 3, 25, tx - 3, 30], fill=pal[12]); d.line([tx + 3, 25, tx + 3, 30], fill=pal[12])
    d.polygon([(tx - 4, 25), (tx, 20), (tx + 4, 25)], fill=pal[12])
    for x in range(w):                           # a lit window in the cottage on the far shore
        pass
    px[110, horizon - 2] = pal[6]
    return im

def cave():
    pal = [hexc(c) for c in ['#04060a', '#0c1218', '#18222c', '#28343e', '#3e4e58', '#64808c',
                             '#9cb4bc', '#d8e6e6', '#0a2a1a', '#1c7040', '#48c070', '#b8f8c0',
                             '#1c3c50', '#2e6078', '#f4fcfc', '#506470']]
    w, h = 128, 96
    im = Image.new('RGB', (w, h)); px = im.load(); d = ImageDraw.Draw(im)
    random.seed(3)
    # rock everywhere first, in rough bands
    for y in range(h):
        for x in range(w):
            n = math.sin(x / 7 + y / 11) + math.sin(x / 3.1 - y / 5.3) * 0.5 + random.random() * 0.5
            px[x, y] = pal[1 if n < 0.1 else 2 if n < 0.9 else 3]
    # the mouth: a ragged arch on the right, daylight sky over the sea
    mouth = [(76, 72)]
    for k in range(0, 33):
        t = k / 32 * math.pi
        r = 26 + int(1.5 * math.sin(k * 1.7))
        mouth.append((100 - int(r * math.cos(t)), 70 - int(r * 1.9 * math.sin(t))))
    mouth.append((124, 72))
    d.polygon(mouth, fill=pal[6])
    d.polygon([(76, 54), (124, 52), (124, 72), (76, 72)], fill=pal[13])       # the sea
    d.line([(76, 53), (124, 51)], fill=pal[7])                                # the horizon's glare
    for y in range(56, 72, 3):
        for x in range(78, 124):
            if (x * 3 + y) % 9 == 0: px[x, y] = pal[7]
    for y in range(18, 52):                                                   # a paler sky near the horizon
        for x in range(76, 125):
            if px[x, y] == pal[6] and y > 38 and B4[y % 4][x % 4] < (y - 38): px[x, y] = pal[7]
    for x0 in (90, 109):                                                      # rock teeth hanging in the mouth
        L = 6
        top = min(yy for yy in range(h) if px[x0, yy] in (pal[6], pal[7])) if any(px[x0, yy] in (pal[6], pal[7]) for yy in range(h)) else 20
        d.polygon([(x0 - 2, top - 1), (x0 + 2, top - 1), (x0, top + L)], fill=pal[2])
    for y in range(10, 74):                                                   # the lit rim of the mouth
        for x in range(70, 126):
            if px[x, y] in (pal[1], pal[2], pal[3]) and x + 1 < w and px[x + 1, y] in (pal[6], pal[7]):
                px[x, y] = pal[4]; px[x - 1, y] = pal[3]
    # the floor: wet stones, catching the light toward the mouth
    for _ in range(90):
        cx, cy = random.randrange(0, 124), random.randrange(74, 98)
        r = random.randrange(2, 6)
        c = 12 if cx > 70 else random.choice([2, 3])
        d.ellipse([cx - r, cy - r // 2, cx + r, cy + r // 2], fill=pal[c])
        px[min(cx + r // 2, w - 1), min(max(cy - r // 3, 0), h - 1)] = pal[5 if cx < 70 else 6]
    # the glass float: round (fat pixels are two wide, so 7 across is 14 on screen), glowing
    fx, fy = 40, 82
    for rr, c in ((11, 8), (9, 8)):                                           # its glow on the stones
        d.ellipse([fx - rr // 2 - 3, fy + 2, fx + rr // 2 + 3, fy + 6], fill=pal[c])
    d.ellipse([fx - 4, fy - 7, fx + 4, fy + 5], fill=pal[9])
    d.ellipse([fx - 3, fy - 6, fx + 3, fy + 4], fill=pal[10])
    d.ellipse([fx - 2, fy - 5, fx, fy - 2], fill=pal[11])
    px[fx - 1, fy - 5] = pal[14]
    d.line([(fx - 2, fy - 7), (fx + 2, fy - 7)], fill=pal[9])                 # its net knot
    # drips from the roof
    for x in (18, 47, 60):
        for y in range(2, 2 + random.randrange(6, 14), 2):
            px[x, y] = pal[5]
    return im

def lamproom():
    pal = [hexc(c) for c in ['#080a14', '#28385a', '#d8a040', '#f4ecd8']]
    w, h = 256, 96
    im = Image.new('RGB', (w, h), pal[0]); d = ImageDraw.Draw(im)
    for x0 in range(0, w, 64):                   # window panes, the dusk sea outside
        d.rectangle([x0 + 4, 6, x0 + 60, 60], fill=pal[1])
        d.line([x0 + 4, 40, x0 + 60, 40], fill=pal[0])
        for y in range(44, 60, 4):
            d.line([x0 + 6 + (y % 8), y, x0 + 22 + (y % 8), y], fill=pal[0])
    cx = 128                                     # the great lens: stacked prism rings
    d.rectangle([cx - 30, 10, cx + 30, 78], fill=pal[0])
    for i, y in enumerate(range(12, 76, 4)):
        half = 30 - abs(y - 44) // 3
        d.line([cx - half, y, cx + half, y], fill=pal[3] if i % 2 else pal[2])
        d.line([cx - half, y + 1, cx + half, y + 1], fill=pal[1])
    d.rectangle([cx - 6, 36, cx + 6, 52], fill=pal[1])            # the dark wick housing
    d.rectangle([cx - 2, 40, cx + 2, 48], fill=pal[0])
    d.line([cx - 30, 10, cx - 30, 78], fill=pal[3]); d.line([cx + 30, 10, cx + 30, 78], fill=pal[3])
    d.rectangle([cx - 36, 78, cx + 36, 84], fill=pal[2])          # the pedestal
    d.rectangle([0, 84, w - 1, 95], fill=pal[1])                  # the floor and railing
    for x in range(0, w, 12):
        d.line([x, 66, x, 84], fill=pal[2])
    d.line([0, 66, w - 1, 66], fill=pal[3])
    return im

if __name__ == '__main__':
    title().save(os.path.join(HERE, 'title.png'))
    cave().save(os.path.join(HERE, 'cave.png'))
    lamproom().save(os.path.join(HERE, 'lamproom.png'))
    print('title.png cave.png lamproom.png')
