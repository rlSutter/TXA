"""snpreview.py - render compiled TXA music to a WAV file for listening.

An approximation of the TMS9919 (SN76489) good enough to judge a
conversion: square-wave tones at 111860.8 / value Hz, 2 dB attenuation
steps, and a 15-bit noise shift register (white: taps 0 and 1; periodic:
one bit in fifteen) clocked at 3579545 / 512, 1024 or 2048 Hz, or by tone
C for rate 3. It is a preview, not an emulator; check the result in
js99er or Classic99 and on the console before calling a piece finished.

Uses numpy when it is installed and plain Python when it is not.
"""

import struct
import wave

CHIP_DIVIDER = 111860.8
NOISE_RATES = (3579545 / 512, 3579545 / 1024, 3579545 / 2048)
MASTER = 0.22                   # per-voice peak, so four voices cannot clip


def _noise_sequences():
    white = []
    reg = 0x4000
    for _ in range(32767):
        white.append(1.0 if reg & 1 else -1.0)
        fb = (reg & 1) ^ ((reg >> 1) & 1)
        reg = (reg >> 1) | (fb << 14)
    periodic = [1.0] + [-1.0] * 14
    return white, periodic


def _amp(att):
    return 0.0 if att >= 15 else MASTER * 10 ** (-att / 10.0)


def render(song, path, rate=44100, loops=1):
    try:
        import numpy as np
    except ImportError:
        np = None
    white, periodic = _noise_sequences()
    ticks = song.ticks * max(1, loops)
    total = ticks * rate // 60
    if np is not None:
        mix = np.zeros(total)
        white_a = np.array(white)
        periodic_a = np.array(periodic)
    else:
        mix = [0.0] * total
    tone_c = song.voices.get('C')

    for voice, states in song.voices.items():
        phase = 0.0
        t = 0
        while t < ticks:
            value, att = states[t % song.ticks]
            # extend the run while the state (and, for rate 3, tone C) holds
            u = t + 1
            while u < ticks and states[u % song.ticks] == (value, att) and \
                    not (voice == 'N' and value & 3 == 3 and tone_c and
                         tone_c[u % song.ticks] != tone_c[t % song.ticks]):
                u += 1
            s0, s1 = t * rate // 60, u * rate // 60
            n = s1 - s0
            amp = _amp(att)
            if amp and n:
                if voice != 'N':
                    step = CHIP_DIVIDER / value / rate
                    if np is not None:
                        ph = phase + np.arange(n) * step
                        mix[s0:s1] += np.where(ph % 1.0 < 0.5, amp, -amp)
                    else:
                        for i in range(n):
                            mix[s0 + i] += amp if (phase + i * step) % 1.0 \
                                < 0.5 else -amp
                    phase = (phase + n * step) % 1.0
                else:
                    r = value & 3
                    if r == 3:
                        cval = tone_c[t % song.ticks][0] if tone_c else 0
                        shift = CHIP_DIVIDER / cval if cval else 0.0
                    else:
                        shift = NOISE_RATES[r]
                    seq = white if value & 4 else periodic
                    step = shift / rate
                    if np is not None:
                        arr = white_a if value & 4 else periodic_a
                        idx = (phase + np.arange(n) * step).astype(np.int64)
                        mix[s0:s1] += arr[idx % len(seq)] * amp
                    else:
                        for i in range(n):
                            mix[s0 + i] += seq[int(phase + i * step) %
                                               len(seq)] * amp
                    phase = (phase + n * step) % len(seq)
            t = u

    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        if np is not None:
            pcm = (np.clip(mix, -1.0, 1.0) * 32767).astype('<i2').tobytes()
        else:
            pcm = b''.join(struct.pack('<h', int(max(-1.0, min(1.0, x)) *
                                                  32767)) for x in mix)
        w.writeframes(pcm)
