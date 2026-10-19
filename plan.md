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

**M2 is complete** apart from Rebecca's js99er check and timing, and
two follow-ups: command history (FCTN E/X) and a 160-character, two-row
input line (now: what fits on the row after the prompt).

## Next

1. Rebecca's js99er (and console) check of txa-m2demo8.bin, and timing.
2. Engine speed work if the timing says so: a faster fetch/dispatch
   path and cheaper story-memory access.
3. M3: the world model and full standard library (light, doors,
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
