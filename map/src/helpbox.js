import React from 'react';
import {CardText, CardTitle, Card, CardBody, CardSubtitle} from 'reactstrap';
import {dev, stuff_by_type} from './common.js'

const UntestedWarning = (<CardText className="border m-2 p-2 border-danger"><i>
NOTE: this variation is rarely used and thus is less tested than most.
In rare cases you may recieve an unfinishable seed. Leaving Web Tracking on is recommended for troubleshooting purposes.
If you believe you have recieved an unfinishable seed, please inform Eiko in the <a target="_blank"  rel="noopener noreferrer" href="/discord">Ori discord</a>.</i>
</CardText>)

const noneTitle = "Confused?";
const noneSub = "Mouse over anything to learn more!";
const noneLines = ["Additional context-specific information will appear here as you interact with the UI."];
const vars = ["Starved", "NonProgressMapStones", "Hard", "0XP", "Entrance", "BonusPickups", "DoubleSkills", "StrictMapstones", "ClosedDungeons", "OpenWorld", "StompTriggers", "TPStarved", "WallStarved", "GrenadeStarved", "Race", "InLogicWarps"]
const presets = ["Casual", "Standard", "Expert", "Master", "Glitched", "Custom"]
const goalModes = ["ForceTrees", "ForceMaps", "Bingo"]
const keyModes = ["Shards", "Clues", "Limitkeys", "Free"]

const bonuses = {}
stuff_by_type["Upgrades"].forEach(({label, value, desc}) => bonuses[value]={name: label, desc: [desc]})
bonuses["RP|RB/0"] = {name: "Repeatable Mega Health", desc: [
    "Restores health to full, then grants 5 additional temporary health.", 
    (<div><i><b>Repeatable</b> pickups are not consumed, and can be collected any number of times.</i></div>)
]}
bonuses["RP|RB/1"] = {name: "Repeatable Mega Energy", desc: [
    "Restores energy to full, then grants 5 additional temporary energy.", 
    (<div><i><b>Repeatable</b> pickups are not consumed, and can be collected any number of times.</i></div>)
]}
bonuses["WP|*"] = {name: "Warp", desc: [
    "A Warp pickup is a permenant 1-way portals to a specific place on the map. Use a warp by touching the pickup and then pressing AltR.",
    (<div><i>Warps are not consumed, and can be used any number of times.</i></div>)
 ]}
bonuses["BS|*"] = {name: "Random Bonus Skill", desc: [(<div>A random bonus skill. Check out the <a target="_blank" rel="noopener noreferrer"  href="/faq?g=bonus_pickups">bonus item glossary</a> for more info on these.</div>)]}

const getHelpContent = (category, option) => {
    let {lines, title, subtitle, extras} = getHelpHelper(category, option)
    return {lines: lines.map((l,i) => (<CardText key={`card-line-${i}`}>{l}</CardText>)), title: title, subtitle: subtitle, extras: extras}
}

const getHelpHelper = (category, option) => {
    let lines = noneLines;
    let title = noneTitle;
    let subtitle = noneSub;  
    let extras = [];
    let match = true;
    switch(category) {
        case "flags":
            let h = {}
            if(vars.includes(option)) {
                h = getHelpHelper("variations", option)
                h.lines[h.lines.length-1] = (<div><i>(This variation has been applied to your seed.)</i></div>)
            } else if(presets.includes(option)) {
                h = getHelpHelper("logicModes", option.toLowerCase())
                h.lines.pop()
                h.lines = h.lines.filter(l => l.startsWith && !l.startsWith("Recommended"))
                if(option !== "Custom")
                    h.lines.push((<div><i>(Your seed is using this Logic Mode.)</i></div>))
            } else if(keyModes.includes(option)) {
                h = getHelpHelper("keyModes", option)
                h.lines[h.lines.length-1] = (<div><i>(Your seed is using this Key Mode.)</i></div>)
            } else if(goalModes.includes(option)) {
                h = getHelpHelper("goalModes", option)
                h.lines[h.lines.length-1] = (<div><i>(Your seed is using this Goal Mode.)</i></div>)
            } else if(option.startsWith("Frags")) {
                let [, required, total] = option.split("/")
                h.title = "Warmth Fragments"
                h.lines = [
                    "The Warmth Fragments Goal Mode scatters " + total + " warmth fragments across the entire map. You must collect " + required + " of them to access the final escape.",
                    (<div><i>(Your seed is using this Goal Mode.)</i></div>)
                ]
            } else if(option.startsWith("WorldTour")) {
                let [, relics] = option.split("=")
                h = getHelpHelper("goalModes", "WorldTour")
                h.lines[0] = h.lines[0].replace(/8/g, relics)
                h.lines[2] = (<div><i>(Your seed is using this Goal Mode.)</i></div>)
            } else if(option.startsWith("pool=")) {
                let [, poolName] = option.split("=")
                h = getHelpHelper("itemPool", poolName)
                h.lines.push((<div><i>(Your seed is using this pool preset.)</i></div>))
            } else if(option.startsWith("share")) {
                let sharedCats = option.split("=")[1].split("+").join(", ")
                h.title = "Shared Item Categories"
                h.lines = [
                    "Players in this game will share items in these categories: " + sharedCats,
                    "For more info on shared item categories, check out the multiplayer tab."
                ]
            } else if(option.startsWith("mode")) {
                let [, mode] = option.split("=")
                h.title = "Multiplayer Game Mode"
                if(mode.toLowerCase() === "shared")
                     h.lines = ["A Co-op game creates different seeds for each player in the game. Items in the selected Shared Item Categories will be shared between players when found."]
                else if(mode.toLowerCase() === "none")
                     h.lines = ["A Race creates 1 copy of the generated seed for each player, each with a different player ID. This creates a map that can be used to watch all the players racing at once!"]
                h.lines.push((<div><i>(Your seeds are using this Multiplayer Mode.)</i></div>))
            } else if(option === "balanced") {
                h = getHelpHelper("advanced", "fillAlgBalanced")
                h.lines.push((<div><i>(Your seed was generated using this fill algorithm)</i></div>))
            } else if(option.startsWith("prefer_path_difficulty")) {
                h = getHelpHelper("advanced", "pathDiff")
                h.lines[2] = ((<div><i>(Your seed has path difficulty set to {option.split('=')[1]})</i></div>))
            }
            h.subtitle = "Flags"
            return h
        case "logicModes":
            subtitle = "Logic Modes"
            switch(option) {
                case "casual":
                    title =  "Casual" 
                    lines = [
                        "Casual is the easiest logic mode, intended and recommended for players who have never done a speedrun of Ori.",
                        "This difficulty mode does not require the use of glitches or creative use of skills.",
                        "Recommended for people who played Ori casually and are looking to try out the randomizer."
                    ]
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
                        "Master is even more difficult than Expert, and is only recommended for players looking to push the game (and their sanity) to the limit.",
                        (<div>Master seeds frequently require several extremely difficult and obscure tricks, including iceless, some very long double bash chains, and some <i>truly awful</i> lures. <b>Not for the feint of heart.</b></div>), 
                        "Selecting this logic mode will set the path difficulty to Hard and enable the Starved variation."
                    ]
                    break;
                case "glitched":
                    title = "Glitched"
                    lines = [ 
                        "Glitched is a logic mode designed for those familiar with Ori's numerous glitches. It includes every logic path that Expert does, and adds new ones requiring knowledge of the game's various out-of-bounds tricks and other unsafe paths.",
                        "This logic mode also contains paths that require timed level-ups, farming for ability points, and various tricks that potentially softlock your save file (or the game) if done incorrectly. Back up your saves!",
                        "Recommended only for those familiar with (at minimium) one of Ori's OOB-heavy categories, such as Reverse Event Order or All Dungeons.",
                        "Selecting this logic mode will set the path difficulty to Hard.",
                    ]
                    break;
                case "custom":
                    title = "Custom"
                    lines = [ 
                        "Custom is the Logic Mode for any user-specified set of logic paths.",
                    ]
                    break;
                default:
                    match = false;
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
                        "Selecting this option creates a seed with no Goal Mode, allowing the game to be completed once enough skills (and the Sunstone) are acquired.",
                        "Playing with no goal mode is not recommended."
                    ]
                    break;
                case "Multiple":
                    title = "Multiple"
                    lines = [
                        "You have multiple goal modes selected. Check out the Advanced Tab for more info."
                    ]
                    break;
                case "ForceTrees":
                    title = "Force Trees"
                    lines = [
                        "The Force Trees Goal Mode requires players to visit all ten skill trees before completing the game. As a side-effect, it makes Ginso Tree access mandatory, as the Bash tree cannot be reached without it.", 
                        "Force Trees is the default Goal Mode, and is a good starting point for new players.",
                    ]
                    break;
                case "ForceMaps":
                    title = "Force Maps"
                    lines = [
                        "The Force Maps Goal Mode requires that you turn in all 9 mapstones before finishing the game. As a side-effect, it makes Forlorn Ruins access mandatory.",
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
                        "The Warmth Fragments Goal Mode scatters a large number of warmth fragments (default 30) across the entire map. Players must collect a certain number of those fragments (default 20) to access the final escape.",
                        "The total number of fragments, as well as the number of 'extra' (non-required) fragments, can be configured in the Advanced Tab of the seed generator.",
                        "Warmth Fragments is recommended for players who like exploring and efficiently checking large numbers of pickups in an unstructured manner, and plays well with most Key Modes, including Free."
                    ]
                    break;
                case "Bingo":
                    title = "Bingo"
                    lines = [
                        "The Bingo Goal mode is a completely different way of playing the Ori Randomizer. Instead of trying to beat the game, players must complete objectives on a randomly-generated bingo card",
                        "This goal mode is not recommended for newer players due to the game knowledge that tends to be required, and is much easier with 2 monitors. If you're interested in trying it but unsure how it works, please join the discord and ask about it there!"
                    ]
                    break;
                default:
                    match = false;
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
                        "Note that the Balanced fill algorithm can interfere with Starved.",
                        "Recommended for everyone at least once, and for players who enjoy more linear pathing or constrained situations. "
                    ]
                    break;
                case "TPStarved":
                    title = "TPStarved"
                    lines = [
                        "The TPStarved variation is a new setting that reduces the probability that players will be given teleporter pickups in the early game. It also reduces the probability that teleporter paths are chosen when the seed generator is picking progression paths. This tends to create seeds that open up more slowly, and reduce the frequency of forced early dungeon-teleporter usage.",
                        "Recommended for players who want teleporters in their item pool but would prefer to avoid finding too many of them early on."
                    ]
                    break;
                case "WallStarved":
                    title = "WallStarved"
                    lines = [
                        "The WallStarved variation is a new setting that reduces the probability that players will be given wall interaction skills (Wall Jump and Climb) in the first 40 pickups. It also reduces the probability that these pickups are chosen when the seed generator is picking progression paths. This usually forces the seed generator to place powerful skills more early on.",
                        "Recommended for players who prefer seeds that are very likely to have powerful skills like Bash and Charge Jump very early on."
                    ]
                    break;
                case "GrenadeStarved":
                    title = "GrenadeStarved"
                    lines = [
                        "The GrenadeStarved variation is a new setting that dramatically reduces the probability that players will find Grenade in the first 60 pickups. It also reduces the probability that grenade is chosen when the seed generator is picking progression paths.",
                        "Recommended for players looking to reduce the likelihood of seeds where Bash+Grenade is the early-game movement option."
                    ]
                    break;
                case "Race":
                    title = "Race"
                    lines = [
                        "Race flag for tourney races."
                    ]
                    break;
                case "GoalModeFinish":
                    title = "Skip Final Escape"
                    lines = [
                        "The Skip Final Escape variation removes the need for players to complete the Mount Horu final escape.", 
                        "Upon finishing their selected goal mode (or goal modes, if more than one is picked), players will recieve a special bonus skill, which can be activated at any time to warp to the credits.",
                        "Note: Bingo already has this functionality built-in."
                    ]
                    break;
                case "Hard":
                    title = "Hard Mode"
                    lines = [
                        "The Hard Mode variation removes all health cells and all but 3 energy cells from the pool of available items, capping your health at 3 and energy at 4 for the entire seed. Additionally, it removes all bonus pickups from the pickup pool.",
                        "Due to these restrictions, it is incompatible with logic paths that require taking 3 or more damage (standard-dboost, expert-dboost, master-dboost), and the Extra Bonus Pickups variation.",
                        "Recommended for people who hate feeling safe and like to live on the edge."
                    ]
                    extras.push(UntestedWarning);
                    break;
                case "OHKO":
                    title = "One-Hit KO"
                    lines = [
                        "The One-Hit KO variation causes any amount of damage Ori takes to be instantly lethal. It is incompatible with all logic paths that require damage boosts.",
                        "Recommended for anyone who really enjoys the sound Ori makes when dying."
                    ]
                    extras.push(UntestedWarning);
                    break;
                case "0XP":
                    title = "0 Experience"
                    lines = [
                        "Inspired by the incredibly unpopular 0 XP speedrunning category, the 0 Experience variation prevents Ori from ever gaining levels or acquiring experience. Experience dropped by enemies will do nothing.",
                        "Recommended for anyone who watched a 0 XP run and thought it seemed fun."
                    ]
                    extras.push(UntestedWarning);
                    break;
                case "InLogicWarps":
                    title = "In-Logic Warps"
                    lines = [
                        "Following warps is considered in-logic!",
                        "Beware! This might be terrible." // FIXME: uh. come on. 
                    ]
                    break;
                case "Entrance":
                    title = "Entrance Shuffle"
                    lines = [
                        "The Entrance Shuffle variation remaps each door (the dungeon entrances and the 8 Horu side rooms) in the game to go to another door instead.",
                        "Recommended for anyone who likes being confused, or is interested in spending more time in Horu than usually necessary."
                    ]
                    break;
                case "BonusPickups":
                    title = "More Bonus Pickups"
                    lines = [
                        "More Bonus Pickups introduces several new bonus pickups not normally found in the randomizer, including some new activateable skills.",
                        "Note: The default bindings for bonus skills are Alt+Q to swap between them, and Alt+Mouse1 to activate them. These bindings can be changed in the RandomizerRebinding.txt file.",
                        'Note: The "ExtremeSpeed" and "Gravity Swap" pickups are toggleable: activating them will turn them on, and cost energy over time. They will automatically turn off if you run out of energy.',
                        "Recommended for people interested in trying out some cool and probably pretty overpowered pickups."
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
                    title = "Strict Mapstones"
                    lines = [
                        "The Strict Mapstones variation forces the seed generator to place a mapstone for every reachable mapstone pedestal.",
                        "This variation represents the pre-3.0 default behavior, and is not generally recommended due to how predictable it makes early game mapstone placements."
                    ]
                    break;
                case "ClosedDungeons":
                    title = "Closed Dungeons"
                    lines = [
                        "The Closed Dungeons variation reverts several changes made in version 3.0 that made the dungeons more accessible. These changes were: ",
                        (<ul>
                            <li>Keystone doors can be opened from both sides</li>
                            <li>Horu and Ginso Teleporters have been added to the item pool</li>
                            <li>Horu starts with the lava already drained, allowing TP access to the entire dungeon</li>
                            <li>The second Ginso miniboss room has both lower doors opened by default, allowing TP access to most of the dungeon. (The lowest two pickups are blocked by the first miniboss)</li>
                        </ul>),
                        "Enabling this variation will disable all of the above!",
                        "This variation exists primarily for legacy reasons and is not recommended for normal use"
                    ]
                    break;
                case "OpenWorld":
                    title = "Open World"
                    lines = [
                        "The Open World variation makes a few impactful changes to the state of the world, with the primary intent of making more areas reachable earlier, especially the left side of the map. These changes are:",
                        (<ul>
                            <li>The first Keystone door in the Sunken Glades area starts open</li>
                            <li>The two doors into Valley of the Wind from the "Valley Entry" room (immediately left of the Spirit Tree) start out open</li>
                            <li>The Valley "killplane" has been removed (Kuro will no longer autokill players passing through the main Valley room)</li>
                        </ul>),
                        "Recommended for players who are familiar with the randomizer and looking for more varied and challenging seeds."
                    ]
                    break;
                case "StompTriggers":
                    title = "Legacy Kuro Behavior"
                    lines = [
                        "The Legacy Kuro Behavior variation reverts to the vanilla and pre-3.0 randomizer behavior for the Kuro kill plane in Valley and the Kuro cutscene in Hollow Grove. Both of these will only exist once you've acquired the Stomp skill.",
                        "This variation will be overridden if you select Open World, which removes the killplane and cutscene completely.",
                        "This variation exists primarily for legacy reasons and is not recommended for normal use."
                    ]
                    break;
                default:
                    match = false;
                    break;
            }
            break;
        case "seedTab":
            subtitle  = "Seed Info"
            let multi = false;
            if(option.endsWith("Multi"))
            {
                multi = true;
                option = option.slice(0, option.length - 5);
            }
            let aux = option.endsWith("Aux")
            if(aux)
                option = option.replace("Aux","")
            
            switch(option) {
                case "playerPanel":
                    title = "Player ID"
                    lines = ["This box indicates the player number and map icon color associated with each seed."]
                    if(multi)
                    {
                        lines = lines.concat("Decide among your fellow players who gets what player number, and make sure each seed is accounted for.",
                                             "Remember to send your fellow players the URL to the current page so they can get their seeds!")
                    } else {
                        lines.push("In single player games, the player number is always 1, and the map icon is always blue.")
                    }
                break;
                case "openBingoBoard":
                    title = "Open Bingo Board"
                    lines = [
                        "Click here to open the bingo board creation page (or the bingo board, if it has already been created)",
                        "Once you create the bingo board, you will be able to download seeds from that page."
                    ]

                break;
                case "downloadButton":
                    title = "Download Seed"
                    lines = [
                        "Click here to download your seed file.",
                        "Once downloaded, move or copy the randomizer.dat file into your OriDE folder. (It should be named randomizer.dat and be in the same folder as OriDE.exe)"
                    ]
                    if(multi)
                        lines.push("Remember to send your fellow players the URL to the current page so they can get their seeds!")
                break;
                case "spoilerView":
                    title = "Open Spoiler"
                    lines = [
                        "Click here to open your spoiler in a new tab.",
                        "The spoiler contains a detailed report of what items are placed where, and the order in which the randomizer intended you to find them.",
                        "Don't be afraid to check your spoiler if you get stuck!"
                    ]
                break;
                case "noSpoilers":
                    title = "No Spoilers Available"
                    lines = [
                        "This seed has no text spoiler available! Consider loading it into the Logic Helper or using the tracking map's spoiler function."
                    ]
                break;
                case "spoilerDownload":
                    title = "Download Spoiler"
                    lines = [
                        "Click here to download your spoiler as a text file.",
                        "The spoiler contains a detailed report of what items are placed where, and the order in which the randomizer intended you to find them.",
                        "Don't be afraid to check your spoiler if you get stuck!"
                    ]
                break;
                case "tracking":
                    title = "Web Tracking Features"
                    lines = [
                        "These tools are available because Web Tracking is enabled. Mouse over them for more info."
                    ]
                break;
                case "mapLink":
                    title = "Tracking Map"
                    lines = [
                        "The tracking map is a powerful tool designed to help players learn and get a feel for the logic while playing the game.",
                        "It provides a live-updating map that shows where Ori currently is and what pickups are currently considered in logic.",
                        "The tracking map can also be used as a visual spoiler, or as a coordination tool between multiple players in co-op games.",
                        "Using the tracking map is recommended for players with multiple monitors, especially those learning a new logic mode."
                    ]
                break;
                case "gameId":
                    title = "Game Id"
                    lines = ["Input this into the restreaming script for the player this is for to configure their tracking map"]
                break;
                case "histLink":
                    title = "Game Log"
                    lines = [
                        "The game log provides a list of important pickups found by each player in the game, as well as their location.",
                        "It can provide an easy at-a-glance check of what pickups have been already found, but is in general less useful than the tracking map."
                    ]
                break;
                case "flags":
                    title = "Flags"
                    lines = ["Each flag here represents some setting selected in the seed generation process. Mouse over each one to learn more."]
                break;
                default:
                    match = false;
                break;
            }
            if(aux && match)
            lines.push("Key Item Spoiler Mode: in this mode, the spoiler lists the locations of important items.")
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
                    match = false;
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
                        "For a coop game, set this to the number of players in the game. Note that games with more people will have less relevant pickups for each individual player.",
                        "For a split shards game, set this to the number of players in the game.",
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
                        "One player should generate the game and share the generated link or distribute the seeds to ensure all players are using the same seed.", 
                    ]
                    break;
                case "Cloned Seeds":
                    title = "Cloned Seeds"
                    subtitle = "Co-op Seed Generation Modes"
                    lines = [
                        "Cloned Seeds are just single-player seeds that have shared items enabled. All items are in the same place, and stacking shared items (such as health regeneration or shards) can be duplicated if multiplayers players collect them.",
                        "Because Cloned Seeds are mostly identical, they are ideal for co-op games where all players can talk to each other, so that they can coordinate checking different areas. Bingo and Clues are great Goal and Dungeon Key Modes for Cloned Seeds.",
                    ]
                    break;
                case "Seperate Seeds":
                    title = "Seperate Seeds"
                    subtitle = "Co-op Seed Generation Modes"
                    lines = [
                        "Seperate Seeds are made by simulataneously generating a seed for each player in the game. Each shared item is only assigned to one player; once it becomes accessible for one player, it will be in the logic for both of them.",
                        "Because the seeds for each player are generated seperately, the progression paths of each player will be different, though they will at certain points rely on each other.",
                        "For Seperate Seeds, player communication is not as important, as no information gained by one player will be relevant to the others (besides informing them of shared pickups they have, which the game does already).",
                        "Seperate Seeds work best when individual shared items don't block progression for other players.",
                        "Recommended settings: Do not share skills (or teleporters), do share upgrades, world events, and misc, set the dungeon key mode to either Shards or Free, and set the Goal Mode to either Warmth Fragments or World Tour."
                    ]
                    break;
                default:
                    match = false;
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
                        "With Share Misc enabled, tree activation, teleporter activation, and World Tour Relics are shared between players.",
                        "Sharing teleporters and tree progression will generally reduce the amount of time an average co-op seed will take to complete."
                    ]
                    break;
                case "World Events":
                    title = "Share World Events"
                    lines = [
                        "With Share World Events enabled, the 3 Dungeon Keys (or Shards), Clean Water, Wind Restored, and Warmth Fragments will be shared between players when found.",
                        "Sharing World Events is recommended for every co-op game varient, though it is less interesting in certain Dungeon Key modes (*cough*limitkeys*cough*).",
                        "Note: Shards and Warmth Fragments are always deduped as though Dedup Shared were enabled"
                    ]
                    break;
                case "Upgrades":
                    title = "Share Upgrades"
                    lines = [
                        "With Share Upgrades enabled, all permenant upgrades (or bonuses) will be shared between players when found.",
                        "All upgrades besides Mega Health and Mega Energy are considered permenant upgrades, including everything unlocked by the 'More Bonus Pickups' variation.",
                    ]
                    break;
                case "Dedup":
                    title = "Dedup Shared"
                    lines= [
                        "With Dedup Shared enabled, stackable bonus pickups (Extra Double Jump, Regens, Skill Velocity, etc) will only grant one stack per item location.",
                        "(Without Dedup Shared, players can gain up to 1 stack per player of any of these items, as long as each player collects their copy).",
                        "Dedup Shared has no effect on seeds without Share Upgrades enabled. Shards and Warmth Fragments are always deduped."
,
                    ]
                    break;
                case "Hints":
                    title = "Hints"
                    lines = [
                        "A variation for Cloned Seeds, this on-by-default option adds hints when player gets a pickup that contains a shared item for one of the other players in the game.",
                        "Instead of seeing Warmth Returned, players will instead see the share type of the item in question. In games with more than 2 players, the hint will also specify which player has the pickup in their seed.",
                        "Without hints, Cloned Seeds work best with fewer players (more than 3 can lead to a lot of duplicate checking) and fewer overall shared items (shared upgrades not recommended).",
                        "With hints, however, the number of players and shared pickups can both be higher without issue; knowing the pickup type helps distinguish between which shared pickups are important.",
                    ]
                    break;
                default:
                    match = false;
                    break;
            }
        break;
        case "advanced":
            subtitle = "Advanced Options"
            switch(option) {
                case "bingoLines":
                    title = "Bingo Lines"
                    lines = ["Set the number of bingo lines to play for. Can also be adjusted on board generation"]
                    break;
                case "sense":
                    title = "Sense Triggers"
                    lines = [
                        "Use this field to trigger what pickups the sense ability can sense. The default value is EV+RB17+RB19+RB21+RB28+SK",
                        "To match an entire class of pickups, use the first 2 characters; to match a specific pickup, use the entire pickup code (no |)"
                    ]
                    break;
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
                        "The closer the required fragment count is to the total fragment count, the longer and more tedious the search for fragments becomes."
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
                case "goalModes":
                    title = "Extra Goal Modes"
                    lines = [
                        "Use these buttons to add extra goal modes to your seed."
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
                        "You can use these fields to control what the first several pickups of your seed will be!",
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
                    match = false;
                    break;
            }
        break;
        case "itemPool":
            subtitle = "Item Pool Editor"
            switch(option) {
                case "deleteRow":
                    title = "Delete"
                    lines = [
                        "Use this button to remove all copies of a pickup from the item pool.",
                        "Note: removing some items from the pool (like health cells) will prevent some logic paths (like damage boost paths) from being chosen."
                    ]
                    break
                case "count":
                    title = "Count"
                    lines = [
                        "This field sets the minimum number of times this row's pickup will be placed in the seed.",
                    ]
                    break
                case "upTo":
                    title = "Maximum"
                    lines = [
                        "This field sets the maximum number of times this row's pickup will be placed in the seed. Leaving it set to the same number as the minimum results in that number always being chosen.",
                    ]
                    break;
                case "pickupSelectorDisabled":
                    title = "Pickup Selector (locked)"
                    lines = [
                        "This item cannot be modified or removed from the pool; at least some number of copies of this item are required for seed generation.",
                    ]
                    break;
                case "Standard":
                    title = "Standard"
                    subtitle = "Item Pool Presets"
                    lines = [
                        "The Standard item pool preset is the default and recommend item pool preset for most players, especially newer players.",
                        "It contains every teleporter, a decent selection of bonus pickups, and the default amount of Cells (Health, Energy, and Ability)",
                    ]
                    break;
                case "Hard":
                    title = "Hard"
                    subtitle = "Item Pool Presets"
                    lines = [
                        "The Hard item pool preset is a preset pool for people who like tedium and getting a lot of pickups with small amounts of Exp.",
                        "It contains no bonus pickups, no Health cells, and only 4 Energy Cells.",
                    ]
                    break;
                case "Extra Bonus":
                    title = "Extra Bonus"
                    subtitle = "Item Pool Presets"
                    lines = [
                        "The Extra Bonus item pool preset introduces several new bonus pickups not normally found in the randomizer, including some new activateable skills.",
                        "It also contains more copies of existing pickups; 2 more Attack Upgrades for a total of 5, and 2 more Extra Double Jumps for a total 3. Mega Health and Mega Energy pickups are not consumed on pickup.",
                        "Lastly, it adds 4-8 warps, which are pickups that act as permenant 1-way portals to a different place on the map. Use a warp by touching the pickup and then pressing AltR.",
                        "Note: The default bindings for bonus skills are Alt+Q to swap between them, and Alt+Mouse1 to activate them. These bindings can be changed in the RandomizerRebinding.txt file.",
                        "Mouse over the individual rows to learn more about the bonus pickups!",
                        (<div>Check out the <a target="_blank" rel="noopener noreferrer"  href="/faq?g=bonus_pickups">bonus item glossary</a> for more info about the extra bonus items.</div>),
                    ]
                    break;
                case "Bonus Lite":
                    title = "Bonus Lite"
                    subtitle = "Item Pool Presets"
                    lines = [
                        "The Bonus Lite item pool preset contains a few new passive bonus pickups (3 Skill Velocity Upgrades, 3 Jump Upgrades, and 1 each of Health Drain, Energy Drain, and Underwater Skill Usage)",
                        "It also contains more copies of existing pickups; 2 more Attack Upgrades for a total of 5, and 2 more Extra Double Jumps for a total 3.",
                        "Lastly, it adds 4-8 Warps, which are pickups that act as permenant 1-way portals to a different place on the map. Use a warp by touching the pickup and then pressing AltR.",
                        (<div>Check out the <a target="_blank" rel="noopener noreferrer"  href="/faq?g=bonus_pickups">bonus item glossary</a> for more info about the extra bonus items.</div>),
                    ]
                    break;
                case "Competitive":
                    title = "Competitive"
                    subtitle = "Item Pool Presets"
                    lines = [
                        "The Competitive item pool preset is a minor variant on the default item pool intended for use in races, particularly races in the Clues keymode.",
                        "It contains almost all of the items in the Standard item pool, but removes the Horu and Ginso teleporters",
                    ]
                    break;
                case "Custom":
                    title = "Custom"
                    subtitle = "Item Pool Presets"
                    lines = [
                        "Custom item pools are user-defined and can contain basically anything. However, they do need to have at least 3 energy cells for seeds to generate successfully",
                    ]
                    break;
                default:
                    if(bonuses[option]) {
                        let {name, desc} = bonuses[option]
                        title = `${name}`
                        subtitle = "Item Descriptions"
                        lines = desc
                    } else {
                        title = "Pickup Selector"
                        lines = [
                            "Use this box to select or modify an item being placed in the pickup pool. If you place multiple pickups into this box, all of them will be placed in the same location (or locations).",
                            "For example, if you add '10 experience' to the default 'Ability Cell' row, every Ability Cell pickup will also give 10 experience.",
                        ]
                        break;
                    }
                    break;
            }

        break;
        case "general":
            subtitle = "General Options"
            switch(option) {
                case "logicModes":
                    title = "Logic Modes"
                    lines = [
                        "Logic modes are sets of logic paths tailored for specific play experiences. Changing the logic mode will have a major impact on seed difficulty.", 
                        "New players should start out with the Casual logic mode unless they are already familiar with the basics of Ori speedrunning.",
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
                        "Dungeon key modes change how the 3 dungeon keys (the Watervein, Gumon Seal, and Sunstone) are acquired. Since the Sunstone is always required, and the Water Vein is required by default (see Forcetrees under Goal Modes for more info), placement of the Dungeon Keys matters a fair bit.",
                        "New players should start with Clues or Free."
                    ]
                    break;
                case "seedTab":
                    title = "Seed Tab"
                    lines = [
                        "View and download your generated seed here!"
                    ]
                break;
                case "customPool":
                    title = "Item Pool Tab"
                    lines = [
                        (<div>The Item Pool tab allows users to customize the contents of the item pool (the set of items placed by the randomizer), either by selecting one of the available Item Pool presets or by manually adding / removing items.</div>),
                        (<div>Note: the presets in this tab replace the old "Extra Bonus Pickups" and "Hard Mode" variations.</div>),
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
                case "seed":
                    title = "Seed"
                    lines = [
                        "The Seed field is used as a starting point for the seed generator's pRNG. If left blank, a value will be auto-generated",
                        "If you use the same seed value and leave all the other options the same, you will get end up with the same randomizer.dat file (though only for the same seed generator release)."
                    ]
                break;
                case "webTracking":
                    title = "Web Tracking"
                    lines = [
                        "With Web Tracking enabled, the randomizer will send updates to the server as you play the game. Seeds downloaded with Web Tracking enabled have a special Sync flag, which is used by the server to identify and track that game.",
                        "Web tracking does not collect or store any personal info. The only information the game sends to the server is Ori's current position, and the location and ID of collected pickups.",
                        "Web tracking is required for the Bingo Goal Mode, for the Map tracker to function properly, and for all multiplayer modes."
                    ]
                break;
                case "webTracking-locked":
                    title = "Web Tracking"
                    lines = [
                        "With Web Tracking enabled, the randomizer will send updates to the server as you play the game. Seeds downloaded with Web Tracking enabled have a special Sync flag, which is used by the server to identify and track that game.",
                        "Web tracking does not collect or store any personal info. The only information the game sends to the server is Ori's current position, and the location and ID of collected pickups.",
                        "Web tracking is required for the Bingo Goal Mode, for the Map tracker to function properly, and for all multiplayer modes.",
                        (<i>(Because you have selected one or more options that requires Web Tracking, it cannot currently be disabled)</i>)
                    ]
                break;
                case "generate":
                    title = "Generate Seed"
                    subtitle = ""
                    lines = [
                        "Click here to start building your seed! This may take several seconds."
                    ]
                break;
                case "generateMulti":
                    title = "Generate Seed"
                    subtitle = ""
                    lines = [
                        "Click here to start building your seeds! This may take several seconds."
                    ]
                break;
                case "seedBuilding":
                    title = "Generating..."
                    subtitle = ""
                    lines = [
                        "The server is building your seed now. This may take several seconds."
                    ]
                break;
                case "seedBuildingMulti":
                    title = "Generating..."
                    subtitle = ""
                    lines = [
                        "The server is building your seed now. This may take several seconds."
                    ]
                break;
                case "seedBuilt":
                    title = "Seed Generation Complete!"
                    subtitle = ""
                    lines = [
                        "Your seed is ready to download.",
                        "Tip: You can share your seed with anyone by sending them this page's current URL."
                    ]
                    break;
                case "seedBuiltBingo":
                    title = "Bingo Seed Generation Complete!"
                    subtitle = ""
                    lines = [
                        "The bingo board creation page should open in a new window. If it does not, click the buttons to the left to open it.",
                        "Once you create the bingo board, you will be able to download seeds from that page."
                    ]
                break;
                case "seedBuiltMulti":
                    title = "Multiplayer Seed Generation Complete!"
                    subtitle = ""
                    lines = [
                        "Your seeds are ready to download.",
                        "Send your fellow players this page's current URL so they can download their seeds.",
                        "Make sure everyone is using a different player number!"
                    ]
                break;
                default:
                    match = false;
                break;
            }
            break;
        case "logicPaths":
            subtitle = "Logic Paths"
            switch(option) {
                case "casual-core":
                    title = "Casual Core"
                    lines = [
                        (<div><b>Casual Core</b> logic paths are the basis of the casual preset and the randomizer logic as a whole. All of the intended mechanics taught by a casual playthrough are included, including bashing off of your thrown grenades and performing wall charge jumps.</div>),
                        "A small number of non-casual behaviors are also included, such as using Stomp to break some vertical barriers.",
                        (<div><b>Casual Core</b> paths are enabled by default in all logic presets, and cannot be disabled.</div>)
                    ]
                    break;
                case "casual-dboost":
                    title = "Casual Damage Boost"
                    lines = [
                        (<div><b>Casual Damage Boost</b> paths are the simplest type of damage boost. These paths may require you to take up to 2 damage. You won't be required to collect any underwater pickups, but you may be required to briefly swim through dirty water or cross a spike pit.</div>),
                        "Examples: boosting once on the spike wall near the Grenade tree to get the XP orb with only Charge Jump; using Climb instead of Wall Jump to reach the Double Jump tree; collecting the top-left keystone in Spirit Caverns without wall interaction.",
                        (<div><b>Casual Damage Boost</b> paths are generally very straightforward to perform, though they can be a little tricky if you're still at 3 HP.</div>),
                        "These paths are enabled by default in all logic presets, and are incompatible with the OHKO variation."
                    ]
                    break;
                case "standard-core":
                    title = "Standard Core"
                    lines = [
                        (<div><b>Standard Core</b> logic paths are the basis of the standard preset. These paths represent the tricks, tech, and knowledge that one might learn from doing speedruns of Ori DE.</div>),
                        "Tech that might be required includes bash glides, dash glides, and using wall charge jumps to break floors/ceilings. Some slightly precise jumps may also be required, such as reaching the Spirit Caverns ability cell using Double Jump and Wall Jump.",
                        (<div><b>Standard Core</b> paths don't require a high level of execution, nor do they require a high degree of area-specific knowledge, but they do require a higher degree of overall game knowledge than Casual paths.</div>),
                        "These paths are enabled by default in all logic presets except Casual."
                    ]
                    break;
                case "standard-lure":
                    title = "Standard Lure"
                    lines = [
                        (<div><b>Standard Lure</b> logic paths represent manipulating enemies to cross distances or drawing their projectiles in a particular way to help you reach pickups or locations that would otherwise not be accessible.</div>),
                        (<div>Examples: performing the all skills "fronkey walk" to bash up to the XP orb right of the start; using the baneling near the Horu Fields entrance to break the floor to get the health cell.</div>),
                        (<div><b>Standard Lure</b> paths may require some minor area-specific knowledge, but are generally not difficult to perform.</div>),
                        "These paths are enabled by default in all logic presets except Casual."
                    ]
                    break;
                case "standard-dboost":
                    title = "Standard Damage Boost"
                    lines = [
                        (<div><b>Standard Damage Boost</b> logic paths incorporate damage boosts of up to 3 damage, plus a few more difficult 1-2 damage boost paths. Underwater pickups are still not required, nor is any damage boosting in Misty Woods.</div>),
                        "Examples: collecting Ginso Tree keystones without Double Jump or Bash; collecting the health cell behind the 2-energy door in Moon Grotto with only Wall Jump; crossing the moat in death gauntlet with only Wall Jump or Climb.",
                        (<div><b>Standard Damage Boost</b> paths usually are not especially tricky to do, but may require some confidence jumping onto spikes that deal a lot of damage.</div>),
                        "These paths are enabled by default in all logic presets except Casual, and are incompatible with the OHKO variation."
                    ]
                    break;
                case "standard-abilities":
                    title = "Standard Abilities"
                    lines = [
                        (<div><b>Standard Abilities</b> logic paths incorporate use of the Air Dash ability. At least three ability cells will be provided before you're expected to make use of Air Dash.</div>),
                        "Examples: collecting Ginso Tree keystones without taking damage; accessing the area below the Moon Grotto teleporter.",
                        "These paths are enabled by default in all logic presets except Casual, and are incompatible with the 0 XP variation."
                    ]
                    break;
                case "expert-core":
                    title = "Expert Core"
                    lines = [
                        (<div><b>Expert Core</b> logic paths are the basis of the expert preset. These paths either require a notable amount of area-specific knowledge or a higher degree of execution than standard paths.</div>),
                        "Examples: juggling a frog up Sorrow Pass to get access to the Sunstone; passing through the crushing blocks in Blackroot without Dash; reaching the plant in Valley entry with only Wall Jump and Charge Flame.",
                        "These paths are enabled by default in the Expert, Master, and Glitched presets."
                    ]
                    break;
                case "expert-lure":
                    title = "Expert Lure"
                    lines = [
                        (<div><b>Expert Lure</b> logic paths represent more difficult enemy lures possibly involving multiple enemies or complex combinations of bash angles and other movement techniques.</div>),
                        (<div>Examples: performing the "Sorrow Bash" trick to enter Sorrow Pass using chained bashes on the birds at the top of Valley; bashing the frog near the upper Swamp entrance to use his projectiles to break your way in.</div>),
                        (<div><b>Expert Lure</b> paths require a fair bit of practice for most runners. Don't be afraid to ask for help on the Ori discord!</div>),
                        "These paths are enabled by default in the Expert, Master, and Glitched presets."
                    ]
                    break;
                case "expert-dboost":
                    title = "Expert Damage Boost"
                    lines = [
                        (<div><b>Expert Damage Boost</b> logic paths incorporate damage boosts of up to 6 damage. These could include swimming sequences with underwater pickups or damaging yourself repeatedly across spikes.</div>),
                        "Examples: getting to the Energy Cell in the main pool of Sunken Glades with 7 health; reaching the lower Swamp access in Moon Grotto using only Dash and 4 health; getting the underwater ability cell in Death Gauntlet with 4 health.",
                        "These paths are enabled by default in the Expert, Master, and Glitched presets."
                    ]
                    break;
                case "expert-abilities":
                    title = "Expert Abilities"
                    lines = [
                        (<div><b>Expert Abilities</b> logic paths incorporate use of the Charge Dash ability. These paths may also implicitly assume use of Air Dash. Six ability cells will be provided for these paths.</div>),
                        "Charge Dash can be expected to be used to break plants or cross long distances without losing height. You may also be expected to perform Rocket Jumps by quickly canceling an upwards Charge Dash with a jump input.",
                        "These paths are enabled by default in the Expert, Master, and Glitched presets."
                    ]
                    break;
                case "dbash":
                    title = "Double Bash"
                    lines = [
                        (<div><b>Double Bash</b> logic paths require performing one or more double bashes. Incredibly long sequences of double bashes are not included, but you may be expected to do up to five or six in a row.</div>),
                        "Examples: reaching the pickups above the water in the Spider Coves area with only Bash; navigating Horu Fields with only Bash; you get the idea.",
                        (<div>The randomizer has support for "free double bashes", which you can configure in RandomizerKeybindings.txt. This allows you to hold a specified button while releasing one Bash to get an automatic double bash.</div>),
                        (<div><b>Double Bash</b> paths are enabled by default in the Expert, Master, and Glitched presets.</div>)
                    ]
                    break;
                case "master-core":
                    title = "Master Core"
                    lines = [
                        (<div><b>Master Core</b> logic paths are the basis of the master preset. These paths require deep, thorough knowledge of the intricacies of each area of the game, as well as the ability to execute difficult strategies.</div>),
                        (<div>Examples: double bashing a spider shot from the bottom of Blackroot Burrows to break the floor to enter lower Blackroot; performing the "iceless" jump to reach the experience orb above the Hollow Grove map.</div>),
                        (<div><b>Master Core</b> paths may also require you to perform "double jump wall climbing", repeatedly jumping into and then turning away from a single wall to refresh your jumps to continue scaling it.</div>),
                        "These paths are only enabled by default in the Master preset."
                    ]
                    break;
                case "master-lure":
                    title = "Master Lure"
                    lines = [
                        (<div><b>Master Lure</b> logic paths represent the most difficult enemy lures, involving avoiding damaging environmental obstacles or maneuvering enemies through tight quarters.</div>),
                        "Examples: kiting a fronkey down to the Wall Jump tree area to Bash off of him to reach the pickups there; using a fronkey to break both barriers to reach the underwater cell in the main area of Hollow Grove.",
                        "These paths are only enabled by default in the Master preset."
                    ]
                    break;
                case "master-dboost":
                    title = "Master Damage Boost"
                    lines = [
                        (<div><b>Master Damage Boost</b> logic paths incorporate damage boosts of any amount. In addition, these paths may require the Ultra Defense ability. Twelve ability cells will be provided before Ultra Defense is expected.</div>),
                        "Examples: collecting all of the underwater pickups in Swamp with 7 health and Ultra Defense; getting from the Swamp keystone door to the Stomp tree with only Wall Jump and 12 health.",
                        "These paths are only enabled by default in the Master preset."
                    ]
                    break;
                case "master-abilities":
                    title = "Master Abilities"
                    lines = [
                        (<div><b>Master Abilities</b> logic paths incorporate use of the Triple Jump ability. These paths may also implicitly assume use of Air Dash and Charge Dash. Twelve ability cells will be provided for these paths.</div>),
                        "Examples: crossing Horu Fields with only Wall Jump, Double Jump, Dash, and the Triple Jump ability; reaching the ability cell in the outer Swamp mortar area with only Wall Jump, Double Jump, and the Triple Jump ability.",
                        "These paths are only enabled by default in the Master preset."
                    ]
                    break;
                case "gjump":
                    title = "Grenade Jump"
                    lines = [
                        (<div><b>Grenade Jump</b> logic paths incorporate use of grenade jumps, a trick in which you press Grenade one frame before performing a wall Charge Jump. These paths all require Climb, Charge Jump, and Grenade.</div>),
                        "Examples: crossing Horu Fields with grenade jumps; navigating the right side of Lost Grove without Bash; ascending from the Valley entrance to the main area of Valley (with some combination of Double Jump and damage boosts).",
                        "These paths are only enabled by default in the Master preset."
                    ]
                    break;
                case "glitched":
                    title = "Glitched"
                    lines = [
                        (<div><b>Glitched</b> logic paths incorporate the tricks which are disallowed by the common randomizer ruleset: clips, out of bounds, teleport anywhere, and warp displacement.</div>),
                        "Examples: Terra clipping from the Ginso Tree to Horu; warp displacing using the Swamp teleporter to reach the outer Swamp mortar ability cell; using the Blackroot boulder to clip into Moon Grotto.",
                        (<div>WARNING: many <b>Glitched</b> paths require spending ability points or other one-time tricks. Backing up your save early and often is heavily recommended.</div>),
                        "These paths are only enabled by default in the Glitched preset."
                    ]
                    break;
                case "timed-level":
                    title = "Timed Level"
                    lines = [
                        (<div><b>Timed Level</b> logic paths represent leveling up at specific places to obtain health and energy refills or damage otherwise unreachable enemies. These can require luck, careful planning, or a lot of farming.</div>),
                        (<div>Examples: the all skills "fronkey walk", using a timed level on a fronkey to enter death gauntlet with only 2 energy; leveling on the frog at the grenade basketball puzzle in Blackroot to kill the other frog to reach an ability cell.</div>),
                        "These paths are only enabled by default in the Glitched preset."
                    ]
                    break;
                case "insane":
                    title = "Insane"
                    lines = [
                        (<div><b>Insane</b> logic paths should not exist. They are a sign of the depths of depravity to which the randomizer developers have sunk.</div>),
                        (<div>Examples: completing the Ginso escape with nothing but Double Jump and Triple Jump; accessing the right Valley "bird stomp cell" by double bashing a baneling from lower Valley.</div>),
                        "WARNING: seriously, if you turn these on, you will regret it. Some of these might take you an hour just to execute once. They're HARD.",
                        "These paths are not enabled by default in any mode. We don't hate you that much."
                    ]
                    break;
                default:
                    match = false
                    break;
            }
            break;
        default:
            match = false;
            break;
    }
    if(dev && !match)
        console.log(`No help text for ${category}, ${option}`)
    return {lines: lines, title: title, subtitle: subtitle, extras: extras}
}

const HelpBox = ({title, subtitle, lines, extras, padding, style}) => {
    return (
    <Card className={padding} style={style}><CardBody className={padding}>
        <CardTitle className="text-center">{title}</CardTitle>
            <CardSubtitle className="p-1 text-center">{subtitle}</CardSubtitle>
        {lines}
        {extras}
    </CardBody></Card>
    )
};

export {getHelpContent, HelpBox};