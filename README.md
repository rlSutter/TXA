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

**Status:** the engine and workbench are complete (milestones M0-M6);
the manuals are being written (M7), after which this is 1.0. See
`plan.md` for the history and decisions, and `docs/` for the Technical
Reference (generated from the source) and the music notation.

## Trying it

Get the release's cartridge image (`txa-workbench8.bin`, for a
FinalGROM 99) and disk images, or build them as below. In js99er, use
the "Generic Disk" controller setting. Put `lamplight-workbench.dsk` in
DSK1, start the workbench, and press P (the project), C (compile), T
(test-play) or B (build) then R (run).

## Licence and credits

MIT (see LICENSE). The 80-column font is derived from X11 misc-fixed
5x8 (public domain). The assembler, xdt99 (Ralph Benzinger), is used to
build but not included.

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
