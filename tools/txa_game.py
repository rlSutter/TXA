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
