# TXA 1.0

*3 November 2026*

TXA is an Infocom-style text adventure system for the TI-99/4A with an
F18A (or PICO9918) and a SAMS card of 512K or more. Version 1.0 is the
first public release.

## What's included

- **The story language and its standard library:** a world model of
  rooms, objects, doors, containers, light and characters; a parser
  that understands commands like "put the lantern on the table", with
  pronouns, disambiguation, OOPS and AGAIN; timed events; scores and
  endings.
- **The engine:** 80-column text, pictures on the F18A's bitmap layer,
  music and sound effects, UNDO, saved games, scrollback, and RECORD and
  REPLAY for walkthroughs. It runs from disk (Editor/Assembler option 5,
  TIPI) or from a FinalGROM cartridge.
- **The TXA Workbench**, a FinalGROM cartridge that does everything but
  edit on the TI itself: it compiles a story byte for byte as the PC
  does, test-plays it with debugging verbs, shows its statistics,
  imports TI Artist pictures, and builds the finished game.
- **PC tools** in Python: the compiler, a reference VM, the game writer
  (disk images and cartridges, with a player's card for each game), and
  converters for pictures (PNG, TI Artist) and music (TXA music notation,
  MIDI).
- **Seven manuals**, as Markdown and PDF: the Authoring Language
  Reference, the Standard Library Reference, the Workbench Manual, the
  Tutorial, the Engine Implementation Guide, the Technical Reference and
  the Player's Card; and TXA music notation.
- **Two games:** *Lamplight*, the sample game, and *The Ferry House*,
  the Tutorial's game, each as a disk and a cartridge.

## In the zip

- `cartridge/txa-workbench8.bin`: the workbench (FinalGROM 99, 256K).
- `games/`: Lamplight and The Ferry House, disks and cartridges, with
  their player's cards.
- `workbench/`: sample disks for the workbench (Lamplight's source,
  pictures and music; a game with a TI Artist picture).
- `manuals/`: every manual, Markdown and PDF.

## Requirements and notes

- A TI-99/4A with 32K memory expansion, an F18A or PICO9918, a SAMS card
  of 512K or more, and a FinalGROM 99 or a disk system. TI's own disk
  controller reads single-density disks only; the release's disks are.
- In js99er, choose the "Generic Disk" controller setting and turn on
  F18A and SAMS. js99er draws pictures doubled sideways in 80 columns
  (an emulator bug); real hardware is right.
- A game may have up to 12 source files on the workbench, the library's 8
  among them.
- Tested in the cycle-counting simulator and in js99er; not yet on a
  real console.

## Licence

MIT. The 80-column font derives from X11 misc-fixed (public domain); the
hummingbird picture and the MIDI file behind Lamplight's harbour tune are
public domain. Designed by Rebecca Sutter, built with Claude.
