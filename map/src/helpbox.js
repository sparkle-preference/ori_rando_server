import React from 'react';
import {CardText, CardTitle, Card, CardBody, CardSubtitle} from 'reactstrap';


//const DbashWarning = (<CardText className="border font-weight-bold border-danger">Warning: This logic mode can require chained double bashes!</CardText>)

const noneTitle = "Confused?";
const noneSub = "Mouse over anything to learn more!";
const noneLines = ["Additional context-specific information will appear here as you interact with the UI."];

const getHelpContent = (category, option) => {
	let lines = noneLines;
    let title = noneTitle;
	let subtitle = noneSub;  
	let extra = [];
	switch(category ) {
		case "logicModes":	
			subtitle = "Logic Modes"
			switch(option) {
				case "casual":						
					title =  "Casual" 
					lines = ["Casual is the easiest logic mode, intended and recommended for players who have never done a speedrun of Ori."]
					break;
				case "standard":						
					title = "Standard"
					lines = [ 
						"Standard is the default randomizer logic mode, intended for users who are familiar with Ori movement and basic speedrunning tech. The community weekly races use this logic mode.", 
						"Recommended for players who have speedrun Ori before, or have played Casual seeds and want something a bit more complicated."
					]
					break;
				case "expert":						
					title = "Expert"
					lines = [
						"Expert is far more difficult than Standard. It can require tedious, more difficult, and more annoying techniques, including several pieces of area-specific knowledge.", 
						"Recommended for experienced Ori Randomizer players."
					]
					break;
				case "master":						
					title = "Master"
					lines = [
						"Master is even more difficult than Expert, and is only recommended for players looking to push the game to the limit. Master seeds frequently require several extremely difficult or obscure tricks, including very long double bash chains.", 
						"Selecting this logic mode will set the path difficulty to Hard and enable the Starved variation."
					]
//					extra.push(DbashWarning)
					break;
				case "glitched":						
					title = "Glitched"
					lines = [ 
						"Glitched is the hardest logic mode in the game, and not recommended for most players. In addition to everything that Master requires, it requires knowledge of the game's various out-of-bounds tricks and other unsafe paths.",
						"This logic mode also contains paths that require timed level-ups, farming for ability points, and various tricks that potentially softlock your save file (or the game) if done incorrectly.",
						"Selecting this logic mode will set the path difficulty to Hard.",
					]
//					extra.push(DbashWarning)
					break;
				case "custom":
					title = "Custom"
					lines = [ 
						"Custom is the Logic Mode for any user-specified set of logic paths.",
					]
					break;
				default:
					break;
			}
			lines.push("For more detailed info about Logic Modes, check out the help sections inside the Logic Paths tab")
			break;
        case "goalModes":
            subtitle = "Goal Modes"
            switch(option) {
				case "None":
					title = "None"
					lines = [
						"Selecting this option creates a seed with no Goal Mode; the final escape can be accessed at any time."
					]
					break;                
				case "ForceTrees":
					title = "Force Trees"
					lines = [
						"The Force Trees Goal Mode requires players to visit all ten skill trees before completing the game. As a side-effect, it makes Ginso Tree access mandatory, as the Bash tree cannot be reached without it.", 
						"Force Trees is the default Goal Mode, and is a good starting point for new players.",
					]
					break;                
				case "ForceMapStones":
					title = "Force Maps"
					lines = [
						"The Force Maps Goal Mode requires that you turn in all 9 mapstones before finishing the game. As a side-effect, it makes Forlorn Ruins access manditory.",
                        "Force Maps is recommended for players looking for something new to try, and for cartographers everywhere."
					]
                    break;
				case "WorldTour":
					title = "World Tour"
					lines = [
						"The World Tour Goal Mode selects 8 zones at random, and places a Relic in a random location in each of those zones. Relics are special pickups with unique flavor text, and collecting all 8 of them is required to access the final escape.",
                        "You can learn which zones contain Relics and check what Relics you have already collected by pressing alt+4, configurable via RandomizerKeybindings.txt.",
                        "World Tour is intended for players who wish to see more of the game world, including less-visited zones like Forlorn and Horu, and can be played with any Key Mode, through Shards is recommended. You can configure the number of Relics (1-11, default 8) in the Advanced Tab of the seed generator."
					]
                    break;
				case "WarmthFrags":
					title = "Warmth Fragments"
					lines = [
						"The Warmth Fragments Goal Mode scatters a large number of fragments (default 40) across the entire map. Players must collect a certain number of those fragments (default 30) to access the final escape.",
						"The total number of fragments, as well as the number of 'extra' (non-required) fragments, can be configured in the Advanced Tab of the seed generator.",
						"Warmth Fragments is recommended for players who like exploring and efficiently checking large numbers of pickups in an unstructured manner, and plays well with most Key Modes, including Free."
					]
                    break;
                default:
                    break;
            }
            break;
		case "variations":
			subtitle = "Variations"
			switch(option) {
				case "Starved":
					title = "Starved"
					lines = [
						"The Starved variation reduces the probability that players will be given skill pickups, unless one is needed to proceed. This tends to create more linear seeds, where each skill gives access to the area or areas where the next skill or important item will be found.",
						"Recommended for everyone at least once, and for players who enjoy more linear pathing or constrained situations. Note that the Balanced fill algorithm can sometimes interfere with Starved."
					]
					break;
				case "NonProgressMapStones":
					title = "Discrete Mapstones"
					lines = [
						"The Discrete Mapstone variation changes how mapstones function, making each individual mapstone turn-in have its own pickup. (By default, the mapstone pickups are granted based on the number of mapstones you have turned in, regardless of where).",
						"This variation exists primarily for legacy reasons and is not recommended for normal use. It cannot be enabled without the StrictMapstones variation."
					]
					break;
				case "Hard":
					title = "Hard Mode"
					lines = [
						"The Hard Mode variation removes all health cells and all but 3 energy cells from the pool of available items, capping your health at 3 and energy at 4 for the entire seed. Additionally, it removes all bonus pickups from the pickup pool.",
						"Due to these restrictions, it is incompatible with logic paths that require taking 3 or more damage (dboost, dboost-hard, extended-damage, and extreme), and the Extra Bonus Pickups variation.",
						"Recommended for people who hate feeling safe and like to live on the edge."
					]
					break;
				case "OHKO":
					title = "One-Hit KO"
					lines = [
						"The One-Hit KO variation causes any amount of damage Ori takes to be instantly lethal. It is incompatible with all logic paths that require damage boosts.",
						"NOTE: this variation is rarely used and thus is less tested than most. Tread carefully!"
					]
					break;
				case "0XP":
					title = "0 Experience"
					lines = [
						"Inspired by the incredibly unpopular 0exp speedrunning category, the 0 Experience variation prevents Ori from ever gaining levels or acquiring experience. Experience dropped by enemies will kill Ori on contact!",
						"Recommended for anyone who watched a 0xp run and thought it seemed fun."
					]
					break;
				case "Entrance":
					title = "Entrance Shuffle"
					lines = [
						"The Entrance Shuffle variation remaps each door (the dungeon entrances and the 8 Horu side rooms) in the game to go to another door instead. Recommended for anyone who likes being confused, or is interested in spending more time in Horu than usually necessary."
					]
					break;
				case "BonusPickups":
					title = "More Bonus Pickups"
					lines = [
						"More Bonus Pickups introduces several new bonus pickups not normally found in the randomizer, including some new activateable skills.",
						"Recommended for people interested in trying out some cool and probably pretty overpowered pickups.",
						"Note: The default bindings for bonus skills are Alt+Q to swap between them, and Alt+Mouse1 to activate them. These bindings can be changed in the RandomizerRebinding.txt file.",
						'Note: The "ExtremeSpeed" and "Gravity Swap" pickups are toggleable: activating them will turn them on, and cost energy over time. They will automatically turn off if you run out of energy.'
					]
					break;
                case "DoubleSkills":
					title = "Extra Copies"
					lines = [
						"The Extra Copies variation adds an extra copy of most skills and world events (though not the dungeon keys) to the item pool, causing 2 of each of these items to be placed on the map.",
                        "Recommended to reduce the frustration inherent in searching for one specific item. Combos well with Key Mode: Free."
					]
					break;
                case "StrictMapstones":
					title = "StrictMapstones"
					lines = [
						"The Strict Mapstones variation forces the seed generator to place a mapstone for every reachable mapstone pedistal.",
                        "Strict Mapstones is required for Discrete Mapstones (since otherwise Discrete Mapstones could softlock players by not providing enough maps).",
                        "This variation represents the pre-3.0 default behavior, and is not generally recommended due to how predictable it makes early game mapstone placements."
					]
					break;
                case "Open":
					title = "Open Mode"
					lines = [
						"The Open Mode variation makes several changes with the primary aim of making the dungeons more accessable. Major changes: ",
                        "> Horu and Ginso Teleporters have been added to the item pool",
                        "> Horu starts with the lava already drained, allowing TP access to the entire dungeon.",
                        "> The second Ginso miniboss room has both lower doors opened by default, allowing TP access to most of the dungeon. (The lowest two pickups are blocked by the first miniboss)",
                        "> The first keystone door in Glades is always open",
                        "> Keystone doors can be opened from behind",
                        "Open Mode is enabled by default and recommended for all players and modes."
					]
					break;
				default:
					break;
			}			
			break;
		case "keyModes":
			subtitle = "Dungeon Key Modes"
			switch(option) {
				case "Shards":
					title = "Shards"
					lines = [
						"In Shards, the dungeon keys are replaced with dungeon key shards. Each key has 5 shards on the map, but only 3 are needed to assemble the full key. Shards cannot generate within the dungeon they unlock.",
                        "To prevent dungeon teleporters from invalidating the shard hunt, the Forlorn, Horu, and Ginso teleporter pickups now require 2 shards of their respective dungeon keys before they activate.",
						"Recommended for: experienced players, Co-op, and players who enjoy exploring and checking lots of pickups."
					]
					break;
				case "Clues":
					title = "Clues"
					lines = [
						"In Clues, the dungeon keys are placed randomly throughout the map. Every 3 skill trees you visit, the game will tell you which zone you can find one of the keys in. You can check your currently unlocked hints (as well as tree, mapstone, and overall progress) by pressing alt+p.",
						(<div>Note: A map of the Zones is available <a target="_blank" rel="noopener noreferrer" href="https://i.imgur.com/lHgbqmI.jpg">here</a>.</div>),
						"Recommended for: newer players, players who like exploring, but don't want to check every pickup"
					]
					break;
				case "Limitkeys":
					title = "Limitkeys"
					lines = [
						"In Limitkeys, the dungeon keys are placed randomly at one of the Skill Trees or World Event locations (the vanilla locations for the Water Vein, Gumon Seal, and Sunstone, Wind Restored at the start of the Forlorn Escape, and Clean Water at the end of the Ginso Escape.)",
						"Recommended for: newer players, players who dislike hunting for dungeon keys once they have the skills they need."
					]
					break;
                case "Free":
                    title = "Free"
                    lines = [
                        "As the name implies, Key Mode Free gives the player all 3 dungeon keys for free upon picking up the first energy.",
                        "Recommended for use with the Warmth Fragments and World Tour goal modes, or for anyone who would prefer to skip the Dungeon Key hunt."
                    ]
                    break;
				case "None":
					title = "None"
					lines = [
						"In None, the dungeon keys are placed randomly throughout the map. No constraints or info is given to help find them.",
						"Recommended for: masochists, people with too much free time."
					]
					break;
				default:
					break;
			}
			break;
		case "multiplayerOptions":
			subtitle = "Multiplayer Options"
			switch (option) {
				case "playerCount":
					title = "Player Count"
					lines = [
						"The number of players in the multiplayer game.",
						"For a coop game, set this to the number of players in the game. Note that games with more people will have less relevant pickups for each individual player (see Co-op below for more details)",
						"For a tracked race, set the mode to Race and this to the number of people in the race to give them each their own tracked icon on the map."
					]
					break;
				case "syncSeedType":
					title = "Co-op Seed Generation Mode"
					lines = [
						"These options change how the randomizer builds co-op seeds.",
						"Since some pickups in multiplayer seeds are shared, the seeds each player gets will be missing some of the shared pickups, to be granted when an ally finds it instead.",
						"Cloned Seeds are made by generating one seed and then splitting up each shared item between players, while leaving the rest of the item the same for all players.",
						"Seperate Seeds generate completely different seeds for each player, with the shared items distributed randomly between all players.",
						"Mouse over the modes to learn more about them!"
					]
					break;
				case "multiGameType":
					title = "Multiplayer Game Type"
					lines = [
						"These options specify which kind of multiplayer game is generated.",
						"A Co-op game creates different seeds for each player in the game (see the help for Seed Generation Modes for more info). Items in the selected Shared Item Categories will be shared between players when found.",
						"A Race creates 1 copy of the generated seed for each player, each with a different player ID. This creates a map that can be used to watch all the players racing at once!",
					]
					break;
				case "Cloned Seeds":
					title = "Cloned Seeds"
					subtitle = "Co-op Seed Generation Modes"
					lines = [
						"Cloned Seeds are made by generating a single player seed and then splitting up each shared item between players, while leaving the rest of the items the same for all players.",
						"For each item to be shared in the original seed, one player is chosen at random. That player will find that item at its intended location; all other players will find Warmth Returned there instead, letting them and their allies know that a shared item is at that location for some other player. ",
						"If hints are enabled below, other players will instead get a message indicating the type of the shared item found at that location, as well as the player who the pickup is for. Check the hints help section for more info and some recommendations.",
						"Because Cloned Seeds are mostly identical, they are ideal for co-op games where all players can talk to each other, so that they can coordinate checking different areas and share the locations of shared items for other players. Shards and Clues are both great Dungeon Key Modes for Cloned Seeds.",
					]
					break;
				case "Seperate Seeds":
					title = "Seperate Seeds"
					subtitle = "Co-op Seed Generation Modes"
					lines = [
						"Seperate Seeds are made by simulataneously generating a seed for each player in the game. Each shared item is only assigned to one player; once it becomes accessable for one player, it will be in the logic for both of them.",
						"Because the seeds for each player are generated seperately, the progression paths of each player will be different, though they will at certain points rely on each other.",
						"For Seperate Seeds, player communication is not as important, as no information gained by one player will be relevant to the others (besides informing them of shared pickups they have, which the game does already).",
						"Seperate Seeds work best when individual shared items don't block progression for other players.",
                        "Recommended settings: Do not share skills (or teleporters), do share upgrades, world events, and misc, set the dungeon key mode to either Shards or Free, and set the Goal Mode to either Warmth Fragments or World Tour."
					]
					break;
				default:
					break;					
			}
		break;

		case "Shared Item Categories":
			subtitle = "Shared Item Categories"
			switch(option) {
				case "Teleporters":
					title = "Share Teleporters"
					lines = [
						"With Share Teleporters enabled, teleporter unlock pickups for one player will also unlock those teleporters for all other players.",
						"Shared teleporters will be taken into account by the logic, so it is important to keep in mind what teleporters your allies have found.",
						"Note: this does not share teleporters activated manually by players, just the pickups that unlock them automatically."
					]
					break;
				case "Skills":
					title = "Share Skills"
					lines = [
						"With Share Skills enabled, skills will be shared between players when found.",
						"Skill sharing is great for Cloned Seeds, but can be frustrating in Seperate Seeds, particularly with more players, as it can lead to situations where 1 player needs to find a skill before the others can do anything."
					]
					break;
				case "Misc":
					title = "Share Miscellaneous Items"
					lines = [
						"With Share Misc enabled, Warmth Fragments and World Tour Relics are shared between players, if they exist.",
						"Sharing Relics and Warmth Fragments will greatly reduce the amount of time an average co-op seed will take to complete."
					]
					break;
				case "World Events":
					title = "Share World Events"
					lines = [
						"With Share World Events enabled, the 3 Dungeon Keys (or Shards), Clean Water, Wind Restored, and Warmth Returned will be shared between players when found.",
						"Sharing World Events is recommended for every co-op game varient, though it is less interesting in certain Dungeon Key modes (*cough*limitkeys*cough*)."
					]
					break;
				case "Upgrades":
					title = "Share Upgrades"
					lines = [
						"With Share World Events enabled, all permenant upgrades (or bonuses) will be shared between players when found.",
						"All upgrades besides Mega Health and Mega Energy are considered permenant upgrades, including everything unlocked by the 'More Bonus Pickups' variation.",
						"There are more upgrades than there are items in any other shared item category. It is disabled by default because it can make Cloned Seeds tedious to check, even when Hints are enabled."
					]
					break;
				case "Hints":
					title = "Hints"
					lines = [
						"A variation for Cloned Seeds, this option adds hints that display when player picks up an item that contains a shared item for one of the other players.",
						"Instead of seeing Warmth Returned, players will instead see the share type of the item in question. In games with more than 2 players, the hint will also specify which player has the pickup in their seed.",
						"Without hints, Cloned Seeds work best with fewer players (more than 3 can lead to a lot of duplicate checking) and fewer overall shared items (shared upgrades not recommended).",
						"With hints, however, the number of players and shared pickups can both be higher without issue; knowing the pickup type helps distinguish between which shared pickups are important.",
					]
					break;
				default:
					break;
			}
		break;
        case "advanced":
            subtitle = "Advanced Options"
            switch(option) {
                case "pathDiff":
					title = "Path Difficulty"
					lines = [
						"Path difficulty influences the likelihood that higher difficulty logic paths will be selected when the randomizer selects forced progression paths.",
						"When set to Hard, paths from higher difficulty logic groups are far more likely to be selected. When set to easy, the opposite is true.",
						"Path difficulty is set to Hard by default in the Master and Glitched logic modes. Leaving it set to normal is recommended otherwise."
					]
                    break;
				case "fragCount":
					title = "Warmth Fragment Count"
					lines = [
						"Set the number of Warmth Fragments that appear on the map here. The more fragments there are, the easier they will be to find."
					]
                    break;
				case "fragRequired":
					title = "Required Fragment Count"
					lines = [
						"Set the number of Warmth Fragments that are required to finish the game here.",
                        "The closer the required fragment count is to the total fragment count, the longer and more tedious the search for fragments becomes"
					]
                    break;
				case "relicCount":
					title = "Relic Count"
					lines = [
						"Set the number of zones that will contain Relics here. There are 11 zones in total.",
                        "Note that numbers lower than 8 are not generally recommended."
					]
                    break;
				case "expPool":
					title = "Experience Pool"
					lines = [
						"This number controls the total amount of experience that will be placed in the experience pickups throughout the game.",
                        "Regardless of the number of exp pickups, the total amount of EXP on the map will always be this number.",
                        "Change it only if you are interested in seeing how the game plays with more (or less) total experience available"
					]
					break;
                case "fillAlg":
					title = "Fill Algorithm"
					lines = [
						"Change the algorithm used to place items during seed generation here. At the moment, only two Fill Algorithms are available, Balanced and Classic"
					]
                    break;
                case "fillAlgClassic":
					title = "Classic Algorithm"
					lines = [
						"The Classic fill algorithm places pickups throughout the world one at a time and mostly at random (though subject to logical constraints).",
                        "It is only recommended for players who are using the Starved flag and don't want to risk the Balanced algorithm interfering with this."
					]
                    break;
                case "fillAlgBalanced":
					title = "Balanced Algorithm"
					lines = [
						"The Balanced fill algorithm is an improved version of the Classic algorithm that insures a more balanced placement of progression items.", 
                        "It does this by swapping newly placed progression items with 'useless' (exp, bonus pickups, etc) items that were placed earlier, creating a more even distribution of skills and other progression items throughout the seed",
                        "Balanced is the default algorithm and recommended in most cases. However, the swaps it makes can result in easier or less linear Starved seeds, as skills can be made available earlier than the progression path originally intended."
					]
                    break;
                case "preplacement":
					title = "Forced Item Placement"
					lines = [
                        (<div>You can use these fields to control what the first 4 pickups of your seed will be! Use the codes found <a target="_blank" rel="noopener noreferrer" href="https://github.com/turntekGodhead/ori_rando_server/blob/master/map/src/shared_map.js#L266">here</a> (no quotes) to specify the pickups you wish to recieve.</div>),
                        "(Future versions of this feature will allow users to select pickups from a list instead of typing their item codes)",
                        "Note that some item combinations (like 4 mapstones in standard logic) can result in an uncompleteable seed.",
                        "This feature is primarily intended for generating seeds to practice specific skill combinations, like Bash+Grenade or Grenade Jumps"
					]
                    break;
                case "cellFreq":
					title = "Forced Cell Frequency"
					lines = [
						"The Forced Cell Frequency number is the maximum number of pickups that can be placed without adding at least 1 Health and Energy cell. Defaults: 20 for Casual, 40 for Standard, and 256 (disabled) for all other difficulties.",
                        "Lower numbers usually means easier access to health and energy, particularly early game. Numbers below 15 are not recommended.",
                        "The standard setting, 40, has minimal impact on most seeds, but can prevent extremely rare situations where most health and energy cells are unreachable for the majority of the seed."
					]
                    break;
                default:
                    break;
            }
        break;
		case "general":
			subtitle = "General Options"
			switch(option) {
				case "logicModes":
					title = "Logic Modes"
					lines = [
						"Logic modes are sets of logic paths tailored for specific play experiences. Some logic modes, such as Hard or OHKO, also have associated variations that will be applied on selection.",
						"Changing the logic mode will have a major impact on seed difficulty.", 
						"Mouse over a logic mode in the dropdown to learn more about it."
					]
					break;
				case "goalModes":
					title = "Goal Modes"
					lines = [
						"Goal Modes are a special kind of Variation that limit access to the final escape until a secondary objective has been completed.",
						"Goal Modes have a major impact on how the game is played. The most popular Goal Modes are Force Trees and World Tour.", 
						"Mouse over a goal mode in the dropdown to learn more about it."
					]
					break;
				case "advanced":
					title = "Advanced Options"
					lines = [
						"The Advanced Options tab contains a variety of settings for power users, including the ability to modify parameters for the World Tour and Warmth Fragments modes, and force seeds to start with specific pickups.",
						"Mouse over the various options within to learn more.", 
					]
					break;
				case "keyModes":
					title = "Dungeon Key Modes"
					lines = [
						"Dungeon key modes change how the 3 dungeon keys (the Watervein, Gumon Seal, and Sunstone) are acquired. Since the Sunstone is always required, and the Water Vein is required by default (see Forcetrees under Variations for more info), placement of the Dungeon Keys matters a fair bit.",
						"New players should start with Clues or Limitkeys."
					]
					break;
				case "seedTab":
					title = "Seed Tab"
					lines = [
						"View and download your generated seed here!"
					]
                break;
				case "variations":
					title = "Variations"
					lines = [
						"Variations introduce additional restrictions on how the game is played or how the seed is generated.",
						"Note: Some variations are not compatible with certain logic paths."
					]
					break;
				case "multiplayer":
					title = "Multiplayer Options"
					lines = [
						"Enable Multiplayer and configure Multiplayer options with this tab."
					]
					break;
				case "logicPaths":
					title = "Logic Paths"
					lines = [
						"Logic paths are groups of rules that specify what areas and pickups Ori is expected to be able to get to under different circumstances.",
						"By default, the enabled logic paths are set by selecting a logic mode. Adding or removing logic paths after that changes the mode to 'Custom'",
						"Mouse over the logic path groups for more info."
					]
					break;
				case "Seed":
					title = "Seed"
					lines = [
						"The Seed field is used as a starting point for the generator's RNG. This means that if you use the same Seed and leave all other options the same, you will get end up with the same randomizer.dat file every time.",
						"A seed value is auto-generated, so you can leave this field without issue."
					]
				break;
				case "WebTracking":
					title = "Web Tracking"
					lines = [
						"With Web Tracking enabled, the randomizer will send updates to the server as you play the game. Seeds downloaded with Web Tracking enabled have a special Sync flag, which is used by the server to identify and track that game.",
						"Web tracking is required for the Map tracker to function properly and for all multiplayer modes."
					]
				break;
				default:
					break;
			}
			break;	
		case "logicPaths":
			subtitle = "Logic Paths"
			switch(option) {
				case "normal":
					title = "Normal"
					lines = [
						"The Normal logic paths specify the intended mechanics of the game: Using wall jump to climb walls, bash to get through Ginso, Keystones to open doors, and energy cells to open Energy doors.",
						"It also contains a few interactions players may not have seen in a casual playthrough, such as using Stomp to break barriers.",
						"These logic paths are enabled by default in every logic mode, and cannot be disabled."
					]
					break;
				case "speed":
					title = "Speed"
					lines = [
						"The Speed logic paths specify the kinds of tricks that one might learn when doing a no-OOB speedrun of Ori.",
						"Examples: using Double Jump to get the Ability Cells in Spirit Caverns and above the First Health Cell in Sunken Glades. Using Dash to dash glide to the plant at the mortar puzzle above Moon Grotto.",
						"The Speed paths tend not to be very difficult to execute and are (with a few exceptions) don't require much in the way of specific knowledge.",
						"These logic paths are enabled by default in every logic mode besides Casual."
					]
					break;
				case "dboost-light":
					title = "Damage Boost (light)"
					lines = [
						"Damage Boost (light) is simplest of the damage boost logic path groups. It contains paths that require taking at most 2 damage.", 
						"Examples: Using Climb instead of Wall Jump to get to the Double Jump tree. Getting to and through Death Gauntlet with 4 Energy Cells and Wall Jump or Climb. Getting the Top Left keystone in Spirit Caverns with Charge Jump (but no wall interaction)",
						"The Damage Boost (Light) paths are usually pretty straightforward, though some of them can be tricky to execute without 1 or 2 extra Health.",
						"These logic paths are enabled by default in every logic mode besides OHKO, and are incompatible with the OHKO variation."
					]
					break;
				case "dboost":
					title = "Damage Boost"
					lines = [
						"Damage Boost is largest of the damage boost logic path groups. It contains paths that require taking up to 5 damage, as well a few more difficult 1-2 damage pickups deemed not appropriate for Damage Boost (Light).", 
						"Examples: Getting to the Energy Cell underwater in the Sunken Glades main pool with 6 Health. Getting to the Climb tree with Bash, DoubleJump, and 4 Health. Getting the Ability Cell behind the underwater 4 energy door with only 3 Health",
						"The Damage Boost paths can be difficult to execute on the minimum amount of health they require, especially without practice. Some pickups (especially underwater ones) can require a quick alt+R after grabbing, depending on your Health.",
						"These logic paths are enabled by default in the Expert, Master, and Glitched logic modes, and are incompatible with the OHKO and Hard Mode variations."
					]
					break;
				case "lure":
					title = "Lure"
					lines = [
						"The Lure logic paths all involve manipulating an enemy into a position that allows them to be used to access a pickup, either via bashing off them or by bashing shots or otherwise using their attacks to break walls or floors.",
						"Examples: Doing the All Skills route Fronkey Walk, and then bashing off the Fronkey to get up to the EXP Orb (or the energy door without wall interaction). Using the Baneling to get the Horu Fields Health Cell without Stomp.",
						"The Lure paths sometimes require a bit of practice to do, but tend not to not take very long and are easy to retry.",
						"These logic paths are enabled by default in every logic mode besides Casual."
					]
					break;
				case "speed-lure":
					title = "Speed Lure"
					lines = [
						"The Speed Lure logic paths contain two very tricky lures used in the All Skills route: Swamp Entry (Entering Swamp with Bash by repositioning and redirecting the frog to the right of the Mortar Redirect puzzle), and Sorrow Bash (Entering Sorrow Pass without Wind Restored by luring and bashing birds).",
						"Both tricks in Speed Lure paths require a fair bit of practice to do for runners not already familiar with them. Tutorial information .",
						"These logic paths are enabled by default in Expert, Master, and Glitched logic modes."	
					]
					break;
				case "lure-hard":
					title = "Lure (Hard)"
					lines = [
						"The Lure (Hard) logic paths contain a few difficult and/or tedious enemy manipulations considered too difficult for Lure.",
						"Examples: Luring a Fronkey down to the Wall Jump Tree to Bash up to the pickups there. Using a Fronkey to stomp the peg and floor to get to the underwater Ability Cell in the area directly below the Hollow Grove mapstone.",
						"These logic paths are enabled by default in the Master and Glitched logic modes, and (due to a single damage boost path) are incompatible with the OHKO and Hard Mode variations."
					]
					break;
				case "dboost-hard":
					title = "Damage Boost (Hard)"
					lines = [
						"The Damage (Hard) logic paths contain 3 very long swimming sections through dirty water: entering Swamp via the lower route, getting the grenade-locked Energy Cell past the water in the Valley Entrance room, and getting the far right Ability Cell in Lost Grove.",
						"These logic paths are enabled by default in the Master and Glitched logic modes, and are incompatible with the OHKO and Hard Mode variations."
					]
					break;
				case "extended":
					title = "Extended"
					lines = [
						"The Extended logic paths are full of tricks that require area-specific knowledge or some tricky or tedious execution to reach.",
						"Examples: Opening the Valley entrance door by bashing the Fronkey onto the peg. Juggling a frog up Sorrow to get access the Sunstone. Passing through the high crushers right of the Dash Tree or at the Boulder Chase area without Dash.",
						"These logic paths are enabled by default in the Expert, Master, Hard, OHKO and Glitched logic modes."
					]
					break;
				case "extended-damage":
					title = "Extended (Damage)"
					lines = [
						"The Extended (Damage) logic paths contain damage boosting tricks that require area-specific knowledge, or are otherwise too difficult or tedious to be included in the Damage Boost logic paths.",
						"Examples: Going from the Spirit Tree to the Valley teleporter without Bash. Going up into Sorrow by repeatedly Charge Jumping off the spikes. Opening the door that leads to the Lost Grove Teleporter without Bash.",
						"These logic paths are enabled by default in the Expert, Master, and Glitched logic modes."
					]
					break;
				case "dbash":
					title = "Double Bash"
					lines = [
						"The Double Bash logic paths all require doing at least one Double Bash to reach a pickup.",
						"These logic paths are enabled by default in the Master, Hard, OHKO and Glitched logic modes."
					]
					break;
				case "cdash":
					title = "Charge Dash"
					lines = [ 
						"The Charge Dash logic paths allow the use of Charge Dash to break open some blue plants, doors, or barriers.",
						"This group also contains a path allowing access to the Glades Laser Grenade pickup with Dash and Grenade, as it is reachable using a combination of Rocket Jumps and normal Charge Dashes.",
						"These logic paths do not include the Valley Entrance Plant, the Dash Plant, the Charge Flame Plant, or any of the Hollow Grove plants, as they are located too early in the game for the player to have gotten enough Ability Points to unlock Charge Dash.",
						"These logic paths are enabled by default in the Expert, Master, Hard, OHKO and Glitched logic modes, and are incompatible with the 0XP variation."

					]
					break;
				case "extreme":
					title = "Extreme"
					lines = [
						"The Extreme logic paths contain tricks too crazy to put anywhere else; the only requirement is that they not require major glitches or induce softlocks",
						"Examples: Double Bashing a spider shot from the left part of Blackroot all the way to the stompable barrier that blocks access to lower Blackroot. Getting the underwater pickups in Swamp without Clean Water.",
						"These logic paths are enabled by default only in the Master and Glitched logic modes, and are incompatible with the OHKO and Hard Mode variations."
					]
					break;
				case "timed-level":
					title = "Timed Level-up"
					lines = [
						"The Timed Level-up paths contain tricks that are only possible to do by leveling up at a specific place. These can require luck, careful planning or a lot of farming.",
						"Examples: Core skip (leveling up to skip the left room in Ginso). Fronkey Walk (the actual All-Skills version, leveling up to open the 4-energy door into Death Gauntlet.)",
						"These logic paths are enabled by default only in the Glitched logic mode, and are incompatible with the 0XP variation."

					]
					break;
				case "glitched":
					title = "Glitched"
					lines = [
						"The Glitched Level-up paths contains many of the known out-of-bounds tricks and other glitches not normally used or allowed in the Randomizer.",
						"Examples: Wrongwarping from the Ginso Tree to Horu. Going out-of-bounds from Valley into the right side of Forlorn.",
						"Warning: Some of these tricks can softlock your save file if required and failed.",
						"These logic paths are enabled by default only in the Glitched logic mode, and are incompatible with the 0XP variation."
					]
					break;
				case "cdash-farming":
					title = "Charge Dash (Farming)"
					lines = [
						"The Charge Dash (Farming) logic paths are similar to the Charged Dash logic paths, but contain a few more rocket jumps. Additionally, it includes paths that unlock the plants not unlocked by the normal Charge Dash logic paths.",
						"As the name implies, the major difference between the two logic path groups is that Charge Dash (Farming) is far more likely to force you to farm for the ability points required to unlock the Charge Dash ability, since the Plants included are earlier in the game.",
						"These logic paths are enabled by default only in the Glitched logic mode, and are incompatible with the 0XP variation."
					]
					break;
				default:
					break;
			}

			break;
		case "none":
		default:
			break;
	}
	return {lines: lines.map(l => (<CardText>{l}</CardText>)), title: title, subtitle: subtitle, extras: extra}
}

const HelpBox = ({title, subtitle, lines, extras, padding}) => (
	<Card className={padding}><CardBody className={padding}>
		<CardTitle className="text-center">{title}</CardTitle>
			<CardSubtitle className="p-1 text-center">{subtitle}</CardSubtitle>
		{lines}
		{extras}
	</CardBody></Card>
);

export {getHelpContent, HelpBox};