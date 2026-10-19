#!/usr/bin/env python3
"""m2_parser_test.py - the standard library's parser on the Python VM.

Plays tests/txa/m2/m2game.txa with the commands in m2game.cmds and
compares the transcript with m2game.expected, a reviewed reference, then
checks the parser's behaviours one by one in it (so a failure says what
broke).  Rebuild the reference with --update after reviewing a change.

  python3 tests/m2_parser_test.py [--update]"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from txc.codegen import compile_file
from txc.txvm import run_image
D = os.path.join(ROOT, 'tests/txa/m2')
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:1500]))
    fails += 0 if ok else 1

img, info = compile_file(os.path.join(D, 'm2game.txa'), [os.path.join(ROOT, 'lib')])
cmds = open(os.path.join(D, 'm2game.cmds')).read().split('\n')[:-1]
out = run_image(img, cmds)
if '--update' in sys.argv:
    open(os.path.join(D, 'm2game.expected'), 'w').write(out); print('reference updated')
want = open(os.path.join(D, 'm2game.expected')).read()
check(f'transcript = the reviewed reference ({len(cmds)} commands)', out == want,
      next((f'line {i}: {a!r} / {b!r}' for i, (a, b) in enumerate(zip(out.splitlines(), want.splitlines())) if a != b), 'length differs'))

def after(cmd, n=1):
    """The response to the first occurrence of >cmd (n lines)."""
    i = out.index('>' + cmd + '\n') + len(cmd) + 2
    return '\n'.join(out[i:].split('\n')[:n])
check('which do you mean', after('take lamp') == 'Which do you mean, the brass lamp or the tin lamp?')
check('a reply narrows the choice', after('take lamp', 3).endswith('>brass\nTaken.'))
check('IT', after('x it') == 'A battered brass lamp.')
check('ALL', after('take all', 2) == 'tin lamp: Taken.\nwooden box: Taken.')
check('ALL BUT', after('drop all but brass lamp', 2) == 'wooden box: Dropped.\ntin lamp: Dropped.')
check('unknown word', after('xyzzy') == 'I don\'t know the word "xyzzy".')
check('OOPS', after('oops tin') == 'Taken.')
check('AGAIN', after('g') == 'You already have the tin lamp.')
check('several commands on a line, open, look in', after('open box. look in box. take coins from box', 3) ==
      'You open the wooden box.\nIn the wooden box you can see some gold coins.\nTaken.')
check('THEM and HER', after('x them') == 'You see nothing special about the gold coins.' and after('x her') == 'Ada is stirring a pot.')
check('REVERSE grammar (GIVE ADA LAMP) and a phrase that stops when nothing fits', after('give ada tin lamp') == 'Ada takes the tin lamp and thanks you.')
check('orders', after('ada, take coins') == '"Get it yourself," says Ada.' and after('cook,') == 'Ada looks at you expectantly.')
check('missing object asked for', after('take the') == 'What do you want to take?' and after('put coins in') == 'What do you want to put coins in?')
check('lists with AND and commas', 'wooden box: You already have the wooden box.' in after('take box, coins', 2))
check('ALL BUT leaves one: no prefix; what characters hold is not in ALL', after('take all but box') == 'Taken.')
check('compass words alone; an exit string; no exit', after('n') == 'Hall' and after('d') == 'The trapdoor is shut fast.' and 'You can\'t go that way.' in out)
check('a reply that is a new command', after('take the', 1) and '>look\nKitchen' in out)
check('belongs to a character', 'That seems to belong to Ada.' in out)
check('the compiler gave no warnings', info['program'].warnings == [], info['program'].warnings)

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
