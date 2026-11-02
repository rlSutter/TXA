# The TXA Workbench Manual

The TXA Workbench is a cartridge that turns a TI-99/4A into a complete
place to make text adventures: it compiles a story's source (byte for
byte as the PC compiler does), test-plays it with debugging verbs, shows
how much room it has used, imports TI Artist pictures, and builds the
finished game's disk. This manual covers every key. The story language
is in the *Authoring Language Reference*, the library in the *Standard
Library Reference*, and a worked example in the *Tutorial*.

## What you need

- A TI-99/4A with 32K memory expansion, an **F18A** (or PICO9918) and a
  **SAMS** card of **512K or more**. The workbench checks its SAMS pages
  when it starts, and if one does not answer it says so ("SAMS page 16
  did not answer") instead of going on.
- A **FinalGROM 99** (or anything that loads a 256K "8" cartridge
  image) with `txa-workbench8.bin`.
- A disk drive, TIPI or emulated drive. Disks for TI's own controller
  must be single density (180K); TXA's sample disks are.
- In **js99er**: the "Generic Disk" controller setting, F18A and SAMS
  on. js99er draws pictures doubled sideways in 80 columns (its bug,
  reported); the game itself is right.

The workbench edits nothing: write source on a PC (any text editor) or on
the TI (Press, TI-Writer, any DIS/VAR 80 editor) and put the files on a
disk. A story's files are DIS/VAR 80 text, lines up to 80 characters.

## Starting

Select "TXA WORKBENCH" from the FinalGROM's menu. The main menu shows the
keys along the bottom:

```
P Project C Compile T Test R Run B Build E Errors S Stats I Import O Options
```

Every key is a single press; FCTN 9 (BACK) leaves a screen without
changes, and FCTN S rubs out while typing.

## P: the project

P asks three things, one after another:

1. **Source file**: the story's main file, as `DSK1.NAME` ("Type the
   source file (DSK1.NAME): FCTN S rubs out, ENTER keeps the one
   shown."). The files it INCLUDEs are found from it.
2. **Build date**, `yymmdd` (the TI has no clock): it goes into the
   story's header, which a save file is checked against.
3. **Game prefix**: 1-6 letters or digits that name the built game's
   files (`LAMPLI` gives `LAMPLI1`, `LAMPLIS01` ...). A new source file
   offers a prefix made from its name.

## C: compile

C reads the source file and every file it INCLUDEs, then lexes, parses,
checks the meaning, generates the code and links the story, showing each
stage on a progress bar. A Lamplight-sized story (9 files, about 3,800
lines) takes a little over a minute. When it is done the screen says
what it read and made:

```
Read 9 files, 3770 lines.
419 declarations, 380 symbols, 48 objects.
Story: 33856 bytes in 9 files on disk.
```

and the story's files are on the source disk (`PREFIXS01`, `S02` ...).

**Errors.** The first error stops the compile, and is shown as the PC
compiler words it, with its file and line:

```
TURN line 88: the action DebugTree has no routine DebugTreeSub
```

**E** shows the last compile's error again ("No error in the last
compile." if there was none). Mend the source, then C again.

**Library devices.** If the source and library are on different disks,
set the library's device in O (below): an INCLUDE whose file is not on
the device it names is then looked for there.

## T: test-play

T compiles and starts the game at once, from memory: nothing is written
except the story's own files, and pictures and music come from the
source disk. Test-play turns on the library's **debug verbs**, which a
built game refuses:

| Verb | Does |
| --- | --- |
| `TREE` (or `TREE n`) | every object, indented under what holds it, with its number |
| `GOTO n` (a room's number or name) | moves you there |
| `PURLOIN n` (number or name) | puts any object in your hands |
| `SCOPE` | the objects the parser can see, with numbers |
| `ACTIONS ON` / `OFF` | announces each action as it happens |
| `TRACE ON` / `OFF` | shows the parser's choices |

**FCTN =** ends test-play and returns to the workbench.

## R: run, and B: build

**B** builds the finished game on the source disk: the engine's files
(`PREFIX1` ...), the story, and its pictures and music. Pictures that are
TI Artist files are converted here (see I); pictures and music made on
the PC are left as they are. When it is done:

```
The game is built: load DSK1.LAMPLI1 (E/A 5, FinalGROM, TIPI).
```

**R** runs the game just built, as a player would see it. A built game
loads with Editor/Assembler option 5 (`DSK1.LAMPLI1`), or from a
FinalGROM or TIPI, on any TI with an F18A and SAMS: it does not need the
workbench.

**RECORD and REPLAY** work in every game, built or test-played: `RECORD`
writes each command typed to a script file on the game's disk
(`PREFIXR0`; `RECORD 3` for script 3), `RECORD` again stops, and
`REPLAY` plays a script back as if typed. Record a walkthrough once and
replay it after every change. (While a script file is open, pictures are
turned off: the disk controller keeps the open file's buffers where the
picture would be drawn.)

## S: statistics

After a compile without errors, S shows the story's size and how much
room is left in each part of it:

```
Statistics of the last compile:
 Objects: 48.  Dictionary words: 285.  Routines: 186.  Strings: 348.
 Story image: 33856 bytes of 262144 (228288 free).
 Dynamic area: 7304 bytes of 16384 (9080 free).
 Tables (to the routines): 12628 bytes of 65536 (52908 free).
 Routines and strings: 21228 bytes.
```

Watch the **dynamic area**: it holds every object, property, global and
array, and the game's changing state, and at 16384 bytes it is the limit
a large story meets first.

## I: TI Artist pictures

A story's `PICTURE Bird "BIRD"` can be a TI Artist picture: put `BIRD_P`
and `BIRD_C` (as TI Artist saves them) on the source disk. A TI Artist
picture is a full screen, 256 x 192; a TXA picture is a band 96 rows high
above the text, so it is fitted one of two ways:

- **crop**: 96 of its rows, at full width and the right proportions;
- **squeeze**: the whole picture at half its height.

**I** shows a picture as the game will and lets you choose: type its name
(`DSK1.` is offered: type `BIRD`), ENTER. After a few seconds' loading
and converting it appears, with "Crop: rows 48 to 143 of the 192." under
it. **FCTN E** and **FCTN X** move the band up and down, **S** switches
between crop and squeeze, **ENTER** saves the choice in `BIRD_T`, and
**FCTN 9** leaves without saving. Without a `BIRD_T`, a picture is cropped
from row 48. B uses the choice when it builds.

## O: options

| Key | Option |
| --- | --- |
| C | the colours: gray on black, white on dark blue, green on black, amber on black, black on white |
| F | the font: normal or bold |
| L | the library devices, spaces apart (`DSK2. DSK3.`) |

The screen changes as you choose. **ENTER** saves the options in
`DSK1.TXAOPT`, which the workbench reads each time it starts; **FCTN 9**
puts them back as they were. A built game keeps its own colours.

## Files on the disk

| File | What |
| --- | --- |
| `NAME` and its INCLUDEs | the source, DIS/VAR 80 |
| `PREFIXS01` .. | the story, written by C, T and B |
| `PREFIX1` .. | the engine, written by B (load the first) |
| `PREFIXP01` .. | the pictures |
| `PREFIXM01` .. | the music and sound effects |
| `PREFIXR0` .. `R9` | RECORD's scripts |
| `NAME_P`, `NAME_C`, `NAME_T` | a TI Artist picture and its fitting |
| `TXAOPT` (on DSK1) | the workbench's options |

A 180K disk holds a Lamplight-sized source and one built game.

## When something goes wrong

- **"SAMS page N did not answer"** at the start: the SAMS card is
  missing, faulty, or smaller than 512K (in js99er: turn SAMS on and give
  it 1M).
- **"Cannot open that file."**: the source file's name or disk is wrong
  (P to change it).
- **Disk errors on a real controller** with a double-density disk: TI's
  controller reads single density only.
- **Pictures doubled sideways** in js99er: its bug; real hardware is
  right.

## Large stories

The workbench compiles any story the format allows, but the time grows
with the source: about a minute for Lamplight. For a large story, write
and compile on the PC (the same compiler, in seconds) and use the
workbench for test-play, RECORD and REPLAY on the TI, and the final build.
