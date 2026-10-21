#!/usr/bin/env python3
"""m3_world_test.py - the standard library's world model, part by part.

Each test world in tests/txa/m3 is played with its .cmds on the Python
VM and compared with its reviewed .expected transcript; then named
checks say which behaviour is right or broken.  --update rewrites the
references after a reviewed change.

  python3 tests/m3_world_test.py [--update]"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from txc.codegen import compile_file
from txc import txvm
D = os.path.join(ROOT, 'tests/txa/m3'); LIB = [os.path.join(ROOT, 'lib')]
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:1500]))
    fails += 0 if ok else 1

def play(world):
    img, info = compile_file(os.path.join(D, world + '.txa'), LIB)
    vm = txvm.VM(img, open(os.path.join(D, world + '.cmds')).read().split('\n')[:-1])
    out = vm.run()
    if '--update' in sys.argv:
        open(os.path.join(D, world + '.expected'), 'w').write(out)
    want = open(os.path.join(D, world + '.expected')).read()
    check(f'{world}: transcript = the reviewed reference', out == want,
          next((f'line {i}: {a!r} / {b!r}' for i, (a, b) in enumerate(zip(out.splitlines(), want.splitlines())) if a != b), 'length differs'))
    check(f'{world}: no compiler warnings', info['program'].warnings == [], info['program'].warnings)
    return out, vm

out, vm = play('world1')
def after(cmd, n=1, nth=1):
    i = -1
    for _ in range(nth):
        i = out.index('>' + cmd + '\n', i + 1)
    i += len(cmd) + 2
    return '\n'.join(out[i:].split('\n')[:n])
check('CANT_GO', after('w') == 'The garden is overgrown past walking.')
check('INITIAL shows until the object is moved', 'An iron key lies forgotten' in after('n', 3) and 'iron key' not in after('look', 3, nth=2))
check('score notification', '[Your score has just gone up by 5 points.]' in after('take key', 3))
check('brief: a visited room shows no description', after('s', 2) == 'Porch\nYou can see a brass lamp and a candle here.')
check('darkness: the room, LOOK, and what cannot be seen', after('d', 2) == 'Darkness\nIt is pitch dark, and you can\'t see a thing.'
      and after('x barrel') == "You can't see any such thing.")
check('a light source makes the room visible', after('d', 2, nth=2) == 'Cellar\nA low cellar that smells of earth and old apples.')
check('a daemon every turn', after('wait', 2) == 'Time passes.\nWater drips into the barrel.')
check('a timer: lit, then out three turns later', after('light candle') == 'The candle catches.' and 'The candle gutters and goes out.' in after('wait', 2, nth=3))
check("the game's before hook", after('jump') == "(The game's before hook saw that.)")
check('meta commands take no time; SCORE', after('score') == 'You have scored 5 out of a possible 10, in 24 turns.'
      and after('score', nth=2) == 'You have scored 5 out of a possible 10, in 26 turns.')
check('superbrief: names only', after('n', 1, nth=2) == 'Parlour' and after('s', 1, nth=2) == 'Porch')
check('the status line: room, score, moves', vm.status == ('Porch', 5, 26), vm.status)

out, vm = play('world2')
check('a locked door blocks the way and the lock', after('n') == 'The front door seems to be locked.' and after('open door') == 'It seems to be locked.')
check('the wrong key; UNLOCK, LOCK, UNLOCK', after('unlock door with apple') == "That doesn't seem to fit the lock."
      and after('lock door with key') == 'You lock the front door.')
check('through an open door to the other side, and back (DOOR_TO with two rooms)', after('n', 1, nth=2) == 'Garden' and after('s') == 'Hall')
check('a floating object in two rooms (FOUND_IN)', after('x stream') == 'Cold, clear and quick.' and after('x water') == 'Cold, clear and quick.')
check('CAPACITY; nothing inside itself', after('put plum in chest') == 'There is no more room in the small chest.'
      and after('put chest in chest') == "You can't put something inside itself.")
check('inventory shows what is inside things, and closed containers', '  a small chest (which is closed)' in after('i', 7)
      and '    a pear' in after('i', 6, nth=2))
check('EMPTY', after('empty chest') == 'You empty the small chest.')
check('ENTER (sit on) and EXIT (get off), and being on something', after('sit on bench') == 'You get onto the bench.'
      and after('look', 1, nth=5) == 'Garden (on the bench)' and after('get off bench') == 'You get off the bench.'
      and after('get off bench', nth=2) == "But you aren't in anything at the moment.")

out, vm = play('world3')
check('WEAR, worn in the inventory, REMOVE; TAKE OFF a worn thing', after('wear cloak') == 'You put on the wool cloak.'
      and '  a wool cloak (being worn)' in after('i', 4) and after('remove cloak') == 'You take off the wool cloak.'
      and after('take off cloak') == "You aren't wearing the wool cloak.")
check('EAT: edible or not; READ', after('eat bread').startswith('You eat the heel of bread') and after('eat note') == "That's hardly something to eat."
      and after('read note') == 'It says: water the ferns.')
check('PUSH and PULL: fixed things, characters, and a BEFORE rule', after('push pots') == "The clay pots won't budge."
      and after('pull lever').startswith('The lever grinds down') and after('push gardener') == 'The gardener might object to that.')
check('SHOW both ways round goes to the character (LIFE)', after('show note to gardener') == after('show gardener the note')
      == '"That\'s the note, that is," the gardener says.')
check('REPLACE: the game\'s SingSub instead of the library\'s', after('sing') == 'You hum a tune the ferns seem to like.')
check('EXTEND: a new grammar line on a library verb', after('smell the air') == 'Nothing smells out of the ordinary.')
check('SAVE asks for a file and saves; RESTORE brings it back and clears UNDO', after('save', 2) == 'Save to which file? (Enter for SAVE1) \nSaved.'
      and 'Restored.' in after('restore', 2) and after('undo') == "You can't undo that.")   # a restore clears the undo history
check('RESTART and QUIT ask first', after('restart', 3) == 'Do you really want to start again?\n> no\nCarrying on, then.'
      and after('quit', 3) == 'Do you really want to stop?\n> no\nCarrying on, then.')

out, vm = play('world4')
check('UNDO with nothing to undo', after('undo') == "You can't undo that.")
check('UNDO takes back the last command only', after('undo', nth=2) == '[Previous turn undone.]' and '  an egg' in after('i', 2, nth=2))
check('UNDO brings back an eaten egg (into the pail)', after('look in pail') == 'In the pail you can see an egg.')
check('UNDO again goes further back', '  an egg' in after('i', 2, nth=3))
check('turns are undone too', after('score') == 'You have scored 0 out of a possible 3, in 4 turns.')

out, vm = play('world5')
check('the end screen after a death: banner, score, the choice', after('jump', 7) ==
      'You step off into the air.\n\n*** You have died ***\n\nIn that game you scored 0 out of a possible 10, in 1 turn.\n\n'
      'Would you like to RESTART, RESTORE a saved game, UNDO your last move, or QUIT?')
check('an answer it doesn\'t know asks again', '> dance\n\nWould you like to RESTART' in out)
check('UNDO at the end screen takes back the fatal move', '> undo\n[Previous turn undone.]' in out)
check('RESTORE at the end screen brings back the saved game', '> restore\nRestore which file? (Enter for SAVE1) \nRestored.' in out)
check('RESTART at the end screen starts again', '> restart\n\nNarrow Ledge' in out)
check('a win with the game\'s own endmessage, and QUIT ends it', '*** You have escaped ***' in out and out.rstrip().endswith('> quit'))

print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
