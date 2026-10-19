"""parser.py - TXA tokens to an AST (recursive descent, no backtracking).

The grammar is written so a two-pass compiler on the TI can follow the
same steps: every construct is recognised from its first token, every
block ends at END, and one statement fills one line.

  file      := decl*
  decl      := INCLUDE str | CONSTANT id = expr | GLOBAL id [= expr]
             | ARRAY id num | ARRAY id = expr {, expr}
             | ATTRIBUTE id {id} | PROPERTY id {id} | PICTURE id str
             | (CLASS | OBJECT | ROOM) id [str] [IN id] NL body END
             | VERB str {str} NL {gline} END
             | ROUTINE id [id {, id}] NL stmts END
  body item := HAS [NOT] id ... | CLASS id ... | IN id | NAME str ...
             | id value {value}             a property with values
             | id NL items END              a property holding a routine;
                                            "Action, Action:" lines in it
                                            open rule cases (BEFORE ... END)
  gline     := {slot | str | slot=id} -> id [REVERSE]
  stmt      := IF expr NL stmts {ELSEIF expr NL stmts} [ELSE NL stmts] END
             | WHILE expr NL stmts END | FOR EACH id IN expr NL stmts END
             | LOCAL id {, id} | PRINT [items] | WRITE items
             | MOVE expr TO expr | REMOVE expr | GIVE expr [NOT] id ...
             | RETURN [expr] | PICTURE expr | target = expr | expr
  items     := item {, item};  item := expr | (form) expr
  expr      := precedence, loosest first: OR; AND; NOT; comparisons
               (= <> < > <= >= HAS HASNT IN NOTIN); + -; * / MOD;
               unary -; postfix .prop and (args)
"""
from .lexer import tokenize, TxaError
from . import ast as A

PRINT_FORMS = {'the', 'The', 'a', 'A', 'an', 'An', 'name', 'number', 'char', 'string'}
CMP = {'=', '<>', '<', '>', '<=', '>='}
CMP_KW = {'HAS', 'HASNT', 'IN', 'NOTIN'}

class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    # ---- token helpers
    @property
    def tok(self):
        return self.t[self.i]
    def peek(self, k=1):
        return self.t[min(self.i + k, len(self.t) - 1)]
    def err(self, msg, tok=None):
        tok = tok or self.tok
        raise TxaError(tok.file, tok.line, msg)
    def at(self, kind, value=None):
        t = self.tok
        return t.kind == kind and (value is None or t.value == value)
    def at_kw(self, *words):
        return self.tok.kind == 'KW' and self.tok.value in words
    def at_sym(self, *syms):
        return self.tok.kind == 'SYM' and self.tok.value in syms
    def take(self):
        t = self.tok; self.i += 1; return t
    def expect(self, kind, value=None, what=None):
        if not self.at(kind, value):
            self.err(f"expected {what or value or kind.lower()}, found {self.describe()}")
        return self.take()
    def expect_nl(self):
        if not self.at('NL'):
            self.err(f'expected the end of the line, found {self.describe()}')
        self.take()
    def describe(self):
        t = self.tok
        return {'NL': 'the end of the line', 'EOF': 'the end of the file'}.get(t.kind) or repr(t.text)
    def ident(self, what='a name'):
        return self.expect('ID', what=what).value
    def action(self):
        """An action name: any word, keywords included, because the
        standard actions Give, Remove and Move share their names with
        keywords.  Only used where nothing else can stand: after -> and
        in a rule case's label."""
        if self.tok.kind in ('ID', 'KW'):
            return self.take().text
        self.err(f'expected an action name, found {self.describe()}')
    def pos(self, t=None):
        t = t or self.tok
        return {'file': t.file, 'line': t.line}

    # ---- declarations
    def file(self):
        decls = []
        while not self.at('EOF'):
            decls.append(self.decl())
        return decls

    def decl(self):
        t = self.tok; p = self.pos()
        if t.kind != 'KW':
            self.err(f'expected a declaration (OBJECT, ROOM, ROUTINE ...), found {self.describe()}')
        k = self.take().value
        if k == 'INCLUDE':
            d = A.Include(self.expect('STR', what='a file name in quotes').value, **p)
        elif k == 'CONSTANT':
            n = self.ident(); self.expect('SYM', '='); d = A.Constant(n, self.expr(), **p)
        elif k == 'GLOBAL':
            n = self.ident(); v = None
            if self.at_sym('='):
                self.take(); v = self.expr()
            d = A.Global(n, v, **p)
        elif k == 'ARRAY':
            n = self.ident()
            if self.at_sym('='):
                self.take(); vals = [self.expr()]
                while self.at_sym(','):
                    self.take(); vals.append(self.expr())
                d = A.Array(n, None, vals, **p)
            else:
                d = A.Array(n, self.expect('NUM', what='the array size').value, None, **p)
        elif k in ('ATTRIBUTE', 'PROPERTY'):
            names = [self.ident()]
            while self.at('ID'):
                names.append(self.take().value)
            d = (A.Attribute if k == 'ATTRIBUTE' else A.Property)(names, **p)
        elif k == 'PICTURE':
            n = self.ident(); d = A.Picture(n, self.expect('STR', what='a picture file name').value, **p)
        elif k in ('CLASS', 'OBJECT', 'ROOM'):
            return self.objdecl(k, p)
        elif k == 'VERB':
            return self.verb(p)
        elif k == 'EXTEND':
            w = self.expect('STR', what='a verb word in quotes').value
            first = False
            if self.at_kw('FIRST'):
                self.take(); first = True
            self.expect_nl()
            v = self.verb_lines(p)
            return A.Extend(w, first, v, **p)
        elif k == 'REPLACE':
            d = A.Replace(self.ident('the routine to replace'), **p)
        elif k == 'ROUTINE':
            n = self.ident('the routine name'); params = []
            if self.at('ID'):
                params.append(self.take().value)
                while self.at_sym(','):
                    self.take(); params.append(self.ident('a parameter name'))
            self.expect_nl()
            body = self.stmts(('END',))
            self.expect('KW', 'END'); self.expect_nl()
            return A.Routine(n, params, body, **p)
        else:
            self.err(f'{t.text} cannot start a declaration', t)
        self.expect_nl()
        return d

    def objdecl(self, kind, p):
        name = self.ident(f'the {kind.lower()} name')
        short = parent = None
        if kind != 'CLASS' and self.at('STR'):
            short = self.take().value
        if kind == 'OBJECT' and self.at_kw('IN'):
            self.take(); parent = self.ident('the parent object')
        self.expect_nl()
        body = []
        while not self.at_kw('END'):
            if self.at('EOF'):
                self.err(f'{kind} {name} has no END')
            body.append(self.body_item())
        self.take(); self.expect_nl()
        return A.ObjDecl(kind, name, short, parent, body, **p)

    def body_item(self):
        p = self.pos()
        if self.at_kw('HAS'):
            self.take(); attrs = self.attr_list()
            self.expect_nl(); return A.Has(attrs, **p)
        if self.at_kw('CLASS'):
            self.take(); names = [self.ident('a class name')]
            while self.at('ID'):
                names.append(self.take().value)
            self.expect_nl(); return A.Classes(names, **p)
        if self.at_kw('IN'):
            self.take(); n = self.ident('the parent object'); self.expect_nl(); return A.InParent(n, **p)
        if self.at_kw('NAME'):
            self.take(); words = [self.expect('STR', what='a dictionary word in quotes').value]
            while self.at('STR'):
                words.append(self.take().value)
            self.expect_nl(); return A.Names(words, **p)
        if self.at('ID'):
            prop = self.take().value
            if self.at('NL'):                       # a routine block: DESC ... END, BEFORE ... END
                self.take()
                body = self.stmts(('END',), cases=True)
                self.expect('KW', 'END'); self.expect_nl()
                return A.PropBlock(prop, body, **p)
            vals = [self.expr()]
            while not self.at('NL'):
                vals.append(self.expr())
            self.expect_nl()
            return A.PropVal(prop, vals, **p)
        self.err(f'expected a property, HAS, NAME, CLASS, IN or END, found {self.describe()}')

    def attr_list(self):
        attrs = []
        while self.at('ID') or self.at_kw('NOT'):
            on = True
            if self.at_kw('NOT'):
                self.take(); on = False
            attrs.append((self.ident('an attribute'), on))
        if not attrs:
            self.err('expected an attribute')
        return attrs

    def verb(self, p):
        words = [self.expect('STR', what='a verb word in quotes').value]
        while self.at('STR'):
            words.append(self.take().value)
        self.expect_nl()
        return A.Verb(words, self.verb_lines(p), **p)

    def verb_lines(self, p):
        lines = []
        while not self.at_kw('END'):
            if self.at('EOF'):
                self.err('VERB has no END')
            lp = self.pos(); toks = []
            while not self.at_sym('->'):
                if self.at('STR'):
                    toks.append(A.GTok('word', self.take().value, None, **lp))
                elif self.at('ID'):
                    v = self.take().value; f = None
                    if self.at_sym('='):
                        self.take(); f = self.ident('a routine name')
                    toks.append(A.GTok('slot', v, f, **lp))
                else:
                    self.err(f'expected a grammar token or ->, found {self.describe()}')
            self.take()
            act = self.action(); rev = False
            if self.at_kw('REVERSE'):
                self.take(); rev = True
            self.expect_nl()
            lines.append(A.GLine(toks, act, rev, **lp))
        self.take(); self.expect_nl()
        return lines

    # ---- statements
    def stmts(self, enders, cases=False):
        body = []
        while not self.at_kw(*enders):
            if self.at('EOF'):
                self.err('missing END')
            if cases and self.is_case():
                body.append(self.case(enders))
            else:
                body.append(self.stmt())
        return body

    def is_case(self):
        """An  Action, Action:  label: names and commas, then a colon."""
        j = self.i
        while True:
            if self.t[j].kind not in ('ID', 'KW'):
                return False
            j += 1
            if self.t[j].kind == 'SYM' and self.t[j].value == ':':
                return True
            if not (self.t[j].kind == 'SYM' and self.t[j].value == ','):
                return False
            j += 1

    def case(self, enders):
        p = self.pos(); acts = [self.action()]
        while self.at_sym(','):
            self.take(); acts.append(self.action())
        self.expect('SYM', ':')
        body = []
        if not self.at('NL'):                     # Action:  statement   on the same line
            body.append(self.stmt())
        else:
            self.take()
        while not self.at_kw(*enders) and not self.is_case():
            if self.at('EOF'):
                self.err('missing END')
            body.append(self.stmt())
        return A.Case(acts, body, **p)

    def block(self, *enders):
        self.expect_nl()
        return self.stmts(enders)

    def stmt(self):
        p = self.pos()
        if self.at_kw('IF'):
            self.take(); arms = [(self.expr(), self.block('ELSEIF', 'ELSE', 'END'))]; orelse = None
            while self.at_kw('ELSEIF'):
                self.take(); arms.append((self.expr(), self.block('ELSEIF', 'ELSE', 'END')))
            if self.at_kw('ELSE'):
                self.take(); orelse = self.block('END')
            self.expect('KW', 'END'); self.expect_nl()
            return A.If(arms, orelse, **p)
        if self.at_kw('WHILE'):
            self.take(); c = self.expr(); b = self.block('END')
            self.expect('KW', 'END'); self.expect_nl()
            return A.While(c, b, **p)
        if self.at_kw('FOR'):
            self.take(); self.expect('KW', 'EACH'); v = self.ident('the loop variable')
            self.expect('KW', 'IN'); par = self.expr(); b = self.block('END')
            self.expect('KW', 'END'); self.expect_nl()
            return A.ForEach(v, par, b, **p)
        if self.at_kw('LOCAL'):
            self.take(); names = [self.ident('a local variable name')]
            while self.at_sym(','):
                self.take(); names.append(self.ident('a local variable name'))
            self.expect_nl(); return A.Local(names, **p)
        if self.at_kw('PRINT', 'WRITE'):
            nl = self.take().value == 'PRINT'; items = []
            if not self.at('NL'):
                items.append(self.pitem())
                while self.at_sym(','):
                    self.take(); items.append(self.pitem())
            elif not nl:
                self.err('WRITE needs something to write')
            self.expect_nl(); return A.Print(items, nl, **p)
        if self.at_kw('MOVE'):
            self.take(); o = self.expr(); self.expect('KW', 'TO'); d = self.expr()
            self.expect_nl(); return A.Move(o, d, **p)
        if self.at_kw('REMOVE'):
            self.take(); o = self.expr(); self.expect_nl(); return A.Remove(o, **p)
        if self.at_kw('GIVE'):
            self.take(); o = self.postfix(); attrs = self.attr_list()
            self.expect_nl(); return A.Give(o, attrs, **p)
        if self.at_kw('RETURN'):
            self.take(); v = None if self.at('NL') else self.expr()
            self.expect_nl(); return A.Return(v, **p)
        if self.at_kw('PICTURE'):
            self.take(); v = self.expr(); self.expect_nl(); return A.PicStmt(v, **p)
        # In statement position "target = value" is an assignment, never a
        # comparison: read a target first, and if = follows, assign.
        # Otherwise read the line again as an expression (a call).
        start = self.i
        if self.at('ID') or self.at_kw('SELF'):
            target = self.postfix()
            if self.at_sym('='):
                if not isinstance(target, (A.Name, A.PropRef, A.Call)):
                    self.err('only a variable, a property or an array element can be assigned to')
                self.take(); v = self.expr(); self.expect_nl()
                return A.Assign(target, v, **p)
            self.i = start
        t0 = self.tok
        e = self.expr()
        if isinstance(e, A.Binary) and e.op == '=':
            self.err('only a variable, a property or an array element can be assigned to', t0)
        if not isinstance(e, (A.Call, A.Name, A.PropRef)):
            self.err('this line computes a value and does nothing with it: a statement, call or assignment is needed here', t0)
        self.expect_nl()
        return A.ExprStmt(e, **p)

    def pitem(self):
        p = self.pos()
        if self.at_sym('(') and self.peek().kind in ('ID', 'KW') and self.peek().text in PRINT_FORMS \
                and self.peek(2).kind == 'SYM' and self.peek(2).value == ')':
            self.take(); form = self.take().text; self.take()   # spelling matters: (the) vs (The)
            return A.PItem(form, self.expr(), **p)
        return A.PItem(None, self.expr(), **p)

    # ---- expressions
    def expr(self):
        e = self.and_expr()
        while self.at_kw('OR'):
            p = self.pos(self.take()); e = A.Binary('OR', e, self.and_expr(), **p)
        return e
    def and_expr(self):
        e = self.not_expr()
        while self.at_kw('AND'):
            p = self.pos(self.take()); e = A.Binary('AND', e, self.not_expr(), **p)
        return e
    def not_expr(self):
        if self.at_kw('NOT'):
            p = self.pos(self.take()); return A.Unary('NOT', self.not_expr(), **p)
        return self.cmp()
    def cmp(self):
        e = self.add()
        if self.at_sym(*CMP) or self.at_kw(*CMP_KW):
            t = self.take(); e = A.Binary(t.value, e, self.add(), **self.pos(t))
            if self.at_sym(*CMP) or self.at_kw(*CMP_KW):
                self.err('comparisons cannot be chained: use AND')
        return e
    def add(self):
        e = self.mul()
        while self.at_sym('+', '-'):
            t = self.take(); e = A.Binary(t.value, e, self.mul(), **self.pos(t))
        return e
    def mul(self):
        e = self.unary()
        while self.at_sym('*', '/') or self.at_kw('MOD'):
            t = self.take(); e = A.Binary(t.value, e, self.unary(), **self.pos(t))
        return e
    def unary(self):
        if self.at_sym('-'):
            t = self.take()
            if self.at('NUM') and self.tok.value == 32768:     # the one place 32768 may appear
                self.take(); return A.Num(-32768, **self.pos(t))
            a = self.unary()
            if isinstance(a, A.Num):
                return A.Num(-a.value, **self.pos(t))
            return A.Unary('-', a, **self.pos(t))
        return self.postfix()
    def postfix(self):
        e = self.primary()
        while True:
            if self.at_sym('.'):
                t = self.take()
                if self.at_kw('NAME'):
                    self.take(); e = A.PropRef(e, 'NAME', **self.pos(t))
                else:
                    e = A.PropRef(e, self.ident('a property name'), **self.pos(t))
            elif self.at_sym('(') and isinstance(e, (A.Name, A.PropRef)):
                t = self.take(); args = []
                if not self.at_sym(')'):
                    args.append(self.expr())
                    while self.at_sym(','):
                        self.take(); args.append(self.expr())
                self.expect('SYM', ')')
                if len(args) > 7:
                    self.err('a call takes at most 7 arguments', t)
                e = A.Call(e, args, **self.pos(t))
            else:
                return e
    def primary(self):
        t = self.tok; p = self.pos()
        if t.kind == 'NUM':
            self.take()
            if t.value == 32768:
                self.err('number 32768 is larger than 32767 (-32768 is allowed)', t)
            return A.Num(t.value, **p)
        if t.kind == 'STR':
            self.take(); return A.Str(t.value, **p)
        if t.kind == 'ACT':
            self.take(); return A.ActionRef(t.value, **p)
        if t.kind == 'DICT':
            self.take(); return A.DictWord(t.value, **p)
        if self.at_kw('NAME'):                       # the NAME property, as a value: PROPLEN(o, NAME)
            self.take(); return A.Name('NAME', **p)
        if t.kind == 'ID':
            self.take(); return A.Name(t.value, **p)
        if self.at_kw('TRUE', 'FALSE', 'NOTHING', 'SELF'):
            self.take(); return A.Const(t.value, **p)
        if self.at_sym('('):
            self.take(); e = self.expr(); self.expect('SYM', ')'); return e
        self.err(f'expected a value, found {self.describe()}')

def parse(text, file='<source>'):
    return Parser(tokenize(text, file)).file()
