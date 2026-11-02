#!/usr/bin/env python3
"""m5_load_test.py - the workbench reads a DV80 source file into SAMS.

Lamplight's source, wrapped to 80 columns (tools/txa_wrap.py), is put in
the simulator's DSK1 as a DIS/VAR 80 file; the workbench cartridge is
started, the name typed at its prompt, and the text it puts in SAMS (from
page 32, each record followed by a line feed) must equal the file, with
the right line and byte counts on the screen.  A name that isn't there
must say so.

  python3 tests/m5_load_test.py"""
import os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'm5l'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
S, build, R, keys_for = g['S'], g['build'], g['R'], g['keys_for']
from txa_wrap import wrap_text
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:1200]))
    fails += 0 if ok else 1

text = wrap_text(open(os.path.join(ROOT, 'samples/lamplight.txa')).read())
lines = text.split('\n')
if lines and lines[-1] == '':
    lines.pop()
want = ''.join(l + '\n' for l in lines).encode('latin-1')
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, 'DSK1'))
open(os.path.join(d, 'DSK1', 'LAMPLIGHT'), 'w', encoding='latin-1').write('\n'.join(lines) + '\n')
cart, _ = build.workbench_cart()
_p = (cart[6] << 8) | cart[7]                    # the console menu's entry: next, start, name
_n = cart[_p - 0x6000 + 4]
_name = cart[_p - 0x6000 + 5: _p - 0x6000 + 5 + _n]
sy = build.symbols(os.path.join(build.B, 'wbench.equ'))
check(f'the console menu names the cartridge TXA WORKBENCH ({_name!r})', _name == b'TXA WORKBENCH')
check('every record fits DV80 (80 characters)', max(len(l) for l in lines) <= 80)

def run(typed, max_steps=150_000_000):
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    # a line is typed with ENTER after it; ('key', c) is the one key c (the menu's)
    queue = [k for t in typed for k in (keys_for(t[1])[:-1] if isinstance(t, tuple) else keys_for(t))]
    steps = hold = free = 0
    while steps < max_steps:
        pc = cpu.pc
        if pc == sy['WK1'] and not m.rw(sy['WBONLY']):
            m.ww(sy['WBONLY'], 1)               # one file, lexed and parsed only (no INCLUDEs followed)
        if pc == sy['WK1'] and not hold and steps >= free:
            if not queue:
                return m
            m.held = queue.pop(0); hold = steps + 12_000
        if hold and steps >= hold:
            m.held = None; hold = 0; free = steps + 12_000
        cpu.step(); steps += 1
    return m

P, C, T = ('key', 'p'), ('key', 'c'), ('key', 't')
m = run([P, '', C])                            # the menu (M6): P, ENTER keeps DSK1.LAMPLIGHT, C compiles
nl, ln = m.rw(sy['WBLNS']), m.rw(sy['WBLENL']) | (m.rw(sy['WBLENH']) << 16)
got = bytes(m.ams[32 * 4096: 32 * 4096 + ln])
check(f'the workbench read {len(lines)} lines, {len(want)} bytes (lexed and parsed them: done 3)', (m.rw(sy['WBDONE']), nl, ln) == (3, len(lines), len(want)), (m.rw(sy['WBDONE']), nl, ln))
check('the text in SAMS (from page 32, a line feed after each record) is the file', got == want,
      next((f'at byte {i}: {want[max(0,i-30):i+30]!r} / {got[max(0,i-30):i+30]!r}' for i in range(min(len(got), len(want))) if got[i] != want[i]), 'length'))
scr = R.screen(m).splitlines()
check('the screen says so', scr[4].strip() == f'Read {len(lines)} lines, {len(want)} bytes.' and scr[0].startswith(' TXA Workbench'), scr[:5])
check('the main menu shows the project and its keys, the results under them',
      scr[2].strip() == 'Source file: DSK1.LAMPLIGHT'
      and scr[10].strip() == 'P Project C Compile T Test R Run B Build E Errors S Stats I Import O Options', scr[:12])
mp = run([P])                               # P: the name open for editing, and said so (Rebecca: "you can't change the filename")
sp = R.screen(mp).splitlines()
check('P shows a cursor after the name and a hint on row 11', sp[2].rstrip().endswith('DSK1.LAMPLIGHT_')
      and sp[11].strip() == 'Type the source file (DSK1.NAME): FCTN S rubs out, ENTER keeps the one shown.', sp[2:12])
mq = run([P, 'dsk1.ab'])                    # typed: the first key replaced the name; ENTER took it
check('typing after P replaces the name (DSK1.AB), and ENTER keeps it', R.screen(mq).splitlines()[2].strip().startswith('Source file: DSK1.AB'),
      R.screen(mq).splitlines()[2])
m2 = run([P, 'dsk1.nosuch', C])            # (lower case: KEYGET stops at SHIFT; it gives capitals)
check('a file that isn\'t there: "Cannot open that file."', m2.rw(sy['WBDONE']) == 0xFFFF and 'Cannot open that file.' in R.screen(m2), R.screen(m2).splitlines()[:5])
m3 = run([P, 'dsk1.lamplightx\b', C])     # an extra letter, then FCTN S rubs it out
check('FCTN S rubs out: "DSK1.LAMPLIGHTX" then FCTN S reads DSK1.LAMPLIGHT', m3.rw(sy['WBLNS']) == len(lines) and m3.rw(sy['WBDONE']) == 3,
      (m3.rw(sy['WBDONE']), m3.rw(sy['WBLNS']), R.screen(m3).splitlines()[2]))
m4 = run([P, 'DSK1.LAMPLIGHT', C])          # capitals typed with SHIFT
check('a name typed with SHIFT (capitals) works', m4.rw(sy['WBLNS']) == len(lines) and m4.rw(sy['WBDONE']) == 3,
      (m4.rw(sy['WBDONE']), R.screen(m4).splitlines()[2]))
m5 = run([C])                               # C alone: the project's default file
check('C alone compiles the project as it stands (DSK1.LAMPLIGHT at start-up)', m5.rw(sy['WBDONE']) == 3 and m5.rw(sy['WBLNS']) == len(lines),
      R.screen(m5).splitlines()[:12])
m6 = run([C, C])                            # compiled twice
check('C again compiles again, the results replaced', m6.rw(sy['WBDONE']) == 3 and m6.rw(sy['WBLNS']) == len(lines)
      and R.screen(m6).splitlines()[4].strip() == f'Read {len(lines)} lines, {len(want)} bytes.', R.screen(m6).splitlines()[:12])
ms = run([('key', 's')])                    # S (M6 part 10) before a full compile: nothing to show
check('S before a compile that links: "No statistics yet ..."', R.screen(ms).splitlines()[4].strip().startswith('No statistics yet'),
      R.screen(ms).splitlines()[3:6])
mo = run([('key', 'o')])                    # O (M6 part 10): the options
check('O shows the options (colours, font, library devices)', R.screen(mo).splitlines()[5].strip().startswith('C  Colours:')
      and R.screen(mo).splitlines()[7].strip().startswith('L  Library devices:'), R.screen(mo).splitlines()[3:10])
mi = run([('key', 'i')])                    # I (M6 part 9): asks for the picture, offering the device
check('I asks for a picture: "Picture: DSK1." on row 6, the hint on row 11', R.screen(mi).splitlines()[6].strip().startswith('Picture: DSK1.')
      and 'NAME_P and NAME_C' in R.screen(mi).splitlines()[11], R.screen(mi).splitlines()[5:12])
me = run([('key', 'e')])                    # E with no compile yet
check('E with no error says so: "No error in the last compile."', R.screen(me).splitlines()[11].strip() == 'No error in the last compile.',
      R.screen(me).splitlines()[10:12])
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
