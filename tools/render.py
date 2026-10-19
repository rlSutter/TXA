#!/usr/bin/env python3
"""Render the simulated screen to a PNG: render.py cart.bin out.png [keys]

Graphics I tiles (or F18A enhanced colour mode 1), the F18A's second tile layer
and bitmap layer, and sprites; tables found through VR2-VR6 as on the chip;
colours from the program's F18A palette, else the 9918A's standard 16."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import sim9900 as S
from PIL import Image

def run(cart, keys):
    m = S.Machine(cart); cpu = S.CPU(m); m.keys = [S.key_pos(c) for c in keys]
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    while m.insns < S.KEY_AT + S.KEY_PERIOD * (len(keys) + 1):
        cpu.step()
    return m

# the F18A's power-on palette: the TMS9918A's 16 colours as 12-bit RGB
STDPAL = [0x000, 0x000, 0x2C3, 0x5D6, 0x54F, 0x76F, 0xD54, 0x4EF, 0xF54, 0xF76, 0xDC3, 0xED6, 0x2B2, 0xC5C, 0xCCC, 0xFFF]
def render(m, path, scale=3):
    pal = m.palette
    def rgb(i):
        v = pal.get(i, STDPAL[i & 15] if i < 16 else 0); return ((v >> 8 & 15) * 17, (v >> 4 & 15) * 17, (v & 15) * 17)
    nt = (m.vregs[2] & 15) * 0x400      # the tables where the VDP's registers put them
    ct = m.vregs[3] * 0x40
    pt = (m.vregs[4] & 7) * 0x800
    ecm = (m.vregs[49] >> 4) & 3 if (m.f18a and m.unlocked) else 0
    img = Image.new('RGB', (256, 192), rgb(m.vregs[7] & 15)); px = img.load()
    for r in range(24):
        for c in range(32):
            ch = m.vram[nt + r * 32 + c]
            if ecm == 1:
                ps = m.vram[ct + ch] & 15
                fg, bg = ps * 2 + 1, ps * 2
            else:
                col = m.vram[ct + ch // 8]; fg, bg = col >> 4, col & 15
            for y in range(8):
                b = m.vram[pt + ch * 8 + y]
                for x in range(8):
                    ci = fg if b >> (7 - x) & 1 else bg
                    if ci or ecm: px[c * 8 + x, r * 8 + y] = rgb(ci)
    # F18A tile layer 2 (drawn last, above sprites, by default) - collected here, applied at the end
    tl2 = None
    if m.f18a and m.unlocked and m.vregs[49] & 0x80:
        nt2 = (m.vregs[10] & 15) * 0x400; ct2 = m.vregs[11] * 0x40
        tl2 = (nt2, ct2)
    # F18A bitmap layer (2 bpp), drawn under sprites
    v = m.vregs
    if m.f18a and m.unlocked and v[31] & 0x80:
        base = v[32] * 64; bx, by = v[33], v[34]
        bw, bh = v[35] or 256, v[36] or 256
        ps = v[31] & 15; trans = v[31] & 0x20; pri = v[31] & 0x40
        ecm_t = (v[49] >> 4) & 3
        if not pri and ecm_t:      # ECM tiles are opaque: the layer is hidden without priority
            bh = 0
        stride = bw // 4
        for y in range(bh):
            for x in range(bw):
                b = m.vram[(base + y * stride + x // 4) & 0x3FFF]
                c = (b >> ((3 - x % 4) * 2)) & 3
                if c or not trans:
                    X, Y = bx + x, by + y
                    if X < 256 and Y < 192:
                        px[X, Y] = rgb(ps * 4 + c)
    big = m.vregs[1] & 2
    mag = 2 if m.vregs[1] & 1 else 1
    secm = (m.vregs[49] & 3) if (m.f18a and m.unlocked) else 0
    spt = (m.vregs[6] & 7) * 0x800
    sat = (m.vregs[5] & 0x7F) * 0x80
    entries = []
    i = sat
    while m.vram[i] != 0xD0 and i < sat + 0x80:
        entries.append(i); i += 4
    for i in reversed(entries):            # lower sprite numbers have priority: draw them last
        sy, sx, pt, cl = m.vram[i:i + 4]; sy = (sy + 1) & 255
        if sy > 224: sy -= 256
        if big:
            pt &= 0xFC
            quads = [(0, 0, 0), (1, 0, 8), (2, 8, 0), (3, 8, 8)]   # (pattern offset, dx, dy)
        else:
            quads = [(0, 0, 0)]
        for q, dx, dy in quads:
            for y in range(8):
                b0 = m.vram[spt + (pt + q) * 8 + y]
                b1 = m.vram[spt + 0x800 + (pt + q) * 8 + y] if secm >= 2 else 0
                for x in range(8):
                    c = (b0 >> (7 - x) & 1) | ((b1 >> (7 - x) & 1) << 1)
                    if not c: continue
                    for my in range(mag):
                        for mx in range(mag):
                            X, Y = sx + (dx + x) * mag + mx, sy + (dy + y) * mag + my
                            if 0 <= X < 256 and 0 <= Y < 192:
                                px[X, Y] = rgb((cl & 15) * 4 + c) if secm >= 2 else (rgb((cl & 15) * 2 + c) if secm == 1 else rgb(cl & 15))
    if tl2:
        nt2, ct2 = tl2
        for r in range(24):
            for c in range(32):
                ch = m.vram[nt2 + r * 32 + c]
                at = m.vram[ct2 + ch]; ps = at & 15; trans = at & 0x10
                for y in range(8):
                    b = m.vram[ch * 8 + y]
                    for x in range(8):
                        pix = b >> (7 - x) & 1
                        if pix == 0 and trans: continue
                        px[c * 8 + x, r * 8 + y] = rgb(ps * 2 + pix)
    img.resize((256 * scale, 192 * scale), Image.NEAREST).save(path)

if __name__ == '__main__':
    cart = open(sys.argv[1], 'rb').read()
    render(run(cart, sys.argv[3] if len(sys.argv) > 3 else 'Q'), sys.argv[2])
