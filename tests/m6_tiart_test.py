#!/usr/bin/env python3
"""m6_tiart_test.py - the workbench's TI Artist converter (M6 part 9,
overlay 12, src/wtiart.a99) against the reference, tools/tiartist.py:
Rebecca's hummingbird (tests/data/BIRD_P, BIRD_C) staged interleaved in
SAMS, converted on the simulated TI by crop 0, crop 48, crop 96 and
squeeze: each record equals tiartist.record byte for byte.

  python3 tests/m6_tiart_test.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); os.chdir(ROOT)
import tiartist
src = open(os.path.join(ROOT, 'tests/m5_sema_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m5_sema_test.py'), '__name__': 'ta'}
sys.argv = ['ta', 'none']
exec(compile(src[:src.index('args = sys.argv[1:]')], 'm5', 'exec'), g)
S, sy, build = g['S'], g['sy'], g['build']
wsy = build.symbols(os.path.join(build.B, 'wovl.equ'))
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:600]))
    fails += 0 if ok else 1
pat, col = tiartist.read_file('tests/data/BIRD_P'), tiartist.read_file('tests/data/BIRD_C')
TIPG, OUTPG = 21, 26
for how in (('crop', 0), ('crop', 48), ('crop', 96), ('squeeze', 0)):
    m = S.Machine(g['cart'], f18a=True, pages=128); cpu = S.CPU(m)
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    steps = 0
    while cpu.pc != sy['WK1'] and steps < 5_000_000:      # to the menu
        cpu.step(); steps += 1
    for i in range(6144):                                  # the picture, interleaved
        m.ams[TIPG * 4096 + 2 * i] = pat[i]; m.ams[TIPG * 4096 + 2 * i + 1] = col[i]
    m.ww(wsy['TIMODE'], 1 if how[0] == 'squeeze' else 0); m.ww(wsy['TIROW'], how[1])
    cpu.regs_set = None
    m.ww(cpu.wp + 0, 12)                                   # R0 = 12: OVGO -> overlay 12, TITEST
    cpu.pc = sy['OVGO']
    steps = 0
    while steps < 20_000_000:
        cpu.step(); steps += 1
        if cpu.pc == sy['WK1']:
            break
    n = m.rw(wsy['TILEN'])
    got = bytes(m.ams[OUTPG * 4096: OUTPG * 4096 + n])
    want = tiartist.record(pat, col, how)
    i = next((k for k in range(min(len(got), len(want))) if got[k] != want[k]), min(len(got), len(want)))
    check(f'{how[0]} {how[1] if how[0] == "crop" else ""}: the TI\'s record equals the reference, {len(want)} bytes '
          f'({steps / 1e6:.1f}M instructions)', got == want, f'at {i} of {len(want)} (ti {len(got)}): ti {got[i:i+12].hex()} ref {want[i:i+12].hex()}')
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
