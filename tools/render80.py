#!/usr/bin/env python3
"""render80.py - TXA's screens from the simulator: text dumps and PNGs.

Adds to the skill's render.py what TXA needs: the F18A's 80-column text
mode (T80) in 24 or 30 rows, the bitmap layer in both pixel formats
(2 bpp and 4 bpp fat pixels) placed on the F18A's 256-pixel grid over
80-column text, and Graphics I for the full-screen picture view.

The PNG is 960 pixels wide whatever the mode: a T80 pixel is 2 wide
(80 x 6 x 2) and a 256-grid pixel is 3.75 wide, the ratio the F18A
draws them in.  Scanlines are 3.75 tall, so a 256 x 192 screen comes out
4:3 with square grid pixels, as on a monitor."""
from PIL import Image

STDPAL = [0x000, 0x000, 0x2C3, 0x5D6, 0x54F, 0x76F, 0xD54, 0x4EF, 0xF54, 0xF76,
          0xDC3, 0xED6, 0x2B2, 0xC5C, 0xCCC, 0xFFF]

def is_t80(m):
    return bool(m.vregs[0] & 4) and bool(m.vregs[1] & 0x10)

def rows(m):
    return 30 if (m.f18a and m.unlocked and m.vregs[49] & 0x40) else 24

def screen(m, reverse_marks=False):
    """The name table as text: 80 or 32 columns, 24 or 30 rows.  Reverse
    glyphs (>80 set) read as their plain letters."""
    cols = 80 if is_t80(m) else 32
    base = (m.vregs[2] & 15) * 0x400
    out = []
    for r in range(rows(m)):
        line = ''
        for c in range(cols):
            ch = m.vram[base + r * cols + c] & 0x7F
            line += chr(ch) if 32 <= ch < 127 else ' '
        out.append(line.rstrip())
    return '\n'.join(out)

def attrs(m, row):
    """The attribute bytes of one T80 row (position attributes)."""
    at = m.vregs[3] << 6
    return bytes(m.vram[at + row * 80: at + row * 80 + 80])

def render(m, path):
    pal = m.palette
    def rgb(i):
        v = pal.get(i, STDPAL[i & 15] if i < 16 else 0)
        return ((v >> 8 & 15) * 17, (v >> 4 & 15) * 17, (v & 15) * 17)
    v = m.vregs
    nrow = rows(m)
    YS = 3.75
    H = int(nrow * 8 * YS)
    img = Image.new('RGB', (960, H), rgb(v[7] & 15)); px = img.load()
    nt = (v[2] & 15) * 0x400; pt = (v[4] & 7) * 0x800
    posattr = m.f18a and m.unlocked and v[50] & 2      # per-cell colours (T80)
    at = v[3] << 6
    def plot(x0, x1, y, col):                  # one span of one scanline, in canvas units
        for Y in range(int(y * YS), int((y + 1) * YS)):
            for X in range(int(x0), int(x1)):
                if 0 <= X < 960 and Y < H:
                    px[X, Y] = col
    if is_t80(m):
        fg0, bg0 = rgb(v[7] >> 4), rgb(v[7] & 15)
        for r in range(nrow):
            for c in range(80):
                ch = m.vram[nt + r * 80 + c]
                if posattr:
                    a = m.vram[(at + r * 80 + c) & 0x3FFF]; fg, bg = rgb(a >> 4), rgb(a & 15)
                else:
                    fg, bg = fg0, bg0
                for y in range(8):
                    b = m.vram[pt + ch * 8 + y]
                    for x in range(6):
                        plot((c * 6 + x) * 2, (c * 6 + x) * 2 + 2, r * 8 + y, fg if b >> (7 - x) & 1 else bg)
    else:                                       # Graphics I
        ct = v[3] * 0x40
        for r in range(nrow):
            for c in range(32):
                ch = m.vram[nt + r * 32 + c]; col = m.vram[ct + ch // 8]
                for y in range(8):
                    b = m.vram[pt + ch * 8 + y]
                    for x in range(8):
                        ci = col >> 4 if b >> (7 - x) & 1 else col & 15
                        X = (c * 8 + x) * 3.75
                        plot(X, X + 3.75, r * 8 + y, rgb(ci or (v[7] & 15)))
    if m.f18a and m.unlocked and v[31] & 0x80 and v[36]:
        base = v[32] * 64; bx, by = v[33], v[34]
        bw, bh = v[35] or 256, v[36]
        fat, trans, ps = v[31] & 0x10, v[31] & 0x20, v[31] & 15
        stride = (bw + 3) >> 2
        for y in range(bh):
            Y = by + y
            if Y >= nrow * 8:
                break
            for x in range(bw):
                X = bx + x
                if X >= 256:                    # cropped, not wrapped (F18A)
                    break
                b = m.vram[(base + y * stride + x // 4) & 0x3FFF]
                if fat:
                    c = (b >> 4) if (x % 4) < 2 else (b & 15); ci = ((ps & 0xC) << 2) | c
                else:
                    c = (b >> ((3 - x % 4) * 2)) & 3; ci = (ps << 2) | c
                if c or not trans:
                    plot(X * 3.75, (X + 1) * 3.75, Y, rgb(ci))
    img.save(path)
