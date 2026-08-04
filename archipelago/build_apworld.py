"""Packages the oride world as oride.apworld for an Archipelago install.

Run from repo root:  python -m archipelago.build_apworld
Output: archipelago/dist/oride.apworld -- drop it in Archipelago's
custom_worlds/ (or worlds/ for a source install).

The zip must hold exactly one top-level folder named like the file, and
everything inside must be reachable through the package loader (pkgutil),
never open() -- there is no filesystem inside a zip.
"""
import io
import json
import os
import sys
import tokenize
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = os.path.join(HERE, "oride_apworld")
PKG_NAME = "oride"
DIST = os.path.join(HERE, "dist")

SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = (".pyc", ".pyo")

REQUIRED_DATA = ("items.json", "locations.json", "graph.json")
# WebHost copies anything under a "/docs/" path out of the zip and serves it;
# the game info page is looked up as "<lang>_<secure_filename(game)>.md", so
# renaming the game means renaming that file (see oride/__init__.py)
REQUIRED_DOCS = ("setup_en.md", "en_Ori_DE_Rando.md")


def collect():
    """-> sorted [(archive name, absolute path)]."""
    files = []
    pkg_dir = os.path.join(PKG_ROOT, PKG_NAME)
    for dirpath, dirnames, filenames in os.walk(pkg_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(SKIP_SUFFIXES):
                continue
            path = os.path.join(dirpath, name)
            arc = os.path.relpath(path, PKG_ROOT).replace(os.sep, "/")
            files.append((arc, path))
    return files


def check(files):
    """Fail loudly here rather than as an import error inside someone's
    Archipelago install."""
    names = {arc for arc, _ in files}
    problems = []
    manifest_arc = "%s/archipelago.json" % PKG_NAME
    if manifest_arc not in names:
        problems.append("missing archipelago.json")
    else:
        with open(dict(files)[manifest_arc]) as f:
            manifest = json.load(f)
        for key in ("game", "compatible_version", "version"):
            if key not in manifest:
                problems.append("manifest is missing %r" % key)
    if "%s/__init__.py" % PKG_NAME not in names:
        problems.append("missing __init__.py")
    for data in REQUIRED_DATA:
        if "%s/data/%s" % (PKG_NAME, data) not in names:
            problems.append("missing data/%s (run archipelago.export_data)" % data)
    for doc in REQUIRED_DOCS:
        if "%s/docs/%s" % (PKG_NAME, doc) not in names:
            problems.append("missing docs/%s (the launcher and website serve "
                            "these; AP's own world test suite requires them)" % doc)
    for arc, path in files:
        if not arc.endswith(".py"):
            continue
        with open(path) as f:
            source = f.read()
        if calls_open(source):
            problems.append("%s calls open(): a zipped apworld has no "
                            "filesystem, read through pkgutil.get_data" % arc)
    return problems


def calls_open(source):
    """Tokenized so comments and strings mentioning open() don't count."""
    skip = (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
            tokenize.INDENT, tokenize.DEDENT, tokenize.STRING)
    previous = None
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in skip:
            continue
        if token.type == tokenize.NAME and token.string == "open":
            if previous is None or previous.string != ".":
                return True
        previous = token
    return False


def main():
    files = collect()
    problems = check(files)
    if problems:
        for problem in problems:
            print("ERROR: %s" % problem)
        return 1
    if not os.path.isdir(DIST):
        os.makedirs(DIST)
    out = os.path.join(DIST, "%s.apworld" % PKG_NAME)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for arc, path in files:
            zf.write(path, arc)
    print("%s (%s files, %.1f KB)" % (out, len(files), os.path.getsize(out) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
