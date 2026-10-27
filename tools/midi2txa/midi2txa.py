#!/usr/bin/env python3
"""midi2txa - convert a Standard MIDI File to TXA music notation.

The TXA spec (Sound and music) fixes what this does: read a MIDI file,
keep the three most important simultaneous tone notes (chosen per track by
the author, or the highest notes by default), map drums to the noise
voice, quantize to a musical grid, fold notes outside the chip's range
into it, and report every compromise. The output is TXA text notation, so
the native workbench can compile it as well as the Python tool.

Before writing anything it compiles its own output with txamusic.py and
checks that every tick matches what it meant to write.

    python3 midi2txa.py song.mid --list          # show the tracks first
    python3 midi2txa.py song.mid --wav song.wav  # convert and preview
    python3 midi2txa.py song.mid --name HARBOUR --prefer 2 --voice C:3:low

Run with --help for every option.
"""

import argparse
import math
import os
import re
import sys
from collections import Counter, defaultdict
from fractions import Fraction

import smf
import txamusic as tm

VERSION = '1.0'
UNITS_PER_QUARTER = tm.UNITS_PER_WHOLE // 4
LINE_WIDTH = 79

# --------------------------------------------------------------- drum kit
#
# One noise channel stands in for the whole kit. Each General MIDI drum is
# mapped to a kind; each kind is a noise type, rate (0 high, 1 middle,
# 2 low), envelope, longest length in 1/192 notes, and a priority for when
# two hits land together (the higher one plays).

DRUM_KINDS = {
    'kick':    dict(white=False, rate=2, env='kick', length=24, pri=6),
    'snare':   dict(white=True, rate=1, env='snare', length=24, pri=5),
    'clap':    dict(white=True, rate=1, env='snare', length=24, pri=5),
    'tom':     dict(white=False, rate=1, env='tom', length=24, pri=4),
    'crash':   dict(white=True, rate=0, env='long', length=96, pri=3),
    'openhat': dict(white=True, rate=0, env='long', length=48, pri=2),
    'perc':    dict(white=True, rate=1, env='short', length=12, pri=2),
    'hat':     dict(white=True, rate=0, env='short', length=12, pri=1),
}

GM_DRUMS = {35: 'kick', 36: 'kick', 37: 'perc', 38: 'snare', 39: 'clap',
            40: 'snare', 41: 'tom', 42: 'hat', 43: 'tom', 44: 'hat',
            45: 'tom', 46: 'openhat', 47: 'tom', 48: 'tom', 49: 'crash',
            50: 'tom', 51: 'openhat', 52: 'crash', 53: 'openhat',
            55: 'crash', 57: 'crash', 59: 'openhat'}

# Envelopes: attenuation added at each tick from the note's start; the
# last step holds. 2 dB per step.
ENVELOPES = {
    'short': [0, 3, 6, 10, 15],
    'snare': [0, 1, 2, 3, 5, 7, 9, 11, 13, 15],
    'kick':  [0, 1, 3, 6, 10, 15],
    'tom':   [0, 1, 2, 4, 6, 8, 11, 15],
    'long':  [0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10,
              10, 11, 11, 12, 12, 13, 13, 14, 14, 15],
    'decay': [0, 0, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4],
    'pluck': [0, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10,
              11, 11, 12, 12, 13, 13, 14, 14, 15],
}
ENV_ORDER = ('decay', 'pluck', 'kick', 'snare', 'tom', 'short', 'long')


class ConvertError(Exception):
    pass


class Note:
    __slots__ = ('track', 'channel', 'pitch', 'vel', 't0', 't1', 'amp',
                 'drum', 's', 'e', 'orig_pitch')

    def __init__(self, track, channel, pitch, vel, t0, amp):
        self.track = track
        self.channel = channel
        self.pitch = pitch
        self.orig_pitch = pitch
        self.vel = vel
        self.t0 = t0
        self.t1 = t0
        self.amp = amp
        self.drum = None
        self.s = self.e = 0


class Seg:
    """One sounding note in an output voice, in 1/192-note units."""
    __slots__ = ('s', 'e', 'key', 'vol', 'env')

    def __init__(self, s, e, key, vol, env):
        self.s, self.e, self.key, self.vol, self.env = s, e, key, vol, env


class Report:
    def __init__(self):
        self.sections = defaultdict(list)

    def add(self, section, line):
        self.sections[section].append(line)

    def text(self):
        out = []
        for name in ('Source', 'Timing', 'Range', 'Voices', 'Drums',
                     'Volume', 'Ignored', 'Output'):
            if self.sections.get(name):
                out.append(name)
                out += ['  ' + line for line in self.sections[name]]
                out.append('')
        return '\n'.join(out)


# ------------------------------------------------------------ reading MIDI

def gather(mf, drum_channels, report):
    """Pair note events and collect tempo and time-signature changes."""
    merged = []
    rank = {'cc': 0, 'prog': 0, 'meta': 0, 'bend': 1, 'touch': 1,
            'off': 2, 'on': 3}
    for ti, events in enumerate(mf.tracks):
        for seq, ev in enumerate(events):
            merged.append((ev[0], rank[ev[1]], ti, seq, ev))
    merged.sort()

    cc7 = [100] * 16
    cc11 = [127] * 16
    open_notes = defaultdict(list)
    notes = []
    tempos = []
    timesigs = []
    bends = Counter()
    pedals = Counter()
    retriggers = 0
    for tick, _, ti, _, ev in merged:
        kind = ev[1]
        if kind == 'meta':
            if ev[2] == 0x51 and len(ev[3]) == 3 and mf.smpte is None:
                us = (ev[3][0] << 16) | (ev[3][1] << 8) | ev[3][2]
                if us:
                    tempos.append((tick, 60e6 / us))
            elif ev[2] == 0x58 and len(ev[3]) >= 2:
                timesigs.append((tick, ev[3][0], 2 ** ev[3][1]))
        elif kind == 'cc':
            if ev[3] == 7:
                cc7[ev[2]] = ev[4]
            elif ev[3] == 11:
                cc11[ev[2]] = ev[4]
            elif ev[3] == 64 and ev[4] >= 64:
                pedals[ti] += 1
            elif ev[3] in (120, 123):           # all sound / notes off
                for key in [k for k in open_notes if k[1] == ev[2]]:
                    for n in open_notes.pop(key):
                        n.t1 = tick
        elif kind == 'bend':
            if ev[3] != 8192:
                bends[ti] += 1
        elif kind == 'on':
            key = (ti, ev[2], ev[3])
            if open_notes[key]:                 # same key struck again
                for n in open_notes[key]:
                    n.t1 = tick
                open_notes[key] = []
                retriggers += 1
            amp = (ev[4] / 127) * (cc7[ev[2]] / 127) * (cc11[ev[2]] / 127)
            n = Note(ti, ev[2], ev[3], ev[4], tick, amp)
            if ev[2] in drum_channels:
                n.drum = GM_DRUMS.get(ev[3], 'perc')
            open_notes[key].append(n)
            notes.append(n)
        elif kind == 'off':
            key = (ti, ev[2], ev[3])
            if open_notes[key]:
                open_notes[key].pop(0).t1 = tick
    hanging = 0
    for key, lst in open_notes.items():
        for n in lst:
            n.t1 = max(n.t1, max(e[0] for e in mf.tracks[key[0]]))
            hanging += 1
    if hanging:
        report.add('Ignored', '%d notes were never released; they end with '
                   'their track' % hanging)
    if retriggers:
        report.add('Timing', '%d notes were struck again while still '
                   'sounding; each ends where the next begins' % retriggers)
    for ti, count in sorted(bends.items()):
        report.add('Ignored', 'track %d: %d pitch-bend events (the chip has '
                   'no bend; notes play at their written pitch)'
                   % (ti + 1, count))
    for ti, count in sorted(pedals.items()):
        report.add('Ignored', 'track %d: sustain pedal pressed %d times (notes '
                   'end where written; holding them would crowd the voices)'
                   % (ti + 1, count))
    return notes, tempos, timesigs


def track_table(mf, notes, drum_channels):
    by_track = defaultdict(list)
    for n in notes:
        by_track[n.track].append(n)
    lines = ['Track  Notes  Channels  Range      Name']
    for ti in range(len(mf.tracks)):
        tn = by_track.get(ti, [])
        chans = sorted({n.channel + 1 for n in tn})
        if tn:
            lo = min(n.pitch for n in tn)
            hi = max(n.pitch for n in tn)
            rng = 'drums' if all(n.drum for n in tn) else \
                '%s-%s' % (tm.note_name(lo), tm.note_name(hi))
        else:
            rng = '-'
        lines.append('%5d  %5d  %-8s  %-9s  %s' % (
            ti + 1, len(tn), ','.join(map(str, chans)) or '-', rng,
            mf.track_name(ti)))
    return '\n'.join(lines)


# --------------------------------------------------------------- timing

def quantizer(ppq, grid_units):
    def q(tick):
        u = Fraction(tick * UNITS_PER_QUARTER) / ppq
        return int(round(u / grid_units)) * grid_units
    return q


def bar_starts(timesigs, end_units):
    """Bar start positions in units, honouring time-signature changes."""
    sigs = sorted(timesigs) or [(0, 4, 4)]
    if sigs[0][0] > 0:
        sigs.insert(0, (0, 4, 4))
    bars = []
    pos = 0
    i = 0
    while pos < end_units or not bars:
        while i + 1 < len(sigs) and sigs[i + 1][0] <= pos:
            i += 1
        num, den = sigs[i][1], min(max(sigs[i][2], 1), 64)
        length = max(1, tm.UNITS_PER_WHOLE * num // den)
        bars.append(pos)
        nxt = pos + length
        if i + 1 < len(sigs) and pos < sigs[i + 1][0] < nxt:
            nxt = sigs[i + 1][0]                # change in mid-bar
        pos = nxt
    bars.append(pos)
    return bars


def tick_function(tempos):
    """Same rounding rule as txamusic: each tempo starts a segment."""
    segs = []
    seg_tick = 0
    for i, (u, t) in enumerate(tempos):
        if i:
            pu, pt, ps = segs[-1]
            seg_tick = ps + tm.ticks_for(u - pu, pt)
        segs.append((u, t, seg_tick))

    def tick(u):
        k = 0
        while k + 1 < len(segs) and segs[k + 1][0] <= u:
            k += 1
        su, st, ss = segs[k]
        return ss + tm.ticks_for(u - su, st)
    return tick


# -------------------------------------------------------- voice reduction

def allocate(notes, voices, priority, report_counts):
    """Give each note a voice; steal from or drop the least important.

    Notes are taken in start order, the most important first among notes
    that start together. A new note takes a free voice (the one whose last
    pitch was nearest, so lines stay coherent); if none is free it replaces
    the least important sounding note, or is dropped if it is the least
    important itself.
    """
    out = {v: [] for v in voices}
    active = {v: None for v in voices}
    last_pitch = {v: None for v in voices}
    for n in sorted(notes, key=lambda n: (n.s, tuple(-x for x in priority(n)))):
        for v in voices:
            if active[v] is not None and active[v][1] <= n.s:
                active[v] = None
        twin = [v for v in voices if active[v] is not None and
                active[v][2].pitch == n.pitch]
        if twin:
            # the same pitch is already sounding: doubling it gains nothing
            v = twin[0]
            old = active[v]
            if priority(n)[0] <= priority(old[2])[0]:
                if n.e > old[1] and old[0] == n.s:
                    old[1] = n.e                    # keep the longer one
                report_counts['doubled'][n.track] += 1
                continue
        free = [v for v in voices if active[v] is None]
        if free:
            used = [v for v in free if last_pitch[v] is not None]
            if used:
                v = min(used, key=lambda v: (abs(last_pitch[v] - n.pitch),
                                             voices.index(v)))
            else:
                v = free[0]
        else:
            v = min(voices, key=lambda v: priority(active[v][2]))
            victim = active[v]
            if priority(n) <= priority(victim[2]):
                report_counts['dropped'][n.track] += 1
                continue
            if victim[0] >= n.s:
                out[v].remove(victim)
                report_counts['dropped'][victim[2].track] += 1
            else:
                victim[1] = n.s
                report_counts['cut'][victim[2].track] += 1
        rec = [n.s, n.e, n]
        out[v].append(rec)
        active[v] = rec
        last_pitch[v] = n.pitch
    return out


def reduce_drums(hits):
    """One noise voice: the most important hit at each moment wins."""
    by_start = defaultdict(list)
    for n in hits:
        by_start[n.s].append(n)
    starts = sorted(by_start)
    chosen = []
    lost = Counter()
    for i, s in enumerate(starts):
        group = sorted(by_start[s],
                       key=lambda n: (-DRUM_KINDS[n.drum]['pri'], -n.vel))
        win = group[0]
        for other in group[1:]:
            lost[other.drum] += 1
        length = DRUM_KINDS[win.drum]['length']
        end = s + length
        if i + 1 < len(starts):
            end = min(end, starts[i + 1])
        chosen.append((s, end, win))
    return chosen, lost


# ------------------------------------------------------ writing notation

_PIECES = []
for _n in tm.VALID_LENGTHS:
    for _d in range(3):
        try:
            _PIECES.append((tm.length_units(_n, _d), _n, _d))
        except ValueError:
            pass
_PIECES.sort(reverse=True)


def decompose(units, _cache={}):
    """Shortest list of (length, dots) adding up to `units`.

    Prefers fewer pieces, then fewer triplet lengths, then fewer dots.
    """
    if units in _cache:
        return _cache[units]
    best = [None] * (units + 1)
    best[0] = ((0, 0, 0), [])
    for u in range(1, units + 1):
        cand = None
        for pu, n, d in _PIECES:
            if pu > u or best[u - pu] is None:
                continue
            c, lst = best[u - pu]
            cost = (c[0] + 1, c[1] + (n % 3 == 0), c[2] + d)
            if cand is None or cost < cand[0]:
                cand = (cost, lst + [(n, d)])
        best[u] = cand
    result = sorted(best[units][1], key=lambda p: -tm.length_units(*p))
    _cache[units] = result
    return result


def voice_atoms(segs, total, bars, tempo_map, noise, default_len):
    """The notation tokens for one voice, before folding and wrapping."""
    tempo_at = dict(tempo_map)
    bar_set = set(bars[1:-1]) if bars else set()
    points = {0, total} | {s.s for s in segs} | {s.e for s in segs}
    points |= {b for b in bar_set if b < total}
    points |= {u for u in tempo_at if u < total}
    points = sorted(points)

    pieces = []
    k = 0
    for a, b in zip(points, points[1:]):
        while k < len(segs) and segs[k].e <= a:
            k += 1
        seg = segs[k] if k < len(segs) and segs[k].s <= a < segs[k].e else None
        pieces.append((a, b, seg))

    atoms = ['T%d' % tempo_at[0]]
    if default_len:
        atoms.append('L%d' % default_len)
    octave = vol = env = None
    vol, env = 15, 0
    lengths = Counter()

    def length_text(n, d):
        lengths[(n, d)] += 1
        if (n, d) == (default_len, 0):
            return ''
        return str(n) + '.' * d

    for i, (a, b, seg) in enumerate(pieces):
        if a in bar_set:
            atoms.append('|')
        if a in tempo_at and a:
            atoms.append('T%d' % tempo_at[a])
        parts = decompose(b - a)
        if seg is None:
            atoms += ['R' + length_text(n, d) for n, d in parts]
            continue
        cont = i > 0 and pieces[i - 1][2] is seg
        if not cont:
            if seg.vol != vol:
                atoms.append('V%d' % seg.vol)
                vol = seg.vol
            if seg.env != env:
                atoms.append('@%d' % seg.env)
                env = seg.env
            if noise:
                white, rate = seg.key
                if rate != octave:
                    atoms.append('O%d' % rate)
                    octave = rate
            else:
                want = seg.key // 12 - 1
                if octave is not None and want == octave + 1:
                    atoms.append('>')
                elif octave is not None and want == octave - 1:
                    atoms.append('<')
                elif want != octave:
                    atoms.append('O%d' % want)
                octave = want
        if noise:
            name = 'W' if seg.key[0] else 'P'
        else:
            name = tm.NOTE_NAMES[seg.key % 12]
        text = '&'.join(name + length_text(n, d) for n, d in parts)
        if i + 1 < len(pieces) and pieces[i + 1][2] is seg:
            text += '&'
        atoms.append(text)
    return atoms, lengths


def fold_repeats(atoms, max_block=48):
    """Replace runs of identical atom blocks with [ ... ]n.

    Safe whatever the block holds: the folded text expands to exactly the
    tokens that were there before.
    """
    out = []
    i = 0
    n = len(atoms)
    while i < n:
        best = None
        for k in range(min(max_block, (n - i) // 2), 0, -1):
            block = atoms[i:i + k]
            r = 1
            while r < tm.MAX_REPEAT and atoms[i + r * k:i + (r + 1) * k] == block:
                r += 1
            if r >= 2:
                width = sum(len(a) + 1 for a in block)
                saving = (r - 1) * width - (4 + len(str(r)))
                if saving > 0 and (best is None or saving > best[0]):
                    best = (saving, k, r)
        if best:
            _, k, r = best
            out += ['['] + atoms[i:i + k] + [']%d' % r]
            i += k * r
        else:
            out.append(atoms[i])
            i += 1
    return out


def wrap(label, atoms):
    lines = []
    cur = label + ':'
    for a in atoms:
        if len(cur) + 1 + len(a) > LINE_WIDTH:
            lines.append(cur)
            cur = label + ':'
        cur += ' ' + a
    lines.append(cur)
    return lines


def expected_state(segs, tick, total_ticks, noise, env_steps):
    state = [(0, 15)] * total_ticks
    for s in segs:
        value = tm.noise_value(*s.key) if noise else tm.TONE_TABLE[s.key]
        steps = env_steps.get(s.env, [0])
        last = len(steps) - 1
        t0, t1 = tick(s.s), tick(s.e)
        for t in range(t0, t1):
            k = t - t0
            att = 15 - s.vol + steps[k if k < last else last]
            state[t] = (value, att) if att < 15 else (0, 15)
    return state


# ------------------------------------------------------------- the driver

def parse_tracks(text, count):
    if not text:
        return []
    out = []
    for part in text.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    for t in out:
        if not 1 <= t <= count:
            raise ConvertError('there is no track %d (the file has %d)'
                               % (t, count))
    return [t - 1 for t in out]


def ti_name(text):
    name = re.sub(r'[^A-Z0-9]', '', text.upper())[:10]
    return name or 'MUSIC'


def convert(args):
    report = Report()
    mf = smf.load(args.midi)
    for w in mf.warnings:
        report.add('Source', w)
    drum_channels = set() if args.no_drums else {args.drum_channel - 1}
    notes, tempos, timesigs = gather(mf, drum_channels, report)
    table = track_table(mf, notes, drum_channels)
    if args.list:
        print(table)
        return 0
    if not notes:
        raise ConvertError('the file has no notes')

    report.add('Source', '%s: format %d, %d tracks, %d notes'
               % (os.path.basename(args.midi), mf.format, len(mf.tracks),
                  len(notes)))
    for line in table.splitlines():
        report.add('Source', line)

    ntracks = len(mf.tracks)
    keep = parse_tracks(args.tracks, ntracks)
    drop = set(parse_tracks(args.drop, ntracks))
    notes = [n for n in notes if (not keep or n.track in keep)
             and n.track not in drop]
    if not notes:
        raise ConvertError('no notes left after --tracks/--drop')

    # ---- timing
    grid = tm.UNITS_PER_WHOLE // args.grid
    q = quantizer(mf.ppq, grid)
    moved = 0
    max_shift = Fraction(0)
    stretched = 0
    for n in notes:
        exact = Fraction(n.t0 * UNITS_PER_QUARTER) / mf.ppq
        n.s = q(n.t0)
        n.e = q(n.t1)
        if n.s != exact:
            moved += 1
            max_shift = max(max_shift, abs(n.s - exact))
        if n.e <= n.s:
            n.e = n.s + grid
            if not n.drum:
                stretched += 1
    if mf.smpte:
        report.add('Timing', 'the file uses SMPTE timing, which has no beat; '
                   'it is read as 120 BPM')
    report.add('Timing', 'grid: 1/%d notes' % args.grid)
    if moved:
        report.add('Timing', '%d note starts moved to the grid (largest move '
                   '%.2f of a grid step)' % (moved, max_shift / grid))
    if stretched:
        report.add('Timing', '%d notes shorter than a grid step were '
                   'lengthened to one step' % stretched)

    qtempos = {}
    for tick, bpm in sorted(tempos):
        qtempos[q(tick)] = bpm * args.tempo_scale
    if 0 not in qtempos:                       # MIDI: 120 until told
        qtempos[0] = 120.0 * args.tempo_scale
    qsigs = sorted((q(t), num, den) for t, num, den in timesigs)

    song_end = max(n.e for n in notes)
    bars = bar_starts(qsigs, song_end)

    # ---- excerpt
    if args.bars:
        m = re.match(r'^(\d+)(?:-(\d+))?$', args.bars)
        if not m:
            raise ConvertError('--bars takes FROM-TO, such as 9-24')
        b0 = int(m.group(1))
        b1 = int(m.group(2) or m.group(1))
        if not 1 <= b0 <= b1 < len(bars):
            raise ConvertError('--bars %s: the piece has %d bars'
                               % (args.bars, len(bars) - 1))
        start, stop = bars[b0 - 1], bars[b1]
        kept = []
        for n in notes:
            if n.e <= start or n.s >= stop:
                continue
            n.s = max(n.s, start) - start
            n.e = min(n.e, stop) - start
            kept.append(n)
        notes = kept
        if not notes:
            raise ConvertError('no notes in bars %s' % args.bars)
        before = [u for u in qtempos if u <= start]
        newt = {0: qtempos[max(before)]}
        for u, t in qtempos.items():
            if start < u < stop:
                newt[u - start] = t
        qtempos = newt
        sig_before = [s for s in qsigs if s[0] <= start]
        qsigs = ([(0,) + sig_before[-1][1:]] if sig_before else []) + \
            [(u - start, a, b) for u, a, b in qsigs if start < u < stop]
        song_end = stop - start
        bars = bar_starts(qsigs, song_end)
        report.add('Timing', 'excerpt: bars %d to %d' % (b0, b1))
    elif not args.no_pad:
        song_end = next(b for b in bars if b >= song_end)
    bars = [b for b in bars if b <= song_end]
    if bars[-1] != song_end:
        bars.append(song_end)

    tempo_map = []
    for u in sorted(qtempos):
        if u >= song_end:
            continue
        t = int(round(qtempos[u]))
        t = min(max(t, tm.TEMPO_MIN), tm.TEMPO_MAX)
        err = abs(t - qtempos[u]) / qtempos[u]
        if err > 0.005:
            report.add('Timing', 'tempo %.2f BPM at bar %d rounded to %d '
                       '(%.1f%%)' % (qtempos[u], _bar_of(bars, u), t, err * 100))
        if not tempo_map or tempo_map[-1][1] != t:
            tempo_map.append((u, t))
    report.add('Timing', 'tempo: %s' % ', '.join(
        '%d from bar %d' % (t, _bar_of(bars, u)) for u, t in tempo_map))

    tone = [n for n in notes if not n.drum]
    hits = [n for n in notes if n.drum]

    # ---- range
    if tone:
        shift = args.transpose
        if args.auto_transpose:
            def folds(sh):
                return sum(1 for n in tone if not
                           tm.LOW_NOTE <= n.pitch + sh <= tm.HIGH_NOTE)
            shift = min((-36, -24, -12, 0, 12, 24, 36),
                        key=lambda sh: (folds(sh), abs(sh)))
            report.add('Range', 'auto-transpose chose %+d semitones' % shift)
        elif shift:
            report.add('Range', 'transposed %+d semitones' % shift)
        folded = Counter()
        for n in tone:
            p = n.pitch + shift
            while p < tm.LOW_NOTE:
                p += 12
            while p > tm.HIGH_NOTE:
                p -= 12
            if p != n.pitch + shift:
                folded[(n.track, 'up' if p > n.pitch + shift else 'down')] += 1
            n.pitch = p
        for (ti, way), c in sorted(folded.items()):
            report.add('Range', 'track %d: %d notes folded %s by octaves into '
                       'A2-B7' % (ti + 1, c, way))

    # ---- voices
    tone_voices = [v for v in 'ABC' if v in args.tone_voices.upper()]
    if not tone_voices:
        raise ConvertError('--tone-voices must name at least one of A, B, C')
    prefer = parse_tracks(args.prefer, ntracks)

    def make_priority(low):
        def pri(n):
            rank = len(prefer) - prefer.index(n.track) if n.track in prefer \
                else 0
            return (rank, -n.pitch if low else n.pitch, n.vel)
        return pri

    counts = {'dropped': Counter(), 'cut': Counter(), 'doubled': Counter()}
    assigned = {}
    pinned_tracks = set()
    for spec in args.voice or []:
        m = re.match(r'^([ABC]):([\d,\-]+)(?::(high|low))?$', spec, re.I)
        if not m:
            raise ConvertError('--voice takes V:TRACKS[:high|low], such as '
                               'C:3:low')
        v = m.group(1).upper()
        if v not in tone_voices:
            raise ConvertError('--voice %s: voice %s is not in --tone-voices'
                               % (spec, v))
        if v in assigned:
            raise ConvertError('voice %s is pinned twice' % v)
        trk = set(parse_tracks(m.group(2), ntracks))
        pinned_tracks |= trk
        low = (m.group(3) or 'high').lower() == 'low'
        mine = [n for n in tone if n.track in trk]
        assigned[v] = allocate(mine, [v], make_priority(low), counts)[v]
        report.add('Voices', 'voice %s: track%s %s only, %s note wins'
                   % (v, 's' if len(trk) > 1 else '',
                      ','.join(str(t + 1) for t in sorted(trk)),
                      'lowest' if low else 'highest'))
    pool_voices = [v for v in tone_voices if v not in assigned]
    pool = [n for n in tone if n.track not in pinned_tracks]
    if pool and pool_voices:
        res = allocate(pool, pool_voices, make_priority(False), counts)
        assigned.update(res)
        report.add('Voices', 'voice%s %s: shared by the other tracks, '
                   'highest notes first%s'
                   % ('s' if len(pool_voices) > 1 else '',
                      ','.join(pool_voices),
                      ' (preferring track %s)' % ','.join(
                          str(t + 1) for t in prefer) if prefer else ''))
    elif pool:
        for n in pool:
            counts['dropped'][n.track] += 1
        report.add('Voices', '%d notes from unpinned tracks have no voice '
                   'left' % len(pool))
    for ti, c in sorted(counts['dropped'].items()):
        report.add('Voices', 'track %d: %d notes dropped (no free voice)'
                   % (ti + 1, c))
    for ti, c in sorted(counts['doubled'].items()):
        report.add('Voices', 'track %d: %d notes merged into the same pitch '
                   'already sounding' % (ti + 1, c))
    for ti, c in sorted(counts['cut'].items()):
        report.add('Voices', 'track %d: %d notes cut short by a more '
                   'important note' % (ti + 1, c))
    if len(tone_voices) < 3:
        report.add('Voices', 'voice%s %s left free for sound effects'
                   % ('s' if 3 - len(tone_voices) > 1 else '',
                      ','.join(v for v in 'ABC' if v not in tone_voices)))

    drum_segs = []
    if hits:
        chosen, lost = reduce_drums(hits)
        drum_segs = chosen
        kinds = Counter(n.drum for n in hits)
        report.add('Drums', 'mapped to the noise voice: %s' % ', '.join(
            '%s %d' % kv for kv in sorted(kinds.items())))
        unmapped = sorted({n.pitch for n in hits if n.pitch not in GM_DRUMS})
        if unmapped:
            report.add('Drums', 'drum notes with no specific sound, played '
                       'as short noise: %s' % ', '.join(map(str, unmapped)))
        for kind, c in sorted(lost.items()):
            report.add('Drums', '%d %s hits dropped (struck with a more '
                       'important drum)' % (c, kind))
    elif not args.no_drums:
        report.add('Drums', 'no drums on channel %d' % args.drum_channel)

    # ---- envelopes and volume
    used_envs = []
    if args.tone_env != 'flat':
        used_envs.append(args.tone_env)
    for _, _, n in drum_segs:
        e = DRUM_KINDS[n.drum]['env']
        if e not in used_envs:
            used_envs.append(e)
    used_envs.sort(key=ENV_ORDER.index)
    env_num = {name: i + 1 for i, name in enumerate(used_envs)}
    env_steps = {env_num[name]: ENVELOPES[name] for name in used_envs}

    def att_of(n):
        return -20 * math.log10(max(n.amp, 1e-4)) / 2

    def volumes(items, boost, label):
        if not items:
            return {}
        raw = {id(n): att_of(n) for n in items}
        offset = 0 if args.no_normalize else min(raw.values())
        out = {}
        clamped = 0
        for n in items:
            att = int(round(raw[id(n)] - offset)) - boost
            if att > 14:
                clamped += 1
            out[id(n)] = 15 - min(max(att, 0), 14)
        if offset > 0.5 and not args.no_normalize:
            report.add('Volume', '%s raised %d dB so the loudest note is full '
                       'volume' % (label, int(round(offset)) * 2))
        if clamped:
            report.add('Volume', '%s: %d very quiet notes kept at V1 rather '
                       'than silent' % (label, clamped))
        spread = Counter(out.values())
        report.add('Volume', '%s volumes used: %s' % (label, ', '.join(
            'V%d x%d' % kv for kv in sorted(spread.items(), reverse=True))))
        return out

    tone_sounded = [rec[2] for v in assigned for rec in assigned[v]]
    tvol = volumes(tone_sounded, args.tone_volume, 'tone')
    dvol = volumes([n for _, _, n in drum_segs], args.drum_volume, 'drums')
    tone_env = env_num.get(args.tone_env, 0)

    held = [0]

    def steady(vols):
        """Keep a voice's volume unless it moves more than the tolerance."""
        out = []
        cur = None
        for vol in vols:
            if cur is None or abs(vol - cur) > args.volume_tolerance:
                cur = vol
            elif vol != cur:
                held[0] += 1
            out.append(cur)
        return out

    voice_segs = {}
    for v in tone_voices:
        recs = [r for r in sorted(assigned.get(v, []), key=lambda r: r[0])
                if r[1] > r[0]]
        vols = steady([tvol[id(n)] for _, _, n in recs])
        segs = [Seg(s, e, n.pitch, vol, tone_env)
                for (s, e, n), vol in zip(recs, vols)]
        if segs:
            voice_segs[v] = segs
    if drum_segs:
        # each drum kind keeps its own level, smoothed like a tone voice
        kind_vols = defaultdict(list)
        for _, _, n in drum_segs:
            kind_vols[n.drum].append(dvol[id(n)])
        smoothed = {k: iter(steady(vs)) for k, vs in kind_vols.items()}
        voice_segs['N'] = [
            Seg(s, e, (DRUM_KINDS[n.drum]['white'], DRUM_KINDS[n.drum]['rate']),
                next(smoothed[n.drum]), env_num[DRUM_KINDS[n.drum]['env']])
            for s, e, n in drum_segs]
    if held[0]:
        report.add('Volume', '%d small volume changes (%d step%s or less) '
                   'smoothed away' % (held[0], args.volume_tolerance,
                                      '' if args.volume_tolerance == 1 else 's'))
    if not voice_segs:
        raise ConvertError('nothing left to play')

    # ---- detune
    used = sorted({s.key for v, segs in voice_segs.items() if v != 'N'
                   for s in segs})
    off = []
    for p in used:
        hz = tm.CHIP_DIVIDER / tm.TONE_TABLE[p]
        ideal = 440 * 2 ** ((p - 69) / 12)
        cents = 1200 * math.log2(hz / ideal)
        if abs(cents) > 10:
            off.append('%s %+.0f' % (tm.note_name(p), cents))
    if off:
        report.add('Range', 'the chip cannot tune these exactly (cents): %s'
                   % ', '.join(off))

    # ---- notation
    name = ti_name(args.name or os.path.splitext(os.path.basename(
        args.midi))[0])
    lines = ['! %s - TXA music, converted from %s by midi2txa %s'
             % (name, _ascii(os.path.basename(args.midi))[:30], VERSION)]
    opts = [_ascii(a)[:60] for a in args.argv if a != args.midi]
    if opts:
        for chunk in wrap('!', ['options:'] + opts):
            lines.append('!' + chunk[2:])
    for name_, num in sorted(env_num.items(), key=lambda kv: kv[1]):
        lines.append('ENV %d %s   ! %s' % (num, env_text(ENVELOPES[name_]),
                                          name_))
    bar_list = None if args.no_bars else bars
    for v in ('A', 'B', 'C', 'N'):
        if v not in voice_segs:
            continue
        noise = v == 'N'
        _, lengths = voice_atoms(voice_segs[v], song_end, bar_list,
                                 tempo_map, noise, None)
        plain = Counter({k: c for k, c in lengths.items() if k[1] == 0})
        default = plain.most_common(1)[0][0][0] if plain else 4
        atoms, _ = voice_atoms(voice_segs[v], song_end, bar_list,
                               tempo_map, noise, default)
        if not args.no_repeats:
            atoms = fold_repeats(atoms)
        lines += wrap(v, atoms)
    text = '\n'.join(lines) + '\n'

    # ---- check our own output against the reference compiler
    song = tm.compile_text(text)
    tick = tick_function(tempo_map)
    total_ticks = tick(song_end)
    if song.ticks != total_ticks:
        raise RuntimeError('internal: notation is %d ticks, expected %d'
                           % (song.ticks, total_ticks))
    for v, segs in voice_segs.items():
        want = expected_state(segs, tick, total_ticks, v == 'N', env_steps)
        got = song.voices[v]
        if got != want:
            t = next(i for i in range(total_ticks) if got[i] != want[i])
            raise RuntimeError('internal: voice %s differs at tick %d '
                               '(%r, expected %r)' % (v, t, got[t], want[t]))

    out_path = args.output or name + '.txm'
    with open(out_path, 'w', newline='\n') as f:
        f.write(text)
    report.add('Output', '%s: %d lines, %d bytes; TI file name %s'
               % (out_path, len(lines), len(text), name))
    report.add('Output', '%.1f seconds, %d bars, notes per voice: %s'
               % (song.seconds, len(bars) - 1, ', '.join(
                   '%s %d' % kv for kv in song.note_counts.items())))
    for w in song.warnings:
        report.add('Output', 'warning: ' + w)
    if args.events:
        tm.write_events(song, args.events)
        report.add('Output', 'internal form written to %s' % args.events)
    if args.wav:
        import snpreview
        snpreview.render(song, args.wav, loops=args.loops)
        report.add('Output', 'preview written to %s' % args.wav)

    rep = report.text()
    rep_path = os.path.splitext(out_path)[0] + '.report.txt'
    with open(rep_path, 'w') as f:
        f.write(rep)
    if not args.quiet:
        print(rep)
    return 0


def _ascii(text):
    return text.encode('ascii', 'replace').decode('ascii')


def env_text(steps):
    """An envelope in ENV form, runs written as value*count."""
    out = []
    i = 0
    while i < len(steps):
        j = i
        while j < len(steps) and steps[j] == steps[i]:
            j += 1
        out.append(str(steps[i]) if j - i == 1 else '%d*%d' % (steps[i], j - i))
        i = j
    return ' '.join(out)


def _bar_of(bars, u):
    k = 0
    while k + 1 < len(bars) and bars[k + 1] <= u:
        k += 1
    return k + 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='midi2txa',
        description='Convert a Standard MIDI File to TXA music notation '
                    '(three tone voices and a noise voice for the TMS9919).',
        epilog='Tracks are numbered from 1, as --list shows them.')
    ap.add_argument('midi', help='the .mid file')
    ap.add_argument('-o', '--output', help='output file (default NAME.txm)')
    ap.add_argument('--name', help='TI file name, up to 10 letters and digits '
                    '(default: from the MIDI file name)')
    ap.add_argument('--list', action='store_true',
                    help='list the tracks and stop')
    g = ap.add_argument_group('choosing notes')
    g.add_argument('--tracks', help='use only these tracks, e.g. 2,3,5-7')
    g.add_argument('--drop', help='leave these tracks out')
    g.add_argument('--prefer', help='tracks whose notes win a voice first, '
                   'most important first, e.g. 2,4')
    g.add_argument('--voice', action='append', metavar='V:TRACKS[:high|low]',
                   help='give a voice to these tracks alone, e.g. C:3:low for '
                   'a bass line (repeatable)')
    g.add_argument('--tone-voices', default='ABC',
                   help='tone voices the music may use (ABC); AB leaves C '
                   'free for sound effects')
    g.add_argument('--bars', help='convert only these bars, e.g. 9-24 '
                   '(for a loop)')
    g = ap.add_argument_group('pitch and timing')
    g.add_argument('--grid', type=int, default=16,
                   choices=[4, 8, 12, 16, 24, 32, 48, 64, 96, 192],
                   help='quantize to 1/N notes (default 16; 24 or 48 keep '
                   'triplets)')
    g.add_argument('--transpose', type=int, default=0,
                   help='semitones to shift every tone note')
    g.add_argument('--auto-transpose', action='store_true',
                   help='shift by whole octaves to fold the fewest notes')
    g.add_argument('--tempo-scale', type=float, default=1.0,
                   help='multiply every tempo, e.g. 0.9 for slower')
    g = ap.add_argument_group('drums, sound and volume')
    g.add_argument('--drum-channel', type=int, default=10,
                   help='MIDI channel holding drums (default 10)')
    g.add_argument('--no-drums', action='store_true',
                   help='ignore drums; no noise voice')
    g.add_argument('--tone-env', default='flat',
                   choices=['flat', 'decay', 'pluck'],
                   help='volume shape for tone notes (default flat)')
    g.add_argument('--tone-volume', type=int, default=0,
                   help='volume steps to add to tone voices (2 dB each)')
    g.add_argument('--drum-volume', type=int, default=0,
                   help='volume steps to add to the noise voice')
    g.add_argument('--volume-tolerance', type=int, default=1,
                   help='ignore volume changes of this many steps or fewer '
                   'within a voice (default 1; 0 keeps every change)')
    g.add_argument('--no-normalize', action='store_true',
                   help='keep MIDI loudness as it is instead of raising the '
                   'loudest note to full volume')
    g = ap.add_argument_group('output')
    g.add_argument('--no-bars', action='store_true',
                   help='leave out the | bar lines')
    g.add_argument('--no-repeats', action='store_true',
                   help='do not fold repeated passages into [ ]n')
    g.add_argument('--no-pad', action='store_true',
                   help='end at the last note instead of the end of its bar')
    g.add_argument('--wav', help='also render a preview WAV')
    g.add_argument('--loops', type=int, default=1,
                   help='times to play the piece in the WAV (2 checks the loop)')
    g.add_argument('--events', help='also write the per-tick internal form '
                   'as CSV')
    g.add_argument('-q', '--quiet', action='store_true',
                   help='do not print the report')
    args = ap.parse_args(argv)
    args.argv = list(sys.argv[1:] if argv is None else argv)
    try:
        return convert(args)
    except (ConvertError, smf.MidiError, OSError) as exc:
        print('midi2txa: %s' % exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
