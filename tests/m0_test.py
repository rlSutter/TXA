#!/usr/bin/env python3
"""m0_test.py - plays the M0 probe in the simulator.

  python3 tests/m0_test.py [--png]

Each check prints one line, PASS or FAIL.  Covers: the requirements
screens (no F18A; F18A with 128K SAMS), SAMS sizing (512K and 1M), the
probe screen in 24 and 30 rows, the bitmap layer's registers and its
picture decoded into VRAM byte for byte, moving and resizing it, the fat
pixel format, the full-screen view and back, the text test's scrolling,
and Quit putting the F18A back.  --png writes screens to build/shots/."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import sim9900 as S, render80 as R
CART = open(os.path.join(ROOT, 'build/txaprobe8.bin'), 'rb').read()
PNG = '--png' in sys.argv
fails = 0

def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '  ' + detail))
    fails += 0 if ok else 1

def boot(f18a=True, pages=128):
    m = S.Machine(CART, f18a=f18a, pages=pages); cpu = S.CPU(m)
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    run(cpu, 3_000_000)
    return m, cpu

def run(cpu, n):
    for _ in range(n):
        cpu.step()

def press(m, cpu, ch, n=400_000):
    m.held = S.key_pos(ch); run(cpu, 60_000); m.held = None; run(cpu, n)

def shot(m, name):
    if PNG:
        os.makedirs(os.path.join(ROOT, 'build/shots'), exist_ok=True)
        R.render(m, os.path.join(ROOT, 'build/shots', name + '.png'))

# --- requirements -----------------------------------------------------------
m, cpu = boot(f18a=False)
t = R.screen(m)
check('no F18A: Graphics I requirements screen', 'NEEDS AN F18A' in t and not R.is_t80(m), t[:200])
shot(m, 'req-nof18a')
m, cpu = boot(pages=32)
t = R.screen(m)
check('128K SAMS: refused in 80 columns, size reported', R.is_t80(m) and '512K or more' in t and ' 128K of SAMS' in t, t[:300])
shot(m, 'req-128k')

# --- the probe screen ---------------------------------------------------------
m, cpu = boot()
t = R.screen(m); top = t.splitlines()[0]
check('80-column mode, 24 rows', R.is_t80(m) and R.rows(m) == 24)
check('status line: title, 512K, 24 rows', 'TXA M0 PROBE' in top and 'SAMS  512K' in top and '24 ROWS' in top, top)
check('status line is reverse video', m.vram[1] == ord('T') | 0x80)
check('help text in the text window', 'full-screen picture view' in t and t.splitlines()[13].startswith('Bitmap layer'), t)
v = m.vregs
check('bitmap layer on, above text, palette 32-35', v[31] == 0xC8, hex(v[31]))
check('bitmap layer at >2800, 256 x 96 from scanline 8', (v[32], v[33], v[34], v[35], v[36]) == (0xA0, 0, 8, 0, 96), str(v[32:37]))
raw2 = open(os.path.join(ROOT, 'build/pic2.raw'), 'rb').read()
check('picture decoded into VRAM byte for byte (RLE)', bytes(m.vram[0x2800:0x4000]) == raw2)
check('palette 32-35 loaded', all(i in m.palette for i in range(32, 36)))
check('font and reverse font', m.vram[0x1000 + ord('A') * 8 + 1] == 0x30 and m.vram[0x1000 + (ord('A') | 0x80) * 8 + 1] == 0xCF)
shot(m, 'probe-24')

press(m, cpu, 'D'); press(m, cpu, 'X'); press(m, cpu, 'Z')
check('D X Z: picture right 8, down 8, 8 rows shorter', (m.vregs[33], m.vregs[34], m.vregs[36]) == (8, 16, 88), str(m.vregs[33:37]))
check('the line on screen follows', 'X=  8  Y= 16  H= 88' in R.screen(m))
press(m, cpu, 'S'); press(m, cpu, 'E'); press(m, cpu, 'W'); press(m, cpu, 'W')
check('S E W W: back, and no taller than the picture', (m.vregs[33], m.vregs[34], m.vregs[36]) == (0, 8, 96), str(m.vregs[33:37]))

press(m, cpu, 'F')
raw4 = open(os.path.join(ROOT, 'build/pic4.raw'), 'rb').read()
check('F: fat pixels, 16 colours, picture reloaded', m.vregs[31] == 0xD8 and bytes(m.vram[0x2800:0x4000]) == raw4, hex(m.vregs[31]))
check('F: palette 32-47 loaded', all(i in m.palette for i in range(32, 48)))
shot(m, 'probe-fat')
press(m, cpu, 'F')

press(m, cpu, 'R')
t = R.screen(m)
check('R: 30 rows', R.rows(m) == 30 and '30 ROWS' in t.splitlines()[0], t.splitlines()[0])
shot(m, 'probe-30')

press(m, cpu, 'P')
t = R.screen(m)
check('P: pane off, layer off, text from row 1', m.vregs[31] == 0 and t.splitlines()[1].startswith('Bitmap layer'), t[:300])
press(m, cpu, 'P')

press(m, cpu, 'T', 3_000_000)
t = R.screen(m).splitlines()
check('T: text test scrolls the window, pane rows untouched', t[-1].startswith('[Press any key]') and t[13] != 'Bitmap layer' and all(not l for l in t[1:13]), '\n'.join(t))
shot(m, 'probe-text')
press(m, cpu, ' ')

press(m, cpu, 'V')
check('V: Graphics I, layer centred, 24 rows', not R.is_t80(m) and m.vregs[49] == 0 and (m.vregs[33], m.vregs[34]) == (0, 48), str(m.vregs[33:37]))
check('V: caption', 'Full-screen view' in R.screen(m))
shot(m, 'view')
press(m, cpu, ' ')
check('back from V: 80 columns, 30 rows, position kept', R.is_t80(m) and R.rows(m) == 30 and m.vregs[34] == 8)

press(m, cpu, 'Q', 200_000)
vr, _, mapping = m.at_reset              # the state at the console reset (the simulator then reboots the cartridge)
check('Q: VR49, VR31, VR0 restored, SAMS mapping off at the reset', vr[49] == 0 and vr[31] == 0 and vr[0] == 0 and not mapping,
      str((vr[0], vr[31], vr[49], mapping)))

# --- SAMS sizing ---------------------------------------------------------------
m, cpu = boot(pages=256)
check('1M card counted as 1024K', 'SAMS 1024K' in R.screen(m).splitlines()[0], R.screen(m).splitlines()[0])
os.environ['SIM_RANDOM_RAM'] = '7'
m, cpu = boot()
check('random RAM at power-up: same screen', 'SAMS  512K' in R.screen(m).splitlines()[0] and m.vregs[31] == 0xC8)

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
