"""Compatibility version of the orirando <-> apworld seed-data contract.

Every yaml orirando.com emits carries `orirando.data_version`. This build
reads yamls from COMPATIBLE_DATA_VERSION through DATA_VERSION and refuses
anything else with a sentence naming the fix, instead of dying somewhere
downstream in a table lookup that was never going to succeed (an item or
location name a newer server invented is a bare KeyError otherwise).

BUMP RULE -- by hand, on BOTH sides. The emitter's copy lives in
archipelago/yaml_emit.py; test.seedgentest asserts the two agree, so a
one-sided bump fails the server suite rather than shipping.

  * DATA_VERSION += 1 whenever the emitted blob or the shipped data tables
    change in a way an older apworld would misread: new item or location
    names, a new cfg key the world has to honor, different rule
    compilation. Appending ap_ids counts -- an old apworld has never heard
    of the new name.
  * COMPATIBLE_DATA_VERSION only moves when a change makes older yamls
    genuinely unreadable. Raising it invalidates every yaml testers are
    already holding, so additive changes leave it alone.

No imports here on purpose: the server's test suite loads this file
directly, without Archipelago on the path.
"""

DATA_VERSION = 3
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
