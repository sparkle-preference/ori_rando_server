"""Compiles areas.ori requirement paths into AP access rules.

A connection's paths are OR'd alternatives; each path is a list of tokens
that AND together. Compilation resolves every path to an item-count
requirement dict (or drops it: disabled pathset tag, dead variation flag),
so rules evaluate as state.has_all_counts -- no re-parsing at fill time.
"""
from collections import Counter

from .shared import (SIMPLE_ITEM_TOKENS, LONGFORM_ITEMS, KEY_EVENT_ITEMS,
                     KEY_SHARD_ITEMS, KEYSANITY_TOKENS, VARIATION_TOKENS)


class RuleCompiler:
    def __init__(self, config, warn, ks_tiers=None):
        self.pathsets = set(config.get("pathsets", ["casualCore"]))
        self.variations = config.get("variations", {})
        self.key_mode = config.get("key_mode", "events")
        # non-empty = generic Keystones are in the AP pool, and keystone
        # doors charge their cumulative tier instead of their face cost
        self.ks_tiers = ks_tiers or {}
        self.warn = warn
        self._warned = set()

    def _warn_once(self, token):
        if token not in self._warned:
            self._warned.add(token)
            self.warn("unknown logic token %r treated as unreachable" % token)

    def _apply_ks_tier(self, needs, edge):
        if not self.ks_tiers or "Keystone" not in needs:
            return needs
        tier = self.ks_tiers.get(edge)
        if tier is None:
            # a keystone requirement on an edge the tier table doesn't know:
            # charge the full pool -- over-asking is sound, under-asking locks
            tier = max(self.ks_tiers.values())
            if edge not in self._warned:
                self._warned.add(edge)
                self.warn("keystone requirement on unknown edge %r charged "
                          "the full tier (%s)" % (edge, tier))
        needs["Keystone"] = max(needs["Keystone"], tier)
        return needs

    def compile_paths(self, paths, edge=None):
        """[{tags, reqs}] -> list of Counters (OR of ANDs).

        [] = no valid path (drop the edge); a Counter() present = free.
        """
        if not paths:
            return [Counter()]  # no paths listed = unconditionally free
        out = []
        for path in paths:
            # a path is usable only when every tag it carries is enabled
            if not set(path["tags"]) <= self.pathsets:
                continue
            needs = self.compile_reqs(path["reqs"])
            if needs is None:
                continue
            if not needs:
                return [Counter()]  # a free path dominates all alternatives
            out.append(self._apply_ks_tier(needs, edge))
        return out

    def compile_reqs(self, reqs):
        """Token list -> Counter of item requirements, or None if the path
        is dead under this seed's config."""
        needs = Counter()
        for tok in reqs:
            if tok == "Free":
                continue
            if tok in SIMPLE_ITEM_TOKENS:
                needs[SIMPLE_ITEM_TOKENS[tok]] += 1
                continue
            if tok in LONGFORM_ITEMS:  # bare longform token = count 1
                item = LONGFORM_ITEMS[tok]
                needs[item] = max(needs[item], 1)
                continue
            if "=" in tok:
                base, _, n = tok.partition("=")
                if base in LONGFORM_ITEMS:
                    # mirrors generator.py translate(): count * [code]. Under
                    # keysanity the KS pool is empty, so plain-Keystone paths
                    # die naturally, same as the engine -- no special case.
                    item = LONGFORM_ITEMS[base]
                    needs[item] = max(needs[item], int(n))
                    continue
                self._warn_once(tok)
                return None
            if tok in VARIATION_TOKENS:
                if not self.variations.get(VARIATION_TOKENS[tok], False):
                    return None
                continue
            if tok in KEY_EVENT_ITEMS:
                if self.key_mode == "free":
                    continue
                if self.key_mode == "shards":
                    item, count = KEY_SHARD_ITEMS[tok]
                    needs[item] = max(needs[item], count)
                else:
                    needs[KEY_EVENT_ITEMS[tok]] += 1
                continue
            if tok in KEYSANITY_TOKENS:
                item, count = KEYSANITY_TOKENS[tok]
                needs[item] = max(needs[item], count)
                continue
            self._warn_once(tok)
            return None
        return needs


def make_rule(needs_list, player):
    """list of Counters -> access rule callable, or None for always-true."""
    if any(not needs for needs in needs_list):
        return None
    frozen = [dict(needs) for needs in needs_list]
    return lambda state: any(state.has_all_counts(needs, player) for needs in frozen)
