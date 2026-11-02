#!/usr/bin/env python3
"""tipi_test.py - what TXA borrowed from the SAMS Kernel: DSRLNK never runs a TIPI's power-up (src/tipi.a99, from the
SAMS Kernel 1.16.1: a TIPI's power-up only resets its Pi).  The workbench
compiles a small program from the simulator's disk card twice: as it is
(a disk controller: powered up, as TXA's VRAM use requires) and with its
first device renamed TIPI (DSK1 the second): no power-up runs, and the
compile reads its files all the same.  Also the workbench's SAMS page test
(WPTEST, from the kernel's AMSTST): a 256K card refused, a 1M card started.

  python3 tests/tipi_test.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); os.chdir(ROOT)
src = open(os.path.join(ROOT, 'tests/m5_sema_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m5_sema_test.py'), '__name__': 'tp'}
sys.argv = ['tp', 'none']
exec(compile(src[:src.index('args = sys.argv[1:]')], 'm5', 'exec'), g)
S, sy = g['S'], g['sy']
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:600]))
    fails += 0 if ok else 1
PROG = 'ROUTINE Main\n  PRINT "hi"\nEND\n'
def as_tipi(m):
    """The card's first device TIPI, DSK1 second (both answered by the same code)."""
    r = m.dsrrom
    r[0x10:0x12] = (0x4050).to_bytes(2, 'big'); r[0x12:0x14] = (0x4030).to_bytes(2, 'big'); r[0x14:0x19] = b'\x04TIPI'
    r[0x50:0x52] = b'\x00\x00'; r[0x52:0x54] = (0x4030).to_bytes(2, 'big'); r[0x54:0x59] = b'\x04DSK1'
import types
RealS = S
def compile_once(tipi):
    made = []
    class M(RealS.Machine):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            if tipi:
                as_tipi(self)
            made.append(self)
    g['S'] = types.SimpleNamespace(**{k: getattr(RealS, k) for k in dir(RealS) if not k.startswith('__')})
    g['S'].Machine = M
    try:
        d, pp = g['stage'](PROG, 'tiny', None)
        m, steps = g['run_ti'](d, 'tiny')
    finally:
        g['S'] = RealS
    return m
m = compile_once(False)
n_plain = getattr(m, 'powerups', 0)
check(f'an ordinary disk card: its power-up runs ({n_plain} times: TXA rebuilds the controller\'s VRAM buffers, which its picture overwrites)',
      n_plain > 0 and m.rw(sy['WBERR']) == 0 and m.rw(sy['WBDONE']) == 4, (n_plain, m.rw(sy['WBERR']), m.rw(sy['WBDONE'])))
t = compile_once(True)
n_tipi = getattr(t, 'powerups', 0)
check('the same card as a TIPI (its first device TIPI): no power-up runs, and the compile reads its files and finishes',
      n_tipi == 0 and t.rw(sy['WBERR']) == 0 and t.rw(sy['WBDONE']) == 4, (n_tipi, t.rw(sy['WBERR']), t.rw(sy['WBDONE'])))
check('the workbench found the TIPI at start-up (TIPCRU >1100)', t.rw(sy['TIPCRU']) == 0x1100 and m.rw(sy['TIPCRU']) == 0,
      (hex(t.rw(sy['TIPCRU'])), hex(m.rw(sy['TIPCRU']))))
# the SAMS page test (WPTEST, from the kernel's AMSTST): a card under 512K
# is refused with a screen saying so; a 1M card starts as before
def boot(pages):
    m = RealS.Machine(g['cart'], f18a=True, pages=pages); cpu = RealS.CPU(m)
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    for _ in range(3_000_000):
        cpu.step()
        if cpu.pc == sy['WK1']:
            break
    return m, cpu
m64, c64 = boot(64)
scr = g['R'].screen(m64)
check('a 256K card is refused: "SAMS page 16 did not answer" (page 80 is the same memory and overwrote it) and what the workbench needs, not the menu',
      'SAMS page 16 did not answer' in scr and '512K or more' in scr and c64.pc != sy['WK1'], scr.splitlines()[1:5])
m256, c256 = boot(256)
check('a 1M card passes the test and reaches the menu', c256.pc == sy['WK1'] and 'did not answer' not in g['R'].screen(m256))
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
