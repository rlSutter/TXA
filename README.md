# TXA: text adventures for the TI-99/4A

TXA is an Infocom-style text adventure system for the TI-99/4A with an
F18A (or PICO9918) and a SAMS card of 512K or more:

- a **story language** with a world model, a standard library and a
  parser that understands commands like "put the lantern on the table";
- an **engine** that plays the compiled stories, with 80-column text,
  pictures on the F18A's bitmap layer, music and sound effects, UNDO,
  saved games and scrollback;
- the **TXA Workbench**, a cartridge that edits nothing but does
  everything else on the TI itself: compiles a story (byte for byte as
  the PC compiler does), test-plays it with debugging verbs, and builds
  the finished game's disk, TI Artist pictures included;
- **PC tools** in Python: the compiler, a reference VM, the game writer,
  the picture and music converters (TXA music notation, MIDI import).

The sample game, *Lamplight*, shows most of it. Designed by Rebecca
Sutter, built with Claude; on The Lantern Coast's kernel.

**Status:** 1.0.2 (5 November 2026; 1.0 was 3 November). The engine, the
workbench, the PC tools and the manuals are complete; the full regression
suite passes. `docs/RELEASE-NOTES.md` says what changed.
See `plan.md` for the history and decisions.

## The manuals

In `docs/`, as Markdown (the release has them as PDF too):

- `LANGUAGE-REFERENCE.md`: the Authoring Language Reference.
- `LIBRARY-REFERENCE.md`: the Standard Library Reference.
- `WORKBENCH-MANUAL.md`: the Workbench Manual.
- `TUTORIAL.md`: the Tutorial, a small game built in five chapters.
- `ENGINE-GUIDE.md`: the Engine Implementation Guide, for other machines.
- `TECHNICAL-REFERENCE.md`: the formats and the TI engine's memory.
- `PLAYERS-CARD.md`: how a player plays (the game writer makes one per game).
- `MUSIC.md`: TXA music notation.

All but the Workbench Manual and the Language Reference are generated
from the source (`tools/gendocs.py`), and `tests/docs_test.py` fails if
any of them drifts from it.

## Trying it

Get the latest release's zip from GitHub, or build it as below
(`python3 tools/mkdist.py`). In js99er, use the "Generic Disk" controller
setting with F18A and SAMS on.

- **To play:** put `games/lamplight.dsk` in DSK1 and load `DSK1.LAMP1`
  with Editor/Assembler option 5, or put `games/lamplight8.bin` on a
  FinalGROM.
- **To make games:** put `cartridge/txa-workbench8.bin` on a FinalGROM
  and `workbench/lamplight-workbench.dsk` in DSK1. Start the workbench and
  press P (the project), then C (compile), T (test-play) or R (run: it
  builds the game first when needed).

## Licence and credits

MIT (see LICENSE). The 80-column font is derived from X11 misc-fixed
5x8 (public domain). The assembler, xdt99 (Ralph Benzinger), is used to
build but not included.

Two sample files are public domain: the hummingbird picture used as
TI Artist test data and in the bird sample disk (`tests/data/BIRD_P`,
`BIRD_C`), and the MIDI file behind Lamplight's harbour tune
(`tools/midi2txa/examples/harbour.mid`).

## Building and testing

    git clone https://github.com/endlos99/xdt99 ../xdt99     # the assembler, next to this repo
    python3 tools/build.py                                     # -> build/
    python3 tests/m0_test.py --png                             # plays the probe in the simulator

Outputs: `build/txaprobe8.bin` (FinalGROM cartridge), `build/txaprobe.dsk`
(disk image with the E/A option 5 files `TXAP1`, `TXAP2`).

The workbench cartridge and a source disk for it:

    python3 -c "import sys; sys.path.insert(0,'tools'); import build; open('build/txa-workbench8.bin','wb').write(build.workbench_cart()[0])"
    python3 tools/txa_srcdisk.py samples/lamplight.txa -o build/lamplight-src.dsk

The test suites are listed in `docs/CONTEXT.md`; the workbench's are
`tests/m5_load_test.py`, `m5_lex_test.py`, `m5_parse_test.py` and
`m5_sema_test.py` (decls, meaning, code, link, errors).

## Licence

MIT (proposed, matching The Lantern Coast; see the spec's open questions).
The font is X11 misc-fixed 5x8, public domain.

Music and sound effects are written in TXA music notation (docs/MUSIC.md;
.txm files, three tone voices and noise, envelopes, repeats), compiled by
tools/midi2txa/txamusic.py; tools/midi2txa/midi2txa.py converts MIDI files
into it, and snpreview.py renders a tune to WAV to judge it by ear.

## Making a game for the TI

    python3 tools/txa_game.py samples/lamplight.txa --prefix LAMP --title LAMPLIGHT --cart

writes the engine as E/A option 5 files (LAMP1..), the story as 4K files
(LAMPS01..), the pictures (LAMPP01..) and the music (LAMPM01..) as files
of their own, a disk image, and a FinalGROM cartridge, in
build/game/lamp/. The engine is the same for every game but for the
story name patched into it, so a story the workbench compiles on the TI
(LAMPLIS01.. for the prefix LAMPLI) plays on it too.
The language is described in the Authoring Language Reference (a Claude
Doc: see docs/CONTEXT.md).
