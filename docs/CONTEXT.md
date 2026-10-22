# TXA: context for a new session

Read this first. `plan.md` has status, open decisions and history; the
specification is the Claude Doc
https://claude.ai/code/artifact/43a54522-f42d-42ed-b2c7-bf348e97a95d
(container id `43a54522-f42d-42ed-b2c7-bf348e97a95d`, root node
`5fb8447c-6c85`).  The Authoring Language Reference is the Claude Doc
https://claude.ai/artifact/FdxcHQseUMuCM6etTi4BzW (doc id
`7688fc9f-8239-4683-9bc0-3fa3dc6e24f7`, body node `c67c40d5-298f`):
keep it current when the language changes.  The six manuals still to
write are stubbed in the Claude Doc
https://claude.ai/artifact/VqqmmXaB3E5RBxdTcfBtU2 (one tab each).

**State (22 October 2026, checkpoint-m5c):** M5 parts 1-4 done: the
workbench loads every file, lexes, parses and does sema.py's whole
meaning stage, identical to Python on the corpus.  Next: part 5, code.
Earlier: **(checkpoint-m4):** M0-M4 complete (engine 1.0
beta: save, restore, undo, scrollback, pictures, sound and music, stories
on disk and the game writer, title page, end screen).  Next: M5, the
native compiler on the TI; its design (decisions D1-D4 for Rebecca) is
the Claude Doc https://claude.ai/artifact/UZ6z6yM1ZeuFV9V4cja64D.  The sample game is
`samples/lamplight.txa`; Rebecca tests it from `LAMPLIGHT-TESTING.md`.

## What it is

An Infocom-style text adventure system for the TI-99/4A (F18A or
PICO9918, SAMS 512K+, disk): a runtime engine, a native workbench that
compiles games on the TI, an authoring language (working name TXA,
Inform's model with block syntax, proposed), and a Python
cross-compiler kept byte-identical as the reference. Rebecca designs and
owns it; Claude builds it. The engine comes first; the story later.

## Where things are

| What | Where |
| --- | --- |
| Repository | `/home/claude/txa` (restore below) |
| Assembler | xdt99 at `/home/claude/xdt99` (commit a77bd31); `git clone https://github.com/endlos99/xdt99` |
| Kernel origin | The Lantern Coast 1.13 (`TheLanternCoast-1_13.bundle`, Rebecca's upload) |
| Build | `python3 tools/build.py` |
| Tests | see "Restoring in a new session" (each prints PASS/FAIL lines and ALL PASS) |
| Outputs | `/mnt/user-data/outputs/txa/` (latest checkpoint: `checkpoint-m4b/`) |
| Library | `lib/`: stdlib.txa (Main), libdefs.txa, parser.txa, verbs.txa, verbs2.txa, turn.txa |
| A game for the TI | `python3 tools/txa_game.py story.txa --prefix NAME [--title T] [--cart]` |

## Source map

| File | Contents |
| --- | --- |
| `src/defs.a99` | every address and layout constant (CPU memory map, VRAM layout, variables) |
| `src/macros.a99` | `.enter`/`.leave` return stack (R10), from Lantern |
| `src/vdp.a99`, `src/keys.a99` | from Lantern unchanged except comments |
| `src/f18a.a99` | Lantern's unlock/detect/palette + status reads, register lists, F18RST |
| `src/pager.a99` | SAMS: detect, identity map, MAPPG, AMSSIZ (counts pages), AMSOFF |
| `src/text80.a99` | 80-column text: mode, font + reverse set, strings, numbers, scrolling |
| `src/rle.a99` | the picture run-length decoder (format in `tools/rlepack.py`) |
| `src/probe.a99` | M0's probe program |
| `src/engine.a99` | the engine: boot, story load into SAMS, checksum, pristine copy, errors, end |
| `src/vm.a99` | VM dispatch (OPTAB) and every opcode handler |
| `src/vmmem.a99` | story memory through SAMS windows A (code), B (data), D (text) |
| `src/output.a99` | CHOUT (the only text path; tests watch it), wrap, scroll, [MORE], strings, numbers |
| `src/txaeng.a99` | the engine build file (engine >A000 must end below >D000) |
| `tools/txc/` | the TXA compiler: lexer, ast, parser, sema, opcodes (THE instruction set), codegen (+linker), txvm (Python reference VM) |
| `tests/txa/` | test programs and `lib/stdlib.txa`, a stand-in standard library |
| `src/fast.a99` | the scratchpad block (copied to >8320 at START): NEXT, FB, FW, RDW, WRW, RDB, WRB |
| `tests/bench_engine.py` | instruction counts and time estimates per command (appends to build/bench.txt) |
| `src/input.a99` | line editor (two rows, 160 chars, FCTN E/X history in SAMS page 27, KEYFRE), KEYGT2, READ, TOKENIZE (+LOOKUP), ALOADV/ASTOREV/HASATTRV/FRESH, ISNAME, FILTERN, ACOPY |
| `src/undo.a99` | UNDOSAVE/UNDO: LAST in SAMS pages 16-19, XOR/RLE records in pages 20-26; PGCOPY; UPMAP (window B base in UBBASE) |
| `src/disk.a99` | DSKCAL (PAB at >37A0, file buffer FBUF >2000) and Lantern's DSRLNK; SPRZER |
| `src/save.a99` | SAVE/RESTORE: the portable save file built in and read from VRAM; FNAME (DSK1. prefix) |
| `tools/txa_game.py` | the game writer: E/A 5 engine files, 4K story (and picture) files, disk image, optional cartridge |
| `src/picture.a99` | PICTURE: the picture area through window D into the bitmap layer; PICOFF, PICRDW (kernel window) |
| `src/wbench.a99` | the TXA Workbench cartridge (M5): the front end, the overlay switch (OVSEL), the memory and SAMS layout |
| `src/wload.a99` | resident: LOADF (one file read, lexed, parsed onto the tree), WALK (the declaration index, INCLUDEs followed), the tree reader (XB, XW, XSKIP), DMAP, and the routines both meaning overlays use |
| `src/wsymdef.a99`, `src/wsym.a99` | the meaning stage's constants, variables, error codes; and its shared routines (symbols, dictionary, heap, errors, warnings, built-ins), in the kernel window |
| `src/wsema.a99`, `src/wsema2.a99` | overlays 3 and 4: the meaning stage's two halves |
| `tests/m5_sema_test.py` | the meaning stage against sema.py (decls, meaning, errors) |
| `tools/fixjumps.py` | rewrites jumps xas99 reports out of range as branches |
| `src/wlex.a99` | the workbench's lexer: SAMS source to SAMS tokens, identical to lexer.py |
| `tests/m5_lex_test.py` | the TI lexer against the Python lexer on the corpus (args: lib, samples, tests, errors) |
| `src/wparse.a99` | the workbench's parser: SAMS tokens to the SAMS tree, identical to parser.py (dump.tree_bytes) |
| `tests/m5_parse_test.py` | the TI parser against the Python parser on the corpus (args: small, lib, samples, tests, errors) |
| `src/diskrec.a99` | DIS/VAR record files (DVOPEN, DVREAD, DVCLOS) for the workbench |
| `tools/txa_srcdisk.py` | a game's source and the library as DIS/VAR 80 files on a TI disk image, for the workbench |
| `tools/txa_wrap.py` | TXA source to 80 columns (D1 continuation), for DV80 files |
| `tools/txc/dump.py` | canonical dumps of the compiler's stages (tokens so far), for M5's comparisons |
| `tests/m5_load_test.py`, `tests/txc_wrap_test.py` | the workbench reading DV80 source; D1 wrapping compiles to identical images |
| `src/startup.a99` | START and everything run once before the story (loaders, CHKST, FATAL); assembled at VSTK with the font |
| `tests/m4_scrollback_test.py` | the scrollback viewer and the screen restored after it |
| `src/sound.a99` | MUSIC/SOUND and the frame-ticked player (kernel window; its own workspace >83E0) |
| `tools/txsound.py` | the sound notation, its compiler, the sound area, the reference Player, WAV previews |
| `samples/sounds/` | Lamplight's tunes and effects (.mml) |
| `tests/m4_sound_test.py` | the TI player against the reference player, byte for byte |
| `tools/txpics.py` | PNG to the TI picture formats; the picture area; read_area() the reference reader |
| `samples/pics/` | Lamplight's pictures and mkart.py, which draws them |
| `tests/m4_picture_test.py` | pictures on the engine: pixels, palette, format, place, SAVE/RESTORE/UNDO |
| `samples/lamplight.txa` | the sample game, its walkthrough (.walk) and reviewed transcript (.expected) |
| `tests/m4_save_test.py`, `tests/m4_disk_test.py` | SAVE/RESTORE cross-checks (identical save files from both VMs); the game writer and loading from disk |
| `demos/m1demo.txa`, `demos/m2demo.txa` | the demonstration stories |
| `lib/` | the standard library in TXA: stdlib (Main), libdefs, parser, verbs, turn (end of turn, daemons, timers, scoring, status) |
| `samples/lamplight.txa` | "Lamplight", the sample game, with its walkthrough (.walk) and reviewed transcript (.expected) |
| `tests/txa/m3/` | the M3 test worlds, each with .cmds and a reviewed .expected |
| `tests/txa/m2/` | the parser test world, its 45 commands and the reviewed reference transcript |
| `src/txaprobe.a99` | the M0 build file: probe at >A000, kernel at >2000 (KENTRY first) |
| `src/cartldr.a99` | cartridge loader: copies the E/A 5 image into RAM |
| `tools/build.py` | generators, assembly, disk image, cartridge, memory-map checks; `engine_cart(image)` builds an engine cartridge carrying a story; `symbols()` reads xas99 -E output |
| `tools/mkfont.py`, `tools/mkpics.py`, `tools/rlepack.py` | font, test pictures, RLE |
| `tools/sim9900.py`, `tools/render.py` | the skill's simulator (1M SAMS, reset state extended) |
| `tools/render80.py` | T80 and bitmap-layer screen dumps and PNGs |

## Restoring in a new session

1. Ask Rebecca to upload `txa-checkpoint-m4b.bundle` (or `txa-latest.bundle`).
2. `cd /home/claude && git clone <bundle> txa`
3. `git clone https://github.com/endlos99/xdt99` next to it (tested at commit a77bd31).
4. `cd txa && python3 tools/build.py` and run the tests (each ends ALL PASS):
   `tests/m0_test.py`, `txc_parse_test.py`, `txc_sema_test.py`,
   `txc_run_test.py`, `m2_parser_test.py`, `m3_world_test.py`,
   `sample_test.py --quick`; the slow engine ones, `m1_vm_test.py`,
   `m2_engine_test.py`, `m3_engine_test.py`, `sample_test.py`,
   `m4_save_test.py`, `m4_disk_test.py`, `m4_picture_test.py`, `m4_quit_test.py`,
   `m4_sound_test.py`, `m4_scrollback_test.py`, `m5_load_test.py`,
   `m5_lex_test.py all`, `m5_parse_test.py all`, `m5_sema_test.py all`
   (the longest: about 25 minutes), run
   1-4 minutes each.  Quick: `txc_wrap_test.py`.  Start each
   in the background with output to a file and collect it in a later
   call: the tool stops any command after 300 s, and kills what a plain
  `nohup ... &` started when the call ends: start it with `setsid nohup`.  Run them one after
   another, never two at once, and never build anything while they run
   (they share build/ and src/gen/).
5. Read `plan.md` (status, decisions, next) and the spec Claude Doc.

## Conventions

- Inline source comments are canonical (Rebecca's rule from Press 2.0):
  explain each routine's contract, registers used, and anything unusual.
- Every generated file says so and is rebuilt by `build.py`; never edit `src/gen/`.
- Report audit findings before changing working code.
- Rebecca reports from js99er in short messages: reproduce before fixing,
  and never claim a fix that was only reasoned.

## Things learned the hard way

- The kernel's KEYGET returns the character in the HIGH byte (ENTER is
  >0D00) and ignores FCTN; the engine's KEYGT2 (input.a99) is the one
  with FCTN keys and a low-byte code.
- A routine that reports through the status flags must not end with
  .leave (its MOV spoils them): keep R11 in memory and make the compare
  the last instruction before B *R11 (CMP1/CMP2 in wparse.a99).
- MAPPG uses R0-R3 and R12: any routine that may cross a SAMS page in
  the middle of a caller's loop must keep R2/R3 itself (TPUT once didn't).
- The simulator harness presses SHIFT for capitals; the kernel's KEYGET
  stops at SHIFT, so type file names in lower case in workbench tests.
- The TI number printer TXDEC takes the number in R0 (R1 width, R2 style).
- xas99 has NO operator precedence: expressions go left to right, so
  VOICES+4*VSIZE means (VOICES+4)*VSIZE.  Parenthesise every mixed
  expression.
- The startup segment (startup.a99 and the font) lives at VSTK (>3000):
  run or read only before the story, then overwritten by the value stack.
  Nothing there may be called once VMRUN has run; START must end with an
  explicit branch (falling through into whatever follows was a bug).
- Before BLWP @>0000, clear the scratchpad from >8320: the console's
  power-up enables interrupts before clearing >83C4 (user hook) and
  >83CE (sound count); the fast block left there hung js99er.  The
  simulator's reset model clears it itself, so test scratch_at_reset.
- The resident engine (>A000-CFFF) is nearly full: new code goes in the
  kernel window (>2000-2FFD) when it fits (picture.a99 did).
- Background chains of several engine suites die partway: run the slow
  suites one per call (each under 300 s).
- RAM variables: build.py refuses to build if two in defs.a99 overlap;
  a variable's size is the "N bytes" (or "N words") in its comment, so
  every buffer must say its size.  It has caught four real overlaps.
- Anything that maps SAMS windows A or B itself (UPMAP, PGCOPY, MAPWIN)
  must SETO CURBH (UNDONE does) before RDW/WRW/GLOAD are used again:
  RESTORE once reloaded the globals through a stale window B.
- KEYGT2 reports a key only when it differs from the last one seen, and
  nothing scans while the game is busy: KEYFRE at the start of each line
  forgets the last key if none is down (a second ENTER was being lost).
- In TXA, 'x' is a dictionary word, not a character: character codes are
  numbers (the library's default save name is 115, 97, 118, 101, 49).
- Cost per command matters: the UNDO snapshot once took about 2 s a
  command (byte at a time); measure with sample_test's estimate after
  any change to the per-command path.

- xas99 reads commas and parentheses in a DATA line's comment as
  operands, and a comment starting with "..." as an expression: keep
  such comments plain.
- R0 cannot be an index register: copy to R1 first.
- VSBW changes R0 (it sets the write bit).
- Scratch words: VT1-VT5 belong to the VM's helpers (PROPF uses VT1-4,
  ARRAY/TREE/ATTRB/SHORTN keep their link in VT5); CHOUT uses CHCHR and
  CHBRK; CHSTR and PRNUM use TMP1-2; PUTPROP keeps the kind in TMP3.
  DETACH, OBJE, RDW and WRW leave R15 alone.
- KEYGET reports a key only when it differs from the last; nothing scans
  between [MORE] waits, so WAITKY clears KEYLST first.
- Simulator harnesses must offer key presses inside the polling loops
  (WK21, WKY1), not at a routine's entry.
- Never build cartridges while engine tests run in the background: they
  share build/ and the generated files.
- TXA names ignore case: a routine IsName collides with the built-in
  ISNAME, a parameter "room" with the keyword ROOM.

- The scratchpad block must end below >83E0 (build.py checks; it ends
  at >83DD with almost no room left).  DSRLNK (M4) uses >8354->8370 and
  >83E0 on: copy the block back after every disk call.
- Globals live in RAM (GLOBRM) while the story runs: GSYNC before
  anything copies the dynamic area, GLOAD after.
- xas99 reads a comment on a bare label line, or after an AORG with no
  operand, as code: put such comments on their own lines.

## Hardware facts learned (with sources in the spec)

- F18A T80: VR0 >04 + VR1 text bit; name table on any 1K boundary when
  unlocked (4K while locked); 30 rows with VR49 >40, name table 2400 bytes.
- Bitmap layer: 2 bpp or 4 bpp fat pixels, on the 256-pixel grid even in
  80 columns; width register 0 = 256, height 0 = no rows; must end below
  >4000 or the F18A wraps. RP2040 PICO9918s have no bitmap layer in T80.
- In 30-row mode the >D0 sprite terminator is disabled: TXA keeps the
  sprite patterns blank instead.
- 30-row mode survives a console reset: F18RST turns it off before quitting.
- The workbench's overlays must not refer to each other's labels: the
  assembler accepts it, but the other overlay is not mapped in.  Shared
  code goes in wload.a99 (resident) or wsym.a99 (kernel window, nearly
  full: about 200 bytes left).
- EQUs cannot refer forward in xas99: the meaning stage's are in
  wsymdef.a99, COPYed at the top of wbench.a99.
- The meaning stage's routines document which registers they use;
  SLOOK, SLOOKK, SADD, DWORD and DADD use R0-R7, so loop counters across
  them live in R8, R9 or memory.
