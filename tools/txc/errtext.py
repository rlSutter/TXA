"""errtext.py - the compiler's error messages as templates, by the TI
workbench's error code (M6 part 6, decision D6: the TI words its errors
exactly as the Python compiler does).  tools/build.py turns this table into
the workbench's message overlay; tests/errtext_test.py checks each
template against the Python compiler's own message for every error case.

The fields a template may use, which the TI's error sites record:
  {n1} {n2}  names or words (an identifier, a dictionary word, a kind; for
             the parser, {n2} is the token found, described as Python's
             describe() does; code 14's {n1} is "KIND NAME")
  {a} {b}    numbers
  {f} {l}    another declaration's file and line
"""

TEMPLATES = {
    # the lexer
    1: 'string not closed',
    2: 'a dictionary word in single quotes is not closed',
    3: 'expected an action name after ##',
    4: 'number {n1} is larger than 32767',
    5: 'hex number {n1} does not fit in 16 bits',
    6: 'unexpected character {n1}',
    # the parser
    10: 'expected {n1}, found {n2}',
    11: 'expected the end of the line, found {n2}',
    12: 'expected a declaration (OBJECT, ROOM, ROUTINE ...), found {n2}',
    13: '{n1} cannot start a declaration',
    14: '{n1} has no END',
    15: 'expected a property, HAS, NAME, CLASS, IN or END, found {n2}',
    16: 'expected an attribute',
    17: 'VERB has no END',
    18: 'expected a grammar token or ->, found {n2}',
    19: 'missing END',
    20: 'WRITE needs something to write',
    21: 'only a variable, a property or an array element can be assigned to',
    22: 'this line computes a value and does nothing with it: a statement, call or assignment is needed here',
    23: 'comparisons cannot be chained: use AND',
    24: 'a call takes at most 7 arguments',
    25: 'number 32768 is larger than 32767 (-32768 is allowed)',
    26: 'expected a value, found {n2}',
    27: 'expected an action name, found {n2}',
    # loading and meaning
    40: 'cannot find the file {n1} (looked for {n2}.txa)',
    41: '{n1} is a built-in function and cannot be declared',
    42: '{n1} is already declared ({f} line {l})',
    43: 'more than 240 globals',
    44: 'more than 48 attributes',
    45: 'more than 63 properties',
    46: 'more than 1000 objects',
    47: 'the constant {n1} is defined in terms of itself',
    48: 'the value of {n1} must be worked out when compiling (numbers and constants only)',
    49: 'division by zero',
    50: '{n1} is not a class',
    51: 'the class {n1} includes itself',
    52: '{n1} is not an object, so nothing can be IN it',
    53: '{n1} is given two parents',
    54: 'unknown attribute "{n1}"',
    55: 'a class cannot say what its objects are IN',
    56: 'unknown property {n1} (declare it with PROPERTY)',
    57: 'unknown name {n1}',
    58: 'SELF has no value outside a routine',
    59: 'a property value must be a number, a string, an object, a routine or a constant expression',
    60: 'a dictionary word cannot be empty or contain spaces: "{n1}"',
    61: '{n1} is inside itself (through IN)',
    62: 'REPLACE {n1}, but this file has no ROUTINE {n1}',
    63: 'EXTEND "{n1}": no VERB has that word',
    64: 'the action {n1} has no routine {n1}Sub',
    65: '"{n1}" is already a word of another VERB',
    66: '{n1} is not a grammar token (noun, held, multi ...) or an attribute',
    67: '{n1} is not a routine',
    68: 'a grammar line takes at most two objects',
    69: '{n1} is declared twice in this routine',
    70: 'more than 16 parameters and locals in one routine',
    71: 'the loop variable {n1} must be a LOCAL',
    72: '{n1} on its own does nothing: did you mean a call, {n1}()?',
    73: '{n1} is a {n2}, not a variable: it cannot be assigned to',
    74: 'only an array element can be assigned to with ( )',
    75: 'an array element takes one index',
    76: '{n1} is a {n2} and has no value here',
    77: '{n1} needs an attribute name after it',
    78: 'unknown property {n1}',
    79: '{n1} takes {a} argument{n2}, not {b}',
    80: 'the second argument of {n1} must be a property name',
    82: '{n1} is a {n2} and cannot be called',
    # code generation and linking
    83: 'there is no ROUTINE Main: the game starts there',
    84: 'rule cases need the library\'s global "action"',
    85: 'cannot compile {n1}',
    87: 'a property holds at most 255 words',
    88: 'the dynamic area is {a} bytes; the limit is 16384 (too many objects or properties)',
    89: 'the tables before the routines pass 64K',
    90: 'the story is {a} bytes; the limit is {b}',
}

def render(code, n1='', n2='', a=0, b=0, f='', l=0):
    """The message for error code, its fields filled in (as the TI fills them)."""
    return TEMPLATES[code].format(n1=n1, n2=n2, a=a, b=b, f=f, l=l)

def pattern(code):
    """A regular expression matching the messages template code can give."""
    import re
    out, t = '', TEMPLATES[code]
    for part in re.split(r'(\{\w+\})', t):
        if re.fullmatch(r'\{\w+\}', part):
            out += '(.*?)'
        else:
            out += re.escape(part)
    return re.compile(out + r'\Z')
