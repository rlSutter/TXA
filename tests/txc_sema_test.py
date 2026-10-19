#!/usr/bin/env python3
"""txc_sema_test.py - TXA's semantic pass.

The spec's example (which names a Cellar it never declares, so it must
fail clearly), the example with the Cellar added, numbering, the object
tree, inheritance, actions, the dictionary, constants, and a set of
mistakes that must each get a clear message.  python3 tests/txc_sema_test.py"""
import os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from txc.sema import analyse
from txc.lexer import TxaError
T = os.path.join(ROOT, 'tests/txa'); LIB = [os.path.join(T, 'lib')]
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '  ' + str(detail)))
    fails += 0 if ok else 1

try:
    analyse(os.path.join(T, 'spec_example.txa'), LIB); check('spec example: Cellar undeclared', False, 'no error')
except TxaError as e:
    check('spec example: the undeclared Cellar is reported', 'unknown name Cellar' in e.msg and e.line == 14, e)

p = analyse(os.path.join(T, 'spec_cellar.txa'), LIB)
names = [o.sym.name for o in p.objects]
check('objects numbered in declaration order', names == ['Kitchen', 'Trapdoor', 'Lamp', 'Cellar'], names)
kit, trap, lamp, cel = p.objects
check('tree: Trapdoor then Lamp inside the Kitchen', kit.child == trap.number and trap.sibling == lamp.number and lamp.sibling == 0 and trap.parent == kit.number)
A = {n: i for i, n in enumerate(p.attrs)}; P = {n: i for i, n in enumerate(p.props)}
check('attributes numbered from 0 in declaration order', A['light'] == 0 and A['switchable'] == 17, A)
check('properties numbered from 1', P['DESC'] == 1 and P['DOWN'] == 12, P)
check('class inheritance: Door gives static and openable', trap.attrs == {A['static'], A['openable'], A['scenery']}, trap.attrs)
check('property values: string, object', kit.props[P['DESC']] == ('values', [('str', 'A cramped kitchen. A trapdoor is set in the floor.')])
      and kit.props[P['DOWN']] == ('values', [('obj', trap.number)]) and cel.props[P['UP']] == ('values', [('obj', 2)]))
check('routine properties kept for code generation', lamp.props[P['BEFORE']][0] == 'routine' and lamp.props[P['AFTER']][0] == 'routine')
check('actions in the order met: Rub (grammar), then the rule cases', p.actions == ['Rub', 'SwitchOn', 'SwitchOff'], p.actions)
check('dictionary: names and verb words, lower case', {'trapdoor', 'trap', 'door', 'brass', 'lamp', 'lantern', 'rub', 'polish'} <= p.dictionary)
check('NAME words on the object', lamp.names == ['brass', 'lamp', 'lantern'])
check('no warnings for the example', p.warnings == [], p.warnings)
exits = [P[x] for x in ['N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW', 'UP', 'DOWN', 'INSIDE', 'OUTSIDE']]
check('every ROOM has all twelve exits; those not given are NOTHING',
      all(n in kit.props for n in exits) and kit.props[P['N']] == ('values', [('num', 0)]) and kit.props[P['DOWN']] == ('values', [('obj', trap.number)]))
check('objects that are not rooms get none', P['N'] not in lamp.props)

def compile_src(src, lib=True):
    d = tempfile.mkdtemp()
    f = os.path.join(d, 'game.txa')
    open(f, 'w').write(('INCLUDE "DSK1.STDLIB"\n' if lib else '') + src)
    return analyse(f, LIB)

p = compile_src('''
CONSTANT B = A * 2 + 1
CONSTANT A = >10
GLOBAL count = B
CLASS Furniture
  HAS static supporter
  CAPACITY 4
END
CLASS Chair
  CLASS Furniture
  CAPACITY 1
END
ROOM Hall "Hall"
END
OBJECT Stool "stool" IN Hall
  CLASS Chair
  NAME "stool" "milking-stool" "threelegged"
  HAS NOT static
END
OBJECT Mouse "mouse"
  IN Stool
  NAME "mouse"
  HAS animate
END
ROUTINE CountKids obj
  LOCAL n, c
  FOR EACH c IN obj
    n = n + 1
  END
  RETURN n
END
''')
check('constants fold, in any order (>10 * 2 + 1 = 33)', p.constants['B'] == 33 and p.constants['A'] == 16)
st, mo = p.objects[1], p.objects[2]
check('class chain: Furniture then Chair then the object (CAPACITY 1, static removed)',
      st.props[p.props.index('CAPACITY')] == ('values', [('num', 1)]) and p.attrs.index('static') not in st.attrs and p.attrs.index('supporter') in st.attrs)
check('IN as a body line', mo.parent == st.number and st.child == mo.number)
check('a word over 12 letters: warned and cut', 'milking-stoo' in st.names and any('longer than 12' in w for w in p.warnings), p.warnings)
check('a routine with LOCALs and FOR EACH', [r.name for r in p.routines if r.name == 'CountKids'] and p.routines[-1].locals == ['OBJ', 'N', 'C'])

def bad(src, part, line=None):
    try:
        compile_src(src)
    except TxaError as e:
        return part in e.msg and (line is None or e.line == line + 1), f'{e.line}: {e.msg}'
    return False, 'no error'
for name, src, part, line in [
    ('declared twice (case ignored)', 'GLOBAL x\nGLOBAL X\n', 'already declared', 2),
    ('unknown attribute', 'OBJECT A "a"\n  NAME "a"\n  HAS lockd\nEND\n', 'unknown attribute "lockd"', 3),
    ('unknown property', 'OBJECT A "a"\n  NAME "a"\n  DSEC "x"\nEND\n', 'unknown property DSEC', 3),
    ('IN something that is not an object', 'OBJECT A "a" IN noun\n  NAME "a"\nEND\n', 'not an object', 1),
    ('an object inside itself', 'OBJECT A "a" IN B\n  NAME "a"\nEND\nOBJECT B "b" IN A\n  NAME "b"\nEND\n', 'inside itself', 1),
    ('action without its Sub routine', 'VERB "kick"\n  noun -> Kick\nEND\n', 'no routine KickSub', 2),
    ('rule case for an unknown action', 'OBJECT A "a"\n  NAME "a"\n  BEFORE\n    Jump: RETURN TRUE\n  END\nEND\n', 'no routine JumpSub', 4),
    ('bad grammar token', 'ROUTINE KickSub\nEND\nVERB "kick"\n  nuon -> Kick\nEND\n', 'not a grammar token', 4),
    ('unknown name in a routine', 'ROUTINE R\n  x = 1\nEND\n', 'unknown name x', 2),
    ('assigning to a routine', 'ROUTINE R\n  R = 1\nEND\n', 'not a variable', 2),
    ('too many arguments', 'ROUTINE R a\nEND\nROUTINE Q\n  R(1, 2)\nEND\n', 'takes 1 argument, not 2', 4),
    ('a bare name that is not a routine', 'ROUTINE R\n  noun\nEND\n', 'on its own does nothing', 2),
    ('HAS with something that is not an attribute', 'ROUTINE R\n  IF noun HAS DESC\n  END\nEND\n', 'unknown attribute', 2),
    ('FOR EACH variable not a LOCAL', 'ROUTINE R\n  FOR EACH noun IN player\n  END\nEND\n', 'must be a LOCAL', 2),
    ('constant defined by itself', 'CONSTANT X = Y\nCONSTANT Y = X + 1\n', 'in terms of itself', 2),
    ('class that is not a class', 'OBJECT A "a"\n  CLASS noun\n  NAME "a"\nEND\n', 'is not a class', 2),
    ('missing INCLUDE file', 'INCLUDE "DSK1.NOPE"\n', 'cannot find the file DSK1.NOPE', 1),
    ('array element with two indexes', 'ARRAY t 4\nROUTINE R\n  t(1, 2) = 3\nEND\n', 'one index', 3),
]:
    ok, detail = bad(src, part, line)
    check('error: ' + name, ok, detail)

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
