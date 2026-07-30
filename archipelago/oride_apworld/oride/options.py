from dataclasses import dataclass

from Options import OptionDict, PerGameCommonOptions


class OrirandoData(OptionDict):
    """The seed pairing blob emitted by orirando.com -- not meant to be
    hand-written. Roll a seed with the Archipelago game mode and download
    the paired yaml from the seed page."""
    display_name = "Orirando Seed Data"
    default = {}


@dataclass
class OriDEOptions(PerGameCommonOptions):
    orirando: OrirandoData
