# TXA plan

Status, what remains, and Rebecca's decisions. Start a new session with
`docs/CONTEXT.md`.

## Status (19 October 2026)

**M0, the hardware probe: complete.** 25 simulator checks pass
(`tests/m0_test.py`) and Rebecca confirmed every screen and key.

The probe runs from RAM at >A000 with the kernel at >2000, loaded either
by E/A option 5 (`TXAP1`, `TXAP2` on `txaprobe.dsk`) or by the cartridge
(`txaprobe8.bin`), whose loader copies the same image into RAM. It
checks for an F18A and 512K of SAMS (counting the card's pages), then
shows the split screen: status line, a 256 x 96 picture on the bitmap
layer, and 80-column text under it.

### Rebecca's results so far (19 October 2026)

Confirmed working: the picture over 80-column text with all four corners
and eight ticks; moving and resizing (E S D X, W Z); fat pixels with 16
colours and a round moon (F); 30 rows (R); the text and scrolling test
(T, readable and fast enough); the full-screen view and return (V); Quit
to a normal title screen (Q).  **M0 passes in js99er.**  The E/A option 5 path also works: Rebecca
loaded `TXAP1` from `txaprobe.dsk` through Editor/Assembler (2026-10-19).  Not yet run on
real hardware: worth a pass on the console (FinalGROM cartridge, and the
disk image through TIPI or a floppy) before M4, since js99er's F18A
emulation and its forgiving disk drive have fooled tests before.

### What M0 must answer (Rebecca's report)

1. Does 80-column mode come up, in 24 and 30 rows (R)?
2. Does the picture show over the text? All four amber corners and 8
   ticks? Do E S D X move it, W Z resize it?
3. Fat pixels (F): 16 colours, the moon round?
4. The full-screen view (V): picture centred, caption under it?
5. The text test (T): readable at 80 columns? Scrolling speed acceptable?
6. The status line's SAMS size: right for the card?
7. The version line's SR14 and SR12 values (they identify the board).
8. Quit (Q): back to the TI title screen with normal colours?

On an RP2040 PICO9918 question 2 is expected to fail (no bitmap layer in
80 columns on that board, per the F18A/PICO9918 reference) and the V view
to work. On an F18A or a PICO9918 PRO both should work.

### Decision waiting on M0's results

- **Picture presentation on boards without the bitmap layer in 80
  columns**: the full-screen view (Graphics I + bitmap layer, any key to
  return) is the proposed fallback, chosen per board at startup.
- **Picture pane size**: settled by M0. 30 rows works, so the split
  screen (96-line pane, 17 text rows) is the main layout.

## M1 (VM and compiler core): under way

Done: the compiler's front end, `tools/txc/` (lexer, AST, parser), with
`tests/txc_parse_test.py` (31 checks: the spec's example, every
construct, and ten malformed inputs that must get a clear message on the
right line).

Syntax details settled while building the parser (for Rebecca's review;
the spec's language summary is unchanged by them):

- Keywords are written in uppercase, but keywords and names are matched
  without regard to case, so ALPHA LOCK never breaks a program.
- `PRINT` ends the line; `WRITE` prints without ending it.
- `ATTRIBUTE` and `PROPERTY` declare new attributes and properties (the
  standard library declares its own this way).
- Any property can hold a routine: the property name alone on its line,
  then statements, then `END` (`DESC ... END`). In a routine property,
  `Action, Action:` lines open rule cases, which is how `BEFORE ... END`
  works.
- Array elements use call syntax: `slots(3) = 7`.
- Action names may be keywords (`Give`, `Remove`, `Move`) after `->` and
  in case labels.
- Hex numbers use the TI's `>` prefix (`>1F`).
- A statement line must be a statement, a call or an assignment;
  `target = value` at the start of a line always assigns.

Also done:
- the semantic pass, `tools/txc/sema.py` (includes, symbol table,
  numbering, the object tree, class inheritance, actions, name checks;
  `tests/txc_sema_test.py`, 35 checks);
- the instruction set, `tools/txc/opcodes.py`: the single definition of
  the VM's 72 opcodes and the image header, read by everything else;
- code generation and linking, `tools/txc/codegen.py` (bytecode, the
  word-substitution text compression, object/property/dictionary/action
  tables, header and checksum; same source, same bytes);
- the Python reference VM, `tools/txc/txvm.py`, the oracle the assembly
  VM will be tested against; `tests/txc_run_test.py`, 22 checks running
  compiled programs end to end.

More language details settled (approved by Rebecca, 2026-10-19):
- `(string) x` prints a string value; `obj.prop()` with no arguments
  prints or runs the property (Inform's PrintOrRun): a string prints, a
  routine runs, a value is returned.
- `##Name` is an action's number (`action = ##Take`), as in Inform:
  action names can't be bare words because actions like Open share
  names with attributes like open.
- Return defaults follow Inform: a ROUTINE that runs off its end returns
  TRUE; a property routine or rule case that runs off its end returns
  FALSE ("carry on with the action").
- Direction properties for in and out are INSIDE and OUTSIDE, because
  IN is the keyword for an object's parent.

Also done (the engine):
- the VM in TMS9900 assembly: `src/engine.a99` (boot, loading the story
  from cartridge banks into SAMS, checksum, the pristine dynamic copy,
  run-time errors, the end of the story), `src/vm.a99` (dispatch and all
  71 opcodes), `src/vmmem.a99` (the story through three SAMS windows: A
  for code, B for data, D for text being printed), `src/output.a99`
  (CHOUT, word wrap at 80 columns, scrolling, [MORE], strings, numbers).
  The resident engine is about 5K at >A000; the kernel 2K at >2000.
- `tests/m1_vm_test.py`, 13 checks: the same compiled images run on the
  assembly VM (in the simulator) and the Python VM, and every character
  the engine prints must equal the Python transcript; plus the screen
  against a model of the wrap rules, the opcode table against
  `opcodes.py`, and a damaged story refused.
- `demos/m1demo.txa` and its cartridge `txa-m1demo8.bin` for js99er.

More language additions (approved by Rebecca, 2026-10-19):
- built-in functions with reserved names: PARENT, CHILD, SIBLING,
  RANDOM, READKEY, SAVE, RESTORE, UNDOSAVE, UNDO, QUIT, RESTART, STATUS,
  SOUND (save/undo are placeholders returning 0 until M4);
- -32768 may be written (only with the minus sign).

A real bug found by the tests and fixed: a second press of the same
key at a second [MORE] was ignored, because nothing scans the keyboard
between waits.  Each wait now forgets the last key.

SAMS layout change from the spec: pages 28-31 hold a pristine copy of
the dynamic area for RESTART, so the undo ring is pages 16-27 (48K).

Maps that change (Rebecca's question, 2026-10-19): every ROOM now gets
all twelve exits automatically, and PUTPROP records the kind of value
stored (a routine name, a string, or anything else), so a routine exit
assigned a room becomes a plain exit and the reverse.  Found and fixed
an engine bug while testing it (PUTPROP lost the kind in a scratch word
PROPF also uses).  `tests/txa/dynmap.txa` checks it on both VMs.  Note
for the manual: keywords ignore case, so a name like `room` cannot be
used for a variable (it is the keyword ROOM).

Rebecca ran `txa-m1demo8.bin` in js99er (2026-10-19): the room
description and contents list, the log book, the lantern's BEFORE/AFTER
rules, the die roll, the wrapped paragraph, scrolling with [MORE], and
the end-of-story return to the title screen all worked.

Text styles (finishing M1): `STYLE(n)`, a built-in, with 1 bold, 2
underline, 4 reverse, added together.  256 glyph slots cannot hold
normal, bold, underlined and reverse sets, so bold and reverse are
colours from the F18A's per-position attributes in 80-column mode (on
every F18A-class board, RP2040 included): normal text is a soft light
gray (palette 14), bold white (15), reverse swaps them.  Underline is a
glyph set in patterns 160-254.  VRAM moved to make room for the
2400-byte attribute table (defs.a99 has the map).  The status line,
[MORE] and the end message use reverse colours.  Tests check the
glyphs and colours on screen.

**M1 is complete.**  Rebecca ran the rebuilt demo (with text styles) in
js99er and it worked (2026-10-19).

## M2 (the parser): under way

**Design change, confirmed by Rebecca (2026-10-19):** the parser is written in
TXA as part of the standard library (lib/parser.txa), not in assembly.
It runs identically on both VMs, so the transcript tests cover it for
free, and a game can replace any part of it.  The engine supplies the
low-level work: READ (line input and editing) and TOKENIZE (words and
dictionary lookup).  A step that is slow on real hardware becomes an
assembly opcode without changing behaviour.

Done (Python side):
- the standard library as real files: lib/stdlib.txa (Main loop),
  lib/libdefs.txa (attributes, properties, globals, player, compass),
  lib/parser.txa, lib/verbs.txa (enough verbs to exercise the parser;
  the full set is M3);
- the parser: articles; names matched on every word, a phrase ending
  where no object fits any more; ALL with EXCEPT/BUT; lists with AND or
  commas; IT/THEM/HIM/HER; orders ("ada, take coins"); several commands
  on a line (full stops, THEN); AGAIN/G; OOPS; "Which do you mean ...?"
  with replies that narrow or start a new command; "What do you want to
  take?"; two-pass grammar matching (quiet trial of every line, then
  questions on the chosen one); Infocom's error messages; compass words
  alone mean GO;
- language and compiler: 'word' dictionary literals; NAME is property 1
  holding dictionary words; PROPLEN(o, P) and PROPWORD(o, P, i); AGET
  and APUT (arrays passed by number); HASATTR(o, a); FRESHLINE();
  READ(text, parse) and TOKENIZE(text, parse); LASTOBJ; the generated
  arrays VERBTAB, GRAMTAB, ACTSUB, DICTVERB (formats in sema.py);
- opcodes READ (new form), TOKENIZE, HASATTRV, ALOADV, ASTOREV, FRESH
  in opcodes.py and the Python VM;
- tests/m2_parser_test.py: a 45-command script on a test world,
  compared with a reviewed reference transcript, plus 19 named checks.

Portability rules (spec, 2026-10-19): two current items must come into
line by M4.  The PICTURE and SOUND placeholders print "[picture n]" and
"[sound n]" on both VMs; rule 2 says optional features degrade silently,
so M4 makes them silent where unsupported (and real on the TI).  Save
files get their platform-independent format in M4 (rule 6).

Done (the TI side):
- src/input.a99: the line editor (block cursor; FCTN S rubs out; SHIFT;
  FCTN I/O/P and SHIFT / and 1 for ? ' " - !), with its own key decoder
  KEYGT2 (KEYGET ignores keys pressed with FCTN or SHIFT); READ (the
  typed line goes through CHOUT, as txvm.py echoes it); TOKENIZE with a
  binary search of the dictionary; ALOADV, ASTOREV, HASATTRV, FRESH.
- Speed: profiling showed name matching dominating, so two inner loops
  became engine built-ins: ISNAME(w, obj) and FILTERN(w, src, n, dst).
  Bytecode run over the test script fell from 431K to 162K instructions.
  Estimate (9 us an instruction): median 1.2 s a command, 90% under
  3.3 s, worst 5.1 s (TAKE ALL and the like).  Needs timing on the
  console.  The engine's own profile: about a third in fetch and
  dispatch (NEXT, FB, FW), a tenth in story memory (BMAP, RDW): both can
  be tightened without touching the library.
- An engine bug from M1 fixed: MOVE kept its destination in VT4, which
  DETACH overwrites when the object has an earlier sibling.
- tests/m2_engine_test.py: the engine plays the 45-command script typed
  key by key (holding and releasing each key) and its transcript equals
  the Python VM's exactly; plus a rub-out/SHIFT test.
- demos/m2demo.txa, cartridge txa-m2demo8.bin: the test world, playable.

**M2 is complete.**  Its two follow-ups were done on 20 October 2026:
command history (FCTN E and FCTN X, the up and down arrows, through the
last 16 commands, kept in SAMS page 27 and shown through window D while
READ runs) and a 160-character input line running onto a second row
(the window scrolls first if the prompt is on the bottom row).  The
undo ring is now pages 16-26.  m2_engine_test checks both against the
Python VM.

## Engine speed work (19 October 2026)

Measured with `tests/bench_engine.py` (the 45-command parser script;
results kept in build/bench.txt).  Instruction counts are exact; seconds
are an estimate (9 us an instruction from the 32K expansion, 5 us from
the scratchpad):

| Step | Instructions | Median | 90% | Worst |
| --- | --- | --- | --- | --- |
| Baseline (after ISNAME/FILTERN) | 8.13M | 1.16 s | 3.31 s | 5.09 s |
| Globals kept in RAM | 7.95M | 1.14 s | 3.24 s | 4.97 s |
| Scratchpad block, 256-entry table | 6.78M | 0.93 s | 2.24 s | 3.49 s |
| VMBR and VFILL unrolled | 5.84M | 0.70 s | 2.02 s | 3.13 s |
| LOAD/STORE direct paths for locals | 5.50M | 0.68 s | 1.92 s | 2.98 s |

What changed:
- src/fast.a99: the dispatch loop (NEXT), code fetches (FB, FW) and the
  story-memory accessors (RDW, WRW, RDB, WRB) run from the scratchpad
  (>8320->83DD), the TI's only wait-state-free RAM; slow paths (page
  ends, remaps) stay in expansion RAM.  OPTAB has 256 entries, so no
  range check.  The data window's cache is now a page base (CURBH).
- Globals live in RAM (GLOBRM, >3C00).  Rule: anything that copies the
  dynamic area (SAVE, UNDO in M4) calls GSYNC first and GLOAD after.
- VMBR and VFILL unrolled like VMBW.
- LOAD and STORE reach locals directly.
- A page-crossing test (a 23K story) makes every slow path run at least
  once (checked by counting).

Still possible, if the console says so: scrolling is about a fifth of
command time; a RAM copy of the text window (scrolling without reading
video memory), or the F18A/PICO9918 GPU's DMA copy, would cut most of
it (the GPU route cannot be tested in the simulator).  The dispatch
loop could shed more with compiler-side changes (short forms of the
commonest instructions).

## M3 (world model and standard library): under way

Parts: 1 the turn and the room; 2 doors and containers in depth; 3 the
verb set; 4 the sample game.

Part 1 done (19 October 2026):
- the action sequence: an order goes to ORDERS; otherwise the game's
  beforehook (a global the game sets to a routine), the room's BEFORE,
  the object's BEFORE, the action routine; action routines call
  AfterRules: the room's AFTER, the object's AFTER, the game's
  afterhook.  (Hooks are globals holding routines, so they are optional:
  TXA has no "optional routine" otherwise.)
- the end of a turn (lib/turn.txa): turns counted (meta commands
  SCORE, VERBOSE, BRIEF, SUPERBRIEF, NOTIFY, QUIT take none; nor does a
  command that did not parse); daemons (StartDaemon/StopDaemon, DAEMON
  property); timers (StartTimer(o, t), StopTimer, TIME_LEFT and TIME_OUT;
  the turn a timer starts counts); the room's EACH_TURN; the game's
  endturnhook; score notification ([Your score has just gone up by 5
  points.]; NOTIFY ON/OFF); the status line.
- light: IsLit; darkness ("Darkness" / "It is pitch dark, and you can't
  see a thing."); in the dark only what is carried is in scope; EXAMINE
  and SEARCH need light.
- room descriptions: BRIEF (default), VERBOSE, SUPERBRIEF; INITIAL
  paragraphs until an object is moved (the moved attribute, given by
  TAKE); "You can (also) see ... here."; "On the oak table is a brass
  lamp." for supporters and open containers, scenery included; CANT_GO.
- verbs: SCORE, VERBOSE, BRIEF, SUPERBRIEF, NOTIFY, SWITCH/TURN ON/OFF.
- STATUS now takes the room, score (-1: none) and moves; the engine
  draws them straight into row 0 (not into the transcript).
- tests: tests/m3_world_test.py (world1: reviewed reference + 12 named
  checks), tests/m3_engine_test.py (the engine plays each M3 world:
  same transcript, and the status line checked).

Library names that collide with built-ins (names ignore case): the
status routine is ShowStatus, not Status.

Part 2 done (19 October 2026):
- floating objects: FOUND_IN lists rooms; MoveFloating brings them into
  the room with the player and removes them from rooms not listed.
- doors: the door attribute; an exit may name a door object; a closed
  door stops the player ("You can't, since the front door is closed." /
  "... seems to be locked."); DOOR_TO with two rooms leads to whichever
  the player is not in, or one room, or a routine.  ENTER / GO THROUGH
  a door.
- locks: lockable, locked, WITH_KEY; UNLOCK/LOCK X WITH Y, OPEN X WITH Y.
- containers: "That can't contain things.", closed, CAPACITY ("There is
  no more room in ..."), nothing inside itself; supporters the same;
  EMPTY; inventory lists contents (indented), "(which is closed)",
  "(which is open but empty)", "(providing light)", "(being worn)".
- entering: the enterable attribute; ENTER / SIT ON / GET IN; EXIT /
  GET OFF / GET OUT / STAND UP; "Garden (on the bench)"; leaving the
  room or taking what you're on asks you to get off first.
- tests: world2 (reference + 8 named checks); the engine plays world1
  and world2 identically.

Library names that collide (names ignore case): IsInside, not Inside
(the INSIDE exit property).

Part 3 done (19 October 2026):
- lib/verbs2.txa: about 45 more verbs (73 verbs, 76 actions in all):
  READ, EAT, DRINK, WEAR, REMOVE/DOFF/TAKE OFF, PUSH/PULL/MOVE/TURN,
  TOUCH, SMELL, LISTEN, TASTE, THROW AT, SHOW, KISS, ATTACK, ANSWER/SAY,
  CLIMB, DIG, BURN, CUT, TIE, FILL, WAVE, SQUEEZE, BLOW, BUY, SLEEP,
  WAKE, THINK, SING, PRAY, SWIM, JUMP, YES, NO, SORRY, RESTART, SAVE,
  RESTORE, UNDO, VERSION.  Default responses written fresh for TXA.
- QUIT and RESTART ask yes or no (YesOrNo); SAVE, RESTORE, UNDO report
  failure until M4.
- Language: REPLACE name (the game's routine of that name replaces the
  library's: the one in the same file as the REPLACE is kept) and
  EXTEND "verb" [FIRST] (grammar lines added to an existing verb).
- TAKE OFF X / GET OFF X: TakeOffSub decides (worn or held: Disrobe;
  otherwise get off).
- tests: world3 (reference + 8 named checks); the engine plays all three
  M3 worlds identically, status lines checked.  The parser script now
  ends with "y" for the quit question.
- size: world3 compiles to 24K with 5K of dynamic state.
- speed: the bigger library (more grammar lines for TAKE/GET) slowed
  the parser 19% (162K -> 193K bytecode instructions on the script).
  Fixed: each GRAMTAB line now starts with the index of the next line
  (NextLine is one read); lines starting with a fixed word are rejected
  without a full match; ACOPY (a new built-in) copies arrays.  Now 169K;
  engine benchmark median 0.74 s, worst 3.32 s (before M3: 0.68 s,
  2.98 s with a library half the size).

Part 4 done (19 October 2026): samples/lamplight.txa, "Lamplight",
the sample game (later the tutorial).  Fifteen rooms; light and dark
(the stair and the sea cave need the lantern), a locked shed and the
keeper's key (given for his spectacles), a character answering ASK
about topics, the tide (a daemon) flooding the causeway (exit routines),
the sea as one floating object in five rooms, a hidden treasure, POUR
and LIGHT verbs added by the game (VERB, EXTEND), 25 points and an
ending.  tests/sample_test.py: the 47-command walkthrough on the Python
VM against a reviewed transcript, then on the engine, identically.
Cartridge: lamplight8.bin.

Library additions found by writing it: a turn that brings light into a
dark room describes the room ("You switch the storm lantern on." then
the cave); one that takes it away says "It is now pitch dark in here!";
the end of a scored game reports "In that game you scored 25 out of a
possible 25, in 47 turns."

**M3 is complete.**

(The happy-path Claude Doc linked below was deleted on 20 October 2026 at
Rebecca's request: LAMPLIGHT-TESTING.md replaces it.)

Fixed after Rebecca's report (19 October 2026; she confirmed the symptom: each
letter in reverse video until ENTER): typed letters stayed in
reverse video until ENTER (the cursor cell's colours were never reset
when a letter replaced it).  m2_engine_test now checks the screen
mid-typing.  The happy-path test for lamplight8.bin is a Claude Doc:
https://claude.ai/code/artifact/271a225f-12cf-4e70-9503-129083f04dec

## M4: under way

Parts: 1 UNDO; 2 SAVE and RESTORE; 3 stories on disk and the game
writer; 4 pictures; 5 sound and music.

Fixed first (20 October 2026): the command history's counters sat
inside the status-line buffer, so a long status line ("Score: 10
Moves: 23") corrupted them.  Moved, and build.py now refuses to build if
any two RAM variables overlap (sizes from the "N bytes" in their
comments); it caught a second overlap at once (UNDO's literal buffer).
Regression test in sample_test.

Part 1 done (20 October 2026): UNDO.
- Opcodes: UNDOSAVE pushes 1, or 2 when an UNDO comes back to it; UNDO
  goes back to the newest snapshot and removes it, or pushes 0.
- Library: a snapshot after reading every command but UNDO itself; when
  UNDO comes back, "[Previous turn undone.]" and the old command is not
  run.  UNDO again goes further back.
- TI (src/undo.a99): LAST (pages 16-19) holds the dynamic area at the
  newest snapshot; records (pages 20-26, 28K) hold the stacks, registers
  and the XOR difference from the snapshot before, run-length coded.
  UNDO: dynamic area = LAST, then LAST ^= the record's difference.  128
  records or a full 28K start the records again.  GSYNC before, GLOAD
  after.  RESTART clears them.
- The Python VM keeps full snapshots, unlimited.
- tests: world4 (reference + 5 named checks); the engine plays it
  identically.

Part 2 done (20 October 2026): SAVE and RESTORE.
- SAVE(t) / RESTORE(t) take a file name in a text array; the library
  asks "Save to which file? (Enter for SAVE1)"; on the TI a name with no
  device gets DSK1. in front.
- The save file (opcodes.py, "the save file"): magic TXS1, version,
  story checksum and release, dynamic length, the PC and frames as story
  addresses, the value stack, the dynamic area as XOR against the
  story's original (run-length coded), a checksum.  The same bytes on
  every engine: the test checks the TI's file is byte for byte the
  Python VM's, and each VM restores the other's.
- RESTORE reads the whole file once to check it (format, story,
  release, sizes, checksum) before changing anything.
- TI: src/disk.a99 (The Lantern Coast's DSRLNK and PAB call; the fast
  block copied back and the sprite patterns zeroed after each call; the
  VM registers kept), src/save.a99 (the file built straight into VRAM
  at >2000, at most 23 sectors / 5888 bytes; a Lamplight save is 435).
- Bugs found and fixed: a second ENTER while the game was busy was lost
  (KEYFRE: a new line forgets the last key if none is down); the file
  name pointer was clobbered by RDW; RESTORE's frame count was in a
  scratch word VGETW uses; RESTORE reloaded the globals through a stale
  data window (getting the story's starting values: the save test now
  changes globals between saving and restoring).
- tests/m4_save_test.py (7 checks).

Part 3 done (20 October 2026): stories on disk, and the game writer.
- tools/txa_game.py story.txa --prefix LAMP [--title] [--cart]: the
  engine as E/A 5 files (LAMP1..3), the story as 4K PROGRAM files
  (LAMPS01..), a DSSD disk image with all of them, and optionally the
  cartridge.  Lamplight: 3 engine files, 8 story files, 189 sectors.
- The engine (STMODE in gen/storysrc.a99) loads the story from
  DSK1.<prefix>Snn into SAMS with "Loading" and a dot a file, then
  checks the whole story's checksum; a missing file stops with its name.
  Story files are 4K (not 8K) because a file passes through the 5888-byte
  VRAM buffer.
- build.py: write_storysrc() and assemble_engine() shared by the
  cartridge build and the game writer.
- tests/m4_disk_test.py (5 checks).
- Still to do: the device the game was loaded from (now always DSK1).

Title page (20 October 2026, Rebecca's request): the library's
TitlePage(title, byline, blurb) clears the screen, shows the title in
bold and the rest centred, waits for a key, clears again.  Engine: STYLE
8 = centred lines (the engine knows the width: portability rule 4) and a
CLS instruction (clear the text window).  Lamplight uses it.  Pictures
and music will join the title page in parts 4 and 5.

UNDO's cost found and cut on the way: the snapshot taken before every
command encoded the whole dynamic area a byte at a time (Lamplight: about
2 s a command on the estimate).  Now a word-at-a-time scan per page with
byte handling only where something changed, and page copies for UNDO,
UINIT and RESTORE: Lamplight's estimate 3.3 s -> 1.6 s a command (1.2 s
before UNDO; the rest is the stacks and globals copied a byte at a time
into each snapshot: room to tighten later).

From Rebecca's play-testing (20 October 2026): the cave's float was
never named ("Something round and green gleams ..."), so a player had
no word for it.  Now named in its INITIAL text, with "green", "round",
"thing", "something" as names, and examinable stones that point to it.
Library: OPEN now reveals what a container held ("You open the drawer,
revealing a box of matches."), Infocom-style; the matches had the same
problem.  Rule for game text, worth putting in the authoring manual:
every object a player needs must be named in text they can see.

Authoring Language Reference written (20 October 2026), a Claude Doc:
https://claude.ai/artifact/FdxcHQseUMuCM6etTi4BzW  (built from the
compiler and library source; its examples and compiler messages were run;
keep it current as the language changes).  Not yet covered there:
scope=Routine supplying out-of-scope objects (not implemented: it only
filters, like noun=Routine).

Part 4 done (21 October 2026): pictures.
- tools/txpics.py: a PNG becomes format 2 (256 x 96, 4 colours: when the
  PNG has at most four) or format 4 (128 x 96 fat pixels, 16 colours,
  scaled and reduced), each with its own 12-bit palette, run-length
  packed.  The picture area (count, offsets, records) follows the story
  in SAMS from the next page (build.story_blob; PICPG in storysrc); the
  portable story image holds only picture numbers (rule 3).  The
  cartridge and the disk files carry story and pictures together.
- src/picture.a99 (in the kernel window: the resident engine was full):
  PICTURE n loads the palette into F18A entries 32-47, decodes the pixels
  through window D into the bitmap layer at >2800, puts the layer at
  scanline 8 under the status line, 96 rows; the text window starts at
  row 13 (rows 1-12 blanked).  PICTURE 0: layer off, text from row 1.
  Every disk call redraws the picture after (PICRDW); RESTART hides it.
- Library: ShowPicture(n) (remembered in picnum, so RESTORE and UNDO show
  it again), room pictures by the PIC property (shown by DescribeRoom,
  hidden in rooms without one and in the dark), PICTURES ON/OFF,
  title_picture for TitlePage (the title page then starts under it).
- Python VM: PICTURE prints nothing (records it); transcripts unchanged.
- Lamplight: three pictures drawn in code (samples/pics/mkart.py):
  TITLE and CAVE in 16 colours, LAMPROOM in 4.  On the title page, the
  lit Sea Cave and the Lamp Room.
- tests/m4_picture_test.py (11 checks: the exact pixels and palette in
  VRAM, format, place, the text window, SAVE/RESTORE/UNDO).
- Not done: the full-screen fallback for RP2040 PICO9918 boards (they
  have no bitmap layer in 80 columns): needs board detection, untestable
  here; and the TI Artist importer (a workbench feature).

From Rebecca's play-test of the pictured build (21 October 2026):
- "the pictures seem to be duplicated horizontally": a js99er bug, found
  in its source (assembly/f18a.ts): in 80-column mode it halves the
  screen x for the bitmap layer's bounds test (bmpX = x >> 1) but not
  for the pixel address (bitmapX1 = x - bitmapX), so each 480-pixel line
  reads two picture rows: the picture at half width, then again (one row
  lower) on the right.  The F18A reference keeps the layer on its
  256-pixel grid in 80 columns, so real hardware should show one
  full-width picture; not yet confirmed on a console.  (The M0 probe
  will have shown the same doubling.)
- The end screen's status line showed the score before the winning
  move (15, not 25): the move that ends the game skipped EndTurn.  Fixed:
  the library counts it as a turn and redraws the status line;
  sample_test checks "Score: 25  Moves: 47" on the engine.
- "--   $-" after the moves on the end screen: not reproduced in the
  simulator; waiting on a screenshot and whether it was js99er or the
  console, and whether SAVE/RESTORE were used.

Manual stubs (21 October 2026, Rebecca's request), a Claude Doc with a
tab each: https://claude.ai/artifact/VqqmmXaB3E5RBxdTcfBtU2 (doc id
e991a3e1-d294-4b84-b02e-d46e2dc1b69b).  Workbench Manual, Engine
Implementation Guide, Standard Library Reference, Tutorial (Lamplight
step by step, each chapter a tested file), Player's Card (generated by
txa_game.py), Technical Reference: purpose, audience, outline, sources,
when each can be written.

End screen (21 October 2026, Rebecca's request): the library's
EndScreen, called when deadflag is 1 or 2.  After the last move's text:
the banner (endmessage, or "*** You have won ***" / "*** You have died
***") and the score, centred; end_picture if set; then "Would you like
to RESTART, RESTORE a saved game, UNDO your last move, or QUIT?" until
one is chosen (UNDO after a death takes back the fatal move).  QUIT
during play skips it; a game may REPLACE it.  Lamplight shows a new
ending picture (the lighthouse lit, samples/pics: ending.png) and its
walkthrough now ends with "quit".  Also fixed: YesOrNo's "Please answer
yes or no." had no line break.  tests: world5 (death, a wrong answer,
UNDO, RESTORE, RESTART, a custom endmessage, QUIT; 6 named checks, the
engine identical); the picture test checks the ending picture.

QUIT left the console hung (21 October 2026, Rebecca's js99er
screenshot: after the end screen's QUIT, the game's text in 40 columns,
no title screen).  Cause: the fast block (copied to >8320-83DD in the
speed work, after M0's probe proved QUIT) covers the console's user
interrupt hook at >83C4 and sound count at >83CE; the console's
power-up enables interrupts before clearing them, so a stale hook jumps
into engine code.  Fixed: QUIT clears >8320->83FF before BLWP @>0000.
The simulator modelled the reset as clearing the scratchpad, which hid
it; it now records the scratchpad as the program left it
(scratch_at_reset).  tests/m4_quit_test.py checks it (and fails on the
old engine).  Also js99er's "-- $-" end-screen junk: same screenshot
shows ",-  -(" in screen memory rows the picture covers; still
unexplained, but not on the visible screen while the game runs.

js99er bug report prepared (21 October 2026): outputs/txa/js99er-pr/
(PULL_REQUEST.md, a one-line patch to assembly/f18a.ts against js99er
master f6054a95 (2026-10-11): bitmapX1 = bmpX - bitmapX; a before/after
image from the renderer's formula; the M0 probe as the test cartridge).
For Rebecca to send to js99er's author.

Part 5 done (21 October 2026): sound and music.
- tools/txsound.py: the notation (an MML dialect: TEMPO, LOOP, voices A B
  C N; notes, lengths and dots, octaves, volume, @ decay, & ties, [ ]
  repeats, drum letters k s h x n0-7), compiled to per-voice event
  streams (tone, rest, volume, decay, noise, hold, end), the sound area
  (tunes then effects), the reference Player, and WAV previews.  A
  looping tune's voices must be the same length; an effect has at most
  two voices.
- Language: MUSIC Name "FILE" and SOUND Name "FILE" declarations
  (numbered from 1); the MUSIC(n) built-in (opcode >63); SOUND(n) was
  already there.  The room property is TUNE (MUSIC is the built-in's
  name; the spec's sketch used MUSIC).
- src/sound.a99 (kernel window): six voices (four music, two effect),
  played once a frame (the VDP frame flag, polled in both key waits and
  at every routine call: three instructions, no registers), in its own
  workspace (>83E0, the GPL workspace) by BLWP; MUSIC and SOUND BLWP
  there too.  Reads the area through window D and puts D back (MAPWIN
  now remembers D's page in DPAGE).  RESTART and QUIT silence the chip.
- Space: the font moved out of the kernel window to VSTK (it is read
  only at startup; the value stack overwrites it), so the E/A 5 chain
  has four files; rle.a99 left the engine (unused); URECS halved (64
  undo records) to make room for the voices.
- Library: PlayMusic (remembered in tunenum, back after RESTORE and
  UNDO), PlaySound, RoomMusic (TUNE), MUSIC ON/OFF, SOUNDS ON/OFF,
  title_music, end_music.
- Lamplight: title (a sea song), harbour (a shanty, the outdoor rooms),
  ending (a fanfare); the tide, a match, the ship's horn.
- tests/m4_sound_test.py: the TI player's chip bytes equal the reference
  player's for the whole walkthrough (4111 frames, 27 calls, 974 bytes).
- Bug found: xas99 has no operator precedence (left to right):
  VOICES+4*VSIZE assembled as (VOICES+4)*VSIZE; parenthesise.

Scrollback done (21 October 2026): every line EMITLN shows is also kept
in a ring of 50 slots (80 characters + 80 colour bytes) in SAMS pages
25-26, carried through window B (a line may be shown during PRSTR, which
owns D; CURBH is marked unknown afterwards).  BACK (FCTN 9) at the prompt
opens the viewer: FCTN E back a line, FCTN X forward, ENTER or BACK
return, a hint in reverse on the bottom row; on return the screen is
drawn again from the ring (the rows above the prompt are always the
latest lines) with the prompt and the typed text.  Centred lines come
back left-aligned.  The undo records went from 7 pages to 5 (20K).
To make room, the startup code (START, the loaders, CHKST, FATAL, the
no-F18A screen) moved to the startup segment at VSTK with the font;
START now ends with B @VMRUN (it used to fall through, which the move
broke at first: the boot looped).  tests/m4_scrollback_test.py (5
checks: the viewer's rows, the hint, the screen restored exactly, the
next command normal).

**M4 is complete** (engine 1.0 beta): save, restore, undo, status line,
scrollback, pictures, sound and music, stories on disk and the game
writer, the title page and the end screen.

M5 design drafted for Rebecca's review (21 October 2026), a Claude Doc:
https://claude.ai/artifact/UZ6z6yM1ZeuFV9V4cja64D (doc id
df223b89-078d-43ef-9658-cc9a72bf1bd6).  Four decisions await her: D1
long strings in DV80 source (recommended: an open string continues on
the next line, the break a space, leading spaces skipped; a language
change in both compilers), D2 the library compiled from source first,
D3 stop at the first error like Python, D4 a separate "TXA Workbench"
cartridge with a minimal front end.  The plan: 1 groundwork (D1, the
cartridge skeleton, DV80 loading, dump formats), 2 lexer, 3 parser,
4 meaning, 5 code, 6 linking and output; each stage matched to Python
on the whole corpus by dumps from SAMS.

Rebecca approved D1-D4 as recommended (21 October 2026).

M5 part 1 under way:
- D1 done in the Python compiler: a string left open at the end of a
  line continues on the next (the break one space; trailing spaces and
  the next line's leading spaces dropped); the string token keeps its
  first line; an open string at the end of the file is an error at its
  first line.  txc_parse_test: 5 checks.
- tools/txa_wrap.py: TXA source to 80 columns (breaks at a single space
  inside any string; long comments move above).  Six long code lines in
  the library rewritten (helpers SeesInto, AllCandidate, ShowsInside;
  IsMeta in groups; locals in the OOPS splice): behaviour unchanged.
- tests/txc_wrap_test.py: the library, Lamplight and every m2/m3 world,
  wrapped, compile to identical images.

M5 part 1 done (21 October 2026):
- D1, tools/txa_wrap.py, the library's long lines (above).
- The simulator's disk does DIS/VAR files (OPEN, READ, CLOSE: a text
  file a record a line; error 5 past the end, 7 when missing).
- src/diskrec.a99 (the workbench's, not the engine's): DVOPEN, DVREAD,
  DVCLOS on the shared DSRLNK and PAB.  disk.a99's DSKCAL now calls the
  program's DSKFIX after a disk call (the engine: the fast block back;
  the workbench: nothing).
- src/wbench.a99, the workbench cartridge skeleton (build.workbench_cart):
  80 columns on the engine's kernel; asks for a source file (default
  DSK1.LAMPLIGHT; the kernel's KEYGET has no FCTN, so no rub-out until
  M6's line editor); reads it record by record into SAMS from page 32,
  a line feed after each; reports lines and bytes.  Its variables live
  in wbench.a99 (over the engine's URECS), not defs.a99.
- tools/txc/dump.py: the canonical token dump (line kind value).
- tests/m5_load_test.py: Lamplight wrapped to 80 columns read into SAMS
  byte for byte (428 lines, 12090 bytes); a missing file reported.

M5 part 2 done (21 October 2026): the lexer on the TI.
- src/wlex.a99: lexer.py's rules in the same order (strings with D1,
  dictionary words, ##actions, names and keywords, decimal to 32768, hex
  where an operand may start, symbols); tokens in SAMS from page 64 as
  kind, line, text length, text (and a number's value); errors stop with
  a code and line (WBERR, WBERRL).  The workbench lexes after loading.
- tests/m5_lex_test.py: the TI's tokens, read back and dumped
  canonically, equal dump.tokens for the whole corpus (the 6 library
  files, Lamplight, the M2 demo, the m2/m3 worlds: about 14,500 tokens);
  7 error cases give the same error on the same line.
- Speed: about 85 TI instructions a source byte: Lamplight with its
  library about 25 s on a real TI.
- Bug found: TPUT's page change called MAPPG, which uses R2 and R3,
  TEMIT's text pointer and count: tokens ran past the end of SAMS until
  the page numbers wrapped onto RAM and the kernel.  R2/R3 now kept.
- The tests type file names in lower case: the kernel's KEYGET stops at
  SHIFT (and gives capitals anyway); part 1's missing-file check had
  passed by luck.

From Rebecca's first try of the workbench (21 October 2026): she had no
disk to mount (only lamplight.txa, a PC file), and FCTN S did nothing at
the prompt.  Now tools/txa_srcdisk.py writes a game's source and the
library, wrapped to 80 columns, as DIS/VAR 80 files on a DSDD image
(build/lamplight-src.dsk: LAMPLIGHT, STDLIB, LIBDEFS, PARSER, VERBS,
VERBS2, TURN), each read back and checked; and the workbench reads keys
itself (WKEY, as the engine's KEYGT2: modifiers set aside before the
scan), so FCTN S rubs out and SHIFT works.  The load test checks both.
Rebecca then loaded it in js99er: "Read 428 lines, 12090 bytes. 1333
tokens." as in the simulator.  It seemed stalled afterwards: it waited
for a key without saying so, and went back to a prompt that looked
unchanged.  Now it says "Press a key to choose another file." and clears
the results when it asks again (tested).

## Next

1. M5 part 3: the parser on the TI (a compact tree in SAMS; its canonical
   text dump to add to dump.py; trees identical for the corpus; the
   first parse error identical for malformed programs).
2. M5 parts 4-6 as in the design doc.

## (was) M5 (waiting on D1-D4): the native compiler (the workbench cartridge: source loading,
   three passes, the precompiled library, error list; done when the TI
   produces images byte-identical to the Python compiler for the whole
   corpus).  Start with its design.

## (was) M4 part 5 (sound and music): MUSIC/SOUND declarations, MML notation
   for Rebecca's review, MIDI import, the TI player (frame-flag ticks in
   key waits and calls), room MUSIC, Lamplight music.

## (was) Next
1. M4: saving, restoring and UNDO (platform-independent save format;
   GSYNC/GLOAD around them; the scratchpad block after disk calls);
   loading stories from disk; pictures and sound (MUSIC/SOUND, silent
   where unsupported); the standalone game writer (EA5 + data files).
2. Rebecca's play-test and timing of lamplight8.bin.

## (done) M3 part 3: the verb set.  Part 4: the sample game.
3. Rebecca's timing of txa-m2demo8.bin when she can.

## (was) Next before M3

1. Rebecca's js99er (and console) check of txa-m2demo8.bin, and timing.
2. M3: the world model and full standard library (light, doors,
   containers in depth, characters, daemons and timers, scoring, the
   Infocom verb set, the sample game).

## (old heading) M1 remaining

Python cross-compiler's semantic pass and code generation; the VM,
text output, word wrap and [MORE]; bold and underline glyph sets.

## Decisions

| Date | Decision |
| --- | --- |
| 2026-10-18 | Engine first, then an original story developed together |
| 2026-10-18 | Custom engine on the Lantern Coast kernel, not a Z-machine |
| 2026-10-18 | Text plus occasional illustrations; import now, editor later |
| 2026-10-18 | Native workbench delivered and documented separately |
| 2026-10-18 | Full spec as a Claude Doc before coding |
| 2026-10-19 | M0 started from The Lantern Coast 1.13 bundle |
| 2026-10-19 | Authoring language approved as proposed: uppercase keywords, terse property names, BEFORE ... END rule blocks, name TXA |
| 2026-10-19 | Sound (M4): background music by location and sound effects, by number like pictures; MUSIC and SOUND opcodes (silent where unsupported); a room MUSIC property the library follows; sources in a text notation (MML-based, designed by Claude for Rebecca's review) and imported from MIDI |
| 2026-10-19 | Portability is an explicit goal: the spec's "Portability rules" (eight rules) are checked for every later decision |
| 2026-10-19 | The parser lives in the TXA standard library; the engine supplies READ and TOKENIZE in assembly |
| 2026-10-19 | Every ROOM gets all twelve exits automatically (NOTHING where not given), so any exit can be changed while the game runs |
| 2026-10-19 | Approved: the built-in functions (reserved names) and -32768 only with its minus sign |
| 2026-10-19 | Approved: `(string) x`; `obj.prop()` as print-or-run; `##Name` for action numbers; Inform's return defaults (ROUTINE TRUE, property routines and rule cases FALSE); INSIDE and OUTSIDE as the in/out direction properties |

## History

- 2026-10-21 M5 part 2: the lexer on the TI, identical to Python for the corpus.
- 2026-10-21 M5 part 1: D1, txa_wrap, DV80 record reading, the workbench skeleton, the token dump.
- 2026-10-21 M4 complete: scrollback; startup code moved to the startup segment.
- 2026-10-21 M4 part 5: sound and music (notation, sound area, TI player identical to the reference, library, Lamplight's tunes and effects).
- 2026-10-21 M4 part 4: pictures (converter, picture area, pane, library, Lamplight's three pictures).
- 2026-10-20 M2 follow-ups: command history (FCTN E/X) and the two-row, 160-character input line.
- 2026-10-19 M3 complete: part 4, the sample game Lamplight; light-change descriptions; final score; parser speed with the full verb set.
- 2026-10-19 M3 part 3: the verb set (73 verbs), QUIT/RESTART confirmation, REPLACE and EXTEND.
- 2026-10-19 M3 part 2: doors, floating objects, locks and keys, containers in depth, inventory contents, EMPTY, ENTER/EXIT.
- 2026-10-19 M3 part 1: action sequence and hooks, end of turn (daemons, timers, EACH_TURN, score notification), light, room descriptions and modes, status line in the engine.
- 2026-10-19 Engine speed work: scratchpad block, globals in RAM, unrolled VDP reads, LOAD/STORE paths: 8.13M -> 5.50M instructions on the script.
- 2026-10-19 M2: the TI side (line editor, READ, TOKENIZE, ISNAME, FILTERN), engine plays the parser script identically; checkpoint-m2.
- 2026-10-19 M2 begun: the standard library's parser in TXA, with the compiler and Python VM support it needs.
- 2026-10-19 M1 complete: text styles (bold, underline, reverse) through position attributes and an underlined glyph set.
- 2026-10-19 M1: the assembly VM, cross-checked against the Python VM; the demo cartridge.
- 2026-10-19 M1: semantic pass, opcodes, code generation and linking, Python reference VM.
- 2026-10-19 M1 begun: the TXA lexer and parser (`tools/txc/`), 31-check test.
- 2026-10-19 M0: repository, kernel ported (VDP, F18A, SAMS, keyboard),
  80-column text layer, RLE picture decoder, SAMS page counting, the
  probe, cartridge loader, build (EA5 + disk image + cartridge),
  simulator extended for T80 and the bitmap layer, 25-check test.
