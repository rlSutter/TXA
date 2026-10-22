#!/usr/bin/env python3
"""m5_sema_test.py - the workbench's meaning stage against tools/txc/sema.py.

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
  errors   malformed programs give the same first error, on the same
           line of the same file

  python3 tests/m5_sema_test.py [decls|meaning|errors|all] [quick]

(meaning checks symbols and objects together, from one run each.)"""
import os, sys, tempfile, glob, re
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

def run_ti(d, main_name, max_steps=2_000_000_000):
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    queue = list(keys_for('dsk1.' + main_name.lower()))
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
    s = Sema([os.path.dirname(path)])
    decls = []
    s.load(path, decls); s.replace_and_extend(decls); s.declare_all(decls); s.build_objects(decls)
    return s.p
def first_diff(a, b):
    al, bl = a.split('\n'), b.split('\n')
    for i, (x, y) in enumerate(zip(al, bl)):
        if x != y:
            return f'line {i + 1}:\n  py: {x}\n  ti: {y}'
    return f'lengths {len(al)} / {len(bl)} lines'

def corpus(quick):
    lamp = [('samples/lamplight.txa', LIB)]
    if quick:
        return lamp
    progs = lamp + [('demos/m1demo.txa', LIB), ('demos/m2demo.txa', LIB), ('tests/txa/m2/m2game.txa', LIB)]
    progs += [(f, LIB) for f in sorted(glob.glob(os.path.join(ROOT, 'tests/txa/m3/world*.txa')))]
    progs += [(os.path.join('tests/txa', f), TLIB) for f in ('run1.txa', 'dynmap.txa', 'spec_cellar.txa')]
    return progs

args = sys.argv[1:]
which = args[0] if args else 'all'
quick = 'quick' in args
if which in ('decls', 'all'):
    for rel, libdir in corpus(quick):
        path = os.path.join(ROOT, rel)
        name = os.path.splitext(os.path.basename(path))[0]
        d, ppath = stage(open(path).read(), name, libdir)
        want = py_decls(ppath, libdir)
        m, steps = run_ti(d, name)
        done, err = m.rw(sy['WBDONE']), m.rw(sy['WBERR'])
        got = ti_decls(m) if done >= 4 else []
        detail = f'not loaded: done={done} stage={m.rw(sy["WBSTAG"])} error={err} line={m.rw(sy["WBERRL"])}' if done < 4 else \
            next((f'decl {i}: py {a} ti {b}' for i, (a, b) in enumerate(zip(want, got)) if a != b), f'counts {len(want)} / {len(got)}')
        check(f'{rel}: {len(want)} declarations in load order, {len(ti_files(m))} files ({steps / 1e6:.0f}M instructions, ~{steps / 3e5:.0f} s on a TI)',
              got == want, detail)

if which in ('meaning', 'all'):
    for rel, libdir in corpus(quick):
        path = os.path.join(ROOT, rel)
        name = os.path.splitext(os.path.basename(path))[0]
        d, ppath = stage(open(path).read(), name, libdir)
        p = py_meaning(ppath)
        m, steps = run_ti(d, name)
        done = m.rw(sy['WBDONE'])
        why = f'not done: done={done} stage={m.rw(sy["WBSTAG"])} error={m.rw(sy["WBERR"])} line={m.rw(sy["WBERRL"])}'
        want, got = dump.symbols(p), (ti_symbols(m) if done >= 4 else '')
        check(f'{rel}: symbols identical ({len(p.symbols)}; {steps / 1e6:.0f}M instructions in all)', got == want, first_diff(want, got) if done >= 4 else why)
        want, got = dump.objects(p), (ti_objects(m) if done >= 4 else '')
        check(f'{rel}: objects identical ({len(p.objects)})', got == want, first_diff(want, got) if done >= 4 else why)

if which in ('errors', 'all'):
    # (file the error is in, line) must match sema.py's
    cases = [('missing include', 'INCLUDE "DSK1.NOSUCH"\nROUTINE Main\nEND\n', None, 40)]
    for label, text, libdir, code in cases:
        d, ppath = stage(text, 'GAME', libdir)
        try:
            s = Sema([d]); s.load(ppath, []); pe = None
        except TxaError as e:
            pe = e
        m, _ = run_ti(d, 'GAME')
        files = ti_files(m) + ['?'] * 16
        got = (m.rw(sy['WBERR']), files[m.rw(sy['WBERRF'])], m.rw(sy['WBERRL']))
        want = (code, os.path.splitext(pe.file)[0].upper(), pe.line) if pe else None
        check(f'error: {label}: {pe.msg if pe else "(none)"}', got == want, f'ti {got}, expected {want}')

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
