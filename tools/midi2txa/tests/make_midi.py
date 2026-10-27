"""Write small Standard MIDI Files for the tests (no dependencies)."""
import struct


def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def track(events, running_status=False):
    """events: (tick, bytes) with full status bytes; sorted here."""
    events = sorted(events, key=lambda e: e[0])
    out = b''
    last = 0
    status = None
    for tick, data in events:
        out += vlq(tick - last)
        last = tick
        if running_status and data[0] < 0xF0 and data[0] == status:
            out += data[1:]
        else:
            out += data
            status = data[0] if data[0] < 0xF0 else None
    out += vlq(0) + b'\xff\x2f\x00'
    return b'MTrk' + struct.pack('>I', len(out)) + out


def smf(tracks, ppq=480, fmt=1):
    return b'MThd' + struct.pack('>IHHH', 6, fmt, len(tracks), ppq) + \
        b''.join(tracks)


def note(ch, pitch, t0, t1, vel=100, zero_off=False):
    off = bytes([0x90 | ch, pitch, 0]) if zero_off else \
        bytes([0x80 | ch, pitch, 64])
    return [(t0, bytes([0x90 | ch, pitch, vel])), (t1, off)]


def tempo(tick, bpm):
    us = int(round(60e6 / bpm))
    return (tick, b'\xff\x51\x03' + us.to_bytes(3, 'big'))


def name(text):
    return (0, b'\xff\x03' + vlq(len(text)) + text.encode())


def timesig(tick, num, den_pow):
    return (tick, bytes([0xFF, 0x58, 4, num, den_pow, 24, 8]))
