#!/usr/bin/env python3
"""m3_engine_test.py - the M3 test worlds on the TI engine.

Each world in tests/txa/m3 is typed into the engine key by key (as in
m2_engine_test.py); the engine's transcript must equal the Python VM's,
and the status line (row 0) must show what the Python VM's STATUS got.

  python3 tests/m3_engine_test.py [world ...] [--png]"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'm3'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
play, R, compile_file = g['play'], g['R'], g['compile_file']
from txc import txvm
D = os.path.join(ROOT, 'tests/txa/m3'); LIB = [os.path.join(ROOT, 'lib')]
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:2500]))
    fails += 0 if ok else 1

worlds = [a for a in sys.argv[1:] if not a.startswith('--')] or sorted(f[:-4] for f in os.listdir(D) if f.endswith('.txa'))
for w in worlds:
    img, _ = compile_file(os.path.join(D, w + '.txa'), LIB)
    cmds = open(os.path.join(D, w + '.cmds')).read().split('\n')[:-1]
    vm = txvm.VM(img, cmds); want = vm.run()
    t0 = time.time()
    import tempfile
    got, m, why, per = play(img, cmds[:-1] if cmds[-1] == 'q' else cmds, disk=tempfile.mkdtemp())   # a disk for SAVE
    if cmds[-1] == 'q':
        want = want[:want.rindex('>q\n') + 1]      # stop at the last prompt (the engine is left waiting)
    ok = got == want
    i = next((k for k in range(min(len(got), len(want))) if got[k] != want[k]), min(len(got), len(want)))
    check(f'{w}: engine transcript = Python transcript ({len(want)} chars, {time.time() - t0:.0f}s)', ok,
          f'stopped by {why}; first difference at {i}:\n  python: {want[max(0, i-80):i+60]!r}\n  engine: {got[max(0, i-80):i+60]!r}')
    row = R.screen(m).splitlines()[0]
    name, sc, mv = vm.status
    right = (f'Score: {sc}  Moves: {mv}' if sc != -1 else f'Moves: {mv}')
    check(f'{w}: status line "{name} ... {right}"', row.startswith(' ' + name) and row.rstrip().endswith(right), repr(row))
    if '--png' in sys.argv:
        R.render(m, os.path.join(ROOT, f'build/shots/m3-{w}.png'))

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
