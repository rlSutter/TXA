# Lamplight — Testing

Lamplight is the TXA sample game: fifteen rooms, a tide, a dark cave, an old keeper who has lost his spectacles, and a lighthouse lamp to light before the ship comes in. This document is for testing it on js99er or a real TI-99/4A. It has four parts:

1. **Setup** for the cartridge and the disk version.
2. **The happy path**: the 47 commands that win the game, with what each should say.
3. **The command reference**: everything the game understands.
4. **Further checks**: the editor, the parser, darkness, UNDO, SAVE and RESTORE, loading from disk, speed and the screen.

Every expected response below comes from the reviewed transcripts that the automated tests check on both the Python reference VM and the TI engine, so any difference on real hardware is worth reporting. Tick each box as you go.

---

## 1. Setup

You need an F18A (or PICO9918) and a SAMS card of 512K or more.

### The cartridge: `lamplight8.bin`

- [ ] In js99er: in Settings, turn on the **F18A** and **SAMS** (512K or more). Load `lamplight8.bin` as a cartridge and choose **LAMPLIGHT** from the menu. On the console: put it on the FinalGROM and choose LAMPLIGHT.
- [ ] Mount a disk as **DSK1** (any blank disk image) if you want to test SAVE and RESTORE: saves go to DSK1.

### The disk version: `lamplight.dsk`

- [ ] In js99er: turn on F18A and SAMS, mount `lamplight.dsk` as **DSK1**, and load the **Editor/Assembler** cartridge.
- [ ] Choose option **5** (Run Program File) and type `DSK1.LAMP1`.
- [ ] "Loading" appears with eight dots, one per story file, then the game starts.

### What should appear first

- [ ] **The title page:** a picture of the dark lighthouse at dusk fills the top of the screen; under it **LAMPLIGHT** in bold, centred, with "A TXA sample game", a short blurb, and "Press any key to begin." The top row shows LAMPLIGHT.
- [ ] Any key removes the picture and clears the screen.
- [ ] Any key clears the screen; then a paragraph about the dark lighthouse, the **Harbour Road** description, and a `>` prompt.
- [ ] The top row (reverse video) now shows **Harbour Road** on the left and **Score: 0  Moves: 0** on the right.

---

## 2. What to watch throughout

- [ ] **Typing.** Letters appear in normal light-gray text as you type, with a single reverse-video block as the cursor. After ENTER the line stays on screen as you typed it, in lower case.
- [ ] **The status line** shows the room and "Score: n  Moves: m", updating after each turn; in the dark it says "Darkness".
- [ ] **Room names** appear in bold (bright white).
- [ ] **[MORE]** appears at the bottom only when a response fills the screen; any key continues. On the happy path it should not appear.
- [ ] **Speed.** Most commands answer in about a second. Note any that take more than about three seconds, with a rough time.

---

## 3. The happy path

Type each command and check the response. Where a response has several lines, the first is shown, plus any score or tide message. Arriving in a room shows its name in bold; on a first visit its description follows.

- [ ] 1. `look` — The Harbour Road description again.
- [ ] 2. `n` — **Cottage Kitchen**; a storm lantern hangs by the door, and old Brannock sits by the stove.
- [ ] 3. `x keeper` — White-whiskered and half-blind without his spectacles.
- [ ] 4. `ask brannock about lamp` — "Gone out, has it? I can't climb that stair, not with my eyes. There's oil in the boat shed. Matches in the drawer."
- [ ] 5. `ask him about key` — "The shed key? I've got it somewhere. Find my spectacles and I'll find the key."
- [ ] 6. `take lantern` — Taken.
- [ ] 7. `open drawer` — You open the drawer, revealing a box of matches.
- [ ] 8. `take matches` — Taken.
- [ ] 9. `u` — **Loft Bedroom**; on the nightstand is a pair of spectacles.
- [ ] 10. `take spectacles` — Taken.
- [ ] 11. `d` — **Cottage Kitchen** (short: you have been here).
- [ ] 12. `give spectacles to brannock` — Brannock puts the spectacles on and beams at you, and gives you a key. Then: [Your score has just gone up by 5 points.]
- [ ] 13. `s` — **Harbour Road**
- [ ] 14. `unlock door with key` — You unlock the shed door.
- [ ] 15. `open door` — You open the shed door.
- [ ] 16. `w` — **Boat Shed**; you can see an oil can here.
- [ ] 17. `take can` — Taken.
- [ ] 18. `e` — **Harbour Road**
- [ ] 19. `s` — **Beach**
- [ ] 20. `w` — **Darkness**, then "It is pitch dark, and you can't see a thing."
- [ ] 21. `turn on lantern` — You switch the storm lantern on. Then the cave appears: **Sea Cave**, its description, and "A glass float, round and green, gleams among the stones."
- [ ] 22. `take float` — Taken. Then: [Your score has just gone up by 5 points.]
- [ ] 23. `e` — **Beach**
- [ ] 24. `n` — **Harbour Road**
- [ ] 25. `e` — **Quay**
- [ ] 26. `wait` — Time passes.
- [ ] 27. `wait` — Time passes.
- [ ] 28. `wait` — Time passes.
- [ ] 29. `wait` — Time passes.
- [ ] 30. `wait` — Time passes. Then: The tide is coming in over the causeway.
- [ ] 31. `e` — The causeway is under water. You'll have to wait for the tide.
- [ ] 32. `x sea` — Grey water, high against the stones.
- [ ] 33. `wait` — Time passes.
- [ ] 34. `wait` — Time passes.
- [ ] 35. `wait` — Time passes.
- [ ] 36. `wait` — Time passes. Then: The tide draws back, and the causeway stones show again.
- [ ] 37. `e` — **Causeway**
- [ ] 38. `e` — **Lighthouse Rock**
- [ ] 39. `n` — **Lighthouse Base**
- [ ] 40. `u` — **Spiral Stair** (lit by your lantern; without it, Darkness)
- [ ] 41. `u` — **Watch Room**; on the desk is a logbook.
- [ ] 42. `read log` — The last entry, in a shaky hand: "Wick trimmed. Oil low - fetch from shed."
- [ ] 43. `u` — **Lamp Room**
- [ ] 44. `x lens` — A tower of glass prisms around a wick. The oil reservoir is dry.
- [ ] 45. `light lens with matches` — The wick is dry; it won't take a flame.
- [ ] 46. `pour oil into lens` — You fill the reservoir from the can, and the wick darkens as it drinks. Then: [Your score has just gone up by 5 points.]
- [ ] 47. `light lens with matches` — The lamp is lit and a ship's horn answers. The picture changes to the lighthouse lit, its beams across the water; then, centred, "\*\*\* You have won \*\*\*" and "In that game you scored 25 out of a possible 25, in 47 turns."; then "Would you like to RESTART, RESTORE a saved game, UNDO your last move, or QUIT?"
- [ ] 48. `quit` — "[End of story: press a key]" appears in reverse video at the bottom; any key returns to the TI title screen. The status line reads Score: 25  Moves: 47.

The five waits at the quay (26–30) let the tide come in, so step 31 shows the causeway flooded; the four after it (33–36) let it go out again.

---

## 4. Command reference

Words separated by slashes are synonyms. X and Y stand for things in the game.

### Moving around

| Command | What it does |
|---|---|
| `north` / `n`, `south` / `s`, `east` / `e`, `west` / `w`, `northeast` / `ne`, `northwest` / `nw`, `southeast` / `se`, `southwest` / `sw`, `up` / `u`, `down` / `d`, `in`, `out` | Moves that way, if there's an exit. `go` / `walk` / `run` can come first (`go north`). |
| `go through X` / `go into X` / `enter X` | Goes through a door, or gets into or onto something you can enter. |
| `sit on X` / `lie on X` / `get on X` / `get in X` | Gets onto or into something, like the bed. |
| `exit` / `leave` / `stand` / `stand up` / `get out` / `get off X` / `get out of X` | Gets off or out of what you're on. |

### Looking

| Command | What it does |
|---|---|
| `look` / `l` | Describes the room fully. |
| `examine X` / `x X` / `look at X` / `inspect X` / `describe X` | Describes a thing. Needs light. |
| `look in X` / `search X` | Shows what's inside or on something. |
| `read X` | Reads it (the logbook); otherwise like examining. |

### Handling things

| Command | What it does |
|---|---|
| `take X` / `get X` / `carry X` / `pick up X` / `pick X up` | Picks it up. |
| `take X from Y` / `remove X from Y` / `take X off Y` | Takes it out of or off something. |
| `drop X` / `discard X` / `put down X` / `throw X` | Drops it. |
| `put X in Y` / `put X into Y` / `insert X in Y` | Puts it into a container. |
| `put X on Y` / `put X onto Y` | Puts it on a surface. |
| `open X` / `close X` / `shut X` | Opens or closes a door, drawer or container. |
| `unlock X with Y` / `open X with Y` / `lock X with Y` | Uses a key (the shed door and the iron key). |
| `empty X` | Tips out a container's contents. |
| `turn on X` / `switch on X` / `turn X on` (and `off`) | Lights or puts out the lantern. |
| `wear X` / `don X`; `remove X` / `doff X` / `take off X` | Puts clothing on or takes it off. |
| `eat X` | Eats something edible. |
| `inventory` / `i` / `inv` | Lists what you're carrying, with anything inside it. |

### People (Brannock)

| Command | What it does |
|---|---|
| `ask Brannock about X` / `tell Brannock about X` | He answers questions about the lamp, the key, the shed, his spectacles and the tide. |
| `give X to Brannock` / `give Brannock X` / `offer` / `hand` | Gives him something. His spectacles earn you the key. |
| `show X to Brannock` / `show Brannock X` | Shows him something. |
| `Brannock, X` | Gives him an order, which he politely ignores. |
| `kiss` / `hug`, `wake`, `attack` / `hit`, `answer` / `say ... to Brannock` | Default responses. |

### Added by Lamplight

| Command | What it does |
|---|---|
| `pour X into Y` / `pour X in Y` / `pour X on Y` | Pours the oil into the great lens. |
| `fill X with Y` | The same, the other way round (`fill lens with oil`). |
| `light X` / `light X with Y` | Lights the great lens with the matches once it has oil. |

### Other actions

Mostly a polite default response in this game: `push` / `press` / `shove` / `move` / `shift`, `pull` / `drag` / `tug`, `rotate` / `twist` / `screw` / `unscrew`, `touch` / `feel` / `pat` / `stroke`, `smell` / `sniff`, `listen` / `hear` (or `listen to X`), `taste` / `lick`, `drink` / `sip`, `throw X at Y`, `climb` / `scale` (or `climb up` / `climb over X`), `dig`, `burn` / `ignite`, `cut` / `chop` / `slice`, `tie X to Y`, `fill X`, `wave` (or `wave X`), `squeeze`, `blow X`, `buy X`, `sleep`, `think`, `sing` / `hum` / `whistle`, `pray`, `swim` / `dive`, `jump` / `hop` / `leap` (or `jump over X`), `yes` / `y`, `no`, `sorry`.

### Playing the game

| Command | What it does |
|---|---|
| `wait` / `z` | Lets a turn pass (useful for the tide). |
| `again` / `g` | Repeats your last command. |
| `oops X` | Replaces the unknown word in your last command (after `x keepr`, `oops keeper`). |
| `score` | Shows your score and turns. Takes no time. |
| `verbose` / `long`, `brief` / `normal`, `superbrief` / `short` | Full room descriptions always, on first visits only (the default), or never. |
| `notify on` / `notify off` | Turns the score messages on or off. |
| `undo` | Takes back the last command; repeat to go further back. |
| `save` / `restore` | Asks for a file name (ENTER for SAVE1) and saves to or restores from DSK1. |
| `restart` / `quit` / `q` | Starts again or stops. Both ask first. |
| `version` | Says the game was written with TXA. |
| `pictures on` / `pictures off` | Shows or hides the pictures. |
| `music on` / `music off` | Plays or silences the music. |
| `sounds on` / `sounds off` | Plays or silences the sound effects. |

### Editing keys

| Key | What it does |
|---|---|
| FCTN S (left arrow) | Rubs out the last letter typed. |
| FCTN E (up arrow) | Brings back your previous command; press again for earlier ones (the last 16 are kept). |
| FCTN X (down arrow) | Steps forward again through recalled commands, back to an empty line. |
| FCTN 9 (BACK) | Shows the earlier text (the last 50 lines); FCTN E / FCTN X scroll, ENTER returns. |
| Long commands | Up to 160 characters; a command runs onto a second screen row. |

### Parser shortcuts

| Shortcut | Example |
|---|---|
| `all`, `everything` | `take all`, `drop all` |
| `all but X` / `all except X` | `drop all but the lantern` |
| Lists with `and` or commas | `take lantern and matches`; `take can, float` |
| `it`, `them`, `him`, `her` for what you last mentioned | `x lens`, then `light it with matches` |
| Several commands on one line, split by `.` or `then` | `open drawer. take matches` |
| Articles are optional | `take the lantern` = `take lantern` |
| Answering "Which do you mean…?" | Reply with the distinguishing word. |
| Answering "What do you want to take?" | Reply with just the object. |

---

## 5. Further checks

Start a new game for each group unless it says otherwise. The expected responses were checked against the game.

### 5.1 Typing and the line editor

- [ ] Type `takx`, press FCTN S once, type `e lantern`: the line reads `take lantern`. (In the kitchen: "Taken.")
- [ ] Type in capitals with ALPHA LOCK down: the game understands, and shows the line in lower case.
- [ ] After a few commands, press FCTN E: your last command comes back. Press it again for the one before, then FCTN X to step forward. ENTER runs the recalled command.
- [ ] FCTN X past the newest command gives an empty line.
- [ ] Type a command longer than one screen row (for example `open drawer. take matches. take lantern. i. look. x keeper. ask brannock about tide`): the typing continues onto the second row, and every command runs.
- [ ] Press ENTER on an empty line: "I beg your pardon?"

### 5.1a Scrollback

- [ ] After several commands, press BACK (FCTN 9) at the prompt: the text window shows the same lines, with "Earlier text: FCTN E back, FCTN X forward, ENTER to return" in reverse on the bottom row.
- [ ] FCTN E scrolls back a line at a time, up to about 50 lines; FCTN X scrolls forward again.
- [ ] Bold room names and reversed text come back with their styles.
- [ ] ENTER (or BACK again) returns: the screen is exactly as it was, with anything you had half-typed still there and the cursor after it.
- [ ] With a picture showing, the scrollback uses only the rows under the picture, and the picture stays.

### 5.2 The parser

- [ ] `x keepr`: I don't know the word "keepr". Then `oops keeper`: White-whiskered and half-blind without his spectacles.
- [ ] `g` (after any command): the command runs again.
- [ ] In the kitchen, `open drawer. take matches`: "You open the drawer, revealing a box of matches." then "Taken."
- [ ] In the kitchen, `take all`: Taken. (Only the lantern can be taken there.)
- [ ] With only the lantern held, `drop all but lantern`: There are none at all available!
- [ ] In the kitchen, `take` alone: "What do you want to take?" Then `lantern`: Taken.
- [ ] `brannock, take lantern`: Brannock has better things to do.
- [ ] `take brannock`: I don't suppose Brannock would care for that.
- [ ] `ask brannock about tide`: "Turns every few minutes this time of year. Don't get caught on the stones."
- [ ] `lantern` on its own (a known word, but not a verb): That's not a verb I recognise.
- [ ] `fly` (a word the game doesn't know at all): I don't know the word "fly".
- [ ] `take the moon`: I don't know the word "moon".

### 5.3 Darkness and light

- [ ] Go to the beach (`s` from the start), then `w` without the lantern: **Darkness**, "It is pitch dark, and you can't see a thing." The status line says Darkness.
- [ ] In the dark, `turn on lantern` without carrying it: You can't see any such thing.
- [ ] With the lantern (`n`, `take lantern`, `s`, `s`, `w`): `turn on lantern` shows the Sea Cave; `turn off lantern` gives "It is now pitch dark in here!"
- [ ] Climb the spiral stair with the lantern off: Darkness.
- [ ] In the lit cave, `x stones`: Wet black stones, worn smooth. A glass float lies among them.
- [ ] In the lit cave, the float answers to what a player might call it: `x green thing`, `take something`, `take ball` all work.

### 5.4 Room descriptions and scoring

- [ ] `verbose`, then walk back into a room you have seen: the full description every time.
- [ ] `brief`: revisited rooms show only their name and contents.
- [ ] `superbrief`: rooms show only their name.
- [ ] `score` near the start: You have scored 0 out of a possible 25, in n turns. It takes no turn (Moves does not change).
- [ ] `notify off`: Score notification off. Then earn points (`n`, `u`, `take spectacles`, `d`, `give spectacles to brannock`): no score message appears, but `score` shows "You have scored 5 out of a possible 25, in 5 turns."

### 5.5 UNDO

- [ ] At the very start, `undo`: You can't undo that.
- [ ] `n`, `take lantern`, `u`, `d`, then `undo`, `undo`: each says [Previous turn undone.]; then `look` shows the Cottage Kitchen *with* the lantern gone from the hook (you still hold it) and Moves back by two.
- [ ] In the kitchen, `take lantern`, `drop lantern`, `undo`: [Previous turn undone.], and `i` shows the storm lantern in your hands again.
- [ ] After `restart` (answer `yes`), `undo`: You can't undo that.

### 5.6 SAVE and RESTORE

A disk must be mounted as DSK1. With the cartridge, any blank disk image; with the disk version, `lamplight.dsk` itself has room.

- [ ] `n`, `take lantern`, `save`, then ENTER at "Save to which file? (Enter for SAVE1)": Saved.
- [ ] `drop lantern`, `s`, `e` (move away), then `restore` and ENTER: Restored. `look` shows the Cottage Kitchen and `i` shows the storm lantern.
- [ ] `save` with a name, for example `test1`: Saved. A file `TEST1` appears on DSK1. `restore` with `test1` brings it back.
- [ ] `restore` with a name that doesn't exist (`nofile`): Restore failed. Nothing changes.
- [ ] Save, quit to the title screen, start the game again, `restore`: the saved game comes back.
- [ ] After a restore, `undo`: You can't undo that (a restore starts the undo history again).
- [ ] The cartridge's save and the disk version's save are interchangeable: save in one, restore in the other.

### 5.7 Loading from disk (the disk version)

- [ ] E/A option 5, `DSK1.LAMP1`: "Loading" and eight dots, then the game.
- [ ] Rename or delete one story file (for example `LAMPS03`) on a copy of the disk and load again: the engine stops with "Cannot find DSK1.LAMPS03". A key returns to the title screen.
- [ ] On another copy, delete the picture files (`LAMPP01` to `LAMPP03`) and load: the game plays without its pictures (M6: pictures and music are files of their own).
- [ ] (Optional) On real hardware with TIPI or a CF7 as DSK1: the same.

### 5.8 The end screen

- [ ] At the end screen, answer `dance`: the question is simply asked again.
- [ ] Answer `undo`: [Previous turn undone.] You are back in the Lamp Room before lighting the lamp, with the Lamp Room picture.
- [ ] Light it again, then answer `restart`: the title page, then a new game.
- [ ] Save during a game, win, then answer `restore` (ENTER for SAVE1): Restored, back at the saved point.

### 5.9 Quitting and restarting

- [ ] `quit`, then `no`: Carrying on, then.
- [ ] `quit`, then `yes`: the game ends; "[End of story: press a key]"; a key returns to the TI title screen with normal colours.
- [ ] `restart`, then `yes`: the title page again; a key, then the introduction and Harbour Road, Score 0, Moves 0.

### 5.10 Sound and music

- [ ] The title page plays a slow sea song (three voices: a melody, a bass, soft surf); it stops when you press a key.
- [ ] Harbour Road, the quay, the causeway, the rock, the beach and the gallery play a lively shanty; the cottage, the shed, the cave and the lighthouse are quiet. Walking between two outdoor rooms, the tune carries on without restarting.
- [ ] At the quay, when the tide turns, a swell of surf plays over the music.
- [ ] `light lens with matches` before the oil: a match scratch.
- [ ] Lighting the lamp: the ship's horn, two low notes fading, then a short fanfare with the end screen.
- [ ] `music off`: Music off. Silence, and it stays off in other rooms. `music on`: the room's tune comes back.
- [ ] `sounds off`: Sound effects off. The tide and the horn are silent; the music still plays.
- [ ] Save outdoors, restore indoors (or the reverse): the music matches where you end up. The same after `undo`.
- [ ] `quit` and `restart`: the sound stops cleanly, no stuck note.
- [ ] The music keeps going while the game prints and thinks (it may pause briefly while a picture draws).

### 5.11 Pictures

- [ ] Light the lantern in the Sea Cave: a picture of the cave (daylight at the mouth, the green float glowing) appears at the top, and the text continues below it.
- [ ] Walk out (`e`): the picture disappears and the text uses the whole screen again.
- [ ] Go back in with the lantern on: the cave picture returns. With the lantern off: no picture (it is dark).
- [ ] The Lamp Room shows the great lens, in four colours at full resolution.
- [ ] `pictures off`: Pictures off. The picture disappears and no pictures appear after that. `pictures on`: Pictures on, and the current room's picture comes back.
- [ ] In the cave with its picture: `save` and `restore` — the picture is intact afterwards (disk calls share its memory, and it is redrawn).
- [ ] In the cave, `e` then `undo`: the cave picture comes back.
- [ ] `restart`: no picture until the title page shows its own.
- [ ] Note how long a picture takes to appear (expected: about a second).

### 5.12 Speed and the screen

- [ ] Note the time for `take all` in the kitchen, for `look` in a room with many things, and for crossing the causeway.
- [ ] Walk around until the screen fills and scrolls: the text scrolls smoothly, with bold room names and the reverse status line intact.
- [ ] After any disk operation (SAVE, RESTORE, loading), the screen is unchanged: no stray characters or sprites.

---

## 6. Reporting

A short note is enough for each problem:

- which section and check (for example "3, step 31" or "5.6, second check");
- what you saw instead, and on which setup (js99er or console; cartridge or disk version);
- for slow commands, the command and a rough time.

A photo of the screen helps with anything visual.
