# TXA 1.0.2

*5 November 2026*

- **Games load from any drive.** A game's files were looked for only on
  the drive it was built for (DSK1 for the release's games), so a disk in
  DSK3 could not load. If the first story file is not there, the engine
  now tries the other drives, DSK1 to DSK9, and uses the one that has it
  for the rest of the story, the pictures, the music, saved games and
  scripts. Load the first engine file from whichever drive holds the disk
  (`DSK3.LAMP1`, say). A game built for a named device such as
  `TIPI.GAMES.` looks only there. If no drive has the story, the message
  names the file the game was built for: "Cannot find DSK1.LAMPS01".
- Three start-up messages are shorter, to make room: "TXA needs SAMS:
  512K or more.", "No TXA story in this cartridge.", "The story is
  damaged."

Everything else is as in 1.0.1.

# TXA 1.0.1

*4 November 2026*

A fix for consoles with a TIPI and a disk controller.

- **Finding disk drives past another card.** When TXA looked for a device
  such as `DSK1`, it stopped at the first card whose list named it, even
  if that card then declined. A TIPI lists `DSK` names and sits at CRU
  `>1000`, ahead of a disk controller at `>1100`, so on a console with
  both, games and the workbench might not load from the floppy drive. The
  search now goes on to the next card, as the console's own routine does.
  The fix comes from the SAMS Kernel 1.28.0, where the same flaw was found
  on real hardware. A new test plants such a card ahead of the drive.
- **Building from a fresh copy.** The build now creates the folders and
  the generated font it needs, so `python tools/mkdist.py` works on a new
  clone (found building the release on Windows).

Everything else is as in 1.0.

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
