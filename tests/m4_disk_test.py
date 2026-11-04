#!/usr/bin/env python3
"""m4_disk_test.py - the game writer, and the engine loading its story from disk.

tools/txa_game.py writes Lamplight as disk files; the engine (run by the
simulator's cartridge loader, but built to read the story from disk)
loads LAMPS01-LAMPS08 from the simulator's DSK1 folder and plays the
first part of the walkthrough: the transcript must equal the Python
VM's.  Also: the disk image holds every file, the E/A 5 chain is sound,
and a missing story file stops with its name.

  python3 tests/m4_disk_test.py"""
import os, sys, tempfile, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build, txa_game, sim9900 as S, render80 as R
from txc.codegen import compile_file
from txc.txvm import run_image
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'm4d'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
keys_for = g['keys_for']
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:2000]))
    fails += 0 if ok else 1

out = tempfile.mkdtemp()
files = txa_game.write_game(os.path.join(ROOT, 'samples/lamplight.txa'), 'LAMP', 'LAMPLIGHT', out=out, quiet=True)
nfiles = len(files['story'])
neng = len(build.ea5_segments('TXAE1')) if False else len(files['engine'])
check(f'the writer: {neng} engine files (the kernel, the font, the resident engine), {nfiles} story files, a disk image',
      neng >= 3 and len(files['story']) == nfiles and os.path.exists(files['disk']), files)
cat = build.run([sys.executable, build.XDM, files['disk']])
every = files['engine'] + files['story'] + files['picture_files'] + files['sound_files']
check('the disk image holds every file, as PROGRAM files', all(n in cat for n in every) and cat.count('PROGRAM') == len(every), cat)
chain = [open(os.path.join(out, n), 'rb').read() for n in files['engine']]
flags = [int.from_bytes(c[:2], 'big') for c in chain]; addrs = [int.from_bytes(c[4:6], 'big') for c in chain]
check('the E/A 5 chain: "more" flags, then the last; it starts at >2000 (KENTRY)', flags[:-1] == [0xFFFF] * (neng - 1) and flags[-1] == 0 and addrs[0] == 0x2000, (flags, [hex(a) for a in addrs]))

# the engine as the writer wrote it (the generic disk engine, its name patched in),
# loaded by the cartridge loader
for n in files['engine']:
    shutil.copy(os.path.join(out, n), os.path.join(build.B, n))
segs = build.ea5_segments(files['engine'][0])
cart, _ = build.cart_from_segments(segs, 'LAMP DISK')
def run(dsk_files, cmds, max_steps=150_000_000, setup=None):
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, 'DSK1'))
    for n in dsk_files:
        shutil.copy(os.path.join(out, n), os.path.join(d, 'DSK1', n))
    sy = build.symbols(os.path.join(build.B, 'engine.equ'))
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
    if setup:
        setup(m)
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    queue = [k for line in cmds for k in keys_for(line)]
    outp, steps, hold, free = [], 0, 0, 0
    while steps < max_steps:
        pc = cpu.pc
        if pc == sy['CHOUT']:
            outp.append(chr(m.rw(0x8300) & 0xFF))
        if pc in (sy['VMHALT'], sy['LDK9'] + 0):
            if pc == sy['LDK9']:
                for _ in range(400_000):
                    cpu.step()
            return ''.join(outp), m, 'halt' if pc == sy['VMHALT'] else 'nofile'
        if pc == sy['WKY1'] and not hold and steps >= free:      # a single-key wait (the title page, [MORE]): any key
            m.held = keys_for(' ')[0]; hold = steps + 12_000
        if pc == sy['WK21'] and not hold and steps >= free:
            if not queue:
                return ''.join(outp), m, 'waiting'
            m.held = queue.pop(0); hold = steps + 12_000
        if hold and steps >= hold:
            m.held = None; hold = 0; free = steps + 12_000
        cpu.step(); steps += 1
    return ''.join(outp), m, 'steps'

img, _ = compile_file(os.path.join(ROOT, 'samples/lamplight.txa'), [os.path.join(ROOT, 'lib')], title='LAMPLIGHT')
walk = open(os.path.join(ROOT, 'samples/lamplight.walk')).read().split('\n')[:-1][:12]
want = run_image(img, walk)
allfiles = files['story'] + files['picture_files'] + files['sound_files']
got, m, why = run(allfiles, walk)
want = want[:want.rindex('\n>') + 2] if why == 'waiting' else want
i = next((k for k in range(min(len(got), len(want))) if got[k] != want[k]), min(len(got), len(want)))
check(f'the story ({nfiles} files), pictures ({len(files["picture_files"])}) and sounds ({len(files["sound_files"])}) loaded from '
      f'their own disk files: the walkthrough\'s start plays identically', got == want,
      f'{why} at {i}: python {want[max(0,i-80):i+60]!r}\n  ti {got[max(0,i-80):i+60]!r}')
got2, m2, why2 = run([n for n in allfiles if n != 'LAMPS03'], [])
screen = R.screen(m2)
check('a missing story file stops with its name', why2 == 'nofile' and 'Cannot read the story file DSK1.LAMPS03' in screen, screen[:400])

# 1.0.1, from the SAMS Kernel's 1.28.0: a card that lists DSK1 but declines it (a
# plain return, as a TIPI can for a device it is not set up for; a real TIPI's DSR
# lists DSK names), at CRU >1000, ahead of the drive at >1100.  The search must go
# on to the next name and card, as the console's DSRLNK does; TXA's once stopped
# there with an error, so a console with a TIPI and a disk controller could not
# load from the floppy.  (The kernel found it on real hardware: a TIPI and an
# RS232 card hid PIO.)
def decoy(m):
    rom = bytearray(0x2000)
    rom[0:4] = b'\xAA\x01\x00\x00'
    rom[8:10] = (0x4010).to_bytes(2, 'big')                       # the DSR list
    rom[0x10:0x12] = b'\x00\x00'; rom[0x12:0x14] = (0x4030).to_bytes(2, 'big'); rom[0x14:0x19] = b'\x04DSK1'
    rom[0x30:0x32] = (0x045B).to_bytes(2, 'big')                  # B *R11: declines
    st = {'on': False}
    cw, rb = m.cru_write, m.rb
    def cru_write(bit, v):
        if bit == 0x800:                                          # CRU >1000
            st['on'] = bool(v); return
        cw(bit, v)
    def rb2(addr):
        if st['on'] and 0x4000 <= addr < 0x6000:
            return rom[addr - 0x4000]
        return rb(addr)
    m.cru_write = cru_write; m.rb = rb2
got_d, m_d, why_d = run(allfiles, walk, setup=decoy)
check('a card at >1000 that lists DSK1 and declines it (a TIPI can): the search goes on to the drive at >1100, and the walkthrough\'s start plays as without it',
      why_d == why and got_d == got, (why_d, got_d[-300:], R.screen(m_d)[:300]))

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
