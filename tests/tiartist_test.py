#!/usr/bin/env python3
"""tiartist_test.py - TI Artist pictures (M6 part 9, tools/tiartist.py):
decoding, the two fittings, the record (packed, unpacking to the pixels),
txpics finding NAME_P/NAME_C with NAME_T's choice.  tests/data/BIRD_P
and BIRD_C are Rebecca's sample (a hummingbird), with TIFILES headers.

  python3 tests/tiartist_test.py"""
import os, sys, tempfile, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); os.chdir(ROOT)
import tiartist, txpics, rlepack
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:800]))
    fails += 0 if ok else 1
pat, col = tiartist.read_file('tests/data/BIRD_P'), tiartist.read_file('tests/data/BIRD_C')
rows = tiartist.pixels(pat, col)
check('the files: 6144 bytes each once the TIFILES header is off; 256 x 192 pixels', len(pat) == len(col) == 6144 and len(rows) == 192 and len(rows[0]) == 256)
check('a cell decoded by hand: cell 0 row 0, all background (colour 1 on 1)', rows[0][:8] == [1] * 8 and col[0] == 0x11, (rows[0][:8], hex(col[0])))
# a known pixel: find a foreground pixel and check it against the bytes
cell = next(i for i in range(768) if any(pat[i * 8 + r] for r in range(8)))
r = next(r for r in range(8) if pat[cell * 8 + r]); b = next(b for b in range(8) if pat[cell * 8 + r] & (0x80 >> b))
check(f'a foreground pixel (cell {cell}, row {r}, bit {b}) takes the colour byte\'s high nybble',
      rows[(cell // 32) * 8 + r][(cell % 32) * 8 + b] == col[cell * 8 + r] >> 4)
for how in (('crop', 0), ('crop', 48), ('crop', 96), ('squeeze', 0)):
    fat = tiartist.fit(rows, how)
    rec = tiartist.record(pat, col, how)
    data = rlepack.unpack(rec[2 + 32:])
    ok = rec[0] == 4 and rec[1] == 16 and data == tiartist.raw(fat) and len(data) == 6144
    check(f'{how[0]} {how[1] if how[0] == "crop" else ""}: a format-4 record, 16 colours, {len(rec)} bytes; it unpacks to the fitted pixels', ok)
fat = tiartist.fit(rows, ('crop', 48))
check('crop: a fat pixel is its pair\'s first pixel unless that is background', all(
    fat[y][x] == tiartist.pick(rows[48 + y][2 * x], rows[48 + y][2 * x + 1]) for y in range(96) for x in range(128)))
sq = tiartist.fit(rows, ('squeeze', 0))
check('squeeze: rows paired first, then pixels', all(
    sq[y][x] == tiartist.pick(tiartist.pick(rows[2 * y][2 * x], rows[2 * y + 1][2 * x]), tiartist.pick(rows[2 * y][2 * x + 1], rows[2 * y + 1][2 * x + 1]))
    for y in range(96) for x in range(128)))
try:
    tiartist.fit(rows, ('crop', 97)); bad = False
except ValueError:
    bad = True
check('a band must start at an even row from 0 to 96', bad)
d = tempfile.mkdtemp()
shutil.copy('tests/data/BIRD_P', os.path.join(d, 'BIRD_P')); shutil.copy('tests/data/BIRD_C', os.path.join(d, 'BIRD_C'))
check('no BIRD_T: crop 48', tiartist.settings(os.path.join(d, 'BIRD')) == ('crop', 48))
open(os.path.join(d, 'BIRD_T'), 'w').write('squeeze\n')
check('BIRD_T "squeeze": squeeze', tiartist.settings(os.path.join(d, 'BIRD')) == ('squeeze', 0))
open(os.path.join(d, 'BIRD_T'), 'w').write('crop 20\n')
f = tiartist.find('BIRD', [d])
check('find: BIRD_P and BIRD_C', f is not None and f[0].endswith('BIRD_P'))
class Sym:
    def __init__(s): s.number, s.name = 1, 'Bird'; s.decl = type('D', (), {'path': 'BIRD'})()
info = {'program': type('P', (), {'pictures': [Sym()]})()}
area = txpics.picture_area(info, [d])
recs = txpics.read_area(area)
check('txpics builds the picture area from the TI Artist files with BIRD_T\'s crop 20',
      len(recs) == 1 and area[6:] == tiartist.record(pat, col, ('crop', 20)), (len(recs), len(area)))
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
