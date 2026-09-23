"""Version of the orirando <-> apworld seed-data contract (`orirando.data_version`).

Bump by hand on both sides (yaml_emit.DATA_VERSION; test.seedgen_test pins them).
DATA_VERSION += 1 when an older apworld would misread the blob or tables (new
names, new cfg keys, different rule compilation). COMPATIBLE_DATA_VERSION moves
only when older yamls become unreadable. No imports: the server suite loads this file.
"""

# 4: "stones" export + keystone tiers; 5: Mini Health/Energy; 6: tiers on every non-keysanity seed
DATA_VERSION = 6
COMPATIBLE_DATA_VERSION = 1

# yamls emitted before data_version existed came from the only table
# generation that has ever shipped, so they read as version 1
LEGACY_DATA_VERSION = 1


def data_version_problem(cfg):
    """orirando blob -> a sentence naming the fix, or None if readable."""
    raw = cfg.get("data_version", LEGACY_DATA_VERSION)
    try:
        version = int(raw)
    except (TypeError, ValueError):
        return ("its data_version is %r, which is not a version number. "
                "Download the yaml again with the AP YAML button on the "
                "seed page instead of editing it by hand." % (raw,))
    if version > DATA_VERSION:
        return ("it was made for Ori DE Rando apworld data version %d, and "
                "this oride.apworld only understands up to %d. Download the "
                "current one from orirando.com/generator/apworld, put it in "
                "your Archipelago custom_worlds folder replacing this one, "
                "and generate again." % (version, DATA_VERSION))
    if version < COMPATIBLE_DATA_VERSION:
        return ("it is Ori DE Rando apworld data version %d, and this "
                "oride.apworld needs at least %d: the item tables changed "
                "after that yaml was made. Download the yaml again with the "
                "AP YAML button on the seed page -- a fresh yaml for the "
                "same seed works fine." % (version, COMPATIBLE_DATA_VERSION))
    return None
