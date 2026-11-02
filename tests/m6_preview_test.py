#!/usr/bin/env python3
"""m6_preview_test.py - the I key (M6 part 9): a TI Artist picture previewed
on the TI and its fitting chosen.  With BIRD_P and BIRD_C on DSK1 and no
BIRD_T: I, the name (offered as DSK1.), ENTER; the picture shows as crop 48
(the bitmap in VRAM is tiartist's crop 48, the layer on as the engine sets
it, the TI's colours in palette 32-47, the row reading "Crop: rows 48 to
143"); FCTN X twice: crop 52; S: the squeeze; S: crop 52 again; ENTER:
BIRD_T says "crop 52", the menu is back and the layer off.  Then I again
reads BIRD_T: the preview opens at crop 52.

  python3 tests/m6_preview_test.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); os.chdir(ROOT)
import tiartist
src = open(os.path.join(ROOT, 'tests/m5_sema_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m5_sema_test.py'), '__name__': 'pv'}
sys.argv = ['pv', 'none']
exec(compile(src[:src.index('args = sys.argv[1:]')], 'm5', 'exec'), g)
S, sy, R, keys_for = g['S'], g['sy'], g['R'], g['keys_for']
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:700]))
    fails += 0 if ok else 1
pat, col = tiartist.read_file('tests/data/BIRD_P'), tiartist.read_file('tests/data/BIRD_C')
rows = tiartist.pixels(pat, col)
def raw(how):
    return tiartist.raw(tiartist.fit(rows, how))
import tempfile
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, 'DSK1'))
open(os.path.join(d, 'DSK1', 'BIRD_P'), 'wb').write(pat)
open(os.path.join(d, 'DSK1', 'BIRD_C'), 'wb').write(col)

def session(steps, m=None):
    """Press each key set in steps at the workbench's key wait; snapshot the
    state before each press (and once more after the last)."""
    if m is None:
        m = S.Machine(g['cart'], f18a=True, pages=128); m.disk_dir = d
        cpu = S.CPU(m); cpu.pc = m.rw(m.rw(0x6006) + 2)
    else:
        m, cpu = m
    snaps = []; queue = list(steps); steps_run = hold = free = 0
    while steps_run < 120_000_000:
        if cpu.pc == sy['WK1'] and not hold and steps_run >= free:
            snaps.append({'vram': bytes(m.vram[0x2000:0x3800]), 'vr': list(m.vregs), 'pal': dict(m.palette),
                          'screen': R.screen(m)})
            if not queue:
                break
            m.held = queue.pop(0); hold = steps_run + 12_000
        if hold and steps_run >= hold:
            m.held = None; hold = 0; free = steps_run + 12_000
        cpu.step(); steps_run += 1
    return snaps, (m, cpu)

def k(s):
    return keys_for(s)[:-1]
ENTER = keys_for('')
steps = k('i') + k('bird') + ENTER + k('\x0c') + k('\x0c') + k('s') + k('s') + ENTER
snaps, mc = session(steps)
n0 = len(k('i'))                       # the menu, then I
s_name = snaps[n0]
check('I asks for the picture, offering the source\'s device: "Picture: DSK1."', 'Picture: DSK1.' in s_name['screen'],
      s_name['screen'].splitlines()[5:7])
i_show = n0 + len(k('bird')) + 1      # after ENTER: the preview, waiting for a key
s = snaps[i_show]
def shows(s, how, label):
    want = raw(how)
    on = s['vr'][31] == 0xD8 and s['vr'][32] == 0x80 and s['vr'][34] == 8 and s['vr'][36] == 96
    pal = all(s['pal'].get(32 + i) == v for i, v in enumerate(tiartist.TI_PALETTE))
    got = s['vram'][:6144]
    first = next((j for j in range(6144) if got[j] != want[j]), None)
    check(label, on and pal and got == want, (hex(s['vr'][31]), s['vr'][32:37], pal, first))
shows(s, ('crop', 48), 'no BIRD_T: the preview shows crop 48 (tiartist\'s pixels in VRAM >2000, the layer on at row 1, 96 rows, 16 colours, the TI palette in 32-47)')
check('row 13: "Crop: rows 48 to 143 of the 192."', 'Crop: rows 48 to 143 of the 192.' in s['screen'], s['screen'].splitlines()[12:15])
shows(snaps[i_show + 2], ('crop', 52), 'FCTN X twice: crop 52')
shows(snaps[i_show + 3], ('squeeze', 0), 'S: the squeeze')
check('row 13 says so', 'Squeeze: the whole picture at half height.' in snaps[i_show + 3]['screen'])
shows(snaps[i_show + 4], ('crop', 52), 'S again: back to crop 52')
end = snaps[-1]
t = open(os.path.join(d, 'DSK1', 'BIRD_T')).read() if os.path.exists(os.path.join(d, 'DSK1', 'BIRD_T')) else None
check('ENTER: BIRD_T written, "crop 52"', t is not None and t.strip() == 'crop 52', t)
check('the menu is back and the layer off', not end['vr'][31] & 0x80 and 'P Project C Compile' in end['screen'], (hex(end['vr'][31]),))
snaps2, _ = session(k('i') + ENTER, mc)
s2 = snaps2[-1]
shows(s2, ('crop', 52), 'I again (the name kept): BIRD_T read, the preview opens at crop 52')
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
