#!/usr/bin/env python3
"""m6_testplay_test.py - test-play (M6 part 5, D4): the compiled game played from SAMS.

  - P, T compiles Lamplight and plays it from SAMS: the engine from the
    cartridge, the story the compile left in SAMS (nothing written to
    disk), the pictures and music from their files: the title page and the
    start of the walkthrough as the Python VM plays them;
  - FCTN = ends it: the console restarts with the cartridge on bank 0, so
    the workbench is back;
  - test-play writes no files.

  python3 tests/m6_testplay_test.py"""
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
    equeue = [k for line in walk for k in ([line] if isinstance(line, set) else keys_for(line))]
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

P, T = ('key', 'p'), ('key', 't')
FCTN_EQ = {(0, 4), (0, 0)}                     # FCTN and = (column 0, row 0; key_pos('=') means ENTER)
d, ppath = g['stage'](open('samples/lamplight.txa').read(), 'lamplight', g['LIB'])
outC = tempfile.mkdtemp()                       # Lamplight's picture and music files, from the PC
fc = txa_game.write_game('samples/lamplight.txa', 'LAMPLI', 'LAMPLIGHT', out=outC, quiet=True)
for n in fc['picture_files'] + fc['sound_files']:
    shutil.copy(os.path.join(outC, n), os.path.join(d, 'DSK1', n))
before = set(os.listdir(os.path.join(d, 'DSK1')))
esy = build.symbols(os.path.join(build.B, 'engine.equ'))
img, _ = compile_file('samples/lamplight.txa', ['lib'], title='LAMPLIGHT', date=g['DATE'])
walk = open('samples/lamplight.walk').read().split('\n')[:-1][:12]
want_all = run_image(img, walk)
got, m, why = run_then_play(d, [P, 'dsk1.lamplight', '', '', T], walk)
want = want_all[:want_all.rindex('\n>') + 2] if why == 'waiting' else want_all
i = next((k for k in range(min(len(got), len(want))) if got[k] != want[k]), min(len(got), len(want)))
check(f'T compiled and test-played the game from SAMS: the title page and the walkthrough\'s start as the Python VM plays them '
      f'({len(got)} characters)', got == want and why == 'waiting',
      f'{why} at {i}: python {want[max(0, i - 80):i + 60]!r}\n  ti {got[max(0, i - 80):i + 60]!r}')
check('the engine ran in test-play mode (STMODE 2) and found the picture files (PICPG 8)',
      m.rw(esy['STMODE']) == 2 and m.rw(esy['PICPG']) == 8, (m.rw(esy['STMODE']), m.rw(esy['PICPG'])))
after = set(os.listdir(os.path.join(d, 'DSK1')))
new = sorted(after - before)
check('test-play wrote nothing but the compile\'s story files (no engine files)', all(n.startswith('LAMPLIS') for n in new), new)
d3, _ = g['stage'](open('samples/lamplight.txa').read(), 'lamplight', g['LIB'])
for n in fc['picture_files'] + fc['sound_files']:
    shutil.copy(os.path.join(outC, n), os.path.join(d3, 'DSK1', n))
try:
    got3, m3, why3 = run_then_play(d3, [P, 'dsk1.lamplight', '', '', T], ['look', FCTN_EQ], to_reset=True)
    ok3, detail = why3 == 'reset' and m3.bank == 0, (why3, m3.bank)
except S.Halt as e:
    ok3, detail = False, str(e)
check('FCTN = ends test-play: the console restarts with the cartridge on bank 0, the workbench back', ok3, detail)

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
