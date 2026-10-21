#!/usr/bin/env python3
"""txc_wrap_test.py - D1 at scale: every program in the corpus, wrapped to
80 columns by tools/txa_wrap.py (long strings continued on the next line,
long comments moved above), compiles to exactly the same story image, and
no wrapped line is longer than 80 characters (DV80 files on the TI).

  python3 tests/txc_wrap_test.py"""
import os, sys, tempfile, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from txa_wrap import wrap_text
from txc.codegen import compile_file
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:800]))
    fails += 0 if ok else 1

def wrapped_dir(src_dir, d):
    os.makedirs(d, exist_ok=True); longest = 0
    for f in glob.glob(os.path.join(src_dir, '*.txa')):
        w = wrap_text(open(f).read())
        longest = max([longest] + [len(l) for l in w.split('\n')])
        open(os.path.join(d, os.path.basename(f)), 'w').write(w)
    return longest

tmp = tempfile.mkdtemp()
longest = wrapped_dir(os.path.join(ROOT, 'lib'), os.path.join(tmp, 'lib'))
check('the standard library wraps to 80 columns', longest <= 80, longest)
programs = [('samples', 'lamplight.txa', 'lib')] + [(os.path.relpath(os.path.dirname(f), ROOT), os.path.basename(f), 'lib')
            for f in sorted(glob.glob(os.path.join(ROOT, 'tests/txa/m[23]/*.txa')))]
for sub, name, lib in programs:
    d = os.path.join(tmp, sub)
    lng = wrapped_dir(os.path.join(ROOT, sub), d)
    a, _ = compile_file(os.path.join(ROOT, sub, name), [os.path.join(ROOT, lib)])
    b, _ = compile_file(os.path.join(d, name), [os.path.join(tmp, lib)])
    check(f'{sub}/{name}: wrapped (longest line {lng}), the same image ({len(a)} bytes)', a == b and lng <= 80)
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
