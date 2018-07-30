import React from 'react';
import  {Collapse,  Navbar,  NavbarBrand, Nav,  NavItem,  NavLink, UncontrolledDropdown, Input, 
		UncontrolledButtonDropdown, DropdownToggle, DropdownMenu, DropdownItem, Button, Row, FormFeedback,
		Col, Container, TabContent, TabPane} from 'reactstrap'
import {Helmet} from 'react-helmet';
import {NotificationContainer, NotificationManager} from 'react-notifications';
import 'react-notifications/lib/notifications.css';
import './index.css';

import {getHelpContent, HelpBox} from "./helpbox.js"
import {listSwap, get_param, presets} from './shared_map.js';


const dev = window.document.URL.includes("devshell")
const base_url = dev ?  "https://8080-dot-3616814-dot-devshell.appspot.com" : "http://orirandocoopserver.appspot.com"
const keymode_options = ["None", "Shards", "Limitkeys", "Clues", "Warmth Frags"];

const textStyle = {color: "black", textAlign: "center"}
const SiteBar = ({dlltime, user}) => {
	
	let logonoff = user ? [
		(<DropdownItem href={"/plando/"+ user}> {user}'s seeds </DropdownItem>),
		(<DropdownItem href="/logout">  Logout </DropdownItem>)
	] :  (<DropdownItem href="/login"> Login </DropdownItem>) 

	return (
		<Navbar className="border border-dark p-2" expand="md">
		<NavbarBrand href="/">Ori DE Randomizer</NavbarBrand>
			<Nav className="ml-auto" navbar>
			<UncontrolledDropdown nav inNavbar>
				<DropdownToggle nav caret>
				Downloads
				</DropdownToggle>
				<DropdownMenu right>
				<DropdownItem href="https://github.com/turntekGodhead/OriDERandomizer/raw/master/Assembly-CSharp.dll">
					DLL (Last Updated {dlltime})
				</DropdownItem>
				<DropdownItem href="https://github.com/david-c-miller/OriDETracker/releases/download/v3.0-beta/OriDETracker-v3.0-beta.zip">
					Beta Tracker
				</DropdownItem>
				<DropdownItem href="/vanilla">
					Vanilla Seed
				</DropdownItem>
				</DropdownMenu>
			</UncontrolledDropdown>
			<NavItem>
				<NavLink href={"/activeGames"}>Active Games</NavLink>
			</NavItem>
			<NavItem>
				<NavLink href={"/logichelper"}>Interactive Logic Helper</NavLink>
			</NavItem>
			<UncontrolledDropdown nav inNavbar>
				<DropdownToggle nav caret>
				Bingo
				</DropdownToggle>
				<DropdownMenu right>
				<DropdownItem href="/bingo">
					Generate Board
				</DropdownItem>
				<DropdownItem href="https://bingosync.com/">
					Start Bingo Game
				</DropdownItem>
				</DropdownMenu>
			</UncontrolledDropdown>
				
			<UncontrolledDropdown nav inNavbar>
				<DropdownToggle nav caret>
				Plandomizer
				</DropdownToggle>
				<DropdownMenu right>
				<DropdownItem href="/plando/simple">
					Open Plando Editor
				</DropdownItem>
				<DropdownItem href="/plando/all">
					View All Seeds
				</DropdownItem>
				<DropdownItem divider />
				{logonoff}
				</DropdownMenu>
			</UncontrolledDropdown>
			</Nav>
		</Navbar>
	)

}

const variations = {
	forcetrees: "Force Trees",
	starved: "Starved",
	discmaps: "Discrete Mapstones",
	hardmode: "Hard Mode",
	ohko: "OHKO",
	"0xp": "0 XP",
	notp: "No Teleporters",
	noplants: "No Plants",
	forcemaps: "Force Mapstones",
	forcerandomescape: "Force Random Escape",
	entshuf: "Entrance Shuffle",
	wild: "More Bonus Pickups"
}
const optional_paths = ["speed", "dboost-light", "dboost", "lure", "speed-lure", "lure-hard", "dboost-hard", "extended", "extended-damage", "dbash", "cdash", "extreme", "timed-level", "glitched", "cdash-farming"]
const varPaths = {"ohko": ["ohko", "hardmode"], "0xp": ["0xp", "hardmode"], "hard": ["hardmode"], "master": ["starved"]}
const diffPaths = {"glitched": "hard", "master": "hard"}
const disabledPaths = {
					"hardmode": ["dboost", "dboost-hard", "extended-damage", "extreme", "lure-hard"], 
					"0xp": ["glitched", "cdash", "cdash-farming", "speed-lure", "timed-level"], 
					"ohko": ["dboost-light", "dboost", "dboost-hard", "extended-damage", "extreme", "glitched", "lure-hard"]
					}
const revDisabledPaths = {}
Object.keys(disabledPaths).forEach(v => disabledPaths[v].forEach(path => revDisabledPaths.hasOwnProperty(path) ? revDisabledPaths[path].push(v) : revDisabledPaths[path] = [v]))


export default class MainPage extends React.Component {
	helpEnter = (category, option) => () => {clearTimeout(this.state.helpTimeout) ; this.setState({helpTimeout: setTimeout(this.help(category, option), 250)})}
	helpLeave = () => clearTimeout(this.state.helpTimeout) 
	help = (category, option) => () => this.setState({helpParams: getHelpContent(category, option)})
	
	getWarmthFragsTab = () => {
		let onWarmthClick = () =>  this.state.warmthFragsEnabled ? this.setState({warmthFragsEnabled: false, keyMode: this.state.oldKeyMode}) : this.setState({warmthFragsEnabled: true, oldKeyMode: this.state.keyMode, keyMode: "Warmth Frags"})
		let maxFrags = (this.state.variations.includes("hardmode") ? 150 : 80) - (this.state.variations.includes("wild") ? 20 : 0) - (this.state.variations.includes("noplants") ? 20 : 0)
		let fragCountValid = this.state.fragCount > 0 && this.state.fragCount <= maxFrags
		let fragCountFeedback = this.state.fragCount > maxFrags ? (
				<FormFeedback tooltip>Fragment count must be less than or equal to {maxFrags}</FormFeedback>
			) : (
				<FormFeedback tooltip>Fragment count must be greater than 0</FormFeedback>
			)
		let maxReq = this.state.fragCount - this.state.fragTol;
		let fragRows = ["First Dungeon Key", "Second Dungeon Key", "Last Dungeon Key", "Total Required"].map((text, i) => {
			let key = i;
			let setter = (e) => {
				let curr = this.state.fragKeys;
				curr[key] = parseInt(e.target.value, 10)
				this.setState({fragKeys: curr})
			};
			let currCount = this.state.fragKeys[key] 
			let valid = currCount > 0 && currCount <= maxReq;
			let feedback = currCount > maxReq ? (
				<FormFeedback tooltip>Fragment requirement must not be greater than {maxReq} (the total number of fragments, minus the tolerance value)</FormFeedback>
			) : (
				<FormFeedback tooltip>Fragment requirement must be greater than 0</FormFeedback>
			)
			return (
				<Row className="p-1 justify-content-center">
					<Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("warmthFrags", text)} className="text-center pt-1 border">
						<span class="align-middle">{text}</span>
					</Col><Col xs="4">
						<Input type="number" value={currCount } disabled={!this.state.warmthFragsEnabled} invalid={!valid} onChange={setter}/> 
						{feedback}
					</Col>
				</Row>
			)
		})
		return (
			<TabPane tabId="warmthFrags">
				<Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("warmthFrags", "Enable")} className="p-1 justify-content-center">
					<Col xs="6">
						<Button block color="warning" outline={!this.state.warmthFragsEnabled} onClick={onWarmthClick}>{this.state.warmthFragsEnabled ? "Disable" : "Enable"} Warmth Fragments</Button>
					</Col>
				</Row>
				<Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("warmthFrags", "fragCount")} className="p-1 justify-content-center">
					<Col xs="4" className="text-center pt-1 border">
						<span class="align-middle">Warmth Fragment Count</span>
					</Col><Col xs="4">
						<Input type="number" value={this.state.fragCount} disabled={!this.state.warmthFragsEnabled} invalid={!fragCountValid} onChange={(e) => this.setState({fragCount: parseInt(e.target.value, 10)})}/> 
						{fragCountFeedback}
					</Col>
				</Row>
				{fragRows}
				<Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("warmthFrags", "fragTol")} className="p-1 justify-content-center">
					<Col xs="4" className="text-center pt-1 border">
						<span class="align-middle">Logic Tolerance</span>
					</Col><Col xs="4">
						<Input type="number" value={this.state.fragTol} disabled={!this.state.warmthFragsEnabled} invalid={this.state.fragTol <= 0} onChange={(e) => this.setState({fragTol: parseInt(e.target.value, 10)})}/> 
						<FormFeedback tooltip>Tolerance cannot be negative</FormFeedback>
					</Col>
				</Row>
				<Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("warmthFrags", "expPool")} className="p-1 justify-content-center">
					<Col xs="4" className="text-center pt-1 border">
						<span class="align-middle">Exp Pool</span>
					</Col><Col xs="4">
						<Input type="number" value={this.state.expPool} invalid={this.state.expPool < 100} onChange={(e) => this.setState({expPool: parseInt(e.target.value, 10)})}/> 
						<FormFeedback tooltip>Experience Pool must be at least 100</FormFeedback>
					</Col>
				</Row>
			</TabPane>
		)
	}

	
	getMultiplayerTab = () => {
		let multiplayerButtons = ["Skills", "Dungeon Keys", "Teleporters", "Upgrades", "World Events"].map(stype => (
			<Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("Shared Item Categories", stype)} className="p-2">
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
				<Collapse isOpen={this.state.user}>
					<Row className="p-1 justify-content-center">
						<Col xs="4" className="text-center pt-1 border">
							<span class="align-middle">SyncId (leave blank)</span>
						</Col><Col xs="4">
							<Input type="number" value={this.state.syncId} invalid={!(this.state.syncId === "" || this.state.syncId > 0)} onChange={(e) => this.setState({syncId: parseInt(e.target.value)})}/>
							<FormFeedback tooltip>syncId must be positive</FormFeedback>
						</Col>
					</Row>
				</Collapse>
			</TabPane>
		)
	}
	
	generateSeed = () => {
		let pMap = {"Race": "None", "None": "Default", "Co-op": "Shared", "Cloned Seeds": "split", "Seperate Seeds": "disjoint", "Warmth Frags": "frags", 
					"World Events": "events", "Dungeon Keys": "keys", "hard": "hardmode"}
		let f = (p) => pMap.hasOwnProperty(p) ? pMap[p] : p.toLowerCase()
		let urlParams = []
		urlParams.push("mode="+f(this.state.keyMode))
		if(this.state.pathDiff !== "Normal")
			urlParams.push("pathdiff="+this.state.pathDiff)
		urlParams.push("genmode="+this.state.fillAlg)
		this.state.variations.forEach(v => urlParams.push(f(v)+"=on"))
		this.state.paths.forEach(v => urlParams.push(v+"=on"))
		urlParams.push("pathMode="+this.state.pathMode)
		urlParams.push("playerCount="+this.state.players)
		urlParams.push("expPool="+this.state.expPool)
		if(this.state.tracking)
		{
				urlParams.push("tracking=on")
			if(this.state.syncId !== "")
				urlParams.push("syncid="+this.state.syncId)
			if(this.state.players > 1) {
				urlParams.push("synctype="+f(this.state.coopGenMode))
				urlParams.push("syncmode="+f(this.state.coopGameMode))
				if(this.state.coopGameMode === "Co-op")
					this.state.shared.forEach(s => urlParams.push(f(s)+"=on"))
				if(this.state.coopGenMode === "Cloned Seeds" && this.state.hints)
					urlParams.push("hints=on")				
			} else {
				urlParams.push("syncmode=None")
			}			
		}
		if(this.state.warmthFragsEnabled)
		{
			urlParams.push("warm_frags=on")
			urlParams.push("fragNum="+this.state.fragCount)
			this.state.fragKeys.concat(this.state.fragTol).forEach((key, i) => urlParams.push("fragKey"+(i+1)+"="+key))
		}
		let seed = this.state.seed || Math.round(Math.random() * 1000000000) ;
		if(seed === "daily")
		{
	  	    let d = new Date();
	        let month = '' + (d.getMonth() + 1);
	        let day = '' + d.getDate();
	        let year = d.getFullYear();
		    if (month.length < 2) month = '0' + month;
		    if (day.length < 2) day = '0' + day;
			seed = [year, month, day].join('-');
			urlParams.push("seed=" + seed)			
			let url = base_url + "/mkseed?" + urlParams.join("&")
			NotificationManager.warning("Daily seeds generated here will not match those generated by the other site. Click here to download anyways.", "Continue?", 10000, () => { window.location.href = url })
			return
		} else if(seed === "vanilla") {
			this.setState({seed: ""})
			window.location.href = "/vanilla"
			return
		} else {
			urlParams.push("seed=" + seed)			
			let url = base_url + "/mkseed?" + urlParams.join("&")
			window.location.href = url
		}
	}

	constructor(props) {
		super(props);
		let user = get_param("user");
		let dllTime = get_param("dll_last_update");
		this.state = {user: user, activeTab: 'variations', coopGenMode: "Cloned Seeds", coopGameMode: "Co-op", players: 1, tracking: true, dllTime: dllTime, variations: ["forcetrees"], 
					 paths: presets["standard"], keyMode: "Clues", oldKeyMode: "Clues", pathMode: "standard", pathDiff: "Normal", helpParams: getHelpContent("none", null),
					 customSyncId: "", seed: "", fillAlg: "Balanced", shared: ["Skills", "Dungeon Keys", "Teleporters", "World Events"], hints: false,
					 warmthFragsEnabled: false, fragCount: 35, fragKeys: [7, 14, 21, 28], fragTol: 3, syncId: "", expPool: 10000, lastHelp: new Date()};
	}
	onPath = (p) => () => this.state.paths.includes(p) ? this.setState({pathMode: "custom", paths: this.state.paths.filter(x => x !== p)}) : this.setState({pathMode: "custom", paths: this.state.paths.concat(p)})	
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
	onKeyMode = (mode) => () => (mode === "Warmth Frags" && !this.state.warmthFragsEnabled) ? this.setState({keyMode: mode, warmthFragsEnabled: true, activeTab: "warmthFrags"}) : this.setState({keyMode: mode})

	
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
		this.setState({variations: vars, pathMode: mode, paths: presets[mode], pathDiff: pd})
	}

	render = () => {
		let pathModeOptions = Object.keys(presets).map(mode => (
			<DropdownItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicModes", mode)} className="text-capitalize" active={mode===this.state.pathMode.toLowerCase()} onClick={this.onMode(mode)}>{mode}</DropdownItem>
		))
		let keyModeOptions = keymode_options.map(mode => (
			<DropdownItem active={mode===this.state.keyMode} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("keyModes", mode)} onClick={this.onKeyMode(mode)}>{mode}</DropdownItem>
		))
		let pathDiffOptions = ["Easy", "Normal", "Hard"].map(mode => (
			<DropdownItem active={mode===this.state.pathDiff} onClick={()=> this.setState({pathDiff: mode})}>{mode}</DropdownItem>
		))
		let variationButtons = Object.keys(variations).filter(x => x !== "wild").map(v=> {
			let name = variations[v];
			return (
			<Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", v)} className="p-2">
				<Button block outline={!this.state.variations.includes(v)} onClick={this.onVar(v)}>{name}</Button>
			</Col>
			)		
		})
		variationButtons.push((
			(
			<Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", "wild")} className="p-2">
				<Button block outline={!this.state.variations.includes("wild")} disabled={(() => {
					if(this.state.variations.includes("hardmode")) {
						if(this.state.variations.includes("wild"))
							this.onVar("wild")()
						return true;
					}
					return false;
				})()} onClick={this.onVar("wild")}>{variations["wild"]}</Button>
			</Col>
			)		
		))
		let pathButtons = [(
		<Col xs="3" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicPaths",  "normal")}  className="p-2">
				<Button block disabled={true} className="text-capitalize">Normal</Button>
		</Col>
		)].concat(optional_paths.map(path=> (
			<Col xs="3" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicPaths", path)}  className="p-2">
				<Button block outline={!this.state.paths.includes(path)} disabled={this.pathDisabled(path)} className="text-capitalize" onClick={this.onPath(path)}>{path}</Button>
			</Col>
		)))
		let multiplayerTab = this.getMultiplayerTab()
		let warmthFragsTab = this.getWarmthFragsTab()
		
		return (
 		<Container className="pl-4 pr-4 pb-4 pt-2 mt-5">
 			<NotificationContainer style={{top: "inherit", right: "inherit"}}/>
			<SiteBar dlltime={this.state.dllTime} user={this.state.user}/>
			<Helmet>
				<style>{'body { background-color: white}'}</style>
			</Helmet>
			<Row className="p-1">
				<Col>
					<span><h3 style={textStyle}>Seed Generator v2.5.C:</h3></span>
				</Col>
			</Row>
			<Row className="p-3 border">
				<Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "logicModes")}>
					<Row>
						<Col xs="6"  className="text-center pt-1 border">
							<span class="align-middle">Logic Mode</span>
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
						<Col xs="6" onMouseLeave={this.helpEnter("general", "keyModes")} onMouseEnter={this.helpEnter("keyModes", this.state.keyMode)}>
							<UncontrolledButtonDropdown className="w-100">
								<DropdownToggle color="primary" caret block> {this.state.keyMode} </DropdownToggle>
								<DropdownMenu>
									{keyModeOptions}
								</DropdownMenu>
							</UncontrolledButtonDropdown>
						</Col>
					</Row>
				</Col>
				<Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "pathDiff")}>
					<Row>
						<Col xs="6"  className="text-center pt-1 border">
							<span class="align-middle">Path Difficulty</span>
						</Col>
						<Col xs="6">
							<UncontrolledButtonDropdown className="w-100">
								<DropdownToggle color="primary" caret block> {this.state.pathDiff} </DropdownToggle>
								<DropdownMenu> {pathDiffOptions} </DropdownMenu>
							</UncontrolledButtonDropdown>
						</Col>
					</Row>
				</Col>
			</Row>
			<Row className="justify-content-middle p-2">
			<Col>
				<Nav tabs>
					<NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "variations")}>
						<NavLink active={this.state.activeTab === 'variations'} onClick={() => { this.setState({activeTab: 'variations'})}}>
						Variations
						</NavLink>
					</NavItem>
					<NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "logicPaths")}>
						<NavLink active={this.state.activeTab === 'logic paths'} onClick={() => { this.setState({activeTab: 'logic paths'})}}>
						Logic Paths
						</NavLink>
					</NavItem>
					<NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("general", "multiplayer")}>
						<NavLink active={this.state.activeTab === 'multiplayer'} onClick={() => { this.setState({activeTab: 'multiplayer'})}}>
						Multiplayer Options
						</NavLink>
					</NavItem>
					<NavItem onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("keyModes", "Warmth Frags")}>
						<NavLink active={this.state.activeTab === 'warmthFrags'} onClick={() => { this.setState({activeTab: 'warmthFrags'})}}>
						Warmth Fragment Mode
						</NavLink>
					</NavItem>
				</Nav>
			</Col>
			</Row>
			<Row className="justify-content-start p-2">
				<Col xs="8">
					<Row>
						<Col>
							<TabContent className="p-1 border" activeTab={this.state.activeTab}>
								<TabPane tabId="variations">
									<Row className="p-2">
										{variationButtons}
									</Row>
								</TabPane>
								<TabPane tabId="logic paths">
									<Row className="p-2">
										{pathButtons}
									</Row>
								</TabPane>
								{multiplayerTab}
								{warmthFragsTab}
							</TabContent>
						</Col>
					</Row>
					<Row className="align-items-center">
						<Col xs="6">
							<Row className="p-1">
								<Col xs="5" className="text-center pt-1 border">
									<span class="align-middle">Seed</span>
								</Col><Col xs="7">
									<Input type="text" value={this.state.seed} onChange={(e) => this.setState({seed: e.target.value})}/>
								</Col>
							</Row><Row className="p-1">
								<Col xs="5" className="text-center pt-1 border">
									<span class="align-middle">Fill Algorithm</span>
								</Col><Col xs="7">
									<UncontrolledButtonDropdown className="w-100">
										<DropdownToggle color="primary" caret block> {this.state.fillAlg} </DropdownToggle>
										<DropdownMenu>
											<DropdownItem active={"Classic"===this.state.fillAlg} onClick={()=> this.setState({fillAlg: "Classic"})}>Classic</DropdownItem>
											<DropdownItem active={"Balanced"===this.state.fillAlg} onClick={()=> this.setState({fillAlg: "Balanced"})}>Balanced</DropdownItem>
										</DropdownMenu>
									</UncontrolledButtonDropdown>
								</Col>
							</Row><Row>
								<Col>
									<Button color="info" block outline={!this.state.tracking} onClick={()=>this.setState({tracking: !this.state.tracking})}>Web Tracking {this.state.tracking ? "Enabled" : "Disabled"}</Button>
								</Col>
							</Row>
						</Col>
						<Col>
							<Button color="success" size="lg" onClick={this.generateSeed} block>Generate Seed</Button>
						</Col>
					</Row>
				</Col>
				<Col>
					<HelpBox {...this.state.helpParams} />
				</Col>
			</Row>
			</Container>
		)

	}
};


