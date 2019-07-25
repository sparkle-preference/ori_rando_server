import React from 'react';
import  {DropdownToggle, DropdownMenu, Dropdown, DropdownItem, Nav, NavLink, NavItem, Collapse,  Input, UncontrolledButtonDropdown, Button, 
        Row, FormFeedback, Col, Container, TabContent, TabPane, Modal, ModalHeader, ModalBody, ModalFooter, Media} from 'reactstrap'
import {NotificationContainer, NotificationManager} from 'react-notifications';

import 'react-notifications/lib/notifications.css';
import './index.css';

import {getHelpContent, HelpBox} from "./helpbox.js"
import {get_param, presets, name_from_str, get_preset, player_icons, doNetRequest, get_random_loader, PickupSelect, Cent, dev, randInt, gotoUrl} from './common.js';
import SiteBar from "./SiteBar.js"

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
            {item: "TP|Ginso", count: 1},
            {item: "TP|Horu", count: 1},
            {item: "TP|Forlorn", count: 1},
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
            {item: "HC|1", count: 12},
            {item: "EC|1", count: 14, minimum: 3},
            {item: "AC|1", count: 33},
            {item: "RP|RB/0", count: 3},
            {item: "RP|RB/1", count: 3},
            {item: "RB|6", count: 5},
            {item: "RB|9", count: 1},
            {item: "RB|10", count: 1},
            {item: "RB|11", count: 1},
            {item: "RB|12", count: 5},
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
            {item: "HC|1", count: 12},
            {item: "EC|1", count: 14, minimum: 3},
            {item: "AC|1", count: 33},
            {item: "RB|0", count: 3},
            {item: "RB|1", count: 3},
            {item: "RB|6", count: 5},
            {item: "RB|9", count: 1},
            {item: "RB|10", count: 1},
            {item: "RB|11", count: 1},
            {item: "RB|12", count: 5},
            {item: "RB|13", count: 3},
            {item: "RB|15", count: 3},
            {item: "RB|31", count: 1},
            {item: "RB|32", count: 1},
            {item: "RB|33", count: 3},
            {item: "RB|36", count: 1},
            {item: "WP|*", count: 4, upTo: 8, maximum: 14},
        ]
    default:
        console.log(`${pool_name} is not a valid pool name! Using the standard pool instead`)
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
const VAR_NAMES = {
    ForceTrees: "Force Trees",
    Starved: "Starved",
    Hard: "Hard Mode",
    OHKO: "One Hit KO",
    "0XP": "Zero Experience",
    ForceMaps: "Force Maps",
    Entrance: "Entrance Shuffle",
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
    Bingo: "Bingo"
}
const cellFreqPresets = (preset) => preset === "casual" ? 20 : (preset === "standard" ? 40 : 256)
const optional_paths = ['casual-dboost', 'standard-core', 'standard-dboost', 'standard-lure', 'standard-abilities', 'expert-core', 'expert-dboost', 'expert-lure', 'expert-abilities', 'dbash', 'master-core', 'master-dboost', 'master-lure', 'master-abilities', 'gjump', 'glitched', 'timed-level', 'insane']
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
        minimum = minimum || 1
        prev.selectedPool = "Custom"
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

    getItemPoolTab = ({inputStyle}) => {
        let itemSelectors = this.state.itemPool.map((row, index) => {
          let disabled = row.minimum && row.minimum > 0
          let delButton = disabled ? null : (<Button onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", "deleteRow")} onClick={this.deletePoolItem(index)} color="danger">X</Button>)
          
          return (<Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "customPool")} className="p-1 justify-content-center">
            <Col xs="4">
            <Cent>
                <Input  onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", "count")} type="number" className="mr-2" style={inputStyle} invalid={row.maximum && row.maximum < row.row} value={row.count} onChange={(e) => this.updateItemCount(index, parseInt(e.target.value, 10), row)}/>
                <FormFeedback tooltip>Maximum number of {name_from_str(row.item)} allowed is {row.maximum}</FormFeedback>
                {" - "}
                <Input type="number" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("itemPool", "upTo")}  invalid={row.upTo && (row.upTo < row.count || (row.maximum && row.maximum < row.upTo))} className="ml-2" style={inputStyle} value={row.upTo || row.count} onChange={(e) => this.updateItemUpTo(index, parseInt(e.target.value, 10))}/>
                <FormFeedback tooltip>{row.upTo < row.count ? `Max count can't be lower than min count(${row.count})` : `Maximum number of ${name_from_str(row.item)} allowed is ${row.maximum}`}</FormFeedback>
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
    
    getAdvancedTab = ({inputStyle, menuStyle}) => {
        let {variations, senseData, fillAlg, expPool, pathDiff, cellFreq, relicCount, fragCount, fragReq} = this.state
        let [leftCol, rightCol] = [4, 7]
        let pathDiffOptions = ["Easy", "Normal", "Hard"].map(mode => (
            <DropdownItem key={`pd-${mode}`} active={mode===pathDiff} onClick={()=> this.setState({pathDiff: mode})}>{mode}</DropdownItem>
        ))
        const starting_pickups = {"Spawn With:": 2, "First Pickup:": 919772, "Second Pickup:": -1560272, "Third Pickup:": 799776, "Fourth Pickup:": -120208}
        let fass_rows = Object.keys(starting_pickups).map(name => {
            let coord = starting_pickups[name];
            return (
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "preplacement")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">{name}</span>
                    </Col><Col xs={rightCol}>
                        <PickupSelect updater={(code, _) => this.onFass(coord, code)}/> 
                    </Col>
                </Row>
            )
        })
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
                        <FormFeedback tooltip>Experience Pool must be at least 100</FormFeedback>
                    </Col>
                </Row>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "sense")} className="p-1 justify-content-center">
                    <Col xs={leftCol} className="text-center pt-1 border">
                        <span className="align-middle">Sense Triggers</span>
                    </Col><Col xs={rightCol}>
                        <Input style={inputStyle} type="text" value={senseData}  onChange={(e) => this.setState({senseData: e.target.value})}/> 
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
                        <FormFeedback tooltip>Forced Cell Frequency must be at least 3</FormFeedback>
                    </Col>
                </Row>
                {fass_rows}
                <Collapse isOpen={variations.includes("WorldTour")}>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "relicCount")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span className="align-middle">Relic Count</span>
                        </Col><Col xs={rightCol}>
                            <Input style={inputStyle} type="number" value={relicCount} invalid={relicCount > 11 || relicCount < 1} onChange={(e) => this.setState({relicCount: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip>Relic count must be greater than 0 and less than 12</FormFeedback>
                        </Col>
                    </Row>
                </Collapse>
                <Collapse isOpen={variations.includes("WarmthFrags")}>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fragCount")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span className="align-middle">Fragment Count</span>
                        </Col><Col xs={rightCol}>
                            <Input style={inputStyle} type="number" value={fragCount} invalid={fragCount > 60 || fragCount < 1} onChange={(e) => this.setState({fragCount: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip>Frag Count must be between 1 and 60</FormFeedback>
                        </Col>
                    </Row>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fragRequired")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span className="align-middle">Fragments Required</span>
                        </Col><Col xs={rightCol}>
                            <Input style={inputStyle} type="number" value={fragReq} invalid={fragCount < fragReq || fragReq <= 0} onChange={e => this.setState({fragReq: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip>Fragments Required must be between 0 and Fragment Count ({fragCount})</FormFeedback>
                        </Col>
                    </Row>
                </Collapse>
            </TabPane>
        )
    }
    getMultiplayerTab = ({inputStyle, menuStyle}) => {
        let {shared, players, tracking, coopGameMode, keyMode, coopGenMode, teamStr, dedupShared} = this.state
        let multiplayerButtons = ["Skills", "Teleporters", "Upgrades", "World Events", "Misc"].map(stype => (
            <Col xs="4" key={`share-${stype}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("Shared Item Categories", stype)} className="p-2">
                <Button block outline={!shared.includes(stype)} onClick={this.onSType(stype)}>Share {stype}</Button>
            </Col>
        ))
        
        let playerNumValid = tracking && players > 0;
        let playerNumFeedback = tracking ? (players > 0 ? null : (
            <FormFeedback tooltip>Need at least one player...</FormFeedback>
        )) : (
            <FormFeedback tooltip>Multiplayer modes require web tracking to be enabled</FormFeedback>
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
                <Collapse isOpen={false}>
                    <Row className="p-1 justify-content-center">
                        <Col xs="4" className="text-center pt-1 border">
                            <span className="align-middle">Teams</span>
                        </Col><Col xs="4">
                            <Input style={inputStyle} type="text" value={teamStr} invalid={!this.teamStrValid()} onChange={(e) => this.setState({teamStr: e.target.value})}/>
                            <FormFeedback tooltip>Team format: 1,2|3,4|5,6. Each player must appear once.</FormFeedback>
                        </Col>
                    </Row>
                </Collapse>
            </TabPane>
        )
    }
    teamStrValid = () => {
        let teamStr = this.state.teamStr;
        if(teamStr === "") return true;
        let retval = true;
        let players = [...Array(this.state.players).keys()].map(i => i+1)
        let teams = teamStr.split("|");
        teams.forEach(team => team.split(",").forEach(p => {
            if(isNaN(p)) retval = false;
            else p = parseInt(p,10)
            if(p > this.state.players) retval = false;
            if(players[p-1] !== p) retval = false;
            players[p-1] = 0;
        }))
        return retval && players.reduce((a,b)=>a+b,0) === 0
    }
    
    generateSeed = () => {
        let pMap = {"Race": "None", "None": "Default", "Co-op": "Shared", "World Events": "WorldEvents", "Cloned Seeds": "cloned", "Seperate Seeds": "disjoint"}
        let url = "/generator/build"
        let f = (p) => pMap.hasOwnProperty(p) ? pMap[p] : p
        let json = {
            "key_mode": f(this.state.keyMode),
            'gen_mode': this.state.fillAlg,
            'variations': this.state.variations,
            'logic_paths': this.state.paths,
            "exp_pool": this.state.expPool,
            "cell_freq": this.state.cellFreq,
            "pool_preset": this.state.selectedPool
        }
        if(this.state.pathDiff !== "Normal")
            json.path_diff=this.state.pathDiff
        if(this.state.senseData)
            json.sense=this.state.senseData
        if(this.state.variations.includes("WarmthFrags"))
        {
            json.frags=this.state.fragCount
            json.frags_req=this.state.fragReq
        }
        if(this.state.variations.includes("WorldTour"))
            json.relics=this.state.relicCount

        if(this.state.variations.includes("Bingo"))
            url += "?bingo=1"

        json.players=this.state.players
        json.fass = []
        Object.keys(this.state.fass).forEach(loc => {
            if(this.state.fass[loc]) {
                if(this.state.fass[loc] !== "NO|1")
                {
                    let item = this.state.fass[loc].split("|");
                    json.fass.push({loc: loc, code: item[0], id: item[1]})
                }
            }
        })
        json.item_pool = {} //{"HC": 12, "EC": 14, "AC": 33, }
        this.state.itemPool.forEach(({item, count, upTo}) => { json.item_pool[item] = upTo ? [count, upTo] : [count] })
        json.tracking = this.state.tracking
        if(this.state.tracking && this.state.players > 1) {
            json.sync_gen=f(this.state.coopGenMode)
            json.sync_mode=f(this.state.coopGameMode)
            json.dedup_shared = this.state.dedupShared
            if(this.state.coopGameMode === "Co-op")
                json.sync_shared = this.state.shared.map(s => f(s))
            if(this.state.coopGenMode === "Cloned Seeds" && this.state.hints)
                json.sync_hints = true
            if(!this.state.dedupShared)
                json.teams={1: [...Array(this.state.players).keys()].map(x=>x+1)}
            else if(this.state.teamStr !== "" && this.teamStrValid()) {
                let teams = this.state.teamStr.split("|");
                let i = 1;
                json.teams={}
                teams.forEach(team => json.teams[i++] = team.split(",").map(p => parseInt(p, 10)))
            }
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
            metaUpdate.goalModes = metaUpdate.variations.filter(v => ["ForceTrees", "WorldTour", "ForceMaps", "WarmthFrags", "Bingo"].includes(v)) || ["None"]
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
                let redir = `/bingo/board?game_id=${res.gameId}&fromGen=1&seed=${res.seed}`
                if(res.flagLine.includes("mode=Shared"))
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
        let variationButtons = Object.keys(VAR_NAMES).filter(x => !["Entrance", "NonProgressMapStones", "BonusPickups", "StompTriggers", 
                                                                     "ForceTrees", "WorldTour", "ForceMaps", "WarmthFrags", "Hard", "Bingo"].includes(x)).map(v=> {
            let name = VAR_NAMES[v];
            return (
            <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", v)} className="p-2">
                <Button block color="primary" outline={!this.state.variations.includes(v)} onClick={this.onVar(v)}>{name}</Button>
            </Col>
            )
        })

        // Legacy Killplane is incompatible with Open World. 
        //It also sees no use, so it will be removed soon(tm)
        // variationButtons.push((
        //     (
        //     <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", "StompTriggers")} className="p-2">
        //         <Button block outline={!this.state.variations.includes("StompTriggers")} disabled={(() => {
        //             if(this.state.variations.includes("OpenWorld")) {
        //                 if(this.state.variations.includes("StompTriggers"))
        //                     this.onVar("StompTriggers")()
        //                 return true;
        //             }
        //             return false;
        //         })()} onClick={this.onVar("StompTriggers")}>{VAR_NAMES["StompTriggers"]}</Button>
        //     </Col>
        //     )
        // ))
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
            let {inputPlayerCount, gameId, seedIsBingo, paramId, flagLine, spoilers, inputSeed} = this.state
            let raw = flagLine.split('|');
            let seedStr = raw.pop();
            // let {shared, unshared} = raw.join("").split(",").reduce((acc, curr) => (curr.startsWith("mode=") || curr.startsWith("shared=")) ? 
            //         {shared: acc.shared.concat(curr), unshared: acc.unshared} : {shared: acc.shared, unshared: acc.unshared.concat(curr)}, {shared: [], unshared: []})
            
            // let sharedFlags = shared.length > 0 ? (<Row><Col><span className="align-middle">Sync: {shared.join(", ")}</span></Col></Row>) : null
            // let flags = unshared.join(", ");
            let flagCols = raw.join("").split(",").map(flag => (<Col xs="auto" className="text-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("flags", flag)}><span class="ml-auto mr-auto align-middle">{flag}</span></Col>))

            let mapUrl = "/tracker/game/"+gameId+"/map";
            
            let playerRows = [...Array(inputPlayerCount).keys()].map(p => {
                p++;
                let seedParams = [];
                if(gameId > 0)
                    seedParams.push(`game_id=${gameId}`)
                let seedUrl = "/generator/seed/"+paramId
                let spoilerUrl = "/generator/spoiler/"+paramId
                let downloadSpoilerUrl = spoilerUrl + "?download=1"
                if(inputPlayerCount > 1)
                {
                    seedParams.push("player_id="+p);
                    spoilerUrl += "?player_id="+p;
                    downloadSpoilerUrl += "&player_id="+p;
                }
                let mainButtonText = "Download Seed"
                let mainButtonHelp = "downloadButton"+this.multi()
                seedUrl += "?" + seedParams.join("&")
                if(seedIsBingo) {
                    seedUrl = `/bingo/board?game_id=${gameId}&fromGen=1&seed=${inputSeed}`
                    if(inputPlayerCount > 1) {
                        seedUrl += `&teamMax=${inputPlayerCount}`
                    }
                    mainButtonText = `Open Bingo Board`
                    mainButtonHelp = "openBingoBoard"
                }
                return (
                    <Row className="align-content-center p-1 border-bottom">
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
                        <Col xs="3" className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", this.state.spoilers ? "spoilerButton" : "noSpoilers")}>
                            <Button color={spoilers ? "primary" : "secondary"} disabled={!spoilers} href={spoilerUrl} target="_blank" block >View Spoiler</Button>
                        </Col>
                        <Col xs="3" className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", this.state.spoilers ? "spoilerDownload" : "noSpoilers")}>
                            <Button color={spoilers ? "primary" : "secondary"} disabled={!spoilers} href={downloadSpoilerUrl} target="_blank" block >Save Spoiler</Button>
                        </Col>
                    </Row>
                )
            })
            let trackedInfo = gameId > 0 ? (
                  <Row className="p-1 pt-3 align-items-center border-dark border-top">
                    <Col xs="3" className="text-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "tracking")}>
                        Tracking:
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
        <Col xs="3" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicPaths",  "casual-core")}  className="p-1">
                <Button block disabled={true} className="text-capitalize">Casual-Core</Button>
        </Col>
        )].concat(optional_paths.map(path=> (
            <Col xs="3" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicPaths", path)}  className="p-1">
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

    getQuickstartModal = ({inputStyle}) => {
        return (
                <Modal size="lg" isOpen={this.state.quickstartOpen} backdrop={"static"} className={"modal-dialog-centered"} toggle={this.closeQuickstart}>
                  <ModalHeader style={inputStyle} toggle={this.closeQuickstart} centered>Welcome to the Ori DE Randomizer!</ModalHeader>
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
                              Join the Ori <a target='_blank' rel='noopener noreferrer' href="https://discord.gg/jeAnNpT">discord</a>. 
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
                    <Button color="secondary" onClick={this.closeQuickstart}>Close</Button>
                  </ModalFooter>
                </Modal>
        )
    }

    constructor(props) {
        super(props);
        let user = get_param("user");
        let url = new URL(window.document.location.href);
        let paramId = url.searchParams.get("param_id");
        let quickstartOpen = window.document.location.href.includes("/quickstart");
        let gameId = parseInt(url.searchParams.get("game_id") || -1, 10);
        let seedTabExists = (paramId !== null);
        if(seedTabExists)
        {
            if(gameId > 0)
                doNetRequest(`/generator/metadata/${paramId}/${gameId}`,this.acceptMetadata);
            else
                doNetRequest(`/generator/metadata/${paramId}`,this.acceptMetadata);

        }
        let activeTab = seedTabExists ? 'seed' : 'variations';
        this.state = {user: user, activeTab: activeTab, coopGenMode: "Cloned Seeds", coopGameMode: "Co-op", players: 1, tracking: true, variations: ["ForceTrees"], gameId: gameId, itemPool: get_pool("Standard"),
                     paths: presets["standard"], keyMode: "Clues", oldKeyMode: "Clues", pathMode: "standard", pathDiff: "Normal", helpParams: getHelpContent("none", null), goalModes: ["ForceTrees"], selectedPool: "Standard",
                     seed: "", fillAlg: "Balanced", shared: ["Skills", "Teleporters", "World Events", "Upgrades", "Misc"], hints: true, helpcat: "", helpopt: "", quickstartOpen: quickstartOpen, dedupShared: false,
                     expPool: 10000, lastHelp: new Date(), seedIsGenerating: seedTabExists, cellFreq: cellFreqPresets("standard"), fragCount: 30, fragReq: 20, relicCount: 8, loader: get_random_loader(),
                     paramId: paramId, seedTabExists: seedTabExists, reopenUrl: "", teamStr: "", flagLine: "", fass: {},  goalModesOpen: false, spoilers: true, seedIsBingo: false};
        if(url.searchParams.has("fromBingo")) {
            this.state.goalModes = ["Bingo"]
            this.state.variations = ["Bingo", "OpenWorld"]
            this.state.itemPool = get_pool("Extra Bonus")
            this.state.selectedPool = "Extra Bonus"
            this.updateUrl()
        }

    }
        
    closeQuickstart = () => {
         window.history.replaceState('',window.document.title, window.document.URL.split("/quickstart")[0]);
         this.setState({quickstartOpen: false})
    }

    onTab = (tabName) => () => this.setState({activeTab: tabName})
    onFass = (l, i) => this.setState(prevState => {
        let new_fass = prevState.fass;
        new_fass[l] = i;
        return {fass: new_fass}
    })
    onPath = (p) => () => this.setState({paths: this.state.paths.includes(p) ? this.state.paths.filter(x => x !== p) : this.state.paths.concat(p)}, () => this.setState(p => {return {pathMode: get_preset(p.paths)}}))
    onSType = (s) => () => this.state.shared.includes(s) ? this.setState({shared: this.state.shared.filter(x => x !== s)}) : this.setState({shared: this.state.shared.concat(s)})    
    onVar = (v) => () =>  this.state.variations.includes(v) ? this.setState({variations: this.state.variations.filter(x => x !== v)}) : this.setState({variations: this.state.variations.concat(v)})
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
            console.log("vars did not include previous goalMode?");
        if(mode !== "None" && !vars.includes(mode))
            vars = vars.concat(mode)
        else
            console.log("vars already included goalMode?")
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
        let {pathMode, goalModes, keyMode, helpParams, goalModesOpen, seedTabExists, helpcat, activeTab, seed, tracking, seedIsGenerating} = this.state;
        let s = getComputedStyle(document.body);
        let styles = {inputStyle: {'borderColor': s.getPropertyValue('--dark'), 'backgroundColor': s.getPropertyValue("background-color"), 'color': s.getPropertyValue("color")}, menuStyle: {}}

        // if(dark) {
        //     pageStyle = 'body { background-color: #333; color: white }';
        //     styles.inputStyle = {'backgroundColor': '#333', 'color': 'white'}
        //     styles.menuStyle.backgroundColor = "#666"
        // } else {
        //    pageStyle = 'body { background-color: white; color: black }';
        // }  

        let pathModeOptions = Object.keys(presets).map(mode => (
            <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicModes", mode)} className="text-capitalize" active={mode===pathMode.toLowerCase()} onClick={this.onMode(mode)}>{mode}</DropdownItem>
        ))
        let keyModeOptions = keymode_options.map(mode => (
            <DropdownItem active={mode===keyMode} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("keyModes", mode)} onClick={this.onKeyMode(mode)}>{mode}</DropdownItem>
        ))
        let validGoalModes = ["None", "ForceTrees", "WorldTour", "ForceMaps", "WarmthFrags"]
        if(tracking) 
            validGoalModes.push("Bingo")

        let goalModeOptions = goalModes.length === 1 ? validGoalModes.map(mode => (
            <DropdownItem active={mode===goalModes[0]} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("goalModes", mode)} onClick={this.onGoalMode(mode)}>{VAR_NAMES[mode] || mode}</DropdownItem>
        )) : null

        helpParams.padding = goalModesOpen ? "pt-5" : ""
        let lockTracking = goalModes.includes("Bingo") || this.state.players > 1
        let multiplayerTab = this.getMultiplayerTab(styles)
        let advancedTab = this.getAdvancedTab(styles)
        let poolTab = this.getItemPoolTab(styles)
        let seedTab = this.getSeedTab()
        let variationsTab = this.getVariationsTab()
        let pathsTab = this.getPathsTab()
        
        let seedNav = seedTabExists ? (
            <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "seedTab")}>
                <NavLink active={activeTab === 'seed'} onClick={this.onTab('seed')}>
                    Seed
                </NavLink>
            </NavItem>
        ) : null;
        let modal = this.getQuickstartModal(styles);
        let goalModeMulti = goalModes.length > 1;

        return (
         <Container className="pl-4 pr-4 pb-4 pt-2 mt-5">
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
                                <DropdownMenu style={styles.menuStyle}>
                                    {goalModeOptions}
                                </DropdownMenu>
                            </Dropdown>
                        </Col>
                    </Row>
                </Col>
            </Row>
            <Row className="justify-content-center p-2">
            <Col>
                <Nav tabs>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "variations")}>
                        <NavLink active={activeTab === 'variations'} onClick={this.onTab('variations')}>
                        Variations
                        </NavLink>
                    </NavItem>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "logicPaths")}>
                        <NavLink active={activeTab === 'logic paths'} onClick={this.onTab('logic paths')}>
                        Logic Paths
                        </NavLink>
                    </NavItem>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "customPool")}>
                        <NavLink active={activeTab === 'item pool'} onClick={this.onTab('item pool')}>
                        Item Pool
                        </NavLink>
                    </NavItem>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "multiplayer")}>
                        <NavLink active={activeTab === 'multiplayer'} onClick={this.onTab('multiplayer')}>
                        Multiplayer Options
                        </NavLink>
                    </NavItem>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "advanced")}>
                        <NavLink active={activeTab === 'advanced'} onClick={() => { dev && console.log(this.state); this.onTab('advanced')()}}>
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
                    <Row>
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