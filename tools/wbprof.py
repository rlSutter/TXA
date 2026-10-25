"""wbprof.py - where a Lamplight compile on the workbench spends its
instructions: counts by overlay and by routine (the nearest label below the
PC, from the right assembly's listing).  Made for the optimization passes
(October 2026); about a minute.

  python3 tools/wbprof.py"""
import sys, os, time, collections, bisect
sys.argv = ['x', 'none']; os.chdir('/home/claude/txa')
src = open(os.path.join('tests', 'm5_sema_test.py')).read(); src = src[:src.index("args = sys.argv[1:]")]
g = {'__file__': os.path.abspath('tests/m5_sema_test.py'), '__name__': 'd'}
exec(compile(src, 't', 'exec'), g)
S, sy, keys_for, DATE = g['S'], g['sy'], g['keys_for'], g['DATE']
build = g['build']
# labels: the resident/kernel ones (wbench.equ) and each overlay's (wovl.lst / wbench.lst by staging)
res = sorted((v, k) for k, v in sy.items() if not (0xB000 <= v < 0xD000))
def parse_lst(path):
    """(overlay -> sorted [(addr, label)]) from a listing: labels inside XORG >B000 blocks."""
    import re
    out = collections.defaultdict(list); ov = 0; base = None
    for line in open(path, encoding='latin-1'):
        if 'XORG >B000' in line:
            ov += 1; base = None
            continue
        m = re.match(r'^\d{4} ([0-9A-F]{4}) [0-9A-F]{4} ', line)
        if m and ov:
            a = int(m.group(1), 16)
            if base is None:
                base = a
            if len(line) > 19 and line[19] not in ' *':
                out[ov].append((0xB000 + a - base, line[19:].split()[0]))
            continue
        if False:
            if base is None:
                base = a
            out[ov].append((0xB000 + a - base, m.group(2)))
    return out
ov14 = parse_lst('build/wbench.lst')
ov5n = parse_lst('build/wovl.lst')
ovl = {}
for k, v in ov14.items():
    if k <= 4: ovl[k] = sorted(v)
for k, v in ov5n.items():
    ovl[k + 4] = sorted(v)
d, pp = g['stage'](open('samples/lamplight.txa').read(), 'lamplight', g['LIB'])
m = S.Machine(g['cart'], f18a=True, pages=128); cpu = S.CPU(m); m.disk_dir = d
cpu.pc = m.rw(m.rw(0x6006) + 2)
queue = keys_for('p')[:-1] + keys_for('dsk1.lamplight') + keys_for('') + keys_for('') + keys_for('c')[:-1]
steps = hold = free = 0; dated = False
pcs = collections.Counter(); ovc = sy['OVCUR']
t = time.time()
while steps < 60_000_000:
    pc = cpu.pc
    if pc == sy['WK1'] and not dated:
        for i, c in enumerate(DATE.strftime('%y%m%d').encode()):
            m.wb(sy['WDATE'] + i, c)
        dated = True
    if pc == sy['WK1'] and not hold and steps >= free:
        if not queue:
            break
        m.held = queue.pop(0); hold = steps + 12_000
    if hold and steps >= hold:
        m.held = None; hold = 0; free = steps + 12_000
    if 0xB000 <= pc < 0xD000:
        pcs[(m.rw(ovc), pc)] += 1
    else:
        pcs[(0, pc)] += 1
    cpu.step(); steps += 1
print(f'{steps / 1e6:.1f}M instructions, {time.time() - t:.0f} s', flush=True)
def label(ov, pc):
    tab = ovl.get(ov, []) if ov else res
    i = bisect.bisect_right(tab, (pc, 'zzzz')) - 1
    return tab[i][1] if i >= 0 else '?'
byov = collections.Counter(); byrt = collections.Counter()
for (ov, pc), n in pcs.items():
    byov[ov] += n
    byrt[(ov, label(ov, pc))] += n
print('by overlay (0: resident and kernel):')
for ov, n in sorted(byov.items()):
    print(f'  {ov:2}  {n / 1e6:6.2f}M  {100 * n / steps:5.1f}%')
print('the top 40 routines:')
for (ov, lab), n in byrt.most_common(40):
    print(f'  {n / 1e6:6.2f}M  {100 * n / steps:5.1f}%  ov{ov:<2} {lab}')
