"""codegen.py - from a checked Program to a TXA story image.

Two parts.  The code generator turns every routine (and every property
routine) into bytecode, with labels for jumps and fixups for packed
addresses of routines and strings not yet placed.  The linker lays out
the image (opcodes.py's header and table formats), chooses the text
substitution table, packs every string, places routines and strings on
4-byte boundaries and resolves the fixups.

Return conventions (Inform's, so Inform habits carry over):
 - a ROUTINE that runs off its end returns TRUE;
 - a property routine (DESC ... END, BEFORE ... END) that runs off its
   end returns FALSE, and so does a rule case that runs off its end:
   "carry on with the action".

The text substitution table (spec: Text compression): strings are cut
into tokens, each a run of letters plus one following space if there is
one ("the ", "door", "You ").  Each token is scored (length - 1) x
occurrences; the 128 best with a score above 0, ties broken by the
token's bytes, become codes >80->FF.  Encoding cuts a string into the
same tokens and replaces those in the table.  Both compilers do exactly
this, so both produce the same image.
"""
import datetime, re
from . import ast as A
from .lexer import TxaError
from .opcodes import BY_NAME, HDR, HEADER_SIZE, MAGIC, FORMAT_VERSION, OBJ_ENTRY, PROP_STR, PROP_ROUTINE, PROP_VALUES

MAX_IMAGE = 256 * 1024
TOKEN = re.compile(r'[A-Za-z]+ ?|[^A-Za-z]')


def wrap(v):
    v &= 0xFFFF
    return v - 0x10000 if v > 0x7FFF else v


class Code:
    """One routine's bytecode under construction."""
    def __init__(self, name, nlocals):
        self.name = name
        self.b = bytearray([nlocals])
        self.labels = {}
        self.jumps = []           # (position of the offset, label)
        self.fixups = []          # (position, ('routine', name) | ('str', text))
        self.nlab = 0

    def label(self):
        self.nlab += 1
        return self.nlab

    def here(self, lab):
        self.labels[lab] = len(self.b)

    def op(self, name, *args):
        code, _, operands, _, _ = BY_NAME[name]
        self.b.append(code)
        for kind, a in zip(operands, args):
            if kind == 'b':
                self.b.append(a & 0xFF)
            elif kind == 'w':
                self.b += (a & 0xFFFF).to_bytes(2, 'big')
            elif kind == 'j':
                self.jumps.append((len(self.b), a)); self.b += b'\0\0'
            elif kind == 'p':
                self.fixups.append((len(self.b), a)); self.b += b'\0\0'

    def resolve_jumps(self):
        for pos, lab in self.jumps:
            off = self.labels[lab] - (pos + 2)
            self.b[pos:pos + 2] = (off & 0xFFFF).to_bytes(2, 'big')


class Gen:
    def __init__(self, prog):
        self.p = prog
        self.codes = []           # Code, in output order
        self.strings = []         # every string, in first-use order
        self.string_set = set()
        self.anon = 0

    def err(self, node, msg):
        raise TxaError(node.file, node.line, msg)

    def string(self, s):
        if s not in self.string_set:
            self.string_set.add(s); self.strings.append(s)
        return ('str', s)

    def var_number(self, name, scope):
        u = name.upper()
        if u in scope:
            return scope.index(u)
        s = self.p.sym(name)
        return 16 + s.number

    # ---- routines --------------------------------------------------------
    def routine(self, name, params, body, locals_, falls_off, cases=False):
        c = Code(name, len(locals_))
        self.cur, self.scope = c, locals_
        if cases:
            self.case_body(body)
        else:
            self.stmts(body)
        c.op('RTRUE' if falls_off else 'RFALSE')
        c.resolve_jumps()
        self.codes.append(c)
        return name

    def case_body(self, body):
        """A rule block: statements before the first case run every time;
        each case tests the action number against its labels."""
        c = self.cur
        action = self.p.sym('action')
        if any(isinstance(x, A.Case) for x in body) and (not action or action.kind != 'global'):
            self.err(body[0], 'rule cases need the library\'s global "action"')
        for item in body:
            if not isinstance(item, A.Case):
                self.stmt(item); continue
            nxt, hit = c.label(), c.label()
            for i, a in enumerate(item.actions):
                n = [x.upper() for x in self.p.actions].index(a.upper())
                c.op('LOAD', 16 + action.number); self.push_num(n); c.op('EQ')
                if i < len(item.actions) - 1:
                    c.op('JNZ', hit)
                else:
                    c.op('JZ', nxt)
            c.here(hit)
            self.stmts(item.body)
            c.op('RFALSE')
            c.here(nxt)

    def stmts(self, body):
        for s in body:
            self.stmt(s)

    def stmt(self, s):
        c = self.cur
        if isinstance(s, A.Local):
            return
        if isinstance(s, A.Assign):
            t = s.target
            if isinstance(t, A.Name):
                self.expr(s.value); c.op('STORE', self.var_number(t.id, self.scope))
            elif isinstance(t, A.PropRef):
                self.expr(t.obj); self.expr(s.value)
                c.op('PUTPROP', self.prop_number(t.prop), self.value_kind(s.value))
            else:
                arr = self.p.sym(t.func.id)
                self.expr(t.args[0]); self.expr(s.value); c.op('ASTORE', arr.number)
        elif isinstance(s, A.ExprStmt):
            self.expr(s.expr); c.op('POP')
        elif isinstance(s, A.If):
            end = c.label()
            for cond, body in s.arms:
                nxt = c.label()
                self.expr(cond); c.op('JZ', nxt)
                self.stmts(body); c.op('JMP', end)
                c.here(nxt)
            if s.orelse:
                self.stmts(s.orelse)
            c.here(end)
        elif isinstance(s, A.While):
            top, end = c.label(), c.label()
            c.here(top); self.expr(s.cond); c.op('JZ', end)
            self.stmts(s.body); c.op('JMP', top); c.here(end)
        elif isinstance(s, A.ForEach):
            v = self.var_number(s.var, self.scope); top, end = c.label(), c.label()
            self.expr(s.parent); c.op('CHILD'); c.op('STORE', v)
            c.here(top); c.op('LOAD', v); c.op('JZ', end)
            self.stmts(s.body)
            c.op('LOAD', v); c.op('SIBLING'); c.op('STORE', v); c.op('JMP', top)
            c.here(end)
        elif isinstance(s, A.Print):
            for it in s.items:
                e = it.expr
                if it.form is None and isinstance(e, A.Str):
                    c.op('PRINTS', self.string(e.value))
                elif it.form in ('the', 'The', 'a', 'A', 'an', 'An'):
                    self.expr(e); c.op('PRINTA', {'the': 0, 'The': 1, 'a': 2, 'an': 2, 'A': 3, 'An': 3}[it.form])
                elif it.form == 'name':
                    self.expr(e); c.op('PRINTO')
                elif it.form == 'char':
                    self.expr(e); c.op('PRINTC')
                elif it.form == 'string':
                    self.expr(e); c.op('PRINTV')
                else:                               # a number, or (number)
                    self.expr(e); c.op('PRINTN')
            if s.newline:
                c.op('NEWLINE')
        elif isinstance(s, A.Move):
            self.expr(s.obj); self.expr(s.dest); c.op('MOVE')
        elif isinstance(s, A.Remove):
            self.expr(s.obj); c.op('REMOVE')
        elif isinstance(s, A.Give):
            self.expr(s.obj)
            for i, (name, on) in enumerate(s.attrs):
                if i < len(s.attrs) - 1:
                    c.op('DUP')
                c.op('SETATTR' if on else 'CLRATTR', self.p.sym(name).number)
        elif isinstance(s, A.Return):
            v = None if s.value is None else self.p_fold(s.value)
            if s.value is None or v == 1:
                c.op('RTRUE')
            elif v == 0:
                c.op('RFALSE')
            else:
                self.expr(s.value); c.op('RET')
        elif isinstance(s, A.PicStmt):
            self.expr(s.value); c.op('PICTURE')
        else:
            self.err(s, f'cannot compile {type(s).__name__}')    # pragma: no cover

    def value_kind(self, e):
        """The property kind a value gets when assigned: a string literal is
        a string, a routine's name a routine, anything else a value.  (A
        routine or string held in a variable is not known to be one when
        compiling, and is stored as a value.)"""
        if isinstance(e, A.Str):
            return PROP_STR
        if isinstance(e, A.Name) and e.id.upper() not in self.scope:
            s = self.p.sym(e.id)
            if s and s.kind == 'routine':
                return PROP_ROUTINE
        return PROP_VALUES

    def p_fold(self, e):
        from .sema import Sema
        sm = Sema.__new__(Sema); sm.p = self.p
        return sm.fold(e)

    def prop_number(self, name):
        return self.p.sym(name).number

    def push_num(self, v):
        c = self.cur; v = wrap(v)
        if v == 0:
            c.op('PUSH0')
        elif v == 1:
            c.op('PUSH1')
        elif -128 <= v <= 127:
            c.op('PUSHB', v)
        else:
            c.op('PUSHW', v)

    def expr(self, e):
        c = self.cur
        v = self.p_fold(e)
        if v is not None:
            return self.push_num(v)
        if isinstance(e, A.ActionRef):
            return self.push_num([x.upper() for x in self.p.actions].index(e.name.upper()))
        if isinstance(e, A.DictWord):
            return self.push_num(self.p.dictnum[e.word[:12]])
        if isinstance(e, A.Str):
            c.op('PUSHW', 0); c.fixups.append((len(c.b) - 2, self.string(e.value)))
        elif isinstance(e, A.Const):
            c.op('LOADSELF')                          # TRUE/FALSE/NOTHING folded above
        elif isinstance(e, A.Name):
            u = e.id.upper()
            if u in self.scope:
                return c.op('LOAD', self.scope.index(u))
            s = self.p.sym(e.id)
            if s.kind == 'global':
                c.op('LOAD', 16 + s.number)
            elif s.kind in ('object', 'picture', 'array', 'music', 'sound'):
                self.push_num(s.number)
            elif s.kind == 'routine':
                c.op('PUSHW', 0); c.fixups.append((len(c.b) - 2, ('routine', s.name)))
            else:
                self.err(e, f'{e.id} has no value here')
        elif isinstance(e, A.Unary):
            self.expr(e.arg); c.op('NEG' if e.op == '-' else 'NOT')
        elif isinstance(e, A.Binary):
            if e.op in ('AND', 'OR'):
                done, short = c.label(), c.label()
                self.expr(e.left); c.op('JZ' if e.op == 'AND' else 'JNZ', short)
                self.expr(e.right); c.op('JZ' if e.op == 'AND' else 'JNZ', short)
                if e.op == 'AND':
                    c.op('PUSH1'); c.op('JMP', done); c.here(short); c.op('PUSH0')
                else:
                    c.op('PUSH0'); c.op('JMP', done); c.here(short); c.op('PUSH1')
                c.here(done)
            elif e.op in ('HAS', 'HASNT'):
                self.expr(e.left); c.op('HASATTR', self.p.sym(e.right.id).number)
                if e.op == 'HASNT':
                    c.op('NOT')
            else:
                self.expr(e.left); self.expr(e.right)
                op = {'+': 'ADD', '-': 'SUB', '*': 'MUL', '/': 'DIV', 'MOD': 'MOD', '=': 'EQ', '<>': 'NE',
                      '<': 'LT', '>': 'GT', '<=': 'LE', '>=': 'GE', 'IN': 'IN', 'NOTIN': 'IN'}[e.op]
                c.op(op)
                if e.op == 'NOTIN':
                    c.op('NOT')
        elif isinstance(e, A.PropRef):
            self.expr(e.obj); c.op('GETPROP', self.prop_number(e.prop))
        elif isinstance(e, A.Call):
            f = e.func
            if isinstance(f, A.PropRef):              # obj.prop(args)
                self.expr(f.obj)
                if not e.args:                        # obj.prop(): print or run (Inform's PrintOrRun)
                    return c.op('RUNPROP', self.prop_number(f.prop))
                for a in e.args:
                    self.expr(a)
                return c.op('CALLPROP', self.prop_number(f.prop), len(e.args))
            u = f.id.upper()
            from .sema import BUILTINS, PROP_ARG
            if u in BUILTINS and u not in self.scope:
                op, _, value = BUILTINS[u]
                if u in PROP_ARG:                      # PROPLEN(o, P), PROPWORD(o, P, i)
                    self.expr(e.args[0])
                    for a in e.args[2:]:
                        self.expr(a)
                    return c.op(op, self.prop_number(e.args[1].id))
                for a in e.args:
                    self.expr(a)
                c.op(op)
                if not value:
                    c.op('PUSH0')
                return
            s = None if u in self.scope else self.p.sym(f.id)
            if s and s.kind == 'array':
                self.expr(e.args[0]); return c.op('ALOAD', s.number)
            for a in e.args:
                self.expr(a)
            if s and s.kind == 'routine':
                c.op('CALL', ('routine', s.name), len(e.args))
            else:                                     # a routine held in a variable
                self.expr(f); c.op('CALLV', len(e.args))
        else:
            self.err(e, f'cannot compile {type(e).__name__}')    # pragma: no cover

    def generate(self):
        p = self.p
        main = p.sym('Main')
        if not main or main.kind != 'routine':
            raise TxaError('<program>', 0, 'there is no ROUTINE Main: the game starts there')
        for r in p.routines:
            self.routine(r.name, r.params, r.body, r.locals, falls_off=True)
        self.proproutines = {}
        for o in p.objects:
            for num, prop in o.props.items():
                if prop[0] == 'routine':
                    self.anon += 1
                    name = f'{o.sym.name}.{p.props[num]}'
                    blk = prop[1]
                    self.routine(name, [], blk.body, blk.locals, falls_off=False, cases=True)
                    self.proproutines[(o.number, num)] = name
        for g in p.globals:                           # strings in initial values
            if isinstance(g.decl.value, A.Str):
                self.string(g.decl.value.value)
        for a in p.arrays:
            if hasattr(a, 'gen_values'):
                continue
            for v in a.decl.values or []:
                if isinstance(v, A.Str):
                    self.string(v.value)
        for o in p.objects:                           # strings the tables need
            if o.short is not None:
                self.string(o.short)
            for prop in o.props.values():
                if prop[0] == 'values':
                    for k, v in prop[1]:
                        if k == 'str':
                            self.string(v)


# ---- text ------------------------------------------------------------------
def tokens(s):
    return TOKEN.findall(s)

def choose_abbrevs(strings):
    count = {}
    for s in strings:
        for t in tokens(s):
            if len(t) > 1:
                count[t] = count.get(t, 0) + 1
    scored = sorted(((len(t) - 1) * n, t) for t, n in count.items())
    best = sorted(scored, key=lambda x: (-x[0], x[1].encode('latin-1')))
    return [t for sc, t in best[:128] if sc > 0]

def encode(s, abbrevs):
    index = {t: i for i, t in enumerate(abbrevs)}
    out = bytearray()
    for t in tokens(s):
        if t in index:
            out.append(0x80 + index[t])
        else:
            for ch in t:
                o = ord(ch)
                if ch == '\n':
                    o = 10
                if not (o == 10 or 32 <= o < 127):
                    o = ord('?')
                out.append(o)
    out.append(0)
    return bytes(out)

def decode(data, pos, abbrevs):
    out = []
    while data[pos]:
        b = data[pos]; pos += 1
        out.append(abbrevs[b - 0x80] if b >= 0x80 else chr(b))
    return ''.join(out)


# ---- the linker ------------------------------------------------------------
class Image:
    def __init__(self):
        self.b = bytearray(HEADER_SIZE)

    def align(self, n):
        while len(self.b) % n:
            self.b.append(0)

    def word(self, v):
        self.b += (v & 0xFFFF).to_bytes(2, 'big')

    def set_word(self, off, v):
        self.b[off:off + 2] = (v & 0xFFFF).to_bytes(2, 'big')

    def set_hdr(self, field, v):
        self.set_word(HDR[field], v)


def link(prog, gen, title='TXA GAME', release=1, date=None):
    p, img = prog, Image()
    fix = []                                          # (offset in image, ('routine'|'str', key))
    def ref(kind, key):
        fix.append((len(img.b), (kind, key))); img.word(0)
    # object table
    img.set_hdr('objects', len(img.b)); img.set_hdr('object_count', len(p.objects))
    obj_at = len(img.b)
    img.b += bytes(OBJ_ENTRY * len(p.objects))
    # property tables
    img.align(2); img.set_hdr('props_start', len(img.b))
    for o in p.objects:
        e = obj_at + (o.number - 1) * OBJ_ENTRY
        img.set_word(e, o.parent); img.set_word(e + 2, o.sibling); img.set_word(e + 4, o.child)
        for a in o.attrs:
            img.b[e + 6 + a // 8] |= 0x80 >> (a % 8)
        img.set_word(e + 12, len(img.b))
        if o.short is not None:
            ref('str', o.short)
        else:
            img.word(0)
        for num in sorted(o.props):
            prop = o.props[num]
            if prop[0] == 'routine':
                img.b += bytes([num | PROP_ROUTINE, 1]); ref('routine', gen.proproutines[(o.number, num)])
                continue
            vals = prop[1]
            if len(vals) == 1 and vals[0][0] == 'str':
                img.b += bytes([num | PROP_STR, 1]); ref('str', vals[0][1]); continue
            if len(vals) == 1 and vals[0][0] == 'routine':
                img.b += bytes([num | PROP_ROUTINE, 1]); ref('routine', vals[0][1]); continue
            if len(vals) > 255:
                raise TxaError(o.sym.decl.file, o.sym.decl.line, 'a property holds at most 255 words')
            img.b += bytes([num | PROP_VALUES, len(vals)])
            for k, v in vals:
                if k in ('str', 'routine'):
                    ref(k, v)
                elif k == 'dict':
                    img.word(p.dictnum[v])
                else:
                    img.word(v)
        img.b.append(0); img.align(2)
    # globals
    img.set_hdr('globals', len(img.b))
    gstart = len(img.b); img.b += bytes(480)
    from .sema import Sema
    sm = Sema.__new__(Sema); sm.p = p
    for g in p.globals:
        if g.decl.value is not None:
            k, v = sm.prop_value(g.decl.value, g.decl)
            if k in ('str', 'routine'):
                fix.append((gstart + 2 * g.number, (k, v)))
            else:
                img.set_word(gstart + 2 * g.number, v)
    # arrays: a directory (count, then offset and length for each), then the data
    img.set_hdr('arrays', len(img.b))
    img.word(len(p.arrays)); dirpos = len(img.b); img.b += bytes(4 * len(p.arrays))
    for a in p.arrays:
        d = a.decl
        if hasattr(a, 'gen_values'):                  # VERBTAB, GRAMTAB, ACTSUB, DICTVERB
            vals = a.gen_values
        else:
            vals = [('num', 0)] * d.size if d.values is None else [sm.prop_value(v, d) for v in d.values]
        img.set_word(dirpos + 4 * a.number, len(img.b)); img.set_word(dirpos + 4 * a.number + 2, len(vals))
        for k, v in vals:
            if k in ('str', 'routine'):
                ref(k, v)
            else:
                img.word(v)
    img.align(2)
    dyn = len(img.b)
    if dyn > 16384:
        raise TxaError('<program>', 0, f'the dynamic area is {dyn} bytes; the limit is 16384 (too many objects or properties)')
    img.set_hdr('dynamic_len', dyn)
    # dictionary: count, then 14-byte entries (12 characters, zero-padded; a flags byte, 1 noun,
    # 2 verb, 4 preposition; the verb's number), sorted: a word's number is its place, from 1
    img.set_hdr('dictionary', len(img.b))
    verbs = {w.lower()[:12] for v in p.verbs for w in v.words}
    preps = {t.value.lower()[:12] for v in p.verbs for gl in v.lines for t in gl.tokens if t.kind == 'word'}
    nouns = {w for o in p.objects for w in o.names}
    words = sorted(p.dictionary, key=lambda w: w.encode('latin-1'))
    assert all(p.dictnum[w] == i + 1 for i, w in enumerate(words))
    img.word(len(words))
    for w in words:
        img.b += w.encode('latin-1').ljust(12, b'\0')
        img.b.append((1 if w in nouns else 0) | (2 if w in verbs else 0) | (4 if w in preps else 0))
        img.b.append(p.verb_of.get(w, 0))
    # grammar: defined in M2 (the parser); an empty table for now
    img.set_hdr('grammar', len(img.b)); img.word(0)
    # actions: count, then each action's routine
    img.set_hdr('actions', len(img.b)); img.word(len(p.actions))
    for a in p.actions:
        ref('routine', p.sym(a + 'Sub').name)
    # text substitutions: 128 offsets (from the table start; 0 = unused), then the words
    abbrevs = choose_abbrevs(gen.strings)
    img.set_hdr('abbrevs', len(img.b)); tab = len(img.b); img.b += bytes(256)
    for i, t in enumerate(abbrevs):
        img.set_word(tab + 2 * i, len(img.b) - tab); img.b += t.encode('latin-1') + b'\0'
    if len(img.b) > 0xFFFF:
        raise TxaError('<program>', 0, 'the tables before the routines pass 64K')
    tables_end = len(img.b)                           # (statistics: tools/txc/stats.py)
    # routines, then strings, each on a 4-byte boundary
    where = {}
    for c in gen.codes:
        img.align(4); where[('routine', c.name)] = len(img.b) // 4
        for pos, key in c.fixups:
            fix.append((len(img.b) + pos, key))
        img.b += c.b
    for s in gen.strings:
        img.align(4); where[('str', s)] = len(img.b) // 4
        img.b += encode(s, abbrevs)
    img.align(4)
    if len(img.b) > MAX_IMAGE:
        raise TxaError('<program>', 0, f'the story is {len(img.b)} bytes; the limit is {MAX_IMAGE}')
    for off, key in fix:
        img.set_word(off, where[key])
    # header
    img.b[0:4] = MAGIC
    img.set_hdr('version', FORMAT_VERSION); img.set_hdr('release', release)
    img.set_hdr('image_len_hi', len(img.b) >> 16); img.set_hdr('image_len_lo', len(img.b))
    img.set_hdr('entry', where[('routine', p.sym('Main').name)])
    date = date or datetime.date.today()
    img.b[HDR['build_date']:HDR['build_date'] + 6] = date.strftime('%y%m%d').encode()
    img.b[HDR['title']:HDR['title'] + 16] = title.upper()[:16].ljust(16).encode('latin-1')
    for field, attr in (('attr_proper', 'proper'), ('attr_plural', 'plural')):
        s = p.sym(attr)
        img.b[HDR[field]] = s.number if s and s.kind == 'attribute' else 255
    img.set_hdr('checksum', sum(img.b[HEADER_SIZE:]) & 0xFFFF)
    return bytes(img.b), {'abbrevs': abbrevs, 'where': where,
                          'stats': {'routines': len(gen.codes), 'strings': len(gen.strings), 'tables_end': tables_end}}


def compile_file(path, libpath=(), title=None, release=1, date=None):
    from .sema import analyse
    prog = analyse(path, libpath)
    gen = Gen(prog); gen.generate()
    import os
    image, info = link(prog, gen, title or os.path.splitext(os.path.basename(path))[0], release, date)
    info['program'] = prog
    return image, info
