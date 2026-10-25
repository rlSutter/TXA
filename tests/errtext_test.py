#!/usr/bin/env python3
"""errtext_test.py - the message templates (tools/txc/errtext.py) against
the Python compiler's own messages: every error case of m5_sema_test's
errors stage, and the missing INCLUDE, must match its code's template with
the fields as wildcards.  Quick: no simulator.

  python3 tests/errtext_test.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); os.chdir(ROOT)
from txc import errtext
src = open('tests/m5_sema_test.py').read()
g = {'__file__': os.path.join(ROOT, 'tests/m5_sema_test.py'), '__name__': 'et'}
sys.argv = ['et', 'none']                       # no stage: just its definitions
try:
    exec(compile(src, 'm5', 'exec'), g)
except SystemExit:
    pass
Sema, Gen, link, TxaError, stage, code_of, DATE = g['Sema'], g['Gen'], g['link'], g['TxaError'], g['stage'], g['code_of'], g['DATE']
fails = 0
cases = [('missing include', 'INCLUDE "DSK1.NOSUCH"\nROUTINE Main\nEND\n')] + g['ERRS']
for case in cases:
    label, text = case[0], case[1]
    d, ppath = stage(text, 'GAME', None, case[2] if len(case) > 2 else ())
    try:
        p = Sema([d]).run(ppath); gg = Gen(p); gg.generate(); link(p, gg, 'GAME', 1, DATE); pe = None
    except TxaError as e:
        pe = e
    if not pe:
        print(f'FAIL  {label}: no error'); fails += 1; continue
    c = code_of(pe.msg)
    ok = c in errtext.TEMPLATES and errtext.pattern(c).match(pe.msg)
    print(('PASS  ' if ok else 'FAIL  ') + f'{c}: {pe.msg}' + ('' if ok else f'\n      template: {errtext.TEMPLATES.get(c)!r}'))
    fails += 0 if ok else 1
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
