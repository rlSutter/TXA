"""stats.py - the workbench's statistics screen (S, M6 part 10), as the
reference: the lines the TI must show for a compile, from the story image
and the compiler's counts.  The spec: "object, word and string counts,
image size, free space by section".  The sections and their limits are the
linker's: the dynamic area (16384 bytes: the engine's undo and save pages),
the tables before the routines (64K: the header holds 16-bit offsets to
them) and the whole image (MAX_IMAGE)."""
from .opcodes import HDR

MAX_IMAGE = 262144
DYN_MAX = 16384
TABLES_MAX = 65536

def lines(img, info):
    w = lambda off: (img[off] << 8) | img[off + 1]
    objects = w(HDR['object_count'])
    words = w(w(HDR['dictionary']))
    size = (w(HDR['image_len_hi']) << 16) | w(HDR['image_len_lo'])
    dyn = w(HDR['dynamic_len'])
    st = info['stats']
    tab = st['tables_end']
    return [
        f"Objects: {objects}.  Dictionary words: {words}.  Routines: {st['routines']}.  Strings: {st['strings']}.",
        f"Story image: {size} bytes of {MAX_IMAGE} ({MAX_IMAGE - size} free).",
        f"Dynamic area: {dyn} bytes of {DYN_MAX} ({DYN_MAX - dyn} free).",
        f"Tables (to the routines): {tab} bytes of {TABLES_MAX} ({TABLES_MAX - tab} free).",
        f"Routines and strings: {size - tab} bytes.",
    ]
