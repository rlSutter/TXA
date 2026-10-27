# TXA music notation

Version 1.0 draft, for Rebecca's review. The reference implementation is
`txamusic.py`; where this document and that file disagree, the file is right
and this document is the bug.

A music source file is plain ASCII, DV80 (no line longer than 80 characters),
so it can be typed in Press 2.0 or TI-Writer and compiled on the TI. A game
declares it the way it declares a picture (`MUSIC Harbour "HARBOUR"`); the
same notation serves `SOUND` effects, which play once instead of looping.

## A short example

```
! HARBOUR - the quay theme
ENV 1 0 1 2*2 3*3 4          ! a gentle decay that settles 8 dB down
A: T96 L8 O5 @1 V14 [ C D E G F E D C | ]3 D E F# A G F# E D
B: T96 L2 O3 @1 V12 [ G > C | < B > E < | ]2
C: T96 L4 O3 [ C G C G | ]4
N: T96 L16 [ [ O2 P8 O0 W W O1 W8 O0 W W ]2 | ]4
```

Each voice is written on its own lines, labelled `A:`, `B:` or `C:` (the three
tone voices) or `N:` (noise). Lines with the same label join in order, so a
voice can run over as many lines as it needs. A voice that never appears stays
silent. Case does not matter, spaces are optional, and `!` starts a comment
that runs to the end of the line.

## Notes and rests

| Write | Meaning |
| --- | --- |
| `C D E F G A B` | A note in the current octave |
| `#` or `+` after the note, `-` after it | Sharp, flat (`C#`, `B-`) |
| A number after the note | Its length: 1 whole, 2 half, 4 quarter, 8 eighth, 16, 32, 64; 3, 6, 12, 24, 48, 96, 192 are the triplet lengths |
| `.` after the length | Half as long again; `..` adds a quarter more (where the length allows it) |
| `R` | A rest, with a length like a note |
| `&` between two notes | A tie: the second note continues the first without a new attack |
| `\|` | A bar line, for reading; the compiler ignores it |

A note with no length uses the default length set by `L`. A tie joins notes of
the same pitch only. Commands (`T`, `V`, `O` and the rest) may sit between the
two halves of a tie; a `V` there changes the volume without a new attack.

## Commands

| Command | Meaning | Default |
| --- | --- | --- |
| `L n` | Default note length (dots allowed: `L8.`) | `L4` |
| `O n` | Octave; octave 4 runs from middle C to the B above | `O4` (noise: `O1`) |
| `>` `<` | Up or down one octave | |
| `T n` | Tempo in quarter notes per minute, 20 to 999 | `T120` |
| `V n` | Volume, 0 (silent) to 15 (loudest), in 2 dB steps | `V15` |
| `@ n` | Envelope n (defined by `ENV`); `@0` is flat | `@0` |
| `[ ... ]n` | Play the passage n times (1 to 255); repeats nest up to 8 deep | |

The tone voices reach from **A2 to B7**: the TMS9919's lowest note is about
109 Hz, and above B7 the tuning drifts too far. A note outside that range is an
error that names the note and the line.

The letter `E` is a note, so envelopes use `@` rather than an `E` command.

## The noise voice

The noise voice plays `W` (white noise) and `P` (periodic noise, a buzz) with
lengths, rests, ties, volume and envelopes exactly like a tone voice. Its
octave command selects the rate instead of a pitch:

| Rate | `O0` | `O1` | `O2` | `O3` |
| --- | --- | --- | --- | --- |
| Noise | High (hiss, hi-hat) | Middle (snare) | Low (rumble, kick) | Follows tone voice C's pitch |

`O3` couples the noise to voice C, which is how TI music gets pitched noise
and deep periodic basses; it ties up voice C while it plays.

## Envelopes

```
ENV n step step step ...
```

An envelope (n from 1 to 15) is a list of attenuation steps added to the
voice's volume, one step per 1/60-second tick from the start of each note; the
last step holds for the rest of the note. `2*3` writes a run of three 2s. An
envelope has at most 64 steps. A tie does not restart the envelope; a new note
does. `ENV 1 0 3 6 10 15` is a short click, `ENV 2 0 0 1 1 2*4 3*6 4` a
decay that settles 8 dB down.

## How time works

These rules fix the result to the tick, so the TI workbench and the Python
tool produce the same internal form from the same text.

Lengths are counted in 1/192 of a whole note, so every length, dot and
triplet above is a whole number of units. Each voice keeps its own position
and its own tempo; the converter writes the same `T` commands at the same
places in every voice, and hand-written music should do the same. A `T`
command starts a new tempo stretch at the current position. Inside a stretch,
the tick where a position falls is

    stretch start tick + (150 × units since the stretch began + T) ÷ (2 × T)

with integer division, which is 75 × units ÷ T rounded half up. Rounding each
position (rather than each note's length) keeps voices in step and stops drift:
at T120 four sixteenths fall on ticks 0, 8, 15 and 23 and end on 30, exactly a
quarter note. A tempo stretch may last at most 65,535 ticks (about 18 minutes),
so the division fits the TMS9900's `DIV`. A note that rounds to no ticks at all
is reported as a warning and not heard.

## What the compiler produces

The result, which the spec calls the internal form, is a list per voice with
one entry per tick: the chip value and the attenuation (0 loudest, 15 silent).
For tone voices the value is the 10-bit tone divider (111860.8 ÷ frequency).
For noise it is the control byte: >E0, plus 4 for white noise, plus the rate.
Attenuation is `15 − V` plus the envelope step for that tick, capped at 15. A
silent tick is written as value 0, attenuation 15. A piece lasts as long as its
longest voice; shorter voices are silent for the rest.

How a platform stores and plays that state is that platform's business: the
TI engine's encoding in SAMS belongs to M4, and another engine would convert
the same internal form for its own chip (Portability rules 2, 3 and 8).

### Tone table

A native compiler carries these 63 values as a constant table; they are
`round(111860.8 ÷ frequency)` at A4 = 440 Hz.

```
A2   1017 | A#2   960 | B2    906 | C3    855 | C#3   807 | D3    762
D#3   719 | E3    679 | F3    641 | F#3   605 | G3    571 | G#3   539
A3    508 | A#3   480 | B3    453 | C4    428 | C#4   404 | D4    381
D#4   360 | E4    339 | F4    320 | F#4   302 | G4    285 | G#4   269
A4    254 | A#4   240 | B4    226 | C5    214 | C#5   202 | D5    190
D#5   180 | E5    170 | F5    160 | F#5   151 | G5    143 | G#5   135
A5    127 | A#5   120 | B5    113 | C6    107 | C#6   101 | D6     95
D#6    90 | E6     85 | F6     80 | F#6    76 | G6     71 | G#6    67
A6     64 | A#6    60 | B6     57 | C7     53 | C#7    50 | D7     48
D#7    45 | E7     42 | F7     40 | F#7    38 | G7     36 | G#7    34
A7     32 | A#7    30 | B7     28
```

## Limits

| Limit | Value |
| --- | --- |
| Line length | 80 characters |
| Voices | A, B, C (tone) and N (noise) |
| Tone range | A2 to B7 |
| Tempo | 20 to 999, whole numbers |
| Repeat count, nesting | 1 to 255, 8 deep |
| Envelopes | 1 to 15, up to 64 steps each |
| One tempo stretch | 65,535 ticks |
| One voice after repeats | 200,000 tokens |

## Decisions in this draft that need your review

1. **`@n` for envelopes.** `E` is a note name, so it cannot also be the
   envelope command; `@` is the MML convention for instrument changes.
2. **Noise as `W` and `P`, rate set by `O`.** Reuses a command authors already
   know, and `O3` names the chip's coupled mode directly.
3. **Whole-number tempos.** MIDI tempos such as 132.5 round to 133; the
   converter reports any rounding over half a percent.
4. **Per-voice timing with matching `T` commands**, as classic MML does, rather
   than one global tempo line. A voice reads correctly on its own.
5. **`V15` is loudest**, the MML convention, rather than the chip's attenuation
   order.
6. **Range A2 to B7.** Lower notes do not exist on the chip; higher ones drift
   more than 20 cents.
