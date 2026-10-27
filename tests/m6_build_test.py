#!/usr/bin/env python3
"""m6_build_test.py - Build (M6 part 3): the workbench writes a whole game.

  - B on the simulated TI compiles the project and writes the engine's
    files, LAMPLI1 .. LAMPLI5: the same bytes as the PC game writer's for
    the prefix LAMPLI (the generic engine, its story name patched in);
  - its story files equal the PC's but for the build date;
  - the game the TI built (its engine and story, the PC's picture and
    music files) plays the start of Lamplight's walkthrough with the
    Python VM's transcript;
  - the project's prefix can be changed: P, ..., a new prefix, B writes
    the files under it.

  python3 tests/m6_build_test.py"""
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

P, B = ('key', 'p'), ('key', 'b')
d, ppath = g['stage'](open('samples/lamplight.txa').read(), 'lamplight', g['LIB'])
m, steps = run_keys(d, [P, 'dsk1.lamplight', '', 'lampli', B])
scr = g['R'].screen(m).splitlines()
eng = sorted(n for n in os.listdir(os.path.join(d, 'DSK1')) if n.startswith('LAMPLI') and n[6:].isdigit())
check(f'B compiled the project and wrote the engine\'s files: {eng} ({steps / 1e6:.0f}M instructions)', len(eng) == 5, eng)
check('the screen says how to load it', 'The game is built: load DSK1.LAMPLI1' in scr[8], scr[4:11])
outC = tempfile.mkdtemp()
fc = txa_game.write_game('samples/lamplight.txa', 'LAMPLI', 'LAMPLIGHT', out=outC, quiet=True)
same = [open(os.path.join(d, 'DSK1', a), 'rb').read() == open(os.path.join(outC, a), 'rb').read() for a in fc['engine']]
check(f'the TI\'s engine files equal the PC game writer\'s, byte for byte ({len(same)} files)', all(same) and eng == fc['engine'], same)
img, _ = compile_file('samples/lamplight.txa', ['lib'], title='LAMPLIGHT', date=g['DATE'])
nfiles = (len(img) + 4095) // 4096                 # (the story's files: as many as its length needs)
story = b''.join(open(os.path.join(d, 'DSK1', f'LAMPLIS{i:02d}'), 'rb').read() for i in range(1, nfiles + 1))
check('the TI\'s story files equal the PC compiler\'s image', story == img, (len(story), len(img)))
walk = open('samples/lamplight.walk').read().split('\n')[:-1][:12]
want_all = run_image(img, walk)
tifiles = [os.path.join(d, 'DSK1', n) for n in eng + [f'LAMPLIS{i:02d}' for i in range(1, nfiles + 1)]]
for n in eng:                                   # (play() loads the engine from outC: the TI's go there)
    shutil.copy(os.path.join(d, 'DSK1', n), os.path.join(outC, n))
got, mm, why = play(outC, eng, tifiles[len(eng):] + fc['picture_files'] + fc['sound_files'], walk)
want = want_all[:want_all.rindex('\n>') + 2] if why == 'waiting' else want_all
check('the game the TI built plays (its engine and story, the PC\'s pictures and music): the walkthrough\'s start as the Python VM plays it',
      got == want, why)
d2, _ = g['stage'](open('samples/lamplight.txa').read(), 'lamplight', g['LIB'])
m2, _ = run_keys(d2, [P, 'dsk1.lamplight', '', 'glow', B])
names = sorted(os.listdir(os.path.join(d2, 'DSK1')))
import re
check('another prefix (GLOW): the story and engine files take it', 'GLOW1' in names and 'GLOWS01' in names
      and not any(re.match(r'LAMPLI(S?\d+)$', n) for n in names),
      names)

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
