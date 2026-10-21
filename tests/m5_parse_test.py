#!/usr/bin/env python3
"""m5_parse_test.py - the workbench's parser against tools/txc/parser.py.

Each program of the corpus, wrapped to 80 columns, is read, lexed and
parsed on the workbench in the simulator; its tree (SAMS from page 96, in
tools/txc/dump.py's encoding) must equal the Python parser's, byte for
byte.  Malformed programs must give the same error on the same line.

  python3 tests/m5_parse_test.py [lib|samples|tests|errors|small|all]"""
import os, sys, tempfile, glob, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'm5p'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
S, build, keys_for = g['S'], g['build'], g['keys_for']
from txa_wrap import wrap_text
from txc.parser import parse
from txc.lexer import TxaError
from txc import dump
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:2500]))
    fails += 0 if ok else 1

cart, _ = build.workbench_cart()
sy = build.symbols(os.path.join(build.B, 'wbench.equ'))

def run_ti(text, max_steps=600_000_000):
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, 'DSK1'))
    open(os.path.join(d, 'DSK1', 'SOURCE'), 'w', encoding='latin-1').write(text if text.endswith('\n') else text + '\n')
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    queue = list(keys_for('dsk1.source'))
    steps = hold = free = 0; p0 = None
    while steps < max_steps:
        pc = cpu.pc
        if pc == sy['PARSE'] and p0 is None: p0 = steps
        if pc == sy['WK1'] and not hold and steps >= free:
            if not queue:
                break
            m.held = queue.pop(0); hold = steps + 12_000
        if hold and steps >= hold:
            m.held = None; hold = 0; free = steps + 12_000
        cpu.step(); steps += 1
    return m, steps - (p0 or steps)

def ti_tree(m):
    n = m.rw(sy['WBTREE'])
    return bytes(m.ams[96 * 4096: 96 * 4096 + n])

def diff(want, got):
    a, b = dump.tree_text(want).split('\n'), dump.tree_text(got).split('\n')
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return '\n'.join([f'line {i}:'] + [f'  py: {l}' for l in a[max(0, i - 6):i + 3]] + [f'  ti: {l}' for l in b[max(0, i - 6):i + 3]])
    return f'lengths {len(want)} / {len(got)} bytes, {len(a)} / {len(b)} lines'

def corpus(which):
    if which == 'small':
        return [('small', 'ROUTINE Foo a\n  IF a > 1 AND NOT x.N\n    PRINT (the) a, "hi"\n  ELSE\n    y = -5 + f(a, 2)\n  END\n  GIVE self light NOT open\nEND\n'
                 'OBJECT Lamp "brass lamp" IN Hall\n  NAME "brass" "lamp"\n  HAS light\n  BEFORE\n    Take, Give: RETURN TRUE\n    Drop:\n      PRINT "No."\n  END\n  WEIGHT 3 >1F\nEND\n'
                 'VERB "take" "get"\n  multi -> Take\n  noun "from" noun=IsC -> Remove REVERSE\nEND\nARRAY a = 1, -32768, \'lamp\'\nGLOBAL g = ##Take\n')]
    files = []
    if which in ('lib', 'all'): files += sorted(glob.glob(os.path.join(ROOT, 'lib/*.txa')))
    if which in ('samples', 'all'): files += [os.path.join(ROOT, 'samples/lamplight.txa'), os.path.join(ROOT, 'demos/m2demo.txa')]
    if which in ('tests', 'all'): files += sorted(glob.glob(os.path.join(ROOT, 'tests/txa/m[23]/*.txa')))
    return [(os.path.relpath(f, ROOT), wrap_text(open(f).read())) for f in files]

which = sys.argv[1] if len(sys.argv) > 1 else 'small'
if which != 'errors':
    for name, text in corpus(which):
        want = dump.tree_bytes(parse(text))
        m, insns = run_ti(text)
        done = m.rw(sy['WBDONE'])
        got = ti_tree(m) if done == 3 else b''
        check(f'{name}: tree identical ({len(want)} bytes; parsing {insns / 1e6:.1f}M instructions, ~{insns / 3e5:.0f} s on a TI)',
              got == want, diff(want, got) if done == 3 else f'not parsed: done={done} error={m.rw(sy["WBERR"])} line={m.rw(sy["WBERRL"])}')

CODES = [('expected the end of the line', 11), ('expected a declaration', 12), ('cannot start a declaration', 13),
         ('VERB has no END', 17), ('has no END', 14), ('expected a property, HAS', 15), ('expected a grammar token', 18),
         ('missing END', 19), ('WRITE needs', 20), ('only a variable', 21), ('this line computes', 22),
         ('comparisons cannot be chained', 23), ('a call takes at most', 24), ('number 32768 is larger', 25),
         ('expected a value', 26), ('expected an action name', 27)]
def code_of(msg):
    if re.fullmatch(r'expected an attribute', msg): return 16
    for k, c in CODES:
        if k in msg: return c
    return 10 if msg.startswith('expected ') else -1
if which in ('errors', 'all'):
    cases = ['ROUTINE F\n  x = 1 2\nEND\n', '42\n', 'END\n', 'OBJECT A "a"\n  HAS light\n', 'OBJECT A "a"\n  42\nEND\n',
             'OBJECT A "a"\n  HAS\nEND\n', 'VERB "x"\n  noun -> X\n', 'VERB "x"\n  42 -> X\nEND\n', 'ROUTINE F\n  x = 1\n',
             'ROUTINE F\n  WRITE\nEND\n', 'ROUTINE F\n  3 = 4\nEND\n', 'ROUTINE F\n  1 + 2\nEND\n', 'ROUTINE F\n  x = a < b < c\nEND\n',
             'ROUTINE F\n  f(1,2,3,4,5,6,7,8)\nEND\n', 'ROUTINE F\n  x = 32768\nEND\n', 'ROUTINE F\n  x = )\nEND\n',
             'VERB "x"\n  noun -> 42\nEND\n', 'GLOBAL\n', 'ROUTINE F\n  IF x\n    y = 1\n  ELSE\n    y = 2\nEND\n']
    for text in cases:
        try:
            parse(text); pmsg, pline = '(none)', 0
        except TxaError as e:
            pmsg, pline = e.msg, e.line
        m, _ = run_ti(text)
        tcode, tline = m.rw(sy['WBERR']), m.rw(sy['WBERRL'])
        check(f'error: {pmsg[:50]!r} line {pline}', (tcode, tline) == (code_of(pmsg), pline), f'ti code {tcode} line {tline}; expected {code_of(pmsg)} line {pline}')
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
