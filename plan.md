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
to a normal title screen (Q).  **M0 passes in js99er.**  Not yet run on
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

More language details settled (for Rebecca's review):
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

More language additions (for Rebecca's review):
- built-in functions with reserved names: PARENT, CHILD, SIBLING,
  RANDOM, READKEY, SAVE, RESTORE, UNDOSAVE, UNDO, QUIT, RESTART, STATUS,
  SOUND (save/undo are placeholders returning 0 until M4);
- -32768 may be written (only with the minus sign).

A real bug found by the tests and fixed: a second press of the same
key at a second [MORE] was ignored, because nothing scans the keyboard
between waits.  Each wait now forgets the last key.

SAMS layout change from the spec: pages 28-31 hold a pristine copy of
the dynamic area for RESTART, so the undo ring is pages 16-27 (48K).

M1 remaining: bold and underline glyph sets (STYLE), and Rebecca's
js99er check of the demo cartridge.

## Next: M2 (the parser)

Tokenizer, dictionary lookup, grammar tables in the image, noun
resolution, disambiguation, orders, AGAIN/OOPS; READ becomes real.

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

## History

- 2026-10-19 M1: the assembly VM, cross-checked against the Python VM; the demo cartridge.
- 2026-10-19 M1: semantic pass, opcodes, code generation and linking, Python reference VM.
- 2026-10-19 M1 begun: the TXA lexer and parser (`tools/txc/`), 31-check test.
- 2026-10-19 M0: repository, kernel ported (VDP, F18A, SAMS, keyboard),
  80-column text layer, RLE picture decoder, SAMS page counting, the
  probe, cartridge loader, build (EA5 + disk image + cartridge),
  simulator extended for T80 and the bitmap layer, 25-check test.
