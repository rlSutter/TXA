"""opcodes.py - the TXA story VM's instruction set: the one definition.

The compiler (codegen.py), the Python reference VM (txvm.py) and the
documentation generator read this table; the assembly VM's dispatch
table is checked against it by the tests.  Change an opcode here and
nowhere else.

The machine
-----------
- Values are 16-bit words, signed for arithmetic and comparison.
- A value stack and a call stack.  Each call frame holds up to 16 local
  variables (parameters first), the return address, the caller's stack
  height and the caller's SELF.
- Variables are numbered 0-255: 0-15 are the current frame's locals,
  16-255 are the globals (global n is variable 16 + n).
- SELF is a register: set by RUNPROP/CALLPROP to the object whose
  property is running, put back when that routine returns.
- Routines and strings start on 4-byte boundaries and are named by
  16-bit *packed addresses* (byte address / 4), reaching a 256K image.
- A routine starts with one byte, its local count (parameters
  included); its code follows.  Locals past the arguments start at 0.
- Jumps carry a signed 16-bit offset from the byte after the jump.
- Operands follow the opcode: b = one byte (unsigned unless noted),
  w = one word (high byte first), j = a jump offset, p = a packed address.

Stack notation: "a b -> c" pops b then a and pushes c.
"""

# (code, name, operands, stack effect, description)
OPS = [
    # ---- constants, stack, variables
    (0x00, 'NOP',      '',  '',           'Do nothing.'),
    (0x01, 'PUSHB',    'b', '-> v',       'Push a signed byte (-128 to 127).'),
    (0x02, 'PUSHW',    'w', '-> v',       'Push a word.'),
    (0x03, 'PUSH0',    '',  '-> 0',       'Push 0 (FALSE, NOTHING).'),
    (0x04, 'PUSH1',    '',  '-> 1',       'Push 1 (TRUE).'),
    (0x05, 'POP',      '',  'v ->',       'Discard the top of the stack.'),
    (0x06, 'DUP',      '',  'v -> v v',   'Copy the top of the stack.'),
    (0x07, 'LOADSELF', '',  '-> obj',     'Push SELF.'),
    (0x08, 'LOAD',     'b', '-> v',       'Push variable b (0-15 local, 16-255 global).'),
    (0x09, 'STORE',    'b', 'v ->',       'Pop into variable b.'),
    (0x0A, 'INC',      'b', '',           'Add 1 to variable b.'),
    (0x0B, 'DEC',      'b', '',           'Subtract 1 from variable b.'),
    # ---- arithmetic and logic
    (0x10, 'ADD',      '',  'a b -> a+b', 'Add.'),
    (0x11, 'SUB',      '',  'a b -> a-b', 'Subtract.'),
    (0x12, 'MUL',      '',  'a b -> a*b', 'Multiply (low 16 bits).'),
    (0x13, 'DIV',      '',  'a b -> a/b', 'Divide, truncating toward zero; division by zero is a run-time error.'),
    (0x14, 'MOD',      '',  'a b -> r',   'Remainder, with the sign of a; by zero is a run-time error.'),
    (0x15, 'NEG',      '',  'a -> -a',    'Negate.'),
    (0x16, 'NOT',      '',  'a -> !a',    'Logical not: 1 if a is 0, else 0.'),
    (0x18, 'EQ',       '',  'a b -> f',   '1 if a = b, else 0.'),
    (0x19, 'NE',       '',  'a b -> f',   '1 if a <> b.'),
    (0x1A, 'LT',       '',  'a b -> f',   '1 if a < b (signed).'),
    (0x1B, 'GT',       '',  'a b -> f',   '1 if a > b.'),
    (0x1C, 'LE',       '',  'a b -> f',   '1 if a <= b.'),
    (0x1D, 'GE',       '',  'a b -> f',   '1 if a >= b.'),
    # ---- control
    (0x20, 'JMP',      'j', '',           'Jump.'),
    (0x21, 'JZ',       'j', 'v ->',       'Jump if v is 0.'),
    (0x22, 'JNZ',      'j', 'v ->',       'Jump if v is not 0.'),
    (0x23, 'CALL',     'pb', 'args -> r', 'Call routine p with the top b values as arguments (b <= 7); push its result.'),
    (0x24, 'CALLV',    'b', 'args r -> v', 'Call the routine whose packed address is on top, under it b arguments. Calling 0 returns 0.'),
    (0x25, 'RET',      '',  'v ->',       'Return v to the caller.'),
    (0x26, 'RTRUE',    '',  '',           'Return 1.'),
    (0x27, 'RFALSE',   '',  '',           'Return 0.'),
    # ---- the object tree
    (0x30, 'PARENT',   '',  'o -> p',     'Parent of o (0 for none).'),
    (0x31, 'CHILD',    '',  'o -> c',     'First child of o.'),
    (0x32, 'SIBLING',  '',  'o -> s',     'Next sibling of o.'),
    (0x33, 'MOVE',     '',  'o d ->',     'Move o to be the first child of d.'),
    (0x34, 'REMOVE',   '',  'o ->',       'Take o out of the tree (parent 0).'),
    (0x35, 'IN',       '',  'o p -> f',   '1 if the parent of o is p.'),
    (0x36, 'HASATTR',  'b', 'o -> f',     '1 if o has attribute b.'),
    (0x37, 'SETATTR',  'b', 'o ->',       'Give o attribute b.'),
    (0x38, 'CLRATTR',  'b', 'o ->',       'Take attribute b from o.'),
    (0x39, 'GETPROP',  'b', 'o -> v',     "First word of o's property b; 0 if o has none. A string or routine gives its packed address."),
    (0x3A, 'PUTPROP',  'bb', 'o v ->',    "Set the first word of o's property b1 and its kind to b2 (>00 a value, >40 a string, >80 a routine), so a routine exit given a room becomes a value and the reverse; a run-time error if o has none."),
    (0x3B, 'PROPLEN',  'b', 'o -> n',     "Number of words in o's property b; 0 if none."),
    (0x3C, 'RUNPROP',  'b', 'o -> r',     "Property b of o: a routine is called with SELF = o and its result pushed; a string is printed and 1 pushed; a value is pushed; none pushes 0."),
    (0x3D, 'CALLPROP', 'bb', 'o args -> r', 'Call the routine in property b1 of o with b2 arguments and SELF = o; 0 if o has no such routine.'),
    (0x3E, 'GETPROPN', 'b', 'o i -> v',   'Word i (from 0) of property b of o; 0 past the end.'),
    (0x3F, 'HASATTRV', '',  'o a -> f',   '1 if o has attribute a (a number on the stack: the grammar holds attributes as numbers).'),
    # ---- arrays
    (0x40, 'ALOAD',    'b', 'i -> v',     'Element i of array b; a run-time error outside it.'),
    (0x41, 'ASTORE',   'b', 'i v ->',     'Set element i of array b.'),
    (0x42, 'ALEN',     'b', '-> n',       'Number of elements in array b.'),
    (0x43, 'ALOADV',   '',  'a i -> v',   'Element i of the array whose number is a (an array named as a value gives its number).'),
    (0x44, 'ASTOREV',  '',  'a i v ->',   'Set element i of array a.'),
    # ---- text
    (0x48, 'PRINTS',   'p', '',           'Print the packed string p.'),
    (0x49, 'PRINTV',   '',  'p ->',       'Print the packed string on the stack (0 prints nothing).'),
    (0x4A, 'PRINTN',   '',  'n ->',       'Print a signed number.'),
    (0x4B, 'PRINTO',   '',  'o ->',       "Print o's short name."),
    (0x4C, 'PRINTC',   '',  'c ->',       'Print one character.'),
    (0x4D, 'NEWLINE',  '',  '',           'End the line.'),
    (0x4E, 'STYLE',    '',  'n ->',       'Text style from now on: 0 roman, 1 bold, 2 underline, 4 reverse, added together to combine.'),
    (0x4F, 'PRINTA',   'b', 'o ->',       "Print o's name with an article: 0 'the', 1 'The', 2 'a', 3 'A' (plural, proper and vowel rules)."),
    # ---- input
    (0x50, 'READ',     '',  't p -> n',   'Read a command line into text array t (t(0) = length, then one character per element, lower case) and TOKENIZE it into parse array p; push the word count.'),
    (0x51, 'READKEY',  '',  '-> c',       'Wait for a key; push its code.'),
    (0x53, 'FRESH',    '',  '',           'End the line if anything has been printed on it since the last new line.'),
    (0x52, 'TOKENIZE', '',  't p -> n',   'Split the text in array t into words: p(0) = count, then for each word its dictionary number (0 if unknown), its first character (index into t) and its length. Words are runs of characters other than space, comma and period; a comma or period is a word by itself. Matched on 12 characters. Words past the space in p are dropped.'),
    # ---- system
    (0x58, 'RANDOM',   '',  'n -> r',     'A random number from 1 to n; n <= 0 reseeds (0 at random, -s with s) and pushes 0.'),
    (0x59, 'QUIT',     '',  '',           'End the game: back to the title screen.'),
    (0x5A, 'RESTART',  '',  '',           'Reload the dynamic area and start again.'),
    (0x5B, 'SAVE',     '',  '-> f',       'Save the game (asks for a file name); 1 if saved.'),
    (0x5C, 'RESTORE',  '',  '-> f',       'Restore a saved game; 0 if it failed (on success execution continues after the SAVE).'),
    (0x5D, 'UNDOSAVE', '',  '-> f',       'Take an undo snapshot; 1, or 2 when continuing after an UNDO.'),
    (0x5E, 'UNDO',     '',  '-> f',       'Go back to the last snapshot; 0 if there is none.'),
    (0x5F, 'PICTURE',  '',  'n ->',       'Show picture n (0 hides the pane).'),
    (0x60, 'STATUS',   '',  '',           'Redraw the status line.'),
    (0x61, 'SOUND',    '',  'n ->',       'Play sound effect n.'),
]

BY_NAME = {o[1]: o for o in OPS}
BY_CODE = {o[0]: o for o in OPS}
assert len(BY_NAME) == len(OPS) and len(BY_CODE) == len(OPS)

def operand_size(ops):
    return sum({'b': 1, 'w': 2, 'j': 2, 'p': 2}[c] for c in ops)

# ---- the story image -------------------------------------------------------
MAGIC = b'TXA1'
FORMAT_VERSION = 1
HEADER_SIZE = 64
# header fields: name -> byte offset (all words unless noted)
HDR = {
    'magic': 0,            # 4 bytes 'TXA1'
    'version': 4,          # format version
    'release': 6,          # the game's release number
    'flags': 8,
    'image_len_hi': 10,    # image length in bytes, high and low words
    'image_len_lo': 12,
    'dynamic_len': 14,     # bytes from 0 to the end of the dynamic area
    'objects': 16,         # offset of the object table
    'object_count': 18,
    'props_start': 20,     # offset of the first property table
    'globals': 22,         # offset of the globals (240 words)
    'arrays': 24,          # offset of the array directory
    'dictionary': 26,      # offset of the dictionary (static)
    'grammar': 28,         # offset of the grammar table
    'actions': 30,         # offset of the action table
    'abbrevs': 32,         # offset of the text substitution table
    'entry': 34,           # packed address of Main
    'checksum': 36,        # sum of all bytes after the header, mod 65536
    'build_date': 38,      # 6 bytes YYMMDD in ASCII
    'pictures': 44,        # offset of the picture index (0 = none)
    'title': 46,           # 16 bytes, the game's title, space padded
    'attr_proper': 62,     # byte: the attribute meaning "proper name" (255 = none), for PRINTA
    'attr_plural': 63,     # byte: the attribute meaning "plural" (255 = none)
}
# The static tables (dictionary, grammar, actions, substitutions) must lie
# in the first 64K, because the header holds 16-bit offsets to them;
# routines and strings may lie anywhere in the 256K, by packed address.
OBJ_ENTRY = 14             # parent, sibling, child, 6 bytes of attributes, property table offset
PROP_STR, PROP_ROUTINE, PROP_VALUES = 0x40, 0x80, 0x00   # kind bits in a property entry's first byte
