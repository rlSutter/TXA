#!/usr/bin/env python3
"""m6_record_test.py - RECORD and REPLAY (M6 part 8): command scripts on disk.

  - in the built game (B, R): RECORD, two commands, RECORD again (stops),
    REPLAY (the two commands again, as if typed), then a command from the
    keyboard, then REPLAY 1 (no such script): the transcript is the Python
    VM's with the same script;
  - DSK1 holds LAMPLIR0, a DIS/VAR 80 file with exactly the two commands.

  python3 tests/m6_record_test.py"""
import os, sys, tempfile, shutil, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
os.chdir(ROOT)
import build, txa_game, sim9900 as S
from txc.codegen import compile_file
from txc.txvm import run_image
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:2000]))
    fails += 0 if ok else 1

# the workbench harness (m5_sema_test's), for the TI's own compile
src = open(os.path.join(ROOT, 'tests/m5_sema_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m5_sema_test.py'), '__name__': 'm6'}
sys.argv = ['m6', 'none']
exec(compile(src[:src.index('args = sys.argv[1:]')], 'm5', 'exec'), g)
keys_for = g['keys_for']

# the engine, as a game writer wrote it, run by the simulator's cartridge loader
def play(out, engine, dsk_files, cmds, max_steps=150_000_000):
    for n in engine:
        shutil.copy(os.path.join(out, n), os.path.join(build.B, n))
    cart, _ = build.cart_from_segments(build.ea5_segments(engine[0]), 'M6 TEST')
    sy = build.symbols(os.path.join(build.B, 'engine.equ'))
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, 'DSK1'))
    for n in dsk_files:
        shutil.copy(n if os.path.isabs(n) else os.path.join(out, n), os.path.join(d, 'DSK1', os.path.basename(n)))
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    queue = [k for line in cmds for k in keys_for(line)]
    outp, steps, hold, free = [], 0, 0, 0
    while steps < max_steps:
        pc = cpu.pc
        if pc == sy['CHOUT']:
            outp.append(chr(m.rw(0x8300) & 0xFF))
        if pc in (sy['VMHALT'], sy['LDK9']):
            return ''.join(outp), m, 'halt' if pc == sy['VMHALT'] else 'nofile'
        if pc == sy['WKY1'] and not hold and steps >= free:
            m.held = keys_for(' ')[0]; hold = steps + 12_000
        if pc == sy['WK21'] and not hold and steps >= free:
            if not queue:
                return ''.join(outp), m, 'waiting'
            m.held = queue.pop(0); hold = steps + 12_000
        if hold and steps >= hold:
            m.held = None; hold = 0; free = steps + 12_000
        cpu.step(); steps += 1
    return ''.join(outp), m, 'steps'

img, _ = compile_file('samples/lamplight.txa', ['lib'], title='LAMPLIGHT')
walk = open('samples/lamplight.walk').read().split('\n')[:-1][:12]
want_all = run_image(img, walk)
def same_as_python(got, why):
    want = want_all[:want_all.rindex('\n>') + 2] if why == 'waiting' else want_all
    return got == want, want


def run_keys(d, items, max_steps=400_000_000):
    """The workbench from power-up: a string is typed with ENTER after it,
    ('key', c) is the one key c.  The date is set to DATE first."""
    cart = g['cart']; sy = g['sy']
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    queue = [k for it in items for k in (keys_for(it[1])[:-1] if isinstance(it, tuple) else keys_for(it))]
    steps = hold = free = 0; dated = False
    while steps < max_steps:
        pc = cpu.pc
        if pc == sy['WK1'] and not dated:
            for i, c in enumerate(g['DATE'].strftime('%y%m%d').encode()):
                m.wb(sy['WDATE'] + i, c)
            dated = True
        if pc == sy['WK1'] and not hold and steps >= free:
            if not queue:
                break
            m.held = queue.pop(0); hold = steps + 12_000
        if hold and steps >= hold:
            m.held = None; hold = 0; free = steps + 12_000
        cpu.step(); steps += 1
    return m, steps



def run_then_play(d, items, walk, max_steps=120_000_000, to_reset=False):
    """The workbench from power-up: the menu's keys; once R's relocator has
    run and the engine has started at >2000, the engine's output is kept
    and the walkthrough's lines are typed at its prompt.  Returns the
    engine's output, the machine, and why it stopped ('menu': the
    workbench waits with no keys left; 'waiting': the engine does)."""
    wsy = g['sy']; esy = build.symbols(os.path.join(build.B, 'engine.equ'))
    m = S.Machine(g['cart'], f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    queue = [k for it in items for k in (keys_for(it[1])[:-1] if isinstance(it, tuple) else keys_for(it))]
    equeue = [k for line in walk for k in keys_for(line)]
    steps = hold = free = 0; dated = reloc = engine = False; out = []
    while steps < max_steps:
        pc = cpu.pc
        if m.__dict__.get('console_resets'):           # the engine's QUIT restarted the console
            return ''.join(out), m, 'reset'
        if not engine:
            if pc == wsy['WK1'] and not dated:
                for i, c in enumerate(g['DATE'].strftime('%y%m%d').encode()):
                    m.wb(wsy['WDATE'] + i, c)
                dated = True
            if pc == wsy['RELOC']:                  # (>F000: nothing else runs there)
                reloc = True
            if reloc and pc == 0x2000:              # (the workbench's kernel starts at >2000 too)
                engine = True
            elif pc == wsy['WK1'] and not hold and steps >= free:
                if not queue:
                    return ''.join(out), m, 'menu'
                m.held = queue.pop(0); hold = steps + 12_000
        else:
            if pc == esy['CHOUT']:
                out.append(chr(m.rw(0x8300) & 0xFF))
            if pc == esy['LDK9'] or (pc == esy['VMHALT'] and not to_reset):
                return ''.join(out), m, 'halt' if pc == esy['VMHALT'] else 'nofile'
            if pc == esy['WKY1'] and not hold and steps >= free:
                m.held = keys_for(' ')[0]; hold = steps + 12_000
            if pc == esy['WK21'] and not hold and steps >= free:
                if not equeue:
                    return ''.join(out), m, 'waiting'
                m.held = equeue.pop(0); hold = steps + 12_000
        if hold and steps >= hold:
            m.held = None; hold = 0; free = steps + 12_000
        cpu.step(); steps += 1
    return ''.join(out), m, 'steps'

P, B, Rk = ('key', 'p'), ('key', 'b'), ('key', 'r')
d, ppath = g['stage'](open('samples/lamplight.txa').read(), 'lamplight', g['LIB'])
outC = tempfile.mkdtemp()
fc = txa_game.write_game('samples/lamplight.txa', 'LAMPLI', 'LAMPLIGHT', out=outC, quiet=True)
for n in fc['picture_files'] + fc['sound_files']:
    shutil.copy(os.path.join(outC, n), os.path.join(d, 'DSK1', n))
esy = build.symbols(os.path.join(build.B, 'engine.equ'))
img, _ = compile_file('samples/lamplight.txa', ['lib'], title='LAMPLIGHT', date=g['DATE'])
cmds = ['record', 'look', 'n', 'record', 'replay', 'inventory', 'replay 1']
files = {}
want_all = run_image(img, cmds, files=files)
got, m, why = run_then_play(d, [P, 'dsk1.lamplight', '', '', B, Rk], cmds)
want = want_all[:want_all.rindex('\n>') + 2] if why == 'waiting' else want_all
i = next((k for k in range(min(len(got), len(want))) if got[k] != want[k]), min(len(got), len(want)))
check(f'RECORD, two commands, RECORD, REPLAY, a keyboard command, REPLAY 1: the transcript as the Python VM plays it ({len(got)} characters)',
      got == want and why == 'waiting', f'{why} at {i}: python {want[max(0, i - 80):i + 60]!r}\n  ti {got[max(0, i - 80):i + 60]!r}')
path = os.path.join(d, 'DSK1', 'LAMPLIR0')
recs = open(path, 'rb').read().split(b'\n')[:-1] if os.path.exists(path) else None
check('DSK1.LAMPLIR0 holds the two commands, a record each (the RECORD commands themselves left out)', recs == [b'look', b'n'], recs)
check('the Python VM\'s script is the same', files.get('R0') == ['look', 'n'], files)
check('REPLAY of a script that is not there says so', 'There is no script 1.' in got, got[-200:])

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
