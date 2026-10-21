r"""dump.py - canonical text dumps of the compiler's stages, for comparing
the TI compiler (M5) with this one stage by stage.

Tokens (the lexer): one line a token, "line kind value", with the value
written so that both compilers produce exactly the same text:
  NUM    the number in decimal, as the lexer gave it
  STR    the string's characters inside double quotes, each one outside
         32-126, and every backslash or double quote, as \xHH
  ID KW ACT DICT SYM   the text as the lexer keeps it
  NL EOF               no value
Later stages (the tree, the symbols, routine code) add their formats here
as the TI compiler reaches them."""

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
