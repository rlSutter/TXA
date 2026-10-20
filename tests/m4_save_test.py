#!/usr/bin/env python3
"""m4_save_test.py - SAVE and RESTORE, and the save file's portability.

Lamplight is played on the Python VM and on the TI engine (the simulator
with its disk controller, files in a folder): take the lantern, SAVE,
drop it, RESTORE, look.  The transcripts must match; the save file the
TI wrote must be byte for byte the Python VM's (portability rule 6); each
VM must restore the other's file; a damaged file must fail and change
nothing.

  python3 tests/m4_save_test.py"""
import os, sys, tempfile, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'm4'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
play = g['play']
from txc.codegen import compile_file
from txc import txvm
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:2000]))
    fails += 0 if ok else 1

img, _ = compile_file(os.path.join(ROOT, 'samples/lamplight.txa'), [os.path.join(ROOT, 'lib')], title='LAMPLIGHT')
cmds = ['n', 'take lantern', 'save', '', 'drop lantern', 'i', 'restore', '', 'i', 'look', 'q', 'y']

pydir = tempfile.mkdtemp(); vm = txvm.VM(img, cmds); vm.save_dir = pydir
want = vm.run()
check('Python: saved, dropped, restored: the lantern is back', 'Saved.' in want and 'Restored.' in want
      and want.count('  a storm lantern') == 1 and 'You are empty-handed.' in want)
pyfile = open(os.path.join(pydir, 'save1'), 'rb').read()

tidir = tempfile.mkdtemp()
got, m, why, _ = play(img, cmds, disk=tidir)
i = next((k for k in range(min(len(got), len(want))) if got[k] != want[k]), min(len(got), len(want)))
check('TI: the same transcript as the Python VM', got == want and why == 'halt',
      f'{why} at {i}: python {want[max(0,i-80):i+60]!r}\n  ti {got[max(0,i-80):i+60]!r}')
tipath = os.path.join(tidir, 'DSK1', 'SAVE1')
tifile = open(tipath, 'rb').read() if os.path.exists(tipath) else b''
check(f'the save files are identical ({len(pyfile)} bytes): one format on every engine', tifile == pyfile,
      f'ti {len(tifile)} bytes, python {len(pyfile)}; first difference at '
      f'{next((k for k in range(min(len(tifile), len(pyfile))) if tifile[k] != pyfile[k]), "end")}')

# each restores the other's file: start a new game, restore, look
cmds2 = ['restore', 'kit', 'i', 'q', 'y']
d = tempfile.mkdtemp(); open(os.path.join(d, 'kit'), 'wb').write(tifile)
vm2 = txvm.VM(img, cmds2); vm2.save_dir = d; out2 = vm2.run()
check('the Python VM restores the TI\'s file', 'Restored.' in out2 and '  a storm lantern' in out2, out2[-300:])
d2 = tempfile.mkdtemp(); os.makedirs(os.path.join(d2, 'DSK1')); open(os.path.join(d2, 'DSK1', 'KIT'), 'wb').write(pyfile)
want3 = txvm.VM(img, cmds2, ) ; want3.save_dir = d; want3 = want3.run()
got3, m3, why3, _ = play(img, cmds2, disk=d2)
check('the TI restores the Python VM\'s file', got3 == want3 and why3 == 'halt', got3[-300:])

# a damaged file: one byte changed
bad = bytearray(pyfile); bad[30] ^= 0x55
d3 = tempfile.mkdtemp(); os.makedirs(os.path.join(d3, 'DSK1')); open(os.path.join(d3, 'DSK1', 'KIT'), 'wb').write(bad)
open(os.path.join(d3, 'kit'), 'wb').write(bad)
vm4 = txvm.VM(img, ['take lantern', 'restore', 'kit', 'i', 'q', 'y']); vm4.save_dir = d3; want4 = vm4.run()
check('Python: a damaged file fails and changes nothing', 'Restore failed.' in want4 and '  a storm lantern' not in want4.split('Restore failed.')[1][:0] , want4[-200:])
got4, _, why4, _ = play(img, ['n', 'take lantern', 'restore', 'kit', 'i', 'q', 'y'], disk=d3)
check('TI: a damaged file fails and changes nothing', 'Restore failed.' in got4 and '  a storm lantern' in got4.split('Restore failed.')[1], got4[-300:])

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
