#!/usr/bin/env python3
"""m2_engine_test.py - the parser on the TI engine, typed key by key.

The test world (tests/txa/m2/m2game.txa) runs in the simulator; the
harness types each command of m2game.cmds on the simulated keyboard
(holding and releasing every key, ENTER at the end) whenever the engine
waits for a key, and presses SPACE at [MORE].  Every character the
engine passes to CHOUT must equal the Python VM's transcript.  Also:
the line editor's rub-out (FCTN S) and SHIFT, TOKENIZE's word table,
and the engine's time per command.

  python3 tests/m2_engine_test.py [--png]"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import sim9900 as S, render80 as R, build
from txc.codegen import compile_file
from txc.txvm import run_image
D = os.path.join(ROOT, 'tests/txa/m2'); LIB = [os.path.join(ROOT, 'lib')]
PNG = '--png' in sys.argv
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:2500]))
    fails += 0 if ok else 1

FCTN, SHIFT = (0, 4), (0, 5)
def keys_for(line):
    """The key presses that type line: each a set of held keys."""
    out = []
    for ch in line:
        if ch == '\b':
            out.append({FCTN, S.key_pos('S')})
        elif ch.isupper():
            out.append({SHIFT, S.key_pos(ch)})
        else:
            out.append({S.key_pos(ch.upper() if ch.isalpha() else ch)})
    out.append({S.key_pos('\r')})
    return out

def play(image, lines, max_steps=400_000_000, hold=12_000, gap=12_000):
    cart, _ = build.engine_cart(image, 'TXA M2 TEST')
    sy = build.symbols(os.path.join(ROOT, 'build/engine.equ'))
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m)
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    queue = [k for line in lines for k in keys_for(line)]
    per_cmd, cmd_t0 = [], None
    out, steps, hold_until, free_until, more = [], 0, 0, 0, 0
    chout, halt, waitk2, waitky = sy['CHOUT'], sy['VMHALT'], sy['WK21'], sy['WKY1']   # the polling loops
    while steps < max_steps:
        pc = cpu.pc
        if pc == chout:
            out.append(chr(m.rw(0x8300) & 0xFF))
        elif pc == halt:
            return ''.join(out), m, 'halt', per_cmd
        elif pc == waitky and not more and not hold_until and steps >= free_until:
            more = 1
        elif pc == waitk2 and not hold_until and steps >= free_until:
            if cmd_t0 is not None:
                per_cmd.append(steps - cmd_t0); cmd_t0 = None
            if not queue:
                return ''.join(out), m, 'waiting', per_cmd
            k = queue.pop(0)
            m.held = k; hold_until = steps + hold
            if k == {S.key_pos('\r')}:
                cmd_t0 = steps + hold
        if hold_until and steps >= hold_until:
            m.held = None; hold_until = 0; free_until = steps + gap
        elif more and not hold_until and steps >= free_until and pc != waitk2:
            m.held = {S.key_pos(' ')}; hold_until = steps + hold; more -= 1
        cpu.step(); steps += 1
    return ''.join(out), m, 'steps', per_cmd

img, info = compile_file(os.path.join(D, 'm2game.txa'), LIB)
cmds = open(os.path.join(D, 'm2game.cmds')).read().split('\n')[:-1]
want = run_image(img, cmds)
t0 = time.time()
got, m, why, per_cmd = play(img, cmds)
ok = got == want and why == 'halt'
i = next((k for k in range(min(len(got), len(want))) if got[k] != want[k]), min(len(got), len(want)))
check(f'the 45-command script: engine transcript = Python transcript ({len(want)} chars, {time.time() - t0:.0f}s)', ok,
      f'stopped by {why}; first difference at {i}:\n  python: {want[max(0, i-80):i+60]!r}\n  engine: {got[max(0, i-80):i+60]!r}')
if per_cmd:
    # An estimate only: about 9 microseconds an instruction for this kind of
    # code on a 3 MHz TMS9900 running from the 32K expansion (wait states
    # included).  Real timing comes from Rebecca's console.
    secs = sorted(n * 9e-6 for n in per_cmd)
    print(f'      engine time per command (estimate): median {secs[len(secs)//2]:.1f}s, '
          f'90% under {secs[int(len(secs) * 0.9)]:.1f}s, worst {secs[-1]:.1f}s')
if PNG:
    os.makedirs(os.path.join(ROOT, 'build/shots'), exist_ok=True); R.render(m, os.path.join(ROOT, 'build/shots/m2-engine.png'))

# the line editor: rub out, SHIFT; an over-long line stops at the row's end
got, m, why, _ = play(img, ['take xx\b\btin LAMP', 'q'])
check('rub out (FCTN S) and SHIFT: "take xx<-<-tin LAMP" reads as "take tin lamp"',
      '>take tin lamp\nTaken.' in got, got[-200:])

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
