from dataclasses import dataclass

from Options import DeathLink, OptionDict, PerGameCommonOptions


class OrirandoData(OptionDict):
    """The seed pairing blob emitted by orirando.com -- not meant to be
    hand-written. Roll a seed with the Archipelago game mode and download
    the paired yaml from the seed page."""
    display_name = "Orirando Seed Data"
    default = {}


@dataclass
class OriDEOptions(PerGameCommonOptions):
    orirando: OrirandoData
    # set on orirando.com; the emitted yaml mirrors the blob's death_link
    # into it. The bridge reads the seed's own params, so editing this alone
    # changes nothing in game.
    death_link: DeathLink
