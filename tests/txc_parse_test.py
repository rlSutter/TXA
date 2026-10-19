#!/usr/bin/env python3
"""txc_parse_test.py - the TXA lexer and parser.

Parses the specification's example and a set of constructs, checking
the tree; then checks that malformed source gets a clear message with
the right line.  python3 tests/txc_parse_test.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from txc.parser import parse
from txc.lexer import tokenize, TxaError
from txc import ast as A
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '  ' + str(detail)))
    fails += 0 if ok else 1

# --- the spec's example
src = open(os.path.join(ROOT, 'tests/txa/spec_example.txa')).read()
d = parse(src, 'spec_example.txa')
check('spec example: 6 declarations', [type(x).__name__ for x in d] == ['Include', 'ObjDecl', 'ObjDecl', 'ObjDecl', 'Verb', 'Routine'], d)
kitchen, trap, lamp, verb, rub = d[1:]
check('ROOM with short name and properties', kitchen.kind == 'ROOM' and kitchen.short == 'Kitchen'
      and kitchen.body[1] == A.PropVal('DOWN', [A.Name('Trapdoor')]) and kitchen.body[2] == A.Has([('light', True)]))
check('OBJECT IN parent, CLASS, NAME words', trap.parent == 'Kitchen' and trap.body[0] == A.Classes(['Door'])
      and trap.body[1] == A.Names(['trapdoor', 'trap', 'door']))
before = lamp.body[3]; after = lamp.body[4]
check('BEFORE block with a case', isinstance(before, A.PropBlock) and before.name == 'BEFORE'
      and before.body[0].actions == ['Rub'] and isinstance(before.body[0].body[0], A.If))
check('AFTER cases with statements on the label line', [c.actions for c in after.body] == [['SwitchOn'], ['SwitchOff']]
      and after.body[1].body[0] == A.Give(A.Const('SELF'), [('light', False)]))
check('IF self HAS on', before.body[0].body[0].arms[0][0] == A.Binary('HAS', A.Const('SELF'), A.Name('on')))
check('VERB grammar line', verb.words == ['rub', 'polish'] and verb.lines[0] == A.GLine([A.GTok('slot', 'noun', None)], 'Rub', False))
check('PRINT with (the)', rub.body[0] == A.Print([A.PItem(None, A.Str('You rub ')), A.PItem('the', A.Name('noun')), A.PItem(None, A.Str('. Nothing happens.'))], True))

# --- more constructs
d = parse('''
CONSTANT MAXCOINS = 12
GLOBAL score = 0
ARRAY slots 10
ARRAY primes = 2, 3, 5, 7
ATTRIBUTE haunted cursed
PROPERTY weight
PICTURE LampRoom "DSK2.LAMPROOM_P"
VERB "put" "place"
  multiheld "in" container -> Insert
  multiheld "on" noun=IsSupporter -> PutOn
  "down" multiheld -> Drop
END
VERB "give"
  creature held -> Give REVERSE
END
ROUTINE Weigh obj, extra
  LOCAL total, n
  total = obj.weight + extra * 2 - -3
  FOR EACH n IN obj
    total = total + Weigh(n, 0)
  END
  IF total > >1F AND NOT (obj HASNT light)
    WRITE "Heavy: ", (number) total
    PRINT
  ELSEIF total = 0 OR obj NOTIN player
    RETURN FALSE
  ELSE
    slots(3) = total MOD 7
  END
  WHILE n < 10
    n = n + 1
  END
  MOVE obj TO player
  REMOVE obj
  PICTURE LampRoom
  obj.weight = 0
  RETURN total
END
OBJECT Box "box"
  DESC
    PRINT "A box, ", (a) self, "."
  END
  LIFE
    Ask, Tell:
      PRINT "It says nothing."
    Attack: RETURN TRUE
    Give, Remove: PRINT "Keyword-named actions."
  END
END
''', 't.txa')
check('CONSTANT, GLOBAL, ARRAY (size, values), ATTRIBUTE, PROPERTY, PICTURE',
      d[0] == A.Constant('MAXCOINS', A.Num(12)) and d[1] == A.Global('score', A.Num(0)) and d[2] == A.Array('slots', 10, None)
      and d[3] == A.Array('primes', None, [A.Num(2), A.Num(3), A.Num(5), A.Num(7)]) and d[4] == A.Attribute(['haunted', 'cursed'])
      and d[6] == A.Picture('LampRoom', 'DSK2.LAMPROOM_P'))
v = d[7]
check('grammar: literal words, filters, leading preposition', v.lines[0].tokens[1] == A.GTok('word', 'in', None)
      and v.lines[1].tokens[2] == A.GTok('slot', 'noun', 'IsSupporter') and v.lines[2].tokens[0] == A.GTok('word', 'down', None))
check('grammar: REVERSE', d[8].lines[0].reverse)
r = d[9]
check('ROUTINE parameters and LOCAL', r.params == ['obj', 'extra'] and r.body[0] == A.Local(['total', 'n']))
e = r.body[1].value
check('precedence: a.p + b * 2 - -3', e == A.Binary('-', A.Binary('+', A.PropRef(A.Name('obj'), 'weight'), A.Binary('*', A.Name('extra'), A.Num(2))), A.Num(-3)), e)
check('FOR EACH and a call', isinstance(r.body[2], A.ForEach) and r.body[2].body[0].value.right == A.Call(A.Name('Weigh'), [A.Name('n'), A.Num(0)]))
cond = r.body[3].arms[0][0]
check('hex, AND, NOT, HASNT', cond == A.Binary('AND', A.Binary('>', A.Name('total'), A.Num(31)), A.Unary('NOT', A.Binary('HASNT', A.Name('obj'), A.Name('light')))), cond)
check('WRITE with (number), bare PRINT', r.body[3].arms[0][1][0].newline is False and r.body[3].arms[0][1][0].items[1].form == 'number'
      and r.body[3].arms[0][1][1] == A.Print([], True))
check('ELSEIF with OR and NOTIN; array element assignment', r.body[3].arms[1][0].op == 'OR' and r.body[3].orelse[0].target == A.Call(A.Name('slots'), [A.Num(3)]))
check('WHILE, MOVE TO, REMOVE, PICTURE, property assignment, RETURN',
      [type(s).__name__ for s in r.body[4:]] == ['While', 'Move', 'Remove', 'PicStmt', 'Assign', 'Return'])
box = d[10]
check('property routine block (DESC) and multi-action case', isinstance(box.body[0], A.PropBlock) and isinstance(box.body[0].body[0], A.Print)
      and box.body[1].body[0].actions == ['Ask', 'Tell'] and box.body[1].body[1].actions == ['Attack'] and box.body[1].body[2].actions == ['Give', 'Remove'])
check('keywords and names ignore case; names keep their spelling',
      parse('object Coin "coin"\n  has Valuable\nend\n')[0] == A.ObjDecl('OBJECT', 'Coin', 'coin', None, [A.Has([('Valuable', True)])]))
check('strings: ^ and ~', tokenize('PRINT "a^b ~hi~"')[1].value == 'a\nb "hi"')

# --- errors
def err(src, line, part):
    try:
        parse(src, 'e.txa')
    except TxaError as x:
        return x.line == line and part in x.msg, f'{x.line}: {x.msg}'
    return False, 'no error'
for name, src, line, part in [
    ('unclosed string', 'ROUTINE A\n  PRINT "oops\nEND\n', 2, 'not closed'),
    ('missing END in an object', 'OBJECT A "a"\n  HAS light\n', 3, 'has no END'),
    ('number too large', 'CONSTANT X = 40000\n', 1, 'larger than 32767'),
    ('chained comparison', 'ROUTINE A\n  IF 1 < 2 < 3\n  END\nEND\n', 2, 'cannot be chained'),
    ('bad assignment target', 'ROUTINE A\n  3 = 4\nEND\n', 2, 'can be assigned'),
    ('junk after a statement', 'ROUTINE A\n  MOVE a TO b c\nEND\n', 2, 'end of the line'),
    ('grammar line without ->', 'VERB "x"\n  noun\nEND\n', 2, 'grammar token or ->'),
    ('a statement at top level', 'PRINT "hi"\n', 1, 'cannot start a declaration'),
    ('more than 7 arguments', 'ROUTINE A\n  B(1,2,3,4,5,6,7,8)\nEND\n', 2, 'at most 7'),
    ('stray character', 'ROUTINE A\n  x = 1 ; 2\nEND\n', 2, 'unexpected character'),
]:
    ok, detail = err(src, line, part)
    check('error: ' + name, ok, detail)

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
