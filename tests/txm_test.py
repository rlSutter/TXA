#!/usr/bin/env python3
"""txm_test.py - TXA music notation (.txm) through the TI build: a tune
compiled tick by tick by the reference compiler (tools/midi2txa/txamusic.py),
encoded as the player's events by txsound.compile_txm, and played back by
txsound's reference player (the TI engine's is tested against it): the
chip's state after every frame must be the compiler's state for that tick,
over two loops of the tune.  Also the converter package's own tests.

  python3 tests/txm_test.py"""
import os, sys, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, os.path.join(ROOT, 'tools/midi2txa'))
os.chdir(ROOT)
import txsound, txamusic
fails = 0
def check(name, ok, detail=''):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok else '\n' + str(detail)[:1500]))
    fails += 0 if ok else 1

def chip_state(writes, chip):
    """Apply the player's chip bytes to chip = {ch: [value, att]} (ch 3 the noise)."""
    latch = None
    for b in writes:
        if b & 0x80:
            ch = (b >> 5) & 3
            if b & 0x10:
                chip[ch][1] = b & 15
            elif ch == 3:
                chip[3][0] = 0xE0 | (b & 7); latch = None
            else:
                chip[ch][0] = (chip[ch][0] & 0x3F0) | (b & 15); latch = ch
        elif latch is not None:
            chip[latch][0] = (chip[latch][0] & 15) | ((b & 0x3F) << 4)

def play_and_compare(path, loop=True, loops=2):
    text = open(path).read()
    song = txamusic.compile_text(text)
    lp, voices = txsound.compile_txm(text, os.path.basename(path), loop)
    item = txsound.item_bytes(lp, voices)
    area = (1).to_bytes(2, 'big') + (0).to_bytes(2, 'big') + (8).to_bytes(4, 'big') + item
    pl = txsound.Player(area)
    pl.play_music(1)
    chip = {0: [0, 15], 1: [0, 15], 2: [0, 15], 3: [0, 15]}
    bad = []
    for t in range(song.ticks * loops):
        chip_state(pl.tick(), chip)
        for v in song.voices:
            ch = 'ABCN'.index(v)
            want = song.voices[v][t % song.ticks]
            got = chip[ch]
            ok = (got[1] == want[1] == 15) or (got[1] == want[1] and got[0] == want[0])
            if not ok and len(bad) < 5:
                bad.append((t, v, tuple(got), want))
    return song, item, bad

harbour = os.path.join(ROOT, 'tools/midi2txa/examples/HARBOURB.txm')
song, item, bad = play_and_compare(harbour)
check(f'HARBOURB.txm: {song.ticks} ticks ({song.ticks / 60:.0f} s), {len(item)} bytes of events: the player\'s chip state is the '
      f'reference compiler\'s at every tick, twice round', not bad, bad)
simple = os.path.join(ROOT, 'tools/midi2txa/examples/HARBOUR.txm')
song2, item2, bad2 = play_and_compare(simple)
check(f'HARBOUR.txm (no envelopes): {song2.ticks} ticks, {len(item2)} bytes: the same, twice round', not bad2, bad2)
r = subprocess.run([sys.executable, 'tests/test_all.py'], cwd=os.path.join(ROOT, 'tools/midi2txa'), capture_output=True, text=True)
check('the converter package\'s own tests (tools/midi2txa/tests/test_all.py) pass', r.returncode == 0 and 'OK' in r.stderr + r.stdout,
      (r.stdout + r.stderr)[-800:])
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
