#!/usr/bin/env python3
"""txa_game.py - the game writer: a TXA story as files a TI can run.

  python3 tools/txa_game.py story.txa --prefix LAMP [--title LAMPLIGHT]
                            [--lib lib] [--out build/game] [--cart]

Writes, into the output folder:
  LAMP1, LAMP2, ...   the engine, as E/A option 5 program files (load
                      LAMP1 from Editor/Assembler option 5, a FinalGROM
                      menu or a TIPI menu)
  LAMPS01, ...        the story, 4K a file (PROGRAM files): the engine
                      loads them from DSK1 into SAMS at startup
  <title>.dsk         a DSSD disk image holding all of them
  <title>8.bin        with --cart: a FinalGROM cartridge carrying the
                      story itself (no disk needed)

The prefix is at most 6 letters, so every file name fits the TI's ten
characters.  The player needs an F18A (or PICO9918), 512K of SAMS and,
for the disk version, a disk drive (or TIPI / CF7 as DSK1)."""
import argparse, os, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build
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
    os.makedirs(os.path.join(ROOT, 'src/gen'), exist_ok=True)
    if not os.path.exists(os.path.join(ROOT, 'src/gen/font.a99')):
        subprocess.run([sys.executable, 'tools/mkfont.py'], cwd=ROOT, check=True)
    build.check_ramvars()
    # the engine, reading the story from disk files
    build.write_storysrc(image, disk_prefix=f'{device}.{prefix}S')
    segs = build.assemble_engine(prefix + '1')
    ea5 = []
    name = prefix + '1'
    while True:
        p = os.path.join(build.B, name)
        shutil.copy(p, os.path.join(out, name)); ea5.append(name)
        if not int.from_bytes(open(p, 'rb').read()[:2], 'big'):
            break
        name = name[:-1] + chr(ord(name[-1]) + 1)
    # the story, 4K a file
    story = []
    for i in range(0, len(image), 4096):
        n = f'{prefix}S{i // 4096 + 1:02d}'
        open(os.path.join(out, n), 'wb').write(image[i:i + 4096]); story.append(n)
    # the disk image
    dsk = os.path.join(out, title.lower() + '.dsk')
    build.run([sys.executable, build.XDM, dsk, '-X', 'dssd', '-n', title[:10]])
    build.run([sys.executable, build.XDM, dsk, '-a'] + ea5 + story + ['-f', 'PROGRAM'], cwd=out)
    files = {'engine': ea5, 'story': story, 'disk': dsk, 'image_bytes': len(image), 'warnings': info['program'].warnings}
    if cart:
        c, _ = build.engine_cart(image, title[:20])
        cp = os.path.join(out, title.lower() + '8.bin')
        open(cp, 'wb').write(c); files['cart'] = cp
    if not quiet:
        print(f'{title}: story {len(image)} bytes in {len(story)} files; engine {len(ea5)} E/A 5 files')
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
