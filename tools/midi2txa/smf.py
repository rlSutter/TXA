"""smf.py - a Standard MIDI File reader with no dependencies.

Reads format 0, 1 and 2 files (format 2 is read like format 1, with a
warning), RIFF-wrapped RMID files, running status, SysEx and meta events.
Returns every track as a list of events with absolute tick times; nothing
is interpreted here beyond what the file format itself defines, so the
converter decides what the events mean.

Event tuples, by kind:
    (tick, 'on',    channel, note, velocity)     velocity 0 is kept as 'off'
    (tick, 'off',   channel, note, velocity)
    (tick, 'cc',    channel, controller, value)
    (tick, 'prog',  channel, program, 0)
    (tick, 'bend',  channel, value14, 0)
    (tick, 'touch', channel, value, 0)           key or channel pressure
    (tick, 'meta',  type, data_bytes, 0)
Channels are 0-15 (so General MIDI drums are channel 9).
"""

import struct
from fractions import Fraction


class MidiError(Exception):
    """The file is not a MIDI file, or is too damaged to read."""


class MidiFile:
    def __init__(self, fmt, division, tracks, warnings):
        self.format = fmt
        self.division = division          # raw 16-bit signed value
        self.tracks = tracks              # list of event lists
        self.warnings = warnings
        if division > 0:
            self.ppq = Fraction(division)
            self.smpte = None
        else:
            # SMPTE timing: ticks per second = frames * ticks per frame.
            # There is no musical beat, so the converter treats it as
            # 120 BPM (one quarter note = half a second).
            fps = -(division >> 8)
            fps = Fraction(2997, 100) if fps == 29 else Fraction(fps)
            tpf = division & 0xFF
            self.smpte = (fps, tpf)
            self.ppq = fps * tpf / 2

    def track_name(self, index):
        for ev in self.tracks[index]:
            if ev[1] == 'meta' and ev[2] == 0x03:
                text = ev[3].decode('latin-1', 'replace')
                return ''.join(c for c in text if c.isprintable()).strip()
        return ''


def _vlq(data, pos):
    value = 0
    for _ in range(4):
        if pos >= len(data):
            raise MidiError('truncated variable-length number')
        b = data[pos]
        pos += 1
        value = (value << 7) | (b & 0x7F)
        if not b & 0x80:
            return value, pos
    raise MidiError('variable-length number longer than four bytes')


_DATA_LEN = {0x80: 2, 0x90: 2, 0xA0: 2, 0xB0: 2, 0xC0: 1, 0xD0: 1, 0xE0: 2}
_SYSTEM_LEN = {0xF1: 1, 0xF2: 2, 0xF3: 1}


def _parse_track(body, warnings, number):
    events = []
    pos = 0
    tick = 0
    status = None
    n = len(body)
    while pos < n:
        try:
            delta, pos = _vlq(body, pos)
        except MidiError as exc:
            warnings.append('track %d: %s; rest of track ignored' % (number, exc))
            break
        tick += delta
        if pos >= n:
            break
        b = body[pos]
        if b == 0xFF:                                   # meta event
            if pos + 1 >= n:
                break
            mtype = body[pos + 1]
            length, pos = _vlq(body, pos + 2)
            data = bytes(body[pos:pos + length])
            pos += length
            events.append((tick, 'meta', mtype, data, 0))
            if mtype == 0x2F:                           # end of track
                break
            continue
        if b in (0xF0, 0xF7):                           # SysEx
            length, pos = _vlq(body, pos + 1)
            pos += length
            status = None
            continue
        if b >= 0xF1:                                   # stray system bytes
            pos += 1 + _SYSTEM_LEN.get(b, 0)
            continue
        if b & 0x80:
            status = b
            pos += 1
        elif status is None:
            warnings.append('track %d: data byte with no running status at '
                            'tick %d; rest of track ignored' % (number, tick))
            break
        kind = status & 0xF0
        ch = status & 0x0F
        need = _DATA_LEN[kind]
        if pos + need > n:
            break
        d1 = body[pos]
        d2 = body[pos + 1] if need == 2 else 0
        pos += need
        if kind == 0x90 and d2 > 0:
            events.append((tick, 'on', ch, d1, d2))
        elif kind in (0x80, 0x90):
            events.append((tick, 'off', ch, d1, d2))
        elif kind == 0xB0:
            events.append((tick, 'cc', ch, d1, d2))
        elif kind == 0xC0:
            events.append((tick, 'prog', ch, d1, 0))
        elif kind == 0xE0:
            events.append((tick, 'bend', ch, d1 | (d2 << 7), 0))
        else:
            events.append((tick, 'touch', ch, d1, 0))
    return events


def read(data):
    """Parse MIDI file bytes and return a MidiFile."""
    warnings = []
    if data[:4] == b'RIFF':                            # RMID wrapper
        i = data.find(b'data')
        if i < 0:
            raise MidiError('RIFF file without a data chunk')
        data = data[i + 8:]
    start = data.find(b'MThd')
    if start < 0:
        raise MidiError('not a MIDI file (no MThd header)')
    if start:
        warnings.append('%d bytes before the MIDI header were skipped' % start)
    data = data[start:]
    if len(data) < 14:
        raise MidiError('MIDI header is truncated')
    hlen = struct.unpack('>I', data[4:8])[0]
    fmt, ntracks, division = struct.unpack('>HHh', data[8:14])
    if division == 0:
        raise MidiError('MIDI header gives a time division of 0')
    if fmt == 2:
        warnings.append('format 2 file: tracks are read as if played together')
    pos = 8 + hlen
    tracks = []
    while len(tracks) < ntracks and pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        clen = struct.unpack('>I', data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + clen]
        if len(body) < clen:
            warnings.append('track %d is truncated' % (len(tracks) + 1))
        pos += 8 + clen
        if cid != b'MTrk':
            continue                                    # unknown chunk
        tracks.append(_parse_track(body, warnings, len(tracks) + 1))
    if len(tracks) < ntracks:
        warnings.append('header promises %d tracks, found %d'
                        % (ntracks, len(tracks)))
    if not tracks:
        raise MidiError('no tracks found')
    return MidiFile(fmt, division, tracks, warnings)


def load(path):
    with open(path, 'rb') as f:
        return read(f.read())
