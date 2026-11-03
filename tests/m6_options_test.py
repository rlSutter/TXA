#!/usr/bin/env python3
"""m6_options_test.py - the options (O, M6 part 10): colours, font and
library devices, kept in DSK1.TXAOPT.  Without the file, the workbench
looks as before.  O shows them; C gives white on dark blue (palette 14
and 1); F the bold font (each glyph ORed with itself a pixel right, its
inverted copy too); L types the library devices; ENTER writes TXAOPT.  A
fresh start reads it back.  With Lamplight's library only on DSK2, the
compile finds it there.  FCTN 9 puts the colours back.

  python3 tests/m6_options_test.py"""
import os, sys, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); os.chdir(ROOT)
src = open(os.path.join(ROOT, 'tests/m5_sema_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m5_sema_test.py'), '__name__': 'op'}
sys.argv = ['op', 'none']
exec(compile(src[:src.index('args = sys.argv[1:]')], 'm5', 'exec'), g)
S, sy, R, keys_for, DATE = g['S'], g['sy'], g['R'], g['keys_for'], g['DATE']
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:700]))
    fails += 0 if ok else 1
PATTAB = 0x1800
def session(d, keys, max_steps=300_000_000):
    m = S.Machine(g['cart'], f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    snaps = []; queue = list(keys); steps = hold = free = 0; dated = False
    while steps < max_steps:
        if cpu.pc == sy['WK1'] and not dated:
            for i, c in enumerate(DATE.strftime('%y%m%d').encode()):
                m.wb(sy['WDATE'] + i, c)
            dated = True
        if cpu.pc == sy['WK1'] and not hold and steps >= free:
            snaps.append({'pal': dict(m.palette), 'pat': bytes(m.vram[PATTAB:PATTAB + 2048]), 'screen': R.screen(m)})
            if not queue:
                break
            m.held = queue.pop(0); hold = steps + 12_000
        if hold and steps >= hold:
            m.held = None; hold = 0; free = steps + 12_000
        cpu.step(); steps += 1
    return m, snaps
k = lambda s: keys_for(s)[:-1]
ENTER = keys_for('')
d, pp = g['stage'](open('samples/lamplight.txa').read(), 'lamplight', g['LIB'])
m, sn = session(d, k('o') + k('c') + k('f') + k('l') + keys_for('dsk2.') + ENTER)
s0, so = sn[0], sn[1]
check('no DSK1.TXAOPT: the colours as before (palette 14 >AAA, 1 >000)', s0['pal'].get(14) == 0xAAA and s0['pal'].get(1) == 0x000, (s0['pal'].get(14), s0['pal'].get(1)))
scr = so['screen'].splitlines()
check('O shows the options: colours gray on black, font normal, library none',
      scr[5].strip() == 'C  Colours: gray on black' and scr[6].strip() == 'F  Font: normal' and scr[7].strip() == 'L  Library devices: none', scr[3:10])
sc = sn[2]
check('C: white on dark blue (palette 14 >FFF, 1 >008), said on row 5', sc['pal'].get(14) == 0xFFF and sc['pal'].get(1) == 0x008
      and sc['screen'].splitlines()[5].strip() == 'C  Colours: white on dark blue', (sc['pal'].get(14), sc['pal'].get(1)))
normal, bold = s0['pat'], sn[3]['pat']
want_b = bytes((b | (b >> 1)) for b in normal[32 * 8:127 * 8])
want_i = bytes((~(b | (b >> 1))) & 0xFF for b in normal[32 * 8:127 * 8])
check('F: the bold font: glyphs 32-126 ORed a pixel right, their inverted copies (160-254) too',
      bold[32 * 8:127 * 8] == want_b and bold[160 * 8:255 * 8] == want_i and 'F  Font: bold' in sn[3]['screen'])
t = open(os.path.join(d, 'DSK1', 'TXAOPT')).read().split('\n') if os.path.exists(os.path.join(d, 'DSK1', 'TXAOPT')) else None
check('L, "dsk2.", ENTER; ENTER: DSK1.TXAOPT written: "colours 1", "font bold", "library DSK2."',
      t is not None and t[:3] == ['colours 1', 'font bold', 'library DSK2.'], t)
m2, sn2 = session(d, [])
s2 = sn2[-1]
check('a fresh start reads it: white on dark blue, the bold font, the library device kept',
      s2['pal'].get(14) == 0xFFF and s2['pat'][32 * 8:127 * 8] == want_b
      and bytes(m2.rb(sy['OPLSTR'] + 1 + i) for i in range(5)) == b'DSK2.',
      (s2['pal'].get(14),))
os.makedirs(os.path.join(d, 'DSK2'), exist_ok=True)
moved = []
for n in os.listdir(os.path.join(d, 'DSK1')):
    if n not in ('LAMPLIGHT', 'TXAOPT'):
        shutil.move(os.path.join(d, 'DSK1', n), os.path.join(d, 'DSK2', n)); moved.append(n)
m3, sn3 = session(d, k('p') + keys_for('dsk1.lamplight') + ENTER + ENTER + k('c'))
check(f'the library only on DSK2 ({len(moved)} files): the compile finds it there, without errors',
      m3.rw(sy['WBERR']) == 0 and os.path.exists(os.path.join(d, 'DSK1', 'LAMPLIS01')), (m3.rw(sy['WBERR']), sn3[-1]['screen'].splitlines()[4:10]))
check('the settings survive a 9-file compile (the file table once ran over them): colours 1, font bold, library DSK2.',
      m3.rw(sy['OPCOL']) == 1 and m3.rw(sy['OPFNT']) == 1 and bytes(m3.rb(sy['OPLSTR'] + 1 + i) for i in range(5)) == b'DSK2.',
      (m3.rw(sy['OPCOL']), m3.rw(sy['OPFNT']), bytes(m3.rb(sy['OPLSTR'] + i) for i in range(8))))
m4, sn4 = session(d, k('o') + k('c') + keys_for('\x0e')[:-1])
s4 = sn4[-1]
check('O, C (green on black), FCTN 9: the colours put back (white on dark blue), TXAOPT unchanged',
      sn4[2]['pal'].get(14) == 0x3D3 and s4['pal'].get(14) == 0xFFF and open(os.path.join(d, 'DSK1', 'TXAOPT')).read().startswith('colours 1'),
      (sn4[2]['pal'].get(14), s4['pal'].get(14)))
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
