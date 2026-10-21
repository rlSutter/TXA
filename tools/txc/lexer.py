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
- `'word'` (single quotes) is a dictionary word's number, for the parser.
- `##Name` is the number of the action Name, as in Inform (`action = ##Take`).
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
    'REVERSE', 'EXTEND', 'FIRST', 'REPLACE',
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
    """Tokens for the text.  A string left open at the end of a line
    continues on the next (decision D1, for 80-column TI source): the line
    break becomes one space, trailing spaces before it and the next line's
    leading spaces are dropped, and the statement goes on after the closing
    quote.  Tokens carry the line they are on (a string: the line it starts)."""
    toks = []
    lines = text.splitlines()
    k = 0
    while k < len(lines):
        ln = k + 1
        raw = lines[k]; k += 1
        i, n, line = 0, len(raw), []
        def emit(kind, value, txt, at=None):
            line.append(Tok(kind, value, txt, file, at or ln))
        while i < n:
            c = raw[i]
            if c in ' \t':
                i += 1; continue
            if c == '!':
                break
            if c == '"':
                j = raw.find('"', i + 1)
                if j < 0:                           # D1: the string goes on
                    start = ln
                    parts = [raw[i + 1:].rstrip(' \t')]
                    while True:
                        if k >= len(lines):
                            raise TxaError(file, start, 'string not closed')
                        ln = k + 1
                        raw = lines[k]; k += 1
                        body = raw.lstrip(' \t')
                        j = body.find('"')
                        if j < 0:
                            parts.append(body.rstrip(' \t'))
                            continue
                        parts.append(body[:j])
                        off = len(raw) - len(body)
                        i, n = off + j + 1, len(raw)
                        break
                    s = ' '.join(parts)
                    s = s.replace('^', '\n').replace('~', '"')
                    emit('STR', s, '"' + s + '"', at=start); continue
                s = raw[i + 1:j].replace('^', '\n').replace('~', '"')
                emit('STR', s, raw[i:j + 1]); i = j + 1; continue
            if c == "'":                           # 'lamp': a dictionary word
                j = raw.find("'", i + 1)
                if j < 0 or j == i + 1:
                    raise TxaError(file, ln, "a dictionary word in single quotes is not closed")
                emit('DICT', raw[i + 1:j].lower(), raw[i:j + 1]); i = j + 1; continue
            if raw.startswith('##', i):             # ##Take: an action's number
                m = ID.match(raw, i + 2)
                if not m:
                    raise TxaError(file, ln, 'expected an action name after ##')
                emit('ACT', m.group(0), raw[i:m.end()]); i = m.end(); continue
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
                if v > 32768:                       # 32768 only after a minus sign (the parser checks)
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
    toks.append(Tok('EOF', None, '', file, len(lines) + 1))
    return toks
