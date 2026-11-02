#!/usr/bin/env python3
"""A testing simulator: enough TMS9900 + TI-99/4A + SAMS + F18A to boot a
cartridge image, run it, press keys, and read or render the screen.  From
The Lantern Coast (MIT License, (c) 2026 Rebecca Sutter), where it carried
27 play-through tests.

Not a full emulator.  It models:
  - the TMS9900 instruction subset the kernel uses (asserts on others)
  - 16-bit RAM, scratchpad, cart ROM with 378 bank switching
  - AMS mapper: CRU >1E00 bits 0/1, registers at >4000, 128 pages x 4K (512K)
  - VDP: address/data ports, 8 (or 64 on F18A) registers, 16K VRAM,
    status bit 7 raised every VSYNC_INSNS instructions
  - F18A: VR57 unlock, VR15 status select (SR1 returns >E0), VR47 palette
  - GROM: read-only, font bytes at >06B4 are nonzero so glyphs show
  - keyboard: no key until KEY_AT, then 'Q' held for a while

Usage: sim9900.py cart8.bin [--no-f18a] [--pages N] [--insns N]
"""
import os, sys

VSYNC_INSNS = 3000
KEY_AT = 200_000       # first scripted key goes down at this instruction count
KEY_PERIOD = 60_000    # one key every this many instructions
KEY_HOLD = 30_000      # held for this long
KTAB = ["= \r\0\0\0\0\0", ".LO92SWX", ",KI83DEC", "MJU74FRV", "NHY65GTB", "/;P01AQZ"]

def key_pos(ch):
    if ch == '=': ch = '\r'                 # '=' on the command line means Enter
    for c, col in enumerate(KTAB):
        if ch in col:
            return c, col.index(ch)
    raise SystemExit(f"no key {ch!r}")

class Halt(Exception):
    pass

class Machine:
    def __init__(self, cart, f18a=True, pages=128):
        self.cart = cart
        self.nbanks = len(cart) // 0x2000
        self.bank = 0
        self.scratch = bytearray(256)
        self.ams = bytearray(4096 * max(128, pages))   # TXA: room for a 1M card
        if os.environ.get('SIM_RANDOM_RAM'):              # as at a real power-up: RAM is not zeroed
            import random as _r
            _g = _r.Random(int(os.environ['SIM_RANDOM_RAM']))
            self.ams[:] = bytes(_g.randrange(256) for _ in range(len(self.ams)))
            self.scratch[:] = bytes(_g.randrange(256) for _ in range(256))   # the scratchpad too: a console leaves its own values there
        self.pages = pages           # physical pages actually present
        self.map = list(range(16))   # window -> page
        self.ams_regs_visible = False
        self.ams_mapping = False
        self.f18a = f18a
        self.vram = bytearray(16384)
        self.vregs = [0] * 64
        self.vaddr = 0
        self.vlatch = None
        self.vstatus = 0
        self.unlock = 0
        self.unlocked = False
        self.palette = {}
        self.pal_mode = None
        self.grom_addr = 0
        self.grom_latch = None
        self.grom = bytearray(0x2000)
        try:                                   # a readable stand-in for the console font
            from simfont import FONT
            for n, rows in enumerate(FONT):
                for y, b in enumerate(rows):
                    self.grom[0x6B4 + n * 7 + y] = b
        except ImportError:
            for i in range(0x6B4, 0x6B4 + 64 * 7):
                self.grom[i] = 0x7E if (i - 0x6B4) % 7 else 0x3C
        self.insns = 0
        self.keys = []          # list of (col,row) scripted presses
        self.held = None        # (col,row) held directly by a driver script
        self.vint = False       # VDP interrupt pending (level-triggered until serviced)
        self.blanked = False    # set if the console ISR ever blanked the screen
        self.sound_log = []     # bytes written to the sound chip by the ISR's list player
        self.cpu_sound = []     # bytes the game itself writes to the sound chip (effects)
        self.chip_log = []      # both, in order: (source, instruction count, byte)
        # a fake disk controller DSR at CRU >1100: ROM header, a DSR list
        # entries "DSK1" and "DSK2" whose code is the trap opcode >0180, and a
        # no-op power-up routine.  File I/O goes to disk_dir/DSKn/<name>.
        self.dsr_on = False
        self.disk_dir = None
        self.tifdc = None       # a tools/tifdc.TIFDC: the real TI controller's DSR in place of the stand-in
        rom = bytearray(0x2000)
        rom[0:4] = b'\xAA\x01\x00\x00'
        rom[4:6] = (0x4020).to_bytes(2, 'big'); rom[8:10] = (0x4010).to_bytes(2, 'big')
        rom[0x10:0x12] = (0x4060).to_bytes(2, 'big'); rom[0x12:0x14] = (0x4030).to_bytes(2, 'big'); rom[0x14:0x19] = b'\x04DSK1'
        rom[0x60:0x62] = b'\x00\x00'; rom[0x62:0x64] = (0x4030).to_bytes(2, 'big'); rom[0x64:0x69] = b'\x04DSK2'   # (disk_dir/DSK2: the options' library tests)
        rom[0x20:0x22] = b'\x00\x00'; rom[0x22:0x24] = (0x4040).to_bytes(2, 'big'); rom[0x24] = 0
        for i, w in enumerate((0x0180, 0x1302, 0x05CB, 0x045B, 0x045B)):
            rom[0x30 + 2 * i: 0x32 + 2 * i] = w.to_bytes(2, 'big')
        # the power-up routine: a trap too (pc >4040), then RT.  As on a real
        # controller, power-up resets the controller's buffers: open files are
        # forgotten (READ or CLOSE on one then fails with error 7).
        rom[0x40:0x42] = (0x0180).to_bytes(2, 'big'); rom[0x42:0x44] = (0x045B).to_bytes(2, 'big')
        self.dsrrom = rom

    # ---- memory ------------------------------------------------------
    def page_of(self, addr):
        w = addr >> 12
        p = self.map[w] if self.ams_mapping else w
        return p % self.pages

    def rb(self, addr):
        addr &= 0xFFFF
        if addr < 0x2000:
            return 0
        if addr < 0x4000 or addr >= 0xA000:
            return self.ams[self.page_of(addr) * 4096 + (addr & 0xFFF)]
        if addr < 0x6000:
            if self.ams_regs_visible and addr < 0x4020:
                return self.map[(addr - 0x4000) >> 1]
            if self.tifdc is not None and self.tifdc.rom_on:
                return self.tifdc.read(addr)
            if self.dsr_on:
                return self.dsrrom[addr - 0x4000]
            return 0
        if addr < 0x8000:
            off = self.bank * 0x2000 + (addr - 0x6000)
            return self.cart[off] if off < len(self.cart) else 0
        if 0x8300 <= addr < 0x8400:
            return self.scratch[addr - 0x8300]
        if addr == 0x8800:                       # VDP read data
            v = self.vram[self.vaddr]
            self.vaddr = (self.vaddr + 1) & 0x3FFF
            return v
        if addr == 0x8802:                       # VDP status
            if self.f18a and self.unlocked and self.vregs[15] == 1:
                return 0xE0
            s = self.vstatus
            self.vstatus = 0
            return s
        if addr == 0x9800:                       # GROM read
            v = self.grom[self.grom_addr & 0x1FFF]
            self.grom_addr = (self.grom_addr + 1) & 0xFFFF
            return v
        return 0

    def wb(self, addr, val):
        addr &= 0xFFFF
        val &= 0xFF
        if addr < 0x2000:
            return
        if addr < 0x4000 or addr >= 0xA000:
            self.ams[self.page_of(addr) * 4096 + (addr & 0xFFF)] = val
            return
        if addr < 0x6000:
            if self.ams_regs_visible and addr < 0x4020:
                self.map[(addr - 0x4000) >> 1] = val & 0xFF
            elif self.tifdc is not None and self.tifdc.rom_on:
                self.tifdc.write(addr, val)
            return
        if addr < 0x8000:
            b = (addr - 0x6000) >> 1
            if b < self.nbanks:
                self.bank = b
            return
        if 0x8300 <= addr < 0x8400:
            self.scratch[addr - 0x8300] = val
            return
        if addr == 0x8C00:                       # VDP write data
            if self.pal_mode is not None:
                idx, hi = self.pal_mode
                if hi is None:
                    self.pal_mode = (idx, val)
                else:
                    self.palette[idx] = (hi << 8) | val
                    self.pal_mode = (idx + 1, None)
                return
            self.vram[self.vaddr] = val
            self.vaddr = (self.vaddr + 1) & 0x3FFF
            self.vlatch = None
            return
        if addr == 0x8C02:                       # VDP address / register
            if self.vlatch is None:
                self.vlatch = val
                return
            lo, hi = self.vlatch, val
            self.vlatch = None
            if hi & 0x80:
                reg = hi & 0x3F if (self.f18a and self.unlocked) else hi & 0x07
                if self.f18a and (hi & 0x3F) == 57:
                    # as js99er's F18A (and the real one): locked, two writes in a
                    # row with >1C set unlock it; unlocked, ANY write to VR57 locks
                    # it again (an unlock sequence sent to an unlocked F18A locks it)
                    if not self.unlocked:
                        old = self.vregs[57]
                        self.vregs[57] = lo
                        if (old & 0x1C) == 0x1C and (lo & 0x1C) == 0x1C:
                            self.unlocked = True
                    else:
                        self.vregs[57] = 0
                        self.unlocked = False
                    return
                self.vregs[reg] = lo
                if reg == 47 and self.f18a and self.unlocked:
                    self.pal_mode = ((lo & 0x3F), None) if lo & 0x80 else None
            else:
                self.vaddr = ((hi & 0x3F) << 8) | lo
            return
        if addr == 0x9C02:                       # GROM address, high first
            if self.grom_latch is None:
                self.grom_latch = val
            else:
                self.grom_addr = (self.grom_latch << 8) | val
                self.grom_latch = None
            return
        if 0x8400 <= addr < 0x8600:              # the sound chip: the CPU's own writes
            self.cpu_sound.append(val); self.chip_log.append(('cpu', self.insns, val))
            return
        # others: ignore

    def rw(self, addr):
        addr &= 0xFFFE
        if 0x2000 <= addr < 0x4000 or addr >= 0xA000:      # AMS RAM: both bytes at once
            w = addr >> 12
            i = ((self.map[w] if self.ams_mapping else w) % self.pages) * 4096 + (addr & 0xFFF)
            a = self.ams
            return (a[i] << 8) | a[i + 1]
        if 0x8300 <= addr < 0x8400:                        # scratchpad
            o = addr - 0x8300; sc = self.scratch
            return (sc[o] << 8) | sc[o + 1]
        if 0x6000 <= addr < 0x8000:                        # cartridge ROM
            off = self.bank * 0x2000 + (addr - 0x6000); c = self.cart
            return ((c[off] if off < len(c) else 0) << 8) | (c[off + 1] if off + 1 < len(c) else 0)
        return (self.rb(addr) << 8) | self.rb(addr + 1)    # ports, DSR space: byte by byte

    def ww(self, addr, val):
        addr &= 0xFFFE
        if 0x2000 <= addr < 0x4000 or addr >= 0xA000:      # AMS RAM: both bytes at once
            w = addr >> 12
            i = ((self.map[w] if self.ams_mapping else w) % self.pages) * 4096 + (addr & 0xFFF)
            a = self.ams
            a[i] = (val >> 8) & 0xFF; a[i + 1] = val & 0xFF
            return
        if 0x8300 <= addr < 0x8400:                        # scratchpad
            o = addr - 0x8300; sc = self.scratch
            sc[o] = (val >> 8) & 0xFF; sc[o + 1] = val & 0xFF
            return
        self.wb(addr, val >> 8)                            # the cartridge (bank select), ports
        self.wb(addr + 1, val & 0xFF)

    # ---- CRU ---------------------------------------------------------
    def console_isr(self, cpu):
        """What the console's level-1 routine at >0900 does that matters here,
        modelled faithfully enough to catch mistakes with it:
        - reads the VDP status (clears the flag and resets the address latch);
        - advances the timer at >8379;
        - plays the sound list at >83CC one block per frame when >83CE counts
          down to zero: from VDP RAM when bit 0 of >83FD is set (it sets the VDP
          read address to do so, which clobbers any transfer in progress), from
          GROM otherwise.  A size byte of >00 (or >FF, which also switches memory)
          is a branch: the next two bytes become the list address and nothing
          sounds until the next frame.  A duration of 0 ends the list
          (after Nouspikel, TI-99/4A Tech Pages, "Interrupts");
        - adds 2 to the screen timer at >83D6 and blanks the display (VR1 from
          the copy at >83D4, display bit cleared) when it wraps to zero."""
        self.vstatus &= 0x7F
        self.vlatch = None
        self.scratch[0x79] = (self.scratch[0x79] + 1) & 0xFF
        dur = self.scratch[0xCE]
        if dur:
            dur -= 1
            if dur == 0:
                ptr = (self.scratch[0xCC] << 8) | self.scratch[0xCD]
                in_vram = self.scratch[0xFD] & 1
                def rd(a):
                    if in_vram:
                        self.vaddr = (a + 1) & 0x3FFF       # the ISR's own VDP read
                        return self.vram[a & 0x3FFF]
                    return self.grom[a & 0x1FFF]
                n = rd(ptr); ptr += 1
                if n in (0x00, 0xFF):                    # a branch order: the next two bytes are the new
                    ptr = (rd(ptr) << 8) | rd(ptr + 1)   # address; no sounds change until the next frame
                    if n == 0xFF: self.scratch[0xFD] ^= 1       # (>FF also switches VDP <-> GROM)
                    dur = 1
                else:
                    for i in range(n):
                        b = rd(ptr); ptr += 1
                        self.sound_log.append(b); self.chip_log.append(('isr', self.insns, b))
                    dur = rd(ptr); ptr += 1              # a duration of 0 ends the list
                self.scratch[0xCC] = (ptr >> 8) & 0xFF; self.scratch[0xCD] = ptr & 0xFF
            self.scratch[0xCE] = dur
        t = ((self.scratch[0xD6] << 8) | self.scratch[0xD7]) + 2
        t &= 0xFFFF
        self.scratch[0xD6] = t >> 8; self.scratch[0xD7] = t & 0xFF
        if t == 0:
            self.vregs[1] = self.scratch[0xD4] & 0xBF
            self.blanked = True

    def cru_write(self, bit, v):
        if self.tifdc is not None and 0x880 <= bit < 0x888:
            self.tifdc.cru_write(bit - 0x880, v)
            return
        if bit == 0xF00:          # >1E00 / 2
            self.ams_regs_visible = bool(v)
        elif bit == 0xF01:
            self.ams_mapping = bool(v)
        elif bit == 0x880:        # >1100 / 2: the fake disk controller ROM
            self.dsr_on = bool(v)

    def dsr_trap(self, cpu):
        """Perform the PAB operation that the fake DSK1 DSR was called for.
        Returns True when it handled the call (the DSR then returns to R11+2),
        which may still carry an error code in the PAB's flag byte, as a missing
        file does on a real controller; False (return to R11) when the device is
        not its own."""
        # A real DSR is GPL-called code: it runs in the GPL workspace (>83E0) and
        # reaches the VDP and GROM through that workspace's R15 (>8C02) and R13
        # (>9800). Called any other way its VDP traffic goes astray: it does
        # nothing useful, yet still returns as if it had handled the call.
        if cpu.pc - 2 == 0x4040:
            self.powerups = getattr(self, 'powerups', 0) + 1   # (counted: tests/tipi_test.py)                      # the power-up routine (M6: Rebecca's js99er,
            self.__dict__['dsr_files'] = {}           # with a real controller, found the workbench's
            return True                               # DSRLNK forgetting its open file)
        if getattr(self, 'dsr_strict_ws', True) and (cpu.wp != 0x83E0 or self.rw(0x83FE) != 0x8C02 or self.rw(0x83FA) != 0x9800):
            return True
        import os
        # as a real DSR finds it: >8356 points at the '.' after the device name
        # (DSRLNK moves it there) and >8354 holds the device name's length
        pab = self.rw(0x8356) - self.rw(0x8354) - 10
        op = self.vram[pab]; buf = (self.vram[pab + 2] << 8) | self.vram[pab + 3]
        count = (self.vram[pab + 6] << 8) | self.vram[pab + 7]
        nlen = self.vram[pab + 9]
        name = bytes(self.vram[pab + 10: pab + 10 + nlen]).decode('ascii', 'replace')
        dev, _, fname = name.partition('.')
        def fail(code):
            self.vram[pab + 1] = (self.vram[pab + 1] & 0x1F) | (code << 5)
            if getattr(self, 'dsr_silent', False):          # a DSR that fails without saying so
                self.vram[pab + 1] &= 0x1F
            return False
        # a DSR may move the name pointer on while it parses the rest of the name:
        # a caller must not find the PAB through >8356 afterwards
        if getattr(self, 'dsr_moves_ptr', True):
            p = self.rw(0x8356) + 1; self.scratch[0x56] = (p >> 8) & 0xFF; self.scratch[0x57] = p & 0xFF
        if self.disk_dir is None or dev not in ('DSK1', 'DSK2'):
            return fail(0)
        path = os.path.join(self.disk_dir, dev, fname)
        if op == 6:                                   # SAVE
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = bytearray(self.vram[buf: buf + count])
            if getattr(self, 'dsr_corrupt', False) and len(data) > 20:
                data[20] ^= 0xFF; self.dsr_corrupt = False   # a test: spoil one save
            open(path, 'wb').write(bytes(data))
            return True
        if op in (0, 1, 2, 3):                        # OPEN, CLOSE, READ, WRITE: DIS/VAR files,
            files = self.__dict__.setdefault('dsr_files', {})   # kept as text, a record a line
            if op == 0:
                if (self.vram[pab + 1] & 6) == 2:     # output: a new file (M6 part 8, RECORD)
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    open(path, 'wb').write(b'')
                    files[pab] = [[], 0, path]
                    if self.vram[pab + 4] == 0:
                        self.vram[pab + 4] = 80
                    return True
                if not os.path.exists(path):
                    fail(7); return True
                files[pab] = [open(path, 'rb').read().split(b'\n'), 0, None]
                if files[pab][0] and files[pab][0][-1] == b'':
                    files[pab][0].pop()               # (a last newline ends the last record)
                if self.vram[pab + 4] == 0:
                    self.vram[pab + 4] = 80
                return True
            if op == 1:
                files.pop(pab, None); return True
            if op == 3:                               # WRITE: the record (its count at +5) appended
                f = files.get(pab)
                if f is None or f[2] is None:
                    fail(7); return True
                rec = bytes(self.vram[buf: buf + self.vram[pab + 5]])
                open(f[2], 'ab').write(rec + b'\n')
                return True
            f = files.get(pab)
            if f is None:
                fail(7); return True
            if f[1] >= len(f[0]):
                fail(5); return True                  # past the end
            rec = f[0][f[1]][:self.vram[pab + 4] or 80]; f[1] += 1
            self.vram[buf: buf + len(rec)] = rec
            self.vram[pab + 5] = len(rec)
            return True
        if op == 5:                                   # LOAD
            if not os.path.exists(path):              # as a real controller does: it handled
                fail(7)                               # the call (the skip return) and reports
                return True                           # the error in the PAB's flag byte
            data = open(path, 'rb').read()[:count]
            self.vram[buf: buf + len(data)] = data
            return True
        return fail(0)

    def cru_read(self, bit):
        if self.tifdc is not None and 0x880 <= bit < 0x888:
            return 1 if self.tifdc.cru_read(bit - 0x880) else 0
        # keyboard rows on bits 3-10; column select was written to 18-20
        if 3 <= bit <= 10:
            col = self.keycol
            row = bit - 3
            if self.held is not None:              # TXA: a set of keys may be held (FCTN + S)
                if isinstance(self.held, (set, frozenset)):
                    return 0 if (col, row) in self.held else 1
                return 0 if self.held == (col, row) else 1
            i = (self.insns - KEY_AT) // KEY_PERIOD
            if 0 <= i < len(self.keys) and (self.insns - KEY_AT) % KEY_PERIOD < KEY_HOLD:
                if self.keys[i] == (col, row):
                    return 0
            return 1
        return 1

    keycol = 0

# ---- CPU --------------------------------------------------------------
class CPU:
    def __init__(self, m):
        self.m = m
        self.wp = 0x83E0
        self.pc = 0
        self.st = 0   # bits: 15 LGT,14 AGT,13 EQ,12 C,11 OV
        self.limi = 0 # interrupt mask
        self.trace = False

    def reg(self, n): return self.m.rw(self.wp + 2 * n)
    def setreg(self, n, v): self.m.ww(self.wp + 2 * n, v & 0xFFFF)

    _FBIT = {'L': 0x8000, 'A': 0x4000, 'E': 0x2000, 'C': 0x1000, 'O': 0x0800}
    def flag(self, name, on):
        b = self._FBIT[name]
        if on: self.st |= b
        else: self.st &= ~b
    def get(self, name):
        return bool(self.st & self._FBIT[name])

    def cmp0(self, v, byte):
        mask = 0xFF if byte else 0xFFFF
        v &= mask
        sign = 0x80 if byte else 0x8000
        self.flag('L', v != 0)
        self.flag('A', v != 0 and not (v & sign))
        self.flag('E', v == 0)

    def cmp(self, a, b, byte):
        mask = 0xFF if byte else 0xFFFF
        a &= mask; b &= mask
        bits = 8 if byte else 16
        sa = a - (1 << bits) if a >> (bits - 1) else a
        sb = b - (1 << bits) if b >> (bits - 1) else b
        self.flag('L', a > b)
        self.flag('A', sa > sb)
        self.flag('E', a == b)

    def fetch(self):
        v = self.m.rw(self.pc)
        self.pc = (self.pc + 2) & 0xFFFF
        return v

    # returns address for Ts/S, handling autoinc; register mode returns ('r', n)
    def ea(self, mode, n, byte):
        if mode == 0:
            return ('r', n)
        if mode == 1:
            return ('m', self.reg(n))
        if mode == 2:
            off = self.fetch()
            if n:
                return ('m', (off + self.reg(n)) & 0xFFFF)
            return ('m', off)
        a = self.reg(n)
        self.setreg(n, a + (1 if byte else 2))
        return ('m', a)

    def load(self, ea, byte):
        k, a = ea
        if k == 'r':
            v = self.reg(a)
            return (v >> 8) if byte else v
        return self.m.rb(a) if byte else self.m.rw(a)

    def store(self, ea, v, byte):
        k, a = ea
        if k == 'r':
            if byte:
                self.setreg(a, (v << 8) | (self.reg(a) & 0xFF))
            else:
                self.setreg(a, v)
        else:
            if byte: self.m.wb(a, v)
            else: self.m.ww(a, v)

    def step(self):
        m = self.m
        m.insns += 1
        if m.insns % VSYNC_INSNS == 0:
            m.vstatus |= 0x80
            if m.vregs[1] & 0x20: m.vint = True
        if m.vint and self.limi >= 1:
            m.vint = False
            m.console_isr(self)
        op = self.fetch()
        pc0 = self.pc - 2
        if self.trace:
            print(f"{pc0:04X} {op:04X} R0={self.reg(0):04X} R1={self.reg(1):04X} R5={self.reg(5):04X}")
        if op == 0x0180:                       # simulator trap: fake DSR
            self.flag('E', not m.dsr_trap(self))
            return
        top = op >> 12
        # ---- dual operand: A AB C CB S SB SOC SOCB SZC SZCB MOV MOVB
        if top >= 0x4:
            byte = bool(op & 0x1000)
            ts, s = (op >> 4) & 3, op & 0xF
            td, d = (op >> 10) & 3, (op >> 6) & 0xF
            sea = self.ea(ts, s, byte)
            sv = self.load(sea, byte)
            dea = self.ea(td, d, byte)
            code = top & 0xE
            if code == 0xC:      # MOV
                self.store(dea, sv, byte); self.cmp0(sv, byte)
            elif code == 0x8:    # C
                self.cmp(sv, self.load(dea, byte), byte)
            elif code == 0xA:    # A
                dv = self.load(dea, byte)
                r = sv + dv
                mask = 0xFF if byte else 0xFFFF
                sign = 0x80 if byte else 0x8000
                self.flag('C', r > mask)
                r &= mask
                self.flag('O', bool((sv & sign) == (dv & sign) and (r & sign) != (sv & sign)))
                self.store(dea, r, byte); self.cmp0(r, byte)
            elif code == 0x6:    # S
                dv = self.load(dea, byte)
                mask = 0xFF if byte else 0xFFFF
                sign = 0x80 if byte else 0x8000
                r = dv + ((~sv) & mask) + 1
                self.flag('C', r > mask)
                r &= mask
                self.flag('O', bool((sv & sign) != (dv & sign) and (r & sign) != (dv & sign)))
                self.store(dea, r, byte); self.cmp0(r, byte)
            elif code == 0xE:    # SOC
                r = self.load(dea, byte) | sv
                self.store(dea, r, byte); self.cmp0(r, byte)
            elif code == 0x4:    # SZC
                r = self.load(dea, byte) & ~sv
                self.store(dea, r, byte); self.cmp0(r, byte)
            else:
                raise Halt(f"unimplemented dual op {op:04X} at {pc0:04X}")
            return
        # ---- XOP/XOR/MPY/DIV/COC/CZC: 0x2xxx
        if top == 0x2:
            sub = (op >> 10) & 3
            ts, s = (op >> 4) & 3, op & 0xF
            d = (op >> 6) & 0xF
            sea = self.ea(ts, s, False)
            sv = self.load(sea, False)
            if sub == 2:        # XOR
                r = self.reg(d) ^ sv
                self.setreg(d, r); self.cmp0(r, False)
            elif sub == 0:      # COC
                self.flag('E', (self.reg(d) & sv) == sv)
            elif sub == 1:      # CZC
                self.flag('E', (self.reg(d) & sv) == 0)
            else:
                raise Halt(f"unimplemented 2xxx op {op:04X} at {pc0:04X}")
            return
        if top == 0x3:
            sub = (op >> 10) & 3
            ts, s = (op >> 4) & 3, op & 0xF
            d = (op >> 6) & 0xF
            if sub == 2:        # MPY
                sea = self.ea(ts, s, False)
                r = self.reg(d) * self.load(sea, False)
                self.setreg(d, r >> 16); self.setreg(d + 1, r & 0xFFFF)
            elif sub == 3:      # DIV
                sea = self.ea(ts, s, False)
                sv = self.load(sea, False)
                dividend = (self.reg(d) << 16) | self.reg(d + 1)
                if sv == 0 or self.reg(d) >= sv:
                    self.flag('O', True)
                else:
                    self.flag('O', False)
                    self.setreg(d, dividend // sv); self.setreg(d + 1, dividend % sv)
            elif sub == 0:      # LDCR
                cnt = d or 16
                sea = self.ea(ts, s, cnt <= 8)
                v = self.load(sea, cnt <= 8)
                base = (self.reg(12) >> 1) & 0xFFF
                for i in range(cnt):
                    bit = (v >> i) & 1
                    b = base + i
                    if b in (18, 19, 20):
                        m.keycol = (m.keycol & ~(1 << (b - 18))) | (bit << (b - 18))
                    else:
                        m.cru_write(b, bit)
            elif sub == 1:      # STCR
                cnt = d or 16
                sea = self.ea(ts, s, cnt <= 8)
                base = (self.reg(12) >> 1) & 0xFFF
                v = 0
                for i in range(cnt):
                    v |= m.cru_read(base + i) << i
                if cnt <= 8:
                    old = self.load(sea, True)
                    v |= old & ~((1 << cnt) - 1) & 0xFF
                self.store(sea, v, cnt <= 8)
            return
        # ---- jumps and CRU single bit: 0x1xxx
        if top == 0x1:
            kind = (op >> 8) & 0xF
            disp = op & 0xFF
            if disp >= 0x80: disp -= 0x100
            if kind <= 0xC:
                if kind == 0xC:
                    raise Halt(f"unimplemented op {op:04X}")
                st = self.st                     # only the condition this jump tests
                L = st & 0x8000; A = st & 0x4000; E = st & 0x2000
                if kind == 0: cond = True
                elif kind == 1: cond = not A and not E
                elif kind == 2: cond = not L or E
                elif kind == 3: cond = E
                elif kind == 4: cond = L or E
                elif kind == 5: cond = A
                elif kind == 6: cond = not E
                elif kind == 7: cond = not (st & 0x1000)
                elif kind == 8: cond = st & 0x1000
                elif kind == 9: cond = not (st & 0x0800)
                elif kind == 0xA: cond = not L and not E
                else: cond = L and not E
                if cond:
                    self.pc = (self.pc + 2 * disp) & 0xFFFF
                return
            base = (self.reg(12) >> 1) & 0xFFF
            b = (base + disp) & 0xFFF
            if kind == 0xD: m.cru_write(b, 1)
            elif kind == 0xE: m.cru_write(b, 0)
            else: self.flag('E', bool(m.cru_read(b)))
            return
        # ---- shifts: 0x0Axx
        if 0x08 <= (op >> 8) <= 0x0B:
            kind = (op >> 8) & 3
            r = op & 0xF
            cnt = (op >> 4) & 0xF
            if cnt == 0:
                cnt = self.reg(0) & 0xF or 16
            v = self.reg(r)
            c = 0
            for _ in range(cnt):
                if kind == 0:   # SRA
                    c = v & 1; v = (v >> 1) | (v & 0x8000)
                elif kind == 1: # SRL
                    c = v & 1; v >>= 1
                elif kind == 2: # SLA
                    c = v >> 15; v = (v << 1) & 0xFFFF
                else:           # SRC
                    c = v & 1; v = (v >> 1) | (c << 15)
            self.setreg(r, v); self.cmp0(v, False); self.flag('C', bool(c))
            return
        # ---- immediates: 0x02xx
        if op >> 8 == 0x02 or op >> 8 == 0x03:
            sub = (op >> 5) & 0xF
            r = op & 0xF
            if op == 0x0340:       # IDLE
                raise Halt("IDLE")
            if op == 0x0380:       # RTWP: status, PC and workspace back from R15, R14, R13
                st, pc, wp = self.reg(15), self.reg(14), self.reg(13)
                self.st = st & 0xFFF0; self.limi = st & 0xF; self.pc = pc; self.wp = wp
                return
            if op == 0x0300:       # LIMI
                self.limi = self.fetch() & 0xF; return
            if op == 0x02E0:       # LWPI
                self.wp = self.fetch(); return
            if 0x02A0 <= op <= 0x02AF:  # STWP: the workspace pointer into R
                self.setreg(r, self.wp); return
            if 0x02C0 <= op <= 0x02CF:  # STST: the status register into R
                self.setreg(r, (self.st & 0xFFF0) | (self.limi & 0xF)); return
            imm = self.fetch()
            if sub == 0:           # LI
                self.setreg(r, imm); self.cmp0(imm, False)
            elif sub == 1:         # AI
                v = self.reg(r); s = v + imm
                self.flag('C', s > 0xFFFF); s &= 0xFFFF
                self.setreg(r, s); self.cmp0(s, False)
            elif sub == 2:         # ANDI
                v = self.reg(r) & imm; self.setreg(r, v); self.cmp0(v, False)
            elif sub == 3:         # ORI
                v = self.reg(r) | imm; self.setreg(r, v); self.cmp0(v, False)
            elif sub == 4:         # CI
                self.cmp(self.reg(r), imm, False)
            else:
                raise Halt(f"unimplemented imm op {op:04X}")
            return
        # ---- single operand: 0x04xx-0x07xx
        if 0x0400 <= op < 0x0800:
            kind = (op >> 6) & 0xF
            ts, s = (op >> 4) & 3, op & 0xF
            ea = self.ea(ts, s, False)
            if kind == 0:          # BLWP
                if ea[0] == 'm' and ea[1] == 0x0000:
                    # BLWP @>0000: the console's reset (as FCTN-QUIT).  There is no
                    # console ROM here, so do what matters: scratchpad cleared, the
                    # cartridge port back to bank 0, and the menu's choice of the
                    # cartridge's first program (expansion RAM and the cards keep
                    # their state, as they do on a real console)
                    self.m.at_reset = (list(self.m.vregs), dict(self.m.palette), self.m.ams_mapping)   # for the tests
                    # the scratchpad as the program left it: a real console does
                    # not clear it before its interrupt routine runs (a non-zero
                    # user hook at >83C4, or a sound count at >83CE, hangs the
                    # power-up), so a program must clear it before BLWP @>0000
                    self.m.scratch_at_reset = bytes(self.m.scratch)
                    for i in range(0x100): self.m.scratch[i] = 0
                    # the cartridge keeps the bank last selected (a FinalGROM's
                    # latch survives the reset: Rebecca's js99er lost the
                    # workbench from the menu after a game started with R
                    # quit), so the console finds a cartridge only if that
                    # bank holds the header
                    self.m.bank_at_reset = self.m.bank
                    if self.m.nbanks and self.m.cart[self.m.bank * 0x2000] != 0xAA:
                        raise Halt(f'the console finds no cartridge: bank {self.m.bank} is selected at the reset')
                    self.m.console_resets = getattr(self.m, 'console_resets', 0) + 1
                    self.wp = 0x83E0
                    self.pc = self.m.rw(self.m.rw(0x6006) + 2)
                    return
                # any other vector: the context switch (new WP and PC from the
                # vector; the old WP, PC and status into the new R13-R15)
                v = ea[1] if ea[0] == 'm' else (self.wp + 2 * ea[1]) & 0xFFFF
                nwp, npc = self.m.rw(v), self.m.rw(v + 2)
                if getattr(self.m, 'blwp_log', None) is not None and len(self.m.blwp_log) < 20:
                    self.m.blwp_log.append((v, nwp, npc))
                owp, opc, ost = self.wp, self.pc, self.st
                self.wp = nwp
                self.setreg(13, owp); self.setreg(14, opc); self.setreg(15, (ost & 0xFFF0) | (self.limi & 0xF))
                self.pc = npc
                return
            if kind == 1:          # B
                self.pc = ea[1] if ea[0] == 'm' else self.reg(ea[1]); return
            if kind == 2:          # X
                raise Halt("X unimplemented")
            if kind == 3:          # CLR
                self.store(ea, 0, False); return
            if kind == 4:          # NEG
                v = (-self.load(ea, False)) & 0xFFFF; self.store(ea, v, False); self.cmp0(v, False); return
            if kind == 5:          # INV
                v = (~self.load(ea, False)) & 0xFFFF; self.store(ea, v, False); self.cmp0(v, False); return
            if kind == 6:          # INC
                v = self.load(ea, False); s2 = v + 1; self.flag('C', s2 > 0xFFFF); s2 &= 0xFFFF
                self.store(ea, s2, False); self.cmp0(s2, False); return
            if kind == 7:          # INCT
                v = (self.load(ea, False) + 2) & 0xFFFF; self.store(ea, v, False); self.cmp0(v, False); return
            if kind == 8:          # DEC
                v = self.load(ea, False); s2 = (v - 1) & 0xFFFF; self.flag('C', v != 0)
                self.store(ea, s2, False); self.cmp0(s2, False); return
            if kind == 9:          # DECT
                v = (self.load(ea, False) - 2) & 0xFFFF; self.store(ea, v, False); self.cmp0(v, False); return
            if kind == 0xA:        # BL
                self.setreg(11, self.pc)
                self.pc = ea[1] if ea[0] == 'm' else self.reg(ea[1]); return
            if kind == 0xB:        # SWPB
                v = self.load(ea, False); self.store(ea, ((v << 8) | (v >> 8)) & 0xFFFF, False); return
            if kind == 0xC:        # SETO
                self.store(ea, 0xFFFF, False); return
            if kind == 0xD:        # ABS
                v = self.load(ea, False); self.cmp0(v, False)
                if v & 0x8000: self.store(ea, (-v) & 0xFFFF, False)
                return
        raise Halt(f"unimplemented op {op:04X} at {pc0:04X}")

TILECH = {0x80: '~', 0x81: ',', 0x88: '.', 0x89: 'T', 0x8A: 'w', 0x90: 'h', 0x91: 'M',
          0x92: '=', 0x93: ':', 0x94: '#', 0x95: '#', 0x96: '.', 0x98: 'O', 0x99: 'C',
          0x9A: 'D', 0x9B: 'r', 0x9C: '^', 0x20: ' ', 0xA0: '#', 0xA8: 'x'}

def screen(m):
    base = ((m.vregs[2] & 0x0F) << 10)
    rows = []
    for r in range(24):
        line = ''
        for c in range(32):
            ch = m.vram[base + r * 32 + c]
            if 32 <= ch < 96: line += chr(ch)
            elif ch >= 0xC0: line += chr(ch - 0xA0)      # the ink font (message scroll, key badges)
            else: line += TILECH.get(ch, '.')
        rows.append(line)
    return '\n'.join(rows)

def main():
    args = sys.argv[1:]
    path = args[0]
    f18a = '--no-f18a' not in args
    pages = 128
    insns = 800_000
    if '--pages' in args: pages = int(args[args.index('--pages') + 1])
    if '--insns' in args: insns = int(args[args.index('--insns') + 1])
    keys = 'Q'
    if '--keys' in args: keys = args[args.index('--keys') + 1]
    disk = None
    if '--disk' in args: disk = args[args.index('--disk') + 1]
    cart = open(path, 'rb').read()
    m = Machine(cart, f18a=f18a, pages=pages)
    m.disk_dir = disk
    m.keys = [key_pos(c) for c in keys]
    insns = max(insns, KEY_AT + KEY_PERIOD * (len(keys) + 2))
    cpu = CPU(m)
    # emulate the console menu: jump to the cart's first program entry
    prog = m.rw(0x6006)
    cpu.pc = m.rw(prog + 2)
    try:
        while m.insns < insns:
            cpu.step()
    except Halt as e:
        print("HALT:", e, f"at PC={cpu.pc:04X} after {m.insns} insns")
    print(f"ran {m.insns} instructions, bank={m.bank}, mapping={m.ams_mapping}, "
          f"f18a_unlocked={m.unlocked}, palette entries={len(m.palette)}")
    print("VDP regs:", ' '.join(f"{v:02X}" for v in m.vregs[:8]))
    print("map:", m.map)
    print('+' + '-' * 32 + '+')
    for line in screen(m).split('\n'):
        print('|' + line + '|')
    print('+' + '-' * 32 + '+')
    sat = (m.vregs[5] & 0x7F) * 0x80
    spr = m.vram[sat:sat + 4]
    print(f"sprite0: y={spr[0]} x={spr[1]} pat={spr[2]} col={spr[3]}  PC={cpu.pc:#06x} WP={cpu.wp:#06x}")

if __name__ == '__main__':
    main()
