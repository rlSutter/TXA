#!/usr/bin/env python3
"""txpics.py - pictures for the TI build: PNG to the F18A bitmap layer.

A story declares pictures by name and file (PICTURE Harbour "HARBOUR");
the story image itself holds only their numbers (portability rule 3).
This tool, part of the TI build, converts each picture's PNG and lays the
results out as the picture area, which the engine finds in SAMS right
after the story.

Formats (the F18A bitmap layer, 96 rows high, 256 screen pixels wide):
  2 - 256 x 96, 2 bits a pixel, 4 colours: chosen when the PNG uses at
      most four colours (sharp line art)
  4 - 128 x 96 "fat" pixels, 4 bits a pixel, 16 colours: otherwise (the
      PNG is scaled to 128 x 96 and reduced to 16 colours)
Either way the pixel data is 6144 bytes, most significant pixel first,
then run-length packed (tools/rlepack.py).  Each picture carries its own
palette (12-bit RGB), loaded into F18A palette entries 32-47 when shown.

The picture area:
  word  count
  count x long  each picture's offset from the area's start
  then each picture: byte format (2 or 4), byte colours (4 or 16),
                     that many palette words (>0RGB), the packed pixels
The engine reads it through SAMS window D (src/picture.a99)."""
import os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rlepack import pack, unpack

W, H = 256, 96

def rgb12(r, g, b):
    return (round(r / 17) << 8) | (round(g / 17) << 4) | round(b / 17)

def rgb_of12(v):
    return ((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17

def encode(px, w, h, bpp):
    out, per = bytearray(), 8 // bpp
    for y in range(h):
        for x0 in range(0, w, per):
            b = 0
            for k in range(per):
                b = (b << bpp) | (px[y * w + x0 + k] & ((1 << bpp) - 1))
            out.append(b)
    return bytes(out)

def convert(path):
    """A PNG as (format, palette words, raw 6144 bytes, preview Image)."""
    im = Image.open(path).convert('RGB')
    colours = im.getcolors(1 << 16) or []
    if len(colours) <= 4:
        if im.size != (W, H):
            im = im.resize((W, H), Image.NEAREST)
        cols = sorted(c for _, c in im.getcolors(1 << 16))
        index = {c: i for i, c in enumerate(cols)}
        px = [index[im.getpixel((x, y))] for y in range(H) for x in range(W)]
        pal = [rgb12(*c) for c in cols] + [0] * (4 - len(cols))
        return 2, pal, encode(px, W, H, 2), preview(px, W, pal, 1)
    small = im.resize((W // 2, H), Image.LANCZOS) if im.size != (W // 2, H) else im
    q = small.quantize(colors=16, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    flat = q.getpalette()[:48]
    flat += [0] * (48 - len(flat))
    pal = [rgb12(*flat[i * 3:i * 3 + 3]) for i in range(16)]
    px = list(q.getdata())
    return 4, pal, encode(px, W // 2, H, 4), preview(px, W // 2, pal, 2)

def preview(px, w, pal, sx):
    """What the TI shows (palette at 12 bits), at 2x, for checking by eye."""
    im = Image.new('RGB', (w, H))
    im.putdata([rgb_of12(pal[p]) for p in px])
    return im.resize((w * sx * 2, H * 2), Image.NEAREST)

def record(path):
    fmt, pal, raw, _ = convert(path)
    assert len(raw) == 6144
    packed = pack(raw)
    assert unpack(packed) == raw
    out = bytearray([fmt, len(pal)])
    for v in pal:
        out += v.to_bytes(2, 'big')
    return bytes(out + packed)

def find_png(name, dirs):
    for d in dirs:
        for cand in (name, name.lower(), name.upper()):
            p = os.path.join(d, cand + '.png')
            if os.path.exists(p):
                return p
    return None

def picture_area(info, dirs):
    """The picture area for a compiled story (compile_file's info), PNGs
    looked for in dirs; b'' when the story declares no pictures."""
    pics = info['program'].pictures
    if not pics:
        return b''
    recs = []
    for sym in sorted(pics, key=lambda s: s.number):
        fname = sym.decl.path
        p = find_png(fname, dirs)
        if p is None:
            sys.exit(f'picture {sym.name}: no {fname}.png in ' + ', '.join(dirs))
        recs.append(record(p))
    off = 2 + 4 * len(recs)
    out = bytearray(len(recs).to_bytes(2, 'big'))
    offs = []
    for r in recs:
        offs.append(off); off += len(r)
    for o in offs:
        out += o.to_bytes(4, 'big')
    for r in recs:
        out += r
    return bytes(out)

def read_area(area):
    """The reference reader: [(format, palette, raw pixels)] (tests use it)."""
    n = int.from_bytes(area[:2], 'big'); res = []
    for k in range(n):
        o = int.from_bytes(area[2 + 4 * k:6 + 4 * k], 'big')
        fmt, nc = area[o], area[o + 1]
        pal = [int.from_bytes(area[o + 2 + 2 * i:o + 4 + 2 * i], 'big') for i in range(nc)]
        res.append((fmt, pal, unpack(area[o + 2 + 2 * nc:])))
    return res

if __name__ == '__main__':
    for p in sys.argv[1:]:
        fmt, pal, raw, prev = convert(p)
        out = os.path.splitext(p)[0] + '-ti.png'
        prev.save(out)
        print(f'{p}: format {fmt}, {len(pal)} colours, packed {len(pack(raw))} bytes; preview {out}')
