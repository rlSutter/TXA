"""txvm.py - the Python reference VM for TXA story images.

Runs a story image exactly as the TI engine will (opcodes.py is the
definition), writing text to a list and reading commands from a script.
It is the oracle the assembly VM is tested against: same image, same
commands, same transcript.  Text is produced unwrapped; the TI's screen
code does the wrapping.

  python3 -m txc.txvm story.txa.img [commands...]
"""
from .opcodes import BY_CODE, HDR, HEADER_SIZE, MAGIC, OBJ_ENTRY, PROP_STR, PROP_ROUTINE

class VMError(Exception):
    pass

class Quit(Exception):
    pass

def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v > 0x7FFF else v

class VM:
    def __init__(self, image, commands=(), seed=1):
        if image[:4] != MAGIC:
            raise VMError('not a TXA story image')
        self.img = bytearray(image)
        self.orig = bytes(image)
        self.out = []
        self.commands = list(commands)
        self.seed = seed or 1
        self.stack, self.frames = [], []
        self.self_ = 0
        self.steps = 0
        h = self.hw
        self.objects, self.nobj = h('objects'), h('object_count')
        self.globals, self.arrays = h('globals'), h('arrays')
        ab = h('abbrevs')
        self.abbrevs = []
        for i in range(128):
            off = self.rw(ab + 2 * i)
            self.abbrevs.append(self.cstr(ab + off) if off else '')
        self.attr_proper, self.attr_plural = self.img[HDR['attr_proper']], self.img[HDR['attr_plural']]

    # ---- memory
    def hw(self, field):
        return self.rw(HDR[field])
    def rw(self, a):
        return (self.img[a] << 8) | self.img[a + 1]
    def ww(self, a, v):
        self.img[a] = (v >> 8) & 0xFF; self.img[a + 1] = v & 0xFF
    def cstr(self, a):
        s = []
        while self.img[a]:
            s.append(chr(self.img[a])); a += 1
        return ''.join(s)
    def text(self, packed):
        a, s = packed * 4, []
        while self.img[a]:
            b = self.img[a]; a += 1
            s.append(self.abbrevs[b - 0x80] if b >= 0x80 else chr(b))
        return ''.join(s)

    # ---- objects
    def obj(self, o):
        if not 1 <= o <= self.nobj:
            raise VMError(f'object {o} does not exist')
        return self.objects + (o - 1) * OBJ_ENTRY
    def parent(self, o): return self.rw(self.obj(o))
    def sibling(self, o): return self.rw(self.obj(o) + 2)
    def child(self, o): return self.rw(self.obj(o) + 4)
    def has(self, o, a):
        return bool(self.img[self.obj(o) + 6 + a // 8] & (0x80 >> (a % 8)))
    def setattr_(self, o, a, on):
        p = self.obj(o) + 6 + a // 8; m = 0x80 >> (a % 8)
        self.img[p] = (self.img[p] | m) if on else (self.img[p] & ~m)
    def detach(self, o):
        e = self.obj(o); par = self.rw(e)
        if not par:
            return
        pe = self.obj(par)
        if self.rw(pe + 4) == o:
            self.ww(pe + 4, self.rw(e + 2))
        else:
            c = self.rw(pe + 4)
            while self.rw(self.obj(c) + 2) != o:
                c = self.rw(self.obj(c) + 2)
            self.ww(self.obj(c) + 2, self.rw(e + 2))
        self.ww(e, 0); self.ww(e + 2, 0)
    def move(self, o, d):
        q = d
        while q:                                  # never into itself
            if q == o:
                raise VMError(f'cannot move object {o} inside itself')
            q = self.parent(q)
        self.detach(o)
        e, de = self.obj(o), self.obj(d)
        self.ww(e, d); self.ww(e + 2, self.rw(de + 4)); self.ww(de + 4, o)
    def prop(self, o, n):
        """(kind bits, length, address of the first word) or None."""
        a = self.rw(self.obj(o) + 12) + 2
        while self.img[a]:
            hdr, ln = self.img[a], self.img[a + 1]
            if hdr & 0x3F == n:
                return hdr & 0xC0, ln, a + 2
            a += 2 + 2 * ln
        return None
    def short_name(self, o):
        p = self.rw(self.rw(self.obj(o) + 12))
        return self.text(p) if p else '?'

    # ---- output
    def write(self, s):
        self.out.append(s)
    def transcript(self):
        return ''.join(self.out)

    # ---- calls
    def call(self, packed, args, ret_to, self_obj=None):
        if packed == 0:
            self.stack.append(0); return ret_to
        a = packed * 4
        n = self.img[a]
        locals_ = [s16(x) for x in args[:n]] + [0] * (n - min(n, len(args)))
        if len(self.frames) > 64:
            raise VMError('routines nested too deeply')
        self.frames.append((ret_to, locals_, len(self.stack), self.self_))
        if self_obj is not None:
            self.self_ = self_obj
        return a + 1
    def ret(self, v):
        ret_to, _, height, self_ = self.frames.pop()
        del self.stack[height:]
        self.self_ = self_
        if ret_to is None:
            raise Quit()
        self.stack.append(s16(v))
        return ret_to

    def run(self, max_steps=5_000_000):
        pc = self.call(self.hw('entry'), [], None)
        try:
            while True:
                pc = self.step(pc)
                self.steps += 1
                if self.steps > max_steps:
                    raise VMError('too many steps (a loop that never ends?)')
        except Quit:
            pass
        except VMError as e:
            self.write(f'\n[TXA run-time error: {e}]\n')
        return self.transcript()

    def step(self, pc):
        img, st = self.img, self.stack
        code = img[pc]; pc += 1
        if code not in BY_CODE:
            raise VMError(f'unknown opcode >{code:02X} at {pc - 1}')
        name = BY_CODE[code][1]
        def b():
            nonlocal pc
            v = img[pc]; pc += 1; return v
        def w():
            nonlocal pc
            v = self.rw(pc); pc += 2; return v
        pop = st.pop; push = lambda v: st.append(s16(v))
        locals_ = self.frames[-1][1]
        def load(n):
            return locals_[n] if n < 16 else s16(self.rw(self.globals + 2 * (n - 16)))
        def store(n, v):
            if n < 16:
                if n >= len(locals_):
                    raise VMError(f'local {n} does not exist in this routine')
                locals_[n] = s16(v)
            else:
                self.ww(self.globals + 2 * (n - 16), v & 0xFFFF)
        if name == 'NOP': pass
        elif name == 'PUSHB': v = b(); push(v - 256 if v > 127 else v)
        elif name == 'PUSHW': push(w())
        elif name == 'PUSH0': push(0)
        elif name == 'PUSH1': push(1)
        elif name == 'POP': pop()
        elif name == 'DUP': push(st[-1])
        elif name == 'LOADSELF': push(self.self_)
        elif name == 'LOAD': push(load(b()))
        elif name == 'STORE': n = b(); store(n, pop())
        elif name == 'INC': n = b(); store(n, load(n) + 1)
        elif name == 'DEC': n = b(); store(n, load(n) - 1)
        elif name in ('ADD', 'SUB', 'MUL', 'DIV', 'MOD', 'EQ', 'NE', 'LT', 'GT', 'LE', 'GE', 'IN'):
            y = pop(); x = pop()
            if name in ('DIV', 'MOD') and y == 0:
                raise VMError('division by zero')
            push({'ADD': lambda: x + y, 'SUB': lambda: x - y, 'MUL': lambda: x * y,
                  'DIV': lambda: int(x / y), 'MOD': lambda: x - int(x / y) * y,
                  'EQ': lambda: x == y, 'NE': lambda: x != y, 'LT': lambda: x < y, 'GT': lambda: x > y,
                  'LE': lambda: x <= y, 'GE': lambda: x >= y,
                  'IN': lambda: x != 0 and self.parent(x) == y}[name]())
        elif name == 'NEG': push(-pop())
        elif name == 'NOT': push(pop() == 0)
        elif name == 'JMP': off = s16(w()); pc += off
        elif name in ('JZ', 'JNZ'):
            off = s16(w()); v = pop()
            if (v == 0) == (name == 'JZ'):
                pc += off
        elif name == 'CALL':
            p = w(); n = b(); args = st[len(st) - n:]; del st[len(st) - n:]
            pc = self.call(p, args, pc)
        elif name == 'CALLV':
            n = b(); p = pop() & 0xFFFF; args = st[len(st) - n:]; del st[len(st) - n:]
            pc = self.call(p, args, pc)
        elif name == 'RET': pc = self.ret(pop())
        elif name == 'RTRUE': pc = self.ret(1)
        elif name == 'RFALSE': pc = self.ret(0)
        elif name == 'PARENT': push(self.parent(pop()))
        elif name == 'CHILD': push(self.child(pop()))
        elif name == 'SIBLING': push(self.sibling(pop()))
        elif name == 'MOVE': d = pop(); o = pop(); self.move(o, d)
        elif name == 'REMOVE': self.detach(pop())
        elif name == 'HASATTR': a = b(); push(self.has(pop(), a))
        elif name in ('SETATTR', 'CLRATTR'): a = b(); self.setattr_(pop(), a, name == 'SETATTR')
        elif name == 'GETPROP':
            n = b(); pr = self.prop(pop(), n); push(self.rw(pr[2]) if pr else 0)
        elif name == 'PUTPROP':
            n = b(); kind = b(); v = pop(); o = pop(); pr = self.prop(o, n)
            if not pr:
                raise VMError(f'object {o} has no property {n} to change')
            self.ww(pr[2], v & 0xFFFF)
            hdr = pr[2] - 2                         # the entry's header byte: number and kind
            self.img[hdr] = (self.img[hdr] & 0x3F) | kind
        elif name == 'PROPLEN':
            n = b(); pr = self.prop(pop(), n); push(pr[1] if pr else 0)
        elif name == 'GETPROPN':
            n = b(); i = pop(); pr = self.prop(pop(), n)
            push(self.rw(pr[2] + 2 * i) if pr and 0 <= i < pr[1] else 0)
        elif name == 'RUNPROP':
            n = b(); o = pop(); pr = self.prop(o, n)
            if not pr:
                push(0)
            elif pr[0] == PROP_ROUTINE:
                pc = self.call(self.rw(pr[2]), [], pc, self_obj=o)
            elif pr[0] == PROP_STR:
                self.write(self.text(self.rw(pr[2]))); push(1)
            else:
                push(self.rw(pr[2]))
        elif name == 'CALLPROP':
            n = b(); k = b(); args = st[len(st) - k:]; del st[len(st) - k:]; o = pop()
            pr = self.prop(o, n)
            if pr and pr[0] == PROP_ROUTINE:
                pc = self.call(self.rw(pr[2]), args, pc, self_obj=o)
            else:
                push(0)
        elif name in ('ALOAD', 'ASTORE', 'ALEN'):
            n = b()
            if n >= self.rw(self.arrays):
                raise VMError(f'array {n} does not exist')
            start, ln = self.rw(self.arrays + 2 + 4 * n), self.rw(self.arrays + 4 + 4 * n)
            if name == 'ALEN':
                push(ln)
            else:
                v = pop() if name == 'ASTORE' else None
                i = pop()
                if not 0 <= i < ln:
                    raise VMError(f'index {i} is outside array {n} (0 to {ln - 1})')
                if name == 'ALOAD':
                    push(self.rw(start + 2 * i))
                else:
                    self.ww(start + 2 * i, v & 0xFFFF)
        elif name == 'PRINTS': self.write(self.text(w()))
        elif name == 'PRINTV':
            p = pop() & 0xFFFF
            if p:
                self.write(self.text(p))
        elif name == 'PRINTN': self.write(str(pop()))
        elif name == 'PRINTO':
            o = pop(); self.write(self.short_name(o) if o else 'nothing')
        elif name == 'PRINTC': self.write(chr(pop() & 0xFF))
        elif name == 'NEWLINE': self.write('\n')
        elif name == 'STYLE': b()
        elif name == 'PRINTA':
            form = b(); o = pop(); nm = self.short_name(o)
            proper = self.attr_proper != 255 and self.has(o, self.attr_proper)
            plural = self.attr_plural != 255 and self.has(o, self.attr_plural)
            if proper:
                art = ''
            elif form in (0, 1):
                art = 'the ' if form == 0 else 'The '
            elif plural:
                art = 'some ' if form == 2 else 'Some '
            else:
                art = ('an ' if nm[:1].lower() in 'aeiou' else 'a ')
                art = art if form == 2 else art.capitalize()
            self.write(art + nm)
        elif name == 'READ':
            if not self.commands:
                raise Quit()
            line = self.commands.pop(0)
            self.write(line + '\n')
            self.last_input = line
            push(len(line.split()))
        elif name == 'READKEY': push(13)
        elif name == 'RANDOM':
            n = pop()
            if n <= 0:
                self.seed = -n if n < 0 else 12345; push(0)
            else:
                self.seed = (self.seed * 75 + 74) % 65537     # the engine's generator (ZX81's)
                push(self.seed % n + 1)
        elif name == 'QUIT': raise Quit()
        elif name == 'RESTART':
            self.img[:self.hw('dynamic_len')] = self.orig[:self.hw('dynamic_len')]
            self.stack.clear(); self.frames.clear(); self.self_ = 0
            pc = self.call(self.hw('entry'), [], None)
        elif name in ('SAVE', 'RESTORE', 'UNDOSAVE', 'UNDO'): push(0)    # M4
        elif name in ('PICTURE', 'SOUND'): self.write(f'[{name.lower()} {pop()}]')
        elif name == 'STATUS': pass
        else:
            raise VMError(f'{name} is not implemented')
        return pc

def run_image(image, commands=(), seed=1, max_steps=5_000_000):
    return VM(image, commands, seed).run(max_steps)
