#!/usr/bin/env python3
"""m6_engine_test.py - the generic engine (M6 part 1, decisions D1 and D2).

  - one engine serves every game: two games' engine files are the same but
    for the story-name field the game writer patches in;
  - a story the workbench compiled (the simulated TI writes LAMPLIS01-08)
    plays on that engine with the PC's picture and music files: the start
    of Lamplight's walkthrough gives the Python VM's transcript;
  - a game without its picture files still plays (no pictures).

  python3 tests/m6_engine_test.py"""
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

# 1. one engine, every game
outA, outB = tempfile.mkdtemp(), tempfile.mkdtemp()
fa = txa_game.write_game('samples/lamplight.txa', 'LAMP', 'LAMPLIGHT', out=outA, quiet=True)
fb = txa_game.write_game('demos/m2demo.txa', 'DEMO', 'M2DEMO', out=outB, quiet=True)
def masked(path):
    d = open(path, 'rb').read()
    i = d.find(build.NAMEMARK.encode())
    return d if i < 0 else d[:i] + bytes(build.NAMEFLD + 1 + len(build.NAMEMARK)) + d[i + len(build.NAMEMARK) + 1 + build.NAMEFLD:]
same = [masked(os.path.join(outA, a)) == masked(os.path.join(outB, b)) for a, b in zip(fa['engine'], fb['engine'])]
check(f'one engine for every game: {len(same)} engine files the same for two games but the name field', all(same) and len(fa['engine']) == len(fb['engine']), same)
named = [open(os.path.join(outA, n), 'rb').read().find(b'DSK1.LAMP') >= 0 for n in fa['engine']]
check('the game writer patched the name in (DSK1.LAMP)', any(named), named)

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

# 2. the TI's own story files, with the PC's pictures and music
d, ppath = g['stage'](open('samples/lamplight.txa').read(), 'lamplight', g['LIB'])
m, steps = g['run_ti'](d, 'lamplight')
ti = sorted(glob.glob(os.path.join(d, 'DSK1', 'LAMPLIS*')))
check(f'the workbench wrote the story: {len(ti)} files, LAMPLIS01..', len(ti) == 8, [os.path.basename(f) for f in ti])
outC = tempfile.mkdtemp()
fc = txa_game.write_game('samples/lamplight.txa', 'LAMPLI', 'LAMPLIGHT', out=outC, quiet=True)
got, mm, why = play(outC, fc['engine'], ti + fc['picture_files'] + fc['sound_files'], walk)
ok, want = same_as_python(got, why)
i = next((k for k in range(min(len(got), len(want))) if got[k] != want[k]), min(len(got), len(want)))
check(f'the TI\'s story plays on the generic engine with the PC\'s {len(fc["picture_files"])} picture and {len(fc["sound_files"])} music files: '
      f'the walkthrough\'s start as the Python VM plays it', ok, f'{why} at {i}: python {want[max(0, i - 80):i + 60]!r}\n  ti {got[max(0, i - 80):i + 60]!r}')

# 3. no picture files: the game still plays
got3, m3, why3 = play(outA, fa['engine'], fa['story'] + fa['sound_files'], walk)
ok3, _ = same_as_python(got3, why3)
check('without its picture files the game still plays (no pictures), the same transcript', ok3, why3)

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
