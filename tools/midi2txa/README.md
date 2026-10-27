# midi2txa

Converts Standard MIDI Files into TXA music notation, the MML-style text the
TXA engine's `MUSIC` and `SOUND` declarations compile from. It does what the
spec's Sound and music section asks of MIDI import: keeps the three most
important simultaneous tone notes (chosen per track, or the highest by
default), maps drums to the noise voice, quantizes to a musical grid, folds
notes outside the chip's range into it, and reports every compromise. The
output is text, so the native workbench can compile it on the TI as well.

The package also holds the reference compiler for the notation
(`txamusic.py`), which defines it to the tick, and a preview renderer that
approximates the TMS9919 so a conversion can be judged by ear before it goes
near the console.

Requires Python 3.8 or later and nothing else. If numpy is installed the WAV
preview uses it and runs much faster.

## Quick start

    python3 midi2txa.py song.mid --list              # see the tracks first
    python3 midi2txa.py song.mid --wav song.wav      # convert, report, preview
    python3 txamusic.py SONG.txm --wav check.wav     # compile hand-written music

A conversion writes `NAME.txm` (the notation) and `NAME.report.txt` (every
compromise it made) and prints the report. `NAME` comes from the MIDI file
name, cut to the TI's 10 letters and digits, or from `--name`. Before writing
anything the converter compiles its own output with the reference compiler and
checks every tick against what it meant to produce, so a file it writes always
compiles and always means what the report says.

## A typical session

Most MIDI files need a pass or two. List the tracks, convert once with the
defaults, read the report and listen, then steer it:

    python3 midi2txa.py harbour.mid --list
    python3 midi2txa.py harbour.mid --wav h.wav
    python3 midi2txa.py harbour.mid --prefer 2 --voice C:4:low \
        --tone-env pluck --bars 9-24 --wav h.wav --loops 2

`--prefer 2` makes track 2 (the melody) win a voice before anything else.
`--voice C:4:low` gives voice C to track 4 alone with its lowest note winning,
which keeps a bass line whole instead of letting it lose every contest to
higher notes. `--bars 9-24` keeps just the part that loops well, and
`--loops 2` plays it twice in the preview so the seam can be heard.

## Options

| Option | Effect |
| --- | --- |
| `--tracks 2,3,5-7`, `--drop 6` | Use only some tracks, or leave some out |
| `--prefer 2,4` | Tracks whose notes win a voice first, most important first |
| `--voice C:3:low` | Give a voice to some tracks alone (`high` or `low` note wins); repeatable |
| `--tone-voices AB` | Music uses only these voices, leaving C free for sound effects |
| `--bars 9-24` | Convert only these bars |
| `--grid 16` | Quantize to 1/N notes; 24 or 48 keep triplets |
| `--transpose N`, `--auto-transpose` | Shift tone notes; auto picks the octave shift that folds fewest |
| `--tempo-scale 0.9` | Scale every tempo |
| `--drum-channel 10`, `--no-drums` | Where the drums are, or ignore them |
| `--tone-env flat\|decay\|pluck` | Volume shape for tone notes |
| `--tone-volume N`, `--drum-volume N` | Volume steps (2 dB) to add |
| `--volume-tolerance 1` | Ignore volume changes this small within a voice; 0 keeps all |
| `--no-normalize` | Keep MIDI loudness instead of raising the loudest note to full |
| `--no-bars`, `--no-repeats`, `--no-pad` | Output style: bar lines, `[ ]n` folding, padding to the bar |
| `--wav FILE`, `--loops N`, `--events FILE` | Preview WAV; per-tick internal form as CSV |

## What gets lost, and how the report tells you

The chip has three square-wave voices and one noise channel, so a MIDI file
almost always loses something. The report groups it: **Timing** (notes moved
to the grid, tempo rounding), **Range** (notes folded by octaves, pitches the
chip cannot tune within 10 cents), **Voices** (notes dropped or cut short by
more important ones, and which tracks they came from), **Drums** (which kit
pieces mapped to what, hits lost when two landed together), **Volume**
(normalization and smoothing) and **Ignored** (pitch bends, sustain pedal,
anything the chip cannot do).

Drums follow General MIDI on channel 10. Each kit piece becomes a noise type,
rate and envelope: kicks and toms are periodic noise (a pitched thump), snares
and claps middle-rate white noise, hats and cymbals high-rate white noise with
short or long decays. When two land together, the kick beats the snare, which
beats toms, cymbals and hats.

## Files

| File | What it is |
| --- | --- |
| `midi2txa.py` | The converter |
| `txamusic.py` | Reference compiler: the definition of the notation |
| `snpreview.py` | TMS9919 approximation for WAV previews |
| `smf.py` | MIDI file reader |
| `docs/MUSIC.md` | The notation reference, with the decisions awaiting review |
| `tests/` | Unit tests and the fixture builder (`python3 -m unittest -v tests/test_all.py`) |
| `examples/` | A converted test piece two ways, with reports and a preview |

## Fitting into TXA

These belong beside the cross-compiler in `tools/txc/`. Two joins are left for
M4, because they depend on decisions there. First, the TXA compiler's `MUSIC`
and `SOUND` declarations should call `txamusic.compile_file` on the named
source and encode the per-tick internal form for the engine; that encoding
(the TI's SAMS format) is M4's to define, and other engines would encode the
same internal form for their own chips. Second, how the compiler finds the file
a declaration names (`"HARBOUR"` against `HARBOUR.txm` on a PC, `DSK1.HARBOUR`
on the TI) should follow whatever rule pictures use. The TI workbench's music
compiler must reproduce `txamusic.py` exactly, so the compiler-equivalence test
layer should include a music corpus.
