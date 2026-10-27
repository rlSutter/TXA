import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from make_midi import *

Q = 480
OUT = os.path.join(os.path.dirname(__file__), 'fixtures')
os.makedirs(OUT, exist_ok=True)

def song():
    cond = [name('Harbour Song'), tempo(0, 100), timesig(0, 4, 2),
            tempo(4 * 4 * Q, 132.5)]
    mel = [name('Melody')]
    tune = [72, 74, 76, 79, 77, 76, 74, 72]
    import random
    rnd = random.Random(7)
    for bar in range(8):
        for i, p in enumerate(tune):
            t0 = bar * 4 * Q + i * Q // 2 + rnd.randint(-25, 25)   # sloppy
            mel += note(0, p + (2 if bar % 4 == 3 else 0), max(0, t0),
                        t0 + Q // 2 - 30, vel=90 + rnd.randint(-10, 10))
    chords = [name('Chords')]
    for bar in range(8):
        for p in (48, 52, 55, 59):                  # four notes, one too many
            chords += note(1, p + (5 if bar % 2 else 0), bar * 4 * Q,
                           bar * 4 * Q + 4 * Q - 10, vel=70, zero_off=True)
    bass = [name('Bass')]
    for bar in range(8):
        for beat in range(4):
            p = 24 + (7 if beat % 2 else 0)          # C1/G1: below the chip
            bass += note(2, p, bar * 4 * Q + beat * Q, bar * 4 * Q + beat * Q + Q - 20)
        bass.append((bar * 4 * Q + 100, bytes([0xE2, 0, 0x50])))   # bend
    drums = [name('Drums')]
    for bar in range(8):
        for e in range(8):
            t = bar * 4 * Q + e * Q // 2
            drums += note(9, 42, t, t + 60, vel=60)                # hats
            if e in (0, 4):
                drums += note(9, 36, t, t + 60, vel=120)           # kick
            if e in (2, 6):
                drums += note(9, 38, t, t + 60, vel=110)           # snare
        if bar == 7:
            drums += note(9, 49, bar * 4 * Q, bar * 4 * Q + Q, 127)  # crash
    return smf([track(cond), track(mel), track(chords, running_status=True),
                track(bass), track(drums)], ppq=Q)

def triplets():
    t = [name('Triplets'), tempo(0, 90)]
    for i in range(12):                              # eighth-note triplets
        t += note(0, 60 + i % 6, i * Q // 3, (i + 1) * Q // 3 - 5)
    return smf([track(t)], ppq=Q, fmt=0)

for fname, data in (('harbour.mid', song()), ('triplets.mid', triplets())):
    with open(os.path.join(OUT, fname), 'wb') as f:
        f.write(data)
print('fixtures written')
