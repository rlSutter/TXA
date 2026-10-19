#!/usr/bin/env python3
"""bench_engine.py - how long the engine takes to answer commands.

Plays the parser test script (tests/txa/m2/m2game.cmds) on the engine
in the simulator, counting the CPU instructions spent on each command:
from the release of ENTER until the engine waits for the next key
(typing and waiting are not counted).  Instructions executed from the
16-bit scratchpad RAM (>8000->83FF) are counted apart from the rest,
which run from the 32K expansion with its wait states.

The time is an estimate: about 9 us an instruction from the expansion
and 5 us from the scratchpad on a 3 MHz TMS9900.  The instruction
counts are exact; the console gives the real seconds.

  python3 tests/bench_engine.py [label]     appends to build/bench.txt"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, os.path.join(ROOT, 'tests'))
import sim9900 as S, build
from txc.codegen import compile_file
from txc.txvm import run_image
D = os.path.join(ROOT, 'tests/txa/m2')
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'bench'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
keys_for = g['keys_for']

def bench(label):
    img, _ = compile_file(os.path.join(D, 'm2game.txa'), [os.path.join(ROOT, 'lib')])
    cmds = open(os.path.join(D, 'm2game.cmds')).read().split('\n')[:-1]
    want = run_image(img, cmds)
    cart, _ = build.engine_cart(img, 'TXA BENCH')
    sy = build.symbols(os.path.join(ROOT, 'build/engine.equ'))
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m)
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    queue = [k for line in cmds for k in keys_for(line)]
    enter = {S.key_pos('\r')}
    out, steps, hold_until, free_until, more = [], 0, 0, 0, 0
    counting, slow, fast, per = False, 0, 0, []
    wk21, wky1, chout, halt = sy['WK21'], sy['WKY1'], sy['CHOUT'], sy['VMHALT']
    while steps < 400_000_000:
        pc = cpu.pc
        if pc == chout:
            out.append(chr(m.rw(0x8300) & 0xFF))
        if pc == halt:
            break
        if pc == wky1 and not more and not hold_until and steps >= free_until:
            more = 1
        if pc == wk21 and not hold_until and steps >= free_until:
            if counting:
                per.append((slow, fast)); counting = False
            if not queue:
                break
            k = queue.pop(0); m.held = k; hold_until = steps + 12_000
            if k == enter:
                counting = 'armed'
        if hold_until and steps >= hold_until:
            m.held = None; hold_until = 0; free_until = steps + 12_000
            if counting == 'armed':
                counting, slow, fast = True, 0, 0
        elif more and not hold_until and steps >= free_until and pc != wk21:
            m.held = {S.key_pos(' ')}; hold_until = steps + 12_000; more -= 1
        if counting is True and not (wky1 - 40 <= pc <= wky1 + 40):
            if pc < 0x8400 and pc >= 0x8000:
                fast += 1
            else:
                slow += 1
        cpu.step(); steps += 1
    if counting is True:
        per.append((slow, fast))
    same = ''.join(out) == want
    secs = sorted(s * 9e-6 + f * 5e-6 for s, f in per)
    tot_s, tot_f = sum(s for s, _ in per), sum(f for _, f in per)
    line = (f'{label:24s} transcript {"same" if same else "DIFFERENT"}  instructions {tot_s + tot_f:9d} '
            f'(scratchpad {tot_f:8d})  per command: median {secs[len(secs)//2]:.2f}s  '
            f'90% {secs[int(len(secs)*0.9)]:.2f}s  worst {secs[-1]:.2f}s')
    print(line)
    with open(os.path.join(ROOT, 'build/bench.txt'), 'a') as f:
        f.write(line + '\n')
    return same

if __name__ == '__main__':
    sys.exit(0 if bench(sys.argv[1] if len(sys.argv) > 1 else 'run') else 1)
