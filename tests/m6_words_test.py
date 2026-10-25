#!/usr/bin/env python3
"""m6_words_test.py - the lexer's and the parser's errors in plain words
(M6 part 6, decision D6): every error case of m5_lex_test and m5_parse_test,
compiled as a whole program by the simulated TI, shows "GAME line N: " and
the Python compiler's own message on rows 6 and 7.  (The meaning, code and
link errors are m5_sema_test's errors stage.)

  python3 tests/m6_words_test.py"""
import os, sys, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); os.chdir(ROOT)
src = open('tests/m5_sema_test.py').read()
g = {'__file__': os.path.join(ROOT, 'tests/m5_sema_test.py'), '__name__': 'words'}
sys.argv = ['words', 'none']
try:
    exec(compile(src, 'm5', 'exec'), g)
except SystemExit:
    pass
Sema, TxaError, stage, run_ti, R = g['Sema'], g['TxaError'], g['stage'], g['run_ti'], g['R']
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:600]))
    fails += 0 if ok else 1

def cases_of(path, marker):
    t = open(path).read()
    i = t.index(marker); j = t.index(']\n', i) + 1
    return eval(t[t.index('[', i):j])
lex = [c[0] for c in cases_of('tests/m5_lex_test.py', '    cases = [(')]
par = cases_of('tests/m5_parse_test.py', "    cases = ['")
for text in lex + par:
    d, ppath = stage(text, 'GAME', None)
    try:
        Sema([d]).run(ppath); pe = None
    except TxaError as e:
        pe = e
    if not pe:
        continue                                # (a lexer case that is no error)
    m, _ = run_ti(d, 'GAME')
    scr = R.screen(m).splitlines()
    ti_text = (scr[6].ljust(80)[1:80] + scr[7].ljust(80)[1:80]).rstrip()
    want = f'GAME line {pe.line}: {pe.msg}'
    check(f'words: {want}', ti_text == want, f'ti {ti_text!r}')
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
