import React from 'react';
import  {DropdownToggle, DropdownMenu, DropdownItem, Nav, NavLink, NavItem, Collapse,  Input, UncontrolledButtonDropdown, Button, 
		Row, FormFeedback, Col, Container, TabContent, TabPane, Modal, ModalHeader, ModalBody, ModalFooter, Media} from 'reactstrap'
import {Helmet} from 'react-helmet';
import {NotificationContainer, NotificationManager} from 'react-notifications';
import 'react-notifications/lib/notifications.css';
import './index.css';

import {getHelpContent, HelpBox} from "./helpbox.js"
import {get_param, presets, goToCurry, player_icons, doNetRequest} from './shared_map.js';
import SiteBar from "./SiteBar.js"

const dev = window.document.URL.includes("devshell")
const keymode_options = ["None", "Shards", "Limitkeys", "Clues", "Warmth Frags"];

const textStyle = {color: "black", textAlign: "center"}


const variations = {
	ForceTrees: "Force Trees",
	Starved: "Starved",
	NonProgressMapStones: "Discrete Mapstones",
	Hard: "Hard Mode",
	OHKO: "One Hit KO",
	"0XP": "Zero Experience",
	NoTeleporters: "No Teleporters",
	NoPlants: "No Plants",
	ForceMapStones: "Force Mapstones",
	ForceRandomEscape: "Force Random Escape",
//	Entrance: "Entrance Shuffle",
	BonusPickups: "More Bonus Pickups"
}
const optional_paths = ["speed", "dboost-light", "dboost", "lure", "speed-lure", "lure-hard", "dboost-hard", "extended", "extended-damage", "dbash", "cdash", "extreme", "timed-level", "glitched", "cdash-farming"]
const varPaths = {"ohko": ["OHKO", "Hard"], "0xp": ["0XP", "Hard"], "hard": ["Hard"], "master": ["Starved"]}
const diffPaths = {"glitched": "Hard", "master": "Hard"}
const disabledPaths = {
					"Hard": ["dboost", "dboost-hard", "extended-damage", "extreme", "lure-hard"], 
					"0XP": ["glitched", "cdash", "cdash-farming", "speed-lure", "timed-level"], 
					"OHKO": ["dboost-light", "dboost", "dboost-hard", "extended-damage", "extreme", "glitched", "lure-hard"]
					}
const revDisabledPaths = {}
Object.keys(disabledPaths).forEach(v => disabledPaths[v].forEach(path => revDisabledPaths.hasOwnProperty(path) ? revDisabledPaths[path].push(v) : revDisabledPaths[path] = [v]))


export default class MainPage extends React.Component {
	helpEnter = (category, option, timeout=250) => () => {clearTimeout(this.state.helpTimeout) ; this.setState({helpTimeout: setTimeout(this.help(category, option), timeout)})}
	helpLeave = () => clearTimeout(this.state.helpTimeout) 
	help = (category, option) => () => this.setState({helpcat: category, helpopt: option, helpParams: getHelpContent(category, option)})
	
	getWarmthFragsTab = () => {
		let frag = this.state.frag
		let onWarmthClick = () =>  frag.enabled ? this.onFrag("enabled", false, {keyMode: this.state.oldKeyMode}) : this.onFrag("enabled", true, {oldKeyMode: this.state.keyMode, keyMode: "Warmth Frags"})
		let maxFrags = (this.state.variations.includes("Hard") ? 150 : 80) - (this.state.variations.includes("BonusPickups") ? 20 : 0) - (this.state.variations.includes("NoPlants") ? 20 : 0)
		let fragCountValid = frag.count > 0 && frag.count <= maxFrags
		let fragCountFeedback = frag.count > maxFrags ? (
				<FormFeedback tooltip>Fragment count must be less than or equal to {maxFrags}</FormFeedback>
			) : (
				<FormFeedback tooltip>Fragment count must be greater than 0</FormFeedback>
			)
		let maxReq = frag.count - frag.tolerance;
		let frag_row_data = ["key_1", "key_2", "key_3", "required"]
		let fragRows = ["First Dungeon Key", "Second Dungeon Key", "Last Dungeon Key", "Total Required"].map((text, i) => {
			let key = frag_row_data[i];
			let setter = (e) => this.onFrag(key, parseInt(e.target.value, 10))
			let currCount = frag[key] 
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
						<Input type="number" value={currCount} disabled={!frag.enabled} invalid={!valid} onChange={setter}/> 
						{feedback}
					</Col>
				</Row>
			)
		})
		return (
			<TabPane tabId="warmthFrags">
				<Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("warmthFrags", "Enable")} className="p-1 justify-content-center">
					<Col xs="6">
						<Button block color="warning" outline={!frag.enabled} onClick={onWarmthClick}>{frag.enabled ? "Disable" : "Enable"} Warmth Fragments</Button>
					</Col>
				</Row>
				<Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("warmthFrags", "fragCount")} className="p-1 justify-content-center">
					<Col xs="4" className="text-center pt-1 border">
						<span class="align-middle">Warmth Fragment Count</span>
					</Col><Col xs="4">
						<Input type="number" value={frag.count} disabled={!frag.enabled} invalid={!fragCountValid} onChange={e => this.onFrag("count", parseInt(e.target.value, 10))}/> 
						{fragCountFeedback}
					</Col>
				</Row>
				{fragRows}
				<Row onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("warmthFrags", "fragTol")} className="p-1 justify-content-center">
					<Col xs="4" className="text-center pt-1 border">
						<span class="align-middle">Logic Tolerance</span>
					</Col><Col xs="4">
						<Input type="number" value={this.state.frag.tolerance} disabled={!frag.enabled} invalid={this.state.fragTol <= 0} onChange={e => this.onFrag("tolerance", parseInt(e.target.value, 10))}/> 
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
							<span class="align-middle">SyncId (leave blank if unsure)</span>
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
								<FormFeedback tooltip>Team format: 1,2|3,4|5,6. Must be at least 2 teams, and each player must appear once.</FormFeedback>
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
		let pMap = {"Race": "None", "None": "Default", "Co-op": "Shared", "Warmth Frags": "Frags", 
					"World Events": "Events", "Dungeon Keys": "Keys", "Cloned Seeds": "cloned", "Seperate Seeds": "disjoint"}
		let f = (p) => pMap.hasOwnProperty(p) ? pMap[p] : p
		let urlParams = []
		urlParams.push("key_mode="+f(this.state.keyMode))
		if(this.state.pathDiff !== "Normal")
			urlParams.push("path_diff="+this.state.pathDiff)
		urlParams.push("gen_mode="+this.state.fillAlg)
		this.state.variations.forEach(v => urlParams.push("var="+v))
		this.state.paths.forEach(p => urlParams.push("path="+p))
		urlParams.push("exp_pool="+this.state.expPool)
		urlParams.push("players="+this.state.players)
		if(this.state.tracking)
		{
			if(this.state.syncId !== "")
				urlParams.push("sync_id="+this.state.syncId)
			if(this.state.players > 1) {
				urlParams.push("sync_get="+f(this.state.coopGenMode))
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
		if(this.state.frag.enabled)
			Object.keys(this.state.frag).filter(p => p !== "enabled").forEach(p => urlParams.push("frag_"+p+"="+this.state.frag[p]))
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
			let url = "/generator/build?" + urlParams.join("&")
			NotificationManager.warning(
				"Daily seeds generated here will not match those generated by the other site. Click here to download anyways.", 
				"Continue?", 
				10000, 
				() => this.setState({seedIsGenerating: true, modalOpen: true}, () => doNetRequest(url, this.seedBuildCallback))
				)
			return
		} else if(seed === "vanilla") {
			window.location.href = "/vanilla"
			return
		} else {
			urlParams.push("seed=" + seed)			
			let url = "/generator/build?" + urlParams.join("&")
			this.setState({seedIsGenerating: true, modalOpen: true}, () => doNetRequest(url, this.seedBuildCallback))
		}
	}
	acceptMetadata = ({status, responseText}) => {
		if(status !== 200)
		{
			NotificationManager.error("Failed to recieve seed metadata", "Seed could not be retrieved!", 5000)
			this.setState({modalOpen: false})
		    window.history.replaceState('',window.document.title, window.document.URL.split("?")[0]);
		} else {
			let res = JSON.parse(responseText)
			this.setState({inputPlayerCount: res["playerCount"], inputFlagLine: res["flagLine"]})
		}
	}


	
	seedBuildCallback = ({status, responseText}) => {
		if(status !== 200)
		{
			NotificationManager.error("Failed to generate seed!", "Seed generation failure!", 5000)
			this.setState({seedIsGenerating: false, modalOpen: false})
			return
		} else {
			let res = JSON.parse(responseText)
			let paramId = res["paramId"]
			let gameId = res["gameId"]
			let playerCount = res["playerCount"]
			let flagLine = res["flagLine"]
			let url = window.document.URL.split("?")[0]+"?param_id="+paramId
			if(gameId > 0)
				url += "&game_id="+gameId
		    window.history.replaceState('',window.document.title, url);
			this.setState({paramId: paramId, seedIsGenerating: false, modalOpen: true, inputPlayerCount: playerCount, inputFlagLine: flagLine, allowReopenModal: true, inputGameId: gameId})
		}
	}
	
	getModal = () => {
		if(this.state.seedIsGenerating)
		{
		    return (
		        <Modal isOpen={this.state.modalOpen} toggle={this.closeModal} backdrop={"static"}>
		          <ModalHeader toggle={this.closeModal}>Generating Seed.</ModalHeader>
		          <ModalBody>
					The server is generating your seed. This may take a few seconds...
		          </ModalBody>
		          <ModalFooter>
		            <Button color="secondary" onClick={this.closeModal}>Close</Button>
		          </ModalFooter>
		        </Modal>
		    	)
		}
		else 
		{
			let raw = this.state.inputFlagLine.split('|');
			let seedStr = raw.pop();
			let {shared, unshared} = raw.join("").split(",").reduce((acc, curr) => (curr.startsWith("mode=") || curr.startsWith("shared=")) ? 
					{shared: acc.shared.concat(curr), unshared: acc.unshared} : {shared: acc.shared, unshared: acc.unshared.concat(curr)}, {shared: [], unshared: []})
			
			let sharedFlags = shared.length > 0 ? (<Row><Col><span class="align-middle">Sync: {shared.join(", ")}</span></Col></Row>) : null
			let flags = unshared.join(", ");
			
			let playerRows = (this.state.inputPlayerCount > 1) ? [...Array(this.state.inputPlayerCount).keys()].map(p => {				
				p++;
				let seedUrl = "/generator/seed/"+this.state.paramId+"?player_id="+p
				let spoilerUrl = "/generator/spoiler/"+this.state.paramId+"?player_id="+p
				if(this.state.inputGameId > 0) seedUrl += "&game_id="+this.state.inputGameId
				return (
					<Row className="p-1 border-top border-bottom">
						<Col xs="2" className="text-center pt-1 border">
							<Row><Col xs="2">
								<Media object style={{width: "25px", height: "25px"}} src={player_icons(p,false)} alt={"Icon for player "+p} />
							</Col><Col >
								<span class="align-middle">Player {p}</span>
							</Col></Row>
						</Col>
						<Col xs="3">
							<Button color="primary" block href={seedUrl}>Download Seed</Button>
						</Col>
						<Col xs="3">
							<Button color="primary" href={spoilerUrl} target="_blank" block >View Spoiler</Button>
						</Col>
					</Row>
				)
			}) : (
				<Row className="p-1">
					<Col xs="3">
						<Button color="primary" block href={"/generator/seed/"+this.state.paramId + ((this.state.inputGameId > 0) ? "?game_id="+this.state.inputGameId : "")}>Download Seed</Button>
					</Col>
					<Col xs="3">
						<Button color="primary" block href={"/generator/spoiler/"+this.state.paramId} target="_blank">View Spoiler</Button>
					</Col>
				</Row>
			)
			let trackedInfo = this.state.inputGameId > 0 ? (
	          	<Row className="p-1 border-dark border-bottom">
		          	<Col xs={{ size: 3, offset: 2 }}>
						<Button color="primary" block href={"/tracker/game/"+this.state.inputGameId+"/map"} target="_blank">Open Tracking Map</Button>
	          		</Col>
		          	<Col xs="3">
						<Button color="primary" block href={"/game/"+this.state.inputGameId+"/history"} target="_blank">View Game History</Button>
	          		</Col>
          		</Row>
      		) : null		
		    return (
		        <Modal size="lg" isOpen={this.state.modalOpen} backdrop={"static"} className={"modal-dialog-centered"} toggle={this.closeModal}>
		          <ModalHeader toggle={this.closeModal} centered>Seed {seedStr} ready!</ModalHeader>
		          <ModalBody>
		          	<Container fluid>
		          	<Row>
			          	<Col className="text-center pt-1 border">
			          		<Row><Col>
				          		<span class="align-middle">Flags: {flags}</span>
		          			</Col></Row>
		          			{sharedFlags}			          		
		          		</Col>
	          		</Row>
	          		{trackedInfo}
					{playerRows}
					</Container>
		          </ModalBody>
		          <ModalFooter>
		            <Button color="secondary" onClick={this.closeModal}>Close</Button>
		          </ModalFooter>
		        </Modal>
		    	)
		}
	}
	constructor(props) {
		super(props);
		let user = get_param("user");
		let dllTime = get_param("dll_last_update")
		let url = new URL(window.document.location.href);
		let paramId = url.searchParams.get("param_id");
		let inputGameId = parseInt(url.searchParams.get("game_id") || -1, 10);
		let modalOpen = (paramId !== null);
		if(modalOpen)
			doNetRequest("/generator/metadata/"+paramId,this.acceptMetadata)
		this.state = {user: user, activeTab: 'variations', coopGenMode: "Cloned Seeds", coopGameMode: "Co-op", players: 1, tracking: true, dllTime: dllTime, variations: ["ForceTrees"], 
					 paths: presets["standard"], keyMode: "Clues", oldKeyMode: "Clues", pathMode: "standard", pathDiff: "Normal", helpParams: getHelpContent("none", null),
					 customSyncId: "", seed: "", fillAlg: "Balanced", shared: ["Skills", "Dungeon Keys", "Teleporters", "World Events"], hints: true, helpcat: "", helpopt: "",
					 frag: {enabled: false, count: 40, key_1: 7, key_2:14, key_3: 21, required: 28, tolerance: 3}, syncId: "", expPool: 10000, lastHelp: new Date(), seedIsGenerating: false,
					 paramId: paramId, modalOpen: modalOpen, inputGameId: inputGameId, allowReopenModal: modalOpen, reopenUrl: "", teamStr: "", inputFlagLine: ""};
	}
	
	
	closeModal = () => {
	    window.history.replaceState('',window.document.title, window.document.URL.split("?")[0]);
		this.setState({modalOpen: false})
	}
	reopenModal = () => {
		let url = window.document.URL.split("?")[0]+"?param_id="+this.state.paramId;
		if(this.state.inputGameId > 0)
			url+="&game_id="+this.state.inputGameId
	    window.history.replaceState('',window.document.title, url);
		this.setState({modalOpen: true})
	}
	
	onPath = (p) => () => this.state.paths.includes(p) ? this.setState({pathMode: "custom", paths: this.state.paths.filter(x => x !== p)}) : this.setState({pathMode: "custom", paths: this.state.paths.concat(p)})	
	onSType = (s) => () => this.state.shared.includes(s) ? this.setState({shared: this.state.shared.filter(x => x !== s)}) : this.setState({shared: this.state.shared.concat(s)})	
	onVar = (v) => () =>  this.state.variations.includes(v) ? this.setState({variations: this.state.variations.filter(x => x !== v)}) : this.setState({variations: this.state.variations.concat(v)})
	onFrag = (k, v, args) => this.setState(prev => { let frag = prev.frag; frag[k] = v ; return {frag: frag, ...args} })
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
	onKeyMode = (mode) => () => (mode === "Warmth Frags" && !this.state.frag.enabled) ? this.onFrag("enabled", true, {keyMode: mode, activeTab: "warmthFrags"}) : this.setState({keyMode: mode})

	
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
		let variationButtons = Object.keys(variations).filter(x => x !== "BonusPickups").map(v=> {
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
		let modal = this.getModal()
		let reopenModalBtn = this.state.allowReopenModal ? (<Button color="primary" block onClick={this.reopenModal}>Show Prior Seed</Button>) : null
		return (
 		<Container className="pl-4 pr-4 pb-4 pt-2 mt-5">
			<Helmet>
				<style>{'body { background-color: white}'}</style>
			</Helmet>
 			<Row className="justify-content-center">
	 			<Col>
	 				{modal}
					<NotificationContainer/>
					<SiteBar dlltime={this.state.dllTime} user={this.state.user}/>
				</Col>
			</Row>
			<Row className="p-1">
				<Col>
					<span>
						<h3 style={textStyle}>Seed Generator v2.6.9 ;) (;</h3>
					</span>
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
							<Row>
								<Col>
									<Button color="success" size="lg" onClick={this.generateSeed} block>Generate Seed</Button>
								</Col>
							</Row><Row>
								<Col>
									{reopenModalBtn}
								</Col>
							</Row>
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
