import React from 'react';
import  {DropdownToggle, DropdownMenu, Dropdown, DropdownItem, Nav, NavLink, NavItem, Collapse,  Input, UncontrolledButtonDropdown, Button, 
        Row, FormFeedback, Col, Container, TabContent, TabPane, Modal, ModalHeader, ModalBody, ModalFooter, Media} from 'reactstrap'
import {NotificationContainer, NotificationManager} from 'react-notifications';

import 'react-notifications/lib/notifications.css';
import './index.css';

import {getHelpContent, HelpBox} from "./helpbox.js"
import {get_param, presets, get_preset, get_flag, player_icons, doNetRequest, get_random_loader, PickupSelect} from './common.js';
import SiteBar from "./SiteBar.js"

const dev = window.document.URL.includes("devshell")
const keymode_options = ["None", "Shards", "Limitkeys", "Clues", "Free"];

const textStyle = {color: "black", textAlign: "center"}

const variations = {
    ForceTrees: "Force Trees",
    Starved: "Starved",
    NonProgressMapStones: "Discrete Mapstones",
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
}
const cellFreqPresets = (preset) => preset === "casual" ? 20 : (preset === "standard" ? 40 : 256)
const optional_paths = ['casual-dboost', 'standard-core', 'standard-dboost', 'standard-lure', 'standard-abilities', 'expert-core', 'expert-dboost', 'expert-lure', 'expert-abilities', 'dbash', 'master-core', 'master-dboost', 'master-lure', 'master-abilities', 'gjump', 'glitched', 'timed-level', 'insane']
const varPaths = {"master": ["Starved"]}
const diffPaths = {"glitched": "Hard", "master": "Hard"}
const disabledPaths = {
                    "Hard": ["standard-dboost", "expert-dboost", "master-dboost"], 
                    "0XP": ["glitched", "standard-abilities", "expert-abilities", "master-abilities", "master-dboost", "timed-level", "insane"], 
                    "OHKO": ["standard-dboost", "expert-dboost", "master-dboost", "glitched", "master-lure"]
                    }
const revDisabledPaths = {}
Object.keys(disabledPaths).forEach(v => disabledPaths[v].forEach(path => revDisabledPaths.hasOwnProperty(path) ? revDisabledPaths[path].push(v) : revDisabledPaths[path] = [v]))


export default class MainPage extends React.Component {
    helpEnter = (category, option, timeout=250) => () => {clearTimeout(this.state.helpTimeout) ; this.setState({helpTimeout: setTimeout(this.help(category, option), timeout)})}
    helpLeave = () => clearTimeout(this.state.helpTimeout) 
    help = (category, option) => () => this.setState({helpcat: category, helpopt: option, helpParams: getHelpContent(category, option)})
    
    
    getAdvancedTab = () => {
        let [leftCol, rightCol] = [4, 7]
        let pathDiffOptions = ["Easy", "Normal", "Hard"].map(mode => (
            <DropdownItem active={mode===this.state.pathDiff} onClick={()=> this.setState({pathDiff: mode})}>{mode}</DropdownItem>
        ))
        const starting_pickups = {"Spawn With:": 2, "First Pickup:": 919772, "Second Pickup:": -1560272, "Third Pickup:": 799776, "Fourth Pickup:": -120208}
        let fass_rows = Object.keys(starting_pickups).map(name => {
            let coord = starting_pickups[name];
            return (
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "preplacement")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span class="align-middle">{name}</span>
                        </Col><Col xs={rightCol}>
                            <PickupSelect updater={(code, _) => this.onFass(coord, code)}/> 
                        </Col>
                    </Row>
            )   
        })
        let goalCol = (v) => (
            <Col xs="4" onMouseLeave={this.helpEnter("advanced", "goalModes")} onMouseEnter={this.helpEnter("goalModes", v)} className="p-2">
                <Button block outline={!this.state.variations.includes(v)} onClick={this.onGoalModeAdvanced(v)}>{variations[v]}</Button>
            </Col>
        )
        return (
                <TabPane tabId="advanced">
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "goalModes")} className="p-1 justify-content-center">
                        {goalCol("WorldTour")}
                        {goalCol("WarmthFrags")}
                    </Row>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "goalModes")} className="p-1 justify-content-center border-bottom">
                        {goalCol("ForceTrees")}
                        {goalCol("ForceMaps")}
                    </Row>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "expPool")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span class="align-middle">Exp Pool</span>
                        </Col><Col xs={rightCol}>
                            <Input type="number" value={this.state.expPool} invalid={this.state.expPool < 100} onChange={(e) => this.setState({expPool: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip>Experience Pool must be at least 100</FormFeedback>
                        </Col>
                    </Row>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "sense")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span class="align-middle">Sense Triggers</span>
                        </Col><Col xs={rightCol}>
                            <Input type="text" value={this.state.senseData}  onChange={(e) => this.setState({senseData: e.target.value})}/> 
                        </Col>
                    </Row>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fillAlg")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span class="align-middle">Fill Algorithm</span>
                        </Col><Col xs={rightCol}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" caret block> {this.state.fillAlg} </DropdownToggle>
                                <DropdownMenu>
                                    <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fillAlgClassic")}  active={"Classic" ===this.state.fillAlg} onClick={()=> this.setState({fillAlg: "Classic"})}>Classic</DropdownItem>
                                    <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fillAlgBalanced")} active={"Balanced"===this.state.fillAlg} onClick={()=> this.setState({fillAlg: "Balanced"})}>Balanced</DropdownItem>
                                </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "pathDiff")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span class="align-middle">Path Difficulty</span>
                        </Col>
                        <Col xs={rightCol}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" caret block> {this.state.pathDiff} </DropdownToggle>
                                <DropdownMenu> {pathDiffOptions} </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "cellFreq")} className="p-1 justify-content-center">
                        <Col xs={leftCol} className="text-center pt-1 border">
                            <span class="align-middle">Forced Cell Frequency</span>
                        </Col><Col xs={rightCol}>
                            <Input type="number" value={this.state.cellFreq} invalid={this.state.cellFreq < 3} onChange={(e) => this.setState({cellFreq: parseInt(e.target.value, 10)})}/> 
                            <FormFeedback tooltip>Forced Cell Frequency must be at least 3</FormFeedback>
                        </Col>
                    </Row>
                    {fass_rows}                    
                    <Collapse isOpen={this.state.variations.includes("WorldTour")}>
                        <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "relicCount")} className="p-1 justify-content-center">
                            <Col xs={leftCol} className="text-center pt-1 border">
                                <span class="align-middle">Relic Count</span>
                            </Col><Col xs={rightCol}>
                                <Input type="number" value={this.state.relicCount} invalid={this.state.relicCount > 11 || this.state.relicCount < 1} onChange={(e) => this.setState({relicCount: parseInt(e.target.value, 10)})}/> 
                                <FormFeedback tooltip>Relic count must be greater than 0 and less than 12</FormFeedback>
                            </Col>
                        </Row>
                    </Collapse>
                    <Collapse isOpen={this.state.variations.includes("WarmthFrags")}>
                        <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fragCount")} className="p-1 justify-content-center">
                            <Col xs={leftCol} className="text-center pt-1 border">
                                <span class="align-middle">Fragment Count</span>
                            </Col><Col xs={rightCol}>
                                <Input type="number" value={this.state.fragCount} invalid={this.state.fragCount > 60 || this.state.fragCount < 1} onChange={(e) => this.setState({fragCount: parseInt(e.target.value, 10)})}/> 
                                <FormFeedback tooltip>Frag Count must be between 1 and 60</FormFeedback>
                            </Col>
                        </Row>
                        <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("advanced", "fragRequired")} className="p-1 justify-content-center">
                            <Col xs={leftCol} className="text-center pt-1 border">
                                <span class="align-middle">Fragments Required</span>
                            </Col><Col xs={rightCol}>
                                <Input type="number" value={this.state.fragReq} invalid={this.state.fragCount < this.state.fragReq || this.state.fragReq <= 0} onChange={e => this.setState({fragReq: parseInt(e.target.value, 10)})}/> 
                                <FormFeedback tooltip>Fragments Required must be between 0 and Fragment Count ({this.state.fragCount})</FormFeedback>
                            </Col>
                        </Row>
                    </Collapse>
                </TabPane>
        )
    }
    getMultiplayerTab = () => {
        let multiplayerButtons = ["Skills", "Teleporters", "Upgrades", "World Events", "Misc"].map(stype => (
            <Col xs="4" key={`share-${stype}`} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("Shared Item Categories", stype)} className="p-2">
                <Button block outline={!this.state.shared.includes(stype)} onClick={this.onSType(stype)}>Share {stype}</Button>
            </Col>
        ))
        
        let playerNumValid = this.state.tracking && this.state.players > 0;
        let playerNumFeedback = this.state.tracking ? (this.state.players > 0 ? null : (
            <FormFeedback tooltip>Need at least one player...</FormFeedback>
        )) : (
            <FormFeedback tooltip>Multiplayer modes require web tracking to be enabled</FormFeedback>
        )
        return (
             <TabPane tabId="multiplayer">
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "playerCount")}  className="p-1 justify-content-center">
                    <Col xs="4" className="text-center pt-1 border">
                        <span class="align-middle">Players</span>
                    </Col><Col xs="4">
                        <Input type="number" value={this.state.players} disabled={!this.state.tracking} invalid={!playerNumValid} onChange={(e) => this.setState({players: parseInt(e.target.value, 10)})}/> 
                        {playerNumFeedback }
                    </Col>
                </Row>
                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "multiGameType")} className="p-1 justify-content-center">
                    <Col xs="4" className="text-center pt-1 border">
                        <span class="align-middle">Multiplayer Game Type</span>
                    </Col><Col xs="4">
                        <UncontrolledButtonDropdown className="w-100" >
                            <DropdownToggle disabled={this.state.players < 2} color={this.state.players > 1 ? "primary" : "secondary"} caret block> {this.state.coopGameMode} </DropdownToggle>
                            <DropdownMenu>
                                <DropdownItem active={"Race"===this.state.coopGameMode} onClick={()=> this.setState({coopGameMode: "Race"})}>Race</DropdownItem>
                                <DropdownItem active={"Co-op"===this.state.coopGameMode} onClick={()=> this.setState({coopGameMode: "Co-op"})}>Co-op</DropdownItem>
                                <DropdownItem active={"SplitShards"===this.state.coopGameMode} disabled={this.state.keyMode !== "Shards"} onClick={()=> this.setState({coopGameMode: "SplitShards"})}>Split Shards</DropdownItem>
                            </DropdownMenu>
                        </UncontrolledButtonDropdown>
                    </Col>
                </Row>
                <Collapse isOpen={this.state.players > 1 && this.state.coopGameMode === "Co-op"}>
                    <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "syncSeedType")} className="p-1 justify-content-center">
                        <Col xs="4" className="text-center pt-1 border">
                            <span class="align-middle">Seed Generation Mode</span>
                        </Col><Col onMouseLeave={this.helpEnter("multiplayerOptions", "syncSeedType")} onMouseEnter={this.helpEnter("multiplayerOptions", this.state.coopGenMode)} xs="4">
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle disabled={this.state.players < 2} color={this.state.players > 1 ? "primary" : "secondary"} caret block> {this.state.coopGenMode} </DropdownToggle>
                                <DropdownMenu>
                                    <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "Cloned Seeds")}  active={"Cloned Seeds"===this.state.coopGenMode} onClick={()=> this.setState({coopGenMode: "Cloned Seeds"})}>Cloned Seeds</DropdownItem>
                                    <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("multiplayerOptions", "Seperate Seeds")}  active={"Seperate Seeds"===this.state.coopGenMode} onClick={()=> this.setState({coopGenMode: "Seperate Seeds"})}>Seperate Seeds</DropdownItem>
                                </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                    <Row className="p-2">
                        {multiplayerButtons}
                        <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("Shared Item Categories", "Hints")} className="p-2">
                            <Button block outline={!this.state.hints} disabled={this.state.coopGenMode!=="Cloned Seeds"} onClick={() => this.setState({hints: !this.state.hints})}>Show Hints</Button>
                        </Col>
                    </Row>
                </Collapse>
                <Collapse isOpen={this.state.user !== ""}>
                    <Row className="p-1 justify-content-center">
                        <Col xs="4" className="text-center pt-1 border">
                            <span class="align-middle">SyncId</span>
                        </Col><Col xs="4">
                            <Input type="number" value={this.state.syncId} invalid={!(this.state.syncId === "" || this.state.syncId > 0)} onChange={(e) => this.setState({syncId: parseInt(e.target.value, 10)})}/>
                            <FormFeedback tooltip>syncId must be positive</FormFeedback>
                        </Col>
                    </Row>
                    <Collapse isOpen={this.state.coopGenMode==="Cloned Seeds" && this.state.players > 1 && this.state.coopGameMode === "Co-op"}>
                        <Row className="p-1 justify-content-center">
                            <Col xs="4" className="text-center pt-1 border">
                                <span class="align-middle">Teams</span>
                            </Col><Col xs="4">
                                <Input type="text" value={this.state.teamStr} invalid={!this.teamStrValid()} onChange={(e) => this.setState({teamStr: e.target.value})}/>
                                <FormFeedback tooltip>Team format: 1,2|3,4|5,6. Each player must appear once.</FormFeedback>
                            </Col>
                        </Row>
                    </Collapse>
                </Collapse>
            </TabPane>
        )
    }
    teamStrValid = () => {
        let teamStr = this.state.teamStr;
        if(teamStr === "") return true;
        let teams = teamStr.split("|");
        let retval = true;
        let players = [...Array(this.state.players).keys()].map(i => i+1)
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
        let f = (p) => pMap.hasOwnProperty(p) ? pMap[p] : p
        let urlParams = []
        urlParams.push("key_mode="+f(this.state.keyMode))
        if(this.state.pathDiff !== "Normal")
            urlParams.push("path_diff="+this.state.pathDiff)
        urlParams.push("gen_mode="+this.state.fillAlg)
        this.state.variations.forEach(v => urlParams.push("var="+v))
        this.state.paths.forEach(p => urlParams.push("path="+p))
        if(this.state.senseData)
            urlParams.push("sense="+this.state.senseData)
        urlParams.push("exp_pool="+this.state.expPool)
        urlParams.push("cell_freq="+this.state.cellFreq)
        if(this.state.variations.includes("WarmthFrags"))
        {
            urlParams.push("frags="+this.state.fragCount)
            urlParams.push("frags_req="+this.state.fragReq)
        }
        if(this.state.variations.includes("WorldTour"))
        {
            urlParams.push("relics="+this.state.relicCount)
        }
        urlParams.push("players="+this.state.players)
        let fass = []
        Object.keys(this.state.fass).forEach(loc => {
            if(this.state.fass[loc]) {
                let item = this.state.fass[loc].replace("|","");
                if(["AC", "EC", "KS", "HC", "MS"].includes(item.substr(0,2)))
                    item = item.substr(0,2) // we're sanitizing inputs here i guess
                fass.push(loc+":"+item); 
            }
        })
        if(fass.length > 0)
            urlParams.push("fass="+fass.join("|"))
        if(this.state.tracking)
        {
            if(this.state.syncId !== "")
                urlParams.push("sync_id="+this.state.syncId)
            if(this.state.players > 1) {
                urlParams.push("sync_gen="+f(this.state.coopGenMode))
                urlParams.push("sync_mode="+f(this.state.coopGameMode))
                if(this.state.coopGameMode === "Co-op")
                    this.state.shared.forEach(s => urlParams.push("sync_shared="+f(s)))
                if(this.state.coopGenMode === "Cloned Seeds" && this.state.hints)
                    urlParams.push("sync_hints=on")
                if(this.state.teamStr !== "") {
                    urlParams.push("teams="+this.state.teamStr)
                }
            }
        } else {
            urlParams.push("tracking=Disabled")
        }
        let seed = this.state.seed || Math.round(Math.random() * 1000000000);
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
        urlParams.push("seed=" + seed);
        let url = "/generator/build?" + urlParams.join("&")
        this.helpEnter("general", "seedBuilding" + this.multi())()
        this.setState({seedIsGenerating: true, seedTabExists: true, loader: get_random_loader(), activeTab: "seed"}, () => doNetRequest(url, this.seedBuildCallback))
    }
    
    acceptMetadata = ({status, responseText}) => {
        if(status !== 200)
        {
            NotificationManager.error("Failed to recieve seed metadata", "Seed could not be retrieved!", 5000)
            this.setState({seedTabExists: false, activeTab: 'variations'}, this.updateUrl)
        } else {
            let res = JSON.parse(responseText)
            let metaUpdate = {inputPlayerCount: res["playerCount"], inputFlagLine: res["flagLine"], spoilers: res.spoilers}
            if(res.hasOwnProperty("gameId"))
            {
                metaUpdate.gameId = res["gameId"]
            }
            this.setState(metaUpdate, this.updateUrl)
        }
    }

    updateUrl = () => {
        let {paramId, gameId, seedTabExists, seedIsGenerating} = this.state;
        let url = window.document.URL.split("?")[0];
        if(!seedIsGenerating && seedTabExists)
        {
            url += `?param_id=${paramId}`;
            if(gameId && gameId > 0)
                url += `&game_id=${gameId}`
        }
        window.history.replaceState('',window.document.title, url);
    }
    
    seedBuildCallback = ({status, responseText}) => {
        if(status !== 200)
        {
            NotificationManager.error("Failed to generate seed!", "Seed generation failure!", 5000)
            this.setState({seedIsGenerating: false, seedTabExists: false, activeTab: 'variations'}, this.updateUrl)
            return
        } else {
            let res = JSON.parse(responseText)
            this.helpEnter("general", "seedBuilt" + this.multi())()
            this.setState({
                paramId: res.paramId, seedIsGenerating: false, inputPlayerCount: res.playerCount, 
                inputFlagLine: res.flagLine, gameId: res.gameId
            }, this.updateUrl)
        }
    }
    getVariationsTab = () => {
        let variationButtons = Object.keys(variations).filter(x => !["Entrance", "NonProgressMapStones", "BonusPickups", "StompTriggers", 
                                                                     "ForceTrees", "WorldTour", "ForceMaps", "WarmthFrags"].includes(x)).map(v=> {
            let name = variations[v];
            return (
            <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", v)} className="p-2">
                <Button block outline={!this.state.variations.includes(v)} onClick={this.onVar(v)}>{name}</Button>
            </Col>
            )
        })
        // Bonus Pickups is incompatible with Hard.
        variationButtons.push((
            (
            <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", "BonusPickups")} className="p-2">
                <Button block outline={!this.state.variations.includes("BonusPickups")} disabled={(() => {
                    if(this.state.variations.includes("Hard")) {
                        if(this.state.variations.includes("BonusPickups"))
                            this.onVar("BonusPickups")()
                        return true;
                    }
                    return false;
                })()} onClick={this.onVar("BonusPickups")}>{variations["BonusPickups"]}</Button>
            </Col>
            )
        ))
        // Discrete Mapstones requires Strict Mapstones.
        variationButtons.push((
            (
            <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", "NonProgressMapStones")} className="p-2">
                <Button block outline={!this.state.variations.includes("NonProgressMapStones")} disabled={(() => {
                    if(!this.state.variations.includes("StrictMapstones")) {
                        if(this.state.variations.includes("NonProgressMapStones"))
                            this.onVar("NonProgressMapStones")()
                        return true;
                    }
                    return false;
                })()} onClick={this.onVar("NonProgressMapStones")}>{variations["NonProgressMapStones"]}</Button>
            </Col>
            )
        ))
        // Legacy Killplane is incompatible with Open World.
        variationButtons.push((
            (
            <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", "StompTriggers")} className="p-2">
                <Button block outline={!this.state.variations.includes("StompTriggers")} disabled={(() => {
                    if(this.state.variations.includes("OpenWorld")) {
                        if(this.state.variations.includes("StompTriggers"))
                            this.onVar("StompTriggers")()
                        return true;
                    }
                    return false;
                })()} onClick={this.onVar("StompTriggers")}>{variations["StompTriggers"]}</Button>
            </Col>
            )
        ))
        return (
            <TabPane tabId="variations">
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
                <TabPane tabId='seed' onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "seedBuilding" + this.multi())}>
                    <Row className="p-2 justify-content-center align-items-center">
                        <Col xs="auto" className="align-items-center justify-content-center p-2">{this.state.loader}</Col>
                    </Row>
                </TabPane>
            )
        }
        else 
        {
            let raw = this.state.inputFlagLine.split('|');
            let seedStr = raw.pop();
            // let {shared, unshared} = raw.join("").split(",").reduce((acc, curr) => (curr.startsWith("mode=") || curr.startsWith("shared=")) ? 
            //         {shared: acc.shared.concat(curr), unshared: acc.unshared} : {shared: acc.shared, unshared: acc.unshared.concat(curr)}, {shared: [], unshared: []})
            
            // let sharedFlags = shared.length > 0 ? (<Row><Col><span class="align-middle">Sync: {shared.join(", ")}</span></Col></Row>) : null
            // let flags = unshared.join(", ");
            let flagCols = raw.join("").split(",").map(flag => (<Col xs="auto" className="text-center" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("flags", flag)}><span class="ml-auto mr-auto align-middle">{flag}</span></Col>))

            let mapUrl = "/tracker/game/"+this.state.gameId+"/map";
            
            let playerRows = [...Array(this.state.inputPlayerCount).keys()].map(p => {
                p++;
                let seedParams = [];
                if(this.state.gameId > 0)
                    seedParams.push(`game_id=${this.state.gameId}`)
                let seedUrl = "/generator/seed/"+this.state.paramId
                let spoilerUrl = "/generator/spoiler/"+this.state.paramId
                let downloadSpoilerUrl = spoilerUrl + "?download=1"
                if(this.state.inputPlayerCount > 1)
                {
                    seedParams.push("player_id="+p);
                    spoilerUrl += "?player_id="+p;
                    downloadSpoilerUrl += "&player_id="+p;
                }
                seedUrl += "?" + seedParams.join("&")
                return (
                    <Row className="align-content-center p-1 border-bottom">
                        <Col xs="3" className="pt-1 border" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "playerPanel"+this.multi())}>
                            <Row className="align-content-center"><Col xs="3">
                                <Media object style={{width: "25px", height: "25px"}} src={player_icons(p,false)} alt={"Icon for player "+p} />
                            </Col><Col>
                                <span class="align-middle">Player {p}</span>
                            </Col></Row>
                        </Col>
                        <Col xs="3" className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", "downloadButton"+this.multi())}>
                            <Button color="primary" block target="_blank" href={seedUrl}>Download Seed</Button>
                        </Col>
                        <Col xs="3" className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", this.state.spoilers ? "spoilerButton" : "noSpoilers")}>
                            <Button color={this.state.spoilers ? "primary" : "secondary"} disabled={!this.state.spoilers} href={spoilerUrl} target="_blank" block >View Spoiler</Button>
                        </Col>
                        <Col xs="3" className="pl-1 pr-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("seedTab", this.state.spoilers ? "spoilerDownload" : "noSpoilers")}>
                            <Button color={this.state.spoilers ? "primary" : "secondary"} disabled={!this.state.spoilers} href={downloadSpoilerUrl} target="_blank" block >Save Spoiler</Button>
                        </Col>
                    </Row>
                )
            })
            let trackedInfo = this.state.gameId > 0 ? (
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
                <TabPane tabId='seed'>
                      <Row className="justify-content-center">
                        <span class="align-middle">
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
                <Button block outline={!this.state.paths.includes(path)} disabled={this.pathDisabled(path)} className="text-capitalize" onClick={this.onPath(path)}>{path}</Button>
            </Col>
        )))    
        return (
            <TabPane tabId="logic paths">
                <Row className="p-2">
                    {pathButtons}
                </Row>
            </TabPane>
        )
    }

    getQuickstartModal = () => {
        return (
                <Modal size="lg" isOpen={this.state.quickstartOpen} backdrop={"static"} className={"modal-dialog-centered"} toggle={this.closeQuickstart}>
                  <ModalHeader toggle={this.closeQuickstart} centered>Welcome to the Ori DE Randomizer!</ModalHeader>
                  <ModalBody>
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
                  <ModalFooter>
                    <Button color="secondary" onClick={this.closeQuickstart}>Close</Button>
                  </ModalFooter>
                </Modal>
        )
    }

    constructor(props) {
        super(props);
        let user = get_param("user");
        let dllTime = get_param("dll_last_update")
        let url = new URL(window.document.location.href);
        let paramId = url.searchParams.get("param_id");
        let quickstartOpen = window.document.location.href.includes("/quickstart");
        let gameId = parseInt(url.searchParams.get("game_id") || -1, 10);
        let dark = get_flag("dark") || url.searchParams.has("dark")
        let seedTabExists = (paramId !== null);
        if(seedTabExists)
            doNetRequest("/generator/metadata/"+paramId,this.acceptMetadata);
        let activeTab = seedTabExists ? 'seed' : 'variations';
        this.state = {user: user, activeTab: activeTab, coopGenMode: "Cloned Seeds", coopGameMode: "Co-op", players: 1, tracking: true, dllTime: dllTime, variations: ["ForceTrees"], gameId: gameId,
                     paths: presets["standard"], keyMode: "Clues", oldKeyMode: "Clues", pathMode: "standard", pathDiff: "Normal", helpParams: getHelpContent("none", null), goalModes: ["ForceTrees"],
                     customSyncId: "", seed: "", fillAlg: "Balanced", shared: ["Skills", "Teleporters", "World Events"], hints: true, helpcat: "", helpopt: "", quickstartOpen: quickstartOpen,
                     syncId: "", expPool: 10000, lastHelp: new Date(), seedIsGenerating: false, cellFreq: cellFreqPresets("standard"), fragCount: 30, fragReq: 20, relicCount: 8, loader: get_random_loader(),
                     paramId: paramId, seedTabExists: seedTabExists, reopenUrl: "", teamStr: "", inputFlagLine: "", fass: {},  goalModesOpen: false, spoilers: true, dark: dark};
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
        let pathModeOptions = Object.keys(presets).map(mode => (
            <DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicModes", mode)} className="text-capitalize" active={mode===this.state.pathMode.toLowerCase()} onClick={this.onMode(mode)}>{mode}</DropdownItem>
        ))
        let keyModeOptions = keymode_options.map(mode => (
            <DropdownItem active={mode===this.state.keyMode} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("keyModes", mode)} onClick={this.onKeyMode(mode)}>{mode}</DropdownItem>
        ))
        let goalModeOptions = this.state.goalModes.length === 1 ? ["None", "ForceTrees", "WorldTour", "ForceMaps", "WarmthFrags"].map(mode => (
            <DropdownItem active={mode===this.state.goalModes[0]} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("goalModes", mode)} onClick={this.onGoalMode(mode)}>{variations[mode] || mode}</DropdownItem>
        )) : null

        let helpParams = this.state.helpParams;
        helpParams.padding = this.state.goalModesOpen ? "pt-5" : ""

        let multiplayerTab = this.getMultiplayerTab()
        let advancedTab = this.getAdvancedTab()
        let seedTab = this.getSeedTab()
        let variationsTab = this.getVariationsTab()
        let pathsTab = this.getPathsTab()
        
        let seedNav = this.state.seedTabExists ? (
            <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "seedTab")}>
                <NavLink active={this.state.activeTab === 'seed'} onClick={this.onTab('seed')}>
                    Seed
                </NavLink>
            </NavItem>
        ) : null;
        let modal = this.getQuickstartModal();
        let goalModeMulti = this.state.goalModes.length > 1;
        return (
         <Container className="pl-4 pr-4 pb-4 pt-2 mt-5">
             <Row className="justify-content-center">
                 <Col>
                     {modal}
                    <NotificationContainer/>
                    <SiteBar dark={this.state.dark} user={this.state.user}/>
                </Col>
            </Row>
            <Row className="p-1">
                <Col>
                    <span>
                        <h3 style={textStyle}>Seed Generator 3.0</h3>
                    </span>
                </Col>
            </Row>
            <Row className="p-3 border">
                <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "logicModes")}>
                    <Row>
                        <Col xs="6"  className="text-center pt-1 border">
                            <span className="align-middle">Logic Mode</span>
                        </Col>
                        <Col xs="6" onMouseLeave={this.helpEnter("general", "logicModes")} onMouseEnter={this.helpEnter("logicModes", this.state.pathMode)}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" className="text-capitalize" caret block> {this.state.pathMode} </DropdownToggle>
                                <DropdownMenu> {pathModeOptions} </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "keyModes")}>
                    <Row>
                        <Col xs="6"  className="text-center pt-1 border">
                            <span class="align-middle">Key Mode</span>
                        </Col>
                        <Col xs="6" onMouseEnter={this.helpEnter("keyModes", this.state.keyMode)} onMouseLeave={this.helpEnter("general", "keyModes",(this.state.keyMode === "Clues" && this.state.helpcat === "keyModes") ? 1000 : 250 )}>
                            <UncontrolledButtonDropdown className="w-100">
                                <DropdownToggle color="primary" caret block> {this.state.keyMode} </DropdownToggle>
                                <DropdownMenu>
                                    {keyModeOptions}
                                </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                </Col>
                <Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "goalModes")}>
                    <Row>
                        <Col xs="6"  className="text-center pt-1 border">
                            <span class="align-middle">Goal Mode</span>
                        </Col>
                        <Col xs="6" onMouseLeave={this.helpEnter("general", "goalModes")} onMouseEnter={this.helpEnter("goalModes", goalModeMulti ? "Multiple" : this.state.goalModes[0])}>
                            <Dropdown disabled={goalModeMulti} isOpen={this.state.goalModesOpen} toggle={() => this.setState({goalModesOpen: !this.state.goalModesOpen})} className="w-100">
                                <DropdownToggle disabled={goalModeMulti} color={goalModeMulti ? "disabled" :"primary"} className="text-capitalize" caret={!goalModeMulti} block> 
                                  {goalModeMulti ? "Multiple" : (variations[this.state.goalModes[0]] || this.state.goalModes[0])}                                  
                                </DropdownToggle>
                                <DropdownMenu>
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
                        <NavLink active={this.state.activeTab === 'variations'} onClick={this.onTab('variations')}>
                        Variations
                        </NavLink>
                    </NavItem>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "logicPaths")}>
                        <NavLink active={this.state.activeTab === 'logic paths'} onClick={this.onTab('logic paths')}>
                        Logic Paths
                        </NavLink>
                    </NavItem>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "multiplayer")}>
                        <NavLink active={this.state.activeTab === 'multiplayer'} onClick={this.onTab('multiplayer')}>
                        Multiplayer Options
                        </NavLink>
                    </NavItem>
                    <NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "advanced")}>
                        <NavLink active={this.state.activeTab === 'advanced'} onClick={() => { dev && console.log(this.state); this.onTab('advanced')()}}>
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
                            <TabContent className="p-3 border" activeTab={this.state.activeTab}>
                                {variationsTab}
                                {pathsTab}
                                {multiplayerTab}
                                {advancedTab}
                                {seedTab}
                            </TabContent>
                        </Col>
                    </Row>
                    <Collapse isOpen={this.state.activeTab !== "seed"}>
                        <Row className="align-items-center">
                            <Col xs="6">
                                <Row className="m-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "seed")}>
                                    <Col xs="5" className="text-center pt-1 border">
                                        <span class="align-middle">Seed</span>
                                    </Col><Col xs="7">
                                        <Input type="text" value={this.state.seed} onChange={(e) => this.setState({seed: e.target.value})}/>
                                    </Col>
                                </Row><Row className="m-1" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "webTracking")}>
                                    <Col>
                                        <Button color="info" block outline={!this.state.tracking} onClick={()=>this.setState({tracking: !this.state.tracking})}>Web Tracking {this.state.tracking ? "Enabled" : "Disabled"}</Button>
                                    </Col>
                                </Row>
                            </Col>
                            <Col>
                                <Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "generate" + this.multi())}>
                                    <Col>
                                        <Button color="success" disabled={this.state.seedIsGenerating} size="lg" onClick={this.generateSeed} block>Generate Seed</Button>
                                    </Col>
                                </Row>
                            </Col>
                        </Row>
                    </Collapse>
                </Col>
                <Col>
                    <Row>
                        <HelpBox {...helpParams} />
                    </Row>
                </Col>
            </Row>
            </Container>
        )

    }
};
