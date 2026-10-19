# TXA: an Infocom-style text adventure engine and workbench for the TI-99/4A

TXA (a working name) is a story virtual machine with an Infocom-grade
parser for the TI-99/4A with an F18A (or PICO9918) and a SAMS card of
512K or more, plus a native **workbench** that compiles games on the TI
itself. Built on The Lantern Coast's kernel. Designed by Rebecca Sutter,
built with Claude.

The specification is a Claude Doc:
https://claude.ai/code/artifact/43a54522-f42d-42ed-b2c7-bf348e97a95d

**Status: M0, the hardware probe.** See `plan.md`.

## Building and testing

    git clone https://github.com/endlos99/xdt99 ../xdt99     # the assembler, next to this repo
    python3 tools/build.py                                     # -> build/
    python3 tests/m0_test.py --png                             # plays the probe in the simulator

Outputs: `build/txaprobe8.bin` (FinalGROM cartridge), `build/txaprobe.dsk`
(disk image with the E/A option 5 files `TXAP1`, `TXAP2`).

## Licence

MIT (proposed, matching The Lantern Coast; see the spec's open questions).
The font is X11 misc-fixed 5x8, public domain.
