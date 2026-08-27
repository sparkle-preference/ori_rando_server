import React from 'react';
import  {DropdownToggle, DropdownMenu, Dropdown, DropdownItem, Nav, NavLink, NavItem, Collapse,  Input, UncontrolledButtonDropdown, Button, 
        Row, FormFeedback, Col, Container, TabContent, TabPane, Modal, ModalHeader, ModalBody, ModalFooter, Media, ButtonGroup,
        InputGroup, InputGroupAddon} from 'reactstrap';
import { FaCog, FaSave, FaCopy, FaLock, FaPencilAlt, FaUndo, FaRedo } from 'react-icons/fa';
import {NotificationContainer, NotificationManager} from 'react-notifications';

import 'react-notifications/lib/notifications.css';
import './index.css';

import {getHelpContent, HelpBox} from "./helpbox.js";
import {History, HIST_KEYS, HIST_SET} from './history.js';
import {postNetForm, get_param, spawnKitFor, get_flag, ap_enabled, presets, select_theme, name_from_str, get_preset, player_icons, doNetRequest, get_random_loader, PickupSelect, Cent, dev, randInt, gotoUrl, prng, decompose_pickup, app_enabled} from './common.js';
import SiteBar from "./SiteBar.js";
import Select from 'react-select';
import {picks_by_zone} from './shared_map';


const zonesInOrder = ['Glades', 'Blackroot', 'Grove', 'Grotto', 'Ginso', 'Swamp', 'Valley', 'Misty', 'Forlorn', 'Sorrow', 'Horu'];
const locOptions = [{'label': 'Spawn With', 'value': 2}];
zonesInOrder.forEach(zone =>  picks_by_zone[zone].forEach(p => locOptions.push({'label': `${p.area} ${p.name} (${zone})`, 'value': p.loc})));
picks_by_zone['Mapstone'].forEach(p => locOptions.push({'label': p.name, 'value': p.loc}));
// Buried pseudo-locations: seedgen keeps these items out of the pool until N
// locations are reachable (loc key = BURIED_LOC_BASE + N)
const BURIED_LOC_BASE = 20000000;
// every ten from 50 to 200: a rolled burial can land on any of them, and the
// teleporter tiers reach exactly 50 at the shallow end and 200 at the deep
const BURIED_DEPTHS = Array.from({length: 16}, (_, i) => 50 + i * 10);
BURIED_DEPTHS.forEach(depth => locOptions.push(
    {'label': `Buried${String(depth).padStart(3, "0")} (held back until ${depth} locations are reachable)`, 'value': BURIED_LOC_BASE + depth}));
const locOptionFromCoords = (coords) => locOptions.find(l => l.value === coords);
// multipickup <-> part codes ("SK|3"), for merging burials into an existing row
const pickupToParts = (item) => {
    if(!item || item === "NO|1") return [];
    // only MU is decomposed: partsToPickup rebuilds as MU, so unwrapping an
    // RP/RP group here would silently drop the repeat/one-of. They nest fine.
    if(!item.startsWith("MU|")) return [item];
    let [code, id] = item.split("|");
    return decompose_pickup(code, id).map(([c, i]) => `${c}|${i}`);
}
// parts arrive decomposed (slashes literal), so re-escape on the way back in
const partToSegs = (p) => p.replaceAll("/", "//").replace(/\|/g, "/");
const partsToPickup = (parts) => parts.length === 0 ? "NO|1" : (parts.length === 1 ? parts[0] : "MU|" + parts.map(partToSegs).join("/"));
// blank rows to type into: paramsJson drops item NO|1, so these never reach a seed
// merge items into the Buried row(s) at the given depths for one world, creating rows
// as needed (items already buried there are skipped). Shared by the Advanced buttons
// and by Randomize, so both bury the same way.
const mergeBuried = (fassList, groups, world) => {
    let out = [...fassList];
    groups.forEach(({depth, items}) => {
        const loc = locOptionFromCoords(BURIED_LOC_BASE + depth);
        if(!loc)
            return;  // a depth with no option is a location nothing can name
        const idx = out.findIndex(f => (f.world || 1) === world && f.loc && f.loc.value === loc.value);
        if(idx > -1) {
            let parts = pickupToParts(out[idx].item);
            items.forEach(i => parts.includes(i) || parts.push(i));
            out[idx] = {...out[idx], item: partsToPickup(parts)};
        } else {
            out.push({loc: loc, item: partsToPickup(items), world: world, owner: world});
        }
    });
    return out;
};

const SPAWN_LOC = 2;
const fassDefaultsFor = (world) => [SPAWN_LOC, 919772].map(coords => ({loc: locOptionFromCoords(coords), item: "NO|1", world: world, owner: world}));
// "has the user put anything in the spawn fass_line" -- derived rather than stored,
// because a stored flag has to be cleared again on every path that empties the row.
// Scoped to the world in view: a preset loaded for another player must not quietly
// change what this one's spawn dropdown does.
const spawnFassSet = (fassList, world) => (fassList || []).some(
    f => f.loc && f.loc.value === SPAWN_LOC && f.item !== "NO|1" && (f.world || 1) === (world || 1));
const apDefaultExport = ["skills", "teleporters", "events"];
const GOAL_VARS = ["ForceTrees", "WorldTour", "ForceMaps", "WarmthFrags", "Bingo"];
// flags describing the game rather than a world; the rest ride on a world's row
const seedWideFlag = (flag) => flag === "DeathLink" ||
    ["share=", "mode=", "anti_bk_bias="].some(p => flag.startsWith(p));
// a preset describes one world, so a load drops the lobby. Mirrors SSP_DENY.
const SSP_LOBBY_KEYS = ["players", "playerNames", "coopGenMode", "coopGameMode", "dedupShared",
                        "antiBkBias", "syncShared", "shared", "teams", "apMode", "apExport", "apDeathLink",
                        "worldSettings"];
// dropped by every load path, lobby or not: the seed box is the user's to type,
// and the rest are outputs of a finished seed rather than form inputs.
const PRESET_NEVER_LOAD = ["seed", "flagLine", "isPlando", "spoilers", "teamStr"];
// accepts a full ?preset=owner:name url, the query alone, or a bare owner:name
const parsePresetLink = (text) => {
    let raw = (text || "").trim()
    if(!raw)
        return null
    let at = raw.indexOf("preset=")
    let pair = at === -1 ? raw : raw.slice(at + 7).split("&")[0]
    try {
        pair = decodeURIComponent(pair)
    } catch(e) {
        return null    // a stray % is not a link
    }
    let parts = pair.split(":")
    return (parts.length === 2 && parts[0].trim() && parts[1].trim()) ? [parts[0].trim(), parts[1].trim()] : null
};
// a preset in one line: logic mode, keymode, then up to three flags
const MINIMAL_FLAGS = 3;
const minimalFlagline = (blob) => {
    if(!blob)
        return ""
    let parts = []
    if(blob.paths && blob.paths.length) {
        let mode = get_preset(blob.paths)
        parts.push(mode.charAt(0).toUpperCase() + mode.slice(1))
    }
    if(blob.keyMode)
        parts.push(blob.keyMode)
    // a goal mode is a variation to the generator but the headline to a player, so it leads
    let vars = blob.variations || []
    let ordered = vars.filter(v => GOAL_VARS.includes(v)).concat(vars.filter(v => !GOAL_VARS.includes(v)))
    parts = parts.concat(ordered.slice(0, MINIMAL_FLAGS))
    return parts.join(", ") + (ordered.length > MINIMAL_FLAGS ? "..." : "")
};
// what a hover says about a preset: what the author wrote, then what it plays like
const presetHoverText = (desc, blob) => [desc, minimalFlagline(blob)].filter(Boolean).join("\n") || undefined;
// seedgen spells keymode None "Default" on the wire; the dropdown doesn't
const keyModeFromJson = (mode) => mode === "Default" ? "None" : mode;
// dropdown entries nobody can save over; "latest" carries its lobby, alone.
const PRESET_LAST = "latest", PRESET_DEFAULT = "default";
const presetLabel = (name) => name === PRESET_LAST ? "Last Seed"
                            : name === PRESET_DEFAULT ? "Default" : name;
// key order varies with which optional fields are set, so compare canonically
const canonSettings = (json) => JSON.stringify(Object.keys(json || {}).sort().map(k => [k, json[k]]));
// every form field a preset can carry; paramsJson omits defaults, so a stored preset is sparse
const PRESET_FORM_KEYS = ["keyMode", "fillAlg", "variations", "paths", "expPool", "cellFreq",
                          "selectedPool", "verboseSpoiler", "pathDiff", "senseData",
                          "fragCount", "fragReq", "relicCount", "bingoLines",
                          "bingoDiff", "bingoGoal", "bingoSquares", "bingoMeta", "bingoDisc",
                          "spawn", "spawnSKs", "spawnECs", "spawnHCs", "spawnWeights"];
// only the keys paramsJson would emit, gated on the same conditions
const livePresetKeys = (form) => {
    let ks = ["keyMode", "fillAlg", "variations", "paths", "expPool", "cellFreq",
              "selectedPool", "verboseSpoiler", "pathDiff", "senseData", "spawn"];
    let vars = form.variations || [];
    if(vars.includes("WarmthFrags")) ks.push("fragCount", "fragReq");
    if(vars.includes("WorldTour")) ks.push("relicCount");
    if(vars.includes("Bingo")) ks.push("bingoLines", "bingoDiff", "bingoGoal", "bingoSquares", "bingoMeta", "bingoDisc");
    if(form.spawn === "Random") ks.push("spawnWeights");
    else if(form.spawn && form.spawn !== "Glades") ks.push("spawnSKs", "spawnECs", "spawnHCs");
    return ks;
};
// the loaded preset's name is reserved or someone else's, so a copy needs its own
const nextPresetName = (list) => {
    let n = 1
    while(list.some(s => s.name === `Preset ${n}`)) n++
    return `Preset ${n}`
};
const PLAYER_NAME_MAX = 20;  // matches ap_models.PLAYER_NAME_MAX
const AP_DEFAULT_HOST = "archipelago.gg";
// ap/status idle stepdown: a forgotten tab can be visible, so hidden-gating
// alone can't shed it. [idle seconds before this tier, seconds per poll]
const AP_IDLE_TIERS = [[600, 30], [120, 15]];
// mw share name for each ap export category that can clash with it (shared
// singletons can't also go to the AP pool)
const apShareNames = {"skills": "Skills", "teleporters": "Teleporters", "events": "World Events", "upgrades": "Upgrades"};
const getPool = (pool_name) => { switch(pool_name) {
    case "Standard": 
        return [
            {item: "TP|Grove", count: 1}, 
            {item: "TP|Swamp", count: 1},
            {item: "TP|Grotto", count: 1},
            {item: "TP|Valley", count: 1},
            {item: "TP|Sorrow", count: 1},
            {item: "TP|Ginso", count: 1},
            {item: "TP|Horu", count: 1},
            {item: "TP|Forlorn", count: 1},
            {item: "HC|1", count: 12},
            {item: "EC|1", count: 15, minimum: 4},
            {item: "AC|1", count: 33},
            {item: "RB|0", count: 3},
            {item: "RB|1", count: 3},
            {item: "RB|6", count: 3},
            {item: "RB|9", count: 1},
            {item: "RB|10", count: 1},
            {item: "RB|11", count: 1},
            {item: "RB|12", count: 1},
            {item: "RB|13", count: 3},
            {item: "RB|15", count: 3},
        ];
    case "Hard": 
        return [
            {item: "TP|Grove", count: 1}, 
            {item: "TP|Swamp", count: 1},
            {item: "TP|Grotto", count: 1},
            {item: "TP|Valley", count: 1},
            {item: "TP|Sorrow", count: 1},
            {item: "EC|1", count: 4, minimum: 4},
        ];
    case "Competitive": 
        return [
            {item: "TP|Grove", count: 1}, 
            {item: "TP|Swamp", count: 1},
            {item: "TP|Grotto", count: 1},
            {item: "TP|Valley", count: 1},
            {item: "TP|Sorrow", count: 1},
            {item: "TP|Forlorn", count: 1},
            {item: "HC|1", count: 12},
            {item: "EC|1", count: 15, minimum: 4},
            {item: "AC|1", count: 33},
            {item: "RB|0", count: 3},
            {item: "RB|1", count: 3},
            {item: "RB|6", count: 3},
            {item: "RB|9", count: 1},
            {item: "RB|10", count: 1},
            {item: "RB|11", count: 1},
            {item: "RB|12", count: 1},
            {item: "RB|13", count: 3},
            {item: "RB|15", count: 3},
        ];
    case "Extra Bonus": 
        return [
            {item: "TP|Grove", count: 1}, 
            {item: "TP|Swamp", count: 1},
            {item: "TP|Grotto", count: 1},
            {item: "TP|Valley", count: 1},
            {item: "TP|Sorrow", count: 1},
            {item: "TP|Ginso", count: 1},
            {item: "TP|Horu", count: 1},
            {item: "TP|Forlorn", count: 1},
            {item: "TP|Blackroot", count: 1},
            {item: "HC|1", count: 12},
            {item: "EC|1", count: 15, minimum: 4},
            {item: "AC|1", count: 33},
            {item: "RP|RB/0", count: 3},
            {item: "RP|RB/1", count: 3},
            {item: "RB|6", count: 5},
            {item: "RB|9", count: 1},
            {item: "RB|10", count: 1},
            {item: "RB|11", count: 1},
            {item: "RB|12", count: 2},
            {item: "RB|37", count: 2},
            {item: "RB|13", count: 3},
            {item: "RB|15", count: 3},
            {item: "RB|31", count: 1},
            {item: "RB|32", count: 1},
            {item: "RB|33", count: 2},
            {item: "RG|RB/12/RB/33/RB/37", count: 3},
            {item: "RB|36", count: 1},
            {item: "BS|*", count: 4, maximum: 7},
            {item: "WP|*", count: 4, upTo: 8, maximum: 14},
        ]
    case "Bonus Lite": 
        return [
            {item: "TP|Grove", count: 1}, 
            {item: "TP|Swamp", count: 1},
            {item: "TP|Grotto", count: 1},
            {item: "TP|Valley", count: 1},
            {item: "TP|Sorrow", count: 1},
            {item: "TP|Ginso", count: 1},
            {item: "TP|Horu", count: 1},
            {item: "TP|Forlorn", count: 1},
            {item: "TP|Blackroot", count: 1},
            {item: "HC|1", count: 12},
            {item: "EC|1", count: 15, minimum: 4},
            {item: "AC|1", count: 33},
            {item: "RB|0", count: 3},
            {item: "RB|1", count: 3},
            {item: "RB|6", count: 5},
            {item: "RB|9", count: 1},
            {item: "RB|10", count: 1},
            {item: "RB|11", count: 1},
            {item: "RB|12", count: 2},
            {item: "RB|37", count: 2},
            {item: "RB|13", count: 3},
            {item: "RB|15", count: 3},
            {item: "RB|31", count: 1},
            {item: "RB|32", count: 1},
            {item: "RB|33", count: 2},
            {item: "RG|RB/12/RB/33/RB/37", count: 3},
            {item: "RB|36", count: 1},
            {item: "WP|*", count: 4, upTo: 8, maximum: 14},
        ]
    default:
        dev && console.log(`${pool_name} is not a valid pool name! Using the standard pool instead`)
        return getPool("Standard")
    }
}
const CANONICAL_ORDERING = {}
getPool("Extra Bonus").forEach(({item}, i) => CANONICAL_ORDERING[item] = i)
CANONICAL_ORDERING["RB|0"] = CANONICAL_ORDERING["RP|RB/0"] 
CANONICAL_ORDERING["RB|1"] = CANONICAL_ORDERING["RP|RB/1"] 
const get_canon_index = ({item}) => CANONICAL_ORDERING[item]+1 || 99
const keymode_options = ["None", "Shards", "Limitkeys", "Clues", "Free"];

const VERSION = get_param("version")
// moves on a site-only release, so the changelog link goes unread for those too
const NOTES_ANCHOR = get_param("notes_anchor") || VERSION
const SPAWN_TPS = ["Glades", "Grove", "Swamp", "Grotto", "Forlorn", "Valley", "Horu", "Ginso", "Sorrow", "Blackroot"]

const VAR_NAMES = {
    // variations that are hungry
    Starved: "Starved",
    TPStarved: "TPStarved",
    WallStarved: "WallStarved",
    GrenadeStarved: "GrenadeStarved",

    // variations that are variations
    DoubleSkills: "Extra Copies",
    GoalModeFinish: "Skip Final Escape",
    OpenWorld: "Open World",
    InLogicWarps: "In-Logic Warps",
    Keysanity: "Keysanity",
    Enhanced: "Enhanced",
    Entrance: "Entrance Shuffle",
    OHKO: "One Hit KO",
    "0XP": "Zero Experience",

    // item pools that are secretly variations
    Hard: "Hard Mode",
    BonusPickups: "More Bonus Pickups",

    // goal modes are secretly variations
    ForceMaps: "Force Maps",
    ForceTrees: "Force Trees",
    WarmthFrags: "Warmth Frags",
    WorldTour: "World Tour",
    Bingo: "Bingo",

    // variations that are stupid legacy bullshit
    StrictMapstones: "Strict Mapstones",
    StompTriggers: "Legacy Kuro Behavior",
    ClosedDungeons: "Closed Dungeons",
}

const VAR_WEIGHTS = {
    Starved: .1,
    OHKO: .005,
    "0XP": .01,
    OpenWorld: .25,
    DoubleSkills: .1,
    GoalModeFinish: .1,
    InLogicWarps: .25, // these last ones should be lower after april 1st
    Entrance: .2,
    Keysanity: .2,     // this one especially. hahaha holy shit.
    Enhanced: .2,
}


const SPAWN_OPTS = ["Random", "Glades", "Grove", "Swamp", "Grotto", "Forlorn", "Valley", "Horu", "Ginso", "Sorrow", "Blackroot"]
// randomize stars the mode when a variation bans paths, so match the prefix
const cellFreqPresets = (preset) => preset.startsWith("casual") ? 20 : (preset.startsWith("standard") ? 40 : 256)
// 3 is rolled on its own; these share what is left, evenly
const BINGO_LINE_CHOICES = [1, 2, 4, 5, 7, 11]
// what Randomize can bury. The first four mirror the Advanced buttons; POWER_SKILLS
// is Lapis's grouping and exists nowhere else in the codebase.
const GRENADE = "SK|51"
const WALL_SKILLS = ["SK|3", "SK|12"]                              // wall jump, climb
const POWER_SKILLS = ["SK|0", "SK|8", "SK|50"]                     // bash, charge jump, dash
const TELEPORTER_TIERS = [["TP|Grove", "TP|Swamp", "TP|Grotto", "TP|Valley"],
                          ["TP|Forlorn", "TP|Sorrow", "TP|Ginso", "TP|Horu"]]
const ALL_SKILLS = ["SK|0", "SK|2", "SK|3", "SK|4", "SK|5", "SK|8", "SK|12", "SK|14", "SK|15", "SK|50", GRENADE]
const optionalPaths = ['casual-dboost', 'standard-core', 'standard-dboost', 'standard-lure', 'standard-abilities', 'expert-core', 'expert-dboost', 'expert-lure', 'expert-abilities', 'dbash', 'master-core', 'master-dboost', 'master-lure', 'master-abilities', 'gjump', 'glitched', 'timed-level', 'insane']
const varPaths = {"master": ["Starved"]}
const diffPaths = {"glitched": "Hard", "master": "Hard"}
// an emptied box parses to NaN, which the generator takes as null and dies on
const numOr = (raw, dflt) => { let n = parseInt(raw, 10); return isNaN(n) ? dflt : n }
const disabledPaths = {
                    "0XP": ["glitched", "standard-abilities", "expert-abilities", "master-abilities", "master-dboost", "timed-level", "insane"], 
                    "OHKO": ["casual-dboost", "standard-dboost", "expert-dboost", "master-dboost", "glitched", "master-lure"]
                    }
const revDisabledPaths = {}
Object.keys(disabledPaths).forEach(v => disabledPaths[v].forEach(path => revDisabledPaths.hasOwnProperty(path) ? revDisabledPaths[path].push(v) : revDisabledPaths[path] = [v]))


export default class MainPage extends React.Component {
    helpEnter = (category, option, timeout=250, extra) => () => {clearTimeout(this.state.helpTimeout) ; this.setState({helpTimeout: setTimeout(this.help(category, option, extra), timeout)})}
    helpLeave = () => clearTimeout(this.state.helpTimeout) 
    help = (category, option, extra) => () => this.setState({helpcat: category, helpopt: option, helpParams: {...getHelpContent(category, option), ...extra}})
    

    // an emptied number box parses to NaN
    updateItemCount = (index, newVal, {minimum}) => this.setState(prev => {
        minimum = minimum || 0
        let x = Math.max(newVal || 0, minimum)
        let itemPool = [...prev.itemPool]
        itemPool[index] = {...itemPool[index], count: x}
        return {itemPool: itemPool, selectedPool: "Custom"}
    })
    updateItemUpTo = (index, newVal) => this.setState(prev => {
        let itemPool = [...prev.itemPool]
        itemPool[index] = {...itemPool[index], upTo: newVal}
        return {itemPool: itemPool, selectedPool: "Custom"}
 })
    updatePoolItem = (index, code) => this.setState(prev => {
        let itemPool = [...prev.itemPool]
        itemPool[index] = {...itemPool[index], item: code}
        return {itemPool: itemPool, selectedPool: "Custom"}
    })
    deletePoolItem = (index) => () => this.setState(prev => {
        return {itemPool: prev.itemPool.filter((_, i) => i !== index), selectedPool: "Custom"}
  })
    addPoolItem = (code) => this.setState(prev => {
        this.refs.tabula.clear()
        return {itemPool: prev.itemPool.concat({item: code, count: 1}), selectedPool: "Custom"}
    }
)


    getItemPoolTab = ({inputStyle}) => {
        let itemSelectors = this.state.itemPool.map((row, index) => {
          let disabled = row.minimum && row.minimum > 0
          let delButton = disabled ? null : (<Button onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", "deleteRow")} onClick={this.deletePoolItem(index)} color="danger">X</Button>)
          
          return (<Row key={`pool-row-${index}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "customPool")} className="p-1 justify-content-center">
            <Col xs="4">
            <Cent>
                <Input  onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", "count")} type="number" className="mr-2" style={inputStyle} invalid={row.maximum && row.maximum < row.row} value={row.count} onChange={(e) => this.updateItemCount(index, parseInt(e.target.value, 10), row)}/>
                <FormFeedback tooltip="true">Maximum number of {name_from_str(row.item)} allowed is {row.maximum}</FormFeedback>
                {" - "}
                <Input type="number" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", "upTo")}  invalid={row.upTo && (row.upTo < row.count || (row.maximum && row.maximum < row.upTo))} className="ml-2" style={inputStyle} value={row.upTo || row.count} onChange={(e) => this.updateItemUpTo(index, parseInt(e.target.value, 10))}/>
                <FormFeedback tooltip="true">{row.upTo < row.count ? `Max count can't be lower than min count(${row.count})` : `Maximum number of ${name_from_str(row.item)} allowed is ${row.maximum}`}</FormFeedback>
            </Cent>
            </Col>
            <Col onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", disabled ? "pickupSelectorDisabled" : row.item)} xs="7">
                <PickupSelect value={row.item} isClearable={false} isDisabled={disabled} updater={(code, _) => this.updatePoolItem(index, code)} allowPsuedo allowGroup/>
            </Col>
            <Col xs="1">{delButton}</Col>
          </Row>)
        })

        return (
        <TabPane className="p-3 border" tabId="item pool" data-hist="itemPool">
            {itemSelectors}
            <Row data-hist="itemPoolAdd" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "customPool")} className="p-1 justify-content-center">
            <Col xs="4">
                <Cent>
                    <Input type="number" className="mr-2" style={inputStyle} value={1} disabled/>
                    {" - "}
                    <Input type="number" className="ml-2" style={inputStyle} value={1} disabled/>
                </Cent>
                </Col>
                <Col xs="7" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", "pickupSelector")} >
                    <PickupSelect ref="tabula" value={"NO|1"} updater={(code, _) => this.addPoolItem(code)} allowPsuedo allowGroup/>
                </Col>
                <Col xs="1"></Col>
            </Row>
        </TabPane>
        )

    }
    
    spoilerUrl = (paramId, download, multi, p) => {
        let {active, exclude, byZone} = this.state.auxSpoiler
        let url;
        if(active) {
            url = new URL(`/generator/aux_spoiler/${paramId}`, window.document.URL);
            url.searchParams.set('exclude', exclude.join(" "));
            if(byZone)
                url.searchParams.set('by_zone', 1)
        } else
            url = new URL(`/generator/spoiler/${paramId}`, window.document.URL);
        // AP spoilers and item lists resolve real placements from the game's room
        if(this.state.inputApMode && ap_enabled() && this.state.gameId > 0)
            url.searchParams.set('game_id', this.state.gameId)
        if(download)
            url.searchParams.set("download", 1);
        if(multi)
            url.searchParams.set("player_id", p);
        return url.href
    }

    getAdvancedTab = ({inputStyle, menuStyle}) => {
        let {senseData, fillAlg, spawnSKs, spawnECs, spawnHCs, expPool, bingoLines, pathDiff, cellFreq, 
            relicCount, fragCount, fragReq, spawnWeights, spawn, verboseSpoiler, fassList,
            bingoDiff, bingoGoal, bingoSquares, bingoMeta, bingoDisc} = this.state
        let [leftCol, rightCol] = [4, 7]
        // a doubled row is label + control twice over, spanning the columns a single row does
        const [halfLabelCols, narrowCols] = [2.5, 2]
        const wideCols = leftCol + rightCol - 2 * halfLabelCols - narrowCols
        const colWidth = (cols) => ({flex: `0 0 ${100 * cols / 12}%`, maxWidth: `${100 * cols / 12}%`})
        // data-hist is the undo flash's id: optional, and never interpolated from form state
        const halfLabel = (text, help) => (
            <Col data-hist={help} style={colWidth(halfLabelCols)} className="text-center px-1 border" onMouseLeave={this.helpLeave}
                 onMouseEnter={this.helpEnter("advanced", help)}>
                <Cent>{text}</Cent>
            </Col>)
        const halfCtl = (cols) => (help, children) => (
            <Col data-hist={help} style={colWidth(cols)} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", help)}>
                {children}
            </Col>)
        const [narrowCtl, wideCtl] = [halfCtl(narrowCols), halfCtl(wideCols)]
        const sectionLabel = (text, help) => (
            <Row className="justify-content-center pb-2">
                <Col xs={leftCol} className="text-center pt-1" onMouseLeave={this.helpLeave}
                     onMouseEnter={this.helpEnter("advanced", help)}>
                    <Cent>{text}</Cent>
                </Col>
            </Row>)
        let weightSelectors = spawnWeights.map((weight, index) => (
            <Col data-hist={`spawnWeight-${SPAWN_TPS[index]}`} xs="4" key={`weight-selector-${index}`} className="text-center border">
                    <Col onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "spawnWeights")}><Cent>{SPAWN_TPS[index]}</Cent></Col>
                    <Col onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "spawnWeights")}>
                        <Input style={inputStyle} type="number" value={weight} invalid={weight < 0} onChange={(e) => {
                            let sw = [...spawnWeights]
                            sw[index] = parseFloat(e.target.value, 10)
                            this.setState({spawnWeights: sw})
                        }}/> 
                        <FormFeedback tooltip="true">Weights can't be less than 0</FormFeedback>
                    </Col>
            </Col>
        ))
        let pathDiffOptions = ["Easy", "Normal", "Hard"].map(mode => (
            <DropdownItem key={`pd-${mode}`} active={mode===pathDiff} onClick={()=> this.setState({pathDiff: mode})}>{mode}</DropdownItem>
        ))
        const isMW = this.isMultiworld()
        const fassWorld = isMW ? this.state.fassWorld : 1
        const players = this.state.players
        const fassUsed = new Set(fassList.filter(f => (f.world || 1) === fassWorld).map(({loc}) => loc.value));
        const ownerDropdown = (i, loc, world, owner) => (
            <Col xs="2">
                <UncontrolledButtonDropdown className="w-100">
                    <DropdownToggle caret block color="primary" disabled={loc.value === 2}> {`P${loc.value === 2 ? world : (owner || world)}`} </DropdownToggle>
                    <DropdownMenu style={menuStyle}>
                        {[...Array(players).keys()].map(x => x+1).map(o => (
                            <DropdownItem key={`fass-owner-${i}-${o}`} active={o === (owner || world)} onClick={() => this.onFassList(i, {owner: o})}>{`P${o}'s item`}</DropdownItem>
                        ))}
                    </DropdownMenu>
                </UncontrolledButtonDropdown>
            </Col>
        )
        let fass_rows = fassList.map(({loc, item, world, owner}, i) => ((world || 1) !== fassWorld) ? null : (
            <Row key={`fass-arbitrary-${i}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "preplacement")} className="p-1 justify-content-center">
                    <Col xs={isMW ? leftCol : leftCol+1}>
                        <Select theme={select_theme} className="align-middle" options={locOptions.filter(l => l.value === loc.value || !fassUsed.has(l.value))} value={loc} onChange={(newLoc) => this.onFassList(i, {loc: newLoc})}></Select>
                    </Col><Col xs={isMW ? rightCol-2 : rightCol-1}>
                        <PickupSelect value={item} updater={(code, _) => this.onFassList(i, {item: code})} allowGroup/>
                    </Col>
                    {isMW ? ownerDropdown(i, loc, world || 1, owner) : null}
            </Row>
        )).filter(r => r);
        if(isMW) fass_rows.unshift((
            <Row key={`fass-world-tabs`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "preplacement")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Preplacement World</Cent>
                    </Col><Col xs={rightCol}>
                        <UncontrolledButtonDropdown className="w-100">
                            <DropdownToggle color="primary" caret block>{`P${fassWorld}'s world`}</DropdownToggle>
                            <DropdownMenu style={menuStyle}>
                                {[...Array(players).keys()].map(x => x+1).map(w => (
                                    <DropdownItem key={`fass-world-${w}`} active={fassWorld === w} onClick={() => this.onFassWorld(w)}>{`P${w}'s world`}</DropdownItem>
                                ))}
                            </DropdownMenu>
                        </UncontrolledButtonDropdown>
                    </Col>
            </Row>
        ))
        fass_rows.push((
            <Row key={`fass-arbitrary-next`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "preplacement")} className="p-1 justify-content-center">
                    <Col xs={isMW ? leftCol : leftCol+1}>
                    <Select theme={select_theme} className="align-middle" options={locOptions.filter(l => !fassUsed.has(l.value))} value={{label: 'Add new Placement:', value: -1}} onChange={(newLoc) => this.addToFassList({loc: newLoc, item: "NO|1"})}></Select>
                    </Col><Col xs={isMW ? rightCol-2 : rightCol-1}>
                        <PickupSelect ref="fassTabula" value={"NO|1"} updater={(code, _) => this.addToFassList({item: code})} allowGroup/>
                    </Col>
                    {isMW ? <Col xs="2"/> : null}
            </Row>
        ))
        let goalCol = (v) => (
            <Col xs="6" onMouseLeave={this.helpEnter("advanced", "goalModes")} onMouseEnter={this.helpEnter("goalModes", v)} className="px-2 py-1">
                <Button data-hist={`goal-${v}`} color="primary" block outline={!this.hasVar(v)} onClick={this.onGoalModeAdvanced(v)}>{VAR_NAMES[v]}</Button>
            </Col>
        )
        let legacyVars = ["StompTriggers", "StrictMapstones", "ClosedDungeons"].map(v=> {
            let name = VAR_NAMES[v];
            return (
            <Col key={`var-button-${v}`} xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", v)} className="p-2">
                <Button data-hist={`var-${v}`} block color="primary" outline={!this.hasVar(v)} onClick={this.onVar(v)}>{name}</Button>
            </Col>
            )});
        return (
            <TabPane className="p-3 border" tabId="advanced">
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "goalModes")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Goal Modes</Cent>
                    </Col>
                    <Col xs={rightCol}>
                        <Row>
                            {goalCol("WorldTour")}
                            {goalCol("WarmthFrags")}
                            {goalCol("ForceTrees")}
                            {goalCol("ForceMaps")}
                        </Row>
                    </Col>
                </Row>
                <Row className="p-1 justify-content-center">
                    {halfLabel("Exp Pool", "expPool")}
                    {narrowCtl("expPool", <React.Fragment>
                        <Input style={inputStyle} type="number" value={expPool} invalid={expPool < 100} onChange={(e) => this.setState({expPool: parseInt(e.target.value, 10)})}/>
                        <FormFeedback tooltip="true">Experience Pool must be at least 100</FormFeedback>
                    </React.Fragment>)}
                    {halfLabel("Fill Algorithm", "fillAlg")}
                    {wideCtl("fillAlg",
                        <UncontrolledButtonDropdown className="w-100">
                            <DropdownToggle color="primary" caret block> {fillAlg} </DropdownToggle>
                            <DropdownMenu style={menuStyle}>
                                <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", this.isMultiworld() ? "fillAlgClassicMulti" : "fillAlgClassic")}  active={"Classic" ===fillAlg} onClick={()=> this.setState({fillAlg: "Classic"})}>Classic</DropdownItem>
                                <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fillAlgBalanced")} active={"Balanced"===fillAlg} onClick={()=> this.setState({fillAlg: "Balanced"})}>Balanced</DropdownItem>
                            </DropdownMenu>
                        </UncontrolledButtonDropdown>)}
                </Row>
                <Row className="p-1 justify-content-center">
                    {halfLabel("Cell Frequency", "cellFreq")}
                    {narrowCtl("cellFreq", <React.Fragment>
                        <Input style={inputStyle} type="number" value={cellFreq} invalid={cellFreq < 3} onChange={(e) => this.setState({cellFreq: parseInt(e.target.value, 10)})}/>
                        <FormFeedback tooltip="true">Cell Frequency must be at least 3</FormFeedback>
                    </React.Fragment>)}
                    {halfLabel("Path Difficulty", "pathDiff")}
                    {wideCtl("pathDiff",
                        <UncontrolledButtonDropdown className="w-100">
                            <DropdownToggle color="primary" caret block> {pathDiff} </DropdownToggle>
                            <DropdownMenu style={menuStyle}> {pathDiffOptions} </DropdownMenu>
                        </UncontrolledButtonDropdown>)}
                </Row>
                <Row className="p-1 justify-content-center">
                    {halfLabel("Verbose Spoiler", "verbose")}
                    {narrowCtl("verbose",
                        <Button color="primary" block outline={!verboseSpoiler} onClick={() => this.setState({verboseSpoiler: !verboseSpoiler})}>{verboseSpoiler ? "Enabled" : "Disabled"}</Button>)}
                    {halfLabel("Sense Triggers", "sense")}
                    {wideCtl("sense",
                        <Input style={inputStyle} type="text" value={senseData || ""} onChange={(e) => this.setState({senseData: e.target.value})}/>)}
                </Row>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "buriedPresets")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Bury Items ([Item]Starved)</Cent>
                    </Col><Col xs={rightCol}>
                        <ButtonGroup className="w-100">
                            <Button data-hist="buryWalls" color="primary" outline onClick={this.buryItems([{depth: 50, items: ["SK|3", "SK|12"]}])}>Walls</Button>
                            <Button data-hist="buryGrenade" color="primary" outline onClick={this.buryItems([{depth: 50, items: ["SK|51"]}])}>Grenade</Button>
                            <Button data-hist="buryTeleporters" color="primary" outline onClick={this.buryItems([{depth: 50, items: ["TP|Grove", "TP|Swamp", "TP|Grotto", "TP|Valley"]},
                                                                                     {depth: 100, items: ["TP|Forlorn", "TP|Sorrow", "TP|Ginso", "TP|Horu"]}])}>Teleporters</Button>
                        </ButtonGroup>
                    </Col>
                </Row>
                <div className="border rounded p-1 m-1" data-hist="preplacement">
                    {sectionLabel("Preplacement", "preplacement")}
                    {fass_rows}
                </div>
                <Collapse isOpen={this.hasVar("Bingo")}>
                <div className="border rounded p-1 m-1">
                {sectionLabel("Bingo Settings", "bingoSettings")}
                <Row data-hist="bingoDiff" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "bingoDiff")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Board Difficulty</Cent>
                    </Col><Col xs={rightCol}>
                        <ButtonGroup className="w-100">
                            {["easy", "normal", "hard"].map(d => (
                                <Button key={`bingo-diff-${d}`} className="text-capitalize" color="primary"
                                        active={bingoDiff === d} outline={bingoDiff !== d}
                                        onClick={() => this.setState({bingoDiff: d})}>{d}</Button>))}
                        </ButtonGroup>
                    </Col>
                </Row>
                <Row data-hist="bingoGoal" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "bingoGoal")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Win By</Cent>
                    </Col><Col xs={rightCol}>
                        <ButtonGroup className="w-100">
                            <Button color="primary" active={bingoGoal === "bingos"} outline={bingoGoal !== "bingos"}
                                    onClick={() => this.setState({bingoGoal: "bingos"})}>Lines</Button>
                            <Button color="primary" active={bingoGoal === "squares"} outline={bingoGoal !== "squares"}
                                    onClick={() => this.setState({bingoGoal: "squares"})}>Squares</Button>
                        </ButtonGroup>
                    </Col>
                </Row>
                <Collapse isOpen={bingoGoal === "bingos"}>
                <Row data-hist="bingoLines" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "bingoLines")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Bingo Lines</Cent>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="number" value={bingoLines} invalid={bingoLines > 12 || bingoLines < 1} onChange={(e) => this.setState({bingoLines: parseInt(e.target.value, 10)})}/> 
                        <FormFeedback tooltip="true">Line count must be between 1 and 12</FormFeedback>
                    </Col>
                </Row>
                </Collapse>
                <Collapse isOpen={bingoGoal === "squares"}>
                <Row data-hist="bingoSquares" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "bingoSquares")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Squares to Win</Cent>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="number" value={bingoSquares} invalid={bingoSquares > 25 || bingoSquares < 1} onChange={(e) => this.setState({bingoSquares: parseInt(e.target.value, 10)})}/> 
                        <FormFeedback tooltip="true">Squares must be between 1 and 25</FormFeedback>
                    </Col>
                </Row>
                </Collapse>
                <Row data-hist="bingoMeta" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "bingoMeta")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Meta Bingo</Cent>
                    </Col><Col xs={rightCol}>
                        <Button color="primary" block active={bingoMeta} outline={!bingoMeta}
                                onClick={() => this.setState({bingoMeta: !bingoMeta})}>{bingoMeta ? "Enabled" : "Disabled"}</Button>
                    </Col>
                </Row>
                <Row data-hist="bingoDisc" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "bingoDisc")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Discovery Mode</Cent>
                    </Col><Col xs={rightCol}>
                        <Button color="primary" block active={bingoDisc > 0} outline={!bingoDisc}
                                onClick={() => this.setState({bingoDisc: bingoDisc > 0 ? 0 : 2})}>{bingoDisc > 0 ? "Enabled" : "Disabled"}</Button>
                    </Col>
                </Row>
                <Collapse isOpen={bingoDisc > 0}>
                <Row data-hist="bingoRevealed" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "bingoDisc")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Revealed Squares</Cent>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="number" value={bingoDisc} invalid={bingoDisc > 25 || bingoDisc < 1} onChange={(e) => this.setState({bingoDisc: parseInt(e.target.value, 10)})}/> 
                        <FormFeedback tooltip="true">Revealed squares must be between 1 and 25</FormFeedback>
                    </Col>
                </Row>
                </Collapse>
                </div>
                </Collapse>
                <Collapse isOpen={this.hasVar("WorldTour")}>
                    <Row data-hist="relicCount" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "relicCount")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center border">
                            <Cent>Relic Count</Cent>
                        </Col><Col xs={rightCol}>
                            <Input style={inputStyle} type="number" value={relicCount} invalid={relicCount > 11 || relicCount < 1} onChange={(e) => this.setState({relicCount: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip="true">Relic count must be greater than 0 and less than 12</FormFeedback>
                        </Col>
                    </Row>
                </Collapse>
                <Collapse isOpen={this.hasVar("WarmthFrags")}>
                    <Row data-hist="fragCount" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fragCount")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center border">
                            <Cent>Fragment Count</Cent>
                        </Col><Col xs={rightCol}>
                            <Input style={inputStyle} type="number" value={fragCount} invalid={fragCount > 60 || fragCount < 1} onChange={(e) => this.setState({fragCount: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip="true">Frag Count must be between 1 and 60</FormFeedback>
                        </Col>
                    </Row>
                    <Row data-hist="fragReq" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fragRequired")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center border">
                            <Cent>Fragments Required</Cent>
                        </Col><Col xs={rightCol}>
                            <Input style={inputStyle} type="number" value={fragReq} invalid={fragCount < fragReq || fragReq <= 0} onChange={e => this.setState({fragReq: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip="true">Fragments Required must be between 0 and Fragment Count ({fragCount})</FormFeedback>
                        </Col>
                    </Row>
                </Collapse>
                <Collapse isOpen={spawn !== "Random" && spawn !== "Glades"}>
                <Row data-hist="spawnSKs" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "spawnSkills")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Randomized Starting Skills</Cent>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="text" value={spawnSKs} invalid={spawnSKs < 0 || spawnSKs > 10 } onChange={(e) => this.setState({spawnSKs: numOr(e.target.value, 0)})}/> 
                        <FormFeedback tooltip="true">Can't spawn with less than 0 or more than 10 skills</FormFeedback>
                    </Col>
                </Row>
                <Row data-hist="spawnHCs" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "spawnHCs")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Starting Health</Cent>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="text" value={spawnHCs} invalid={spawnHCs < 3} onChange={(e) => this.setState({spawnHCs: numOr(e.target.value, 3)})}/> 
                        <FormFeedback tooltip="true">Can't spawn with fewer than 3 Health</FormFeedback>
                    </Col>
                </Row>
                <Row data-hist="spawnECs" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "spawnECs")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center border">
                        <Cent>Starting Energy</Cent>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="text" value={spawnECs} invalid={spawnECs < 1} onChange={(e) => this.setState({spawnECs: numOr(e.target.value, 1)})}/> 
                        <FormFeedback tooltip="true">Can't spawn with fewer than 1 Energy</FormFeedback>
                    </Col>
                </Row>
                </Collapse>
                <Collapse isOpen={spawn === "Random"}>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "spawnWeights")} className="p-1 justify-content-center">
                    {weightSelectors}
                </Row>
                </Collapse>
                <Row className="p-1 justify-content-center">
                    <Col onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "legacyFlags")} xs={leftCol} className="text-center border">
                        <Cent>Legacy Flags</Cent>
                    </Col><Col xs={rightCol}>
                    <Row>
                        {legacyVars}
                    </Row>
                    </Col>
                </Row>
            </TabPane>
        )
    }
    getMultiplayerTab = ({inputStyle, menuStyle}) => {
        let {shared, mwShared, players, tracking, coopGameMode, keyMode, coopGenMode, dedupShared, antiBkBias, apMode, apExport, apDeathLink} = this.state
        let shareButtons = (stypes, current, toggle, kind) => stypes.map(stype => (
            <Col xs="4" key={`share-${stype}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("Shared Item Categories", stype)} className="p-2">
                <Button data-hist={`${kind}-${stype.replace(" ", "")}`} block outline={!current.includes(stype)} onClick={toggle(stype)}>Share {stype}</Button>
            </Col>
        ))
        let multiplayerButtons = shareButtons(["Skills", "Teleporters", "Upgrades", "World Events", "Misc"], shared, this.onSType, "shared")
        // multiworld selections are stored separately (default none; shared
        // singletons are a spicier choice there), and no Misc: trees/relics/
        // keysanity keys stay per-world
        let mwShareButtons = shareButtons(["Skills", "Teleporters", "Upgrades", "World Events"], mwShared, this.onMWSType, "mwShared")
        let apFlag = ap_enabled()
        // ap export categories are server-side names; 'stones' covers
        // Mapstones, keysanity zone keys, and generic Keystones (tiered doors)
        let apExportButtons = [["skills", "Skills"], ["teleporters", "Teleporters"], ["events", "World Events"], ["cells", "Cells"], ["stones", "Stones"], ["upgrades", "Upgrades"]].map(([cat, label]) => (
            <Col xs="4" key={`ap-export-${cat}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("AP Export Categories", cat)} className="p-2">
                <Button data-hist={`apExport-${cat}`} block outline={!apExport.includes(cat)} onClick={this.onApExport(cat)}>Export {label}</Button>
            </Col>
        ))

        const perWorld = this.isMultiworld()
        const worldPresetCell = (i) => {
            if(!perWorld)
                return null
            if(i === 0)
                return (<Col xs="6" className="text-center font-italic text-muted">
                            <Cent>seed settings</Cent>
                        </Col>)
            const world = i + 1
            const pick = (name) => () => this.setWorldPreset(world, name)
            const info = this.worldPreset(world)
            return (
                <Col xs="6" data-hist={`worldPreset-${world}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "worldPresets")}>
                    <InputGroup>
                        <Input style={inputStyle} type="text" placeholder="same as world 1" invalid={!!info.bad}
                               title={presetHoverText(info.desc, this.state.worldSettings[i])}
                               value={this.worldPresetValue(world)}
                               onChange={(e) => this.onWorldPresetText(world, e.target.value)}
                               onBlur={() => this.resolveWorldPreset(world)}
                               onKeyPress={(e) => { if(e.key === "Enter") this.resolveWorldPreset(world) }}/>
                        <InputGroupAddon addonType="append">
                            <UncontrolledButtonDropdown>
                                <DropdownToggle color="primary" caret/>
                                <DropdownMenu right style={{zIndex: 10000, ...menuStyle}}>
                                    <DropdownItem active={!info.label} onClick={pick("")}>same as world 1</DropdownItem>
                                    {this.state.sspList.length ? <DropdownItem divider/> : null}
                                    {this.state.sspList.map(s => (
                                        <DropdownItem key={`w${world}-${s.name}`} active={info.label === s.name} onClick={pick(s.name)}>
                                            {s.name}
                                        </DropdownItem>))}
                                </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </InputGroupAddon>
                        <FormFeedback tooltip="true">Paste a preset share link</FormFeedback>
                    </InputGroup>
                </Col>)
        }
        let playerNameRows = !this.playerNamesShown() ? null : [...Array(players).keys()].map(i => (
            <Row key={`player-name-${i}`} className="p-1 justify-content-center">
                <Col xs="3" data-hist={`playerName-${i+1}`} className="text-center border" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "playerNames")}>
                    <Cent>{perWorld ? `P${i+1}'s Name / Settings` : `Player ${i+1} Name`}</Cent>
                </Col><Col xs={perWorld ? "3" : "4"} data-hist={`playerName-${i+1}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "playerNames")}>
                    <Input style={inputStyle} type="text" maxLength={PLAYER_NAME_MAX} placeholder={`Player ${i+1}`}
                           value={this.state.playerNames[i] || ""} onChange={this.onPlayerName(i)}/>
                </Col>
                {worldPresetCell(i)}
            </Row>
        ))
        let playerNumValid = tracking && players > 0;
        let playerNumFeedback = tracking ? (players > 0 ? null : (
            <FormFeedback tooltip="true">Need at least one player...</FormFeedback>
        )) : (
            <FormFeedback tooltip="true">Multiplayer modes require web tracking to be enabled</FormFeedback>
        )
        return (
             <TabPane className="p-3 border" tabId="multiplayer">
                <Row data-hist="players" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "playerCount")}  className="p-1 justify-content-center">
                    <Col xs="4" className="text-center border">
                        <Cent>Players</Cent>
                    </Col><Col xs="4">
                        <Input style={inputStyle} type="number" value={players} disabled={!tracking} invalid={!playerNumValid} onChange={(e) => this.setState({players: parseInt(e.target.value, 10)})}/> 
                        {playerNumFeedback }
                    </Col>
                </Row>
                <Row data-hist="coopGameMode" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "multiGameType")} className="p-1 justify-content-center">
                    <Col xs="4" className="text-center border">
                        <Cent>Multiplayer Game Type</Cent>
                    </Col><Col onMouseLeave={this.helpEnter("multiplayerOptions", "multiGameType")} onMouseEnter={this.helpEnter("multiplayerOptions", coopGameMode)} xs="4">
                        <UncontrolledButtonDropdown className="w-100" >
                            <DropdownToggle disabled={players < 2} color={players > 1 ? "primary" : "secondary"} caret block> {coopGameMode} </DropdownToggle>
                            <DropdownMenu style={menuStyle}>
                                <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "Race")} active={"Race"===coopGameMode} onClick={()=> this.setState({coopGameMode: "Race"})}>Race</DropdownItem>
                                <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "Co-op")} active={"Co-op"===coopGameMode} onClick={()=> this.setState({coopGameMode: "Co-op"})}>Co-op</DropdownItem>
                                <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "Multiworld")} active={"Multiworld"===coopGameMode} onClick={()=> this.setState({coopGameMode: "Multiworld"})}>Multiworld</DropdownItem>
                            </DropdownMenu>
                        </UncontrolledButtonDropdown>
                    </Col>
                </Row>
                <Collapse isOpen={players > 1 && coopGameMode === "Co-op"}>
                    <Row className="p-2">
                        {multiplayerButtons}
                        <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("Shared Item Categories", "Dedup")} className="p-2">
                            <Button data-hist="dedupShared" block outline={!dedupShared} active={dedupShared} disabled={coopGenMode!=="Cloned Seeds"} onClick={() => this.setState({dedupShared: !dedupShared})}>Dedup Shared</Button>
                        </Col>
                    </Row>
                </Collapse>
                <Collapse isOpen={this.isMultiworld()}>
                    <Row data-hist="antiBkBias" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "antiBkBias")} className="p-1 justify-content-center">
                        <Col xs="4" className="text-center border">
                            <Cent>Multiworld Balance Bias</Cent>
                        </Col><Col xs="4">
                            <Input style={inputStyle} type="number" step="0.1" min="0" max="1" value={antiBkBias} invalid={!(antiBkBias >= 0 && antiBkBias <= 1)} onChange={(e) => this.setState({antiBkBias: parseFloat(e.target.value)})}/>
                            <FormFeedback tooltip="true">Balance Bias is a value between 0.0 and 1.0</FormFeedback>
                        </Col>
                    </Row>
                    <Row className="p-2">
                        {mwShareButtons}
                    </Row>
                </Collapse>
                <Collapse isOpen={this.apAvailable()}>
                    <Row className="p-2">
                        <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "apMode")} className="p-2">
                            <Button data-hist="apMode" block outline={!apMode} active={apMode} onClick={this.onApMode}>Archipelago</Button>
                        </Col>
                    </Row>
                    <Collapse isOpen={apMode}>
                        <Row className="p-2">
                            {apExportButtons}
                        </Row>
                        <Row className="p-2">
                            <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "apDeathLink")} className="p-2">
                                <Button data-hist="apDeathLink" block outline={!apDeathLink} active={apDeathLink} onClick={() => this.setState({apDeathLink: !apDeathLink})}>Death Link</Button>
                            </Col>
                        </Row>
                    </Collapse>
                </Collapse>
                {playerNameRows}
            </TabPane>
        )
    }


    // the seedgen form as SeedGenParams reads it, minus the seed
    paramsJson = () => {
        let pMap = {"Race": "None", "None": "Default", "Co-op": "Shared", "World Events": "WorldEvents", "Cloned Seeds": "cloned", "Seperate Seeds": "disjoint"}
        let url = "/generator/build"
        let f = (p) => pMap.hasOwnProperty(p) ? pMap[p] : p
        let json = {
            "keyMode": f(this.state.keyMode),
            'fillAlg': this.state.fillAlg,
            'variations': this.state.variations,
            'paths': this.state.paths,
            "expPool": this.state.expPool,
            "cellFreq": this.state.cellFreq,
            "selectedPool": this.state.selectedPool,
            "verboseSpoiler": this.state.verboseSpoiler
        }
        if(this.state.pathDiff !== "Normal")
            json.pathDiff=this.state.pathDiff
        if(this.state.senseData)
            json.senseData=this.state.senseData
        if(this.hasVar("WarmthFrags"))
        {
            json.fragCount=this.state.fragCount
            json.fragReq=this.state.fragReq
        }
        if(this.hasVar("WorldTour"))
            json.relicCount=this.state.relicCount

        if(this.hasVar("Bingo"))
        {
            url += "?bingo=1"
            json.bingoLines = this.state.bingoLines;
            json.bingoDiff = this.state.bingoDiff;
            json.bingoGoal = this.state.bingoGoal;
            json.bingoSquares = this.state.bingoSquares;
            json.bingoMeta = this.state.bingoMeta;
            json.bingoDisc = this.state.bingoDisc;
        }
        if(this.state.spawn !== "Glades") {
            json.spawn = this.state.spawn;
            if(this.state.spawn !== "Random") {
                if(this.state.spawnSKs !== 0) 
                    json.spawnSKs = this.state.spawnSKs;
                if(this.state.spawnECs !== 1) 
                    json.spawnECs = this.state.spawnECs;
                if(this.state.spawnHCs !== 3) 
                    json.spawnHCs = this.state.spawnHCs;
                 // FIXME: when we allow setting random skills and health for random or glades spawns, fix this
            } else {
                json.spawnWeights = this.state.spawnWeights
            }
        }
        json.players=this.state.players
        if(this.playerNamesShown())
            json.playerNames = [...Array(this.state.players).keys()].map(i => this.state.playerNames[i] || "")
        // world 1 is the form above, so index 0 is always empty; an all-empty list is omitted
        if(this.isMultiworld()) {
            let worlds = [...Array(this.state.players).keys()].map(i => (i && this.state.worldSettings[i]) || {})
            if(worlds.some(w => Object.keys(w).length))
                json.worldSettings = worlds
        }
        json.fass = []
        this.state.fassList.forEach(fassEntry => {
                let world = fassEntry.world || 1
                let owner = fassEntry.owner || world
                // drop rows referencing players that no longer exist
                if(fassEntry.item !== "NO|1" && world <= this.state.players && owner <= this.state.players) {
                    json.fass.push({loc: fassEntry.loc.value.toString(), item: fassEntry.item, world: world, owner: owner})
                }
        });
        json.itemPool = {} //{"HC": 12, "EC": 15, "AC": 33, }
        this.state.itemPool.forEach(({item, count, upTo}) => { json.itemPool[item] = upTo ? [count, upTo] : [count] })
        json.tracking = this.state.tracking
        if(this.state.tracking && this.state.players > 1) {
            json.coopGenMode=f(this.state.coopGenMode)
            json.coopGameMode=f(this.state.coopGameMode)
            if(this.isMultiworld())
                json.antiBkBias = this.state.antiBkBias || 0
            // dedup and teams are cloned-seed concepts; multiworld worlds are
            // distinct by construction, and the server refuses to read them there
            if(this.state.coopGameMode === "Co-op") {
                json.dedupShared = this.state.dedupShared
                json.syncShared = this.state.shared.map(s => f(s))
                if(!this.state.dedupShared)
                    json.teams={1: [...Array(this.state.players).keys()].map(x=>x+1)}
            }
            if(this.isMultiworld())
                json.syncShared = this.state.mwShared.map(s => f(s))
        }
        // outside the players>1 block: a K=1 AP seed is one Ori world in
        // someone else's room. The guard also keeps a visitor without the
        // opt-in from rerolling a rehydrated AP params into a 409.
        if(this.apAvailable() && this.state.apMode) {
            json.apMode = true
            json.apExport = this.state.apExport
            json.apDeathLink = this.state.apDeathLink
            url += url.includes("?") ? "&ap_test=1" : "?ap_test=1"
        }
        return {json: json, url: url}
    }

    generateSeed = () => {
        if(this.apAvailable() && this.state.apMode && this.state.apExport.length === 0) {
            NotificationManager.error("Select at least one Archipelago export category", "Cannot generate seed!", 5000)
            this.setState({activeTab: 'multiplayer'})
            return
        }
        let {json, url} = this.paramsJson()
        // what the Seed tab is a seed of; undo compares against it, so take it before json.seed
        this.seedParams = canonSettings(json)
        let seed = this.state.seed || randInt(0, 1000000000);
        if(seed === "daily")
        {
            let d = new Date()
            let day = d.toLocaleString("en-US", {day: "2-digit", timeZone: "America/Los_Angeles"});
            let month = d.toLocaleString("en-US", {month: "2-digit", timeZone: "America/Los_Angeles"});
            let year = d.toLocaleString("en-US", {year: "numeric",  timeZone: "America/Los_Angeles"});
            seed = [year, month, day].join('-');
        } else if(seed === "vanilla") {
            window.location.href = "/vanilla"
            return
        }
        json.seed = seed
        this.helpEnter("general", "seedBuilding" + this.multi())()
        this.setState({seedIsGenerating: true, seedTabExists: true, seedStale: false, loader: get_random_loader(), activeTab: "seed"}, () => postGenJson(url, json, this.seedBuildCallback))
    }
    
    loadSspList = () => doNetRequest("/preset/list", ({status, responseText}) => {
        if(status !== 200)
            return
        let {owner, settings, hasLatest, restoreLastSeed} = JSON.parse(responseText)
        // absent means an older server: opening on the last seed is what it did
        this.restoreLastSeed = restoreLastSeed !== false
        this.setState({sspOwner: owner, sspList: settings || [], sspHasLatest: !!hasLatest}, () => {
            if(!hasLatest)
                return this.setState({sspLatest: null})
            doNetRequest("/preset/latest", ({status, responseText}) => {
                if(status !== 200)
                    return this.setState({sspLatest: null})
                let latest = JSON.parse(responseText).settings || {}
                this.setState({sspLatest: latest}, this.restoreLastUsed)
            })
        })
    })

    // a load merges: the lobby stays as the user left it, and preplacements are
    // replaced only in the world it lands in.
    mergeSettings = (settings, label, withLobby, key, owner, quiet) => {
        let update = {}
        // anything the preset does not mention goes back to its default
        PRESET_FORM_KEYS.forEach(k => { if(!(k in (settings || {}))) update[k] = this.defaultForm[k] })
        Object.keys(settings || {}).forEach(k => {
            if(PRESET_NEVER_LOAD.includes(k))
                return
            if(withLobby || !SSP_LOBBY_KEYS.includes(k))
                update[k] = settings[k]
        })
        if(withLobby) {
            // the lobby half of acceptMetadata; only "Last Seed" gets here
            update.inputPlayerCount = update.players
            update.playerNames = update.playerNames || []
            update.inputApMode = update.apMode || false
            if(update.coopGameMode === "Multiworld") {
                update.mwShared = update.shared || []
                delete update.shared
            }
            if(!update.apExport || update.apExport.length === 0)
                update.apExport = [...apDefaultExport]
        }
        if(update.keyMode)
            update.keyMode = keyModeFromJson(update.keyMode)
        if(update.paths)
            update.pathMode = get_preset(update.paths)
        if(update.variations) {
            update.goalModes = update.variations.filter(v => GOAL_VARS.includes(v))
            if(update.goalModes.length === 0)
                update.goalModes = ["None"]
        }
        // convert on shape: a blob may carry a pool without naming a preset
        if(update.itemPool && !Array.isArray(update.itemPool))
            update.itemPool = Object.keys(update.itemPool).map(i => ({item: i, count: update.itemPool[i][0], upTo: update.itemPool[i][1] || update.itemPool[i][0]})).sort((a, b) => get_canon_index(a) - get_canon_index(b))
        // a named pool is rebuilt, so saved settings follow later balance changes
        if(update.selectedPool && update.selectedPool !== "Custom")
            update.itemPool = getPool(update.selectedPool)
        // bingo and multiplayer both force tracking on, so a saved off can't win
        if(this.state.players > 1 || (update.goalModes || this.state.goalModes).includes("Bingo"))
            delete update.tracking
        let world = this.isMultiworld() ? (this.state.fassWorld || 1) : 1
        let loadedFass = (update.fass || []).map(({loc, item, code, id}) => (
            {loc: locOptionFromCoords(parseInt(loc, 10)), item: item || `${code}|${id}`, world: world, owner: world}))
        // a preset carrying no placements leaves the blank rows instead of emptying the section
        update.fassList = this.state.fassList.filter(f => (f.world || 1) !== world)
            .concat(loadedFass.length ? loadedFass : fassDefaultsFor(world))
        delete update.fass
        this.setState(update, () => {
            let landed = key || (label === "Default" ? PRESET_DEFAULT : this.state.sspName)
            this.markLoaded(landed, landed === PRESET_DEFAULT ? null : (owner === undefined ? this.state.sspOwner : owner), world)
            if(!quiet)
                NotificationManager.success(label, "Preset loaded", 4000)
        })
    }

    // the form as a preset would store it: what Update writes, and what drift means
    settingsNow = (world) => {
        let json = this.paramsJson().json, out = {}
        Object.keys(json).forEach(k => {
            if(!SSP_LOBBY_KEYS.includes(k) && !PRESET_NEVER_LOAD.includes(k))
                out[k] = json[k]
        })
        // one world's rows, mirroring settings_from: the rest are not this preset
        world = world || 1
        let fass = (out.fass || []).filter(f => (f.world || 1) === world && (f.owner || f.world || 1) === world)
                                   .map(({loc, item}) => ({loc: loc, item: item}))
        if(fass.length)
            out.fass = fass
        else
            delete out.fass
        return out
    }

    // What a stored blob means once loaded: its own values over the defaults for
    // whatever it leaves out. Two blobs are the same settings iff these match.
    denseOf = (blob) => {
        let form = {}
        PRESET_FORM_KEYS.forEach(k => {
            let v = (blob && k in blob) ? blob[k] : this.defaultForm[k]
            form[k] = (v === undefined || v === "") ? null : v
        })
        let out = {}
        livePresetKeys(form).forEach(k => { out[k] = form[k] })
        out.itemPool = (blob && blob.itemPool) || this.defaultSettings.itemPool
        out.fass = (((blob && blob.fass) || []).map(f => `${f.loc}|${f.item || (f.code + "|" + f.id)}`)).sort()
        return canonSettings(out)
    }

    // the name to show for settings the user just got back: Default if they are,
    // one of their presets if it is one, else whatever asked for them
    nameFor = (blob, fallback) => {
        let mine = this.denseOf(blob)
        if(mine === this.denseOf({}))
            return PRESET_DEFAULT
        let hit = this.state.sspList.find(s => s.blob && this.denseOf(s.blob) === mine)
        return hit ? hit.name : fallback
    }

    // names are unique per user, not globally, so a loaded preset needs its owner
    markLoaded = (name, owner, world, snapshot) => this.setState(prev => ({
        sspName: name,
        sspLoadedOwner: owner === undefined ? prev.sspOwner : owner,
        sspLoadedWorld: world || 1,
        sspLoaded: snapshot || canonSettings(this.settingsNow(world || 1)),
    }))

    // the class has to go and a reflow be taken before it returns, or a repeat flash never restarts
    histFlash = (ctl) => {
        clearTimeout(this.histFlashTimer)
        let stale = [...document.querySelectorAll(".hist-flash")]
        stale.forEach(el => el.classList.remove("hist-flash"))
        if(!ctl)
            return
        let hits = [...document.querySelectorAll(`[data-hist="${ctl}"]`)]
        hits.forEach(el => { void el.offsetWidth; el.classList.add("hist-flash") })
        this.histFlashTimer = setTimeout(() => hits.forEach(el => el.classList.remove("hist-flash")), 1200)
    }
    // the help pane bakes the loaded preset in at hover time, so a move has to re-bake it
    refreshPresetHelp = () => {
        let {helpcat, helpopt} = this.state
        if(helpcat === "general" && (helpopt === "savedSettings" || helpopt === "savedSettingsDisabled"))
            this.help(helpcat, helpopt, this.sspHelpExtra())()
    }
    // a plain dense setState: mergeSettings is a preset codec, not a restore primitive
    histApply = (frame) => {
        if(!frame)
            return
        let vals = JSON.parse(frame.blob), update = {}
        HIST_KEYS.forEach((k, i) => { update[k] = vals[i] })
        if(frame.tab)
            update.activeTab = frame.tab
        // players can rewind below the world the edit was made in
        update.fassWorld = Math.min(frame.world || 1, update.players || 1)
        let ssp = this.state.sspName
        this.history.suppress = true
        this.setState(update, () => {
            // the Seed tab outlives the form, and its download links keep working
            if(this.state.seedTabExists && this.seedParams)
                this.setState({seedStale: canonSettings(this.paramsJson().json) !== this.seedParams})
            if(this.state.sspName !== ssp)
                this.refreshPresetHelp()
            this.histFlash(frame.ctl)
        })
    }
    undo = () => this.histApply(this.history.undo())
    redo = () => this.histApply(this.history.redo())
    // a disabled button eats the click that would commit a focused text box
    histReady = () => !this.state.seedIsGenerating && !this.state.sspBusy
    onHistKey = (e) => {
        if(!(e.ctrlKey || e.metaKey) || e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")
            return
        let key = e.key.toLowerCase()
        if(key !== "z" && key !== "y")
            return
        e.preventDefault()
        if(this.histReady())
            (key === "y" || e.shiftKey) ? this.redo() : this.undo()
    }

    // a bare page opens on the last-generated settings; ?param_id= or ?preset= wins
    restoreLastUsed = () => {
        if(this.restored || !this.state.sspLatest)
            return
        // deciding not to restore is still a decision, and loadSspList runs again later
        this.restored = true
        // the toggle is about opening on it, not about keeping it: Last Seed stays
        // in the dropdown, and /reroll still has a seed to reroll
        if(this.state.seedTabExists || this.sharedSsp || !this.restoreLastSeed)
            return
        let latest = this.state.sspLatest, name = this.nameFor(latest, PRESET_LAST)
        // settings only, and silently: an auto-restore is not something the user just did
        this.mergeSettings(latest, presetLabel(name), false, name, undefined, true)
    }

    selectPreset = (name) => {
        let clean = this.state.sspLoaded === canonSettings(this.settingsNow(this.state.sspLoadedWorld))
        // re-picking is a no-op only for the world it was loaded into
        let sameWorld = (this.isMultiworld() ? (this.state.fassWorld || 1) : 1) === this.state.sspLoadedWorld
        if(name === this.state.sspName && clean && sameWorld)
            return
        if(name === PRESET_DEFAULT)
            this.mergeSettings(this.defaultSettings, "Default")
        else if(name === PRESET_LAST)
            doNetRequest("/preset/latest", this.history.carry(this.acceptSsp, "preset"))
        else
            this.fetchSsp(this.state.sspOwner, name)
    }

    // the pencil can edit a preset that is not the loaded one, so the modal
    // carries its own target rather than reading the selection
    openPresetManage = (name) => this.setState(prev => {
        let ssp = prev.sspList.find(s => s.name === name) || {}
        return {presetModal: true, presetArmDelete: false, sspBusy: false,
                presetEditing: name, sspSaveName: name, sspSaveDesc: ssp.desc || "",
                sspSaveHidden: !!ssp.hidden}
    })

    presetEdit = () => {
        let name = (this.state.sspSaveName || "").trim()
        if(!name)
            return NotificationManager.error("Give your preset a name", "Can't save preset!", 4000)
        let target = this.state.presetEditing
        this.setState({sspBusy: true}, () => postNetForm("/preset/edit", {preset: JSON.stringify(
            {name: target, newName: name, desc: this.state.sspSaveDesc,
             hidden: this.state.sspSaveHidden})}, ({status, responseText}) => {
                if(status !== 200) {
                    NotificationManager.error(responseText || "Failed to save preset", "Can't save preset!", 5000)
                    return this.setState({sspBusy: false})
                }
                NotificationManager.success(name, "Preset updated", 4000)
                // a rename only moves the selection if it was the one renamed
                this.setState(prev => ({sspBusy: false, presetModal: false,
                                        sspName: prev.sspName === target ? name : prev.sspName}),
                              this.loadSspList)
            }))
    }

    presetDelete = () => {
        let name = this.state.presetEditing
        this.setState({sspBusy: true}, () => postNetForm("/preset/delete", {preset: JSON.stringify({name: name})},
            ({status, responseText}) => {
                if(status !== 200) {
                    NotificationManager.error(responseText || "Failed to delete preset", "Can't delete preset!", 5000)
                    return this.setState({sspBusy: false, presetArmDelete: false})
                }
                NotificationManager.success(`"${name}" is gone`, "Preset deleted", 4000)
                // deleting the loaded preset leaves its options in the form, so
                // drift is measured against Default from here
                this.setState(prev => prev.sspName === name
                    ? {sspBusy: false, presetModal: false, sspName: PRESET_DEFAULT,
                       sspLoadedOwner: null, sspLoadedWorld: 1,
                       sspLoaded: canonSettings(this.defaultSettings)}
                    : {sspBusy: false, presetModal: false}, this.loadSspList)
            }))
    }

    // Update writes over the selection in place; Save As always asks for a name
    sspUpdate = () => {
        let existing = this.state.sspList.find(s => s.name === this.state.sspName)
        if(!existing)
            return
        // the world it was loaded into; fassWorld is a view, not what to save
        this.setState({sspBusy: true},
                      () => this.postSsp(this.state.sspLoadedWorld || 1, {name: existing.name}))
    }

    acceptSsp = ({status, responseText}, asked) => {
        if(status !== 200) {
            NotificationManager.error(responseText || "That preset could not be loaded", "Can't load preset!", 5000)
            return
        }
        let ssp = JSON.parse(responseText)
        // a borrowed preset is not in sspList, so its description and settings
        // have nowhere else to live
        this.setState({sspLoadedDesc: ssp.desc || "", sspLoadedBlob: ssp.settings || null})
        let label = (ssp.owner && ssp.owner !== this.state.sspOwner) ? `${ssp.name}, by ${ssp.owner}` : ssp.name
        this.mergeSettings(ssp.settings, label, ssp.withLobby,
                           asked || (ssp.withLobby ? PRESET_LAST : undefined), ssp.owner)
    }

    // a share link copies a preset in; it does not stay bound to the owner's
    fetchSsp = (owner, name) => doNetRequest(`/preset/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`,
        this.history.carry((res) => this.acceptSsp(res, name), "preset"))

    openSspSave = () => this.setState(prev => ({sspModal: true, sspSaveDesc: "",
        sspSaveName: nextPresetName(prev.sspList), sspSaveHidden: false}))

    sspSave = () => {
        if(!(this.state.sspSaveName || "").trim()) {
            NotificationManager.error("Give your preset a name", "Can't save preset!", 4000)
            return
        }
        // Save As snapshots the world in view; Update passes the one it loaded
        this.setState({sspBusy: true},
                      () => this.postSsp(this.isMultiworld() ? (this.state.fassWorld || 1) : 1))
    }

    // what is not sent is left alone, so Update can send the name and options only
    postSsp = (world, fields) => {
        let ssp = {...(fields || {name: (this.state.sspSaveName || "").trim(),
                                  desc: this.state.sspSaveDesc, hidden: this.state.sspSaveHidden}),
                   params: this.paramsJson().json, world: world}
        // captured now: the form stays editable, and a later edit is not saved
        let sent = canonSettings(this.settingsNow(world))
        let from = this.state.sspName
        postNetForm("/preset/save", {preset: JSON.stringify(ssp)},
                    (res) => this.sspSaveCallback(res, sent, world, from))
    }

    sspSaveCallback = ({status, responseText}, sent, world, from) => {
        if(status !== 200) {
            NotificationManager.error(responseText || "Failed to save preset", "Can't save preset!", 5000)
            this.setState({sspBusy: false})
            return
        }
        let {name} = JSON.parse(responseText)
        NotificationManager.success(`Saved as "${name}"`, "Preset saved", 4000)
        this.setState({sspBusy: false, sspModal: false}, () => {
            // claim the selection unless the user moved it while this was in flight;
            // a new preset never matches the name we started from
            if(this.state.sspName === from)
                this.markLoaded(name, this.state.sspOwner, world, sent)
            this.loadSspList()
        })
    }

    acceptMetadata = ({status, responseText}) => {
        if(status !== 200)
        {
            NotificationManager.error("Failed to recieve seed metadata", "Seed could not be retrieved!", 5000)
            this.setState({seedIsGenerating: false, seedTabExists: false, activeTab: 'variations'}, this.updateUrl)
        } else {
            let metaUpdate = JSON.parse(responseText)
            if(!metaUpdate.isPlando)
            {
                if(metaUpdate.selectedPool === "Custom")
                    metaUpdate.itemPool = Object.keys(metaUpdate.itemPool).map(i => ({item: i, count: metaUpdate.itemPool[i][0], upTo: metaUpdate.itemPool[i][1] || metaUpdate.itemPool[i][0]})).sort((a, b) => get_canon_index(a) - get_canon_index(b))
                else
                    metaUpdate.itemPool = getPool(metaUpdate.selectedPool) 
            } else {
                metaUpdate.itemPool = this.state.itemPool
            }
            metaUpdate.seedIsGenerating = false
            metaUpdate.inputPlayerCount = metaUpdate.players
            metaUpdate.inputSeed = metaUpdate.seed
            metaUpdate.seedIsBingo = metaUpdate.variations.some(v => v === "Bingo")
            metaUpdate.keyMode = keyModeFromJson(metaUpdate.keyMode)
            metaUpdate.goalModes = metaUpdate.variations.filter(v => GOAL_VARS.includes(v))
            if(metaUpdate.goalModes.length === 0)
                metaUpdate.goalModes = ["None"]
            if(metaUpdate.fass && metaUpdate.fass.length > 0) {
                metaUpdate.fassList = metaUpdate.fass.map(({loc, item, code, id, world, owner}) => (
                    {loc: locOptionFromCoords(parseInt(loc, 10)), item: item || `${code}|${id}`, world: world || 1, owner: owner || world || 1}))
                metaUpdate.fassWorld = 1
                metaUpdate.fass = undefined;
            }
            if(metaUpdate.coopGameMode === "Multiworld") {
                // multiworld share selections live in their own state slot
                metaUpdate.mwShared = metaUpdate.shared || []
                delete metaUpdate.shared
            }
            metaUpdate.playerNames = metaUpdate.playerNames || []
            // apMode/apExport rehydrate by name; empty export = server default
            if(!metaUpdate.apExport || metaUpdate.apExport.length === 0)
                metaUpdate.apExport = [...apDefaultExport]
            metaUpdate.apDeathLink = metaUpdate.apDeathLink || false
            metaUpdate.inputApMode = metaUpdate.apMode || false
            dev && console.log(metaUpdate)
            // the form now is the seed's own settings, whatever this session did before
            this.setState(metaUpdate, () => {
                this.seedParams = canonSettings(this.paramsJson().json)
                this.updateUrl()
            })
        }
    }

    updateUrl = () => {
        let {paramId, gameId, seedTabExists, seedIsGenerating} = this.state;
        
        let url = new URL(window.document.URL);
        if(!seedIsGenerating && seedTabExists)
        {
            url.searchParams.set("param_id", paramId);
            if(gameId && gameId > 0)
                url.searchParams.set("game_id", gameId);
        }
        if(url.searchParams.has("fromBingo"))
            url.searchParams.delete("fromBingo")

        window.history.replaceState('',window.document.title, url.href);
    }
    
    seedBuildCallback = ({status, responseText}) => {
        if(status !== 200)
        {
            // 409 refused before trying, 422 tried and knows why; both carry a reason
            let reason = ((status === 409 || status === 422) && responseText) ? responseText : "Failed to generate seed!"
            NotificationManager.error(reason, "Seed generation failure!", 5000)
            this.setState({seedIsGenerating: false, seedTabExists: false, activeTab: 'variations'}, this.updateUrl)
            return
        } else {
            let res = JSON.parse(responseText)
            if(res.doBingoRedirect) {
                // an AP board stays here: the host needs the apworld and the
                // yamls before anyone downloads a seed, and the seed tab keeps
                // an Open Bingo Board button either way
                if(!(this.apAvailable() && this.state.apMode)) {
                    let redir = `/bingo/board?game_id=${res.gameId}&fromGen=1&seed=${res.seed}&bingoLines=${res.bingoLines || 3}`
                    if(res.flagLine.includes("share="))
                        redir += `&teamMax=${res.playerCount}`
                    if(this.state.randomizedWith === this.state.seed)
                        redir += `&randomSettings=1`;

                    gotoUrl(redir, true)
                }
                this.helpEnter("general", "seedBuiltBingo")()
            }
            else 
                this.helpEnter("general", "seedBuilt" + this.multi())()
            this.setState({
                paramId: res.paramId, seedIsGenerating: false, inputPlayerCount: res.playerCount, inputSeed: res.seed,
                flagLine: res.flagLine, flagLines: res.flagLines || [],
                gameId: res.gameId, seedIsBingo: res.doBingoRedirect || false,
                inputApMode: this.apAvailable() && this.state.apMode
            }, this.updateUrl)
        }
    }
    getVariationsTab = () => {
        // the Starved trio is CLI-only now; Buried placements cover it
        let filteredVars = ["NonProgressMapStones", "BonusPickups", "ForceTrees", "WorldTour", "ForceMaps", "WarmthFrags",
                            "Hard", "Bingo", "StompTriggers", "StrictMapstones", "ClosedDungeons",
                            "TPStarved", "WallStarved", "GrenadeStarved"];
        let variationButtons = Object.keys(VAR_NAMES).filter(x => !filteredVars.includes(x)).map(v=> {
            let name = VAR_NAMES[v];
            return (
            <Col key={`var-button-${v}`} xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", v)} className="p-2">
                <Button data-hist={`var-${v}`} block color="primary" outline={!this.hasVar(v)} onClick={this.onVar(v)}>{name}</Button>
            </Col>
            )
        })

        return (
            <TabPane className="p-3 border" tabId="variations">
                <Row className="p-2">
                    {variationButtons}
                </Row>
            </TabPane>
        )
    }
    
    getSeedTab = () => {
        if(!this.state.seedTabExists)
            return null;
        if(this.state.seedIsGenerating)
        {
            return (
                <TabPane className="p-3 border" tabId='seed' onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "seedBuilding" + this.multi())}>
                    <Row className="p-2 justify-content-center align-items-center">
                        <Col xs="auto" className="align-items-center justify-content-center p-2">{this.state.loader}</Col>
                    </Row>
                </TabPane>
            )
        }
        else 
        {
            let {inputPlayerCount, gameId, seedIsBingo, paramId, flagLine, spoilers, inputSeed, bingoLines, auxSpoiler, inputApMode} = this.state
            let spoilerText = auxSpoiler.active ? "Item List" : "View Spoiler"
            let raw = flagLine.split('|');
            let seedStr = raw.pop();
            let flags = raw.join("").split(",");
            let flagCol = (flag, where) => (<Col key={`flag-${where}-${flag}`} xs="auto" className="text-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("flags", flag)}><span className="ml-auto mr-auto align-middle">{flag}</span></Col>)
            // when the worlds disagree, what they share moves up top and each row
            // keeps only its own differences; when they agree nothing moves
            let perWorld = (this.state.flagLines || []).map(l => l.split('|').slice(0, -1).join("").split(","))
            let mixed = perWorld.length > 1 && new Set(perWorld.map(f => f.join(","))).size > 1
            let common = mixed ? perWorld.reduce((acc, f) => acc.filter(x => f.includes(x)), perWorld[0]) : []
            let flagCols = (mixed ? common : flags.filter(seedWideFlag)).map(f => flagCol(f, "seed"))
            let worldFlagCols = flags.filter(f => !seedWideFlag(f)).map(f => flagCol(f, "world"))
            let worldFlagColsFor = (p) => mixed
                ? perWorld[p - 1].filter(f => !common.includes(f)).map(f => flagCol(f, `w${p}`))
                : worldFlagCols
            let is_race = flags.includes("Race");
            if(is_race && !get_flag("race_wl")) {
                return null;
            }
            let mapUrl = "/tracker/game/"+gameId+"/map";
            
            let playerRows = [...Array(inputPlayerCount).keys()].map(p => {
                p++;
                let seedParams = [];
                if(gameId > 0)
                    seedParams.push(`game_id=${gameId}`)
                let seedUrl = "/generator/seed/"+paramId
                if(inputPlayerCount > 1)
                    seedParams.push("player_id="+p);
                let mainButtonText = "Download Seed"
                // AP seeds bake item names at download time; the help says so
                let mainButtonHelp = (inputApMode && ap_enabled() ? "downloadButtonAp" : "downloadButton")+this.multi()
                seedUrl += "?" + seedParams.join("&")
                if(seedIsBingo) {
                    seedUrl = `/bingo/board?game_id=${gameId}&fromGen=1&seed=${inputSeed}&bingoLines=${bingoLines}`
                    if(inputPlayerCount > 1) {
                        seedUrl += `&teamMax=${inputPlayerCount}`
                    }
                    mainButtonText = `Open Bingo Board`
                    mainButtonHelp = "openBingoBoard"
                }
                let playUrl = "bfr:/play/params/"+paramId;
                playUrl += "?" + seedParams.join("&");
                let showApNotReady = inputApMode && ap_enabled() && gameId > 0 && !seedIsBingo && !this.apNamesReady();
                let showPlay = app_enabled() && !showApNotReady && !seedIsBingo;
                // 12 columns: player 3 + seed 3 (4 with Play) + this world's flags
                return (
                    <Row key={`player-${p}`} className="align-content-center p-1 border-bottom">
                        <Col xs="3" className="pt-1 border" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "playerPanel"+this.multi())}>
                            <Row className="align-content-center"><Col xs="3">
                                <Media object style={{width: "25px", height: "25px"}} src={player_icons(p,false)} alt={"Icon for player "+p} />
                            </Col><Col>
                                <span className="align-middle">Player {p}</span>
                            </Col></Row>
                        </Col>
                        <Col xs={showPlay ? 4 : 3} className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", mainButtonHelp)}>
                            {showApNotReady ? (
                                // item names bake in at download time, so hold the
                                // button until every world's scouts are stored; the
                                // status poll clears this on its own
                                <div>
                                    <Button color="secondary" block disabled>{this.state.apNoLink ? "Connect Room First" : "Waiting For Room…"}</Button>
                                    <Button color="link" size="sm" block target="_blank" href={seedUrl + "&force=1"}>download anyway (generic item names)</Button>
                                </div>
                            ) : (
                                showPlay ? (
                                    <ButtonGroup>
                                        <Button color="primary" block target="_blank" href={seedUrl}>{mainButtonText}</Button>
                                        <Button color="success" href={playUrl}>Play</Button>
                                    </ButtonGroup>
                                ) : (
                                    <Button color="primary" block target="_blank" href={seedUrl}>{mainButtonText}</Button>
                                )
                            )}
                        </Col>
                        <Col xs={showPlay ? 5 : 6} className="pl-1 pr-1 border-left d-flex align-items-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "flags")}>
                            <Row className="justify-content-start align-items-center flag-row w-100">
                                {worldFlagColsFor(p)}
                            </Row>
                        </Col>
                    </Row>
                )
            })

            // one spoiler for the whole seed, so one set of buttons for all of them
            let spoilerHelp = (button) => spoilers ? `spoiler${button + (auxSpoiler.active ? "Aux" : "")}` : "noSpoilers"
            let spoilerRow = (
                <Row className="p-1 align-items-center">
                    <Col xs="3" className="text-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", spoilerHelp("View"))}>
                        <Cent>Spoilers:</Cent>
                    </Col>
                    <Col xs={{size: 3, offset: 2}} className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", spoilerHelp("View"))}>
                        <ButtonGroup className="d-flex">
                            <Button className="w-100" color={spoilers ? "primary" : "secondary"} disabled={!spoilers} href={this.spoilerUrl(paramId, false, false, 1)} target="_blank">{spoilerText}</Button>
                            <Button color={spoilers ? "success" : "secondary"} disabled={!spoilers} onClick={() => this.setState({auxModal: true, auxPlayer: 1})}><FaCog/></Button>
                        </ButtonGroup>
                    </Col>
                    <Col xs="3" className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", spoilerHelp("Download"))}>
                        <Button color={spoilers ? "primary" : "secondary"} disabled={!spoilers} href={this.spoilerUrl(paramId, true, false, 1)} target="_blank" block>Save Spoiler</Button>
                    </Col>
                </Row>
            )
            let trackedInfo = gameId > 0 ? is_race ? (
                  <Row className="p-1 pt-3 align-items-center border-dark border-top">
                    <Col xs="4" className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "downloadButton")}>
                        <Button color="primary" block target="_blank" href={"/generator/seed/"+paramId}>Untracked</Button>
                    </Col>
                    <Col xs="4">
                        <Button color="primary" block onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "histLink")} href={"/game/"+this.state.gameId+"/history?sec="+(new URL(window.document.URL)).searchParams.get("sec")} target="_blank">View Game History</Button>
                    </Col>
                    <Col xs="4" className="text-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "gameId")}>
                        {gameId}
                    </Col>
                  </Row>
              )  : (
                  <Row className="p-1 pt-3 align-items-center border-dark border-top">
                    <Col xs="4" className="text-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "tracking")}>
                        <Cent>Game Id: {gameId}</Cent>
                    </Col>
                    <Col xs="4">
                        <Button color="primary" block onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "mapLink")} href={mapUrl} target="_blank">Open Map</Button>
                    </Col>
                    <Col xs="4">
                        <Button color="primary" block onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "histLink")} href={"/game/"+this.state.gameId+"/history"} target="_blank">View Game History</Button>
                    </Col>
                  </Row>
              ) : null
            return (
                <TabPane className="p-3 border" tabId='seed'>
                      <Row className="justify-content-center">
                        <span className="align-middle">
                            <h5>Seed {seedStr} ready!</h5>
                        </span>
                    </Row>
                    {flagCols.length > 0 ? (
                      <Row className="p-1 align-items-center border-top border-bottom">
                        <Col xs="3" className="text-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "flags")}>
                            Seed Flags:
                        </Col>
                        <Col xs="9 border-left">
                            <Row className="justify-content-start flag-row">
                            {flagCols}
                            </Row>
                        </Col>
                      </Row>
                    ) : null}
                    {playerRows}
                    {spoilerRow}
                    {trackedInfo}
                    {this.getApSetupPanel()}
                    {this.getApPanel()}
                </TabPane>
                )
        }
    }

    // --- Archipelago setup steps (seed tab) ---
    getApSetupPanel = () => {
        // steps 4-5 point at the room panel, so share its gate
        if(!this.apPanelVisible())
            return null
        let worldVersion = get_param("ap_world_version")
        let dataVersion = get_param("ap_data_version")
        let namesReady = this.apNamesReady()
        let step = (n, text, button, help) => (
            <Row key={`ap-step-${n}`} className="p-1 align-items-center border-bottom">
                <Col xs="1" className="text-center">{n}.</Col>
                <Col xs={button ? "8" : "11"}><span className="align-middle">{text}</span></Col>
                {button ? (
                <Col xs="3" className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", help)}>
                    {button}
                </Col>
                ) : null}
            </Row>
        )
        return (
            <Row className="p-1 pt-3 align-items-center border-dark border-top">
                <Col>
                    <Row className="p-1 justify-content-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "apSetup")}>
                        <Col xs="auto"><h5>Archipelago Setup</h5></Col>
                    </Row>
                    {step(1, "Install the Ori apworld: put it in your Archipelago install's custom_worlds folder, replacing any older copy.",
                        <Button color="primary" block target="_blank" href="/generator/apworld">Get apworld</Button>, "apworldDownload")}
                    {step(2, "Get this game's yamls -- one file holding every world -- and drop it in Archipelago's Players folder.",
                        <Button color="primary" block target="_blank" href={"/generator/apyamls/"+this.state.paramId}>Get YAMLs</Button>, "apYaml")}
                    {step(3, "Generate the game in Archipelago, then host the room somewhere (an archipelago.gg room always works and is recommended).")}
                    {step(4, "Enter that room's host and port below and hit Connect.")}
                    {step(5, namesReady
                        ? "Item names are ready: download and distribute Ori seeds now."
                        : "Wait for every world below to report its item names, then download the seeds. Seeds downloaded early say \"AP Item #n\" instead of the real item.")}
                    {step(6, "Ori players load their randomizer.dat files into the randomizer as usual and are ready to play.")}
                    {worldVersion ? (
                        <Row className="p-1">
                            <Col className="text-center"><small className="text-muted">apworld {worldVersion}, seed data version {dataVersion}.</small></Col>
                        </Row>
                    ) : null}
                </Col>
            </Row>
        )
    }

    // --- Archipelago room panel (seed tab, AP-mode games only) ---
    apPanelVisible = () => {
        let {seedTabExists, seedIsGenerating, activeTab, gameId, inputApMode, apHidden} = this.state
        return ap_enabled() && !apHidden && gameId > 0 && inputApMode && seedTabExists && !seedIsGenerating && activeTab === "seed"
    }

    // everything the panel renders except last_activity: it's auto_now on
    // the link row, so a redundant put would read as news
    apStatusSignature = (r) => JSON.stringify(r && [
        r.enabled, r.status, r.host, r.port, r.slots, r.recv_index,
        r.goal_worlds, r.names_total, r.names_resolved, r.deathlinks_in,
        r.last_error, r.dropped])

    apNoteActivity = (report) => {
        let sig = this.apStatusSignature(report)
        if(sig === this.apLastSignature)
            return false
        this.apLastSignature = sig
        this.apLastChangeAt = Date.now()
        return true
    }

    // 5s while anything is changing, then slower. No settled-state gate: a
    // link that never progresses (refused, never scouted) must still idle out
    apPollDelay = () => {
        if(document.hidden) return 60000
        if(this.state.apNoLink) return 30000
        if(this.state.apConnectPending) return 5000
        let idle = (Date.now() - (this.apLastChangeAt || Date.now())) / 1000
        let tier = AP_IDLE_TIERS.find(([after]) => idle >= after)
        return tier ? tier[1] * 1000 : 5000
    }

    apPollTick = () => {
        this.fetchApStatus()
        this.apSchedule()
    }

    // separate from ticking so a response can move the timer it was already
    // scheduled under (the delay is picked before the reply lands)
    apSchedule = () => {
        if(!this.apPolling) return
        if(this.apPollTimer) clearTimeout(this.apPollTimer)
        this.apPollTimer = setTimeout(this.apPollTick, this.apPollDelay())
    }

    apRefreshNow = () => {
        this.fetchApStatus()
        this.apSchedule()
    }

    startApPoll = () => {
        if(this.apPolling) return
        this.apPolling = true
        // every (re)start begins live: never inherit the previous game's tier
        this.apLastSignature = null
        this.apLastChangeAt = Date.now()
        if(!this.apVisListener) {
            this.apVisListener = () => {
                // refresh on return to a visible tab; the listener outlives
                // the panel, so check it's still polling
                if(!document.hidden && this.apPolling) this.apRefreshNow()
            }
            document.addEventListener("visibilitychange", this.apVisListener)
        }
        this.apPollTick()
    }

    stopApPoll = () => {
        this.apPolling = false
        if(this.apPollTimer) clearTimeout(this.apPollTimer)
        this.apPollTimer = null
    }

    fetchApStatus = () => {
        let {gameId} = this.state
        if(!(gameId > 0)) return
        doNetRequest(`/netcode/game/${gameId}/ap/status?time=${(new Date()).getTime()}`, (res) => this.apStatusCallback(gameId, res))
    }

    apStatusCallback = (gameId, {status, responseText}) => {
        if(gameId !== this.state.gameId) return // stale response from a previous game
        if(status === 200) {
            let report = JSON.parse(responseText)
            // snap the cadence back on the same response that carried the news
            let changed = this.apNoteActivity(report)
            let update = {apStatus: report, apNoLink: false, apPollFailed: false}
            // one-time prefill so reconnecting is a single click; an untouched
            // host box counts as empty
            if(!this.apPrefilled && report.host && this.state.apPort === ""
               && (this.state.apHost === "" || this.state.apHost === AP_DEFAULT_HOST)) {
                update.apHost = report.host
                update.apPort = String(report.port)
            }
            this.apPrefilled = true
            this.setState(update, changed ? this.apSchedule : undefined)
        } else if(status === 404) {
            if(responseText && responseText.includes("not enabled"))
                this.setState({apHidden: true}) // server-side ARCHIPELAGO flag is off
            else {
                this.apNoteActivity(null)   // a link that went away is news
                this.setState({apStatus: null, apNoLink: true, apPollFailed: false}) // no link yet; connect creates one
            }
        } else {
            this.setState({apPollFailed: true})
        }
    }

    onApConnect = () => {
        let {gameId, apHost, apPort, apPassword} = this.state
        this.setState({apConnectPending: true}, () => postNetForm(`/netcode/game/${gameId}/ap/connect`,
            {host: apHost.trim(), port: apPort.trim(), password: apPassword}, this.apConnectCallback))
    }

    apConnectCallback = ({status, responseText}) => {
        this.setState({apConnectPending: false})
        if(status === 200) {
            // a pending slow timer must not govern the post-connect cadence
            this.apRefreshNow()
            return
        }
        if(status === 404 && responseText && responseText.includes("not enabled")) {
            this.setState({apHidden: true})
            return
        }
        if(status === 409) // server says non-AP game; drop the panel
            this.setState({apHidden: true})
        NotificationManager.error(responseText || "Connection request failed", "Archipelago", 5000)
    }

    onApDisconnect = () => {
        let {gameId} = this.state
        this.setState({apConnectPending: true}, () => postNetForm(`/netcode/game/${gameId}/ap/disconnect`, {}, this.apDisconnectCallback))
    }

    apDisconnectCallback = ({status, responseText}) => {
        this.setState({apConnectPending: false})
        if(status === 200)
            this.apRefreshNow()
        else if(status === 404 && responseText && responseText.includes("not enabled"))
            this.setState({apHidden: true})
        else
            NotificationManager.error(responseText || "Disconnect request failed", "Archipelago", 5000)
    }

    // -1 = not scouted yet; a world with no AP locations reports 0 of 0
    apNamesTotal = (i) => {
        let totals = this.state.apStatus ? this.state.apStatus.names_total : null
        return totals && totals[i] !== undefined && totals[i] !== null ? totals[i] : -1
    }

    apNamesDone = (i) => (this.state.apStatus && this.state.apStatus.names_resolved ? this.state.apStatus.names_resolved[i] : 0) || 0

    apNamesReady = () => {
        let {apStatus} = this.state
        return !!apStatus && apStatus.slots.length > 0 && apStatus.slots.every((_, i) => this.apNamesTotal(i) >= 0 && this.apNamesDone(i) >= this.apNamesTotal(i))
    }

    getApPanel = () => {
        let {gameId, inputApMode, apHidden, apHost, apPort, apPassword, apConnectPending, apStatus, apNoLink, apPollFailed} = this.state
        if(!(ap_enabled() && !apHidden && gameId > 0 && inputApMode))
            return null
        let portNum = parseInt(apPort, 10)
        let portValid = portNum > 0 && portNum < 65536
        let canConnect = apHost.trim() !== "" && portValid && !apConnectPending
        let canDisconnect = !apConnectPending && !!(apStatus && apStatus.enabled)
        let statusColor = {connected: "text-success", pending: "text-warning", reconnecting: "text-warning", refused: "text-danger"}[apStatus ? apStatus.status : ""] || "text-muted"
        let lastActStr = ""
        if(apStatus && apStatus.last_activity) {
            // naive utc isoformat from the server
            let iso = /(Z|[+-]\d\d:?\d\d)$/.test(apStatus.last_activity) ? apStatus.last_activity : apStatus.last_activity + "Z"
            let d = new Date(iso)
            if(!isNaN(d.getTime()))
                lastActStr = "Last activity: " + d.toLocaleString()
        }
        let namesTotal = this.apNamesTotal, namesDone = this.apNamesDone
        let namesReady = this.apNamesReady()
        let worldRows = apStatus ? apStatus.slots.map((slot, i) => (
            <Row key={`ap-world-${i}`} className="p-1 align-items-center border-bottom">
                <Col xs="1">
                    <Media object style={{width: "25px", height: "25px"}} src={player_icons(i + 1, false)} alt={"Icon for player " + (i + 1)} />
                </Col>
                <Col xs="3">
                    <span className="align-middle">Player {i + 1} ({slot})</span>
                </Col>
                <Col xs="3">
                    <span className="align-middle">{apStatus.recv_index[i] || 0} items received</span>
                </Col>
                <Col xs="3">
                    <span className={"align-middle " + (namesTotal(i) >= 0 && namesDone(i) >= namesTotal(i) ? "text-success" : "text-muted")}>
                        {namesTotal(i) >= 0 ? `${namesDone(i)}/${namesTotal(i)} item names` : "item names pending"}
                    </span>
                </Col>
                <Col xs="2">
                    <span className="align-middle text-success">{apStatus.goal_worlds.includes(i + 1) ? "Goal complete!" : ""}</span>
                </Col>
            </Row>
        )) : null
        return (
            <Row className="p-1 pt-3 align-items-center border-dark border-top">
                <Col>
                    <Row className="p-1 justify-content-center">
                        <Col xs="auto"><h5>Archipelago Room</h5></Col>
                    </Row>
                    <Row className="p-1 align-items-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "apConnect")}>
                        <Col xs="3" className="pl-1 pr-1">
                            <Input type="text" placeholder={AP_DEFAULT_HOST} value={apHost} onChange={(e) => this.setState({apHost: e.target.value})}/>
                        </Col>
                        <Col xs="2" className="pl-1 pr-1">
                            <Input type="text" placeholder="38281" value={apPort} invalid={apPort !== "" && !portValid} onChange={(e) => this.setState({apPort: e.target.value})}/>
                        </Col>
                        <Col xs="3" className="pl-1 pr-1">
                            <Input type="password" autoComplete="off" placeholder="password (optional)" value={apPassword} onChange={(e) => this.setState({apPassword: e.target.value})}/>
                        </Col>
                        <Col xs="2" className="pl-1 pr-1">
                            <Button color="primary" block disabled={!canConnect} onClick={this.onApConnect}>Connect</Button>
                        </Col>
                        <Col xs="2" className="pl-1 pr-1">
                            <Button color="danger" outline block disabled={!canDisconnect} onClick={this.onApDisconnect}>Disconnect</Button>
                        </Col>
                    </Row>
                    {apNoLink ? (
                        <Row className="p-1">
                            <Col className="text-center text-muted">Not connected to an Archipelago room yet.</Col>
                        </Row>
                    ) : null}
                    {apStatus ? (
                        <Row className="p-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "apStatus")}>
                            <Col>
                                <Row className="p-1 align-items-center">
                                    <Col xs="4">
                                        <span className="align-middle">Status: <span className={statusColor}>{apStatus.status}</span></span>
                                    </Col>
                                    <Col xs="4">
                                        <span className="align-middle">Room: {apStatus.host}:{apStatus.port}</span>
                                    </Col>
                                    <Col xs="4" className="text-right">
                                        <small className="text-muted">{lastActStr}</small>
                                    </Col>
                                </Row>
                                {worldRows}
                                <Row className="p-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "apNames")}>
                                    <Col className={namesReady ? "text-center text-success" : "text-center text-warning"}>
                                        {namesReady
                                            ? "Item names are ready: seeds downloaded from now on show what each Archipelago location really holds."
                                            : "Seeds downloaded before the room is connected show \"AP Item #n\" placeholders. Once every world reports its item names, download the seeds again to see the real ones."}
                                    </Col>
                                </Row>
                                {apStatus.last_error ? (
                                    <Row className="p-1">
                                        <Col className="text-danger">Last error: {apStatus.last_error}</Col>
                                    </Row>
                                ) : null}
                                {(apStatus.dropped || []).length > 0 ? (
                                    <Row className="p-1">
                                        <Col className="text-center text-danger">
                                            {`Undeliverable (no free slot - console sends?): ` +
                                             apStatus.dropped.map(d => `${d.n} (P${d.w})`).join(", ")}
                                        </Col>
                                    </Row>
                                ) : null}
                            </Col>
                        </Row>
                    ) : null}
                    {apPollFailed ? (
                        <Row className="p-1">
                            <Col className="text-center text-warning">Status check failed; retrying...</Col>
                        </Row>
                    ) : null}
                </Col>
            </Row>
        )
    }

    getPathsTab = () => {
        let pathButtons = [(
        <Col xs="3" key="path-button-casual-core" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicPaths",  "casual-core")}  className="p-1">
                <Button block disabled={true} className="text-capitalize">Casual-Core</Button>
        </Col>
        )].concat(optionalPaths.map(path=> (
            <Col xs="3" key={`path-button-${path}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicPaths", path)}  className="p-1">
                <Button data-hist={`path-${path}`} block color="primary" outline={!this.state.paths.includes(path)} disabled={this.pathDisabled(path)} className="text-capitalize" onClick={this.onPath(path)}>{path}</Button>
            </Col>
        )))    
        return (
            <TabPane className="p-3 border" tabId="logic paths">
                <Row className="p-2">
                    {pathButtons}
                </Row>
            </TabPane>
        )
    }

    randomize = () => {
        let {seed} = this.state;
        seed = seed || Math.random().toString();
        const hasVar = (v) => newState.variations.includes(v);
        const rng = prng(seed);
        const newState = {randomizedWith: seed};
        const prandInt = (min, max) => Math.floor(rng() * (max - min + 1)) + min;
        const prandPop = (ls) => ls.splice(prandInt(0, ls.length - 1),1)[0]
        // inverse-CDF triangular: peak is the mode, not the mean
        const triangular = (lo, hi, peak) => {
            const u = rng(), turn = (peak - lo) / (hi - lo);
            return u < turn ? lo + Math.sqrt(u * (hi - lo) * (peak - lo))
                            : hi - Math.sqrt((1 - u) * (hi - lo) * (hi - peak));
        };

        // randomize goal modes

        // bingo 10% of the time, something else the rest
        if(rng() < .10) {
            newState.goalModes = ["Bingo"];
        } else {
            const goalModeCountRoll = rng();
            let goalModeCount = 0;
            switch(true) {
                // Goal mode count randomization! 
                // 0 modes 10% of the time; 1 mode 73% of the time; 2 modes 12% of the time;  3 modes 5% of the time 
                case (goalModeCountRoll < .1):
                    break;
                case (goalModeCountRoll < .83):
                    goalModeCount = 1;
                    break;
                case (goalModeCountRoll < .95):
                    goalModeCount = 2;
                    break;
                default:
                    goalModeCount = 3;
                    break;    
            }
            newState.goalModes = [];
            // only 35% of the time is forcemaps even an option. Because it's not good.
            let goalModeValidChoices = rng() > .35 ? ["ForceTrees", "WorldTour", "WarmthFrags"] : ["ForceTrees", "WorldTour", "WarmthFrags", "ForceMaps"];
            while(goalModeCount-- > 0) 
                newState.goalModes.push(prandPop(goalModeValidChoices));
        }
        // done with goal modes - copy them to variations
        newState.variations = [].concat(newState.goalModes);

        // randomize key modes
        const keyModeRoll = rng();
        switch(true) {
            case (keyModeRoll < .01): // 1% None
                newState.keyMode = "None";
                break;
            case (keyModeRoll < .09): // 9% Limitkeys
                newState.keyMode = "Limitkeys";
                break;
            case (keyModeRoll  < .2): // 10% Free
                newState.keyMode = "Free";
                break;
            case (keyModeRoll  < .6): // 40% Clues
                newState.keyMode = "Clues";
                break;
            default:                  // 40% Shards
                newState.keyMode = "Shards";
                break;                        
        }
        const logicPathRoll = rng(); // randomize logic path preset
        switch(true) {
            case (logicPathRoll < .01): // 1% glitched
                newState.pathMode = "glitched";
                break;
            case (logicPathRoll < .09): // 9% master
                newState.pathMode = "master";
                break;
            case (logicPathRoll  < .2): // 10% casual
                newState.pathMode = "casual";
                break;
            case (logicPathRoll  < .6): // 50% standard
                newState.pathMode = "standard";
                break;
            default:                    // 30% expert
                newState.pathMode = "expert";
                break;
        }
        newState.paths = presets[newState.pathMode];

        // Randomize variations - each is an independant roll with probability defined in VAR_WEIGHTS
        Object.keys(VAR_WEIGHTS).map(key => (rng() < VAR_WEIGHTS[key]) && newState.variations.push(key));

        // Bingo precludes 0xp
        if(hasVar("0XP") && hasVar("Bingo")) {
            newState.variations = newState.variations.filter(v => v !== "0XP");
        }

        // If a variation has banned paths, remove them (and put an asterisk on the pathMode string)
        Object.keys(disabledPaths).filter(v => hasVar(v)).forEach(badVar => {
            newState.paths = newState.paths.filter(path => !disabledPaths[badVar].includes(path));
            newState.pathMode += "*";
        });

        // Randomize item pool
        const itemPoolRoll = rng()
        switch(true) {
            // itemPoolRandomization
            case (itemPoolRoll < .04):  // hard 4%
                newState.selectedPool = "Hard";
                break;
            case (itemPoolRoll < .20):  // competitive 16%
                newState.selectedPool = "Competitive";
                break;
            case (itemPoolRoll < .60): // standard 40%
                newState.selectedPool = "Standard";
                break;
            case (itemPoolRoll < .90): // bonus lite 30%
                newState.selectedPool = "Bonus Lite";
                break;
            default: // bonus 10%
                newState.selectedPool = "Extra Bonus";
                break;
        }
        newState.itemPool = getPool(newState.selectedPool)

        // manually add warps to the pool if InLogicWarps was selected and there aren't any after randomize the item pool
        if(hasVar("InLogicWarps") && ! newState.itemPool.some(({item}) => item === "WP|*")) 
                newState.itemPool.push({item: "WP|*", count: 6, upTo: 10, maximum: 14})

        // Randomize spawn location: the two that need no kit from us. Glades has none,
        // and Random's zone is the generator's to pick, so there is nothing to look up
        // here -- making that roll interesting is the generator's job, not this button's.
        newState.spawn = rng() < .5 ? "Random" : "Glades";
        [newState.spawnHCs, newState.spawnECs, newState.spawnSKs] = [3, 1, 0];

        // advanced tab bullshit START

        if(rng() < .2) // 20% of the time, sense is instead inverted sense; you sense everything that's not a skill or event
            newState.senseData = "EX+AC+HC+EC+KS+RB+MS+TW";
        else
            newState.senseData = ""; // clear it so it doesn't stay inverted when spam clicking the button

        if(hasVar("WarmthFrags")) {
            newState.fragReq = prandInt(3, 6)*5; // between 15 and 30, increments of 5
            if(rng() < .05)  // 5% of the time, you are getting every frag
                newState.fragCount = newState.fragReq;
            else
                newState.fragCount = (newState.fragReq * (5 + prandInt(1,3))) / 5 ; // otherwise, there are 20%|40%|60% extra frags (pp up numbers)
        }

        if(hasVar("WorldTour"))
            newState.relicCount = prandInt(6,11);

        // Bury something one roll in seven. Spam-clicking must not stack burials, so a
        // previous roll's are dropped first -- hand-made preplacements are left alone.
        newState.fassList = this.state.fassList.filter(
            f => !(f.loc && f.loc.value >= BURIED_LOC_BASE && (f.world || 1) === 1));
        if(rng() < .15) {
            // triangular 60..180 peaking at 100, to the nearest ten so the row reads Buried100
            const depth = Math.round(triangular(60, 180, 100) / 10) * 10;
            const buryRoll = rng();
            let groups;
            if(buryRoll < .20)
                // the deep tier trails by 30 rather than the preset's 50: past 200 nothing
                // outside a Starved seed would ever reach it
                groups = [{depth: depth - 10, items: TELEPORTER_TIERS[0]},
                          {depth: depth + 20, items: TELEPORTER_TIERS[1]}];
            else if(buryRoll < .40)
                groups = [{depth: depth, items: WALL_SKILLS}];
            else if(buryRoll < .70)
                groups = [{depth: depth, items: [GRENADE]}];
            else if(buryRoll < .90)
                groups = [{depth: depth, items: [POWER_SKILLS[prandInt(0, POWER_SKILLS.length - 1)]]}];
            else {
                // 1-4 skills at 4:3:2:1, drawn without replacement. A lone Grenade and a
                // bare wall jump + climb are categories above, so the draw never rebuilds one.
                const countRoll = rng();
                const count = countRoll < .4 ? 1 : countRoll < .7 ? 2 : countRoll < .9 ? 3 : 4;
                let pool = ALL_SKILLS.filter(s => count > 1 || s !== GRENADE);
                let picked = [];
                while(picked.length < count) {
                    if(count === 2 && picked.length === 1 && WALL_SKILLS.includes(picked[0]))
                        pool = pool.filter(s => !WALL_SKILLS.includes(s));
                    picked.push(prandPop(pool));
                }
                groups = [{depth: depth, items: picked}];
            }
            newState.fassList = mergeBuried(newState.fassList, groups, 1);
        }

        if(hasVar("Bingo")) {
            // win by lines three times in four; there is no lockout knob on this page,
            // so a rolled squares board is never one
            newState.bingoGoal = rng() < .75 ? "bingos" : "squares";
            // 3 is the house default and keeps four rolls in ten; the rest split evenly
            newState.bingoLines = rng() < .4 ? 3 : BINGO_LINE_CHOICES[prandInt(0, BINGO_LINE_CHOICES.length - 1)];
            // triangular over 5..25 peaking at 12, so a board is usually middling and
            // occasionally a sprint or a slog. The ends get half a bin, as rounding does.
            newState.bingoSquares = Math.round(triangular(5, 25, 12));
            const bingoDiffRoll = rng();
            newState.bingoDiff = bingoDiffRoll < .8 ? "normal" : bingoDiffRoll < .95 ? "easy" : "hard";
            newState.bingoMeta = rng() < .5;
            // meta boards get discovery half as often, and reveal one more when they do
            newState.bingoDisc = 0;
            if(rng() < (newState.bingoMeta ? .2 : .4)) {
                const revealRoll = rng(), fewest = newState.bingoMeta ? 2 : 1;
                // the bottom of each range is the rare one
                newState.bingoDisc = fewest + (revealRoll < .1 ? 0 : revealRoll < .55 ? 1 : 2);
            }
        }

        const poolRoll = rng();
        if(poolRoll < .5) // 50% of the time, randomize the exp pool (between 10k and 15k)
            newState.expPool = prandInt(20, 30) * 500;
        else if(poolRoll < .01)      // 1% of the time, do 10x that (because it IS funny)
            newState.expPool *= 10;
        else if(poolRoll < .06) // 5% of the time,  remove 2000 (to allow for the occasional sad pool)
            newState.expPool -= 2000;
        else
            newState.expPool = 10000; // And also! put it back! If you aren't fucking with it!! come ON girlie....

        if(rng() < .1) // 10% of the time, set some very stupidly low FCF
            newState.cellFreq = prandInt(3, 15);
        else
            newState.cellFreq = cellFreqPresets(newState.pathMode); // put it baaack....
        
        const isMasterOrGlitched = newState.pathMode.startsWith("master") || newState.pathMode.startsWith("glitched");
        const pathDiffRoll = rng();
        switch(true) {
            case (pathDiffRoll < .05 || (pathDiffRoll < .7 && isMasterOrGlitched)):
                newState.pathDiff = "Hard";
                break;
            case (pathDiffRoll < .9):
                newState.pathDiff = "Normal"
                break;
            default:
                newState.pathDiff = "Easy";
        }
        if(isMasterOrGlitched && rng() < .7 && !hasVar("Starved"))
            newState.variations.push("Starved");

        this.setState(newState);
    }

    getModal = (modalParams) => {
        let {quickstartOpen, auxModal} = this.state
        if(quickstartOpen)
            return this.getQuickstartModal(modalParams);
        if(auxModal)
            return this.getAuxModal(modalParams);
        if(this.state.sspModal)
            return this.getSspModal(modalParams);
        if(this.state.presetModal)
            return this.getPresetManageModal(modalParams);

    }

    getPresetManageModal = ({inputStyle}) => {
        let {sspSaveName, sspSaveDesc, sspSaveHidden, sspBusy, presetArmDelete, presetEditing} = this.state
        return (
                <Modal isOpen={this.state.presetModal} className={"modal-dialog-centered"} toggle={this.closeModal}>
                  <ModalHeader style={inputStyle} toggle={this.closeModal} centered>{`Preset: ${presetEditing}`}</ModalHeader>
                  <ModalBody style={inputStyle}>
                      <Container fluid>
                        <Row className="p-1">
                            <Col xs="4" className="text-center pt-1 border"><Cent>Name</Cent></Col>
                            <Col xs="8">
                                <Input style={inputStyle} type="text" value={sspSaveName} maxLength={64}
                                       onChange={(e) => this.setState({sspSaveName: e.target.value})}/>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center pt-1 border"><Cent>Description</Cent></Col>
                            <Col xs="8">
                                <Input style={inputStyle} type="text" maxLength={200} value={sspSaveDesc}
                                       onChange={(e) => this.setState({sspSaveDesc: e.target.value})}/>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center pt-1 border"><Cent>Shareable</Cent></Col>
                            <Col xs="8">
                                <Button color="primary" block outline={sspSaveHidden}
                                        onClick={() => this.setState({sspSaveHidden: !sspSaveHidden})}>
                                    {sspSaveHidden ? "Only me" : "Anyone with the link"}
                                </Button>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center pt-1 border"><Cent>Link</Cent></Col>
                            <Col xs="8">
                                <InputGroup>
                                    <Input style={inputStyle} type="text" readOnly value={this.presetShareUrl(presetEditing)}
                                           onFocus={(e) => e.target.select()}/>
                                    <InputGroupAddon addonType="append">
                                        <Button color="info" title="Copy link"
                                                onClick={() => this.copyPresetLink(presetEditing)}><FaCopy/></Button>
                                    </InputGroupAddon>
                                </InputGroup>
                            </Col>
                        </Row>
                        <Row className="p-1 mt-2">
                            <Col>
                                <Button color="danger" block outline={!presetArmDelete} disabled={sspBusy}
                                        onClick={() => presetArmDelete ? this.presetDelete() : this.setState({presetArmDelete: true})}>
                                    {presetArmDelete ? "Click again to delete it for good" : "Delete this preset"}
                                </Button>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col><Cent><small>Deleting only removes the saved copy. Your current options stay in the form.</small></Cent></Col>
                        </Row>
                    </Container>
                  </ModalBody>
                  <ModalFooter style={inputStyle}>
                    <Button color="primary" disabled={sspBusy || !sspSaveName.trim()} onClick={this.presetEdit}>Save changes</Button>
                    <Button color="secondary" onClick={this.closeModal}>Cancel</Button>
                  </ModalFooter>
                </Modal>
        )
    }

    getSspModal = ({inputStyle}) => {
        let {sspSaveName, sspSaveDesc, sspSaveHidden, sspBusy, sspList} = this.state
        let overwrites = sspList.some(s => s.name === sspSaveName.trim())
        return (
                <Modal isOpen={this.state.sspModal} className={"modal-dialog-centered"} toggle={this.closeModal}>
                  <ModalHeader style={inputStyle} toggle={this.closeModal} centered>Save Preset</ModalHeader>
                  <ModalBody style={inputStyle}>
                      <Container fluid>
                        <Row className="p-1">
                            <Col xs="4" className="text-center pt-1 border"><Cent>Name</Cent></Col>
                            <Col xs="8">
                                <Input style={inputStyle} type="text" value={sspSaveName} maxLength={64}
                                       onChange={(e) => this.setState({sspSaveName: e.target.value})}/>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center pt-1 border"><Cent>Description</Cent></Col>
                            <Col xs="8">
                                <Input style={inputStyle} type="text" maxLength={200} value={sspSaveDesc}
                                       onChange={(e) => this.setState({sspSaveDesc: e.target.value})}/>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center pt-1 border"><Cent>Shareable</Cent></Col>
                            <Col xs="8">
                                <Button color="primary" block outline={sspSaveHidden}
                                        onClick={() => this.setState({sspSaveHidden: !sspSaveHidden})}>
                                    {sspSaveHidden ? "Only me" : "Anyone with the link"}
                                </Button>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col><Cent><small>The multiplayer tab isn't saved: load a preset into any lobby.</small></Cent></Col>
                        </Row>
                    </Container>
                  </ModalBody>
                  <ModalFooter style={inputStyle}>
                    <Button color="primary" disabled={sspBusy || !sspSaveName.trim()} onClick={this.sspSave}>{overwrites ? "Overwrite" : "Save"}</Button>
                    <Button color="secondary" onClick={this.closeModal}>Cancel</Button>
                  </ModalFooter>
                </Modal>
        )
    }
    getQuickstartModal = ({inputStyle}) => {
        return (
                <Modal size="lg" isOpen={this.state.quickstartOpen} backdrop={"static"} className={"modal-dialog-centered"} toggle={this.closeModal}>
                  <ModalHeader style={inputStyle} toggle={this.closeModal} centered>Welcome to the Ori DE Randomizer!</ModalHeader>
                  <ModalBody style={inputStyle}>
                      <Container fluid>
                      <Row className="p-1">
                        <span>
                        Welcome to the Ori DE Randomizer! Check out the links below to get started.
                        </span>
                      </Row>
                      <Row>
                          <ol>
                          <li>
                              Join the Ori <a target='_blank' rel='noopener noreferrer' href="/discord">discord</a>. 
                              The community is one of the best resources for getting help with learning the randomizer.
                          </li>
                          <li>
                              Install the Ori Randomizer by copying this <a target='_blank' rel='noopener noreferrer' href="/dll">dll</a> into
                              your Ori DE/oriDE_Data/Managed folder. (Detailed installation instructions are available <a href="/faq?g=install">here</a>)
                          </li>
                          <li>
                              (Optional) Get the Rando Item Tracker <a target='_blank' rel='noopener noreferrer' href="/tracker">here</a>.  (Detailed installation instructions are available <a target='_blank' href="/faq?g=get_tracker">here</a>)
                          </li>
                          <li>
                              Get a seed! Download one of our <a href="/faq?g=starter_seeds">starter seeds</a> or roll your own using the <a href="/">generator</a>. Check out the <a href="/faq?g=gen_seed">generator instructions</a> to learn how to create and install a seed.
                          </li>
                          <li>
                              Start playing! Maybe take a quick glance at the <a href="/faq?g=differences">changes</a> unique to the Ori Randomizer, and check out the <a href="/faq?g=gotchas">list of gotchas</a>.
                          </li>
                          </ol>
                      </Row>
                    </Container>
                  </ModalBody>
                  <ModalFooter style={inputStyle}>
                    <Button color="secondary" onClick={this.closeModal}>Close</Button>
                  </ModalFooter>
                </Modal>
        )
    }

    onSpoilerSettings = (newSettings) => this.setState({auxSpoiler: Object.assign(this.state.auxSpoiler, newSettings)})
    onSpoilerItemType = (itemType) => this.setState(prevState => {
        let newAux = prevState.auxSpoiler;
        if(newAux.exclude.includes(itemType))
            newAux.exclude = newAux.exclude.filter(t => t !== itemType)
        else
            newAux.exclude.push(itemType)
            
        return {auxSpoiler: newAux}
    })

    getAuxModal = ({inputStyle}) => {
        let {auxModal, auxSpoiler} = this.state
        let itemTypes = ["AC", "EC", "HC", "KS", "MS", "EX"].map(iType => (<Col>
            <Button key={`asif-${iType}`} outline={!auxSpoiler.exclude.includes(iType)} onClick={() => this.onSpoilerItemType(iType)}>{iType}</Button>
        </Col>))
        return (
                <Modal isOpen={auxModal} backdrop={"static"} className={"modal-dialog-centered"} toggle={this.closeModal}>
                  <ModalHeader style={inputStyle} toggle={this.closeModal} centered>Spoiler Settings</ModalHeader>
                  <ModalBody style={inputStyle}>
                      <Container fluid>
                      <Row>
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Spoiler Type</Cent>
                            </Col>
                            <Col xs="6">
                                <UncontrolledButtonDropdown nav inNavbar>
                                    <DropdownToggle color="primary" nav caret>
                                    {auxSpoiler.active ? "Item List" : "Logic Spoiler"}
                                    </DropdownToggle>
                                    <DropdownMenu right>
                                        <DropdownItem active={!auxSpoiler.active} onClick={() => this.onSpoilerSettings({active: false})}>
                                            Logic Spoiler
                                        </DropdownItem>
                                        <DropdownItem active={auxSpoiler.active} onClick={() => this.onSpoilerSettings({active: true})}>
                                            Item List
                                        </DropdownItem>
                                    </DropdownMenu>
                                </UncontrolledButtonDropdown>
                            </Col>
                        </Row>
                        <Collapse isOpen={auxSpoiler.active}>
                        <Row>
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Sort By</Cent>
                            </Col>
                            <Col xs="6">
                                <UncontrolledButtonDropdown nav inNavbar>
                                    <DropdownToggle color="primary" nav caret>
                                    {auxSpoiler.byZone ? "Zone" : "Item Type"}
                                    </DropdownToggle>
                                    <DropdownMenu right>
                                        <DropdownItem active={!auxSpoiler.byZone} onClick={() => this.onSpoilerSettings({byZone: false})}>
                                            Item Type
                                        </DropdownItem>
                                        <DropdownItem active={auxSpoiler.byZone} onClick={() => this.onSpoilerSettings({byZone: true})}>
                                            Zone
                                        </DropdownItem>
                                    </DropdownMenu>
                                </UncontrolledButtonDropdown>
                            </Col>
                        </Row>
                        <Row>
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Exclude</Cent>
                            </Col>
                            <Col xs="6">
                                <Row> {itemTypes} </Row>
                            </Col>
                        </Row>
                        </Collapse>
                    </Container>
                  </ModalBody>
                  <ModalFooter style={inputStyle}>
                    <Button color="secondary" onClick={this.closeModal}>Close</Button>
                  </ModalFooter>
                </Modal>
        )
    }

    constructor(props) {
        super(props);
        let user = get_param("user");
        let url = new URL(window.document.location.href);
        let paramId = url.searchParams.get("param_id");
        if(get_flag("race_wl")) VAR_NAMES["Race"] = "Race"
        let quickstartOpen = window.document.location.href.includes("/quickstart");
        let gameId = parseInt(url.searchParams.get("game_id") || -1, 10);
        let seedTabExists = (paramId !== null);
        if(seedTabExists)
        {
            if(gameId > 0)
                doNetRequest(`/generator/metadata/${paramId}/${gameId}`,this.acceptMetadata);
            else
                doNetRequest(`/generator/metadata/${paramId}`,this.acceptMetadata);

        } else {

        }

        let activeTab = seedTabExists ? 'seed' : 'variations';

        this.state = {user: user, activeTab: activeTab, coopGenMode: "Cloned Seeds", coopGameMode: "Multiworld", players: 1, antiBkBias: 0, dropActive: false,
                        tracking: true, variations: ["ForceTrees"], gameId: gameId, itemPool: getPool("Standard"), dedupShared: false, 
                        paths: presets["standard"], keyMode: "Clues", oldKeyMode: "Clues", spawn: "Glades", 
                        spawnHCs: 3, spawnECs: 1, spawnSKs: 0, pathMode: "standard", pathDiff: "Normal", helpParams: getHelpContent("none", null), 
                        goalModes: ["ForceTrees"], selectedPool: "Standard", seed: "", fillAlg: "Balanced", quickstartOpen: quickstartOpen, 
                        shared: ["Skills", "Teleporters", "World Events", "Upgrades", "Misc"], mwShared: [], helpcat: "", helpopt: "",
                        apMode: false, apExport: [...apDefaultExport], apDeathLink: false, inputApMode: false, playerNames: [],
                        worldSettings: [],
                        apHost: AP_DEFAULT_HOST, apPort: "", apPassword: "", apConnectPending: false, apStatus: null, apNoLink: false, apHidden: false, apPollFailed: false,
                        histAt: -1, histLen: 0, seedStale: false,
                        expPool: 10000, lastHelp: new Date(), seedIsGenerating: seedTabExists, cellFreq: cellFreqPresets("standard"),
                        fragCount: 30, fragReq: 20, relicCount: 8, loader: get_random_loader(), paramId: paramId, seedTabExists: seedTabExists, 
                        reopenUrl: "", flagLine: "", flagLines: [], fassList: fassDefaultsFor(1), fassWorld: 1, goalModesOpen: false, 
                        spoilers: true, spawnWeights: [1.0,2.0,2.0,2.0,1.5,2.0,0.1,0.1,0.25,0.5], seedIsBingo: false, bingoLines: 3,
                        bingoDiff: "normal", bingoGoal: "bingos", bingoSquares: 13, bingoMeta: false, bingoDisc: 0, 
                        auxModal: false, auxPlayer: 1, auxSpoiler: {active: false, byZone: false, exclude: ["EX","KS", "AC", "EC", "HC", "MS"]},
                        verboseSpoiler: get_param("verbose") === "True",
                        sspList: [], sspOwner: null, sspName: PRESET_DEFAULT, sspHasLatest: false,
                        sspLoaded: null, sspLoadedOwner: null, sspLoadedWorld: 1, presetEditing: "",
                        sspLatest: null, sspLoadedDesc: "", sspLoadedBlob: null,
                        sspModal: false, presetModal: false, presetArmDelete: false, sspBusy: false,
                        sspSaveName: "", sspSaveDesc: "", sspSaveHidden: false};
        
        // the untouched form IS the Default entry; its arrays are the live state arrays, not copies
        this.defaultSettings = this.settingsNow()
        this.defaultForm = {}
        PRESET_FORM_KEYS.forEach(k => { this.defaultForm[k] = this.state[k] })
        this.state.sspLoaded = canonSettings(this.defaultSettings)

        if(url.searchParams.has("fromBingo")) {
            this.state.goalModes = ["Bingo"]
            this.state.variations = ["Bingo", "OpenWorld"]
            this.state.itemPool = getPool("Bonus Lite")
            this.state.selectedPool = "Bonus Lite"
            this.updateUrl()
        }
        this.history = new History(() => this.state)
        this.history.onChange = () => this.setState({histAt: this.history.index, histLen: this.history.stack.length})
        this.apPollTimer = null
        this.apPrefilled = false
        // until /preset/list says otherwise, opening on the last seed is the behaviour
        this.restoreLastSeed = true
        // ?preset=owner:name -- a share link, which needs no login to open
        let shared = (url.searchParams.get("preset") || "").split(":")
        this.sharedSsp = shared.length === 2 && shared[0] && shared[1] ? shared : null
    }

    // React never calls component.setState itself, so shadowing it here sees every
    // write without touching the ~117 call sites, 30 of which are inline in render.
    setState(update, cb) {
        if(!update || typeof update === "function" || Object.keys(update).some(k => HIST_SET.has(k)))
            this.history.touch()
        return super.setState(update, cb)
    }

    componentDidMount() {
        this.history.attach()
        // the form as loaded is frame 0, whether or not anything restores over it:
        // without this the first edit of a page that restored nothing is frame 0
        // itself, and undo has nowhere to go back to
        this.history.touch()
        document.addEventListener("keydown", this.onHistKey)
        if(this.apPanelVisible())
            this.startApPoll()
        this.loadSspList()
        if(this.sharedSsp)
            this.fetchSsp(this.sharedSsp[0], this.sharedSsp[1])
    }

    componentDidUpdate(prevProps, prevState) {
        // a path banned by an active variation can't stay selected
        let paths = this.state.paths.filter(p => !this.pathDisabled(p))
        if(paths.length !== this.state.paths.length)
            this.setState({paths: paths, pathMode: get_preset(paths)})
        if(prevState.gameId !== this.state.gameId) {
            // new game: any polled link state belongs to the old one
            this.apPrefilled = false
            this.stopApPoll() // re-armed below with an immediate fetch
            this.setState({apStatus: null, apNoLink: false, apHidden: false, apPollFailed: false})
        }
        if(this.apPanelVisible())
            this.startApPoll()
        else
            this.stopApPoll()
    }

    componentWillUnmount() {
        document.removeEventListener("keydown", this.onHistKey)
        this.history.detach()
        this.stopApPoll()
    }
        
    closeModal = () => {
         window.history.replaceState('',window.document.title, window.document.URL.split("/quickstart")[0]);
         this.setState({quickstartOpen: false, auxModal: false, sspModal: false, presetModal: false})
    }

    onTab = (tabName) => () => this.setState({activeTab: tabName})
    onFassList = (index, update) => this.setState(prevState => {
        let fassList = [...prevState.fassList];
        Object.assign(fassList[index], update);
        return {fassList: fassList};
    });
    addToFassList = ({loc, item}) => this.setState(prevState => {
        let fassList = [...prevState.fassList];
        let world = this.isMultiworld() ? prevState.fassWorld : 1;
        let newLoc = loc;
        if(!newLoc) {
            const usedCoords = new Set(fassList.filter(fass => (fass.world || 1) === world).map(fass => fass.loc.value));
            newLoc = locOptions.find(loc => !usedCoords.has(loc.value));
            if(!newLoc) return {};
        }
        fassList.push({loc: newLoc, item: item, world: world, owner: world});
        this.refs.fassTabula.clear();
        return {fassList: fassList};
    });
    buryItems = (groups) => () => this.setState(prevState => ({
        fassList: mergeBuried(prevState.fassList, groups, this.isMultiworld() ? prevState.fassWorld : 1)
    }));
    onFassWorld = (w) => this.setState(prevState => {
        let update = {fassWorld: w};
        // first visit to a world's tab: offer the usual suggestion rows
        if(!prevState.fassList.some(f => (f.world || 1) === w))
            update.fassList = prevState.fassList.concat(fassDefaultsFor(w));
        return update;
    });
    hasVar = (v) => this.state.variations.includes(v);
    isMultiworld = () => this.state.tracking && this.state.players > 1 && this.state.coopGameMode === "Multiworld";
    // any solo mode can join an AP room; Race/Co-op with other Ori players
    // can't. Turning AP on turns tracking on.
    apAvailable = () => ap_enabled() && (this.isMultiworld() || this.state.players === 1);
    onPath = (p) => () => this.setState({paths: this.state.paths.includes(p) ? this.state.paths.filter(x => x !== p) : this.state.paths.concat(p)}, () => this.setState(p => {return {pathMode: get_preset(p.paths)}}))
    onSType = (s) => () => this.state.shared.includes(s) ? this.setState({shared: this.state.shared.filter(x => x !== s)}) : this.setState({shared: this.state.shared.concat(s)})
    // a category can't be both mw-shared and ap-exported; the newest click wins
    onMWSType = (s) => () => this.setState(prev => prev.mwShared.includes(s)
        ? {mwShared: prev.mwShared.filter(x => x !== s)}
        : {mwShared: prev.mwShared.concat(s), apExport: prev.apMode ? prev.apExport.filter(c => apShareNames[c] !== s) : prev.apExport})
    onApMode = () => this.setState(prev => prev.apMode ? {apMode: false}
        : {apMode: true, tracking: true,  // the bridge delivers over netcode
           mwShared: prev.mwShared.filter(s => !prev.apExport.map(c => apShareNames[c]).includes(s))})
    // bingo hands names out by lobby, except on an AP board where pid is the world
    // a world's rulebook is frozen into the seed at roll time, so we store the
    // preset's settings rather than its name -- editing it later changes nothing
    assignWorld = (world, blob, label, desc) => this.setState(prev => {
        let worlds = [...prev.worldSettings]
        while(worlds.length < prev.players)
            worlds.push({})
        worlds[world - 1] = blob ? {...blob} : {}
        return {worldSettings: worlds,
                worldPresets: {...(prev.worldPresets || {}), [world]: {label: label || "", desc: desc || "",
                                                                      text: undefined, bad: false}}}
    })

    setWorldPreset = (world, name) => {
        let hit = this.state.sspList.find(s => s.name === name)
        this.assignWorld(world, hit && hit.blob, hit ? hit.name : "", hit && hit.desc)
    }

    // the link a player hands the host; opening it copies the preset in
    presetShareUrl = (name) => `${window.location.origin}/?preset=${encodeURIComponent(this.state.sspOwner || "")}:${encodeURIComponent(name || "")}`

    copyPresetLink = (name) => {
        let url = this.presetShareUrl(name)
        let done = () => NotificationManager.success(url, "Link copied", 4000)
        if(navigator.clipboard)
            navigator.clipboard.writeText(url).then(done, () => NotificationManager.error(url, "Copy it by hand", 6000))
        else
            NotificationManager.info(url, "Copy this link", 8000)
    }

    // Default is the untouched form and Last Seed is what you played; neither is
    // a saved row, but both have settings worth describing
    blobFor = (name, fallback) => name === PRESET_DEFAULT ? this.defaultSettings
                                : name === PRESET_LAST ? this.state.sspLatest
                                : fallback

    // a borrowed preset is not in sspList, so its description lives on the form
    sspHelpExtra = () => {
        let {sspName, sspList, sspOwner, sspLoadedOwner, sspLoadedDesc, sspLoadedBlob} = this.state
        let borrowed = !!sspLoadedOwner && sspLoadedOwner !== sspOwner
        let entry = sspList.find(s => s.name === sspName) || {}
        return {preset: {name: presetLabel(sspName) + (borrowed ? ` (${sspLoadedOwner})` : ""),
                         desc: borrowed ? sspLoadedDesc : entry.desc,
                         flags: minimalFlagline(this.blobFor(sspName, borrowed ? sspLoadedBlob : entry.blob))}}
    }

    worldPreset = (world) => (this.state.worldPresets || {})[world] || {}

    // what the box shows: the resolved preset, unless the user is mid-edit
    worldPresetValue = (world) => {
        let info = this.worldPreset(world)
        return info.text !== undefined ? info.text : (info.label || "")
    }

    // the box keeps what was typed until focus leaves
    onWorldPresetText = (world, text) => this.setState(prev => ({
        worldPresets: {...(prev.worldPresets || {}), [world]: {...(prev.worldPresets || {})[world], text: text, bad: false}}
    }))

    // an unusable link assigns nothing, so the red box and the seed agree
    failWorldPreset = (world) => this.setState(prev => {
        let worlds = [...prev.worldSettings]
        if(worlds.length >= world)
            worlds[world - 1] = {}
        return {worldSettings: worlds,
                worldPresets: {...(prev.worldPresets || {}), [world]: {...(prev.worldPresets || {})[world], label: "", bad: true}}}
    })

    // a pasted link is fetched once and copied in, exactly like opening one
    resolveWorldPreset = (world) => {
        let info = this.worldPreset(world)
        if(info.text === undefined)
            return
        // named, not inferred: a blur is caused by whatever the user clicked next
        let tag = (fn) => this.history.carry(fn, `worldPreset-${world}`)
        let text = info.text.trim()
        if(!text)
            return tag(() => this.assignWorld(world, null, ""))()
        let link = parsePresetLink(text)
        if(!link)
            return tag(() => this.failWorldPreset(world))()
        let [owner, name] = link
        doNetRequest(`/preset/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`, tag(({status, responseText}) => {
            if(status !== 200)
                return this.failWorldPreset(world)
            let ssp = JSON.parse(responseText)
            let mine = ssp.owner === this.state.sspOwner
            this.assignWorld(world, ssp.settings, mine ? ssp.name : `${ssp.name} (${ssp.owner})`, ssp.desc)
        }))
    }

    playerNamesShown = () => (this.apAvailable() && this.state.apMode) || this.state.players > 1
    onPlayerName = (i) => (e) => {
        // read before setState: the synthetic event is recycled by the time
        // the updater runs
        let name = e.target.value.slice(0, PLAYER_NAME_MAX)
        this.setState(prev => {
            let names = [...prev.playerNames]
            while(names.length <= i) names.push("")
            names[i] = name
            return {playerNames: names}
        })
    }
    onApExport = (cat) => () => this.setState(prev => prev.apExport.includes(cat)
        ? {apExport: prev.apExport.filter(x => x !== cat)}
        : {apExport: prev.apExport.concat(cat), mwShared: prev.mwShared.filter(s => s !== apShareNames[cat])})
    onVar = (v) => () => {
        if(this.hasVar(v)) {
            this.setState({variations: this.state.variations.filter(x => x !== v)})
        } else {
            if(v === "Race")
                this.setState({variations: ["Race", "WorldTour"], players: 4, coopGameMode: "Race", keyMode: "Shards", goalModes: ["WorldTour"]})
            else {
                if(v === "InLogicWarps" && !this.state.itemPool.some(({item}) => item === "WP|*")) this.setState(prev => {
                    return {itemPool: prev.itemPool.concat({item: "WP|*", count: 4, upTo: 8, maximum: 14}),
                            variations: prev.variations.concat(v), selectedPool: "Custom"}
                });
                else this.setState({variations: this.state.variations.concat(v)});
            }
        }
    }
    pathDisabled = (path) => revDisabledPaths.hasOwnProperty(path) && revDisabledPaths[path].some(v => this.hasVar(v))
    onKeyMode = (mode) => () => this.setState({keyMode: mode})

    onSpawnLoc = (loc) => () => this.setState(prev => {
        if(loc === "Random" || spawnFassSet(prev.fassList, prev.fassWorld)) // on your own, nerds!
            return {spawn: loc}
 
        let [hp, energy, skills] = spawnKitFor(loc, prev.pathMode)
        return {spawn: loc, spawnHCs: hp, spawnECs: energy, spawnSKs: skills}
    });
    
    onGoalModeAdvanced = (mode) => () => {
        let goalModes = this.state.goalModes.filter(v => v !== "None");
        if(goalModes.includes(mode))
        {
            if(goalModes.length === 1)
            {
                this.setState({goalModes: ["None"], variations: this.state.variations.filter(v => v !== mode)})                
            } else {
                this.setState({goalModes: goalModes.filter(v => v !== mode), variations: this.state.variations.filter(v => v !== mode)})
            }
        }
        else
        {
            this.setState({goalModes: goalModes.concat(mode), variations: this.state.variations.concat(mode)})
        }
    }


    onGoalMode = (mode) => () => {
        let oldMode = this.state.goalModes[0];
        if(oldMode === mode)
            return;
        let vars = this.state.variations;
        if(vars.includes(oldMode))
            vars = vars.filter(v => v !== oldMode);
        else
            dev && console.log("vars did not include previous goalMode?");
        if(mode !== "None" && !vars.includes(mode))
            vars = vars.concat(mode)
        else
            dev && console.log("vars already included goalMode?")
        this.setState({goalModes: [mode], variations: vars})
    }
    multi = () => this.state.players > 1 ? "Multi" : ""
    onMode = (mode) => () => {
        let vars = this.state.variations
        // If a variation is in the list due to current pathmode, remove it.
        if(varPaths.hasOwnProperty(this.state.pathMode))
            vars = vars.filter(v => !varPaths[this.state.pathMode].includes(v))
        // Then add any variations tied to the new pathmode.
        if(varPaths.hasOwnProperty(mode))
            vars = vars.concat(varPaths[mode].filter(v => !vars.includes(v)))
        let pd = this.state.pathDiff
        if(diffPaths.hasOwnProperty(this.state.pathMode))
            pd = "Normal"
        if(diffPaths.hasOwnProperty(mode))
            pd = diffPaths[mode]
        this.setState({variations: vars,cellFreq: cellFreqPresets(mode), pathMode: mode, paths: presets[mode], pathDiff: pd})
    }

    render = () => {
        let {randomizedWith, spawn, pathMode, goalModes, keyMode, helpParams, goalModesOpen, seedTabExists, seedStale, helpcat, activeTab, seed, tracking, seedIsGenerating, user} = this.state;
        const canRandomize = seed !== randomizedWith;
        const canUndo = this.history.canUndo() && this.histReady()
        const canRedo = this.history.canRedo() && this.histReady()
        const randomizeButton = canRandomize ?
        (<Button className="w-100" color="danger" onClick={this.randomize}>Randomize!</Button>) :
        (<Button className="w-100" disabled block>Randomize</Button>);
        let s = getComputedStyle(document.body);
        let styles = {inputStyle: {'borderColor': s.getPropertyValue('--dark'), 'backgroundColor': s.getPropertyValue("background-color"), 'color': s.getPropertyValue("color")}, menuStyle: {}}

        let pathModeOptions = Object.keys(presets).map(mode => (
            <DropdownItem key={`pathmode-${mode}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicModes", mode)} className="text-capitalize" active={mode===pathMode.toLowerCase()} onClick={this.onMode(mode)}>{mode}</DropdownItem>
        ))
        let spawnOptions = SPAWN_OPTS.map(loc => (
            <DropdownItem key={`spawn-${loc}`} active={loc===spawn} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "spawnLoc")} onClick={this.onSpawnLoc(loc)}>{loc}</DropdownItem>
        ))

        // picking an entry loads it; every other preset action is in here too
        const {sspList, sspName, sspLoaded, sspOwner} = this.state
        const sspBorrowed = !!this.state.sspLoadedOwner && this.state.sspLoadedOwner !== sspOwner
        const sspMine = !sspBorrowed && sspList.some(s => s.name === sspName)
        const sspEditable = !!user && sspMine
        // a preset can be deleted while the form still holds it; that is not a borrow
        const sspGone = !!user && !sspBorrowed && !sspMine
                        && sspName !== PRESET_DEFAULT && sspName !== PRESET_LAST
        const sspEdited = !!sspLoaded && sspLoaded !== canonSettings(this.settingsNow(this.state.sspLoadedWorld))
        // Default is the untouched form, so there is nothing to copy out of it
        const isDefault = canonSettings(this.settingsNow(this.state.sspLoadedWorld)) === canonSettings(this.defaultSettings)

        const presetItem = (name) => (
            <DropdownItem key={`ssp-${name}`} active={sspName === name} title={minimalFlagline(this.blobFor(name))}
                          onClick={() => this.selectPreset(name)}>
                {presetLabel(name)}
            </DropdownItem>)
        // nothing to say, no tooltip: undefined drops the attribute, "" would not
        const savedItem = (s) => (
            <DropdownItem key={`ssp-${s.name}`} active={sspName === s.name} title={presetHoverText(s.desc, s.blob)}
                          className="d-flex align-items-center" onClick={() => this.selectPreset(s.name)}>
                <span className="flex-grow-1 text-truncate">{s.name}{s.hidden ? " (private)" : ""}</span>
                <span className="pl-3" title={`Edit ${s.name}`}
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); this.openPresetManage(s.name) }}><FaPencilAlt/></span>
            </DropdownItem>)
        // an entry that would load nothing new is not worth offering
        const latestIsDefault = !!this.state.sspLatest && this.denseOf(this.state.sspLatest) === this.denseOf({})
        const sspOptions = [presetItem(PRESET_DEFAULT)]
            .concat(this.state.sspHasLatest && !latestIsDefault ? [presetItem(PRESET_LAST)] : [])
            .concat(sspList.length ? [<DropdownItem key="ssp-div1" divider/>] : [])
            .concat(sspList.map(savedItem))
            .concat(user ? [<DropdownItem key="ssp-div2" divider/>,
                            <DropdownItem key="ssp-new" onClick={this.openSspSave}>Create new&hellip;</DropdownItem>] : [])

        const sspHelp = this.helpEnter("general", user ? "savedSettings" : "savedSettingsDisabled", 250,
                                       this.sspHelpExtra())

        // one chip: save over what is loaded, or keep a copy of what cannot be
        const presetChip = sspEditable
            ? {icon: <FaSave/>, ok: sspEdited, act: this.sspUpdate, help: "updatePreset"}
            : {icon: <FaCopy/>, ok: !!user && !isDefault, act: this.openSspSave, help: "copyPreset"}

        let keyModeOptions = keymode_options.map(mode => (
            <DropdownItem key={`keymode-${mode}`} active={mode===keyMode} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("keyModes", mode)} onClick={this.onKeyMode(mode)}>{mode}</DropdownItem>
        ))
        let validGoalModes = ["None", "ForceTrees", "WorldTour", "ForceMaps", "WarmthFrags", "Bingo"];
        let goalModeOptions = goalModes.length <= 1 ? validGoalModes.map(mode => (
            <DropdownItem key={`goalmode-${mode}`} active={mode===goalModes[0]} disabled={mode==="Bingo" && !tracking} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("goalModes", mode)} onClick={this.onGoalMode(mode)}>{VAR_NAMES[mode] || mode}{mode==="Bingo" && !tracking ? '(Needs tracking!)' : ''}</DropdownItem>
        )) : [];

        helpParams.padding = goalModesOpen ? "pt-5 mt-3" : ""
        let lockTracking = goalModes.includes("Bingo") || this.state.players > 1
        let multiplayerTab = this.getMultiplayerTab(styles)
        let advancedTab = this.getAdvancedTab(styles)
        let poolTab = this.getItemPoolTab(styles)
        let seedTab = this.getSeedTab()
        let variationsTab = this.getVariationsTab()
        let pathsTab = this.getPathsTab()
        let seedNav = seedTabExists ? (
            <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", seedStale ? "seedTabStale" : "seedTab")}>
                <NavLink className={seedStale ? "text-warning" : undefined} active={activeTab === 'seed'} onClick={this.onTab('seed')}>
                    Seed
                </NavLink>
            </NavItem>
        ) : null;
        let modal = this.getModal(styles);
        let goalModeMulti = goalModes.length > 1;
        let presetPoolOptions = ["Standard", "Competitive", "Extra Bonus", "Bonus Lite", "Hard"].map(preset => (
            <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", preset)} key={`pd-${preset}`} active={this.state.selectedPool===preset} onClick={()=> this.setState({selectedPool: preset, itemPool: getPool(preset)})}>{preset}</DropdownItem>
        ))

        return (
         <Container className="pl-2 pr-2 pb-4 pt-2 mt-5">
             <Row className="justify-content-center">
                 <Col>
                     {modal}
                    <NotificationContainer/>
                    <SiteBar/>
                </Col>
            </Row>
            <Row className="pt-1">
                <Cent><h3>Seed Generator {VERSION}</h3></Cent>
            </Row>
            <Row className="pb-1">
                <Cent><a target="blank" href={`/patchnotes#${NOTES_ANCHOR}`}>(changelog)</a></Cent>
            </Row>
            <Row className="p-3 border">
                <Col xs="4" data-hist="logicMode" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "logicModes")}>
                    <Row>
                        <Col xs="5"  className="text-center border">
                            <Cent>Logic Mode</Cent>
                        </Col>
                        <Col xs="7" onMouseLeave={this.helpEnter("general", "logicModes")} onMouseEnter={this.helpEnter("logicModes", pathMode)}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" className="text-capitalize" caret block> {pathMode} </DropdownToggle>
                                <DropdownMenu style={styles.menuStyle}> {pathModeOptions} </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4" data-hist="keyMode" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "keyModes")}>
                    <Row>
                        <Col xs="5"  className="text-center border">
                            <Cent>Key Mode</Cent>
                        </Col>
                        <Col xs="7" onMouseEnter={this.helpEnter("keyModes", keyMode)} onMouseLeave={this.helpEnter("general", "keyModes",(keyMode === "Clues" && helpcat === "keyModes") ? 1000 : 250 )}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" caret block> {keyMode} </DropdownToggle>
                                <DropdownMenu style={styles.menuStyle}>
                                    {keyModeOptions}
                                </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4" data-hist="goalMode" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "goalModes")}>
                    <Row>
                        <Col xs="5"  className="text-center border">
                            <Cent>Goal Mode</Cent>
                        </Col>
                        <Col xs="7" onMouseLeave={this.helpEnter("general", "goalModes")} onMouseEnter={this.helpEnter("goalModes", goalModeMulti ? "Multiple" : goalModes[0])}>
                            <Dropdown disabled={goalModeMulti} isOpen={goalModesOpen} toggle={() => this.setState({goalModesOpen: !goalModesOpen})} className="w-100">
                                <DropdownToggle disabled={goalModeMulti} color={goalModeMulti ? "disabled" :"primary"} className="text-capitalize" caret={!goalModeMulti} block> 
                                  {goalModeMulti ? ((goalModes || []).map(gm => gm.split('').filter(c => c === c.toUpperCase()).join('')).join("+")) : (goalModes.length > 0 ? (VAR_NAMES[goalModes[0]] || goalModes[0]) : "None")}
                                </DropdownToggle>
                                <DropdownMenu style={{zIndex: 10000, ...styles.menuStyle}}>
                                    {goalModeOptions}
                                </DropdownMenu>
                            </Dropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4" data-hist="itemPoolPreset">
                    <Row>
                        <Col xs="5"  className="text-center border mt-2" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "itemPoolPreset")}>
                            <Cent>Item Pool</Cent>
                        </Col>
                        <Col xs="7" className="mt-2" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", this.state.selectedPool)}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" caret block> {this.state.selectedPool} </DropdownToggle>
                                <DropdownMenu> {presetPoolOptions} </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4" data-hist="spawn" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "spawnLoc")}>
                    <Row>
                        <Col xs="5"  className="text-center border mt-2">
                            <Cent>Spawn</Cent>
                        </Col>
                        <Col xs="7" className="mt-2" onMouseLeave={this.helpEnter("general", "spawnLoc")} onMouseEnter={this.helpEnter("general", "spawnLoc")}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" className="text-capitalize" caret block> {spawn} </DropdownToggle>
                                <DropdownMenu style={styles.menuStyle}> {spawnOptions} </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4" data-hist="preset" className="mt-2">
                <Row>
                    <Col xs="3"  className="text-center border" onMouseLeave={this.helpLeave} onMouseEnter={sspHelp}>
                        <Cent>Preset</Cent>
                    </Col>
                    <Col xs="9" className="d-flex">
                        <UncontrolledButtonDropdown className="flex-grow-1" style={{minWidth: 0}}
                                                    onMouseLeave={this.helpLeave} onMouseEnter={sspHelp}>
                            <DropdownToggle color="info" caret block className="d-flex align-items-center">
                                <span className={`text-truncate flex-grow-1 text-center${sspEdited ? " font-italic" : ""}`}>
                                    {sspEditable || sspGone ? null : <FaLock className="mr-1" style={{verticalAlign: "-.1em"}}/>}
                                    {presetLabel(sspName)}{sspBorrowed ? ` (${this.state.sspLoadedOwner})` : ""}{sspGone ? " (unsaved)" : ""}
                                </span>
                            </DropdownToggle>
                            <DropdownMenu style={{zIndex: 10000, ...styles.menuStyle}}> {sspOptions} </DropdownMenu>
                        </UncontrolledButtonDropdown>
                        <div className="pl-1" onMouseLeave={this.helpLeave}
                             onMouseEnter={this.helpEnter("general", presetChip.ok ? presetChip.help : `${presetChip.help}Disabled`)}>
                            <Button color="info" outline={!presetChip.ok} disabled={!presetChip.ok}
                                    style={presetChip.ok ? undefined : {pointerEvents: "none"}}
                                    onClick={presetChip.act}>{presetChip.icon}</Button>
                        </div>
                    </Col>
                    </Row>
                </Col>
            </Row>
            <Row className="justify-content-center p-2">
            <Col>
                <Nav tabs>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "variations")}>
                        <NavLink style={{cursor: "pointer"}} active={activeTab === 'variations'} onClick={this.onTab('variations')}>
                        Variations
                        </NavLink>
                    </NavItem>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "logicPaths")}>
                        <NavLink style={{cursor: "pointer"}} active={activeTab === 'logic paths'} onClick={this.onTab('logic paths')}>
                        Logic Paths
                        </NavLink>
                    </NavItem>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "customPool")}>
                        <NavLink style={{cursor: "pointer"}} active={activeTab === 'item pool'} onClick={this.onTab('item pool')}>
                        Customize Items
                        </NavLink>
                    </NavItem>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "multiplayer")}>
                        <NavLink style={{cursor: "pointer"}} active={activeTab === 'multiplayer'} onClick={this.onTab('multiplayer')}>
                        Multiplayer Options
                        </NavLink>
                    </NavItem>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "advanced")}>
                        <NavLink style={{cursor: "pointer"}} active={activeTab === 'advanced'} onClick={() => { dev && console.log(this.state); this.onTab('advanced')()}}>
                        Advanced
                        </NavLink>
                    </NavItem>
                    {seedNav}
                </Nav>
            </Col>
            </Row>
            <Row className="justify-content-start p-2">
                <Col xs="8">
                    <Row>
                        <Col>
                            <TabContent activeTab={activeTab}>
                                {variationsTab}
                                {pathsTab}
                                {poolTab}
                                {multiplayerTab}
                                {advancedTab}
                                {seedTab}
                            </TabContent>
                        </Col>
                    </Row>
                    <Collapse isOpen={activeTab !== "seed"}>
                        <Row className="align-items-center">
                            <Col xs="6">
                                <Row className="m-1" data-hist="seed" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "seed")}>
                                    <Col xs="5" className="text-center border">
                                        <Cent>Seed</Cent>
                                    </Col><Col xs="7">
                                        <Input style={styles.inputStyle} type="text" value={seed} onChange={(e) => this.setState({seed: e.target.value})}/>
                                    </Col>
                                </Row>
                                <Row className="m-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "webTracking" + (lockTracking ? "-locked" : ""))}>
                                    <Col>
                                        <Button color="info" data-hist="webTracking" block outline={!tracking} disabled={lockTracking} onClick={()=>this.setState({tracking: !tracking})}>Web Tracking {tracking ? "Enabled" : "Disabled"}</Button>
                                    </Col>
                                </Row>
                            </Col>
                            <Col>
                                <Row className="m-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", canRandomize ? "randomize" : "randomizeDisabled")}>
                                    <Col xs="6" data-hist="randomize">
                                        {randomizeButton}
                                    </Col>
                                    <Col xs="6" onMouseEnter={this.helpEnter("general", "undoRedo")}
                                         onMouseLeave={this.helpEnter("general", canRandomize ? "randomize" : "randomizeDisabled")}>
                                        <div className="d-flex" role="group">
                                            <Button color="secondary" className="w-100 mr-1" title="Undo" outline={!canUndo} onClick={this.undo}><FaUndo/></Button>
                                            <Button color="secondary" className="w-100" title="Redo" outline={!canRedo} onClick={this.redo}><FaRedo/></Button>
                                        </div>
                                    </Col>
                                </Row>
                                <Row className="m-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "generate" + this.multi())}>
                                    <Col>
                                        <Button color="success" disabled={seedIsGenerating} size="lg" onClick={this.generateSeed} block>Generate Seed</Button>
                                    </Col>
                                </Row>
                            </Col>
                        </Row>
                    </Collapse>
                </Col>
                <Col>
                    <Row className="sticky-top" style={{top: "1rem"}}>
                        <HelpBox style={styles.menuStyle} {...helpParams} />
                    </Row>
                </Col>
            </Row>
            </Container>
        )

    }
};

function postGenJson(url, json, callback)  {
    let xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = () => {
        if (xmlHttp.readyState === 4) {
            callback(xmlHttp);
        }
    };
    xmlHttp.open("POST", url, true);
    xmlHttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    xmlHttp.send(encodeURI(`params=${JSON.stringify(json)}`));
}
