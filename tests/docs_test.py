#!/usr/bin/env python3
"""docs_test.py - the generated manuals cannot drift from the source (M7):
docs/TECHNICAL-REFERENCE.md and docs/LIBRARY-REFERENCE.md are exactly what
tools/gendocs.py makes now; every opcode, header field, overlay, library
attribute, property and action is there.

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
lib = open('docs/LIBRARY-REFERENCE.md').read()
check('docs/LIBRARY-REFERENCE.md is what gendocs.py makes from the library now', lib == gendocs.generate_library())
nodesc = [n for n, d in gendocs.lib_props() if not d]
check(f'every library property has a description ({len(gendocs.lib_props())})', not nodesc, nodesc)
check(f'every library attribute has a description ({len(gendocs.lib_attrs())})', all(a in gendocs.ATTR_DESC for a in gendocs.lib_attrs()))
acts = {a for a, _, _ in gendocs.lib_verbs()}
check(f'every action the grammar names ({len(acts)}) has a row', all(f'`{a}`' in lib for a in acts))
tut = open('docs/TUTORIAL.md').read()
check('docs/TUTORIAL.md is what gendocs.py makes from the chapters now (its code and transcript included)', tut == gendocs.generate_tutorial())
eng = open('docs/ENGINE-GUIDE.md').read()
check('docs/ENGINE-GUIDE.md is what gendocs.py makes now', eng == gendocs.generate_engine_guide())
named = set(gendocs.IO_OPS) | set(gendocs.OPTIONAL_OPS)
core_io = [n for c, n, *_ in O.OPS if c >= 0x48 and n not in named]
check('every input/output and system opcode (>48 on) is in the guide\'s tables', not core_io, core_io)
card = open('docs/PLAYERS-CARD.md').read()
check('docs/PLAYERS-CARD.md is what the game writer\'s card generator makes for Lamplight now', card == gendocs.generate_card())
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
