#!/usr/bin/env python3
"""txa_srcdisk.py - a game's TXA source as a TI disk, for the workbench.

  python3 tools/txa_srcdisk.py samples/lamplight.txa [-o build/lamplight-src.dsk]

Wraps the game's source and the standard library (lib/*.txa) to 80
columns (tools/txa_wrap.py: long strings continue on the next line, D1)
and writes each as a DIS/VAR 80 file, the format Press 2.0 and TI-Writer
use, on a DSDD disk image: the game under its own name (LAMPLIGHT), the
library under the names INCLUDE uses (STDLIB, LIBDEFS, PARSER, VERBS,
VERBS2, TURN).  Mount it as DSK1 and give the workbench DSK1.LAMPLIGHT.
Each file is read back from the image and checked against the text."""
import argparse, glob, os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build
from txa_wrap import wrap_text

def ti_name(path):
    n = os.path.splitext(os.path.basename(path))[0].upper()
    if not (n[:1].isalpha() and n.isalnum() and len(n) <= 10):
        sys.exit(f'{path}: its name must be 1-10 letters and digits, starting with a letter, for the TI')
    return n

def make_disk(game, out=None, lib=None, label=None, fmt='dssd'):
    """fmt: 'dssd' (180K, single density: what the TI's own disk controller
    reads and writes; the default since M6.3, when a double-density disk
    failed under js99er's emulated TI controller) or 'dsdd' (360K, for
    CorComp, Myarc or TIPI)."""
    lib = lib or os.path.join(ROOT, 'lib')
    out = os.path.abspath(out or os.path.join(ROOT, 'build', os.path.splitext(os.path.basename(game))[0] + '-src.dsk'))
    files = [game] + sorted(glob.glob(os.path.join(lib, '*.txa')))
    tmp = tempfile.mkdtemp()
    names, texts = [], {}
    for f in files:
        n = ti_name(f)
        t = wrap_text(open(f).read()).rstrip('\n') + '\n'
        open(os.path.join(tmp, n), 'w', encoding='latin-1').write(t)
        names.append(n); texts[n] = t
    if os.path.exists(out):
        os.remove(out)
    build.run([sys.executable, build.XDM, out, '-X', fmt, '-n', (label or ti_name(game))[:10]])
    build.run([sys.executable, build.XDM, out, '-a'] + names + ['-f', 'DIS/VAR80'], cwd=tmp)
    chk = tempfile.mkdtemp()                  # read every file back from the image
    for n in names:
        build.run([sys.executable, build.XDM, out, '-e', n, '-o', os.path.join(chk, n)])
        back = open(os.path.join(chk, n), encoding='latin-1').read()
        if back.rstrip('\n') != texts[n].rstrip('\n'):
            sys.exit(f'{n}: what came back from the disk image differs')
    return out, names, sum(len(t) for t in texts.values())

if __name__ == '__main__':
    a = argparse.ArgumentParser(description='A TXA game\'s source and the library as DV80 files on a TI disk image.')
    a.add_argument('source'); a.add_argument('-o', '--out')
    a.add_argument('--dsdd', action='store_true', help='a 360K double-density disk (CorComp, Myarc, TIPI) instead of 180K single density')
    o = a.parse_args()
    out, names, size = make_disk(o.source, o.out, fmt='dsdd' if o.dsdd else 'dssd')
    print(f'{out}: {len(names)} DIS/VAR 80 files ({", ".join(names)}), {size} bytes of source; each checked')
