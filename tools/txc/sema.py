"""sema.py - TXA's semantic pass: from syntax trees to a checked program.

What it does, in order (the TI workbench's pass 1 follows the same
order, which is why each step needs only what the steps before it made):

 1. Load the main file and its INCLUDEs.  A TI path such as
    "DSK1.STDLIB" names the file STDLIB; on a PC that is stdlib.txa,
    looked for beside the including file and then on the library path.
 2. Declare every top-level name.  Names ignore case; a name may be
    declared once.  Attributes are numbered 0-47 and properties 1-63 in
    the order they are declared; objects 1-1000 in declaration order
    (0 is "nothing"); classes are compile-time only: their attributes and
    properties are copied into each object that names them.
 3. Build the object tree: parents from "OBJECT x IN y" or a body's IN
    line; children in declaration order.
 4. Collect actions: every grammar line's action and every rule case's
    label.  An action Name needs a routine NameSub; actions are numbered
    in the order first met.
 5. Check every routine body and property routine: each name used must
    be a local, a parameter or a declared name of a kind that fits where
    it is used (an attribute after HAS, a property after a dot ...).
 6. Fold constant expressions, gather the dictionary (NAME words, verb
    words, grammar words; lower case; matched on 12 characters).

Errors stop the compile at the first one in M1 (the workbench will
collect up to 50); warnings are collected and returned."""

import os
from .lexer import TxaError
from .parser import parse
from . import ast as A

MAX_ATTRS, MAX_PROPS, MAX_OBJECTS, MAX_LOCALS, MAX_GLOBALS = 48, 63, 1000, 16, 240
DICT_LEN = 12
SLOT_TOKENS = {'noun', 'held', 'multi', 'multiheld', 'multiexcept', 'multiinside',
               'creature', 'number', 'topic', 'scope'}
RULE_PROPS = {'BEFORE', 'AFTER', 'LIFE', 'ORDERS'}
# Every ROOM gets all twelve exits (Rebecca's decision, 2026-10-19), so
# any exit can be opened while the game runs: those it was not given are
# added with the value NOTHING.  These are the library's names for them.
EXITS = ['N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW', 'UP', 'DOWN', 'INSIDE', 'OUTSIDE']
# Built-in functions: name -> (opcode, arguments, gives a value).  Their
# names are reserved.  Those that give no value give 0 in an expression.
BUILTINS = {
    'PARENT': ('PARENT', 1, True), 'CHILD': ('CHILD', 1, True), 'SIBLING': ('SIBLING', 1, True),
    'RANDOM': ('RANDOM', 1, True), 'READKEY': ('READKEY', 0, True),
    'SAVE': ('SAVE', 1, True), 'RESTORE': ('RESTORE', 1, True),
    'UNDOSAVE': ('UNDOSAVE', 0, True), 'UNDO': ('UNDO', 0, True),
    'QUIT': ('QUIT', 0, False), 'RESTART': ('RESTART', 0, False),
    'STATUS': ('STATUS', 3, False), 'SOUND': ('SOUND', 1, False), 'STYLE': ('STYLE', 1, False),
    'READ': ('READ', 2, True), 'TOKENIZE': ('TOKENIZE', 2, True),
    'HASATTR': ('HASATTRV', 2, True), 'FRESHLINE': ('FRESH', 0, False),
    'AGET': ('ALOADV', 2, True), 'APUT': ('ASTOREV', 3, False),
    'ISNAME': ('ISNAME', 2, True), 'FILTERN': ('FILTERN', 4, True), 'ACOPY': ('ACOPY', 3, False),
    # the second argument of these two is a property name, not a value
    'PROPLEN': ('PROPLEN', 2, True), 'PROPWORD': ('GETPROPN', 3, True),
}
PROP_ARG = {'PROPLEN', 'PROPWORD'}
# Arrays the compiler makes for the library's parser (their names are reserved):
#   VERBTAB(v)  where verb v's grammar starts in GRAMTAB (v from 1)
#   GRAMTAB     for each verb: its line count, then each line: the index
#               of the next line, action, flags (1 = REVERSE), token
#               count, tokens.  A token is
#               >1000+t a slot (t: 1 noun 2 held 3 multi 4 multiheld
#               5 multiexcept 6 multiinside 7 creature 8 number 9 topic
#               10 scope), +>0800 if a routine follows (noun=R, scope=R);
#               >2000+w a literal word w; >3000+a a noun with attribute a
#   ACTSUB(a)   action a's routine
#   DICTVERB(w) the verb word w belongs to (0 if none), w from 1
GEN_ARRAYS = ['VERBTAB', 'GRAMTAB', 'ACTSUB', 'DICTVERB']
SLOT_CODE = {'noun': 1, 'held': 2, 'multi': 3, 'multiheld': 4, 'multiexcept': 5, 'multiinside': 6,
             'creature': 7, 'number': 8, 'topic': 9, 'scope': 10}   # routine properties whose cases are actions


class Sym:
    """One declared name.  kind: constant, global, array, attribute,
    property, class, object, routine, picture."""
    def __init__(self, kind, name, decl, number=None):
        self.kind, self.name, self.decl, self.number = kind, name, decl, number
    def __repr__(self):
        return f'Sym({self.kind} {self.name} #{self.number})'


class Obj:
    """An object (or room) after inheritance: what the image will hold."""
    def __init__(self, sym, kind, short):
        self.sym, self.kind, self.short = sym, kind, short
        self.number = sym.number
        self.parent = self.child = self.sibling = 0
        self.attrs = set()            # attribute numbers set at the start
        self.props = {}               # property number -> ('values', [values]) or ('routine', PropBlock)
        self.names = []               # dictionary words
        self.classes = []


class Program:
    """The checked program, for code generation."""
    def __init__(self):
        self.symbols = {}             # upper-case name -> Sym
        self.attrs = []               # names, by number
        self.props = ['']             # names, by number (0 unused)
        self.objects = []             # Obj, by number - 1
        self.routines = []            # Routine nodes (named)
        self.actions = []             # action names, by number
        self.globals = []             # Sym, by number
        self.arrays = []              # Sym
        self.pictures = []            # Sym
        self.verbs = []               # Verb nodes
        self.dictionary = set()       # words, lower case, at most 12 characters
        self.constants = {}           # upper name -> value
        self.warnings = []

    def sym(self, name):
        return self.symbols.get(name.upper())


class Sema:
    def __init__(self, libpath=()):
        self.p = Program()
        self.libpath = list(libpath)
        self.loaded = set()

    # ---- errors -------------------------------------------------------------
    def err(self, node, msg):
        raise TxaError(node.file, node.line, msg)

    def warn(self, node, msg):
        self.p.warnings.append(f'{node.file} line {node.line}: warning: {msg}')

    # ---- 1. loading ---------------------------------------------------------
    def resolve(self, tipath, here, node):
        base = tipath.split('.')[-1].split(':')[-1].lower()
        for d in [here] + self.libpath:
            for f in os.listdir(d) if os.path.isdir(d) else []:
                if f.lower() in (base + '.txa', base):
                    return os.path.join(d, f)
        self.err(node, f'cannot find the file {tipath} (looked for {base}.txa)')

    def load(self, path, decls):
        key = os.path.abspath(path)
        if key in self.loaded:
            return
        self.loaded.add(key)
        for d in parse(open(path).read(), os.path.basename(path)):
            if isinstance(d, A.Include):
                self.load(self.resolve(d.path, os.path.dirname(path), d), decls)
            else:
                decls.append(d)

    # ---- 2. declarations ----------------------------------------------------
    def declare(self, kind, name, node, number=None):
        u = name.upper()
        if u in BUILTINS:
            self.err(node, f'{name} is a built-in function and cannot be declared')
        if u in self.p.symbols:
            old = self.p.symbols[u].decl
            self.err(node, f'{name} is already declared ({old.file} line {old.line})')
        s = Sym(kind, name, node, number)
        self.p.symbols[u] = s
        return s

    def declare_all(self, decls):
        p = self.p
        here = decls[0] if decls else A.Num(0, file='<compiler>', line=0)
        self.declare('property', 'NAME', here, 1); p.props.append('NAME')     # NAME is property 1
        for g in GEN_ARRAYS:
            p.arrays.append(self.declare('array', g, here, len(p.arrays)))
        for w in (',', '.'):                                                 # always words, for the parser
            p.dictionary.add(w)
        for d in decls:
            if isinstance(d, A.Constant):
                self.declare('constant', d.name, d)
            elif isinstance(d, A.Global):
                if len(p.globals) >= MAX_GLOBALS:
                    self.err(d, f'more than {MAX_GLOBALS} globals')
                p.globals.append(self.declare('global', d.name, d, len(p.globals)))
            elif isinstance(d, A.Array):
                p.arrays.append(self.declare('array', d.name, d, len(p.arrays)))
            elif isinstance(d, A.Attribute):
                for n in d.names:
                    if len(p.attrs) >= MAX_ATTRS:
                        self.err(d, f'more than {MAX_ATTRS} attributes')
                    self.declare('attribute', n, d, len(p.attrs)); p.attrs.append(n)
            elif isinstance(d, A.Property):
                for n in d.names:
                    if len(p.props) > MAX_PROPS:
                        self.err(d, f'more than {MAX_PROPS} properties')
                    self.declare('property', n, d, len(p.props)); p.props.append(n)
            elif isinstance(d, A.Picture):
                p.pictures.append(self.declare('picture', d.name, d, len(p.pictures) + 1))
            elif isinstance(d, A.ObjDecl):
                if d.kind == 'CLASS':
                    self.declare('class', d.name, d)
                else:
                    if len(p.objects) >= MAX_OBJECTS:
                        self.err(d, f'more than {MAX_OBJECTS} objects')
                    s = self.declare('object', d.name, d, len(p.objects) + 1)
                    p.objects.append(Obj(s, d.kind, d.short))
            elif isinstance(d, A.Routine):
                self.declare('routine', d.name, d); p.routines.append(d)
            elif isinstance(d, A.Verb):
                p.verbs.append(d)
        # LASTOBJ: the highest object number (compiler-made, reserved)
        self.declare('constant', 'LASTOBJ', here)
        p.constants['LASTOBJ'] = sum(1 for d in decls if isinstance(d, A.ObjDecl) and d.kind != 'CLASS')
        # constants may refer to earlier or later constants: fold on demand
        for d in decls:
            if isinstance(d, A.Constant):
                self.const_value(d.name, d, set())

    def const_value(self, name, node, busy):
        u = name.upper()
        if u in self.p.constants:
            return self.p.constants[u]
        s = self.p.symbols[u]
        if u in busy:
            self.err(node, f'the constant {name} is defined in terms of itself')
        busy.add(u)
        v = self.fold(s.decl.value, busy)
        if v is None:
            self.err(s.decl, f'the value of {name} must be worked out when compiling (numbers and constants only)')
        self.p.constants[u] = v
        return v

    def fold(self, e, busy=None):
        """The value of a constant expression, or None if it is not one.
        16-bit arithmetic, as the VM does it."""
        busy = busy if busy is not None else set()
        if isinstance(e, A.Num):
            return e.value
        if isinstance(e, A.Const) and e.which in ('TRUE', 'FALSE', 'NOTHING'):
            return {'TRUE': 1, 'FALSE': 0, 'NOTHING': 0}[e.which]
        if isinstance(e, A.Name):
            s = self.p.sym(e.id)
            if s and s.kind == 'constant':
                return self.const_value(e.id, e, busy)
            return None
        if isinstance(e, A.Unary) and e.op == '-':
            v = self.fold(e.arg, busy)
            return None if v is None else wrap(-v)
        if isinstance(e, A.Binary) and e.op in ('+', '-', '*', '/', 'MOD'):
            a, b = self.fold(e.left, busy), self.fold(e.right, busy)
            if a is None or b is None:
                return None
            if e.op in ('/', 'MOD') and b == 0:
                self.err(e, 'division by zero')
            return wrap({'+': a + b, '-': a - b, '*': a * b,
                         '/': int(a / b), 'MOD': a - int(a / b) * b}[e.op])
        return None

    # ---- 3. objects ---------------------------------------------------------
    def build_objects(self, decls):
        p = self.p
        classdecl = {d.name.upper(): d for d in decls if isinstance(d, A.ObjDecl) and d.kind == 'CLASS'}
        for o in p.objects:
            d = o.sym.decl
            for cls in self.class_chain(d, classdecl, []):     # base classes first, then the object
                self.apply_body(o, cls, inherited=cls is not d)
            if d.parent:
                self.set_parent(o, d.parent, d)
            if o.kind == 'ROOM':
                for x in EXITS:
                    sx = p.sym(x)
                    if sx and sx.kind == 'property' and sx.number not in o.props:
                        o.props[sx.number] = ('values', [('num', 0)])
        for o in p.objects:                                     # children in declaration order
            if o.parent:
                par = p.objects[o.parent - 1]
                if not par.child:
                    par.child = o.number
                else:
                    c = p.objects[par.child - 1]
                    while c.sibling:
                        c = p.objects[c.sibling - 1]
                    c.sibling = o.number
        for o in p.objects:                                     # no loops in the tree
            seen, q = set(), o
            while q.parent:
                if q.number in seen:
                    self.err(o.sym.decl, f'{o.sym.name} is inside itself (through IN)')
                seen.add(q.number); q = p.objects[q.parent - 1]

    def class_chain(self, d, classdecl, path):
        """The declarations to apply to an object, base classes first."""
        chain = []
        for item in d.body:
            if isinstance(item, A.Classes):
                for cname in item.names:
                    s = self.p.sym(cname)
                    if not s or s.kind != 'class':
                        self.err(item, f'{cname} is not a class')
                    if cname.upper() in path:
                        self.err(item, f'the class {cname} includes itself')
                    for c in self.class_chain(classdecl[cname.upper()], classdecl, path + [cname.upper()]):
                        if c not in chain:
                            chain.append(c)
        return chain + [d]

    def set_parent(self, o, pname, node):
        s = self.p.sym(pname)
        if not s or s.kind != 'object':
            self.err(node, f'{pname} is not an object, so nothing can be IN it')
        if o.parent and o.parent != s.number:
            self.err(node, f'{o.sym.name} is given two parents')
        o.parent = s.number

    def apply_body(self, o, d, inherited):
        for item in d.body:
            if isinstance(item, A.Has):
                for name, on in item.attrs:
                    n = self.attr_number(name, item)
                    (o.attrs.add if on else o.attrs.discard)(n)
            elif isinstance(item, A.Names):
                for w in item.words:
                    o.names.append(self.dict_word(w, item))
                o.props[1] = ('values', [('dict', w) for w in o.names])
            elif isinstance(item, A.InParent):
                if inherited:
                    self.err(item, 'a class cannot say what its objects are IN')
                self.set_parent(o, item.name, item)
            elif isinstance(item, A.Classes):
                o.classes += [c for c in item.names if c not in o.classes]
            elif isinstance(item, (A.PropVal, A.PropBlock)):
                s = self.p.sym(item.name)
                if not s or s.kind != 'property':
                    self.err(item, f'unknown property {item.name} (declare it with PROPERTY)')
                if isinstance(item, A.PropVal):
                    o.props[s.number] = ('values', [self.prop_value(v, item) for v in item.values])
                else:
                    o.props[s.number] = ('routine', item, o)

    def prop_value(self, e, node):
        """A property value: a number, a string, an object, a routine or a
        picture.  Returned as (kind, value) for code generation."""
        if isinstance(e, A.Str):
            return ('str', e.value)
        if isinstance(e, A.Name):
            s = self.p.sym(e.id)
            if s is None:
                self.err(e, f'unknown name {e.id}')
            if s.kind == 'object':
                return ('obj', s.number)
            if s.kind == 'routine':
                return ('routine', s.name)
            if s.kind == 'picture':
                return ('num', s.number)
        if isinstance(e, A.Const) and e.which == 'SELF':
            self.err(e, 'SELF has no value outside a routine')
        v = self.fold(e)
        if v is None:
            self.err(e, 'a property value must be a number, a string, an object, a routine or a constant expression')
        return ('num', v)

    def attr_number(self, name, node):
        s = self.p.sym(name)
        if not s or s.kind != 'attribute':
            self.err(node, f'unknown attribute "{name}"')
        return s.number

    def dict_word(self, w, node):
        w = w.lower()
        if not w or ' ' in w:
            self.err(node, f'a dictionary word cannot be empty or contain spaces: "{w}"')
        if len(w) > DICT_LEN:
            self.warn(node, f'"{w}" is longer than {DICT_LEN} letters; the parser will match only "{w[:DICT_LEN]}"')
            w = w[:DICT_LEN]
        self.p.dictionary.add(w)
        return w

    # ---- 4. actions ---------------------------------------------------------
    def use_action(self, name, node):
        p = self.p
        if name.upper() not in (a.upper() for a in p.actions):
            s = p.sym(name + 'Sub')
            if not s or s.kind != 'routine':
                self.err(node, f'the action {name} has no routine {name}Sub')
            p.actions.append(name)

    def collect_actions(self):
        p = self.p
        use = self.use_action
        p.verb_of = {}
        for vn, v in enumerate(p.verbs, 1):
            v.number = vn
            for w in v.words:
                w = self.dict_word(w, v)
                if w in p.verb_of:
                    self.err(v, f'"{w}" is already a word of another VERB')
                p.verb_of[w] = vn
            for gl in v.lines:
                for t in gl.tokens:
                    if t.kind == 'word':
                        self.dict_word(t.value, t)
                    elif t.value.lower() not in SLOT_TOKENS and not self.is_attr(t.value):
                        self.err(t, f'{t.value} is not a grammar token (noun, held, multi ...) or an attribute')
                    if t.filter:
                        s = p.sym(t.filter)
                        if not s or s.kind != 'routine':
                            self.err(t, f'{t.filter} is not a routine')
                if len([t for t in gl.tokens if t.kind == 'slot']) > 2:
                    self.err(gl, 'a grammar line takes at most two objects')
                use(gl.action, gl)
        for o in p.objects:
            for prop in o.props.values():
                if prop[0] == 'routine':
                    for item in prop[1].body:
                        if isinstance(item, A.Case):
                            if prop[1].name.upper() not in RULE_PROPS:
                                pass  # cases in other routine properties are allowed too
                            for a in item.actions:
                                use(a, item)

    def is_attr(self, name):
        s = self.p.sym(name)
        return s is not None and s.kind == 'attribute'

    # ---- 5. bodies ----------------------------------------------------------
    def check_routines(self):
        for r in self.p.routines:
            self.check_body(r.body, r.params, r, in_object=False)
        for o in self.p.objects:
            for prop in o.props.values():
                if prop[0] == 'routine':
                    self.check_body(prop[1].body, [], prop[1], in_object=True)

    def check_body(self, body, params, owner, in_object):
        locals_ = [x.upper() for x in params]
        def collect(stmts):
            for s in stmts:
                if isinstance(s, A.Local):
                    for n in s.names:
                        if n.upper() in locals_:
                            self.err(s, f'{n} is declared twice in this routine')
                        locals_.append(n.upper())
                for sub in sub_bodies(s):
                    collect(sub)
        collect(body)
        if len(locals_) > MAX_LOCALS:
            self.err(owner, f'more than {MAX_LOCALS} parameters and locals in one routine')
        owner.locals = locals_
        scope = set(locals_)
        def stmt(s):
            if isinstance(s, A.If):
                for c, b in s.arms:
                    expr(c); [stmt(x) for x in b]
                [stmt(x) for x in (s.orelse or [])]
            elif isinstance(s, A.While):
                expr(s.cond); [stmt(x) for x in s.body]
            elif isinstance(s, A.ForEach):
                if s.var.upper() not in scope:
                    self.err(s, f'the loop variable {s.var} must be a LOCAL')
                expr(s.parent); [stmt(x) for x in s.body]
            elif isinstance(s, A.Case):
                [stmt(x) for x in s.body]
            elif isinstance(s, A.Print):
                for it in s.items:
                    expr(it.expr)
            elif isinstance(s, A.Move):
                expr(s.obj); expr(s.dest)
            elif isinstance(s, (A.Remove, A.PicStmt)):
                expr(s.obj if isinstance(s, A.Remove) else s.value)
            elif isinstance(s, A.Give):
                expr(s.obj)
                for n, _ in s.attrs:
                    self.attr_number(n, s)
            elif isinstance(s, A.Return):
                if s.value is not None:
                    expr(s.value)
            elif isinstance(s, A.Assign):
                target(s.target); expr(s.value)
            elif isinstance(s, A.ExprStmt):
                e = s.expr
                if isinstance(e, A.Name) and e.id.upper() in BUILTINS and e.id.upper() not in scope:
                    s.expr = A.Call(e, [], file=e.file, line=e.line)
                    expr(s.expr)
                elif isinstance(e, A.Name):
                    sy = self.p.sym(e.id)
                    if e.id.upper() in scope or not sy or sy.kind != 'routine':
                        self.err(s, f'{e.id} on its own does nothing: did you mean a call, {e.id}()?')
                    s.expr = A.Call(e, [], file=e.file, line=e.line)
                else:
                    expr(e)
        def target(e):
            if isinstance(e, A.Name):
                if e.id.upper() in scope:
                    return
                sy = self.p.sym(e.id)
                if not sy:
                    self.err(e, f'unknown name {e.id}')
                if sy.kind != 'global':
                    self.err(e, f'{e.id} is a {sy.kind}, not a variable: it cannot be assigned to')
            elif isinstance(e, A.PropRef):
                expr(e)
            elif isinstance(e, A.Call):
                sy = self.p.sym(e.func.id) if isinstance(e.func, A.Name) else None
                if not sy or sy.kind != 'array':
                    self.err(e, 'only an array element can be assigned to with ( )')
                if len(e.args) != 1:
                    self.err(e, 'an array element takes one index')
                expr(e.args[0])
        def expr(e):
            if isinstance(e, A.DictWord):
                self.dict_word(e.word, e)
                return
            if isinstance(e, A.ActionRef):
                self.use_action(e.name, e)
                return
            if isinstance(e, (A.Num, A.Str, A.Const)):
                if isinstance(e, A.Const) and e.which == 'SELF' and not in_object:
                    self.warn(e, 'SELF in a routine that is not a property: it means the object whose property called it')
                return
            if isinstance(e, A.Name):
                if e.id.upper() in scope:
                    return
                sy = self.p.sym(e.id)
                if not sy:
                    self.err(e, f'unknown name {e.id}')
                if sy.kind in ('attribute', 'property', 'class'):
                    self.err(e, f'{e.id} is a {sy.kind} and has no value here')
                return
            if isinstance(e, A.Unary):
                return expr(e.arg)
            if isinstance(e, A.Binary):
                expr(e.left)
                if e.op in ('HAS', 'HASNT'):
                    if not isinstance(e.right, A.Name):
                        self.err(e, f'{e.op} needs an attribute name after it')
                    self.attr_number(e.right.id, e.right)
                else:
                    expr(e.right)
                return
            if isinstance(e, A.PropRef):
                expr(e.obj)
                sy = self.p.sym(e.prop)
                if not sy or sy.kind != 'property':
                    self.err(e, f'unknown property {e.prop}')
                return
            if isinstance(e, A.Call):
                if isinstance(e.func, A.Name) and e.func.id.upper() in BUILTINS and e.func.id.upper() not in scope:
                    b = e.func.id.upper(); n = BUILTINS[b][1]
                    if len(e.args) != n:
                        self.err(e, f'{b} takes {n} argument{"s" if n != 1 else ""}, not {len(e.args)}')
                    for i, a in enumerate(e.args):
                        if b in PROP_ARG and i == 1:
                            sy = self.p.sym(a.id) if isinstance(a, A.Name) else None
                            if not sy or sy.kind != 'property':
                                self.err(e, f'the second argument of {b} must be a property name')
                        else:
                            expr(a)
                    return
                if isinstance(e.func, A.Name) and e.func.id.upper() not in scope:
                    sy = self.p.sym(e.func.id)
                    if not sy:
                        self.err(e, f'unknown name {e.func.id}')
                    if sy.kind == 'array':
                        if len(e.args) != 1:
                            self.err(e, 'an array element takes one index')
                    elif sy.kind == 'routine':
                        n = len(sy.decl.params)
                        if len(e.args) > n:
                            self.err(e, f'{sy.name} takes {n} argument{"s" if n != 1 else ""}, not {len(e.args)}')
                    else:
                        self.err(e, f'{e.func.id} is a {sy.kind} and cannot be called')
                else:
                    expr(e.func)                  # obj.prop(args) or a routine held in a variable
                for a in e.args:
                    expr(a)
                return
            self.err(e, 'unexpected expression')     # pragma: no cover
        for s in body:
            stmt(s)

    # ---- driver -------------------------------------------------------------
    def replace_and_extend(self, decls):
        """REPLACE name: the routine of that name declared in the same file
        as the REPLACE is kept, any other declaration of it dropped (so a
        game replaces a library routine).  EXTEND "word" [FIRST]: the
        grammar lines join the VERB that has the word, at the end (or the
        start, with FIRST)."""
        repl = {}
        for d in decls:
            if isinstance(d, A.Replace):
                repl[d.name.upper()] = d
        keep = []
        for d in decls:
            if isinstance(d, A.Routine) and d.name.upper() in repl and d.file != repl[d.name.upper()].file:
                continue
            if not isinstance(d, A.Replace):
                keep.append(d)
        for name, r in repl.items():
            if not any(isinstance(d, A.Routine) and d.name.upper() == name for d in keep):
                self.err(r, f'REPLACE {r.name}, but this file has no ROUTINE {r.name}')
        decls[:] = keep
        verbs = [d for d in decls if isinstance(d, A.Verb)]
        for d in [d for d in decls if isinstance(d, A.Extend)]:
            v = next((v for v in verbs if d.word.lower() in (w.lower() for w in v.words)), None)
            if v is None:
                self.err(d, f'EXTEND "{d.word}": no VERB has that word')
            v.lines = (d.lines + v.lines) if d.first else (v.lines + d.lines)
        decls[:] = [d for d in decls if not isinstance(d, A.Extend)]

    def run(self, path):
        decls = []
        self.load(path, decls)
        self.replace_and_extend(decls)
        self.declare_all(decls)
        self.build_objects(decls)
        self.collect_actions()
        self.check_routines()
        self.finish_tables()
        for o in self.p.objects:
            if not o.names and o.kind == 'OBJECT':
                self.warn(o.sym.decl, f'{o.sym.name} has no NAME words, so the player cannot refer to it')
        return self.p


def _finish_tables(self):
    """Number the dictionary (sorted, from 1) and fill the generated arrays."""
    p = self.p
    words = sorted(p.dictionary, key=lambda w: w.encode('latin-1'))
    p.dictnum = {w: i + 1 for i, w in enumerate(words)}
    verbtab, gram = [('num', 0)], []
    for v in p.verbs:
        verbtab.append(('num', len(gram)))
        gram.append(('num', len(v.lines)))
        for gl in v.lines:
            here = len(gram)
            act = [a.upper() for a in p.actions].index(gl.action.upper())
            toks = []
            for t in gl.tokens:
                if t.kind == 'word':
                    toks.append(('num', 0x2000 + p.dictnum[t.value.lower()[:DICT_LEN]]))
                elif t.value.lower() in SLOT_CODE:
                    code = 0x1000 + SLOT_CODE[t.value.lower()]
                    if t.filter:
                        toks += [('num', code + 0x0800), ('routine', p.sym(t.filter).name)]
                    else:
                        toks.append(('num', code))
                else:
                    toks.append(('num', 0x3000 + p.sym(t.value).number))
            gram += [('num', 0), ('num', act), ('num', 1 if gl.reverse else 0), ('num', len([t for t in gl.tokens]))] + toks
            gram[here] = ('num', len(gram))           # where the next line starts
    gen = {
        'VERBTAB': verbtab,
        'GRAMTAB': gram or [('num', 0)],
        'ACTSUB': [('routine', p.sym(a + 'Sub').name) for a in p.actions] or [('num', 0)],
        'DICTVERB': [('num', 0)] + [('num', p.verb_of.get(w, 0)) for w in words],
    }
    for name, vals in gen.items():
        p.sym(name).gen_values = vals

Sema.finish_tables = _finish_tables


def sub_bodies(s):
    if isinstance(s, A.If):
        return [b for _, b in s.arms] + ([s.orelse] if s.orelse else [])
    if isinstance(s, (A.While, A.ForEach, A.Case)):
        return [s.body]
    return []


def wrap(v):
    v &= 0xFFFF
    return v - 0x10000 if v > 0x7FFF else v


def analyse(path, libpath=()):
    return Sema(libpath).run(path)
