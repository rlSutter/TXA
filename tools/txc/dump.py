r"""dump.py - canonical text dumps of the compiler's stages, for comparing
the TI compiler (M5) with this one stage by stage.

Tokens (the lexer): one line a token, "line kind value", with the value
written so that both compilers produce exactly the same text:
  NUM    the number in decimal, as the lexer gave it
  STR    the string's characters inside double quotes, each one outside
         32-126, and every backslash or double quote, as \xHH
  ID KW ACT DICT SYM   the text as the lexer keeps it
  NL EOF               no value
The tree (the parser): a byte encoding both compilers write, pre-order:
  >00 None   >01 True   >02 False   >03 an integer (a 16-bit word)
  >04 a string (length word, then its bytes)
  >05 a list (count word, then the items)   >06 a tuple (count byte, items)
  >07 a node: its type (a byte: its place in NODES, from 1), its line (a
      word), then its fields in ast.py's order
All words high byte first.  tree_bytes(decls) writes it; tree_text(b)
reads it back as indented text, for showing differences.
Later stages (the symbols, routine code) add their formats here as the TI
compiler reaches them."""

def esc(s):
    return '"' + ''.join(c if 32 <= ord(c) < 127 and c not in '\\"' else '\\x%02X' % (ord(c) & 0xFF) for c in s) + '"'

def tokens(toks):
    out = []
    for t in toks:
        if t.kind in ('NL', 'EOF'):
            out.append(f'{t.line} {t.kind}')
        elif t.kind == 'STR':
            out.append(f'{t.line} STR {esc(t.value)}')
        else:
            out.append(f'{t.line} {t.kind} {t.value}')
    return '\n'.join(out) + '\n'


from . import ast as _A
NODES = [_A.Include, _A.Constant, _A.Global, _A.Array, _A.Attribute, _A.Property, _A.Picture,
         _A.SoundDecl, _A.ObjDecl, _A.Verb, _A.Extend, _A.Replace, _A.GLine, _A.GTok, _A.Routine,
         _A.Has, _A.Classes, _A.InParent, _A.Names, _A.PropVal, _A.PropBlock, _A.Case, _A.If,
         _A.While, _A.ForEach, _A.Local, _A.Print, _A.PItem, _A.Move, _A.Remove, _A.Give,
         _A.Return, _A.PicStmt, _A.Assign, _A.ExprStmt, _A.Num, _A.Str, _A.Name, _A.Const,
         _A.Unary, _A.Binary, _A.PropRef, _A.ActionRef, _A.DictWord, _A.Call]
NODE_ID = {c: i + 1 for i, c in enumerate(NODES)}

def _w(n):
    return bytes([(n >> 8) & 0xFF, n & 0xFF])

def _enc(v, out):
    if v is None: out += b'\x00'
    elif v is True: out += b'\x01'
    elif v is False: out += b'\x02'
    elif isinstance(v, int): out += b'\x03' + _w(v & 0xFFFF)
    elif isinstance(v, str):
        b = v.encode('latin-1'); out += b'\x04' + _w(len(b)) + b
    elif isinstance(v, list):
        out += b'\x05' + _w(len(v))
        for x in v: _enc(x, out)
    elif isinstance(v, tuple):
        out += b'\x06' + bytes([len(v)])
        for x in v: _enc(x, out)
    elif isinstance(v, _A.Node):
        out += b'\x07' + bytes([NODE_ID[type(v)]]) + _w(v.line or 0)
        for f in v.fields: _enc(getattr(v, f), out)
    else:
        raise TypeError(f'cannot encode {v!r}')

def tree_bytes(decls):
    out = bytearray(); _enc(decls, out); return bytes(out)

def tree_text(b):
    """The encoding read back as indented text (one value a line)."""
    lines, i = [], 0
    def rd(depth, label=''):
        nonlocal i
        pad = '  ' * depth + (label + ': ' if label else '')
        t = b[i]; i += 1
        if t == 0: lines.append(pad + 'None')
        elif t == 1: lines.append(pad + 'True')
        elif t == 2: lines.append(pad + 'False')
        elif t == 3:
            v = (b[i] << 8) | b[i + 1]; i += 2; lines.append(pad + str(v - 0x10000 if v > 0x7FFF else v))
        elif t == 4:
            n = (b[i] << 8) | b[i + 1]; i += 2; lines.append(pad + repr(b[i:i + n].decode('latin-1'))); i += n
        elif t == 5:
            n = (b[i] << 8) | b[i + 1]; i += 2; lines.append(pad + f'[{n}]')
            for _ in range(n): rd(depth + 1)
        elif t == 6:
            n = b[i]; i += 1; lines.append(pad + f'({n})')
            for _ in range(n): rd(depth + 1)
        elif t == 7:
            k = b[i]; ln = (b[i + 1] << 8) | b[i + 2]; i += 3
            cls = NODES[k - 1] if 1 <= k <= len(NODES) else None
            lines.append(pad + f'{cls.__name__ if cls else "?" + str(k)} @{ln}')
            for f in (cls.fields if cls else ()): rd(depth + 1, f)
        else:
            lines.append(pad + f'?byte {t:02X}'); i = len(b)
    try:
        while i < len(b):
            rd(0)
    except IndexError:
        lines.append('<the encoding ends here, unfinished>')
    return '\n'.join(lines) + '\n'
