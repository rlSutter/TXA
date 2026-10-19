"""lexer.py - TXA source to tokens.

TXA is line-oriented: a NEWLINE token ends every logical line, and the
parser uses it the way other languages use semicolons.  The rules (the
compiler's contract; the Authoring Language Reference will say the same):

- Keywords are written in uppercase.  Keywords and identifiers are both
  matched without regard to case, so ALPHA LOCK on the TI never breaks a
  program; identifiers keep their spelling for messages.
- `!` starts a comment that runs to the end of the line (outside strings).
- Strings are in double quotes and may not span lines.  Inside them `^`
  is a newline and `~` a double quote, as in Inform.  Dictionary words in
  NAME lists are strings too.
- Numbers are decimal (0-32767) or TI-style hex with a leading `>`
  (>1F).  A `>` directly followed by a hex digit after an operator or at
  the start of an expression is hex; otherwise it is "greater than".
- Punctuation: : , ( ) . ->  and the operators + - * / = <> < > <= >=.

Each token records its file and line for error messages."""

import re

KEYWORDS = {
    # declarations
    'INCLUDE', 'CONSTANT', 'GLOBAL', 'ARRAY', 'ATTRIBUTE', 'PROPERTY',
    'CLASS', 'OBJECT', 'ROOM', 'VERB', 'ROUTINE', 'PICTURE', 'END',
    # object bodies
    'IN', 'HAS', 'NOT', 'NAME',
    # statements
    'IF', 'ELSEIF', 'ELSE', 'WHILE', 'FOR', 'EACH', 'LOCAL', 'PRINT',
    'WRITE', 'MOVE', 'TO', 'REMOVE', 'GIVE', 'RETURN', 'TRUE', 'FALSE',
    'NOTHING', 'SELF',
    # expressions
    'AND', 'OR', 'MOD', 'HASNT', 'NOTIN',
    # grammar lines
    'REVERSE',
}

class TxaError(Exception):
    def __init__(self, file, line, msg):
        super().__init__(f'{file} line {line}: {msg}')
        self.file, self.line, self.msg = file, line, msg

class Tok:
    __slots__ = ('kind', 'value', 'text', 'file', 'line')
    def __init__(self, kind, value, text, file, line):
        self.kind, self.value, self.text, self.file, self.line = kind, value, text, file, line
    def __repr__(self):
        return f'{self.kind}:{self.value!r}'

SYMS = ['->', '<>', '<=', '>=', ':', ',', '(', ')', '.', '+', '-', '*', '/', '=', '<', '>']
ID = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
DEC = re.compile(r'[0-9]+')
HEX = re.compile(r'>[0-9A-Fa-f]+')

def tokenize(text, file='<source>'):
    toks = []
    for ln, raw in enumerate(text.splitlines(), 1):
        i, n, line = 0, len(raw), []
        def emit(kind, value, txt):
            line.append(Tok(kind, value, txt, file, ln))
        while i < n:
            c = raw[i]
            if c in ' \t':
                i += 1; continue
            if c == '!':
                break
            if c == '"':
                j = raw.find('"', i + 1)
                if j < 0:
                    raise TxaError(file, ln, 'string not closed on this line')
                s = raw[i + 1:j].replace('^', '\n').replace('~', '"')
                emit('STR', s, raw[i:j + 1]); i = j + 1; continue
            m = ID.match(raw, i)
            if m:
                w = m.group(0); u = w.upper()
                if u in KEYWORDS:
                    emit('KW', u, w)
                else:
                    emit('ID', w, w)
                i = m.end(); continue
            m = DEC.match(raw, i)
            if m:
                v = int(m.group(0))
                if v > 32767:
                    raise TxaError(file, ln, f'number {v} is larger than 32767')
                emit('NUM', v, m.group(0)); i = m.end(); continue
            m = HEX.match(raw, i)
            prev = line[-1] if line else None
            hex_ok = prev is None or prev.kind == 'SYM' and prev.value not in (')',) or prev.kind == 'KW' and prev.value not in ('TRUE', 'FALSE', 'NOTHING', 'SELF')
            if m and hex_ok:
                v = int(m.group(0)[1:], 16)
                if v > 0xFFFF:
                    raise TxaError(file, ln, f'hex number {m.group(0)} does not fit in 16 bits')
                emit('NUM', v - 0x10000 if v > 0x7FFF else v, m.group(0)); i = m.end(); continue
            for s in SYMS:
                if raw.startswith(s, i):
                    emit('SYM', s, s); i += len(s); break
            else:
                raise TxaError(file, ln, f'unexpected character {c!r}')
        if line:
            toks.extend(line)
            toks.append(Tok('NL', None, '', file, ln))
    toks.append(Tok('EOF', None, '', file, len(text.splitlines()) + 1))
    return toks
