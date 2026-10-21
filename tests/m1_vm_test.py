#!/usr/bin/env python3
"""m1_vm_test.py - the assembly VM against the Python reference VM.

Each program is compiled once; the image runs on the Python VM
(tools/txc/txvm.py) and, inside a cartridge, on the TI engine in the
simulator.  Every character the engine passes to CHOUT is recorded; the
two transcripts must match exactly.  Also checks the screen (word wrap,
scrolling, [MORE]) against a Python model of output.a99's rules, the
opcode table against opcodes.py, and a damaged story being refused.

  python3 tests/m1_vm_test.py [--png]"""
import os, sys, tempfile, datetime, re, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import sim9900 as S, render80 as R, build
from txc.codegen import compile_file
from txc.txvm import run_image
from txc.opcodes import OPS
T = os.path.join(ROOT, 'tests/txa'); LIB = [os.path.join(T, 'lib')]
DATE = datetime.date(2026, 10, 19)
PNG = '--png' in sys.argv
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:3000]))
    fails += 0 if ok else 1

def run_engine(image, max_steps=40_000_000):
    """Run the engine with this story; returns (transcript, machine, reason)."""
    cart, _ = build.engine_cart(image)
    sy = build.symbols(os.path.join(ROOT, 'build/engine.equ'))
    m = S.Machine(cart, f18a=True, pages=128); cpu = S.CPU(m)
    cpu.pc = m.rw(m.rw(0x6006) + 2)
    out, steps, pending, hold_until, free_until, fatal_seen = [], 0, 0, 0, 0, False
    chout, halt, waitky, fatal = sy['CHOUT'], sy['VMHALT'], sy['WAITKY'], sy['FATAL']
    while steps < max_steps:
        pc = cpu.pc
        if pc == chout:
            out.append(chr(m.rw(0x8300) & 0xFF))
        elif pc == halt:
            return ''.join(out), m, 'halt'
        elif pc == fatal:
            fatal_seen = True
        elif pc == waitky:
            if fatal_seen:                     # the message is on the screen now
                return ''.join(out), m, 'fatal'
            pending += 1                       # one key press per wait
        # press a key for each wait: down for a while, then up for a while,
        # so the keyboard routine sees a new press every time
        if hold_until and steps >= hold_until:
            m.held = None; hold_until = 0; free_until = steps + 20_000
        elif pending and not hold_until and steps >= free_until:
            m.held = S.key_pos(' '); hold_until = steps + 20_000; pending -= 1
        cpu.step(); steps += 1
    return ''.join(out), m, 'steps'

def compile_src(src, name='game'):
    d = tempfile.mkdtemp(); f = os.path.join(d, name + '.txa')
    open(f, 'w').write(src)
    return compile_file(f, LIB, date=DATE)[0]

def same(name, image, max_steps=40_000_000):
    want = run_image(image, max_steps=2_000_000)
    t0 = time.time()
    got, m, why = run_engine(image, max_steps)
    ok = got == want and why == 'halt'
    if not ok:
        i = next((k for k in range(min(len(got), len(want))) if got[k] != want[k]), min(len(got), len(want)))
        detail = f'stopped by {why}; first difference at {i}:\n  python: {want[i-40:i+60]!r}\n  engine: {got[i-40:i+60]!r}'
    else:
        detail = ''
    check(f'{name}: engine transcript = Python transcript ({len(want)} chars, {time.time() - t0:.0f}s)', ok, detail)
    return m

# the opcode table in vm.a99 matches opcodes.py
src = open(os.path.join(ROOT, 'src/vm.a99')).read()
tab = re.findall(r'DATA ((?:\w+,?)+)', src[src.index('OPTAB  DATA'):src.index('OPTPAD EQU')])
entries = [e for line in tab for e in line.split(',') if e]
names = {code: name for code, name, *_ in OPS}
handler_for = {'NOP': 'OPNOP', 'PUSHB': 'OPPSHB', 'PUSHW': 'OPPSHW', 'PUSH0': 'OPPSH0', 'PUSH1': 'OPPSH1', 'POP': 'OPPOP',
    'DUP': 'OPDUP', 'LOADSELF': 'OPSELF', 'LOAD': 'OPLOAD', 'STORE': 'OPSTOR', 'INC': 'OPINC', 'DEC': 'OPDEC', 'ADD': 'OPADD',
    'SUB': 'OPSUB', 'MUL': 'OPMUL', 'DIV': 'OPDIV', 'MOD': 'OPMOD', 'NEG': 'OPNEG', 'NOT': 'OPNOT', 'EQ': 'OPEQ', 'NE': 'OPNE',
    'LT': 'OPLT', 'GT': 'OPGT', 'LE': 'OPLE', 'GE': 'OPGE', 'JMP': 'OPJMP', 'JZ': 'OPJZ', 'JNZ': 'OPJNZ', 'CALL': 'OPCALL',
    'CALLV': 'OPCLLV', 'RET': 'OPRET', 'RTRUE': 'OPRTRU', 'RFALSE': 'OPRFAL', 'PARENT': 'OPPAR', 'CHILD': 'OPCHLD',
    'SIBLING': 'OPSIB', 'MOVE': 'OPMOVE', 'REMOVE': 'OPREM', 'IN': 'OPIN', 'HASATTR': 'OPHAS', 'SETATTR': 'OPSETA',
    'CLRATTR': 'OPCLRA', 'GETPROP': 'OPGETP', 'PUTPROP': 'OPPUTP', 'PROPLEN': 'OPPLEN', 'RUNPROP': 'OPRUNP',
    'CALLPROP': 'OPCLLP', 'GETPROPN': 'OPGTPN', 'ALOAD': 'OPALD', 'ASTORE': 'OPAST', 'ALEN': 'OPALEN', 'PRINTS': 'OPPRS',
    'PRINTV': 'OPPRV', 'PRINTN': 'OPPRN', 'PRINTO': 'OPPRO', 'PRINTC': 'OPPRC', 'NEWLINE': 'OPNL', 'STYLE': 'OPSTYL',
    'PRINTA': 'OPPRA', 'READ': 'OPREAD', 'READKEY': 'OPRKEY', 'RANDOM': 'OPRAND', 'QUIT': 'OPQUIT', 'RESTART': 'OPRST',
    'SAVE': 'OPSAVE', 'RESTORE': 'OPREST', 'UNDOSAVE': 'OPUSAV', 'UNDO': 'OPUNDO', 'PICTURE': 'OPPIC', 'STATUS': 'OPSTAT',
    'SOUND': 'OPSND', 'HASATTRV': 'OPHASV', 'ALOADV': 'OPALDV', 'ASTOREV': 'OPASTV', 'TOKENIZE': 'OPTOKN',
    'FRESH': 'OPFRSH', 'ISNAME': 'OPISNM', 'FILTERN': 'OPFLTN', 'ACOPY': 'OPACPY', 'CLS': 'OPCLS', 'MUSIC': 'OPMUS'}
bad = [(hex(i), e, names.get(i)) for i, e in enumerate(entries) if (names.get(i) and handler_for[names[i]] != e) or (not names.get(i) and e != 'BADOP')]
check(f'OPTAB matches opcodes.py ({len(names)} opcodes)', not bad and len(entries) >= max(names) + 1, bad)

# programs
img = compile_file(os.path.join(T, 'run1.txa'), LIB, date=DATE)[0]
m = same('run1 (the language end to end)', img)
if PNG:
    os.makedirs(os.path.join(ROOT, 'build/shots'), exist_ok=True); R.render(m, os.path.join(ROOT, 'build/shots/m1-run1.png'))

img = compile_src(open(os.path.join(T, 'spec_cellar.txa')).read() + '''
ROUTINE Main
  noun = Lamp
  action = ##Rub
  IF Lamp.BEFORE() = FALSE
    RubSub()
  END
  GIVE Lamp on
  IF Lamp.BEFORE()
    PRINT "(stopped)"
  END
  action = ##SwitchOn
  PRINT "after: ", Lamp.AFTER(), " lit: ", Lamp HAS light, " / ", (The) Trapdoor, " leads to ", (the) Trapdoor.DOOR_TO
END
''')
same('the spec example: rule cases, SELF, properties', img)

img = compile_src('''INCLUDE "DSK1.STDLIB"
ARRAY rolls 6
ROUTINE Main
  LOCAL i, r
  RANDOM(-7)
  WHILE i < 40
    r = RANDOM(6)
    rolls(r - 1) = rolls(r - 1) + 1
    WRITE r
    i = i + 1
  END
  PRINT
  i = 0
  WHILE i < 6
    WRITE rolls(i), " "
    i = i + 1
  END
  PRINT
  PRINT 32767 + 1, " ", -32768 - 1, " ", 300 * 300, " ", -32768 / -1, " ", 7 / -2, " ", 7 MOD -2, " ", -7 MOD -2
  PRINT 1 < 2, 2 < 1, -1 < 1, 1 <= 1, 2 >= 3, 5 <> 5, 5 = 5, NOT 0, NOT 7
END
''')
same('random numbers, 16-bit wrap, signed division, comparisons', img)

img = compile_file(os.path.join(T, 'dynmap.txa'), LIB, date=DATE)[0]
same('dynamic map: exits changed while running (PUTPROP kinds)', img)

for name, body, part in [
    ('division by zero', 'LOCAL z\n  PRINT 1 / z', 'division'),
    ('array index', 'a(3) = 1', 'outside'),
    ('property not there', 'Box.CAPACITY = 3', 'property'),
    ('moving into itself', 'MOVE Box TO Box', 'inside itself'),
    ('object that does not exist', 'LOCAL o\n  o = 99\n  MOVE o TO Box', 'does not exist'),
]:
    img = compile_src('INCLUDE "DSK1.STDLIB"\nARRAY a 3\nOBJECT Box "box"\n  NAME "box"\nEND\nROUTINE Main\n  PRINT "Before."\n  ' + body + '\n  PRINT "Never."\nEND\n')
    same('run-time error: ' + name, img)

# word wrap, scrolling, [MORE]: 70 lines of varied widths
words = 'the lamp throws a long thin beam across water that has gone quite still tonight and nobody answers'.split()
lines = []
for n in range(70):
    k = 3 + (n * 7) % 23
    lines.append(' '.join(words[(n + j) % len(words)] for j in range(k)))
src = 'INCLUDE "DSK1.STDLIB"\nROUTINE Main\n' + ''.join(f'  PRINT "{n}: {l}"\n' for n, l in enumerate(lines)) + \
      '  WRITE "averyveryverylongwordthatcannotfitonanylineatallbecauseitkeepsgoingandgoingandgoing!!"\n  PRINT " end."\nEND\n'
img = compile_src(src)
m = same('70 lines: word wrap, scrolling, [MORE]', img, 80_000_000)
def model(text, width=80):
    """output.a99's rules: break at the last space (dropped); cut words longer than a line."""
    out, line = [], ''
    for ch in text:
        if ch == '\n':
            out.append(line); line = ''; continue
        if len(line) < width:
            line += ch; continue
        if ch == ' ':
            out.append(line); line = ''; continue
        i = line.rfind(' ')
        if i < 0:
            out.append(line); line = ch
        else:
            out.append(line[:i]); line = line[i + 1:] + ch
    if line:
        out.append(line)
    return out
want = model(run_image(img))
screen = (R.screen(m) + '\n' * 30).splitlines()[1:30]   # the 29 rows of the text window
tail = want[-29:]                                       # (the harness stops before the end message scrolls)
check('screen: the last lines, wrapped as the model says', [s.rstrip() for s in screen[:len(tail)]] == [t.rstrip() for t in tail],
      '\n'.join(f'{a!r}\n{b!r}' for a, b in zip(screen, tail) if a.rstrip() != b.rstrip())[:2000])
if PNG:
    R.render(m, os.path.join(ROOT, 'build/shots/m1-wrap.png'))

# page crossings: a long routine (about 16K of bytecode) whose LOAD and
# STORE operands, jumps and words fall on every alignment, including the
# last byte of a 4K page (the fast paths' special case)
body = []
for i in range(1400):
    body.append(f'  a = a + b * {i % 7 + 1} - c + {i * 37 % 900 + 200} - {i * 37 % 900 + 200}' if i % 3 else f'  c = c + 1')
    if i % 50 == 0:
        body.append(f'  IF a > 1000\n    a = a - 1000\n    g = g + 1\n  END')
src = 'INCLUDE "DSK1.STDLIB"\nGLOBAL g\nROUTINE Main\n  LOCAL a, b, c\n  b = 3\n' + '\n'.join(body) + '\n  PRINT a, " ", b, " ", c, " ", g\nEND\n'
img = compile_src(src)
same(f'page crossings: a {len(img) // 1024}K story, LOAD/STORE/jumps at every alignment', img, 80_000_000)

# text styles: bold and reverse are colours (position attributes), underline a glyph set
img = compile_src('''INCLUDE "DSK1.STDLIB"
ROUTINE Main
  WRITE "plain "
  STYLE(1)
  WRITE "bold "
  STYLE(2)
  WRITE "under line "
  STYLE(4)
  WRITE "rev "
  STYLE(5)
  WRITE "boldrev"
  STYLE(3)
  WRITE " both"
  STYLE(0)
  PRINT " end"
END
''')
m = same('styles: the transcript is unaffected', img)
row = bytes(m.vram[80:160]); att = R.attrs(m, 1)
segs = [('plain ', 0xE1, 0), ('bold ', 0xF1, 0), ('under line ', 0xE1, 0x80), ('rev ', 0x1E, 0), ('boldrev', 0x1F, 0), (' both', 0xF1, 0x80), (' end', 0xE1, 0)]
pos, ok, why = 0, True, []
for text, a, ul in segs:
    for ch in text:
        if row[pos] != ord(ch) | ul or att[pos] != a:
            ok = False; why.append((pos, ch, hex(row[pos]), hex(att[pos]), hex(a)))
        pos += 1
check('styles on screen: bold white, underline glyphs, reverse swapped, combined', ok and att[pos] == 0xE1, why[:6])
check('position attributes on; status line in reverse colours; normal gray and bold white in the palette',
      m.vregs[50] & 2 and set(R.attrs(m, 0)) == {0x1E} and m.palette.get(14) == 0xBBB and m.palette.get(15) == 0xFFF)
check('underlined font: patterns 160-254 with the bottom row filled', all(m.vram[0x1800 + (c | 0x80) * 8 + 7] == 0xFC for c in range(32, 127)))
if PNG:
    R.render(m, os.path.join(ROOT, 'build/shots/m1-styles.png'))

# a damaged story is refused
img = bytearray(compile_file(os.path.join(T, 'run1.txa'), LIB, date=DATE)[0]); img[200] ^= 0xFF
got, m, why = run_engine(bytes(img), 20_000_000)
check('a damaged story is refused (checksum)', why == 'fatal' and 'damaged' in R.screen(m), R.screen(m)[:300])

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
