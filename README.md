# TXA: an Infocom-style text adventure engine and workbench for the TI-99/4A

TXA (a working name) is a story virtual machine with an Infocom-grade
parser for the TI-99/4A with an F18A (or PICO9918) and a SAMS card of
512K or more, plus a native **workbench** that compiles games on the TI
itself. Built on The Lantern Coast's kernel. Designed by Rebecca Sutter,
built with Claude.

The specification is a Claude Doc:
https://claude.ai/code/artifact/43a54522-f42d-42ed-b2c7-bf348e97a95d

**Status (22 October 2026):** the engine is 1.0 beta (M0-M4: the VM,
the parser, the world model and library, saving, pictures, sound,
scrollback), with the sample game Lamplight. M5, the native compiler on
the TI (the workbench cartridge), is done: it reads a program's files
from disk following its INCLUDEs, lexes, parses, checks its meaning,
generates its code and links the story image, every step identical to
the Python compiler (tools/txc) on the whole test corpus, and writes the
story to disk. M6, the workbench tools, is under way: one engine now
serves every game, the workbench has a main menu, and its Build key
writes a whole game (engine and story) that plays. See `plan.md`.

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
