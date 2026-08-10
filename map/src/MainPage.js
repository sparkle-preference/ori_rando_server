import React from 'react';
import  {DropdownToggle, DropdownMenu, Dropdown, DropdownItem, Nav, NavLink, NavItem, Collapse,  Input, UncontrolledButtonDropdown, Button, 
        Row, FormFeedback, Col, Container, TabContent, TabPane, Modal, ModalHeader, ModalBody, ModalFooter, Media, ButtonGroup} from 'reactstrap';
import { FaCog } from 'react-icons/fa';
import {NotificationContainer, NotificationManager} from 'react-notifications';

import 'react-notifications/lib/notifications.css';
import './index.css';

import {getHelpContent, HelpBox} from "./helpbox.js";
import {get_param, spawn_defaults, get_flag, ap_enabled, presets, select_theme, name_from_str, get_preset, player_icons, doNetRequest, get_random_loader, PickupSelect, Cent, dev, randInt, gotoUrl, prng} from './common.js';
import SiteBar from "./SiteBar.js";
import Select from 'react-select';
import Dropzone from 'react-dropzone';
import {picks_by_zone} from './shared_map';


const zonesInOrder = ['Glades', 'Blackroot', 'Grove', 'Grotto', 'Ginso', 'Swamp', 'Valley', 'Misty', 'Forlorn', 'Sorrow', 'Horu'];
const locOptions = [{'label': 'Spawn With', 'value': 2}];
zonesInOrder.forEach(zone =>  picks_by_zone[zone].forEach(p => locOptions.push({'label': `${p.area} ${p.name} (${zone})`, 'value': p.loc})));
picks_by_zone['Mapstone'].forEach(p => locOptions.push({'label': p.name, 'value': p.loc}));
// Buried pseudo-locations: seedgen keeps these items out of the pool until N
// locations are reachable (loc key = BURIED_LOC_BASE + N)
const BURIED_LOC_BASE = 20000000;
[50, 100, 150, 200].forEach(depth => locOptions.push(
    {'label': `Buried${String(depth).padStart(3, "0")} (held back until ${depth} locations are reachable)`, 'value': BURIED_LOC_BASE + depth}));
const locOptionFromCoords = (coords) => locOptions.find(l => l.value === coords);
// multipickup <-> part codes ("SK|3"), for merging burials into an existing row
const pickupToParts = (item) => {
    if(!item || item === "NO|1") return [];
    if(!item.startsWith("MU|")) return [item];
    let segs = item.substring(3).split("/");
    let parts = [];
    while(segs.length > 1) parts.push(`${segs.shift()}|${segs.shift()}`);
    return parts;
}
const partsToPickup = (parts) => parts.length === 0 ? "NO|1" : (parts.length === 1 ? parts[0] : "MU|" + parts.map(p => p.replace(/\|/g, "/")).join("/"));
const fassDefaultsFor = (world) => [2, 919772, -1560272, 799776, -120208].map(coords => ({loc: locOptionFromCoords(coords), item: "NO|1", world: world, owner: world}));
const apDefaultExport = ["skills", "teleporters", "events"];
const PLAYER_NAME_MAX = 20;  // matches ap_models.PLAYER_NAME_MAX
const AP_DEFAULT_HOST = "archipelago.gg";
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
const SPAWN_TPS = ["Glades", "Grove", "Swamp", "Grotto", "Forlorn", "Valley", "Horu", "Ginso", "Sorrow", "Blackroot"]
const STUPID_KEYS = {
    "blame": "vulajin",
    "gdi": "eiko",
    "dont": "pingme"
}

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
const cellFreqPresets = (preset) => preset === "casual" ? 20 : (preset === "standard" ? 40 : 256)
const optionalPaths = ['casual-dboost', 'standard-core', 'standard-dboost', 'standard-lure', 'standard-abilities', 'expert-core', 'expert-dboost', 'expert-lure', 'expert-abilities', 'dbash', 'master-core', 'master-dboost', 'master-lure', 'master-abilities', 'gjump', 'glitched', 'timed-level', 'insane']
const varPaths = {"master": ["Starved"]}
const diffPaths = {"glitched": "Hard", "master": "Hard"}
const disabledPaths = {
                    "0XP": ["glitched", "standard-abilities", "expert-abilities", "master-abilities", "master-dboost", "timed-level", "insane"], 
                    "OHKO": ["casual-dboost", "standard-dboost", "expert-dboost", "master-dboost", "glitched", "master-lure"]
                    }
const revDisabledPaths = {}
Object.keys(disabledPaths).forEach(v => disabledPaths[v].forEach(path => revDisabledPaths.hasOwnProperty(path) ? revDisabledPaths[path].push(v) : revDisabledPaths[path] = [v]))


export default class MainPage extends React.Component {
    helpEnter = (category, option, timeout=250) => () => {clearTimeout(this.state.helpTimeout) ; this.setState({helpTimeout: setTimeout(this.help(category, option), timeout)})}
    helpLeave = () => clearTimeout(this.state.helpTimeout) 
    help = (category, option) => () => this.setState({helpcat: category, helpopt: option, helpParams: getHelpContent(category, option)})
    

    updateItemCount = (index, newVal, {minimum}) => this.setState(prev => {
        minimum = minimum || 0
        let x = Math.max(newVal, minimum)
        prev.itemPool[index].count = x
        return {itemPool: [...prev.itemPool], selectedPool: "Custom"}
    })
    updateItemUpTo = (index, newVal) => this.setState(prev => {
        prev.itemPool[index].upTo = newVal
        return {itemPool: [...prev.itemPool], selectedPool: "Custom"}
 })
    updatePoolItem = (index, code) => this.setState(prev => {
        prev.itemPool[index].item = code
        return {itemPool: [...prev.itemPool], selectedPool: "Custom"}
    })
    deletePoolItem = (index) => () => this.setState(prev => {
        prev.itemPool.splice(index, 1)
        return {itemPool: [...prev.itemPool], selectedPool: "Custom"}
  })
    addPoolItem = (code) => this.setState(prev => {
        prev.itemPool.push({item: code, count: 1})
        this.refs.tabula.clear()
        return {itemPool: [...prev.itemPool], selectedPool: "Custom"}
    }
)

    onDragEnter = () => this.setState({dropzoneActive: true});

    onDragLeave = () => this.setState({dropzoneActive: false});

onDrop = (files) => {
        let file = files.pop();
        if(file) {
            let reader = new FileReader();
            reader.onload = () => {
                let text = reader.result;
                window.URL.revokeObjectURL(file.preview);
                // do whatever you want with the file content
                dev && console.log(text.split("\n"));
                uploadReaderLines(text.split("\n"))
            };
            reader.onabort = () => console.log('file reading was aborted');
            reader.onerror = () => console.log('file reading has failed');
    
            reader.readAsText(file);            
        } else {
            this.setState({dropzoneActive: false})
        }
    }


    getStupidTab = () => {
        let {customLogic, stupidWarn, stupidMode} = this.state;
        if(!stupidMode)
            return null;
        return (
        <TabPane className="p-3 border" tabId="stupid">
        <Dropzone className="wrapper" disableClick onDrop={this.onDrop} onDragEnter={this.onDragEnter} onDragLeave={this.onDragLeave} >
            <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("stupid", "seedDrop")} className="p-1 justify-content-center border">
                <Col xs="12"><Cent>Drag an areas.ori file here to update your custom logic</Cent></Col>
            </Row>
            <Row className="p-1 justify-content-center">  
                <Col xs="12" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("stupid", "warn")} className="p-2">
                    <Cent>{stupidWarn}</Cent>
                 </Col>
            </Row>
            <Row className="p-1 justify-content-center">
                <Col xs="12" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("stupid", "toggle")} className="p-2">
                    <Button color="primary" block outline={!customLogic} onClick={() => this.setState({customLogic: !customLogic})}>{customLogic ? "Disable" : "Enable"} Custom Logic</Button>
                </Col>
            </Row>
        </Dropzone>
        </TabPane>
        )
 
    }
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
        <TabPane className="p-3 border" tabId="item pool">
            {itemSelectors}
            <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "customPool")} className="p-1 justify-content-center">
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
            // AP item lists resolve their real names from the game's room
            if(this.state.inputApMode && ap_enabled() && this.state.gameId > 0)
                url.searchParams.set('game_id', this.state.gameId)
        } else
            url = new URL(`/generator/spoiler/${paramId}`, window.document.URL);
        if(download)
            url.searchParams.set("download", 1);
        if(multi)
            url.searchParams.set("player_id", p);
        return url.href
    }

    getAdvancedTab = ({inputStyle, menuStyle}) => {
        let {senseData, fillAlg, spawnSKs, spawnECs, spawnHCs, expPool, bingoLines, pathDiff, cellFreq, 
            relicCount, fragCount, fragReq, spawnWeights, spawn, verboseSpoiler, fassList} = this.state
        let [leftCol, rightCol] = [4, 7]
        let weightSelectors = spawnWeights.map((weight, index) => (
            <Col xs="4" key={`weight-selector-${index}`} className="text-center pt-1 border">
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
                    </Col><Col xs={rightCol-1}>
                        <PickupSelect value={item} updater={(code, _) => this.onFassList(i, {item: code})} allowGroup/>
                    </Col>
                    {isMW ? ownerDropdown(i, loc, world || 1, owner) : null}
            </Row>
        )).filter(r => r);
        if(isMW) fass_rows.unshift((
            <Row key={`fass-world-tabs`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "preplacement")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
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
                    <Col xs={leftCol+1}>
                    <Select theme={select_theme} className="align-middle" options={locOptions.filter(l => !fassUsed.has(l.value))} value={{label: 'Add new Placement:', value: -1}} onChange={(newLoc) => this.addToFassList({loc: newLoc, item: "NO|1"})}></Select>
                    </Col><Col xs={rightCol-1}>
                        <PickupSelect ref="fassTabula" value={"NO|1"} updater={(code, _) => this.addToFassList({item: code})} allowGroup/>
                    </Col>
            </Row>
        ))
        let goalCol = (v) => (
            <Col xs="6" onMouseLeave={this.helpEnter("advanced", "goalModes")} onMouseEnter={this.helpEnter("goalModes", v)} className="p-2">
                <Button color="primary" block outline={!this.hasVar(v)} onClick={this.onGoalModeAdvanced(v)}>{VAR_NAMES[v]}</Button>
            </Col>
        )
        let legacyVars = ["StompTriggers", "StrictMapstones", "ClosedDungeons"].map(v=> {
            let name = VAR_NAMES[v];
            return (
            <Col key={`var-button-${v}`} xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", v)} className="p-2">
                <Button block color="primary" outline={!this.hasVar(v)} onClick={this.onVar(v)}>{name}</Button>
            </Col>
            )});
        return (
            <TabPane className="p-3 border" tabId="advanced">
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "goalModes")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
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
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "expPool")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Exp Pool</span>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="number" value={expPool} invalid={expPool < 100} onChange={(e) => this.setState({expPool: parseInt(e.target.value, 10)})}/> 
                        <FormFeedback tooltip="true">Experience Pool must be at least 100</FormFeedback>
                    </Col>
                </Row>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "sense")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Sense Triggers</span>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="text" value={senseData || ""} onChange={(e) => this.setState({senseData: e.target.value})}/> 
                    </Col>
                </Row>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "verbose")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Verbose Spoiler</span>
                    </Col><Col xs={rightCol}>
                        <Button color="primary" block outline={!verboseSpoiler} onClick={() => this.setState({verboseSpoiler: !verboseSpoiler})}>{verboseSpoiler ? "Enabled" : "Disabled"}</Button>
                    </Col>
                </Row>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fillAlg")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Fill Algorithm</span>
                    </Col><Col xs={rightCol}>
                        <UncontrolledButtonDropdown className="w-100">
                            <DropdownToggle color="primary" caret block> {fillAlg} </DropdownToggle>
                            <DropdownMenu style={menuStyle}>
                                <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fillAlgClassic")}  active={"Classic" ===fillAlg} onClick={()=> this.setState({fillAlg: "Classic"})}>Classic</DropdownItem>
                                <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fillAlgBalanced")} active={"Balanced"===fillAlg} onClick={()=> this.setState({fillAlg: "Balanced"})}>Balanced</DropdownItem>
                            </DropdownMenu>
                        </UncontrolledButtonDropdown>
                    </Col>
                </Row>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "pathDiff")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Path Difficulty</span>
                    </Col>
                    <Col xs={rightCol}>
                        <UncontrolledButtonDropdown className="w-100">
                            <DropdownToggle color="primary" caret block> {pathDiff} </DropdownToggle>
                            <DropdownMenu style={menuStyle}> {pathDiffOptions} </DropdownMenu>
                        </UncontrolledButtonDropdown>
                    </Col>
                </Row>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "cellFreq")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Forced Cell Frequency</span>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="number" value={cellFreq} invalid={cellFreq < 3} onChange={(e) => this.setState({cellFreq: parseInt(e.target.value, 10)})}/> 
                        <FormFeedback tooltip="true">Forced Cell Frequency must be at least 3</FormFeedback>
                    </Col>
                </Row>
                {fass_rows}
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "buriedPresets")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <Cent>Bury Items ([Item]Starved)</Cent>
                    </Col><Col xs="2">
                        <Button color="primary" block outline onClick={this.buryItems([{depth: 50, items: ["SK|3", "SK|12"]}])}>Walls</Button>
                    </Col><Col xs="2">
                        <Button color="primary" block outline onClick={this.buryItems([{depth: 50, items: ["SK|51"]}])}>Grenade</Button>
                    </Col><Col xs="3">
                        <Button color="primary" block outline onClick={this.buryItems([{depth: 50, items: ["TP|Grove", "TP|Swamp", "TP|Grotto", "TP|Valley"]},
                                                                                      {depth: 100, items: ["TP|Forlorn", "TP|Sorrow", "TP|Ginso", "TP|Horu"]}])}>Teleporters</Button>
                    </Col>
                </Row>
                <Collapse isOpen={this.hasVar("Bingo")}>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "bingoLines")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Bingo Lines</span>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="number" value={bingoLines} invalid={bingoLines > 12 || bingoLines < 1} onChange={(e) => this.setState({bingoLines: parseInt(e.target.value, 10)})}/> 
                        <FormFeedback tooltip="true">Line count must be between 1 and 12</FormFeedback>
                    </Col>
                </Row>
                </Collapse>
                <Collapse isOpen={this.hasVar("WorldTour")}>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "relicCount")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span className="align-middle">Relic Count</span>
                        </Col><Col xs={rightCol}>
                            <Input style={inputStyle} type="number" value={relicCount} invalid={relicCount > 11 || relicCount < 1} onChange={(e) => this.setState({relicCount: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip="true">Relic count must be greater than 0 and less than 12</FormFeedback>
                        </Col>
                    </Row>
                </Collapse>
                <Collapse isOpen={this.hasVar("WarmthFrags")}>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fragCount")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span className="align-middle">Fragment Count</span>
                        </Col><Col xs={rightCol}>
                            <Input style={inputStyle} type="number" value={fragCount} invalid={fragCount > 60 || fragCount < 1} onChange={(e) => this.setState({fragCount: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip="true">Frag Count must be between 1 and 60</FormFeedback>
                        </Col>
                    </Row>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fragRequired")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span className="align-middle">Fragments Required</span>
                        </Col><Col xs={rightCol}>
                            <Input style={inputStyle} type="number" value={fragReq} invalid={fragCount < fragReq || fragReq <= 0} onChange={e => this.setState({fragReq: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip="true">Fragments Required must be between 0 and Fragment Count ({fragCount})</FormFeedback>
                        </Col>
                    </Row>
                </Collapse>
                <Collapse isOpen={spawn !== "Random" && spawn !== "Glades"}>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "spawnSkills")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Randomized Starting Skills</span>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="text" value={spawnSKs} invalid={spawnSKs < 0 || spawnSKs > 10 } onChange={(e) => this.setState({spawnSKs: parseInt(e.target.value,10)})}/> 
                        <FormFeedback tooltip="true">Can't spawn with less than 0 or more than 10 skills</FormFeedback>
                    </Col>
                </Row>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "spawnHCs")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Starting Health</span>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="text" value={spawnHCs} invalid={spawnHCs < 3} onChange={(e) => this.setState({spawnHCs: parseInt(e.target.value,10)})}/> 
                        <FormFeedback tooltip="true">Can't spawn with fewer than 3 Health</FormFeedback>
                    </Col>
                </Row>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "spawnECs")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Starting Energy</span>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="text" value={spawnECs} invalid={spawnHCs < 1} onChange={(e) => this.setState({spawnECs: parseInt(e.target.value,10)})}/> 
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
                    <Col onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "legacyFlags")} xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Legacy Flags</span>
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
        let shareButtons = (stypes, current, toggle) => stypes.map(stype => (
            <Col xs="4" key={`share-${stype}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("Shared Item Categories", stype)} className="p-2">
                <Button block outline={!current.includes(stype)} onClick={toggle(stype)}>Share {stype}</Button>
            </Col>
        ))
        let multiplayerButtons = shareButtons(["Skills", "Teleporters", "Upgrades", "World Events", "Misc"], shared, this.onSType)
        // multiworld selections are stored separately (default none; shared
        // singletons are a spicier choice there), and no Misc: trees/relics/
        // keysanity keys stay per-world
        let mwShareButtons = shareButtons(["Skills", "Teleporters", "Upgrades", "World Events"], mwShared, this.onMWSType)
        let apFlag = ap_enabled()
        // ap export categories are server-side names; 'stones' covers
        // Mapstones, keysanity zone keys, and generic Keystones (tiered doors)
        let apExportButtons = [["skills", "Skills"], ["teleporters", "Teleporters"], ["events", "World Events"], ["cells", "Cells"], ["stones", "Stones"], ["upgrades", "Upgrades"]].map(([cat, label]) => (
            <Col xs="4" key={`ap-export-${cat}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("AP Export Categories", cat)} className="p-2">
                <Button block outline={!apExport.includes(cat)} onClick={this.onApExport(cat)}>Export {label}</Button>
            </Col>
        ))

        let playerNameRows = !this.playerNamesShown() ? null : [...Array(players).keys()].map(i => (
            <Row key={`player-name-${i}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "playerNames")} className="p-1 justify-content-center">
                <Col xs="4" className="text-center pt-1 border">
                    <span className="align-middle">{`Player ${i+1} Name`}</span>
                </Col><Col xs="4">
                    <Input style={inputStyle} type="text" maxLength={PLAYER_NAME_MAX} placeholder={`Player ${i+1}`}
                           value={this.state.playerNames[i] || ""} onChange={this.onPlayerName(i)}/>
                </Col>
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
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "playerCount")}  className="p-1 justify-content-center">
                    <Col xs="4" className="text-center pt-1 border">
                        <span className="align-middle">Players</span>
                    </Col><Col xs="4">
                        <Input style={inputStyle} type="number" value={players} disabled={!tracking} invalid={!playerNumValid} onChange={(e) => this.setState({players: parseInt(e.target.value, 10)})}/> 
                        {playerNumFeedback }
                    </Col>
                </Row>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "multiGameType")} className="p-1 justify-content-center">
                    <Col xs="4" className="text-center pt-1 border">
                        <span className="align-middle">Multiplayer Game Type</span>
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
                            <Button block outline={!dedupShared} active={dedupShared} disabled={coopGenMode!=="Cloned Seeds"} onClick={() => this.setState({dedupShared: !dedupShared})}>Dedup Shared</Button>
                        </Col>
                    </Row>
                </Collapse>
                <Collapse isOpen={this.isMultiworld()}>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "antiBkBias")} className="p-1 justify-content-center">
                        <Col xs="4" className="text-center pt-1 border">
                            <span className="align-middle">Multiworld Balance Bias</span>
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
                            <Button block outline={!apMode} active={apMode} onClick={this.onApMode}>Archipelago</Button>
                        </Col>
                    </Row>
                    <Collapse isOpen={apMode}>
                        <Row className="p-2">
                            {apExportButtons}
                        </Row>
                        <Row className="p-2">
                            <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "apDeathLink")} className="p-2">
                                <Button block outline={!apDeathLink} active={apDeathLink} onClick={() => this.setState({apDeathLink: !apDeathLink})}>Death Link</Button>
                            </Col>
                        </Row>
                    </Collapse>
                </Collapse>
                {playerNameRows}
            </TabPane>
        )
    }


    generateSeed = () => {
        let pMap = {"Race": "None", "None": "Default", "Co-op": "Shared", "World Events": "WorldEvents", "Cloned Seeds": "cloned", "Seperate Seeds": "disjoint"}
        let url = "/generator/build"
        if(this.apAvailable() && this.state.apMode && this.state.apExport.length === 0) {
            NotificationManager.error("Select at least one Archipelago export category", "Cannot generate seed!", 5000)
            this.setState({activeTab: 'multiplayer'})
            return
        }
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
        }
        if(this.state.spawn !== "Glades") {
            json.spawn = this.state.spawn;
            if(this.state.spawn !== "Random") {
                if(this.state.startingSkills !== 0) 
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
            json.dedupShared = this.state.dedupShared
            if(this.isMultiworld())
                json.antiBkBias = this.state.antiBkBias || 0
            if(this.state.coopGameMode === "Co-op")
                json.syncShared = this.state.shared.map(s => f(s))
            if(this.isMultiworld())
                json.syncShared = this.state.mwShared.map(s => f(s))
            if(!this.state.dedupShared)
                json.teams={1: [...Array(this.state.players).keys()].map(x=>x+1)}
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
        this.setState({seedIsGenerating: true, seedTabExists: true, loader: get_random_loader(), activeTab: "seed"}, () => postGenJson(url, json, this.seedBuildCallback))
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
            metaUpdate.goalModes = metaUpdate.variations.filter(v => ["ForceTrees", "WorldTour", "ForceMaps", "WarmthFrags", "Bingo"].includes(v))
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
            this.setState(metaUpdate, this.updateUrl)
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
            // 409s carry a human-readable reason (removed modes, multiworld flag off)
            let reason = (status === 409 && responseText) ? responseText : "Failed to generate seed!"
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
                flagLine: res.flagLine, gameId: res.gameId, seedIsBingo: res.doBingoRedirect || false,
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
                <Button block color="primary" outline={!this.hasVar(v)} onClick={this.onVar(v)}>{name}</Button>
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
            let flagCols = flags.map(flag => (<Col key={`flag-${flag}`} xs="auto" className="text-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("flags", flag)}><span className="ml-auto mr-auto align-middle">{flag}</span></Col>))
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
                let isMulti = inputPlayerCount > 1
                let spoilerUrl = this.spoilerUrl(paramId, false, isMulti, p)
                let downloadSpoilerUrl = this.spoilerUrl(paramId, true, isMulti, p)
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
                let spoilerHelp = (button) => this.state.spoilers ? `spoiler${button + (auxSpoiler.active ? "Aux" : "")}` : "noSpoilers"
                // 12 columns: player 3 + seed 3 + view 3 + save 3
                return (
                    <Row key={`player-${p}`} className="align-content-center p-1 border-bottom">
                        <Col xs="3" className="pt-1 border" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "playerPanel"+this.multi())}>
                            <Row className="align-content-center"><Col xs="3">
                                <Media object style={{width: "25px", height: "25px"}} src={player_icons(p,false)} alt={"Icon for player "+p} />
                            </Col><Col>
                                <span className="align-middle">Player {p}</span>
                            </Col></Row>
                        </Col>
                        <Col xs="3" className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", mainButtonHelp)}>
                            <Button color="primary" block target="_blank" href={seedUrl}>{mainButtonText}</Button>
                        </Col>
                        <Col xs="3" className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", spoilerHelp("View"))}>
                            <ButtonGroup>
                                <Button color={spoilers ? "primary" : "secondary"} disabled={!spoilers} href={spoilerUrl} target="_blank" block >{spoilerText}</Button>
                                <Button color={spoilers ? "success" : "secondary"} disabled={!spoilers} onClick={() => this.setState({auxModal: true, auxPlayer: p})} target="_blank"><FaCog/></Button>
                            </ButtonGroup>
                        </Col>
                        <Col xs="3" className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab",spoilerHelp("Download"))}>
                            <Button color={spoilers ? "primary" : "secondary"} disabled={!spoilers} href={downloadSpoilerUrl} target="_blank" block >Save Spoiler</Button>
                        </Col>
                    </Row>
                )
            })
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
                    <Col xs="3" className="text-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "tracking")}>
                        Game Id:
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
                    <Row className="p-1 align-items-center border-top border-bottom">
                        <Col xs="3" className="text-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "flags")}>
                            Flags:
                        </Col>
                        <Col xs="9 border-left">
                            <Row className="justify-content-start flag-row">
                            {flagCols}
                            </Row>
                        </Col>
                      </Row>
                    {playerRows}
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

    startApPoll = () => {
        if(this.apPollTimer) return
        this.fetchApStatus()
        this.apPollTimer = setInterval(this.fetchApStatus, 5000)
    }

    stopApPoll = () => {
        if(!this.apPollTimer) return
        clearInterval(this.apPollTimer)
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
            let update = {apStatus: report, apNoLink: false, apPollFailed: false}
            // one-time prefill so reconnecting is a single click; an untouched
            // host box counts as empty
            if(!this.apPrefilled && report.host && this.state.apPort === ""
               && (this.state.apHost === "" || this.state.apHost === AP_DEFAULT_HOST)) {
                update.apHost = report.host
                update.apPort = String(report.port)
            }
            this.apPrefilled = true
            this.setState(update)
        } else if(status === 404) {
            if(responseText && responseText.includes("not enabled"))
                this.setState({apHidden: true}) // server-side ARCHIPELAGO flag is off
            else
                this.setState({apStatus: null, apNoLink: true, apPollFailed: false}) // no link yet; connect creates one
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
            this.fetchApStatus()
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
            this.fetchApStatus()
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
                <Button block color="primary" outline={!this.state.paths.includes(path)} disabled={this.pathDisabled(path)} className="text-capitalize" onClick={this.onPath(path)}>{path}</Button>
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

        // Randomize spawn location
        const spawnRoll = rng()
        switch(true) {
            case (spawnRoll < .4):  // Random 40%
                newState.spawn = "Random";
                break;
            case (spawnRoll < .8):  // Glades 40%
                newState.spawn = "Glades";
                break;
            case (spawnRoll < .85): // Blackroot 5%
                newState.spawn = "Blackroot";
                break;
            case (spawnRoll < .9):  // Ginso 5%
                newState.spawn = "Ginso";
                break;
            case (spawnRoll < .95): // Forlorn 5%
                newState.spawn = "Forlorn";
                break;
            default:                // Horu 5%
                newState.spawn = "Horu";
                break;
        }
        if(newState.spawn !== "Random") {
            [newState.spawnHCs, newState.spawnECs, newState.spawnSkills] = [3, 1, 0]; // defaults
            if(spawn_defaults[newState.spawn].hasOwnProperty(newState.pathMode)) 
                [newState.spawnHCs, newState.spawnECs, newState.spawnSkills] = spawn_defaults[newState.spawn][newState.pathMode];    
        }

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
        let stupidWarn = get_param("error_msg");
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
        let stupidMode = false;
        url.searchParams.forEach((v, k) => {
            if(STUPID_KEYS.hasOwnProperty(k.toLowerCase()) && v.toLowerCase() === STUPID_KEYS[k.toLowerCase()])
            stupidMode = true;          
        })

        let activeTab = seedTabExists ? 'seed' : 'variations';

        this.state = {user: user, activeTab: activeTab, coopGenMode: "Cloned Seeds", coopGameMode: "Multiworld", players: 1, antiBkBias: 0, dropActive: false,
                        tracking: true, variations: ["ForceTrees"], gameId: gameId, itemPool: getPool("Standard"), dedupShared: false, 
                        paths: presets["standard"], keyMode: "Clues", oldKeyMode: "Clues", spawn: "Glades", advancedSpawnTouched: false, 
                        spawnHCs: 3, spawnECs: 0, spawnSKs: 0, pathMode: "standard", pathDiff: "Normal", helpParams: getHelpContent("none", null), 
                        goalModes: ["ForceTrees"], selectedPool: "Standard", seed: "", fillAlg: "Balanced", quickstartOpen: quickstartOpen, 
                        shared: ["Skills", "Teleporters", "World Events", "Upgrades", "Misc"], mwShared: [], helpcat: "", helpopt: "",
                        apMode: false, apExport: [...apDefaultExport], apDeathLink: false, inputApMode: false, playerNames: [],
                        apHost: AP_DEFAULT_HOST, apPort: "", apPassword: "", apConnectPending: false, apStatus: null, apNoLink: false, apHidden: false, apPollFailed: false,
                        expPool: 10000, lastHelp: new Date(), seedIsGenerating: seedTabExists, cellFreq: cellFreqPresets("standard"),
                        fragCount: 30, fragReq: 20, relicCount: 8, loader: get_random_loader(), paramId: paramId, seedTabExists: seedTabExists, 
                        reopenUrl: "", flagLine: "", fassList: fassDefaultsFor(1), fassWorld: 1, goalModesOpen: false, 
                        spoilers: true, spawnWeights: [1.0,2.0,2.0,2.0,1.5,2.0,0.1,0.1,0.25,0.5], seedIsBingo: false, bingoLines: 3, 
                        auxModal: false, auxPlayer: 1, auxSpoiler: {active: false, byZone: false, exclude: ["EX","KS", "AC", "EC", "HC", "MS"]},
                        stupidMode: stupidMode, customLogic: false, stupidWarn: stupidWarn, verboseSpoiler: get_param("verbose") === "True"};
        
        if(url.searchParams.has("fromBingo")) {
            this.state.goalModes = ["Bingo"]
            this.state.variations = ["Bingo", "OpenWorld"]
            this.state.itemPool = getPool("Bonus Lite")
            this.state.selectedPool = "Bonus Lite"
            this.updateUrl()
        }
        this.apPollTimer = null
        this.apPrefilled = false
    }

    componentDidMount() {
        if(this.apPanelVisible())
            this.startApPoll()
    }

    componentDidUpdate(prevProps, prevState) {
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
        this.stopApPoll()
    }
        
    closeModal = () => {
         window.history.replaceState('',window.document.title, window.document.URL.split("/quickstart")[0]);
         this.setState({quickstartOpen: false, auxModal: false})
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
            const usedCoords = new Set(fassList.filter(fass => (fass.world || 1) === world).map(fass => fass.value));
            newLoc = locOptions.find(loc => !usedCoords.has(loc.value));
            if(!newLoc) return {};
        }
        fassList.push({loc: newLoc, item: item, world: world, owner: world});
        this.refs.fassTabula.clear();
        return {fassList: fassList};
    });
    // merge items into the Buried row(s) at the given depths for the current
    // world, creating rows as needed (items already buried there are skipped)
    buryItems = (groups) => () => this.setState(prevState => {
        const world = this.isMultiworld() ? prevState.fassWorld : 1;
        let fassList = [...prevState.fassList];
        groups.forEach(({depth, items}) => {
            const loc = locOptionFromCoords(BURIED_LOC_BASE + depth);
            const idx = fassList.findIndex(f => (f.world || 1) === world && f.loc.value === loc.value);
            if(idx > -1) {
                let parts = pickupToParts(fassList[idx].item);
                items.forEach(i => parts.includes(i) || parts.push(i));
                fassList[idx] = {...fassList[idx], item: partsToPickup(parts)};
            } else {
                fassList.push({loc: loc, item: partsToPickup(items), world: world, owner: world});
            }
        });
        return {fassList: fassList};
    });
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
    playerNamesShown = () => (this.apAvailable() && this.state.apMode) || (!this.hasVar("Bingo") && this.state.players > 1)
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
                    prev.itemPool.push({item: "WP|*", count: 4, upTo: 8, maximum: 14})
                    return {itemPool: [...prev.itemPool], variations: prev.variations.concat(v), selectedPool: "Custom"}
                });
                else this.setState({variations: this.state.variations.concat(v)});
            }
        }
    }
    pathDisabled = (path) => {
        if(revDisabledPaths.hasOwnProperty(path))
            if(revDisabledPaths[path].some(v => this.hasVar(v)))
            {
                if(this.state.paths.includes(path))
                    this.onPath(path)()
                return true
            }
        return false
    }
    onKeyMode = (mode) => () => this.setState({keyMode: mode})

    onSpawnLoc = (loc) => () => this.setState(prev => {
        if(loc === "Random" || prev.advancedSpawnTouched) // on your own, nerds!
            return {spawn: loc}
 
        let [hp, energy, skills] = [3, 1, 0] // defaults
        if(spawn_defaults[loc].hasOwnProperty(this.state.pathMode)) 
            [hp, energy, skills] = spawn_defaults[loc][this.state.pathMode]
        else 
            dev && console.log(this.state.pathMode, loc, spawn_defaults[loc], spawn_defaults.hasOwnProperty(loc), spawn_defaults[loc].hasOwnProperty(this.state.pathMode));
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
            varPaths[mode].forEach(v => vars.includes(v) ? null : vars.push(v))
        let pd = this.state.pathDiff
        if(diffPaths.hasOwnProperty(this.state.pathMode))
            pd = "Normal"
        if(diffPaths.hasOwnProperty(mode))
            pd = diffPaths[mode]
        this.setState({variations: vars,cellFreq: cellFreqPresets(mode), pathMode: mode, paths: presets[mode], pathDiff: pd})
    }

    render = () => {
        let {randomizedWith, stupidMode, spawn, pathMode, goalModes, keyMode, helpParams, goalModesOpen, seedTabExists, helpcat, activeTab, seed, tracking, seedIsGenerating, user} = this.state;
        let s = getComputedStyle(document.body);
        let styles = {inputStyle: {'borderColor': s.getPropertyValue('--dark'), 'backgroundColor': s.getPropertyValue("background-color"), 'color': s.getPropertyValue("color")}, menuStyle: {}}

        let pathModeOptions = Object.keys(presets).map(mode => (
            <DropdownItem key={`pathmode-${mode}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicModes", mode)} className="text-capitalize" active={mode===pathMode.toLowerCase()} onClick={this.onMode(mode)}>{mode}</DropdownItem>
        ))
        let spawnOptions = SPAWN_OPTS.map(loc => (
            <DropdownItem key={`spawn-${loc}`} active={loc===spawn} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "spawnLoc")} onClick={this.onSpawnLoc(loc)}>{loc}</DropdownItem>
        ))

        const rerollButton = user ? (<Button className="w-100" color="info" href="/reroll">Reroll Last Seed</Button>) : <Button className="w-100" color="info" outline disabled>(Can't Reroll!)</Button>;
        const canRandomize = seed !== randomizedWith;
        const randomizeButton = canRandomize ? 
        (<Button className="w-100" color="danger" onClick={this.randomize}>Randomize!</Button>) :
        (<Button className="w-100" disabled block>Randomize</Button>);
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
        let badIdeasTab = this.getStupidTab()
        let variationsTab = this.getVariationsTab()
        let pathsTab = this.getPathsTab()
        let badIdeasNav = stupidMode ? (
            <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "stupidTab")}>
                <NavLink active={activeTab === 'stupid'} onClick={this.onTab('stupid')}>
                    Stupid
                </NavLink>
            </NavItem>
        ) : null;
        let seedNav = seedTabExists ? (
            <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "seedTab")}>
                <NavLink active={activeTab === 'seed'} onClick={this.onTab('seed')}>
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
                <Cent><a target="blank" href="/patchnotes/4.1.x">(changelog)</a></Cent>
            </Row>
            <Row className="p-3 border">
                <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "logicModes")}>
                    <Row>
                        <Col xs="5"  className="text-center pt-1 border">
                            <span className="align-middle">Logic Mode</span>
                        </Col>
                        <Col xs="7" onMouseLeave={this.helpEnter("general", "logicModes")} onMouseEnter={this.helpEnter("logicModes", pathMode)}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" className="text-capitalize" caret block> {pathMode} </DropdownToggle>
                                <DropdownMenu style={styles.menuStyle}> {pathModeOptions} </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "keyModes")}>
                    <Row>
                        <Col xs="5"  className="text-center pt-1 border">
                            <span className="align-middle">Key Mode</span>
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
                <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "goalModes")}>
                    <Row>
                        <Col xs="5"  className="text-center pt-1 border">
                            <span className="align-middle">Goal Mode</span>
                        </Col>
                        <Col xs="7" onMouseLeave={this.helpEnter("general", "goalModes")} onMouseEnter={this.helpEnter("goalModes", goalModeMulti ? "Multiple" : goalModes[0])}>
                            <Dropdown disabled={goalModeMulti} isOpen={goalModesOpen} toggle={() => this.setState({goalModesOpen: !goalModesOpen})} className="w-100">
                                <DropdownToggle disabled={goalModeMulti} color={goalModeMulti ? "disabled" :"primary"} className="text-capitalize" caret={!goalModeMulti} block> 
                                  {goalModeMulti ? ("Multi:" + (goalModes || []).map(gm => gm.split('').filter(c => c === c.toUpperCase()).join('')).join("+")) : (goalModes.length > 0 ? (VAR_NAMES[goalModes[0]] || goalModes[0]) : "None")}
                                </DropdownToggle>
                                <DropdownMenu style={{zIndex: 10000, ...styles.menuStyle}}>
                                    {goalModeOptions}
                                </DropdownMenu>
                            </Dropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4">
                    <Row>
                        <Col xs="5"  className="text-center pt-1 border mt-2" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "itemPoolPreset")}>
                            <span className="align-middle">Item Pool</span>
                        </Col>
                        <Col xs="7" className="mt-2" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", this.state.selectedPool)}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" caret block> {this.state.selectedPool} </DropdownToggle>
                                <DropdownMenu> {presetPoolOptions} </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "spawnLoc")}>
                    <Row>
                        <Col xs="5"  className="text-center pt-1 border mt-2">
                            <span className="align-middle">Spawn</span>
                        </Col>
                        <Col xs="7" className="mt-2" onMouseLeave={this.helpEnter("general", "spawnLoc")} onMouseEnter={this.helpEnter("general", "spawnLoc")}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" className="text-capitalize" caret block> {spawn} </DropdownToggle>
                                <DropdownMenu style={styles.menuStyle}> {spawnOptions} </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4">
                    <Row>
                        <Col xs="5"  className="mt-2" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", canRandomize ? "randomize" : "randomizeDisabled")}>
                            {randomizeButton}
                        </Col>
                        <Col xs="7"  className="mt-2" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", user ? "reroll" : "rerollDisabled")}>
                            {rerollButton}
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
                    {badIdeasNav}
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
                                {badIdeasTab}
                                {seedTab}
                            </TabContent>
                        </Col>
                    </Row>
                    <Collapse isOpen={activeTab !== "seed"}>
                        <Row className="align-items-center">
                            <Col xs="6">
                                <Row className="m-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "seed")}>
                                    <Col xs="5" className="text-center pt-1 border">
                                        <span className="align-middle">Seed</span>
                                    </Col><Col xs="7">
                                        <Input style={styles.inputStyle} type="text" value={seed} onChange={(e) => this.setState({seed: e.target.value})}/>
                                    </Col>
                                </Row><Row className="m-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "webTracking" + (lockTracking ? "-locked" : ""))}>
                                    <Col>
                                        <Button color="info" block outline={!tracking} disabled={lockTracking} onClick={()=>this.setState({tracking: !tracking})}>Web Tracking {tracking ? "Enabled" : "Disabled"}</Button>
                                    </Col>
                                </Row>
                            </Col>
                            <Col>
                                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "generate" + this.multi())}>
                                    <Col>
                                        <Button color="success" disabled={seedIsGenerating} size="lg" onClick={this.generateSeed} block>Generate Seed</Button>
                                    </Col>
                                </Row>
                            </Col>
                        </Row>
                    </Collapse>
                </Col>
                <Col>
                    <Row className="sticky-top">
                        <HelpBox style={styles.menuStyle} {...helpParams} />
                    </Row>
                </Col>
            </Row>
            </Container>
        )

    }
};
function uploadReaderLines(lines)  {
    let xmlHttp = new XMLHttpRequest();
    xmlHttp.open("POST", "user/custom_logic/set", true);
    xmlHttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    xmlHttp.send(encodeURI(`lines=${JSON.stringify(lines)}`));
}

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

function postNetForm(url, fields, callback)  {
    let xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = () => {
        if (xmlHttp.readyState === 4) {
            callback(xmlHttp);
        }
    };
    xmlHttp.open("POST", url, true);
    xmlHttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    xmlHttp.send(Object.keys(fields).map(k => `${k}=${encodeURIComponent(fields[k])}`).join("&"));
}