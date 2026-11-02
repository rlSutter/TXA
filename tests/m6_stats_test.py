#!/usr/bin/env python3
"""m6_stats_test.py - the statistics (S, M6 part 10): after Lamplight is
compiled on the simulated TI, S shows the lines tools/txc/stats.py makes
from the Python compiler's image and counts, word for word (objects,
dictionary words, routines and strings; the image and each section with
its limit and what is free).  Before any compile, S says there is nothing
to show.

  python3 tests/m6_stats_test.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); os.chdir(ROOT)
src = open(os.path.join(ROOT, 'tests/m5_sema_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m5_sema_test.py'), '__name__': 'st'}
sys.argv = ['st', 'none']
exec(compile(src[:src.index('args = sys.argv[1:]')], 'm5', 'exec'), g)
S, sy, R, keys_for, DATE = g['S'], g['sy'], g['R'], g['keys_for'], g['DATE']
from txc.codegen import compile_file
from txc import stats
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:900]))
    fails += 0 if ok else 1

def session(d, keys, max_steps=400_000_000):
    m = S.Machine(g['cart'], f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    queue = list(keys); steps = hold = free = 0; dated = False
    while steps < max_steps:
        if cpu.pc == sy['WK1'] and not dated:
            for i, c in enumerate(DATE.strftime('%y%m%d').encode()):
                m.wb(sy['WDATE'] + i, c)
            dated = True
        if cpu.pc == sy['WK1'] and not hold and steps >= free:
            if not queue:
                break
            m.held = queue.pop(0); hold = steps + 12_000
        if hold and steps >= hold:
            m.held = None; hold = 0; free = steps + 12_000
        cpu.step(); steps += 1
    return m

k = lambda s: keys_for(s)[:-1]
d, pp = g['stage'](open('samples/lamplight.txa').read(), 'lamplight', g['LIB'])
m0 = session(d, k('s'))
scr0 = R.screen(m0).splitlines()
check('S before any compile: "No statistics yet ..."', scr0[4].strip().startswith('No statistics yet: compile first (C)'), scr0[3:6])
m = session(d, k('p') + keys_for('dsk1.lamplight') + keys_for('') + keys_for('') + k('c') + k('s'))
scr = R.screen(m).splitlines()
img, info = compile_file('samples/lamplight.txa', ['lib'], title='LAMPLIGHT', date=DATE)
want = stats.lines(img, info)
check('row 3: "Statistics of the last compile:"', scr[3].strip() == 'Statistics of the last compile:', scr[2:4])
for i, line in enumerate(want):
    check(f'row {4 + i} as stats.py says: "{line}"', scr[4 + i].strip() == line, scr[4 + i])
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
