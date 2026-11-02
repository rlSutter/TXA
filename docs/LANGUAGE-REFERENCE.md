# TXA Authoring Language Reference

TXA is the language TXA games are written in: Inform's model of objects, classes, attributes, properties and before/after rules, written as line-by-line blocks that each close with `END`. This reference covers the whole language as the compiler accepts it for TXA 1.0 (2 November 2026), with the standard library's essentials (every attribute, property, verb and routine is in the *Standard Library Reference*). Every example compiles.

## Introduction

A TXA game is a text file of declarations: rooms, objects, verbs and routines. It starts by including the standard library, which supplies the parser, about 90 actions, light and darkness, doors, containers, scoring, saving and the main loop. Here is a complete game:

```
! garden.txa - the smallest complete TXA game
INCLUDE "DSK1.STDLIB"

ROOM Garden "Walled Garden"
  DESC "Roses run wild over old brick walls. A gate leads north."
  HAS light
  N "The gate is rusted shut."
END

OBJECT Trowel "trowel" IN Garden
  NAME "small" "trowel"
  DESC "A small trowel, its handle worn smooth."
END

ROUTINE Initialise
  location = Garden
END
```

It plays like this:

```
Walled Garden
Roses run wild over old brick walls. A gate leads north.
You can see a trowel here.

>take trowel
Taken.

>n
The gate is rusted shut.
```

The library calls the game's `Initialise` routine once, at the start; it must set `location`, the room the player begins in.

**Compiling and running.** On a PC, the game writer turns a source file into files a TI runs:

```
python3 tools/txa_game.py garden.txa --prefix GARDEN --cart
```

That writes the engine as E/A option 5 files (GARDEN1, GARDEN2, ...), the story as 4K files (GARDENS01, ...), a disk image holding them all, and with `--cart` a FinalGROM cartridge. The player needs an F18A or PICO9918 and a SAMS card of 512K or more. On the TI itself, the TXA Workbench cartridge compiles the same source byte for byte as the PC does, test-plays it and builds the game (see the *Workbench Manual*).

## Source files and lexical rules

TXA is line-oriented: one declaration line or one statement per line, and every block closes with `END`. Source files are plain text (DV80 on the TI, so Press 2.0 or TI-Writer can edit them).

| Element | Rule | Example |
| --- | --- | --- |
| Lines | One statement or declaration line per line; blank lines are ignored. A rule case may put one statement after its label on the same line. | `Take: RETURN TRUE` |
| Case | Keywords are written in capitals by convention, but keywords and names both ignore case, so ALPHA LOCK never breaks a program. Names keep their spelling in messages. | `object` = `OBJECT`; `lamp` = `Lamp` |
| Comments | `!` to the end of the line, outside strings. | `! the cellar` |
| Strings | Double quotes. `^` is a new line, `~` a double quote. A string left open at the end of a line continues on the next: the break reads as one space, and spaces either side of it are dropped, so long text fits 80-column TI source files (tools/txa\_wrap.py wraps a file for you). | `"He says ~hello~.^"` |
| Numbers | Decimal 0 to 32767; `-32768` only written with its minus sign. Hex with the TI's `>` prefix. | `42`, `-32768`, `>1F` |
| Dictionary words | Single quotes: the number of a word in the game's dictionary (for parser code). Matched on 12 letters, lower case. | `IF w = 'lamp'` |
| Action numbers | `##` before an action's name. | `action = ##Take` |
| Names | A letter, then letters, digits or `_`. A name may be declared once (case ignored); keywords, built-in function names and compiler names are reserved (see the appendix). | `Brass_Lamp`, `tide_in` |
| Punctuation | `:` `,` `(` `)` `.` `->` and the operators `+ - * / = <> < > <= >=`. |  |

**Reserved words catch out authors in two ways.** A variable can't be called `room`, `name` or `end` (they are keywords), and a routine can't be called `Random` or `Status` (they are built-ins), because case is ignored. The compiler reports either clearly.

**Files.** `INCLUDE "DSK1.STDLIB"` names a file the TI way; on a PC the compiler looks for `stdlib.txa` beside the including file, then on the library path. A file is included once, however often it is named.

## Declarations

A file is a list of declarations, in any order: a name can be used before or after the line that declares it.

| Declaration | Form | Notes |
| --- | --- | --- |
| INCLUDE | `INCLUDE "DSK1.FILE"` | Includes another source file once. |
| CONSTANT | `CONSTANT MAXCOINS = 12` | A number worked out when compiling, from numbers and other constants (in any order); `CONSTANT B = A * 2 + 1`. |
| GLOBAL | `GLOBAL tide_in` or `GLOBAL greeting = "Hello."` | A variable every routine can use, 0 unless given a value: a number, string, object, routine name or constant expression. |
| ARRAY | `ARRAY slots 10` or `ARRAY primes = 2, 3, 5, 7` | A row of words: the first form is that many zeros, the second those values. Elements count from 0: `slots(3)`. |
| ATTRIBUTE | `ATTRIBUTE haunted cursed` | New yes/no flags objects can have (`HAS haunted`). |
| PROPERTY | `PROPERTY weight colour` | New properties objects can carry. Every property must be declared somewhere (anywhere in the files); the library declares its own the same way. |
| PICTURE | `PICTURE Harbour "HARBOUR"` | A picture, by name and source file (a PNG, or a TI Artist picture NAME_P and NAME_C), numbered from 1. |
| CLASS | `CLASS Furniture` ... `END` | A set of attributes and properties objects can share (Objects). |
| OBJECT | `OBJECT Lamp "brass lamp" IN Kitchen` ... `END` | A thing, with its short name and optionally where it starts. |
| ROOM | `ROOM Kitchen "Kitchen"` ... `END` | A place: an object with all twelve exits (Objects). |
| ROUTINE | `ROUTINE Weigh obj, extra` ... `END` | A routine, with parameters separated by commas (Routines). |
| VERB | `VERB "take" "get"` ... `END` | Verb words and their grammar lines (Grammar). |
| EXTEND | `EXTEND "smell" [FIRST]` ... `END` | More grammar lines for a verb that already exists, at the end, or the start with FIRST. |
| REPLACE | `REPLACE SingSub` | The routine of that name declared in the same file replaces any other declaration of it: how a game replaces a library routine. |

Replacing a library routine looks like this:

```
REPLACE SingSub
ROUTINE SingSub
  PRINT "You hum a tune the ferns seem to like."
END
```

## Objects

Everything in the world is an object: rooms, things, characters, the player. Objects form a tree, where an object's parent is where it is. They are numbered 1 upward in the order declared (0 is NOTHING), and `LASTOBJ` is the highest number.

### The body

| Line | Meaning |
| --- | --- |
| `HAS light openable NOT open` | Gives attributes; `NOT` takes one away (useful after a class gave it). |
| `CLASS Door` | Takes a class's attributes and properties first. |
| `IN Kitchen` | Where it starts (also allowed on the OBJECT line). |
| `NAME "brass" "lamp"` | The words a player can call it. A phrase must use only these words; each is matched on 12 letters. |
| `DESC "A battered lamp."` | A property with a value: a number, string, object, routine name or constant expression. Several values make a list: `FOUND_IN Quay Rocks`. |
| `DESC` alone, statements, `END` | A property holding a routine (see below). |

An object no player can name (no NAME line) gets a compiler warning, unless it is a ROOM.

### Routine properties and rule cases

A property name alone on its line, followed by statements and `END`, holds a routine. Inside it, `SELF` is the object. Lines of the form `Action, Action:` open rule cases, which is how `BEFORE`, `AFTER`, `LIFE` and `ORDERS` work:

```
OBJECT Lamp "brass lamp" IN Kitchen
  NAME "brass" "lamp"
  HAS switchable
  BEFORE
    Rub:
      IF self HAS on
        PRINT "The glass is too hot to rub."
        RETURN TRUE
      END
  END
  AFTER
    SwitchOn:  GIVE self light
    SwitchOff: GIVE self NOT light
  END
END
```

A rule case, or a routine property, that runs off its end returns FALSE: "carry on with the action". `RETURN TRUE` stops the action there. A case label is any action name, keywords included (`Give:`, `Remove:`).

### Classes

A CLASS has a body like an object's. An object (or class) that names classes takes their attributes and properties in order, then its own; a later line wins, and `HAS NOT x` removes what a class gave. Classes exist only while compiling: an object can't be asked its class.

### Rooms and exits

Every ROOM gets all twelve exits, `N S E W NE NW SE SW UP DOWN INSIDE OUTSIDE`, set to NOTHING where not given, so any exit can be changed while the game runs. An exit's value can be:

- a room: `N Hall`;
- a door object (one with the `door` attribute and `DOOR_TO`): a closed door stops the player;
- a string, printed instead of moving: `N "The gate is rusted shut."`;
- a routine, which returns a room to go to, NOTHING for no way, or 1 when it has printed its own reason.

```
ROOM Quay "Quay"
  HAS light
  W HarbourRoad
  E
    IF tide_in
      PRINT "The causeway is under water."
      RETURN 1
    END
    RETURN Causeway
  END
END
```

### Reading and changing properties

| Form | Gives |
| --- | --- |
| `obj.weight` | The first word of the property (a number, an object, or a string's or routine's address); 0 if the object has none. |
| `obj.DESC()` | Print or run: a string is printed (result 1), a routine runs with SELF = obj (its result), a value is the result. |
| `obj.LIFE(a, b)` | Calls the routine in the property with arguments; 0 if it holds no routine. |
| `PROPLEN(obj, NAME)` | How many words the property holds. |
| `PROPWORD(obj, NAME, i)` | Word i, from 0. |
| `obj.N = Cave` | Changes the first word. The object must have the property. A string literal stores a string, a routine's name a routine, anything else a value, so a routine exit can become a plain room and back. |

The tree changes with `MOVE obj TO dest` and `REMOVE obj`, and is read with `PARENT()`, `CHILD()`, `SIBLING()` and `obj IN dest`.

## Routines and statements

A routine has up to 16 parameters and locals together. A call passes up to 7 arguments; a parameter not passed starts at 0, and passing more than the routine has is an error. A ROUTINE that runs off its end returns TRUE; a routine property or rule case returns FALSE (Objects).

```
ROUTINE Fact n
  IF n <= 1
    RETURN 1
  END
  RETURN n * Fact(n - 1)
END
```

| Statement | Form | Notes |
| --- | --- | --- |
| LOCAL | `LOCAL total, n` | Local variables, anywhere in the routine; they start at 0. |
| Assignment | `x = expr`, `obj.prop = expr`, `arr(i) = expr` | At the start of a line, `=` always assigns. |
| IF | `IF cond` ... `ELSEIF cond` ... `ELSE` ... `END` | Any number of ELSEIF arms. |
| WHILE | `WHILE cond` ... `END` |  |
| FOR EACH | `FOR EACH c IN obj` ... `END` | Each child of obj in turn; `c` must be a LOCAL. The next child is found after the body runs, so don't move `c` out of obj inside the loop. |
| PRINT | `PRINT item, item, ...` | Prints the items and ends the line. `PRINT` alone prints a blank line. |
| WRITE | `WRITE item, ...` | Prints without ending the line. |
| MOVE | `MOVE obj TO dest` | obj becomes dest's first child. Moving something inside itself is a run-time error. |
| REMOVE | `REMOVE obj` | Takes obj out of the tree. |
| GIVE | `GIVE obj light NOT open` | Sets and clears attributes. |
| RETURN | `RETURN expr` or `RETURN` | `RETURN` alone returns TRUE. |
| PICTURE | `PICTURE n` | Shows picture n above the text (0 hides it); an engine without pictures shows none. |
| A call | `Describe(room)` or `Tidy` | A line that only computes a value is an error: it must do something. |

There is no BREAK or CONTINUE: leave a loop with RETURN from a small routine, or with a flag in its condition.

### Print items

A string literal prints as written. Any other value prints as a number, unless a form in brackets says otherwise:

| Form | Prints | Example |
| --- | --- | --- |
| `(the) obj` | its name with "the" (none for a proper name) | the brass lamp |
| `(The) obj` | the same, capitalised | The brass lamp |
| `(a) obj` / `(an) obj` | with "a" or "an" by its first letter, "some" for a plural | an apple, some coins |
| `(A) obj` / `(An) obj` | the same, capitalised | An apple |
| `(name) obj` | its short name alone | brass lamp |
| `(number) x` | x as a number | 42 |
| `(char) x` | the character with code x | A |
| `(string) x` | the string whose address x holds (a string property, or a routine's result) |  |

The spelling of a form matters: `(the)` and `(The)` differ. TXA has no character literals: `'a'` is a dictionary word, so a character is written as its code (97 for a).

## Expressions

Every value is a 16-bit signed number, -32768 to 32767. Arithmetic wraps around (32767 + 1 is -32768); division truncates toward zero (-7 / 2 is -3), and MOD takes the sign of the left side (-7 MOD 3 is -1). Dividing by zero is a run-time error.

### Operators, loosest first

| Level | Operators | Notes |
| --- | --- | --- |
| 1 | `OR` | Gives 1 or 0; the right side is skipped when the left decides. |
| 2 | `AND` | The same. |
| 3 | `NOT` | 1 if its operand is 0, else 0. |
| 4 | `= <> < > <= >=`, `x HAS attr`, `x HASNT attr`, `x IN obj`, `x NOTIN obj` | Signed comparisons. Comparisons can't be chained: write `a < b AND b < c`. |
| 5 | `+ -` |  |
| 6 | `* / MOD` |  |
| 7 | unary `-` |  |
| 8 | `obj.prop`, `f(args)`, `arr(i)` | Property, call, array element. |

Parentheses group as usual. `NOT x = y` means `NOT (x = y)`.

### What names stand for

| Name | Its value |
| --- | --- |
| A local or global | its value |
| A constant | its number |
| An object or room | its number (1 upward) |
| A routine | its address, so `f = Weigh` then `f(obj, 0)` calls it |
| An array | its number, for `AGET` and `APUT` (an element is `arr(i)`) |
| A picture | its number |
| `TRUE`, `FALSE`, `NOTHING` | 1, 0, 0 |
| `SELF` | the object whose property routine is running |
| `'word'` | that word's number in the dictionary |
| `##Name` | that action's number |
| `"text"` | the string's address: print it with `(string)` |

An array element outside the array, a property changed on an object that lacks it, and a move inside itself are run-time errors. They stop the game with a message such as `[TXA run-time error: index 3 is outside array 4 (0 to 2)]`, the same on every engine.

## Grammar and actions

A VERB gives the words for a verb and the grammar lines that turn a command into an action. Each line is a pattern, `->`, and an action name; the action Name runs the routine `NameSub`, which must exist.

```
VERB "pour"
  held "into" noun -> Pour
  held "in" noun -> Pour
END

ROUTINE PourSub
  IF second <> Lens
    PRINT "That would only waste it."
    RETURN
  END
  PRINT "You fill the reservoir."
END
```

### Grammar tokens

| Token | Matches |
| --- | --- |
| `"word"` | That word. |
| `noun` | One object in scope. |
| `held` | One object, preferring what the player carries; the library's actions take it first if it is not held ("(first taking the lamp)"). |
| `multi` | One or more objects: ALL, lists with AND or commas, ALL BUT. |
| `multiheld` | The same, among what the player carries. |
| `multiexcept` / `multiinside` | Several objects, for PUT ... IN and TAKE ... FROM. |
| `creature` | A character (an object with `animate`). |
| `number` | A number written in digits (0 to 9999), in the global `parsednum`. |
| `topic` | Any words, up to the next fixed word or the end; in `topicwn` (first word) and `topiclen`. |
| an attribute name | One object that has that attribute: `multiheld "in" container`. |
| `noun=Routine` | One object the routine accepts (it gets the object, returns TRUE or FALSE). |
| `scope=Routine` | For now the same as noun=Routine: the routine accepts or refuses objects already in scope. Bringing in objects from outside scope (something far away, a topic object) is not implemented yet. |

A line takes at most two objects. The first becomes `noun`, the second `second`; `REVERSE` after the action swaps them, for lines like `GIVE ADA THE KEY`:

```
VERB "give"
  held "to" creature -> Give
  creature held -> Give REVERSE
END
```

**How lines are chosen.** The parser tries every line of the verb. A line that uses every word wins; one that runs out of words where an object is wanted makes the parser ask ("What do you want to take?"); otherwise the failure that got furthest is reported. A word belongs to one VERB only: to add lines to a library verb, use `EXTEND "verb"`, or `EXTEND "verb" FIRST` to try them before the library's.

**Actions.** During an action the globals `action` (its number, compared with `##Name`), `noun`, `second` and `actor` say what is happening. Rule cases name actions without `##` (`Take:`); code compares numbers with it (`IF action = ##Take`). An action needs a `NameSub` routine even if only rule cases use it.

## Built-in functions

Built-ins are called like routines and their names are reserved. Those that give a value can be used in expressions; the rest are statements.

| Function | Gives | What it does |
| --- | --- | --- |
| `PARENT(o)`, `CHILD(o)`, `SIBLING(o)` | object | o's parent, first child, next sibling; 0 for none. |
| `RANDOM(n)` | 1 to n | A random number. `RANDOM(0)` reseeds at random, `RANDOM(-s)` with seed s (for testing); both give 0. |
| `READKEY()` | key code | Waits for a key. |
| `READ(t, p)` | word count | Reads a line into text array t (t(0) = length, then lower-case characters) and splits it into parse array p, as TOKENIZE. |
| `TOKENIZE(t, p)` | word count | p(0) = count, then three words per word: its dictionary number (0 if unknown), its first character in t, its length. A comma or full stop is a word by itself. |
| `HASATTR(o, a)` | 1 or 0 | `o HAS a` with the attribute as a number. |
| `ISNAME(w, o)` | 1 or 0 | Whether dictionary word w is one of o's NAME words. |
| `FILTERN(w, s, n, d)` | count | Of the first n objects in array s, copies those with NAME word w into array d. The parser's fast filter. |
| `PROPLEN(o, P)`, `PROPWORD(o, P, i)` | number | How many words o's property P holds; word i of it, from 0. |
| `AGET(a, i)`, `APUT(a, i, v)` | value | Element i of the array whose number is a; set it. For arrays passed as values. |
| `ACOPY(s, d, n)` |  | Copies elements 0 to n-1 of array s into array d. |
| `STYLE(n)` |  | Text style: 0 plain, 1 bold, 2 underline, 4 reverse, 8 centred lines; add to combine (`STYLE(9)`). |
| `FRESHLINE()` |  | Ends the line if anything has been printed on it. |
| `CLS()` |  | Clears the text window. |
| `STATUS(r, s, m)` |  | Draws the status line: room r (0: Darkness), score s (-1: none), moves m. The library does this each turn. |
| `SAVE(t)` | 0, 1 or 2 | Saves to the file named in text array t: 1 saved, 0 failed, 2 when a RESTORE comes back here. |
| `RESTORE(t)` | 0 | Restores the file named in t; on success it doesn't return (execution resumes after its SAVE). |
| `UNDOSAVE()` | 1 or 2 | Takes an undo snapshot: 1, or 2 when an UNDO comes back here. |
| `UNDO()` | 0 | Goes back to the newest snapshot; gives 0 only if there is none. |
| `QUIT()` |  | Ends the game. |
| `RESTART()` |  | Starts the game again from the beginning. |
| `SOUND(n)` |  | Plays sound effect n once, over any music. |
| `MUSIC(n)` |  | Plays tune n, looping if it loops; 0 stops it; the tune already playing goes on. |
| `DEBUG()` | 1 or 0 | 1 when the game is being test-played on the workbench: the library's debug verbs work only then. |
| `RECORD(n)`, `REPLAY(n)` | 1 or 0 | Record the commands typed to script n (0-9), or take commands from it; n < 0 stops. The library's RECORD and REPLAY verbs use them. |

SAVE, RESTORE, UNDOSAVE and UNDO are normally left to the library, which wraps them in the SAVE, RESTORE and UNDO commands.

## Working with the standard library

The library does the playing; a game supplies the world and its rules. This section covers what every game touches; the Standard Library Reference will cover the rest (every action, message and routine).

### What a game must and may supply

| Name | Required | What it is |
| --- | --- | --- |
| `ROUTINE Initialise` | yes | Runs once at the start (and after RESTART). Sets `location`; may set `max_score`, start daemons, show a title page, print an introduction. |
| `beforehook = MyRoutine` | no | A routine that sees every action first; RETURN TRUE stops the action. |
| `afterhook = MyRoutine` | no | Sees every action that has happened; RETURN TRUE stops the library's message. |
| `endturnhook = MyRoutine` | no | Runs at the end of every turn. |

Hooks are globals holding routines, set in Initialise, so a game that doesn't want them does nothing.

### The order of an action

1. An order to a character (`Brannock, take the lantern`) goes to its `ORDERS`; otherwise:
2. the game's `beforehook`;
3. the room's `BEFORE`;
4. the object's (`noun`) `BEFORE`;
5. the action's routine (`TakeSub`), which, once the action has happened, calls `AfterRules`: the room's `AFTER`, the object's `AFTER`, the game's `afterhook`. If any returns TRUE, its message replaces the library's.
6. At the end of the turn (not for meta commands such as SCORE or SAVE): `turns` goes up, daemons run, timers count down, the room's `EACH_TURN` runs, then `endturnhook`, the score message, and the status line.

### Globals a game uses

| Global | Meaning |
| --- | --- |
| `location` | The room the player is in. Moving the player: `MOVE player TO Hall` and `location = Hall`. |
| `player` | The player's object (`Yourself`). |
| `score`, `max_score` | Points scored and the most there are (0: the game keeps no score). |
| `deadflag` | Set to 1 (died) or 2 (won) to end the game; the library prints the ending and the score. |
| `turns` | Turns taken. |
| `noun`, `second`, `action`, `actor` | The current action. |
| `lookmode`, `notify_on` | Brief (1), verbose (2), superbrief (3); score messages on or off. |

### Daemons, timers and the title page

| Routine | What it does |
| --- | --- |
| `StartDaemon(o)`, `StopDaemon(o)` | o's `DAEMON` runs every turn while started (up to 32). |
| `StartTimer(o, t)`, `StopTimer(o)` | o's `TIME_OUT` runs t turns from now (the current turn counts). o must declare `TIME_LEFT 0`. |
| `TitlePage(title, byline, blurb)` | Clears the screen, shows the title in bold and the rest centred, waits for a key. byline or blurb may be 0. |

**Pictures and the end of the game.** `ShowPicture(n)` shows picture n (0 none) and remembers it, so RESTORE and UNDO can show it again; a room's `PIC` property shows its picture on arrival or LOOK, and `title_picture` puts one on the title page. When a move sets `deadflag` to 1 or 2, the library's `EndScreen` prints the banner (the string in `endmessage`, or "You have won" / "You have died") and the score, centred, shows `end_picture` if set, and asks: "Would you like to RESTART, RESTORE a saved game, UNDO your last move, or QUIT?" UNDO after a death takes back the fatal move. A game may `REPLACE EndScreen`.

**Music and sound effects.** Declare tunes and effects like pictures, by name and notation file: `MUSIC Harbour "HARBOUR"`, `SOUND Horn "HORN"` (each kind numbered from 1; the files are written in TXA music notation, `.txm`, described in `docs/MUSIC.md`: voices A, B, C and the noise voice N, notes with lengths and dots, octaves, tempo, volume, envelopes, ties and repeats; MIDI files convert to it with `tools/midi2txa`; the older notation, `.mml`, still works). `PlayMusic(n)` starts tune n (0 stops it; the tune already playing goes on) and remembers it for RESTORE and UNDO; `PlaySound(n)` plays an effect once over the music. A room's `TUNE` property plays while the player is there (the property is TUNE because `MUSIC` is the built-in's name). `title_music` and `end_music` give the title page and end screen their own tunes. Players can say MUSIC ON/OFF and SOUNDS ON/OFF. The built-ins underneath are `MUSIC(n)` and `SOUND(n)`.

### Library attributes

| Attribute | Means |
| --- | --- |
| `light` | Gives light: a lit room, a lamp that is on. A room without light (or a light source in it) is dark. |
| `scenery` | Part of the room: never listed, can't be taken. |
| `static` | Fixed in place: listed, can't be taken. |
| `concealed` | Not listed and not chosen by ALL, though it can be named. |
| `container`, `supporter` | Things go in it, or on it. |
| `open`, `openable`, `transparent` | Open now; can be opened and closed; contents visible when closed. |
| `locked`, `lockable` | With `WITH_KEY`: locked now; can be locked. |
| `door` | With `DOOR_TO` and `FOUND_IN`: a door between two rooms. |
| `enterable` | ENTER, SIT ON or GET IN puts the player in or on it. |
| `switchable`, `on` | SWITCH ON / OFF works; on now. |
| `wearable`, `worn` | Can be worn; worn now. |
| `edible` | EAT removes it. |
| `animate` | A character: ASK, TELL, GIVE, SHOW and orders go to its `LIFE` and `ORDERS`. |
| `proper`, `plural` | A proper name (no "the"); plural ("some", "them", "are"). |
| `male`, `female`, `neuter` | Which pronoun refers to it (HIM, HER). |
| `visited`, `moved` | Set by the library: the room has been seen; the object has been carried (its INITIAL no longer shows). |
| `general` | Not used by the library: the game's own flag. |
| `lit` | Declared by the library but not used: the game's to use. |

### Library properties

| Property | On | Holds |
| --- | --- | --- |
| `NAME` | anything | The words a player can call it. |
| `DESC` | anything | Its description (rooms: the room description). |
| `INITIAL` | things | A paragraph shown in the room until the object is first carried. |
| `N` ... `OUTSIDE` | rooms | The twelve exits. |
| `CANT_GO` | rooms | Said instead of "You can't go that way." |
| `EACH_TURN` | rooms | Run (or printed) at the end of every turn there. |
| `BEFORE`, `AFTER` | anything | Rule cases, by action. |
| `LIFE`, `ORDERS` | characters | Rule cases for ASK, TELL, GIVE, SHOW, KISS ...; for orders. |
| `DOOR_TO`, `FOUND_IN` | doors | The two rooms (it leads to whichever the player is not in), or one room, or a routine; the rooms it is in. |
| `WITH_KEY` | lockable things | The key that fits. |
| `CAPACITY` | containers, supporters | How many things fit. |
| `DAEMON`, `TIME_LEFT`, `TIME_OUT` | anything | See above. |

## Limits

The compiler checks every limit and names what was exceeded. "Library uses" is what the standard library takes before a game declares anything.

| Limit | Most | Library uses |
| --- | --- | --- |
| Attributes | 48 | 28 |
| Properties | 63 | 30 |
| Objects (rooms included) | 1000 | 15 (the player and the compass) |
| Globals | 240 | 60 |
| Parameters and locals in one routine | 16 |  |
| Arguments in one call | 7 |  |
| Object slots in one grammar line | 2 |  |
| Letters a dictionary word is matched on | 12 |  |
| A `number` in a command | 0 to 9999 |  |
| The changeable part of the story (objects, globals, arrays, properties) | 16K |  |
| The whole story image | 256K | about 27K |
| Value stack / call frames | 512 words / 1K |  |
| Daemons / timers running at once | 32 / 32 |  |
| A typed command | 160 characters |  |
| A save file on the TI | 5888 bytes (23 sectors) | Lamplight's: 435 bytes |
| UNDO history on the TI | 28K of changes (over a hundred typical turns) |  |

Strings have no fixed length; text is compressed in the story image, so long descriptions cost less than their length.

## Compiler messages

The compiler stops at the first error, naming the file and line; warnings let the game compile. These are its exact words for the commonest mistakes:

| Message | Cause and fix |
| --- | --- |
| `line 9: unknown name Lantern` | A misspelling, or a name never declared. |
| `line 12: missing END` | A block left open. The line given is where the compiler gave up (often the file's end), so look for the IF, WHILE or object above that lacks its END. |
| `line 8: expected a name, found 'room'` | A keyword used as a name; pick another (`here`, `rm`). |
| `line 8: Random is a built-in function and cannot be declared` | A built-in's name, in any case. |
| `line 9: comparisons cannot be chained: use AND` | `a < b < c`: write `a < b AND b < c`. |
| `line 9: the action Dance has no routine DanceSub` | A grammar line names an action with no routine: write `ROUTINE DanceSub`. |
| `line 10: unknown property WEIGHT (declare it with PROPERTY)` | Add `PROPERTY WEIGHT`. |
| `line 11: Two takes 2 arguments, not 3` | Too many arguments (fewer are fine: the rest start at 0). |
| `line 9: this line computes a value and does nothing with it: a statement, call or assignment is needed here` | A line such as `1 + 2` standing alone: it must do something. |
| `line 8: "take" is already a word of another VERB` | Two VERBs share a word: use `EXTEND "take"` to add lines to the library's. |
| `line 10: the loop variable g must be a LOCAL` | FOR EACH over a global: declare a LOCAL for the loop. |
| `line 8: warning: Box has no NAME words, so the player cannot refer to it` | A warning: add a NAME line (or ignore it for objects no player names). |

At run time, the few things the compiler can't catch (an array index out of range, a property changed on an object that lacks it, an object moved inside itself, dividing by zero) stop the game with a `[TXA run-time error: ...]` message, the same on the PC and the TI.

## Appendix: reserved words

None of these can be declared as a name, in any mix of capitals and small letters.

**Keywords (44):** AND, ARRAY, ATTRIBUTE, CLASS, CONSTANT, EACH, ELSE, ELSEIF, END, EXTEND, FALSE, FIRST, FOR, GIVE, GLOBAL, HAS, HASNT, IF, IN, INCLUDE, LOCAL, MOD, MOVE, NAME, NOT, NOTHING, NOTIN, OBJECT, OR, PICTURE, PRINT, PROPERTY, REMOVE, REPLACE, RETURN, REVERSE, ROOM, ROUTINE, SELF, TO, TRUE, VERB, WHILE, WRITE.

**Built-in functions (30):** ACOPY, AGET, APUT, CHILD, CLS, DEBUG, FILTERN, FRESHLINE, HASATTR, ISNAME, MUSIC, PARENT, PROPLEN, PROPWORD, QUIT, RANDOM, READ, READKEY, RECORD, REPLAY, RESTART, RESTORE, SAVE, SIBLING, SOUND, STATUS, STYLE, TOKENIZE, UNDO, UNDOSAVE.

**Made by the compiler:** LASTOBJ (the highest object number), and the grammar arrays VERBTAB, GRAMTAB, ACTSUB and DICTVERB that the parser reads.

**Taken by the standard library.** The library declares its own attributes, properties, globals and routines (the tables in Working with the standard library), so a game can't reuse those names either, the exit properties N to OUTSIDE among them. Because case is ignored, near-misses collide too: the library's status-line routine is `ShowStatus` because `Status` is a built-in, and its containment test is `IsInside` because `INSIDE` is an exit. To change a library routine, `REPLACE` it rather than declaring a new one of the same name.
