#!/usr/bin/env python3
"""tutorial_test.py - every chapter of the Tutorial (samples/tutorial/
ferry1-5.txa) compiles without warnings and plays as the Tutorial says,
on the Python VM.

  python3 tests/tutorial_test.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); os.chdir(ROOT)
from txc.codegen import compile_file
from txc.txvm import run_image
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[-700:]))
    fails += 0 if ok else 1
PLAYS = {
    1: (['look'], ['Landing Stage', 'slow brown river']),
    2: (['x bench', 'take coin', 'n', 's'], ['polished by years', 'Taken.', 'Porch', 'sagging porch']),
    3: (['take coin', 'n', 'e', 'lift mat', 'take key', 'unlock door with key', 'open door', 'e', 'open box', 'take ticket'],
        ['seems to be locked', 'Underneath lies an iron key', 'You unlock the front door', 'Parlour', 'revealing a ferry ticket']),
    4: (['ask ferryman about river', 'give coin to ferryman'],
        ['One penny across', '(first taking the copper coin)', 'poles you across', 'Far Bank']),
    5: (['take coin', 'wait', 'wait', 'wait', 'give coin to ferryman'],
        ['a bell rings for the ferry', 'You have won', 'you scored 5 out of a possible 5']),
}
for n, (cmds, wants) in PLAYS.items():
    path = f'samples/tutorial/ferry{n}.txa'
    img, info = compile_file(path, ['lib'], title='FERRY')
    check(f'chapter {n}: compiles, no warnings ({len(img)} bytes)', info['program'].warnings == [], info['program'].warnings)
    out = run_image(img, cmds)
    missing = [w for w in wants if w not in out]
    check(f'chapter {n}: plays {cmds} as the Tutorial says', not missing, (missing, out))
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
