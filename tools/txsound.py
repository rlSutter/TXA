#!/usr/bin/env python3
"""txsound.py - music and sound effects for the TI build.

A story declares tunes and effects by name and file (MUSIC Harbour
"HARBOUR", SOUND Horn "HORN"); the story image holds only their numbers
(portability rule 3).  This tool, part of the TI build, compiles each
file's notation into events for the TMS9919, lays them out as the sound
area (in SAMS after the pictures), and is the reference player the TI
engine's player is tested against, write for write.

THE NOTATION (one .mml text file per tune or effect)
  ! a comment, to the end of the line
  TEMPO 90          quarter notes a minute (default 120)
  LOOP              the tune starts again when it ends (music; effects
                    usually play once)
  A: ...  B: ...  C: ...   the three tone voices; N: ... the noise voice.
                    A voice may take several lines; they join up.
In a voice:
  c d e f g a b     a note; then + (or #) sharp, - flat; then a length
                    (1 2 4 8 16 32: whole, half ... thirty-second) and
                    dots (each adds half again).  Middle C is c4.
  r                 a rest, with a length the same way
  o4  < >           the octave (1-7); one down, one up
  l8                the default length (dots allowed: l2. in 3/4 time)
  v12               the volume, 0 (silent) to 15 (loudest)
  @4                decay: the volume falls one step every 4 frames
                    while a note sounds (@0: none, the default)
  &                 ties the next note to this one (no new attack)
  [ ... ]3          plays what's inside 3 times (2 if no number)
  |                 a bar line, for the eye only
On the noise voice the notes are k (a low drum: periodic noise), s (a
snare: white noise), h (a hi-hat: high white noise), x (a high buzz:
periodic), or n0-n7 (the chip's noise types); lengths, r, v, @ as above.

THE EVENTS (each voice a byte stream)
  >01 pp pp dd   a tone: period (10 bits), then dd frames (1-255)
  >02 dd         a rest of dd frames (silent)
  >03 vv         volume vv (0-15) for the following notes
  >04 ee         decay: one step every ee frames (0: none)
  >05 tt dd      noise type tt (0-7) for dd frames
  >06 dd         hold: the note goes on dd more frames (long notes, ties)
  >00            the voice's end
A frame is a sixtieth of a second (the VDP's frame flag).

THE SOUND AREA
  word  M (tunes)   word  S (effects)
  (M+S) x long  each item's offset from the area's start: tunes first,
                then effects (MUSIC n is item n, SOUND n item M+n)
  each item: byte voices, byte flags (1: loops), then per voice
             byte channel (0-2 tone, 3 noise), word its stream's offset
             from the item's start; then the streams

THE PLAYER (the same on the TI: src/sound.a99)
Once a frame, for each voice in order (music voices, then effect voices):
  if it is waiting: one frame less; if a note sounds with a decay, the
  decay count goes down and at 0 restarts and the volume falls a step
  (written to the chip); then, if the wait has run out, events are read
  until one takes time (a tone, a rest, noise or hold) or the voice ends.
  A tone writes the period (two bytes) and the volume (one byte); a rest
  writes silence; noise writes the type and the volume.  At its end a
  voice of a looping item starts its stream again; otherwise it falls
  silent and stops.  While an effect voice uses a channel the music voice
  on it writes nothing; when the effect voice ends, the music voice's
  last period and volume are written back."""
import os, re, sys

FRAMES_PER_MIN = 3600
CLOCK = 3579545 / 32                      # the TMS9919: f = CLOCK / period
NOTE = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
DRUM = {'k': 6, 's': 5, 'h': 4, 'x': 0}   # periodic/white and shift rate
VOICES = 'ABCN'

class MMLError(Exception):
    pass

def period_of(octave, semitone):
    midi = 12 * (octave + 1) + semitone   # c4 = 60
    f = 440.0 * 2 ** ((midi - 69) / 12)
    p = round(CLOCK / f)
    if not 1 <= p <= 1023:
        raise MMLError(f'note out of the TI\'s range (o{octave}, about {f:.0f} Hz): the lowest is about 110 Hz (a2)')
    return p

def parse(text, name='?'):
    """The file as {'tempo', 'loop', 'voices': {letter: [token lists]}}."""
    tempo, loop, voices = 120, False, {}
    cur = None
    for n, raw in enumerate(text.split('\n'), 1):
        line = raw.split('!')[0].strip()
        if not line:
            continue
        m = re.match(r'(?i)^TEMPO\s+(\d+)$', line)
        if m:
            tempo = int(m.group(1)); continue
        if line.upper() == 'LOOP':
            loop = True; continue
        m = re.match(r'(?i)^([ABCN])\s*:(.*)$', line)
        if m:
            cur = m.group(1).upper(); line = m.group(2)
        elif cur is None:
            raise MMLError(f'{name} line {n}: expected TEMPO, LOOP or a voice (A: B: C: N:)')
        voices.setdefault(cur, []).append((n, line))
    if not 20 <= tempo <= 400:
        raise MMLError(f'{name}: TEMPO {tempo} is outside 20-400')
    return {'tempo': tempo, 'loop': loop, 'voices': voices}

def voice_events(lines, letter, tempo, name):
    """One voice's notation as events [(kind, args...)] with exact frame
    timing (rounding error carried, so voices stay together)."""
    text = ' '.join(l for _, l in lines)
    noise = letter == 'N'
    # expand [ ... ]n repeats
    while '[' in text:
        m = re.search(r'\[([^\[\]]*)\](\d*)', text)
        if not m:
            raise MMLError(f'{name} voice {letter}: unmatched [ or ]')
        text = text[:m.start()] + ' '.join([m.group(1)] * int(m.group(2) or 2)) + text[m.end():]
    if ']' in text:
        raise MMLError(f'{name} voice {letter}: unmatched ]')
    octave, deflen, defdots, t_exact, t_frames = 4, 4, 0, 0.0, 0
    out, i, tie = [], 0, False
    quarter = FRAMES_PER_MIN / tempo
    def length_at(j):
        m = re.match(r'(\d*)(\.*)', text[j:])
        ln = int(m.group(1)) if m.group(1) else deflen
        dots = m.group(2) if m.group(1) else '.' * defdots + m.group(2)
        if ln not in (1, 2, 4, 8, 16, 32, 64):
            raise MMLError(f'{name} voice {letter}: length {ln} (use 1 2 4 8 16 32 64)')
        d = 4 / ln
        add = d
        for _ in dots:
            add /= 2; d += add
        return d, j + m.end()
    def frames_for(beats):
        nonlocal t_exact, t_frames
        t_exact += beats * quarter
        f = round(t_exact) - t_frames
        t_frames += f
        return f
    def emit_timed(kind, args, f):
        first = True
        while f > 0:
            d = min(f, 255)
            out.append((kind,) + args + (d,) if first else ('hold', d))
            first = False; f -= d
    while i < len(text):
        ch = text[i].lower()
        if ch in ' \t|':
            i += 1; continue
        if ch == '&':
            tie = True; i += 1; continue
        if ch == 'o':
            m = re.match(r'\d', text[i + 1:])
            if not m: raise MMLError(f'{name} voice {letter}: o needs a number')
            octave = int(text[i + 1]); i += 2; continue
        if ch in '<>':
            octave += -1 if ch == '<' else 1; i += 1; continue
        if ch in 'lv@':
            m = re.match(r'(\d+)(\.*)' if ch == 'l' else r'(\d+)', text[i + 1:])
            if not m: raise MMLError(f'{name} voice {letter}: {ch} needs a number')
            v = int(m.group(1)); i += 1 + m.end()
            if ch == 'l':
                if v not in (1, 2, 4, 8, 16, 32, 64): raise MMLError(f'{name} voice {letter}: l{v}')
                deflen, defdots = v, len(m.group(2))
            elif ch == 'v':
                if v > 15: raise MMLError(f'{name} voice {letter}: v{v} (0-15)')
                out.append(('vol', v))
            else:
                if v > 255: raise MMLError(f'{name} voice {letter}: @{v}')
                out.append(('env', v))
            continue
        if ch == 'r':
            beats, i = length_at(i + 1)
            emit_timed('rest', (), frames_for(beats)); tie = False; continue
        if noise:
            if ch in DRUM:
                kind = DRUM[ch]; i += 1
            elif ch == 'n':
                if i + 1 >= len(text) or not text[i + 1].isdigit() or int(text[i + 1]) > 7:
                    raise MMLError(f'{name} voice N: n0-n7')
                kind = int(text[i + 1]); i += 2
            else:
                raise MMLError(f'{name} voice N: {text[i]!r} (noise notes are k s h x n0-n7)')
            beats, i = length_at(i)
            f = frames_for(beats)
            if tie and out and out[-1][0] in ('noise', 'hold'):
                emit_timed('hold', (), f)
            else:
                emit_timed('noise', (kind,), f)
            tie = False; continue
        if ch in NOTE:
            semi = NOTE[ch]; i += 1
            while i < len(text) and text[i] in '+#-':
                semi += -1 if text[i] == '-' else 1; i += 1
            o, s = octave + semi // 12, semi % 12
            beats, i = length_at(i)
            f = frames_for(beats)
            p = period_of(o, s)
            if tie and out and out[-1][0] in ('tone', 'hold'):
                emit_timed('hold', (), f)
            else:
                emit_timed('tone', (p,), f)
            tie = False; continue
        raise MMLError(f'{name} voice {letter}: unexpected {text[i]!r}')
    return out

def compile_text(text, name='?'):
    """(loop, [(channel, events)]) for a notation file's text."""
    tune = parse(text, name)
    if not tune['voices']:
        raise MMLError(f'{name}: no voices')
    voices, lengths = [], {}
    for letter in VOICES:
        if letter in tune['voices']:
            ev = voice_events(tune['voices'][letter], letter, tune['tempo'], name)
            voices.append((VOICES.index(letter), ev))
            lengths[letter] = sum(e[-1] for e in ev if e[0] in ('tone', 'rest', 'noise', 'hold'))
    if tune['loop']:
        if 0 in lengths.values():
            raise MMLError(f'{name}: a looping voice must take some time')
        if len(set(lengths.values())) > 1:
            raise MMLError(f'{name}: a looping tune\'s voices must be the same length (in frames: '
                           + ', '.join(f'{k} {v}' for k, v in lengths.items()) + ')')
    return tune['loop'], voices

def stream_bytes(events):
    out = bytearray()
    for e in events:
        k = e[0]
        if k == 'tone': out += bytes([1, e[1] >> 8, e[1] & 255, e[2]])
        elif k == 'rest': out += bytes([2, e[1]])
        elif k == 'vol': out += bytes([3, e[1]])
        elif k == 'env': out += bytes([4, e[1]])
        elif k == 'noise': out += bytes([5, e[1], e[2]])
        elif k == 'hold': out += bytes([6, e[1]])
    return bytes(out + b'\x00')

def item_bytes(loop, voices):
    streams = [stream_bytes(ev) for _, ev in voices]
    head = 2 + 3 * len(voices)
    out = bytearray([len(voices), 1 if loop else 0])
    off = head
    for (ch, _), s in zip(voices, streams):
        out += bytes([ch]) + off.to_bytes(2, 'big'); off += len(s)
    for s in streams:
        out += s
    return bytes(out)

def find_file(name, dirs):
    for d in dirs:
        for cand in (name, name.lower(), name.upper()):
            for ext in ('.mml', '.MML', '.txt'):
                p = os.path.join(d, cand + ext)
                if os.path.exists(p):
                    return p
    return None

def sound_area(info, dirs):
    """The sound area for a compiled story (compile_file's info), notation
    files looked for in dirs; b'' when it declares no tunes or effects."""
    prog = info['program']
    tunes = sorted(getattr(prog, 'musics', []), key=lambda s: s.number)
    sounds = sorted(getattr(prog, 'sounds', []), key=lambda s: s.number)
    if not tunes and not sounds:
        return b''
    items = []
    for sym in tunes + sounds:
        p = find_file(sym.decl.path, dirs)
        if p is None:
            sys.exit(f'{sym.kind} {sym.name}: no {sym.decl.path}.mml in ' + ', '.join(dirs))
        try:
            loop, voices = compile_text(open(p).read(), os.path.basename(p))
            if sym.kind == 'sound' and len(voices) > 2:
                raise MMLError(f'{os.path.basename(p)}: an effect may use at most two voices')
            items.append(item_bytes(loop, voices))
        except MMLError as e:
            sys.exit(str(e))
    out = bytearray(len(tunes).to_bytes(2, 'big') + len(sounds).to_bytes(2, 'big'))
    off = 4 + 4 * len(items)
    offs = []
    for it in items:
        offs.append(off); off += len(it)
    for o in offs:
        out += o.to_bytes(4, 'big')
    for it in items:
        out += it
    return bytes(out)

# ---- the reference player ---------------------------------------------------
class Voice:
    def __init__(self, data, start, ch, loop, effect):
        self.data, self.start, self.p, self.ch, self.loop, self.effect = data, start, start, ch, loop, effect
        self.wait = 0; self.vol = 15; self.cur = 0; self.env = 0; self.envc = 0
        self.period = 0; self.sounding = False; self.active = True

class Player:
    """The player, a frame at a time: tick() returns that frame's chip writes."""
    def __init__(self, area):
        self.area = area
        self.m = int.from_bytes(area[:2], 'big') if area else 0
        self.music, self.fx = [], []
        self.cur = 0

    def item(self, k):
        o = int.from_bytes(self.area[4 + 4 * k:8 + 4 * k], 'big')
        n, flags = self.area[o], self.area[o + 1]
        res = []
        for v in range(n):
            ch = self.area[o + 2 + 3 * v]
            so = int.from_bytes(self.area[o + 3 + 3 * v:o + 5 + 3 * v], 'big')
            res.append((ch, o + so))
        return res, bool(flags & 1)

    def busy(self, ch):
        return any(v.active and v.ch == ch for v in self.fx)

    def write_tone(self, out, v):
        if v.ch == 3:
            return
        out += [0x80 | (v.ch << 5) | (v.period & 15), (v.period >> 4) & 0x3F]

    def write_att(self, out, v, vol):
        out.append(0x90 | (v.ch << 5) | (15 - vol))

    def silence(self, out, ch):
        out.append(0x90 | (ch << 5) | 15)

    def play_music(self, n):
        out = []
        if n == self.cur:                      # the tune playing goes on
            return out
        self.cur = n
        for v in self.music:
            if v.active and not self.busy(v.ch):
                self.silence(out, v.ch)
        self.music = []
        if n:
            vs, loop = self.item(n - 1)
            self.music = [Voice(self.area, s, ch, loop, False) for ch, s in vs]
        return out

    def play_sound(self, n):
        out = []
        for v in self.fx:
            if v.active:
                self.end_fx(out, v)
        vs, _ = self.item(self.m + n - 1)
        self.fx = [Voice(self.area, s, ch, False, True) for ch, s in vs]
        return out

    def end_fx(self, out, v):
        v.active = False
        mv = next((m for m in self.music if m.active and m.ch == v.ch), None)
        if mv and mv.sounding:
            if mv.ch == 3:
                out.append(0xE0 | mv.period)
            else:
                self.write_tone(out, mv)
            self.write_att(out, mv, mv.cur)
        else:
            self.silence(out, v.ch)

    def run_voice(self, out, v):
        quiet = (not v.effect) and self.busy(v.ch)
        d = v.data
        if v.wait:
            v.wait -= 1
            if v.sounding and v.env and v.cur:
                v.envc -= 1
                if v.envc == 0:
                    v.envc = v.env; v.cur -= 1
                    if not quiet: self.write_att(out, v, v.cur)
        while v.wait == 0 and v.active:
            k = d[v.p]
            if k == 0:
                if v.loop:
                    v.p = v.start
                    continue
                if v.effect:
                    self.end_fx(out, v)
                else:
                    v.active = False
                    if not quiet: self.silence(out, v.ch)
                break
            if k == 1:
                v.period = (d[v.p + 1] << 8) | d[v.p + 2]; v.wait = d[v.p + 3]; v.p += 4
                v.cur = v.vol; v.envc = v.env; v.sounding = True
                if not quiet:
                    self.write_tone(out, v); self.write_att(out, v, v.cur)
            elif k == 2:
                v.wait = d[v.p + 1]; v.p += 2; v.sounding = False
                if not quiet: self.silence(out, v.ch)
            elif k == 3:
                v.vol = d[v.p + 1]; v.p += 2
            elif k == 4:
                v.env = d[v.p + 1]; v.p += 2
            elif k == 5:
                v.period = d[v.p + 1]; v.wait = d[v.p + 2]; v.p += 3
                v.cur = v.vol; v.envc = v.env; v.sounding = True
                if not quiet:
                    out.append(0xE0 | v.period); self.write_att(out, v, v.cur)
            elif k == 6:
                v.wait = d[v.p + 1]; v.p += 2
            else:
                raise ValueError(f'bad event {k}')

    def tick(self):
        out = []
        for v in self.music:
            if v.active: self.run_voice(out, v)
        for v in self.fx:
            if v.active: self.run_voice(out, v)
        return out

def preview(path, seconds=8, rate=22050):
    """A WAV of how the TI would sound (square waves and noise), to listen to."""
    import struct, wave, random
    loop, voices = compile_text(open(path).read(), os.path.basename(path))
    area = (1).to_bytes(2, 'big') + (0).to_bytes(2, 'big') + (8).to_bytes(4, 'big') + item_bytes(loop, voices)
    pl = Player(area); out = pl.play_music(1)
    state = {c: [0, 15] for c in range(4)}; noise = [0, 15]; latch = [0]
    def apply(b):
        if b & 0x80:
            ch, typ = (b >> 5) & 3, (b >> 4) & 1
            latch[0] = (ch, typ)
            if typ: state[ch][1] = b & 15
            elif ch == 3: noise[0] = b & 7
            else: state[ch][0] = (state[ch][0] & 0x3F0) | (b & 15)
        else:
            ch, typ = latch[0]
            if not typ and ch < 3: state[ch][0] = (state[ch][0] & 15) | ((b & 0x3F) << 4)
    for b in out: apply(b)
    samples, phase, rnd = [], [0.0] * 3, random.Random(1)
    per = rate // 60
    for frame in range(seconds * 60):
        for b in pl.tick(): apply(b)
        for _ in range(per):
            s = 0.0
            for c in range(3):
                p, att = state[c]
                if p and att < 15:
                    phase[c] = (phase[c] + (CLOCK / p) / rate) % 1.0
                    s += (1 if phase[c] < 0.5 else -1) * 10 ** (-att * 2 / 20) * 0.22
            if state[3][1] < 15:
                s += (rnd.random() * 2 - 1) * 10 ** (-state[3][1] * 2 / 20) * 0.18
            samples.append(int(max(-1, min(1, s)) * 30000))
    wp = os.path.splitext(path)[0] + '-ti.wav'
    with wave.open(wp, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(struct.pack(f'<{len(samples)}h', *samples))
    return wp

if __name__ == '__main__':
    for p in sys.argv[1:]:
        loop, voices = compile_text(open(p).read(), os.path.basename(p))
        it = item_bytes(loop, voices)
        print(f'{p}: {len(voices)} voices, {len(it)} bytes{", loops" if loop else ""}; preview {preview(p)}')
