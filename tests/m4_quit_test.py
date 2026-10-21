#!/usr/bin/env python3
"""m4_quit_test.py - QUIT hands the console back clean.

The engine is played to its end (QUIT, yes), a key pressed at "[End of
story]", and the state at the console reset (BLWP @>0000) checked: the
scratchpad from >8320 cleared (the fast block once left the console's
user interrupt hook at >83C4 set, and js99er hung on the game's screen),
the F18A's extended registers back to their defaults, SAMS mapping off.

  python3 tests/m4_quit_test.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'm4q'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
S, build, keys_for = g['S'], g['build'], g['keys_for']
import txpics
from txc.codegen import compile_file
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:1500]))
    fails += 0 if ok else 1

srcf = os.path.join(ROOT, 'samples/lamplight.txa')
img, info = compile_file(srcf, [os.path.join(ROOT, 'lib')], title='LAMPLIGHT')
area = txpics.picture_area(info, [os.path.join(ROOT, 'samples/pics')])
cart, _ = build.engine_cart(img, 'LAMPLIGHT', pictures=area)
sy = build.symbols(os.path.join(build.B, 'engine.equ'))
m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m)
cpu.pc = m.rw(m.rw(0x6006) + 2)
queue = [k for line in ['n', 'take lantern', 's', 's', 'w', 'turn on lantern', 'quit', 'yes'] for k in keys_for(line)]
steps = hold = free = 0
while steps < 200_000_000 and not getattr(m, 'console_resets', 0):
    pc = cpu.pc
    if pc in (sy['WKY1'], sy['WK21']) and not hold and steps >= free:
        m.held = queue.pop(0) if (queue and pc == sy['WK21']) else keys_for(' ')[0]
        hold = steps + 12_000
    if hold and steps >= hold:
        m.held = None; hold = 0; free = steps + 12_000
    cpu.step(); steps += 1
check('QUIT reaches the console reset (with a picture showing)', getattr(m, 'console_resets', 0) == 1)
scr = getattr(m, 'scratch_at_reset', b'\xff' * 256)
check('the scratchpad from >8320 is clear at the reset (user hook >83C4, sound count >83CE)', scr[0x20:] == bytes(0xE0),
      ' '.join(f'>{0x8300 + i:04X}={scr[i]:02X}' for i in range(0x20, 0x100) if scr[i])[:600])
vr, pal, ams = m.at_reset
check('the F18A back to defaults: VR49 (rows) 0, VR50 (attributes) 0, VR31 (bitmap layer) 0, VR47 0, VR15 0, VR0 0',
      (vr[49], vr[50], vr[31], vr[47], vr[15], vr[0]) == (0, 0, 0, 0, 0, 0), (vr[49], vr[50], vr[31], vr[47], vr[15], vr[0]))
check('SAMS mapping off', not ams)
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
