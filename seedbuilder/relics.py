from collections import OrderedDict

_glades = [
    ("Unusually Sharp Spike", "Twice as deadly as the other spikes."),
    ("Withered Fruit", "Gazing at it evokes memories of happier times."),
    ("Fil's Bracelet", "A simple band made of tightly-woven plant fibers."),
    ("Redcap Mushroom", "Eating these is said to help you grow taller."),
    ("Fronkeysbane", "Fronkeys are mildly allergic to this small flower.")
]

_grove = [
    ("Unhatched Spider Egg", "Hopefully it stays unhatched."),
    ("Fallen Branch", "A small, faintly glowing branch of the Spirit Tree."),
    ("Seed Stash", "An innocent squirrel was saving these. What kind of devil are you?"),
    ("Sunpetal", "A beautiful flower native to the Grove area."),
    ("Tiny Spirit Tree", "This replica is incredibly detailed, with a piece of energy crystal in the center.")
]

_grotto = [
    ("Slick Stone", "So smooth and slippery, you can barely hang on to it."),
    ("Broken Keystones", "A pair of keystones, snapped in half"),
    ("Strange Carving", "A creature with snakes on its head, staring at a large plant"),
    ("#*Water Vein* #(Fake)", "It looks just like the real thing! Did Gumo make this?"),
    ("Cloth Mask", "A simple face covering. Belonged to the spirit Leru.")
]

_blackroot = [
    ("Sol's Defused Grenade", "Safe enough to use as a ball! ...right?"),
    ("Torn Friendship Bracelet", "A bond that was made would soon be dissolved."),
    ("Ike's Boots of Fleetness", "He moved swifter than the wind."),
    ("Naru's Chisel", "A skilled artisan could sculpt great works with this tool."),
    ("Glowing Mushroom", "Doubles as a light source and a tasty snack."),
]

_swamp = [
    ("Polluted Water Canteen", "Who would want to drink this?"),
    ("Gold-eyed Frog", "Insects stand no chance against its deft tongue."),
    ("Ilo's Training Weights", "Solid rock, nearly too heavy to carry."),
    ("Spooky Drawing", "Some kind of ghost frog, spitting through walls."),
    ("Rhino Fossil", "Both smaller and cuter than the modern specimen.")
]

_ginso = [
    ("Lightning-Scarred Branch", "As a mother to her child, the Ginso Tree protects the rest of the forest."),
    ("Reem's Lucky Coin", "Said to help you escape the notice of predators."),
    ("Gheemur Shell", "This tough carapace is covered in spikes and seems impervious to harm."),
    ("Hardy Tuber", "Seems to thrive in the moisture here."),
    ("Spirit Lamp", "Glows with a soft, warm light. The string it used to hang from is snapped off.")
]

_valley = [
    ("Treasure Map", "A map depicting a treasure found after a long swim."),
    ("White Raven Feather", "A bit too small to be used as a parachute."),
    ("Comfy Earmuffs", "Softens the sounds of screaming birds and frogs."),
    ("Strange Drawing", "A figure in blue walking through golden fields."),
    ("Abandoned Nest", "Looks like a small family of birds used to live here.")
]

_misty = [
    ("Atsu's Candle", "Does little good in these heavy mists."),
    ("Tatsu's Glasses", "Strange spiral patterns cover both eyes"),
    ("Mushroom Sample", "Still glowing: probably not safe to eat."),
    ("Angry Scribbles", "Left behind by a frustrated cartographer"),
    ("Sister's Lament", "A poem written by Tatsu, mourning her brother Atsu")
]

_forlorn = [
    ("Furtive Fritter", "A favorite snack of the Gumon."),
    ("Mathematical Reference", "Only used by the most cerebral forest denizens."),
    ("Crystal Lens", "Focuses energy into deadly beams of light."),
    ("Magnetic Alloy", "Used by the Gumon to construct floating platforms."),
    ("Complex Tool", "Looks like it might have had several different uses")
]

_sorrow = [
    ("Drained Light Vessel", "The light of the Spirit Tree once filled this orb."),
    ("Tattered Leaf", "Riddled with puncture marks."),
    ("Nir's Sketchbook", "Contains a beautiful drawing of Nibel from the top of Sorrow Pass."),
    ("Tumble Seed", "A small pod dropped by an unusual airborne plant."),
    ("Rock Sharpener", "Extremely worn down. Whoever owned this must have used it a lot.")

]

_horu = [
    ("Obsidian Fragment", "Chipped off of an ancient lava flow."),
    ("Ancient Sketch", "A drawing of what appears to be the Water Vein."),
    ("\"The Fish Stratagem\"", "A record of many tasty recipes involving fish."),
    ("Flask of Fire", "Full of lava! Maybe the locals drink this stuff?"),
    ("Ancient Stone", "Primordial rock from deep beneath the forest's surface, brought upwards by the shifting rocks.")
]

relics = OrderedDict([
    ("Glades", _glades),
    ("Grove", _grove),
    ("Grotto", _grotto),
    ("Blackroot", _blackroot),
    ("Swamp", _swamp),
    ("Ginso", _ginso),
    ("Valley", _valley),
    ("Misty", _misty),
    ("Forlorn", _forlorn),
    ("Sorrow", _sorrow),
    ("Horu", _horu)
])