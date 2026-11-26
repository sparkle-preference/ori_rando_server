"""The default practice segments: every .bfrp in practice_defaults/, fetched by clients that lack them."""
import hashlib
import os
import re
import zipfile

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "practice_defaults")
EXT = ".bfrp"
ORDER = "order.txt"
RETIRED = "retired_demos.txt"


def defaults():
    """Their names, without the extension: order.txt's first, as listed, then the rest alphabetically."""
    if not os.path.isdir(DIR):
        return []
    names = sorted((f[:-len(EXT)] for f in os.listdir(DIR) if f.endswith(EXT)), key=str.lower)
    by_lower = {name.lower(): name for name in names}
    first = []
    for listed in order():
        name = by_lower.get(listed.lower())
        if name is not None and name not in first:
            first.append(name)
    return first + [name for name in names if name not in first]


def order():
    """order.txt's names as written, one a line, the extension optional; none without the file."""
    path = os.path.join(DIR, ORDER)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        lines = [line.strip() for line in f]
    return [line[:-len(EXT)] if line.endswith(EXT) else line for line in lines if line]


def default_path(file):
    """The path of practice_defaults/<file>, or None for a name the listing doesn't hold."""
    if file.endswith(EXT) and file[:-len(EXT)] in defaults():
        return os.path.join(DIR, file)
    return None


def retired_demos():
    """retired_demos.txt's SHA-1s (each line's first word; # starts a comment), less any still shipped. A client
    swaps a delivered default's demo ghost for the current one only while its own is on this list."""
    path = os.path.join(DIR, RETIRED)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        words = [line.split("#", 1)[0].split() for line in f]
    hashes = [w[0].lower() for w in words if w and re.fullmatch(r"[0-9a-fA-F]{40}", w[0])]
    shipped = shipped_demos()
    return [h for h in dict.fromkeys(hashes) if h not in shipped]


def shipped_demos():
    """The SHA-1 of every demo ghost, root or variant, in the .bfrp files served now."""
    found = set()
    for name in defaults():
        with zipfile.ZipFile(os.path.join(DIR, name + EXT)) as z:
            for entry in z.namelist():
                if re.fullmatch(r"(variants/[^/]+/)?ghosts/demo\.ghost", entry):
                    found.add(hashlib.sha1(z.read(entry)).hexdigest())
    return found
