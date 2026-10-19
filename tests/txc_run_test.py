#!/usr/bin/env python3
"""txc_run_test.py - compile TXA programs and run them on the Python VM.

The language end to end: arithmetic and precedence, 16-bit overflow,
signed division, constants, globals, arrays, recursion, loops, logic,
the object tree, attributes, articles, print-or-run properties, rule
cases, run-time errors; and image facts (header, checksum, alignment,
determinism).  python3 tests/txc_run_test.py"""
import os, sys, tempfile, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from txc.codegen import compile_file, encode, decode, choose_abbrevs
from txc.txvm import run_image, VM
from txc.opcodes import HDR, HEADER_SIZE
T = os.path.join(ROOT, 'tests/txa'); LIB = [os.path.join(T, 'lib')]
DATE = datetime.date(2026, 10, 19)
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)))
    fails += 0 if ok else 1

img, info = compile_file(os.path.join(T, 'run1.txa'), LIB, date=DATE)
out = run_image(img)
want = """Arithmetic: 14 20 -3 -1 -32768
Constants and globals: 30 Hello from a global.
Factorial 7 = 5040
Arrays: 58
Logic: yes
In the kitchen: an oak table, some coins, Ada.
That is 3 things; on the table: the 1.
"""
lines = out.splitlines()
check('arithmetic, constants, globals, recursion, arrays, logic', out.startswith(want[:want.index('In the')]), out)
check('FOR EACH, articles (an, some, proper)', 'In the kitchen: an oak table, some coins, Ada.' in out, out)
check('PRINTA forms', 'The apple / an apple / Some coins / Ada / Kitchen' in out, out)
check('a property routine with SELF; print-or-run', 'A red apple, on the table.\nA red apple.\nA cramped kitchen.\n' in out, out)
check('GIVE with NOT and two attributes; HAS', 'Attributes: 011' in out, out)
check('MOVE, IN, NOTIN', 'Tree: the apple moved' in out, out)
check('REMOVE', 'Parent after REMOVE: 0 an oak table, some coins, Ada.' in out, out)
check('ran to the end', out.rstrip().endswith('Done.'), out)

# image facts
check('magic, version, title, date', img[:4] == b'TXA1' and img[HDR['title']:HDR['title'] + 4] == b'RUN1' and img[HDR['build_date']:HDR['build_date'] + 6] == b'261019')
check('checksum', int.from_bytes(img[HDR['checksum']:HDR['checksum'] + 2], 'big') == sum(img[HEADER_SIZE:]) & 0xFFFF)
check('length on a 4-byte boundary and recorded', len(img) % 4 == 0 and int.from_bytes(img[10:14], 'big') == len(img))
img2, _ = compile_file(os.path.join(T, 'run1.txa'), LIB, date=DATE)
check('the same source gives the same bytes', img == img2)
check('proper and plural attribute numbers in the header', img[HDR['attr_proper']] == info['program'].attrs.index('proper') and img[HDR['attr_plural']] == info['program'].attrs.index('plural'))

# text compression
strings = ['the door is open. ', 'the door is closed. ', 'You see the door.']
ab = choose_abbrevs(strings)
check('substitution table: best tokens first', ab[:2] == ['door ', 'the '] or ab[0] in ('the ', 'door '), ab)
for s in strings + ['', 'no letters 123!', 'line^two'.replace('^', '\n')]:
    e = encode(s, ab)
    if decode(e, 0, ab) != s:
        check('encode/decode round trip', False, repr(s)); break
else:
    check('encode/decode round trip', True)
c = sum(len(encode(s, ab)) - 1 for s in strings); r = sum(len(s) for s in strings)
check('compression saves space', c < r, f'{c} vs {r}')

# the spec example compiles and runs a rule case
def build(src):
    d = tempfile.mkdtemp(); f = os.path.join(d, 'game.txa')
    open(f, 'w').write(src)
    return compile_file(f, LIB, date=DATE)[0]
img = build(open(os.path.join(T, 'spec_cellar.txa')).read() + '''
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
  action = ##SwitchOff
  PRINT "after: ", Lamp.AFTER(), " lit: ", Lamp HAS light
  action = ##SwitchOn
  PRINT "after: ", Lamp.AFTER(), " lit: ", Lamp HAS light
END
''')
out = run_image(img)
check('rule cases: no case falls through to the action; a case returns TRUE',
      out == 'You rub the brass lamp. Nothing happens.\nThe glass is too hot to rub.\n(stopped)\nafter: 0 lit: 0\nafter: 0 lit: 1\n', out)

# maps that change: routine exits replaced by rooms and back, exits opened on rooms that had none
img, _ = compile_file(os.path.join(T, 'dynmap.txa'), LIB, date=DATE)
out = run_image(img)
check('dynamic map: routine exit, then a room, a routine again, a string; an exit opened and closed',
      out == ('The water is too deep.\n-> no way\n-> Causeway\n-> Cave\n(a hidden way)\n-> Cave\n'
             'A wall of fog.-> Shore\n'            # a string prints (no new line) and gives 1: object 1
             '\n-> no way\n-> Cave\n-> no way\nExits on Cave: 00 (all present)\n'), out)

# run-time errors
for name, body, part in [
    ('division by zero', 'LOCAL z\n  PRINT 1 / z', 'division by zero'),
    ('array index', 'ARRAYX', 'outside array'),
    ('property not there', 'Box.CAPACITY = 3', 'has no property'),
    ('moving into itself', 'MOVE Box TO Box', 'inside itself'),
    ('an endless loop', 'WHILE TRUE\n  END', 'too many steps'),
]:
    src = 'INCLUDE "DSK1.STDLIB"\nARRAY a 3\nOBJECT Box "box"\n  NAME "box"\nEND\nROUTINE Main\n  ' + body.replace('ARRAYX', 'a(3) = 1') + '\nEND\n'
    out = run_image(build(src), max_steps=200_000)
    check('run-time error: ' + name, '[TXA run-time error:' in out and part in out, out)

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
