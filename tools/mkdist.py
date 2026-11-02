#!/usr/bin/env python3
"""mkdist.py - the TXA distribution folder (M7): everything a user needs,
built from the repository.

  python3 tools/mkdist.py [--version 1.0] [--out dist]

Writes dist/txa-<version>/ and dist/txa-<version>.zip:
  README.txt, LICENSE
  cartridge/   txa-workbench8.bin        the workbench (FinalGROM 99, 256K)
  games/       lamplight.dsk, lamplight8.bin, LAMP-CARD.md      the sample game
               ferry.dsk, ferry8.bin, FERRY-CARD.md             the tutorial's game
  workbench/   lamplight-workbench.dsk   Lamplight's source, pictures and music
               bird-workbench.dsk        a game with a TI Artist picture
  manuals/     each manual as Markdown and PDF
The PC tools (the compiler, game writer, converters) are the repository itself."""
import argparse, os, shutil, subprocess, sys, tempfile, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build, txa_game, tiartist

MANUALS = [('LANGUAGE-REFERENCE', 'TXA Authoring Language Reference'), ('LIBRARY-REFERENCE', 'TXA Standard Library Reference'),
           ('WORKBENCH-MANUAL', 'TXA Workbench Manual'), ('TUTORIAL', 'The TXA Tutorial'),
           ('ENGINE-GUIDE', 'TXA Engine Implementation Guide'), ('TECHNICAL-REFERENCE', 'TXA Technical Reference'),
           ('PLAYERS-CARD', "TXA Player's Card"), ('MUSIC', 'TXA Music Notation')]
CSS = """body { font-family: "DejaVu Serif", Georgia, serif; font-size: 11pt; line-height: 1.4; max-width: 46em; margin: 2em auto; }
h1, h2, h3 { font-family: "DejaVu Sans", Arial, sans-serif; }
code, pre { font-family: "DejaVu Sans Mono", monospace; font-size: 9pt; }
pre { background: #f4f4f4; padding: 0.6em; white-space: pre-wrap; }
table { border-collapse: collapse; font-size: 9pt; margin: 0.8em 0; }
th, td { border: 1px solid #bbb; padding: 3px 6px; vertical-align: top; }
th { background: #eee; }
"""

README = """TXA {version}: text adventures for the TI-99/4A
================================================

TXA is an Infocom-style text adventure system for the TI-99/4A with an
F18A (or PICO9918) and a SAMS card of 512K or more.  Designed by Rebecca
Sutter, built with Claude.  MIT licence (LICENSE).

To play
-------
games/lamplight.dsk is the sample game.  Put it in DSK1 and load
DSK1.LAMP1 with Editor/Assembler option 5, or from a FinalGROM or TIPI
menu; or put games/lamplight8.bin on a FinalGROM.  games/LAMP-CARD.md
says how to play.  games/ferry.dsk is the tutorial's small game.

To make games
-------------
cartridge/txa-workbench8.bin is the TXA Workbench, for a FinalGROM 99.
With workbench/lamplight-workbench.dsk in DSK1, start it and press P, C
(compile), T (test-play), B (build) and R (run).  The manuals are in
manuals/, as Markdown and PDF:

  Authoring Language Reference   the TXA language
  Standard Library Reference     every attribute, property, verb, routine
  Workbench Manual               every key of the workbench
  Tutorial                       a small game built in five chapters
  Engine Implementation Guide    for writing an engine on another machine
  Technical Reference            the formats and the TI engine's memory
  Player's Card                  how a player plays (one comes with each game)
  Music Notation                 TXA music notation 1.0

The PC tools (the compiler, game writer, picture and music converters)
are in the source repository, which also builds everything here.

In js99er, use the "Generic Disk" controller setting with F18A and SAMS on.
"""

def pdf(md, title, out):
    with tempfile.TemporaryDirectory() as d:
        css = os.path.join(d, 'style.css'); open(css, 'w').write(CSS)
        html = os.path.join(d, 'm.html')
        subprocess.run(['pandoc', md, '-s', '--css', css, '--metadata', f'pagetitle={title}', '-o', html], check=True)
        subprocess.run(['wkhtmltopdf', '--enable-local-file-access', '-q', '-s', 'Letter', html, out],
                       check=True, stderr=subprocess.DEVNULL)

def main():
    a = argparse.ArgumentParser(); a.add_argument('--version', default='1.0'); a.add_argument('--out', default=os.path.join(ROOT, 'dist'))
    args = a.parse_args()
    top = os.path.join(args.out, f'txa-{args.version}')
    shutil.rmtree(top, ignore_errors=True)
    for sub in ['cartridge', 'games', 'workbench', 'manuals']:
        os.makedirs(os.path.join(top, sub))
    open(os.path.join(top, 'README.txt'), 'w').write(README.format(version=args.version))
    shutil.copy(os.path.join(ROOT, 'LICENSE'), top)
    cart, _ = build.workbench_cart()
    open(os.path.join(top, 'cartridge', 'txa-workbench8.bin'), 'wb').write(cart)
    with tempfile.TemporaryDirectory() as t:
        for src, prefix, title, name in [('samples/lamplight.txa', 'LAMP', 'LAMPLIGHT', 'lamplight'),
                                         ('samples/tutorial/ferry5.txa', 'FERRY', 'THE FERRY HOUSE', 'ferry')]:
            g = os.path.join(t, name)
            f = txa_game.write_game(os.path.join(ROOT, src), prefix, title, out=g, cart=True, quiet=True)
            shutil.copy(f['disk'], os.path.join(top, 'games', f'{name}.dsk'))
            carts = [n for n in os.listdir(g) if n.endswith('8.bin')]
            if carts:
                shutil.copy(os.path.join(g, carts[0]), os.path.join(top, 'games', f'{name}8.bin'))
            shutil.copy(f['card'], os.path.join(top, 'games'))
        # the workbench disks: Lamplight's source with its pictures and music; the bird game with its TI Artist picture
        wl = os.path.join(top, 'workbench', 'lamplight-workbench.dsk')
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'txa_srcdisk.py'), os.path.join(ROOT, 'samples/lamplight.txa'), '-o', wl],
                       check=True, stdout=subprocess.DEVNULL)
        g = os.path.join(t, 'lampli')
        f = txa_game.write_game(os.path.join(ROOT, 'samples/lamplight.txa'), 'LAMPLI', 'LAMPLIGHT', out=g, quiet=True)
        build.run([sys.executable, build.XDM, wl, '-a'] + f['picture_files'] + f['sound_files'] + ['-f', 'PROGRAM'], cwd=g)
        wb = os.path.join(top, 'workbench', 'bird-workbench.dsk')
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'txa_srcdisk.py'), os.path.join(ROOT, 'tests/txa/bird/birdgame.txa'), '-o', wb],
                       check=True, stdout=subprocess.DEVNULL)
        b = os.path.join(t, 'bird'); os.makedirs(b)
        open(os.path.join(b, 'BIRD_P'), 'wb').write(tiartist.read_file(os.path.join(ROOT, 'tests/data/BIRD_P')))
        open(os.path.join(b, 'BIRD_C'), 'wb').write(tiartist.read_file(os.path.join(ROOT, 'tests/data/BIRD_C')))
        open(os.path.join(b, 'BIRD_T'), 'w').write('crop 20\n')
        build.run([sys.executable, build.XDM, wb, '-a', 'BIRD_P', 'BIRD_C', '-f', 'PROGRAM'], cwd=b)
        build.run([sys.executable, build.XDM, wb, '-a', 'BIRD_T', '-f', 'DIS/VAR80'], cwd=b)
    for name, title in MANUALS:
        md = os.path.join(ROOT, 'docs', f'{name}.md')
        shutil.copy(md, os.path.join(top, 'manuals'))
        pdf(md, title, os.path.join(top, 'manuals', f'{name}.pdf'))
    z = os.path.join(args.out, f'txa-{args.version}.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for dp, _, fs in os.walk(top):
            for fn in sorted(fs):
                p = os.path.join(dp, fn)
                zf.write(p, os.path.relpath(p, args.out))
    print(f'{top}\n{z}: {os.path.getsize(z)} bytes')

if __name__ == '__main__':
    main()
