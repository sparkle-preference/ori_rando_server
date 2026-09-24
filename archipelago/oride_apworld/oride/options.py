from dataclasses import dataclass

from Options import DeathLink, OptionDict, PerGameCommonOptions, StartInventoryPool


class OrirandoData(OptionDict):
    """The seed pairing blob emitted by orirando.com -- not meant to be
    hand-written. Roll a seed with the Archipelago game mode and download
    the paired yaml from the seed page."""
    display_name = "Orirando Seed Data"
    default = {}


@dataclass
class OriDEOptions(PerGameCommonOptions):
    orirando: OrirandoData
    # mirrored from the blob; the bridge reads the seed's params, so editing this changes nothing
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool
