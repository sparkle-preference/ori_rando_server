import React from 'react';
import  {DropdownToggle, DropdownMenu, Dropdown, DropdownItem, Nav, NavLink, NavItem, Collapse,  Input, UncontrolledButtonDropdown, Button, 
        Row, FormFeedback, Col, Container, TabContent, TabPane, Modal, ModalHeader, ModalBody, ModalFooter, Media, ButtonGroup} from 'reactstrap';
import { FaCog } from 'react-icons/fa';
import {NotificationContainer, NotificationManager} from 'react-notifications';

import 'react-notifications/lib/notifications.css';
import './index.css';

import {getHelpContent, HelpBox} from "./helpbox.js";
import {get_param, spawn_defaults, get_flag, presets, select_theme, name_from_str, get_preset, player_icons, doNetRequest, get_random_loader, PickupSelect, Cent, dev, randInt, gotoUrl} from './common.js';
import SiteBar from "./SiteBar.js";
import Select from 'react-select';
import Dropzone from 'react-dropzone'
import {picks_by_zone} from './shared_map'


const zonesInOrder = ['Glades', 'Blackroot', 'Grove', 'Grotto', 'Ginso', 'Swamp', 'Valley', 'Misty', 'Forlorn', 'Sorrow', 'Horu'];
const locOptions = [{'label': 'Spawn With', 'value': 2}];
zonesInOrder.forEach(zone =>  picks_by_zone[zone].forEach(p => locOptions.push({'label': `${p.area} ${p.name} (${zone})`, 'value': p.loc})));
picks_by_zone['Mapstone'].forEach(p => locOptions.push({'label': p.name, 'value': p.loc}));
const locOptionFromCoords = (coords) => locOptions.find(l => l.value === coords);
const get_pool = (pool_name) => { switch(pool_name) {
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
            {item: "EC|1", count: 14, minimum: 3},
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
            {item: "EC|1", count: 3, minimum: 3},
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
            {item: "EC|1", count: 14, minimum: 3},
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
            {item: "EC|1", count: 14, minimum: 3},
            {item: "AC|1", count: 33},
            {item: "RP|RB/0", count: 3},
            {item: "RP|RB/1", count: 3},
            {item: "RB|6", count: 5},
            {item: "RB|9", count: 1},
            {item: "RB|10", count: 1},
            {item: "RB|11", count: 1},
            {item: "RB|12", count: 3},
            {item: "RB|37", count: 3},
            {item: "RB|13", count: 3},
            {item: "RB|15", count: 3},
            {item: "RB|31", count: 1},
            {item: "RB|32", count: 1},
            {item: "RB|33", count: 3},
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
            {item: "EC|1", count: 14, minimum: 3},
            {item: "AC|1", count: 33},
            {item: "RB|0", count: 3},
            {item: "RB|1", count: 3},
            {item: "RB|6", count: 5},
            {item: "RB|9", count: 1},
            {item: "RB|10", count: 1},
            {item: "RB|11", count: 1},
            {item: "RB|12", count: 3},
            {item: "RB|37", count: 3},
            {item: "RB|13", count: 3},
            {item: "RB|15", count: 3},
            {item: "RB|31", count: 1},
            {item: "RB|32", count: 1},
            {item: "RB|33", count: 3},
            {item: "RB|36", count: 1},
            {item: "WP|*", count: 4, upTo: 8, maximum: 14},
        ]
    default:
        dev && console.log(`${pool_name} is not a valid pool name! Using the standard pool instead`)
        return get_pool("Standard")
    }
}
const CANONICAL_ORDERING = {}
get_pool("Extra Bonus").forEach(({item}, i) => CANONICAL_ORDERING[item] = i)
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
    ForceTrees: "Force Trees",
    Starved: "Starved",
    Hard: "Hard Mode",
    OHKO: "One Hit KO",
    "0XP": "Zero Experience",
    ForceMaps: "Force Maps",
    BonusPickups: "More Bonus Pickups",
    ClosedDungeons: "Closed Dungeons",
    OpenWorld: "Open World",
    WorldTour: "World Tour",
    DoubleSkills: "Extra Copies",
    WarmthFrags: "Warmth Frags",
    StrictMapstones: "Strict Mapstones",
    StompTriggers: "Legacy Kuro Behavior",
    TPStarved: "TPStarved",
    GoalModeFinish: "Skip Final Escape",
    Bingo: "Bingo",
    WallStarved: "WallStarved",
    GrenadeStarved: "GrenadeStarved",
    InLogicWarps: "In-Logic Warps",
    Entrance: "Entrance Shuffle",
    Keysanity: "Keysanity",
}
const SPAWN_OPTS = ["Random", "Glades", "Grove", "Swamp", "Grotto", "Forlorn", "Valley", "Horu", "Ginso", "Sorrow", "Blackroot"]
const cellFreqPresets = (preset) => preset === "casual" ? 20 : (preset === "standard" ? 40 : 256)
const optionalPaths = ['casual-dboost', 'standard-core', 'standard-dboost', 'standard-lure', 'standard-abilities', 'expert-core', 'expert-dboost', 'expert-lure', 'expert-abilities', 'dbash', 'master-core', 'master-dboost', 'master-lure', 'master-abilities', 'gjump', 'glitched', 'timed-level', 'insane']
const varPaths = {"master": ["Starved"]}
const diffPaths = {"glitched": "Hard", "master": "Hard"}
const disabledPaths = {
                    "Hard": ["standard-dboost", "expert-dboost", "master-dboost"], 
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
                <PickupSelect value={row.item} isClearable={false} isDisabled={disabled} updater={(code, _) => this.updatePoolItem(index, code)} allowPsuedo/>
            </Col>
            <Col xs="1">{delButton}</Col>
          </Row>)
        })
        let presetPoolOptions = ["Standard", "Competitive", "Extra Bonus", "Bonus Lite", "Hard"].map(preset => (
            <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", preset)} key={`pd-${preset}`} active={this.state.selectedPool===preset} onClick={()=> this.setState({selectedPool: preset, itemPool: get_pool(preset)})}>{preset}</DropdownItem>
        ))

        return (
        <TabPane className="p-3 border" tabId="item pool">
            <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "customPool")} className="p-1 justify-content-center">
                    <Col xs="4">
                        <Cent>Pool Preset: </Cent>
                    </Col>
                    <Col onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", this.state.selectedPool)} xs="4">
                        <UncontrolledButtonDropdown className="w-100">
                            <DropdownToggle color="primary" caret block> {this.state.selectedPool} </DropdownToggle>
                            <DropdownMenu> {presetPoolOptions} </DropdownMenu>
                        </UncontrolledButtonDropdown>
                    </Col>
                </Row>
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
                    <PickupSelect ref="tabula" value={"NO|1"} updater={(code, _) => this.addPoolItem(code)} allowPsuedo/>
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
        if(download)
            url.searchParams.set("download", 1);
        if(multi)
            url.searchParams.set("player_id", p);
        return url.href
    }

    getAdvancedTab = ({inputStyle, menuStyle}) => {
        let {variations, senseData, fillAlg, spawnSKs, spawnECs, spawnHCs, expPool, bingoLines, pathDiff, cellFreq, 
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
        const fassUsed = new Set(fassList.map(({loc}) => loc.value));
        let fass_rows = fassList.map(({loc, item}, i) => (
            <Row key={`fass-arbitrary-${i}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "preplacement")} className="p-1 justify-content-center">
                    <Col xs={leftCol+1}>
                        <Select theme={select_theme} className="align-middle" options={locOptions.filter(l => l.value === loc.value || !fassUsed.has(l.value))} value={loc} onChange={(newLoc) => this.onFassList(i, {loc: newLoc})}></Select>
                    </Col><Col xs={rightCol-1}>
                        <PickupSelect value={item} updater={(code, _) => this.onFassList(i, {item: code})}/>
                    </Col>
            </Row>
        ));
        fass_rows.push((
            <Row key={`fass-arbitrary-next`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "preplacement")} className="p-1 justify-content-center">
                    <Col xs={leftCol+1}>
                    <Select theme={select_theme} className="align-middle" options={locOptions.filter(l => !fassUsed.has(l.value))} value={{label: 'Add new Placement:', value: -1}} onChange={(newLoc) => this.addToFassList({loc: newLoc, item: "NO|1"})}></Select>
                    </Col><Col xs={rightCol-1}>
                        <PickupSelect ref="fassTabula" value={"NO|1"} updater={(code, _) => this.addToFassList({item: code})}/>
                    </Col>
            </Row>
        ))
        let goalCol = (v) => (
            <Col xs="6" onMouseLeave={this.helpEnter("advanced", "goalModes")} onMouseEnter={this.helpEnter("goalModes", v)} className="p-2">
                <Button color="primary" block outline={!variations.includes(v)} onClick={this.onGoalModeAdvanced(v)}>{VAR_NAMES[v]}</Button>
            </Col>
        )
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
                <Collapse isOpen={variations.includes("Bingo")}>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "bingoLines")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Bingo Lines</span>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="number" value={bingoLines} invalid={bingoLines > 12 || bingoLines < 1} onChange={(e) => this.setState({bingoLines: parseInt(e.target.value, 10)})}/> 
                        <FormFeedback tooltip="true">Line count must be between 1 and 12</FormFeedback>
                    </Col>
                </Row>
                </Collapse>
                <Collapse isOpen={variations.includes("WorldTour")}>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "relicCount")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span className="align-middle">Relic Count</span>
                        </Col><Col xs={rightCol}>
                            <Input style={inputStyle} type="number" value={relicCount} invalid={relicCount > 11 || relicCount < 1} onChange={(e) => this.setState({relicCount: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip="true">Relic count must be greater than 0 and less than 12</FormFeedback>
                        </Col>
                    </Row>
                </Collapse>
                <Collapse isOpen={variations.includes("WarmthFrags")}>
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

            </TabPane>
        )
    }
    getMultiplayerTab = ({inputStyle, menuStyle}) => {
        let {shared, players, tracking, coopGameMode, keyMode, coopGenMode, dedupShared} = this.state
        let multiplayerButtons = ["Skills", "Teleporters", "Upgrades", "World Events", "Misc"].map(stype => (
            <Col xs="4" key={`share-${stype}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("Shared Item Categories", stype)} className="p-2">
                <Button block outline={!shared.includes(stype)} onClick={this.onSType(stype)}>Share {stype}</Button>
            </Col>
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
                    </Col><Col xs="4">
                        <UncontrolledButtonDropdown className="w-100" >
                            <DropdownToggle disabled={players < 2} color={players > 1 ? "primary" : "secondary"} caret block> {coopGameMode} </DropdownToggle>
                            <DropdownMenu style={menuStyle}>
                                <DropdownItem active={"Race"===coopGameMode} onClick={()=> this.setState({coopGameMode: "Race"})}>Race</DropdownItem>
                                <DropdownItem active={"Co-op"===coopGameMode} onClick={()=> this.setState({coopGameMode: "Co-op"})}>Co-op</DropdownItem>
                                <DropdownItem active={"SplitShards"===coopGameMode} disabled={keyMode !== "Shards"} onClick={()=> this.setState({coopGameMode: "SplitShards"})}>Split Shards</DropdownItem>
                            </DropdownMenu>
                        </UncontrolledButtonDropdown>
                    </Col>
                </Row>
                <Collapse isOpen={players > 1 && coopGameMode === "Co-op"}>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "syncSeedType")} className="p-1 justify-content-center">
                        <Col xs="4" className="text-center pt-1 border">
                            <span className="align-middle">Seed Generation Mode</span>
                        </Col><Col onMouseLeave={this.helpEnter("multiplayerOptions", "syncSeedType")} onMouseEnter={this.helpEnter("multiplayerOptions", coopGenMode)} xs="4">
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle disabled={players < 2} color={players > 1 ? "primary" : "secondary"} caret block> {coopGenMode} </DropdownToggle>
                                <DropdownMenu style={menuStyle}>
                                    <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "Cloned Seeds")}  active={"Cloned Seeds"===coopGenMode} onClick={()=> this.setState({coopGenMode: "Cloned Seeds"})}>Cloned Seeds</DropdownItem>
                                    <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "Seperate Seeds")}  active={"Seperate Seeds"===coopGenMode} onClick={()=> this.setState({coopGenMode: "Seperate Seeds"})}>Seperate Seeds</DropdownItem>
                                </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                    <Row className="p-2">
                        {multiplayerButtons}
                        <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("Shared Item Categories", "Dedup")} className="p-2">
                            <Button block outline={!dedupShared} active={dedupShared} disabled={coopGenMode!=="Cloned Seeds"} onClick={() => this.setState({dedupShared: !dedupShared})}>Dedup Shared</Button>
                        </Col>
                    </Row>
                </Collapse>
            </TabPane>
        )
    }
    
    
    generateSeed = () => {
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
        if(this.state.variations.includes("WarmthFrags"))
        {
            json.fragCount=this.state.fragCount
            json.fragReq=this.state.fragReq
        }
        if(this.state.variations.includes("WorldTour"))
            json.relicCount=this.state.relicCount

        if(this.state.variations.includes("Bingo"))
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
        json.fass = []
        this.state.fassList.forEach(fassEntry => {
                if(fassEntry.item !== "NO|1") {
                    let item = fassEntry.item.split("|");
                    json.fass.push({loc: fassEntry.loc.value.toString(), code: item[0], id: item[1]})
                }
        });
        json.itemPool = {} //{"HC": 12, "EC": 14, "AC": 33, }
        this.state.itemPool.forEach(({item, count, upTo}) => { json.itemPool[item] = upTo ? [count, upTo] : [count] })
        json.tracking = this.state.tracking
        if(this.state.tracking && this.state.players > 1) {
            json.coopGenMode=f(this.state.coopGenMode)
            json.coopGameMode=f(this.state.coopGameMode)
            json.dedupShared = this.state.dedupShared
            if(this.state.coopGameMode === "Co-op")
                json.syncShared = this.state.shared.map(s => f(s))
            if(!this.state.dedupShared)
                json.teams={1: [...Array(this.state.players).keys()].map(x=>x+1)}
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
                    metaUpdate.itemPool = get_pool(metaUpdate.selectedPool) 
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
                metaUpdate.fassList = metaUpdate.fass.map(({loc, item}) => ({loc: locOptionFromCoords(parseInt(loc, 10)), item: item}))
                metaUpdate.fass = undefined;
            }
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
            NotificationManager.error("Failed to generate seed!", "Seed generation failure!", 5000)
            this.setState({seedIsGenerating: false, seedTabExists: false, activeTab: 'variations'}, this.updateUrl)
            return
        } else {
            let res = JSON.parse(responseText)
            if(res.doBingoRedirect) {
                let redir = `/bingo/board?game_id=${res.gameId}&fromGen=1&seed=${res.seed}&bingoLines=${res.bingoLines || 3}`
                if(res.flagLine.includes("share="))
                    redir += `&teamMax=${res.playerCount}`
                gotoUrl(redir, true)
                this.helpEnter("general", "seedBuiltBingo")()
            }
            else 
                this.helpEnter("general", "seedBuilt" + this.multi())()
            this.setState({
                paramId: res.paramId, seedIsGenerating: false, inputPlayerCount: res.playerCount, inputSeed: res.seed,
                flagLine: res.flagLine, gameId: res.gameId, seedIsBingo: res.doBingoRedirect || false
            }, this.updateUrl)
        }
    }
    getVariationsTab = () => {
        let filteredVars = ["NonProgressMapStones", "BonusPickups", "ForceTrees", "WorldTour", "ForceMaps", "WarmthFrags", "Hard", "Bingo"];
        if(!this.state.stupidMode) {
            filteredVars = filteredVars.concat("StompTriggers", "StrictMapstones")
        }
        let variationButtons = Object.keys(VAR_NAMES).filter(x => !filteredVars.includes(x)).map(v=> {
            let name = VAR_NAMES[v];
            return (
            <Col key={`var-button-${v}`} xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", v)} className="p-2">
                <Button block color="primary" outline={!this.state.variations.includes(v)} onClick={this.onVar(v)}>{name}</Button>
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
            let {inputPlayerCount, gameId, seedIsBingo, paramId, flagLine, spoilers, inputSeed, bingoLines, auxSpoiler} = this.state
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
                let mainButtonHelp = "downloadButton"+this.multi()
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
                                <Button color={spoilers ? "success" : "secondary"} disabled={!spoilers} onClick={() => this.setState({auxModal: true})} target="_blank"><FaCog/></Button>
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
                            <Row className="justify-content-start">
                            {flagCols}
                            </Row>
                        </Col>
                      </Row>
                    {playerRows}
                    {trackedInfo}
                </TabPane>
                )
        }
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
        const fassListDefault = [2, 919772, -1560272, 799776, -120208].map(coords => ({loc: locOptions.find(l => l.value === coords), item: "NO|1"}));
        
        this.state = {user: user, activeTab: activeTab, coopGenMode: "Cloned Seeds", coopGameMode: "Co-op", players: 1, dropActive: false, 
                        tracking: true, variations: ["ForceTrees"], gameId: gameId, itemPool: get_pool("Standard"), dedupShared: false, 
                        paths: presets["standard"], keyMode: "Clues", oldKeyMode: "Clues", spawn: "Glades", advancedSpawnTouched: false, 
                        spawnHCs: 3, spawnECs: 0, spawnSKs: 0, pathMode: "standard", pathDiff: "Normal", helpParams: getHelpContent("none", null), 
                        goalModes: ["ForceTrees"], selectedPool: "Standard", seed: "", fillAlg: "Balanced", quickstartOpen: quickstartOpen, 
                        shared: ["Skills", "Teleporters", "World Events", "Upgrades", "Misc"], helpcat: "", helpopt: "", 
                        expPool: 10000, lastHelp: new Date(), seedIsGenerating: seedTabExists, cellFreq: cellFreqPresets("standard"),
                        fragCount: 30, fragReq: 20, relicCount: 8, loader: get_random_loader(), paramId: paramId, seedTabExists: seedTabExists, 
                        reopenUrl: "", flagLine: "", fassList: [...fassListDefault], goalModesOpen: false, 
                        spoilers: true, spawnWeights: [1.0,2.0,2.0,2.0,1.5,2.0,0.1,0.1,0.25,0.5], seedIsBingo: false, bingoLines: 3, 
                        auxModal: false, auxSpoiler: {active: false, byZone: false, exclude: ["EX","KS", "AC", "EC", "HC", "MS"]}, 
                        stupidMode: stupidMode, customLogic: false, stupidWarn: stupidWarn, verboseSpoiler: get_param("verbose") === "True"};
        
        if(url.searchParams.has("fromBingo")) {
            this.state.goalModes = ["Bingo"]
            this.state.variations = ["Bingo", "OpenWorld"]
            this.state.itemPool = get_pool("Extra Bonus")
            this.state.selectedPool = "Extra Bonus"
            this.updateUrl()
        }
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
        let newLoc = loc;
        if(!newLoc) {
            const usedCoords = new Set(fassList.map(fass => fass.value));
            newLoc = locOptions.find(loc => !usedCoords.has(loc.value));
            if(!newLoc) return {};    
        }
        fassList.push({loc: newLoc, item: item});
        this.refs.fassTabula.clear();
        return {fassList: fassList};
    });
    onPath = (p) => () => this.setState({paths: this.state.paths.includes(p) ? this.state.paths.filter(x => x !== p) : this.state.paths.concat(p)}, () => this.setState(p => {return {pathMode: get_preset(p.paths)}}))
    onSType = (s) => () => this.state.shared.includes(s) ? this.setState({shared: this.state.shared.filter(x => x !== s)}) : this.setState({shared: this.state.shared.concat(s)})    
    onVar = (v) => () => {
        if(this.state.variations.includes(v)) {
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
            if(revDisabledPaths[path].some(v => this.state.variations.includes(v)))
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
        let {stupidMode, spawn, pathMode, goalModes, keyMode, helpParams, goalModesOpen, seedTabExists, helpcat, activeTab, seed, tracking, seedIsGenerating, user} = this.state;
        let s = getComputedStyle(document.body);
        let styles = {inputStyle: {'borderColor': s.getPropertyValue('--dark'), 'backgroundColor': s.getPropertyValue("background-color"), 'color': s.getPropertyValue("color")}, menuStyle: {}}

        let pathModeOptions = Object.keys(presets).map(mode => (
            <DropdownItem key={`pathmode-${mode}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicModes", mode)} className="text-capitalize" active={mode===pathMode.toLowerCase()} onClick={this.onMode(mode)}>{mode}</DropdownItem>
        ))
        let spawnOptions = SPAWN_OPTS.map(loc => (
            <DropdownItem key={`spawn-${loc}`} active={loc===spawn} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "spawnLoc")} onClick={this.onSpawnLoc(loc)}>{loc}</DropdownItem>
        ))

        let rerollButton = user ? (<Button color="info" href="/reroll">Reroll Last Seed</Button>) : <Button color="info" outline disabled>Reroll Last Seed</Button>;

        let keyModeOptions = keymode_options.map(mode => (
            <DropdownItem key={`keymode-${mode}`} active={mode===keyMode} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("keyModes", mode)} onClick={this.onKeyMode(mode)}>{mode}</DropdownItem>
        ))
        let validGoalModes = ["None", "ForceTrees", "WorldTour", "ForceMaps", "WarmthFrags", "Bingo"]
        let goalModeOptions = goalModes.length === 1 ? validGoalModes.map(mode => (
            <DropdownItem key={`goalmode-${mode}`} active={mode===goalModes[0]} disabled={mode==="Bingo" && !tracking} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("goalModes", mode)} onClick={this.onGoalMode(mode)}>{VAR_NAMES[mode] || mode}{mode==="Bingo" && !tracking ? '(Needs tracking!)' : ''}</DropdownItem>
        )) : null

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

        return (
         <Container className="pl-2 pr-2 pb-4 pt-2 mt-5">
             <Row className="justify-content-center">
                 <Col>
                     {modal}
                    <NotificationContainer/>
                    <SiteBar/>
                </Col>
            </Row>
            <Row className="p-1">
                <Cent><h3 >Seed Generator {VERSION}</h3></Cent>
            </Row>
            <Row className="p-3 border">
                <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "logicModes")}>
                    <Row>
                        <Col xs="6"  className="text-center pt-1 border">
                            <span className="align-middle">Logic Mode</span>
                        </Col>
                        <Col xs="6" onMouseLeave={this.helpEnter("general", "logicModes")} onMouseEnter={this.helpEnter("logicModes", pathMode)}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" className="text-capitalize" caret block> {pathMode} </DropdownToggle>
                                <DropdownMenu style={styles.menuStyle}> {pathModeOptions} </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "keyModes")}>
                    <Row>
                        <Col xs="6"  className="text-center pt-1 border">
                            <span className="align-middle">Key Mode</span>
                        </Col>
                        <Col xs="6" onMouseEnter={this.helpEnter("keyModes", keyMode)} onMouseLeave={this.helpEnter("general", "keyModes",(keyMode === "Clues" && helpcat === "keyModes") ? 1000 : 250 )}>
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
                        <Col xs="6"  className="text-center pt-1 border">
                            <span className="align-middle">Goal Mode</span>
                        </Col>
                        <Col xs="6" onMouseLeave={this.helpEnter("general", "goalModes")} onMouseEnter={this.helpEnter("goalModes", goalModeMulti ? "Multiple" : goalModes[0])}>
                            <Dropdown disabled={goalModeMulti} isOpen={goalModesOpen} toggle={() => this.setState({goalModesOpen: !goalModesOpen})} className="w-100">
                                <DropdownToggle disabled={goalModeMulti} color={goalModeMulti ? "disabled" :"primary"} className="text-capitalize" caret={!goalModeMulti} block> 
                                  {goalModeMulti ? "Multiple" : (VAR_NAMES[goalModes[0]] || goalModes[0])}
                                </DropdownToggle>
                                <DropdownMenu style={{zIndex: 10000, ...styles.menuStyle}}>
                                    {goalModeOptions}
                                </DropdownMenu>
                            </Dropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4" className="text-center pt-1 mt-1"onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", user ? "reroll" : "rerollDisabled")}>
                    {rerollButton}
                </Col>
                <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "spawnLoc")}>
                    <Row>
                        <Col xs="6"  className="text-center pt-1 border mt-2">
                            <span className="align-middle">Spawn</span>
                        </Col>
                        <Col xs="6" className="mt-2" onMouseLeave={this.helpEnter("general", "spawnLoc")} onMouseEnter={this.helpEnter("general", "spawnLoc")}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" className="text-capitalize" caret block> {spawn} </DropdownToggle>
                                <DropdownMenu style={styles.menuStyle}> {spawnOptions} </DropdownMenu>
                            </UncontrolledButtonDropdown>
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
                        Item Pool
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