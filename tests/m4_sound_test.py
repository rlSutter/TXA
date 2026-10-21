#!/usr/bin/env python3
"""m4_sound_test.py - music and sound effects: the notation, the sound
area, and the TI player against the reference player, byte for byte.

Lamplight (with its tunes and effects) is built for the TI and its
walkthrough played on the engine in the simulator.  Every frame tick
(SNDTKE), every MUSIC and SOUND (SMUSE, SSNDE) and every byte written to
the sound chip is logged; the same ticks and calls, in the same order,
are fed to tools/txsound.py's Player, and the chip bytes must be equal.
The transcript must still equal the Python VM's (sound prints nothing).

  python3 tests/m4_sound_test.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build, txpics, txsound, sim9900 as S
from txc.codegen import compile_file
from txc import txvm
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'm4s'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
keys_for = g['keys_for']
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:1800]))
    fails += 0 if ok else 1

# the notation
lp, vs = txsound.compile_text('TEMPO 120\nA: o4 l4 c d e8 f8 g2\n', 't')
check('the notation: c d e8 f8 g2 at 120 is 30+30+15+15+60 frames', [e[-1] for e in vs[0][1] if e[0] == 'tone'] == [30, 30, 15, 15, 60])
try:
    txsound.compile_text('LOOP\nA: c4 d4\nC: c4\n', 'bad'); ok = False
except txsound.MMLError as e:
    ok = 'same length' in str(e)
check('a looping tune with voices of different lengths is refused', ok)

srcf = os.path.join(ROOT, 'samples/lamplight.txa')
img, info = compile_file(srcf, [os.path.join(ROOT, 'lib')], title='LAMPLIGHT')
pics = txpics.picture_area(info, [os.path.join(ROOT, 'samples/pics')])
area = txsound.sound_area(info, [os.path.join(ROOT, 'samples/sounds')])
check('the sound area: 3 tunes, 3 effects', area[:4] == bytes([0, 3, 0, 3]), area[:4].hex())
cart, _ = build.engine_cart(img, 'LAMPLIGHT', pictures=pics, sounds=area)
sy = build.symbols(os.path.join(build.B, 'engine.equ'))

walk = open(os.path.join(ROOT, 'samples/lamplight.walk')).read().split('\n')[:-1]
m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m)
cpu.pc = m.rw(m.rw(0x6006) + 2)
queue = [k for line in walk for k in keys_for(line)]
events, out, steps, hold, free = [], [], 0, 0, 0
nchip = 0
while steps < 600_000_000:
    pc = cpu.pc
    if pc == sy['SNDTKE']: events.append(('tick',))
    elif pc == sy['SMUSE']: events.append(('music', m.rw(sy['SNDARG'])))
    elif pc == sy['SSNDE']: events.append(('sound', m.rw(sy['SNDARG'])))
    elif pc == sy['SOFFE']: events.append(('off',))
    if pc == sy['CHOUT']:
        out.append(chr(m.rw(0x8300) & 0xFF))
    if pc == sy['VMHALT']:
        break
    if pc in (sy['WKY1'], sy['WK21']) and not hold and steps >= free:
        m.held = queue.pop(0) if (queue and pc == sy['WK21']) else keys_for(' ')[0]
        hold = steps + 12_000
    if hold and steps >= hold:
        m.held = None; hold = 0; free = steps + 12_000
    cpu.step(); steps += 1
got = [v for (who, _, v) in m.chip_log if who == 'cpu']

want_text = txvm.VM(img, walk).run()
check('the walkthrough plays identically with sound on', ''.join(out) == want_text[:len(''.join(out))] and len(out) > len(want_text) - 40)

pl = txsound.Player(area); exp = []
for e in events:
    if e[0] == 'tick': exp += pl.tick()
    elif e[0] == 'music': exp += pl.play_music(e[1])
    elif e[0] == 'sound': exp += pl.play_sound(e[1])
    elif e[0] == 'off':
        pl.music, pl.fx, pl.cur = [], [], 0; exp += [0x9F, 0xBF, 0xDF, 0xFF]
ticks = sum(1 for e in events if e[0] == 'tick')
calls = [e for e in events if e[0] in ('music', 'sound')]
check(f'the player ran ({ticks} frames, {len(calls)} MUSIC/SOUND calls, {len(got)} chip bytes)', ticks > 600 and len(got) > 200, (ticks, len(got)))
k = next((i for i in range(min(len(got), len(exp))) if got[i] != exp[i]), min(len(got), len(exp)))
check('the TI player writes exactly what the reference player writes', got == exp,
      f'first difference at byte {k} of {len(got)}/{len(exp)}: ti {bytes(got[max(0,k-8):k+8]).hex(" ")} / ref {bytes(exp[max(0,k-8):k+8]).hex(" ")}')
check('MUSIC: the title tune, the harbour tune outdoors, the fanfare at the end',
      [n for (w, n) in calls if w == 'music'][:3] == [1, 0, 2] and ('music', 3) in calls)
check('SOUND: the tide (twice), the match on the dry wick, the horn at the end',
      [n for (w, n) in calls if w == 'sound'] == [3, 3, 2, 1], [n for (w, n) in calls if w == 'sound'])
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
