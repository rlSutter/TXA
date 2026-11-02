#!/usr/bin/env python3
"""engprof.py - where the TI engine spends its instructions playing
Lamplight's walkthrough (samples/lamplight.walk): counts by routine (the
nearest label below the PC, from build/engine.equ), and the instructions
per command.  Made for the optimization pass (2 November 2026).

  python3 tools/engprof.py"""
import os, sys, bisect, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); os.chdir(ROOT)
from txc.codegen import compile_file
import build
src = open('tests/m2_engine_test.py').read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'prof'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
S = g['S']
counts = collections.Counter()
step0 = S.CPU.step
def step(self):
    counts[self.pc] += 1
    return step0(self)
S.CPU.step = step
img, info = compile_file('samples/lamplight.txa', ['lib'], title='LAMPLIGHT')
walk = [l for l in open('samples/lamplight.walk').read().splitlines() if l and not l.startswith('#')]
got, m, why, per = g['play'](img, walk)
sy = build.symbols(os.path.join(build.B, 'engine.equ'))
labs = sorted((a, n) for n, a in sy.items() if 0x2000 <= a < 0xE000 and not n.startswith('H.'))
addrs = [a for a, _ in labs]
byr = collections.Counter()
for pc, c in counts.items():
    i = bisect.bisect_right(addrs, pc) - 1
    byr[labs[i][1] if i >= 0 else '?'] += c
total = sum(counts.values())
print(f'{total / 1e6:.1f}M instructions, {len(walk)} commands; median per command {sorted(per)[len(per)//2] / 1e6:.2f}M, worst {max(per) / 1e6:.2f}M ({why})')
for n, c in byr.most_common(40):
    print(f'  {c / 1e6:6.2f}M {100 * c / total:5.1f}%  {n}')
