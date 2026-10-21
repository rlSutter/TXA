#!/usr/bin/env python3
"""txa_wrap.py - TXA source to 80 columns, for DV80 files on the TI.

A line longer than the width is broken inside its string, at a space,
using D1 (a string left open at the end of a line continues on the next:
the break reads as one space).  Continuation lines are indented to just
past the string's opening quote.  A trailing comment that makes a line
too long moves onto its own lines above it; a long comment line is
wrapped as several.  A long line with no string to break (or no space
in it to break at) is reported, not changed.  The wrapped
source compiles to exactly the same story image.

  python3 tools/txa_wrap.py in.txa [out.txa] [--width 80]"""
import sys

def wrap_line(line, width=80):
    """The line as lines of at most width: each break at a single space
    inside a string (D1 turns the break back into exactly one space)."""
    if len(line) <= width:
        return [line]
    indent = ' ' * (len(line) - len(line.lstrip(' ')) + 4)
    out, cur, first = [], line, True
    while len(cur) > width:
        ins = not first                       # a continuation line starts inside its string
        best = -1
        for i, c in enumerate(cur[:width]):
            if c == '"':
                ins = not ins
            elif c == ' ' and ins and i > len(indent) and cur[i - 1] != ' ' and i + 1 < len(cur) and cur[i + 1] != ' ':
                best = i
        if best < 0:
            raise ValueError(f'no single space inside a string to break at before column {width}: {cur[:50]}...')
        out.append(cur[:best])
        cur = indent + cur[best + 1:]
        first = False
        # the string is open on the new line only if the break was inside one
    out.append(cur)
    return out

def split_comment(line):
    """(code, comment): the comment starts at a ! outside any string."""
    ins = False
    for i, c in enumerate(line):
        if c == '"':
            ins = not ins
        elif c == '!' and not ins:
            return line[:i].rstrip(), line[i:]
    return line, ''

def wrap_comment(indent, comment, width):
    words, out, cur = comment[1:].split(), [], indent + '!'
    for w in words:
        if len(cur) + 1 + len(w) > width and cur.strip() != '!':
            out.append(cur); cur = indent + '!'
        cur += ' ' + w
    out.append(cur)
    return out

def wrap_text(text, width=80):
    res = []
    for n, line in enumerate(text.split('\n'), 1):
        try:
            if len(line) <= width:
                res.append(line); continue
            code, comment = split_comment(line)
            indent = line[:len(line) - len(line.lstrip(' '))]
            if comment:
                res.extend(wrap_comment(indent, comment, width))
            if code.strip():
                res.extend(wrap_line(code, width))
        except ValueError as e:
            raise ValueError(f'line {n}: {e}')
    return '\n'.join(res)

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    width = int(sys.argv[sys.argv.index('--width') + 1]) if '--width' in sys.argv else 80
    out = wrap_text(open(args[0]).read(), width)
    if len(args) > 1:
        open(args[1], 'w').write(out)
    else:
        sys.stdout.write(out)
