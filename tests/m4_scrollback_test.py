#!/usr/bin/env python3
"""m4_scrollback_test.py - BACK at the prompt shows the earlier text.

Lamplight is played on the engine; at a prompt BACK (FCTN 9) opens the
scrollback and FCTN E goes back three lines: each text row must then show
the line that was three rows higher on the screen before, with the hint
in reverse on the bottom row.  ENTER returns: the screen (characters and
colours) must be exactly as it was.  The next command must run normally,
so the transcript equals the Python VM's.

  python3 tests/m4_scrollback_test.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'm4b'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
S, build, R, keys_for = g['S'], g['build'], g['R'], g['keys_for']
from txc.codegen import compile_file
from txc import txvm
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:2000]))
    fails += 0 if ok else 1

img, _ = compile_file(os.path.join(ROOT, 'samples/lamplight.txa'), [os.path.join(ROOT, 'lib')], title='LAMPLIGHT')
cart, _ = build.engine_cart(img, 'LAMPLIGHT')
sy = build.symbols(os.path.join(build.B, 'engine.equ'))
before = ['look', 'n', 'x keeper', 'ask brannock about lamp', 'ask him about key', 'ask him about tide', 'look']
lines = before + ['\x0e\x0b\x0b\x0b', 'i', 'quit', 'yes']
queue = [(li, ki, k) for li, line in enumerate(lines) for ki, k in enumerate(keys_for(line))]
m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m)
cpu.pc = m.rw(m.rw(0x6006) + 2)
def shot():
    return bytes(m.vram[0:80 * 30]), bytes(m.vram[0x0980:0x0980 + 80 * 30]), R.screen(m).splitlines()
out, steps, hold, free, snaps = [], 0, 0, 0, {}
iback = len(before)
while steps < 300_000_000:
    pc = cpu.pc
    if pc == sy['CHOUT']:
        out.append(chr(m.rw(0x8300) & 0xFF))
    if pc == sy['VMHALT']:
        break
    if pc in (sy['WKY1'], sy['WK21']) and not hold and steps >= free:
        if pc == sy['WK21'] and queue:
            li, ki, k = queue[0]
            if li == iback and ki == 0 and 'pre' not in snaps:
                snaps['pre'] = shot(); snaps['crow'] = m.rw(sy['CROW']); snaps['top'] = m.rw(sy['TXTTOP'])
            if li == iback and ki == 4 and 'view' not in snaps:      # the ENTER after three FCTN E
                snaps['view'] = shot()
            if li == iback + 1 and ki == 0 and 'post' not in snaps:
                snaps['post'] = shot()
            queue.pop(0); m.held = k
        else:
            m.held = keys_for(' ')[0]
        hold = steps + 12_000
    if hold and steps >= hold:
        m.held = None; hold = 0; free = steps + 12_000
    cpu.step(); steps += 1

pre, view, post = snaps.get('pre'), snaps.get('view'), snaps.get('post')
check('the run reached the scrollback and came back', pre and view and post)
rows = 30; crow, top = snaps['crow'], snaps['top']
ok, detail = True, []
for r in range(top, rows - 1):          # viewer row r shows the line from pre-row r - 3 - (crow - 1 - (rows - 2))
    src_row = r - 3 - ((rows - 2) - (crow - 1))
    if top <= src_row < crow:
        if view[2][r] != pre[2][src_row]:
            ok = False; detail.append((r, view[2][r][:40], src_row, pre[2][src_row][:40]))
check('three lines back, every row shows the line that was three rows higher', ok, detail[:4])
check('the hint is on the bottom row, in reverse', view[2][rows - 1].startswith('Earlier text: FCTN E back')
      and view[1][(rows - 1) * 80] == 0x1E, view[2][rows - 1])
check('ENTER returns to exactly the screen as it was (characters and colours)', post[0] == pre[0] and post[1] == pre[1],
      next((f'row {i // 80}: {pre[2][i // 80]!r} / {post[2][i // 80]!r}' for i in range(len(pre[0])) if pre[0][i] != post[0][i]), 'colours differ'))
want = txvm.VM(img, before + ['i', 'quit', 'yes']).run()
got = ''.join(out)
check('the next command runs normally: the transcript equals the Python VM\'s', got == want,
      next((f'at {i}: {want[max(0,i-50):i+40]!r} / {got[max(0,i-50):i+40]!r}' for i in range(min(len(got), len(want))) if got[i] != want[i]), 'length'))
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
