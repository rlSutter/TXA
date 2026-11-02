#!/usr/bin/env python3
"""txa_game.py - the game writer: a TXA story as files a TI can run.

  python3 tools/txa_game.py story.txa --prefix LAMP [--title LAMPLIGHT]
                            [--lib lib] [--out build/game] [--cart]

Writes, into the output folder:
  LAMP1, LAMP2, ...   the engine, as E/A option 5 program files (load
                      LAMP1 from Editor/Assembler option 5, a FinalGROM
                      menu or a TIPI menu)
  LAMPS01, ...        the story image, 4K a file (PROGRAM files)
  LAMPP01, ...        the pictures, if the story has any, 4K a file
  LAMPM01, ...        the music and sounds, if any, 4K a file
                      (the engine loads all three sets from the device
                      into SAMS at startup: the story by its header's
                      length, the other two until a file is missing)
  <title>.dsk         a DSSD disk image holding all of them
  <title>8.bin        with --cart: a FinalGROM cartridge carrying the
                      story itself (no disk needed)

The engine is the generic one (M6): the same files for every game but
for its story-name field (device and prefix), which is patched in here.
The prefix is at most 6 letters, so every file name fits the TI's ten
characters.  The player needs an F18A (or PICO9918), 512K of SAMS and,
for the disk version, a disk drive (or TIPI / CF7 as DSK1)."""
import argparse, os, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build, txpics, txsound
from txc.codegen import compile_file

def write_game(source, prefix, title=None, lib=None, out=None, cart=False, device='DSK1', quiet=False):
    prefix = prefix.upper()
    if not (1 <= len(prefix) <= 6 and prefix.isalnum() and prefix[0].isalpha()):
        sys.exit('the prefix must be 1 to 6 letters or digits, starting with a letter')
    title = (title or os.path.splitext(os.path.basename(source))[0]).upper()
    lib = lib or os.path.join(ROOT, 'lib')
    out = out or os.path.join(ROOT, 'build', 'game', prefix.lower())
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        os.remove(os.path.join(out, f))
    image, info = compile_file(source, [lib], title=title)
    srcdir = os.path.dirname(os.path.abspath(source))
    pictures = txpics.picture_area(info, [srcdir, os.path.join(srcdir, 'pics')])
    sounds = txsound.sound_area(info, [srcdir, os.path.join(srcdir, 'sounds')])
    os.makedirs(os.path.join(ROOT, 'src/gen'), exist_ok=True)
    if not os.path.exists(os.path.join(ROOT, 'src/gen/font.a99')):
        subprocess.run([sys.executable, 'tools/mkfont.py'], cwd=ROOT, check=True)
    build.check_ramvars()
    # the engine: the generic one (M6, D1), its story name patched in
    ea5 = []
    for i, data in enumerate(build.generic_engine_files()):
        n = f'{prefix}{i + 1}'
        patched = build.patch_engine_name(data, device, prefix)
        open(os.path.join(out, n), 'wb').write(patched if patched is not None else data); ea5.append(n)
    if not any(build.NAMEMARK.encode() in open(os.path.join(out, n), 'rb').read() for n in ea5):
        sys.exit('the engine files have no story-name field')
    # the story, the pictures, the music and sounds: each in 4K files (M6, D2)
    def chunks(data, letter):
        names = []
        for i in range(0, len(data), 4096):
            n = f'{prefix}{letter}{i // 4096 + 1:02d}'
            open(os.path.join(out, n), 'wb').write(data[i:i + 4096]); names.append(n)
        return names
    story, picfiles, sndfiles = chunks(image, 'S'), chunks(pictures, 'P'), chunks(sounds, 'M')
    # the disk image
    dsk = os.path.join(out, title.lower() + '.dsk')
    build.run([sys.executable, build.XDM, dsk, '-X', 'dssd', '-n', title[:10]])
    build.run([sys.executable, build.XDM, dsk, '-a'] + ea5 + story + picfiles + sndfiles + ['-f', 'PROGRAM'], cwd=out)
    files = {'engine': ea5, 'story': story, 'picture_files': picfiles, 'sound_files': sndfiles, 'disk': dsk, 'image_bytes': len(image), 'picture_bytes': len(pictures),
             'pictures': len(info['program'].pictures), 'warnings': info['program'].warnings}
    card = os.path.join(out, f'{prefix}-CARD.md')                  # the player's card (M7)
    open(card, 'w').write(player_card(title, prefix, device, pictures=bool(pictures), music=bool(sounds)))
    files['card'] = card
    if cart:
        c, _ = build.engine_cart(image, title[:20], pictures=pictures, sounds=sounds)
        cp = os.path.join(out, title.lower() + '8.bin')
        open(cp, 'wb').write(c); files['cart'] = cp
    if not quiet:
        pics = f', {files["pictures"]} pictures ({len(pictures)} bytes)' if pictures else ''
        print(f'{title}: story {len(image)} bytes in {len(story)} files{pics} in {len(picfiles)}, sounds in {len(sndfiles)}; '
              f'engine {len(ea5)} E/A 5 files')
        print(f'  load {ea5[0]} with E/A option 5; the disk image is {os.path.basename(dsk)}')
        for w in info['program'].warnings:
            print('  ' + w)
    return files

if __name__ == '__main__':
    a = argparse.ArgumentParser(description='Write a TXA story as TI disk files (and optionally a cartridge).')
    a.add_argument('source'); a.add_argument('--prefix', required=True)
    a.add_argument('--title'); a.add_argument('--lib'); a.add_argument('--out')
    a.add_argument('--cart', action='store_true'); a.add_argument('--device', default='DSK1')
    o = a.parse_args()
    write_game(o.source, o.prefix, o.title, o.lib, o.out, o.cart, o.device)

def player_card(title, prefix, device='DSK1', pictures=False, music=False):
    """The game's player's card (M7): a page of Markdown with its title,
    how to load it, and how to play.  Written beside the game's files as
    PREFIX-CARD.md; docs/PLAYERS-CARD.md is Lamplight's."""
    extras = []
    if pictures:
        extras.append('PICTURES OFF and PICTURES ON hide and show the pictures.')
    if music:
        extras.append('MUSIC OFF and SOUNDS OFF silence the music and the sound effects (ON brings them back).')
    return f"""# {title}

*An interactive story for the TI-99/4A, made with TXA.*

## Starting

You need a TI-99/4A with 32K memory expansion, an F18A (or PICO9918) and
a SAMS card of 512K or more. Put the game's disk in {device}, then load
`{device}.{prefix}1` with Editor/Assembler option 5, or choose it from a
FinalGROM or TIPI menu.

## Playing

You read what happens and type what you do, then press ENTER:

```
> look            > take the lamp     > open the door with the key
> go north        > put coin on table > ask the keeper about the tide
```

Directions: N, S, E, W, NE, NW, SE, SW, UP, DOWN, IN, OUT (just N works).
Shortcuts: L look, X examine, I inventory, Z wait, G again. Several
commands go on one line with THEN or full stops: TAKE KEY. GO NORTH.
If a word is misspelt, OOPS and the right word corrects it.

## Keys

- **FCTN S** rubs out; **FCTN E** and **FCTN X** bring back earlier
  commands.
- **FCTN 9** (BACK) at the prompt shows what has scrolled away: FCTN E
  and X move through it, ENTER returns.

## Saving

- **SAVE** and **RESTORE** keep and bring back a game on disk.
- **UNDO** takes back your last move (again for the one before).
- **RESTART** starts over; **QUIT** ends; **SCORE** shows how you are
  doing.
- **VERBOSE** describes every room every time; **BRIEF** only the first.
{chr(10).join('- ' + e for e in extras)}
"""
