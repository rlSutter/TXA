"""ast.py - the TXA abstract syntax tree.

Every node carries the file and line it came from, for error messages.
Nodes are plain classes with named fields; `kind` is the class name."""

class Node:
    fields = ()
    def __init__(self, *args, file=None, line=None):
        for f, v in zip(self.fields, args):
            setattr(self, f, v)
        self.file, self.line = file, line
    def __repr__(self):
        return f"{type(self).__name__}({', '.join(f'{f}={getattr(self, f)!r}' for f in self.fields)})"
    def __eq__(self, other):
        return type(self) is type(other) and all(getattr(self, f) == getattr(other, f) for f in self.fields)

def node(name, *fields):
    return type(name, (Node,), {'fields': fields})

# declarations
Include   = node('Include', 'path')
Constant  = node('Constant', 'name', 'value')
Global    = node('Global', 'name', 'value')
Array     = node('Array', 'name', 'size', 'values')          # size or values (None for the other)
Attribute = node('Attribute', 'names')
Property  = node('Property', 'names')
Picture   = node('Picture', 'name', 'path')
ObjDecl   = node('ObjDecl', 'kind', 'name', 'short', 'parent', 'body')   # kind: CLASS, OBJECT, ROOM
Verb      = node('Verb', 'words', 'lines')
Extend    = node('Extend', 'word', 'first', 'lines')            # EXTEND "verb" [FIRST]
Replace   = node('Replace', 'name')                            # REPLACE routine
GLine     = node('GLine', 'tokens', 'action', 'reverse')
GTok      = node('GTok', 'kind', 'value', 'filter')            # kind: 'slot' / 'word'; filter: routine for noun=R / scope=R
Routine   = node('Routine', 'name', 'params', 'body')
# object body items
Has       = node('Has', 'attrs')                               # [(attr, on)]
Classes   = node('Classes', 'names')
InParent  = node('InParent', 'name')
Names     = node('Names', 'words')
PropVal   = node('PropVal', 'name', 'values')                  # values: list of expressions
PropBlock = node('PropBlock', 'name', 'body')                  # body: list of stmts and Case
Case      = node('Case', 'actions', 'body')                    # a rule block's  Action, Action:  section
# statements
If        = node('If', 'arms', 'orelse')                       # arms: [(cond, body)]
While     = node('While', 'cond', 'body')
ForEach   = node('ForEach', 'var', 'parent', 'body')
Local     = node('Local', 'names')
Print     = node('Print', 'items', 'newline')                  # PRINT ends the line, WRITE does not
PItem     = node('PItem', 'form', 'expr')                      # form: None, 'the', 'The', 'a', 'A', 'name', 'number', 'char'
Move      = node('Move', 'obj', 'dest')
Remove    = node('Remove', 'obj')
Give      = node('Give', 'obj', 'attrs')
Return    = node('Return', 'value')
PicStmt   = node('PicStmt', 'value')
Assign    = node('Assign', 'target', 'value')
ExprStmt  = node('ExprStmt', 'expr')
# expressions
Num       = node('Num', 'value')
Str       = node('Str', 'value')
Name      = node('Name', 'id')                                 # an identifier, resolved later
Const     = node('Const', 'which')                             # TRUE FALSE NOTHING SELF
Unary     = node('Unary', 'op', 'arg')
Binary    = node('Binary', 'op', 'left', 'right')
PropRef   = node('PropRef', 'obj', 'prop')
ActionRef = node('ActionRef', 'name')                         # ##Name
DictWord  = node('DictWord', 'word')                          # 'word'
Call      = node('Call', 'func', 'args')                       # also array element: resolved later
