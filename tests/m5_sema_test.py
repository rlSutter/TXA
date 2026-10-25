#!/usr/bin/env python3
"""m5_sema_test.py - the workbench's meaning stage and code generator against
tools/txc/sema.py and codegen.py.

Each program of the corpus and its library, wrapped to 80 columns, goes
in the simulator's DSK1 as DIS/VAR 80 files (the main file under its own
base name, the library files as STDLIB, LIBDEFS ...); the workbench
compiles it from the prompt, following its INCLUDEs.  What the TI built
in SAMS is read back and compared with what sema.py builds from the same
wrapped files:

  decls    the declaration index: every declaration's node type, file
           and line, in load() order (INCLUDEs followed in place)
  symbols  the symbol table after REPLACE, EXTEND and declare_all, with
           the constants worked out (dump.symbols)
  objects  every object after build_objects: tree, attributes,
           properties in order, NAME words (dump.objects)
  tables   after the whole pass: actions, the sorted dictionary with each
           word's VERB, VERBTAB, GRAMTAB, ACTSUB, DICTVERB (dump.tables),
           and the warnings (dump.warnings)
  code     the code generator (M5 part 5): every routine's bytecode, in
           output order, with its fixups, and the strings (dump.code)
  link     the linker (M5 part 6): the whole story image, byte for byte,
           and the 4K PROGRAM files it is written to (dump: the bytes)
  date     the build date's prompt: nothing taken but a date (yymmdd,
           month 01-12, day 01-31), the header gets it, the next compile
           offers it again
  errors   malformed programs give the same first error, on the same
           line of the same file, one for each of sema.py's errors (but
           'more than 1000 objects'); and the warnings

  python3 tests/m5_sema_test.py [decls|meaning|code|link|date|errors|all] [quick] [only=name ...]

(meaning checks symbols, objects and tables together, from one run each.)"""
import os, sys, tempfile, glob, re, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
src = open(os.path.join(ROOT, 'tests/m2_engine_test.py')).read()
g = {'__file__': os.path.join(ROOT, 'tests/m2_engine_test.py'), '__name__': 'm5s'}
exec(compile(src[:src.index('img, info = compile_file')], 'm2', 'exec'), g)
S, build, R, keys_for = g['S'], g['build'], g['R'], g['keys_for']
from txa_wrap import wrap_text
from txc.sema import Sema
from txc.lexer import TxaError
from txc import dump
from txc.codegen import Gen, link
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:2500]))
    fails += 0 if ok else 1

cart, _ = build.workbench_cart()
sy = build.symbols(os.path.join(build.B, 'wbench.equ'))
LIB, TLIB = os.path.join(ROOT, 'lib'), os.path.join(ROOT, 'tests/txa/lib')

def stage(main_text, main_name, libdir, extra=()):
    """A directory with the program's files, wrapped: for Python (name.txa)
    and for the TI (DSK1/NAME).  Returns (dir, python path)."""
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, 'DSK1'))
    files = [(main_name, main_text)]
    if libdir:
        files += [(os.path.splitext(os.path.basename(f))[0], open(f).read()) for f in sorted(glob.glob(os.path.join(libdir, '*.txa')))]
    files += list(extra)
    for name, text in files:
        w = wrap_text(text)
        w = w if w.endswith('\n') else w + '\n'
        open(os.path.join(d, name.lower() + '.txa'), 'w', encoding='latin-1').write(w)
        open(os.path.join(d, 'DSK1', name.upper()), 'w', encoding='latin-1').write(w)
    return d, os.path.join(d, main_name.lower() + '.txa')

DATE = datetime.date(2026, 10, 22)              # the build date both compilers use

def run_ti(d, main_name, max_steps=2_000_000_000):
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    # the menu (M6): P, the name, ENTER takes the date offered, ENTER the prefix, C compiles
    queue = keys_for('p')[:-1] + keys_for('dsk1.' + main_name.lower()) + keys_for('') + keys_for('') + keys_for('c')[:-1]
    steps = hold = free = 0
    dated = False
    while steps < max_steps:
        pc = cpu.pc
        if pc == sy['WK1'] and not dated:            # (the TI has no clock: the date the prompt offers, WDATE)
            for i, c in enumerate(DATE.strftime('%y%m%d').encode()):
                m.wb(sy['WDATE'] + i, c)
            dated = True
        if pc == sy['WK1'] and not hold and steps >= free:
            if not queue:
                break
            m.held = queue.pop(0); hold = steps + 12_000
        if hold and steps >= hold:
            m.held = None; hold = 0; free = steps + 12_000
        cpu.step(); steps += 1
    m.cpu = cpu                                 # (for diagnostics: where it stopped)
    return m, steps

def ti_files(m):
    out = []
    for i in range(m.rw(sy['NF'])):
        a = sy['FTAB'] + i * sy['FTSIZ']
        n = m.rb(a)
        out.append(bytes(m.rb(a + 1 + k) for k in range(n)).decode('latin-1'))
    return out

def ti_decls(m):
    files, out = ti_files(m), []
    for i in range(m.rw(sy['DXN'])):
        p = sy['DXPG'] * 4096 + i * 8
        e = m.ams[p:p + 8]
        out.append((e[5], files[e[4] & 0x7F], (e[6] << 8) | e[7]))
    return out

def py_decls(path, libdir):
    s = Sema([os.path.dirname(path)])
    decls = []
    s.load(path, decls)
    return [(dump.NODE_ID[type(x)], os.path.splitext(x.file)[0].upper(), x.line) for x in decls]

KINDS = [None, 'constant', 'global', 'array', 'attribute', 'property', 'class', 'object', 'routine', 'picture', 'music', 'sound']
def sw(v):
    return v - 0x10000 if v > 0x7FFF else v
def amw(m, a):
    return (m.ams[a] << 8) | m.ams[a + 1]
def ti_symname(m, i):
    r = sy['SYMPG'] * 4096 + i * 32
    n, pg, of = m.ams[r + 3], amw(m, r + 10), amw(m, r + 12)
    return bytes(m.ams[pg * 4096 + of: pg * 4096 + of + n]).decode('latin-1')
def ti_symbols(m):
    out = []
    for i in range(1, m.rw(sy['SN']) + 1):
        r = sy['SYMPG'] * 4096 + i * 32
        k = KINDS[m.ams[r + 2]] if m.ams[r + 2] < len(KINDS) else f'?{m.ams[r + 2]}'
        n = '-' if k in ('class', 'routine') else sw(amw(m, r + 4))
        out.append(f'{ti_symname(m, i)} {k} {n}')
    return '\n'.join(out) + '\n'
def ti_word(m, w):
    a = sy['DICPG'] * 4096 + w * 16
    return bytes(m.ams[a + 3: a + 3 + m.ams[a + 2]]).decode('latin-1')
def ti_tree_str(m, pg, of):
    a = pg * 4096 + of
    assert m.ams[a] == 4, 'not a string'
    n = amw(m, a + 1)
    return bytes(m.ams[a + 3: a + 3 + n]).decode('latin-1')
def ti_objects(m):
    H = lambda c: sy['HPPG'] * 4096 + c * 4
    out = []
    for o in range(1, m.rw(sy['ON']) + 1):
        r = sy['OBJPG'] * 4096 + o * 32
        sym, kind = amw(m, r), amw(m, r + 2)
        par, ch, sib = (amw(m, r + 4 + 2 * k) for k in range(3))
        attrs = [n for n in range(48) if m.ams[r + 22 + n // 8] & (0x80 >> (n % 8))]
        names, c = [], amw(m, r + 14)
        while c:
            names.append(ti_word(m, amw(m, H(c) + 2))); c = amw(m, H(c))
        props, c = [], amw(m, r + 10)
        while c:
            e = H(c); num, pk = amw(m, e + 2), amw(m, e + 4)
            if pk == 1:
                vals, v = [], amw(m, e + 8)
                for _ in range(amw(m, e + 6)):
                    a = H(v); vk, v1, v2 = amw(m, a), amw(m, a + 2), amw(m, a + 4)
                    vals.append({1: lambda: f'num:{sw(v1)}', 2: lambda: 'str:' + dump.esc(ti_tree_str(m, v1, v2)), 3: lambda: f'obj:{v1}',
                                 4: lambda: f'routine:{ti_symname(m, v1)}', 5: lambda: f'dict:{ti_word(m, v1)}'}.get(vk, lambda: f'?{vk}')())
                    v += 2
                props.append(f'{num}=' + ','.join(vals))
            elif pk == 2:
                pg, of = amw(m, e + 8), amw(m, e + 10)
                props.append(f'{num}=block@{amw(m, pg * 4096 + of + 2)}')
            elif pk == 3:
                props.append(f'{num}=' + ','.join('dict:' + w for w in names))
            else:
                props.append(f'{num}=?{pk}')
            c = amw(m, e)
        out.append(f'{o} {ti_symname(m, sym)} {"OBJECT" if kind == 1 else "ROOM" if kind == 2 else kind} {par} {ch} {sib} '
                   f'attrs {" ".join(str(a) for a in attrs)} | props {" ".join(props)} | names {" ".join(names)}')
    return '\n'.join(out) + '\n'
def py_meaning(path):
    return Sema([os.path.dirname(path)]).run(path)
def ti_tables(m):
    W = lambda pg, i: amw(m, pg * 4096 + 2 * i)
    acts, subs = [], []
    for a in range(m.rw(sy['ACN'])):
        r = sy['ACTPG'] * 4096 + (a // 56) * 4096 + (a % 56) * 72
        acts.append(ti_tree_str(m, amw(m, r + 68), amw(m, r + 70)))
        subs.append('routine:' + ti_symname(m, amw(m, r + 66)))
    dn = m.rw(sy['DN'])
    words = []
    for place in range(1, dn + 1):
        w = W(sy['DSPG'], place)
        words.append(f'{dump.esc(ti_word(m, w))}/{W(sy["DVBPG"], w)}')
    vt = ' '.join(f'num:{W(sy["VTBPG"], i)}' for i in range(m.rw(sy['VN']) + 1))
    g = []
    for i in range(m.rw(sy['GRN'])):
        a = sy['GRMPG'] * 4096 + i * 4
        k, v = amw(m, a), amw(m, a + 2)
        g.append(f'num:{sw(v)}' if k == 1 else f'routine:{ti_symname(m, v)}' if k == 4 else f'?{k}:{v}')
    dv = ' '.join(f'num:{W(sy["DVTPG"], i)}' for i in range(dn + 1))
    return '\n'.join(['actions ' + ' '.join(acts), 'dictionary ' + ' '.join(words), 'VERBTAB ' + vt,
                      'GRAMTAB ' + ' '.join(g), 'ACTSUB ' + (' '.join(subs) or 'num:0'), 'DICTVERB ' + dv]) + '\n'
def ti_warnings(m):
    files, out = ti_files(m), []
    for i in range(m.rw(sy['WN'])):
        a = sy['WRNPG'] * 4096 + i * 6
        out.append(f'{amw(m, a)} {files[amw(m, a + 2)]} {amw(m, a + 4)}')
    return '\n'.join(out) + '\n'
def ti_code(m):
    """The TI's code, decoded as dump.code writes Python's."""
    props = {}
    for i in range(1, m.rw(sy['SN']) + 1):
        r = sy['SYMPG'] * 4096 + i * 32
        if m.ams[r + 2] == 5:
            props[amw(m, r + 4)] = ti_symname(m, i)
    def cbyte(a):
        blk = a >> 12
        return m.ams[(blk if blk < 2 else blk + 2) * 4096 + (a & 0xFFF)]
    fixes = {}
    for f in range(m.rw(sy['FXN'])):
        a = sy['FIXPG'] * 4096 + f * 8
        fixes.setdefault(amw(m, a), {})[amw(m, a + 2)] = (amw(m, a + 4), amw(m, a + 6))
    out = []
    for r in range(m.rw(sy['RN'])):
        a = sy['RDIRPG'] * 4096 + r * 8
        kind, prop, key, start, n = m.ams[a], m.ams[a + 1], amw(m, a + 2), amw(m, a + 4), amw(m, a + 6)
        if kind == 1:
            name = ti_symname(m, key)
        else:
            o = sy['OBJPG'] * 4096 + key * 32
            name = ti_symname(m, amw(m, o)) + '.' + props.get(prop, f'?{prop}')
        fx, parts, i = fixes.get(r, {}), [], 0
        while i < n:
            if i in fx:
                k, v = fx[i]
                parts.append(f'R:{ti_symname(m, v)}' if k == 1 else f'S:{v}'); i += 2
            else:
                parts.append(f'{cbyte(start + i):02X}'); i += 1
        out.append(f'{name} ' + ' '.join(parts))
    for i in range(m.rw(sy['STRN'])):
        a = sy['STRPG'] * 4096 + 512 + i * 8
        out.append(f'S{i} ' + dump.esc(ti_tree_str(m, amw(m, a + 2), amw(m, a + 4))))
    return '\n'.join(out) + '\n'

def meaning_done(m):
    """The meaning stage finished: everything did, or only the code
    generator found an error (83 on: a program without Main)."""
    return m.rw(sy['WBDONE']) >= 4 or m.rw(sy['WBERR']) >= 83

def first_diff(a, b):
    al, bl = a.split('\n'), b.split('\n')
    for i, (x, y) in enumerate(zip(al, bl)):
        if x != y:
            return f'line {i + 1}:\n  py: {x}\n  ti: {y}'
    return f'lengths {len(al)} / {len(bl)} lines'

def corpus(quick):
    sel = [a[5:] for a in sys.argv[1:] if a.startswith('only=')]
    progs = corpus_all(quick)
    return [x for x in progs if any(k in x[0] for k in sel)] if sel else progs

def corpus_all(quick):
    lamp = [('samples/lamplight.txa', LIB)]
    if quick:
        return lamp
    progs = lamp + [('demos/m2demo.txa', LIB), ('tests/txa/m2/m2game.txa', LIB)]
    progs += [(f, LIB) for f in sorted(glob.glob(os.path.join(ROOT, 'tests/txa/m3/world*.txa')))]
    progs += [(os.path.join('tests/txa', f), TLIB) for f in ('run1.txa', 'dynmap.txa', 'spec_cellar.txa')]
    return progs

args = sys.argv[1:]
which = args[0] if args else 'all'
quick = 'quick' in args
if which in ('decls', 'all'):
    for rel, libdir in corpus(quick):
        path = os.path.join(ROOT, rel)
        name = os.path.splitext(os.path.basename(path))[0].replace('_', '')   # (the harness cannot type _)
        d, ppath = stage(open(path).read(), name, libdir)
        want = py_decls(ppath, libdir)
        m, steps = run_ti(d, name)
        done, err = (4 if meaning_done(m) else m.rw(sy['WBDONE'])), m.rw(sy['WBERR'])
        got = ti_decls(m) if done >= 4 else []
        detail = f'not loaded: done={done} stage={m.rw(sy["WBSTAG"])} error={err} line={m.rw(sy["WBERRL"])}' if done < 4 else \
            next((f'decl {i}: py {a} ti {b}' for i, (a, b) in enumerate(zip(want, got)) if a != b), f'counts {len(want)} / {len(got)}')
        check(f'{rel}: {len(want)} declarations in load order, {len(ti_files(m))} files ({steps / 1e6:.0f}M instructions, ~{steps / 3e5:.0f} s on a TI)',
              got == want, detail)

if which in ('meaning', 'all'):
    for rel, libdir in corpus(quick):
        path = os.path.join(ROOT, rel)
        name = os.path.splitext(os.path.basename(path))[0].replace('_', '')   # (the harness cannot type _)
        d, ppath = stage(open(path).read(), name, libdir)
        p = py_meaning(ppath)
        m, steps = run_ti(d, name)
        done = 4 if meaning_done(m) else m.rw(sy['WBDONE'])
        why = f'not done: done={done} stage={m.rw(sy["WBSTAG"])} error={m.rw(sy["WBERR"])} line={m.rw(sy["WBERRL"])}'
        want, got = dump.symbols(p), (ti_symbols(m) if done >= 4 else '')
        check(f'{rel}: symbols identical ({len(p.symbols)}; {steps / 1e6:.0f}M instructions in all)', got == want, first_diff(want, got) if done >= 4 else why)
        want, got = dump.objects(p), (ti_objects(m) if done >= 4 else '')
        check(f'{rel}: objects identical ({len(p.objects)})', got == want, first_diff(want, got) if done >= 4 else why)
        want, got = dump.tables(p), (ti_tables(m) if done >= 4 else '')
        check(f'{rel}: actions, dictionary, grammar tables identical ({len(p.actions)} actions, {len(p.dictionary)} words, '
              f'{len(p.sym("GRAMTAB").gen_values)} GRAMTAB)', got == want, first_diff(want, got) if done >= 4 else why)
        want, got = dump.warnings(p), (ti_warnings(m) if done >= 4 else '')
        check(f'{rel}: warnings identical ({len(p.warnings)})', got == want, first_diff(want, got) if done >= 4 else why)

CODES = [('is a built-in function', 41), ('is already declared', 42), ('more than 240 globals', 43),
         ('more than 48 attributes', 44), ('more than 63 properties', 45), ('more than 1000 objects', 46), ('is defined in terms of itself', 47), ('must be worked out when compiling', 48),
         ('division by zero', 49), ('is not a class', 50), ('includes itself', 51), ('nothing can be IN it', 52),
         ('is given two parents', 53), ('unknown attribute', 54), ('a class cannot say what its objects are IN', 55),
         ('(declare it with PROPERTY)', 56), ('unknown name', 57), ('SELF has no value outside a routine', 58),
         ('a property value must be', 59), ('a dictionary word cannot be empty', 60), ('is inside itself', 61),
         ('but this file has no ROUTINE', 62), ('no VERB has that word', 63), ('has no routine', 64),
         ('is already a word of another VERB', 65), ('is not a grammar token', 66), ('is not a routine', 67),
         ('a grammar line takes at most two objects', 68), ('is declared twice in this routine', 69),
         ('parameters and locals in one routine', 70), ('must be a LOCAL', 71), ('on its own does nothing', 72),
         ('it cannot be assigned to', 73), ('only an array element can be assigned to', 74),
         ('an array element takes one index', 75), ('and has no value here', 76), ('needs an attribute name after it', 77),
         ('unknown property', 78), ('the second argument of', 80), (' argument', 79),
         ('cannot be called', 82), ('cannot find the file', 40), ('there is no ROUTINE Main', 83),
         ('rule cases need the library', 84), ('cannot compile Case', 85), ('a property holds at most 255', 87),
         ('the dynamic area is', 88), ('the tables before the routines pass 64K', 89), ('the story is', 90)]
def code_of(msg):
    for k, c in CODES:
        if k in msg:
            return c
    return -1
def names(n, stem, kw):
    """n names declared with kw, ten to a line (DV80 lines are short)."""
    sep = ', ' if kw.strip() == 'LOCAL' else ' '
    return ''.join(f'{kw}' + sep.join(f'{stem}{i}' for i in range(k, min(n, k + 10))) + '\n' for k in range(0, n, 10))
ERRS = [
    ('a built-in name declared', 'GLOBAL random\n'),
    ('declared twice', 'GLOBAL a\nGLOBAL A\n'),
    ('241 globals', ''.join(f'GLOBAL g{i}\n' for i in range(241))),
    ('49 attributes', names(49, 'a', 'ATTRIBUTE ')),
    ('63 properties', names(63, 'P', 'PROPERTY ')),
    ('a constant defined by itself', 'CONSTANT A = B\nCONSTANT B = A + 1\n'),
    ('a constant not worked out', 'GLOBAL g\nCONSTANT A = g\n'),
    ('division by zero', 'CONSTANT A = 1 / (2 - 2)\n'),
    ('not a class', 'GLOBAL g\nOBJECT O "o"\n  CLASS g\nEND\n'),
    ('a class including itself', 'CLASS A\n  CLASS B\nEND\nCLASS B\n  CLASS A\nEND\nOBJECT O "o"\n  CLASS A\nEND\n'),
    ('IN a global', 'GLOBAL g\nOBJECT O "o" IN g\nEND\n'),
    ('two parents', 'OBJECT P "p"\nEND\nOBJECT Q "q"\nEND\nOBJECT O "o" IN P\n  IN Q\nEND\n'),
    ('unknown attribute (HAS)', 'OBJECT O "o"\n  HAS shiny\nEND\n'),
    ('a class with IN', 'OBJECT P "p"\nEND\nCLASS C\n  IN P\nEND\nOBJECT O "o"\n  CLASS C\nEND\n'),
    ('unknown property in a body', 'OBJECT O "o"\n  COLOUR 3\nEND\n'),
    ('unknown name as a value', 'PROPERTY P\nOBJECT O "o"\n  P nowhere\nEND\n'),
    ('SELF as a value', 'PROPERTY P\nOBJECT O "o"\n  P SELF\nEND\n'),
    ('a global as a value', 'PROPERTY P\nGLOBAL g\nOBJECT O "o"\n  P g\nEND\n'),
    ('a NAME with a space', 'OBJECT O "o"\n  NAME "two words"\nEND\n'),
    ('inside itself', 'OBJECT A "a" IN B\nEND\nOBJECT B "b" IN A\nEND\n'),
    ('REPLACE without the routine', 'REPLACE Foo\n'),
    ('EXTEND an unknown verb', 'EXTEND "zap"\n  noun -> Zap\nEND\n'),
    ('an action without its routine', 'VERB "zap"\n  noun -> Zap\nEND\n'),
    ('a word of two verbs', 'ROUTINE ZapSub\nEND\nVERB "zap"\n  noun -> Zap\nEND\nVERB "Zap"\n  noun -> Zap\nEND\n'),
    ('not a grammar token', 'ROUTINE ZapSub\nEND\nVERB "zap"\n  thing -> Zap\nEND\n'),
    ('a filter that is not a routine', 'ROUTINE ZapSub\nEND\nGLOBAL g\nVERB "zap"\n  noun=g -> Zap\nEND\n'),
    ('three objects in a line', 'ROUTINE ZapSub\nEND\nVERB "zap"\n  noun noun noun -> Zap\nEND\n'),
    ('a local twice', 'ROUTINE F\n  LOCAL a\n  IF a\n    LOCAL a\n  END\nEND\n'),
    ('17 locals', 'ROUTINE F\n' + names(17, 'v', '  LOCAL ') + 'END\n'),
    ('a loop variable not local', 'ROUTINE F\n  FOR EACH x IN 1\n  END\nEND\n'),
    ('a global on its own', 'GLOBAL g\nROUTINE F\n  g\nEND\n'),
    ('a built-in on its own, arguments missing', 'ROUTINE F\n  STATUS\nEND\n'),
    ('assigning to a constant', 'CONSTANT C = 1\nROUTINE F\n  C = 2\nEND\n'),
    ('assigning to a call', 'ROUTINE G\nEND\nROUTINE F\n  G(1) = 2\nEND\n'),
    ('an element with two indexes', 'ARRAY a 3\nROUTINE F\n  a(1, 2) = 2\nEND\n'),
    ('an attribute as a value', 'ATTRIBUTE shiny\nROUTINE F\n  RETURN shiny\nEND\n'),
    ('HAS without an attribute name', 'GLOBAL g\nROUTINE F\n  RETURN g HAS 3\nEND\n'),
    ('HAS an unknown attribute', 'GLOBAL g\nROUTINE F\n  RETURN g HAS shiny\nEND\n'),
    ('an unknown property after a dot', 'GLOBAL g\nROUTINE F\n  RETURN g.COLOUR\nEND\n'),
    ('a built-in with too few arguments', 'ROUTINE F\n  RETURN RANDOM()\nEND\n'),
    ('a routine with too many arguments', 'ROUTINE G a\nEND\nROUTINE F\n  G(1, 2)\nEND\n'),
    ('PROPLEN without a property', 'ROUTINE F\n  RETURN PROPLEN(1, 2)\nEND\n'),
    ('calling a global', 'GLOBAL g\nROUTINE F\n  g(1)\nEND\n'),
    ('an unknown name in a routine', 'ROUTINE F\n  RETURN nowhere\nEND\n'),
    ('a GIVE of an unknown attribute', 'OBJECT O "o"\nEND\nROUTINE F\n  GIVE O shiny\nEND\n'),
    ('no ROUTINE Main', 'ROUTINE Start\nEND\n'),
    ('rule cases without the global "action"', 'ROUTINE Main\nEND\nROUTINE TakeSub\nEND\nPROPERTY BEFORE\n'
     'VERB "take"\n  noun -> Take\nEND\nOBJECT O "o"\n  BEFORE\n    Take: RETURN TRUE\n  END\nEND\n'),
    ('division by zero in a routine', 'ROUTINE Main\n  RETURN 3 / (1 - 1)\nEND\n'),
    ('a global starting with an unknown name', 'ROUTINE Main\nEND\nGLOBAL g = nowhere\n'),
    ('a global starting with SELF', 'ROUTINE Main\nEND\nGLOBAL g = SELF\n'),
    ('a global starting with another global', 'ROUTINE Main\nEND\nGLOBAL h\nGLOBAL g = h\n'),
    ('an array value that is not known', 'ROUTINE Main\nEND\nARRAY a = 1, nowhere\n'),
    ('an array value divided by zero', 'ROUTINE Main\nEND\nARRAY a = 1, 2 / 0\n'),
    ('an error in an included file', 'GLOBAL g\nINCLUDE "DSK1.MORE"\n', [('MORE', 'GLOBAL h\nGLOBAL H\n')]),
    ('a bad token in lines EXTENDed from another file', 'ROUTINE ZapSub\nEND\nVERB "zap"\n  noun -> Zap\nEND\nINCLUDE "DSK1.MORE"\n',
     [('MORE', 'EXTEND "zap"\n  thing -> Zap\nEND\n')]),
]
if which in ('code', 'all'):
    for rel, libdir in corpus(quick):
        path = os.path.join(ROOT, rel)
        name = os.path.splitext(os.path.basename(path))[0].replace('_', '')   # (the harness cannot type _)
        d, ppath = stage(open(path).read(), name, libdir)
        p = py_meaning(ppath)
        g = Gen(p)
        try:
            g.generate()
        except TxaError as e:                  # (spec_cellar has no Main: the same error)
            m, steps = run_ti(d, name)
            check(f'{rel}: code generation fails as in Python: {e.msg}',
                  (m.rw(sy['WBERR']), m.rw(sy['WBERRL'])) == (code_of(e.msg), e.line),
                  f'ti error {m.rw(sy["WBERR"])} line {m.rw(sy["WBERRL"])}')
            continue
        m, steps = run_ti(d, name)
        done = m.rw(sy['WBDONE'])
        why = f'not done: done={done} stage={m.rw(sy["WBSTAG"])} error={m.rw(sy["WBERR"])} line={m.rw(sy["WBERRL"])}'
        want, got = dump.code(g), (ti_code(m) if done >= 4 else '')
        check(f'{rel}: code identical ({len(g.codes)} routines, {sum(len(c.b) for c in g.codes)} bytes, {len(g.strings)} strings; '
              f'{steps / 1e6:.0f}M instructions in all, ~{steps / 3e5:.0f} s on a TI)', got == want, first_diff(want, got) if done >= 4 else why)

if which in ('link', 'all'):
    for rel, libdir in corpus(quick):
        path = os.path.join(ROOT, rel)
        name = os.path.splitext(os.path.basename(path))[0].replace('_', '')   # (the harness cannot type _)
        d, ppath = stage(open(path).read(), name, libdir)
        p = py_meaning(ppath)
        g = Gen(p)
        try:
            g.generate()
        except TxaError:
            continue                           # (no Main: the code stage checks its error)
        img, _ = link(p, g, name.upper(), 1, DATE)
        m, steps = run_ti(d, name)
        done = m.rw(sy['WBDONE'])
        why = f'not done: done={done} stage={m.rw(sy["WBSTAG"])} error={m.rw(sy["WBERR"])} line={m.rw(sy["WBERRL"])}'
        base = m.rw(sy['IMGPG']) * 4096
        ti = bytes(m.ams[base: base + len(img)]) if done >= 4 else b''
        diff = next((i for i in range(min(len(img), len(ti))) if img[i] != ti[i]), None)
        check(f'{rel}: story image identical ({len(img)} bytes; {steps / 1e6:.0f}M instructions in all, ~{steps / 3e5:.0f} s on a TI)',
              ti == img, why if done < 4 else f'first difference at {diff}: python {img[diff]:02X} ti {ti[diff]:02X}' if diff is not None else 'lengths differ')
        nfiles = (len(img) + 4095) // 4096
        scr = R.screen(m).splitlines()
        check(f'{rel}: the screen says "Story: {len(img)} bytes in {nfiles} files on disk."',
              f'Story: {len(img)} bytes in {nfiles} files on disk.' in scr[7] and not scr[5].strip(), f'{scr[5]!r} {scr[7]!r}')
        prefix = name.upper()[:6]
        files = sorted(glob.glob(os.path.join(d, 'DSK1', prefix + 'S[0-9][0-9]')))
        joined = b''.join(open(f, 'rb').read() for f in files)
        want = [f'{prefix}S{i + 1:02d}' for i in range((len(img) + 4095) // 4096)]
        check(f'{rel}: written as {len(files)} PROGRAM files, {prefix}S01.., together the image',
              joined == img and [os.path.basename(f) for f in files] == want, f'files {[os.path.basename(f) for f in files]}, {len(joined)} bytes')

if which in ('date', 'all'):
    def run_keys(d, lines, max_steps=200_000_000):
        """The workbench from power-up, typing lines (each with ENTER), no
        date set beforehand; returns the machine and the screen at the end."""
        m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
        cpu.pc = m.rw(m.rw(0x6006) + 2)
        # a line is typed with ENTER after it; ('key', c) is the one key c (the menu's)
        queue = [k for ln in lines for k in (keys_for(ln[1])[:-1] if isinstance(ln, tuple) else keys_for(ln))]
        steps = hold = free = 0
        while steps < max_steps:
            pc = cpu.pc
            if pc == sy['WK1'] and not hold and steps >= free:
                if not queue:
                    break
                m.held = queue.pop(0); hold = steps + 12_000
            if hold and steps >= hold:
                m.held = None; hold = 0; free = steps + 12_000
            cpu.step(); steps += 1
        m.waiting = steps < max_steps            # (stopped at a key wait, not still running)
        return m, R.screen(m).splitlines()
    def cpu_waits(m):
        return getattr(m, 'waiting', False)
    path = os.path.join(ROOT, 'tests/txa/run1.txa')
    d, ppath = stage(open(path).read(), 'run1', TLIB)
    # no date yet: ENTER alone, then month 13, are refused; a rub-out; then a date
    P, C = ('key', 'p'), ('key', 'c')
    m, scr = run_keys(d, [P, 'dsk1.run1', '', '261322'])
    check('date: the prompt asks for the build date', 'Build date (yymmdd):' in scr[3], scr[3])
    check('date: ENTER without a date, or month 13, compiles nothing (and the prompt still takes keys)',
          m.rw(sy['WBDONE']) < 4 and '261322' in scr[3] and cpu_waits(m), scr[3])
    m, scr = run_keys(d, [P, 'dsk1.run1', '', '261322', '261023\b2', '', C])
    base = m.rw(sy['IMGPG']) * 4096
    check('date: a date (with a rub-out) compiles, and the header has it',
          m.rw(sy['WBDONE']) >= 4 and bytes(m.ams[base + 38: base + 44]) == b'261022', f'{bytes(m.ams[base + 38: base + 44])} {scr[3]}')
    m, scr = run_keys(d, [P, 'dsk1.run1', '261022', '', C, P, 'dsk1.run1'])
    check('date: the next compile offers the last date', '261022' in scr[3], scr[3])
    m, scr = run_keys(d, [P, 'dsk1.run1', '261022', '', C, P, 'dsk1.run1', '', '', C])
    check('date: ENTER takes it', m.rw(sy['WBDONE']) >= 4 and bytes(m.ams[m.rw(sy['IMGPG']) * 4096 + 38:][:6]) == b'261022', scr[3])

if which in ('errors', 'all'):
    WORDS = []
    cases = [('missing include', 'INCLUDE "DSK1.NOSUCH"\nROUTINE Main\nEND\n')] + ERRS
    for case in cases:
        label, text = case[0], case[1]
        d, ppath = stage(text, 'GAME', None, case[2] if len(case) > 2 else ())
        try:
            pp_ = Sema([d]).run(ppath); gg = Gen(pp_); gg.generate(); link(pp_, gg, 'GAME', 1, DATE); pe = None
        except TxaError as e:
            pe = e
        m, _ = run_ti(d, 'GAME')
        files, f = ti_files(m), m.rw(sy['WBERRF'])
        got = (m.rw(sy['WBERR']), files[f] if f < len(files) else '?', m.rw(sy['WBERRL']))   # (255: the whole program)
        pfile = '?' if pe and pe.file == '<program>' else os.path.splitext(pe.file)[0].upper() if pe else '?'
        want = (code_of(pe.msg), pfile, pe.line) if pe else (0, '?', 0)
        check(f'error: {label}: {pe.msg if pe else "(none)"}', got == want, f'ti {got}, expected {want}')
        if pe:                                  # M6 part 6: the TI words it as Python does
            import re as _re
            scr = R.screen(m).splitlines()
            ti_text = (scr[6][1:80] + scr[7][1:80]).rstrip()
            msg = _re.sub(r'([\w-]+)\.txa', lambda mm: mm.group(1).upper(), pe.msg)
            want_text = (msg if pfile == '?' else f'{pfile} line {pe.line}: {msg}')
            WORDS.append((label, ti_text == want_text))
            check(f'words: {want_text}', ti_text == want_text, f'ti {ti_text!r}')
    text = 'ROUTINE F\n  RETURN SELF\nEND\nOBJECT O "o"\n  NAME "extraordinarily"\nEND\nOBJECT Q "q"\nEND\nROOM R "r"\nEND\n'
    d, ppath = stage(text, 'GAME', None)
    p = Sema([d]).run(ppath)
    m, _ = run_ti(d, 'GAME')
    check(f'warnings: SELF outside a property, a long NAME word, an OBJECT without NAME words ({len(p.warnings)})',
          ti_warnings(m) == dump.warnings(p), f'ti {ti_warnings(m)!r}, expected {dump.warnings(p)!r}')

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
