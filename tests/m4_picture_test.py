#!/usr/bin/env python3
"""m4_picture_test.py - pictures: the converter, the picture area, the pane.

Lamplight (with its three pictures) is built for the TI and played on the
engine in the simulator.  At the title page, in the lit cave and in the
lamp room the bitmap layer must hold exactly the converter's pixels and
palette, in the right format and place, with the text window below it;
between pictures the layer is off.  The transcript must equal the Python
VM's (pictures print nothing).  A SAVE and RESTORE (disk calls overwrite
the layer's VRAM) and an UNDO must leave the right picture showing.
Screenshots go to build/shots/pic-*.png.

  python3 tests/m4_picture_test.py"""
import os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build, txpics, sim9900 as S, render80 as R
from txc.codegen import compile_file
from txc import txvm
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'm4p'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
keys_for = g['keys_for']
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:1500]))
    fails += 0 if ok else 1

srcf = os.path.join(ROOT, 'samples/lamplight.txa')
img, info = compile_file(srcf, [os.path.join(ROOT, 'lib')], title='LAMPLIGHT')
area = txpics.picture_area(info, [os.path.join(ROOT, 'samples'), os.path.join(ROOT, 'samples/pics')])
pics = txpics.read_area(area)
check('the converter: 4 pictures, formats 4, 4, 2, 4, each 6144 bytes of pixels',
      [p[0] for p in pics] == [4, 4, 2, 4] and all(len(p[2]) == 6144 for p in pics), [(p[0], len(p[2])) for p in pics])
blob, picpg, _ = build.story_blob(img, area)
check('the picture area starts on the page after the story', picpg == (len(img) + 4095) // 4096 and blob[picpg * 4096:] == area)
cart, _ = build.engine_cart(img, 'LAMPLIGHT', pictures=area)
sy = build.symbols(os.path.join(build.B, 'engine.equ'))

def run(lines, snap_after=(), disk=None, max_steps=400_000_000):
    """Type the lines; return (transcript, machine, {line index: snapshot})."""
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m)
    if disk:
        m.disk_dir = disk
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    queue = [(i, k) for i, line in enumerate(lines) for k in keys_for(line)]
    out, steps, hold, free, snaps, cur = [], 0, 0, 0, {}, -1
    def snap():
        return {'vr': list(m.vregs), 'pal': dict(m.palette), 'bml': bytes(m.vram[0x2800:0x4000]),
                'curpic': m.rw(sy['CURPIC']), 'txttop': m.rw(sy['TXTTOP'])}
    while steps < max_steps:
        pc = cpu.pc
        if pc == sy['CHOUT']:
            out.append(chr(m.rw(0x8300) & 0xFF))
        if pc == sy['VMHALT']:
            return ''.join(out), m, snaps
        if pc == sy['WKY1'] and not hold and steps >= free:
            if 'title' not in snaps:
                snaps['title'] = snap(); R.render(m, os.path.join(ROOT, 'build/shots/pic-title.png'))
            m.held = keys_for(' ')[0]; hold = steps + 12_000
        if pc == sy['WK21'] and not hold and steps >= free:
            # line cur has run once the next key belongs to a later line
            if cur in snap_after and cur not in snaps and (not queue or queue[0][0] != cur):
                snaps[cur] = snap()
            if not queue:
                return ''.join(out), m, snaps
            cur, m.held = queue.pop(0); hold = steps + 12_000
        if hold and steps >= hold:
            m.held = None; hold = 0; free = steps + 12_000
        cpu.step(); steps += 1
    return ''.join(out), m, snaps

def shows(s, k):
    fmt, pal, raw = pics[k - 1]
    on = s['vr'][31] & 0x80 and (bool(s['vr'][31] & 0x10) == (fmt == 4))
    place = s['vr'][32] == 0xA0 and s['vr'][34] == 8 and s['vr'][36] == 96
    palok = all(s['pal'].get(32 + i) == v for i, v in enumerate(pal))
    return bool(on and place and palok and s['bml'] == raw and s['curpic'] == k and s['txttop'] == 13), \
        (hex(s['vr'][31]), s['vr'][32:37], palok, s['bml'] == raw, s['curpic'], s['txttop'])

walk = open(os.path.join(ROOT, 'samples/lamplight.walk')).read().split('\n')[:-1]
want = txvm.VM(img, walk).run()
i_lit, i_lamp = walk.index('turn on lantern'), walk.index('x lens') - 1
got, m, snaps = run(walk[:-1], snap_after={0, i_lit, i_lamp})
want_part = want[:want.rindex('\n>light lens with matches\n') + 2]
check('the walkthrough plays identically with pictures on', got.startswith(want_part[:len(got)]) and len(got) >= len(want_part) - 2,
      next((f'at {k}: {want_part[max(0,k-60):k+40]!r} / {got[max(0,k-60):k+40]!r}' for k in range(min(len(got), len(want_part))) if got[k] != want_part[k]), 'length'))
ok, d = shows(snaps['title'], 1)
check('the title page shows the title picture (fat pixels, 16 colours) with text below', ok, d)
s0 = snaps[0]
check('after the title page the layer is off and the text window starts at row 1', not s0['vr'][31] & 0x80 and s0['txttop'] == 1 and s0['curpic'] == 0,
      (hex(s0['vr'][31]), s0['txttop'], s0['curpic']))
ok, d = shows(snaps[i_lit], 2)
check('lighting the lantern in the cave shows the cave picture', ok, d)
ok, d = shows(snaps[i_lamp], 3)
check('the lamp room shows its picture in the 4-colour format', ok, d)
end = {'vr': list(m.vregs), 'pal': dict(m.palette), 'bml': bytes(m.vram[0x2800:0x4000]),
       'curpic': m.rw(sy['CURPIC']), 'txttop': m.rw(sy['TXTTOP'])}
ok, d = shows(end, 4)
check('the end screen shows the ending picture (end_picture)', ok, d)
R.render(m, os.path.join(ROOT, 'build/shots/pic-end.png'))

# SAVE and RESTORE (the disk calls overwrite the layer's VRAM) and UNDO
cave = ['n', 'take lantern', 's', 's', 'w', 'turn on lantern', 'save', '', 'restore', '', 'e', 'undo', 'q', 'y']
got2, m2, snaps2 = run(cave, snap_after={7, 9, 10, 11}, disk=tempfile.mkdtemp())
ok, d = shows(snaps2[7], 2)
check('after SAVE the cave picture is drawn again', ok, d)
ok, d = shows(snaps2[9], 2)
check('after RESTORE the cave picture shows', ok, d)
check('leaving the cave hides it', not snaps2[10]['vr'][31] & 0x80 and snaps2[10]['txttop'] == 1)
ok, d = shows(snaps2[11], 2)
check('UNDO brings it back', ok, d)
R.render(m2, os.path.join(ROOT, 'build/shots/pic-cave-undo.png'))
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
