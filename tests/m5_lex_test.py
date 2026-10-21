#!/usr/bin/env python3
"""m5_lex_test.py - the workbench's lexer against tools/txc/lexer.py.

Each program of the corpus, wrapped to 80 columns, is put in the
simulator's DSK1 as a DIS/VAR 80 file; the workbench reads and lexes it;
its token stream (SAMS from page 64) is read back and written in the
canonical dump form (tools/txc/dump.py), which must equal the Python
lexer's dump exactly.  Small malformed files must give the same error on
the same line.  The instructions the lexing took are counted (a real TI
runs about 300,000 a second).

  python3 tests/m5_lex_test.py [lib|samples|tests|errors|all]"""
import os, sys, tempfile, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'm5x'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
S, build, R, keys_for = g['S'], g['build'], g['R'], g['keys_for']
from txa_wrap import wrap_text
from txc.lexer import tokenize, TxaError
from txc import dump
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:1500]))
    fails += 0 if ok else 1

cart, _ = build.workbench_cart()
sy = build.symbols(os.path.join(build.B, 'wbench.equ'))
KIND = {1: 'NUM', 2: 'STR', 3: 'ID', 4: 'KW', 5: 'ACT', 6: 'DICT', 7: 'SYM', 8: 'NL', 9: 'EOF'}

def run_ti(text, max_steps=400_000_000):
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, 'DSK1'))
    open(os.path.join(d, 'DSK1', 'SOURCE'), 'w', encoding='latin-1').write(text if text.endswith('\n') else text + '\n')
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    queue = [k for k in keys_for('dsk1.source')]   # (lower case: the kernel's KEYGET stops at SHIFT, and gives capitals anyway)
    steps = hold = free = 0; lex0 = lex1 = None
    while steps < max_steps:
        pc = cpu.pc
        if pc == sy['LEXALL'] and lex0 is None: lex0 = steps
        if pc == sy['WK1'] and not hold and steps >= free:
            if not queue:
                break
            m.held = queue.pop(0); hold = steps + 12_000
        if hold and steps >= hold:
            m.held = None; hold = 0; free = steps + 12_000
        cpu.step(); steps += 1
    return m, steps - (lex0 or steps)

def ti_dump(m):
    n = m.rw(sy['LXTCNT'])
    data = m.ams[64 * 4096:]
    out, p = [], 0
    for _ in range(n):
        k = data[p]; line = (data[p + 1] << 8) | data[p + 2]; ln = (data[p + 3] << 8) | data[p + 4]
        txt = bytes(data[p + 5:p + 5 + ln]).decode('latin-1'); p += 5 + ln
        kind = KIND.get(k, f'?{k}')
        if kind == 'NUM':
            v = (data[p] << 8) | data[p + 1]; p += 2
            if txt.startswith('>') and v > 0x7FFF:
                v -= 0x10000
            out.append(f'{line} NUM {v}')
        elif kind in ('NL', 'EOF'):
            out.append(f'{line} {kind}')
        elif kind == 'STR':
            out.append(f'{line} STR {dump.esc(txt)}')
        else:
            out.append(f'{line} {kind} {txt}')
    return '\n'.join(out) + '\n'

def first_diff(a, b):
    al, bl = a.split('\n'), b.split('\n')
    for i, (x, y) in enumerate(zip(al, bl)):
        if x != y:
            return f'token {i}: python {x!r} / ti {y!r}'
    return f'lengths {len(al)} / {len(bl)}'

def corpus(which):
    files = []
    if which in ('lib', 'all'):
        files += sorted(glob.glob(os.path.join(ROOT, 'lib/*.txa')))
    if which in ('samples', 'all'):
        files += [os.path.join(ROOT, 'samples/lamplight.txa'), os.path.join(ROOT, 'demos/m2demo.txa')]
    if which in ('tests', 'all'):
        files += sorted(glob.glob(os.path.join(ROOT, 'tests/txa/m[23]/*.txa')))
    return files

which = sys.argv[1] if len(sys.argv) > 1 else 'samples'
total_insns = total_bytes = 0
for f in corpus(which):
    text = wrap_text(open(f).read())
    want = dump.tokens(tokenize(text, os.path.basename(f)))
    m, insns = run_ti(text)
    got = ti_dump(m) if m.rw(sy['WBDONE']) == 2 else f'(not lexed: done={m.rw(sy["WBDONE"])} error={m.rw(sy["WBERR"])} line={m.rw(sy["WBERRL"])})'
    total_insns += insns; total_bytes += len(text)
    check(f'{os.path.relpath(f, ROOT)}: {want.count(chr(10))} tokens identical ({insns / 1e6:.1f}M instructions, ~{insns / 3e5:.0f} s on a TI)',
          got == want, first_diff(want, got))
if total_bytes:
    print(f'      lexing speed: {total_insns / total_bytes:.0f} instructions a source byte')

if which in ('errors', 'all'):
    cases = [('PRINT "never\nclosed\n', 1, 1), ("x = 'lamp\n", 2, 1), ("x = ''\n", 2, 1), ('ok\nx = ## Take\n', 3, 2),
             ('x = 40000\n', 4, 1), ('x = >1FFFF\n', 5, 1), ('ok\n\nx = 3 @ 4\n', 6, 3), ('x = 32768\n', 0, 0)]
    for text, code, line in cases:
        try:
            tokenize(text); pcode, pline = 0, 0
        except TxaError as e:
            pcode, pline = code, e.line
        m, _ = run_ti(text)
        tcode, tline = m.rw(sy['WBERR']), m.rw(sy['WBERRL'])
        check(f'error case {text.splitlines()[-1][:20]!r}: python line {pline}, ti code {tcode} line {tline}',
              (tcode, tline) == (pcode, pline) and pcode == code and pline == line, (tcode, tline, pcode, pline))
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
