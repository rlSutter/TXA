#!/usr/bin/env python3
"""docs_test.py - the generated manuals cannot drift from the source (M7):
docs/TECHNICAL-REFERENCE.md is exactly what tools/gendocs.py makes now,
and it names every opcode, every header field and every overlay.

  python3 tests/docs_test.py"""
import os, sys, subprocess, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); os.chdir(ROOT)
from txc import opcodes as O
import gendocs, build
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:600]))
    fails += 0 if ok else 1
text = open('docs/TECHNICAL-REFERENCE.md').read()
check('docs/TECHNICAL-REFERENCE.md is what gendocs.py makes from the source now (run it if not)', text == gendocs.generate())
missing = [n for _, n, *_ in O.OPS if f'| `{n}` |' not in text]
check(f'every opcode has its row ({len(O.OPS)})', not missing, missing)
missing = [n for n in O.HDR if f'| `{n}` |' not in text]
check(f'every header field has its row ({len(O.HDR)})', not missing, missing)
sy = build.symbols(os.path.join(build.B, 'wbench.equ'))
n = 1
while f'OV{n}END' in sy:
    n += 1
rows = re.findall(r'^\| (\d+) \| [^|]+ \| ', text.split('## 5. The workbench')[1].split('## 6.')[0], re.M)
check(f'every overlay the build knows ({n - 1}) has its row', sorted(map(int, rows)) == list(range(1, n)), rows)
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
