# TXA: context for a new session

Read this first. `plan.md` has status, open decisions and history; the
specification is the Claude Doc
https://claude.ai/code/artifact/43a54522-f42d-42ed-b2c7-bf348e97a95d
(container id `43a54522-f42d-42ed-b2c7-bf348e97a95d`, root node
`5fb8447c-6c85`).

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
| Repository | `/home/claude/txa` (restore: `git clone txa-latest.bundle txa`) |
| Assembler | xdt99 at `/home/claude/xdt99` (commit a77bd31); `git clone https://github.com/endlos99/xdt99` |
| Kernel origin | The Lantern Coast 1.13 (`TheLanternCoast-1_13.bundle`, Rebecca's upload) |
| Build | `python3 tools/build.py` |
| Tests | `tests/m0_test.py`, `txc_parse_test.py`, `txc_sema_test.py`, `txc_run_test.py`, `m1_vm_test.py` (each prints PASS/FAIL lines and ALL PASS) |
| Outputs | `/mnt/user-data/outputs/txa/` |

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
| `demos/m1demo.txa` | the M1 demonstration story |
| `src/txaprobe.a99` | the M0 build file: probe at >A000, kernel at >2000 (KENTRY first) |
| `src/cartldr.a99` | cartridge loader: copies the E/A 5 image into RAM |
| `tools/build.py` | generators, assembly, disk image, cartridge, memory-map checks; `engine_cart(image)` builds an engine cartridge carrying a story; `symbols()` reads xas99 -E output |
| `tools/mkfont.py`, `tools/mkpics.py`, `tools/rlepack.py` | font, test pictures, RLE |
| `tools/sim9900.py`, `tools/render.py` | the skill's simulator (1M SAMS, reset state extended) |
| `tools/render80.py` | T80 and bitmap-layer screen dumps and PNGs |

## Conventions

- Inline source comments are canonical (Rebecca's rule from Press 2.0):
  explain each routine's contract, registers used, and anything unusual.
- Every generated file says so and is rebuilt by `build.py`; never edit `src/gen/`.
- Report audit findings before changing working code.
- Rebecca reports from js99er in short messages: reproduce before fixing,
  and never claim a fix that was only reasoned.

## Hardware facts learned (with sources in the spec)

- F18A T80: VR0 >04 + VR1 text bit; name table on any 1K boundary when
  unlocked (4K while locked); 30 rows with VR49 >40, name table 2400 bytes.
- Bitmap layer: 2 bpp or 4 bpp fat pixels, on the 256-pixel grid even in
  80 columns; width register 0 = 256, height 0 = no rows; must end below
  >4000 or the F18A wraps. RP2040 PICO9918s have no bitmap layer in T80.
- In 30-row mode the >D0 sprite terminator is disabled: TXA keeps the
  sprite patterns blank instead.
- 30-row mode survives a console reset: F18RST turns it off before quitting.
