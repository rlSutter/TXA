#!/usr/bin/env python3
"""sample_test.py - "Lamplight", the sample game, played to its end.

The walkthrough (samples/lamplight.walk) on the Python VM must give the
reviewed transcript (samples/lamplight.expected) and win with full
marks; then (unless --quick) the TI engine plays the same walkthrough,
typed key by key, and must give the same transcript.

  python3 tests/sample_test.py [--quick] [--update] [--png]"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from txc.codegen import compile_file
from txc import txvm
S = os.path.join(ROOT, 'samples'); LIB = [os.path.join(ROOT, 'lib')]
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:2000]))
    fails += 0 if ok else 1

img, info = compile_file(os.path.join(S, 'lamplight.txa'), LIB, title='LAMPLIGHT')
walk = open(os.path.join(S, 'lamplight.walk')).read().split('\n')[:-1]
vm = txvm.VM(img, walk); out = vm.run()
if '--update' in sys.argv:
    open(os.path.join(S, 'lamplight.expected'), 'w').write(out)
want = open(os.path.join(S, 'lamplight.expected')).read()
check(f'walkthrough = the reviewed transcript ({len(walk)} commands)', out == want,
      next((f'line {i}: {a!r} / {b!r}' for i, (a, b) in enumerate(zip(out.splitlines(), want.splitlines())) if a != b), 'length differs'))
check('the game is won with full marks', '*** You have won ***' in out and 'you scored 25 out of a possible 25' in out)
check('the tide floods and uncovers the causeway', "The causeway is under water. You'll have to wait for the tide." in out
      and 'The tide draws back' in out)
check('light arriving in the dark cave describes it', 'You switch the storm lantern on.\n\nSea Cave' in out)
check('no compiler warnings', info['program'].warnings == [], info['program'].warnings)
print(f'      story image {len(img)} bytes')

if '--quick' not in sys.argv:
    src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
    g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'sample'}
    exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
    t0 = time.time()
    got, m, why, per = g['play'](img, walk)
    ok = got == want and why == 'halt'
    i = next((k for k in range(min(len(got), len(want))) if got[k] != want[k]), min(len(got), len(want)))
    check(f'the engine plays it identically ({time.time() - t0:.0f}s)', ok,
          f'stopped by {why}; first difference at {i}:\n  python: {want[max(0, i-80):i+60]!r}\n  engine: {got[max(0, i-80):i+60]!r}')
    if per:
        secs = sorted(n * 9e-6 for n in per)
        print(f'      engine time per command (estimate): median {secs[len(secs)//2]:.1f}s, worst {secs[-1]:.1f}s')
    if '--png' in sys.argv:
        g['R'].render(m, os.path.join(ROOT, 'build/shots/lamplight-end.png'))
    # the command history with a long status line ("Score: 5  Moves: 7"):
    # the status buffer once overlapped the history's counters
    typed = ['n', 'u', 'take spectacles', 'd', 'give spectacles to brannock', 'i', '\x0b', 'q', 'y']
    meant = ['n', 'u', 'take spectacles', 'd', 'give spectacles to brannock', 'i', 'i', 'q', 'y']
    want2 = txvm.VM(img, meant).run()
    got2, m2, why2, _ = g['play'](img, typed)
    check('history after the score appears on the status line', got2 == want2 and why2 == 'halt',
          f'{why2}: {got2[-200:]!r}')

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
