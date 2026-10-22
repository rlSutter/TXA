#!/usr/bin/env python3
"""fixjumps.py - assemble the workbench and rewrite each conditional or
plain jump xas99 reports out of range as a branch: JMP L -> B @L; Jcc L
-> the opposite jump over a B @L.  Repeats until none are left.  A tool
for writing the workbench's long routines; review the diff after.  It
rewrites only the workbench's own files (w*.a99): a jump reported out of
range in a shared kernel file means a label clash, to be fixed by hand."""
import re, subprocess, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INV = {'JEQ': 'JNE', 'JNE': 'JEQ', 'JL': 'JHE', 'JHE': 'JL', 'JH': 'JLE', 'JLE': 'JH', 'JOC': 'JNC', 'JNC': 'JOC'}
src = os.path.join(ROOT, 'src')
OWN = re.compile(r'^w\w*\.a99$')              # the workbench's own sources (wbench, wload, wsym, ...)
for _ in range(20):
    r = subprocess.run([sys.executable, os.path.join(ROOT, '../xdt99/xas99.py'), '-R', '-i', '-o', '/tmp/fj', 'wbench.a99'],
                       cwd=src, capture_output=True, text=True)
    out = r.stdout + r.stderr
    hits = re.findall(r'> (\w+\.a99) <\d> (\d{4}) - .*\n\*\*\*\*\* Error: Out of range', out)
    if not hits:
        print('no jumps out of range'); break
    byfile = {}
    for f, ln in hits:
        if not OWN.match(f):                   # never the kernel the engine shares
            print('not rewriting', f, ln, '(a shared file: fix it by hand, or rename a clashing label)'); continue
        byfile.setdefault(f, set()).add(int(ln))
    for f, lines in byfile.items():
        p = os.path.join(src, f); L = open(p).read().split('\n')
        for ln in sorted(lines, reverse=True):
            line = L[ln - 1]
            m = re.match(r'^(\S*)(\s+)(J\w+)(\s+)(\S+)(.*)$', line)
            if not m:
                print('cannot fix', f, ln, line); continue
            lab, sp, op, sp2, tgt, rest = m.groups()
            if op == 'JMP':
                L[ln - 1] = f'{lab}{sp}B{" " * 4}@{tgt}{rest}'
            elif op in INV:
                L[ln - 1:ln] = [f'{lab}{sp}{INV[op]}{sp2}$+6{rest}', f'       B    @{tgt}']
            elif op == 'JLT':
                L[ln - 1:ln] = [f'{lab}{sp}JGT{sp2}$+8{rest}', '       JEQ  $+6', f'       B    @{tgt}']
            elif op == 'JGT':
                L[ln - 1:ln] = [f'{lab}{sp}JLT{sp2}$+8{rest}', '       JEQ  $+6', f'       B    @{tgt}']
            else:
                print('cannot fix', f, ln, line)
        open(p, 'w').write('\n'.join(L))
        print(f'{f}: {len(lines)} jumps made branches')
