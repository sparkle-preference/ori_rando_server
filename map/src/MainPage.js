import './index.css';
import React from 'react';
import  {Collapse,  Navbar,  NavbarBrand, Nav,  NavItem,  NavLink, UncontrolledDropdown, Input, 
		UncontrolledButtonDropdown, DropdownToggle, DropdownMenu, DropdownItem, Button, Row, FormFeedback,
		Col, Container, TabContent, TabPane, Card, CardBody, CardTitle, CardSubtitle, CardText} from 'reactstrap'
import {Helmet} from 'react-helmet';
import {listSwap, get_param, presets} from './shared_map.js';


const dev = window.document.URL.includes("devshell")
const base_url = dev ?  "https://8080-dot-3616814-dot-devshell.appspot.com" : "http://orirandocoopserver.appspot.com"

const textStyle = {color: "black", textAlign: "center"}
const SiteBar = ({dlltime, user}) => {
	
	let logonoff = user ? [
		(<DropdownItem href={"'/plando/"+ user + "'"}> {user}'s seeds </DropdownItem>),
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
const varPaths = {"ohko": ["ohko", "hardmode"], "0xp": ["0xp", "hardmode"], "hard": ["hardmode"], "master": ["starved"]}
const diffPaths = {"glitched": "hard", "master": "hard"}
const disabledPaths = {
					"hardmode": ["dboost", "dboost-hard", "extended-damage", "extreme"], 
					"0xp": ["glitched", "cdash", "cdash-farming", "speed-lure"], 
					"ohko": ["dboost-light", "dboost", "dboost-hard", "extended-damage", "extreme", "glitched"]
					}
const revDisabledPaths = {"dboost": ["hardmode", "ohko"], "dboost-hard": ["hardmode", "ohko"], "extended-damage": ["hardmode", "ohko"], 
						"extreme": ["ohko", "hardmode"], "glitched": ["0xp", "ohko"], "cdash": ["0xp"], "cdash-farming": ["0xp"], "speed-lure": ["0xp"]}

const noneTitle = "Confused?"
const noneSub = "Mouse over anything to learn more!"
const noneText = "Additional context-specific information will appear here as you interact with the UI."

export default class MainPage extends React.Component {
	helpEnter = (category, option) => () => {clearTimeout(this.state.helpTimeout) ; this.setState({helpTimeout: setTimeout(this.help(category, option), 250)})}
	helpLeave = () => clearTimeout(this.state.helpTimeout) 
	help = (category, option) => () => {
		switch(category ) {
			case "logicModes":
				let helpParams = {helpSub: "Logic Mode", helpExtra: (
					<CardText>For more detailed info about Logic Modes, check the help sections inside the Logic Paths tab</CardText>
				)}
				
				switch(option) {
					case "casual":						
						helpParams = Object.assign({helpTitle: "Casual", helpText: "Casual is the easiest logic mode, intended for players who have never done a speedrun of Ori."}, helpParams)
						break;
					case "standard":						
						helpParams = Object.assign({helpTitle: "Standard", helpText: "Standard is the default randomizer logic mode, intended for users who are familiar with Ori movement and basic speedrunning tech. The community weekly races use this logic mode."}, helpParams)
						break;
					case "dboost":						
						helpParams = Object.assign({helpTitle: "Dboost", helpText: "Dboost (or Damage Boost) is the next step up from Standard, and can require players to take up to 5 damage from spikes, poison water, or other hazards while collecting pickups."}, helpParams)
						break;
					case "expert":						
						helpParams = Object.assign({helpTitle: "Expert", helpText: "Expert is for players who've been playing the randomizer for a while, and can require tedious, more difficult, and more annoying techniques."}, helpParams)
						break;
					case "master":						
						helpParams = Object.assign({helpTitle: "Master", helpText: "Master is even more difficult than Expert, and is only recommended for players looking to push the game to the limit. Additionally, the path difficulty is set to hard and the Starved variation is set. Warning: can require double bashing."}, helpParams)
						break;
					case "hard":						
						helpParams = Object.assign({helpTitle: "Hard", helpText: "The Hard logic mode is designed for the 'Hard Mode' variation, which limits players to 3 health and 4 energy for the entire game. Selecting this Logic Mode will automatically turn Hard Mode on. Warning: can require double bashing"}, helpParams)
						break;
					case "ohko":						
						helpParams = Object.assign({helpTitle: "One-Hit KO", helpText: "The One-Hit KO logic mode uses the 'OHKO' and 'Hard Mode' variations. This limits Ori to 3 health and 4 energy (Hard Mode) and makes all damage taken by Ori lethal (OHKO). Selecting this Logic Mode will automatically turn both Hard Mode and OHKO on. Warning: can require double bashing"}, helpParams)
						break;
					case "0xp":						
						helpParams = Object.assign({helpTitle: "Zero Experience", helpText: "The Zero Experience logic mode uses the '0xp' and 'Hard Mode' variations. This limits Ori to 3 health and 4 energy (Hard Mode) and makes it impossible to acquire experience or ability cells (0xp). Selecting this option will automatically turn both Hard Mode and 0xp on. Warning: not for the feint of heart."}, helpParams)
						break;
					case "glitched":						
						helpParams = Object.assign({helpTitle: "Glitched", helpText: "Glitched is the hardest logic mode in the game, and not recommended for most players. In addition to everything that Master requires, it requires knowledge of the game's various out-of-bounds tricks and other unsafe paths. Tread carefully!"}, helpParams)
						break;
				}
				this.setState(helpParams);
				break;
			case "variations":
				switch(option) {
					case "forcetrees":
						this.setState({helpTitle: "Force Trees", helpSub: "Variations", helpText: "The Force Trees variation requires players to visit all ten skill trees before completing the game. It is wildly popular, enabled by default, and recommended for all players. The community weekly races use this variation.", helpExtra: null})
						break;
					case "starved":
						this.setState({helpTitle: "Starved", helpSub: "Variations", helpText: "The Starved variation reduces the probability that players will be given skill pickups, unless one is needed to proceed. This tends to create more linear seeds, where each skill gives access to the area or areas where the next skill or important item will be found. Recommended for everyone at least once, and for players who enjoy more linear pathing or constrained situations.", helpExtra: null})
						break;
					case "discmaps":
						this.setState({helpTitle: "Discrete Mapstones", helpSub: "Variations", helpText: "The Discrete Mapstone variation changes how mapstones function, making each individual mapstone turn-in have its own pickup. (By default, the mapstone pickups are granted based on the number of mapstones you have turned in, regardless of where). This variation exists primarily for legacy reasons and is not recommended for normal use.", helpExtra: null})
						break;
					case "hardmode":
						this.setState({helpTitle: "Hard Mode", helpSub: "Variations", helpText: "The Hard Mode variation removes all health cells and all but 3 energy cells from the pool of available items, capping your health at 3 and energy at 4 for the entire seed. As a result, it is incompatible with logic paths that require taking 3 or more damage (dboost, dboost-hard, extended-damage, and extreme). Recommended for people who hate feeling safe and like to live on the edge.", helpExtra: null})
						break;
					case "ohko":
						this.setState({helpTitle: "One-Hit KO", helpSub: "Variations", helpText: "The One-Hit KO variation causes any amount of damage Ori takes to be instantly lethal. As such, it is incompatible with all logic paths that require damage boosts. NOTE: this variation is rarely used and thus is less tested than most. Tread carefully!", helpExtra: null})
						break;
					case "0xp":
						this.setState({helpTitle: "0 Experience", helpSub: "Variations", helpText: "Inspired by the incredibly unpopular 0exp speedrunning category, the 0 Experience variation prevents Ori from ever gaining levels or acquiring experience. Experience dropped by enemies will kill Ori on contact! Recommended for anyone who watched a 0xp run and thought it seemed fun.", helpExtra: null})
						break;
					case "noplants":
						this.setState({helpTitle: "No Plants", helpSub: "Variations", helpText: "The No Plants variation makes it so that pickups will not be placed in plants. This variation exists primarily for legacy reasons and is not recommended for normal use.", helpExtra: null})
						break;
					case "notp":
						this.setState({helpTitle: "No Teleporters", helpSub: "Variations", helpText: "The No Teleporters variation makes it so that you cannot unlock teleporters via pickups. This variation exists primarily for legacy reasons, but if you find that teleporter unlocks are frequently causing you confusion or unhappiness, this will help.", helpExtra: null})
						break;
					case "forcemaps":
						this.setState({helpTitle: "Force Maps", helpSub: "Variations", helpText: "The Force Maps variation requires that you turn in all 9 mapstones before finishing the game. Intended as an alternative to Force Trees (though you can do both), it has the effect of making the Forlorn Ruins (and thus either the Forlorn TP or Gumon Seal) manditory. Recommend for players looking for something new to try and for cartographers everywhere", helpExtra: null})
						break;
					case "forcerandomescape":
						this.setState({helpTitle: "Force Random Escape", helpSub: "Variations", helpText: "The Force Random Escape variation requires that you finish either the Forlorn or Ginso escapes before completing the game. Recommended for anyone who misses doing the Forlorn Escape, since it is otherwise never useful to complete.", helpExtra: null})
						break;
					case "entshuf":
						this.setState({helpTitle: "Entrance Shuffle", helpSub: "Variations", helpText: "The Entrance Shuffle variation remaps each door (the dungeon enterances and the 8 horu side rooms) in the game to go to another door instead. Recommended for anyone who likes being confused, or is interested in spending more time in Horu than usually necessary.", helpExtra: null})
						break;
					case "wild":
						this.setState({helpTitle: "More Bonus Pickups", helpSub: "Variations", helpText: "More Bonus Pickups introduces several new bonus pickups not normally found in the randomizer, including some new activateable skills. Recommended for people interested in trying out some cool and probably pretty overpowered pickups.", helpExtra: (<CardText>Note: The default bindings for bonus skills are Alt+Q to swap between them, and Alt+Mouse1 to activate them. These bindings can be changed in the RandomizerRebinding.txt file. The "ExtremeSpeed" and "Gravity Swap" pickups are toggleable: activating them will turn them on, and cost energy over time. They will automatically turn off if you run out of energy</CardText>)})
						break;
				}
				
				break;
			case "keyModes":
				switch(option) {
					case "Shards":
						this.setState({helpTitle: "Shards", helpSub: "Dungeon Key Modes", helpText: "In Shards, the dungeon keys are replaced with dungeon key shards. Each key has 5 shards on the map, but only 3 are needed to assemble the full key. Shards cannot generate within the dungeon they unlock.", helpExtra: (<CardText>Recommended for: experienced players, Co-op, and players who enjoy exploring and checking lots of pickups.</CardText>)})
						break;
					case "Clues":
						this.setState({helpTitle: "Clues", helpSub: "Dungeon Key Modes", helpText: "In Clues, the dungeon keys are placed randomly throughout the map. Every 3 skill trees you visit, the game will tell you which zone you can find one of the keys in. You can check your currently unlocked hints (as well as tree, mapstone, and overall progress) by pressing alt+p.", helpExtra: [(<CardText>Note: A map of the Zones is available <a target="_blank" href="https://i.imgur.com/lHgbqmI.jpg">here</a>.</CardText>), (<CardText>Recommended for: newer players, players who like exploring, but don't want to check every pickup.</CardText>)]})
						break;
					case "Limitkeys":
						this.setState({helpTitle: "Limitkeys", helpSub: "Dungeon Key Modes", helpText: "In Limitkeys, the dungeon keys are placed randomly at one of the Skill Trees or World Event locations (the vanilla locations for the Water Vein, Gumon Seal, and Sunstone, Wind Restored at the start of the Forlorn Escape, and Clean Water at the end of the Ginso Escape.)", helpExtra: (<CardText>Recommended for: newer players, players who dislike hunting for dungeon keys once they have the skills they need.</CardText>)})
						break;
					case "None":
						this.setState({helpTitle: "None", helpSub: "Dungeon Key Modes", helpText: "In None, the dungeon keys are placed randomly throughout the map. No constraints or info is given to help find them.", helpExtra: (<CardText>Recommended for: mashochists, people with too much free time.</CardText>)})
						break;
					case "Warmth Frags":
						this.setState({helpTitle: "Warmth Fragments", helpSub: "Dungeon Key Modes", helpText: "Warmth Fragments is an experimental new mode which removes the dungeon keys entirely. Instead, a configurable number of Warmth Fragments are required to access each dungeon (the unlock order is random). Check out the Warmth Fragment Mode tab for more details.", helpExtra: (<CardText>Recommended for: people who like exploring and efficiently checking large numbers of pickups</CardText>)})
						break;
				}
				break;
			case "general":
				switch(option) {
					case "logicModes":
						this.setState({helpTitle: "Logic Modes", helpSub: "General Options", helpText: "Logic Modes are sets of Logic Paths tailored for specific play experiences. Some Logic Modes, such as Hard or OHKO, also have associated variations that will be applied on selection. Changing the Logic Mode will have a major impact on seed difficulty. Mouse over a logic mode in the dropdown to learn more.", helpExtra: null})
						break;
					case "keyModes":
						this.setState({helpTitle: "Dungeon Key Modes", helpSub: "General Options", helpText: "Dungeon Key Modes change how the 3 dungeon keys (the Watervein, Gumon Seal, and Sunstone) are acquired. Since the Sunstone is always required, and the Water Vein is required by default (see Forcetrees under Variations for more info), placement of the Dungeon Keys matters a fair bit. New players should start with Clues or Limitkeys.", helpExtra: null})
						break;
					case "pathDiff":
						this.setState({helpTitle: "Path Difficulty", helpSub: "General Options", helpText: "Path Difficulty influences the likelihood that important or required pickups are placed in obscure or difficult to reach locations. With difficulty set to high, expect to see more pickups in difficult or out-of-the-way locations.", helpExtra: null})
						break;
					case "variations":
						this.setState({helpTitle: "Variations", helpSub: "General Options", helpText: "Variations introduce additional restrictions on how the game is played or how the seed is generated. Mouse over individual variations for more info. Note: Some variations are not compatible with certain Logic Paths.", helpExtra: null})
						break;
				}
				break;	
			case "logicPaths":
				this.setState({helpTitle: option, helpSub: "Logic Paths (WIP)", helpText: "Coming soon(tm)"})
				break;
			case "none":
			default:
				this.setState({helpTitle: noneTitle, helpSub: noneSub, helpText: noneText})
		}
	}
	
	getWarmthFragsTab = () => {
		let onWarmthClick = () =>  this.state.warmthFragsEnabled ? this.setState({warmthFragsEnabled: false, keyMode: this.state.oldKeyMode}) : this.setState({warmthFragsEnabled: true, oldKeyMode: this.state.keyMode, keyMode: "Warmth Frags"})
		let fragCountValid = this.state.fragCount > 0 && this.state.fragCount <= 60
		let fragCountFeedback = this.state.fragCount  > 0 ? (this.state.freqCount <= 60 ? null : (
				<FormFeedback tooltip>Fragment count must be less than or equal to 60</FormFeedback>
			)) : (
				<FormFeedback tooltip>Fragment count must be greater than 0</FormFeedback>
			)
		let maxReq = this.state.fragCount + this.state.fragTol;
		let fragRows = ["First Dungeon Key", "Second Dungeon Key", "Last Dungeon Key", "Total Required"].map((text, i) => {
			let key = i;
			let setter = (e) => {
				let curr = this.state.fragKeys;
				curr[key] = e.target.value
				this.setState({fragKeys: curr})
			};
			let currCount = this.state.fragKeys[key] 
			let valid = currCount > 0 && currCount < maxReq;
			let feedback = currCount > 0 ? (currCount < maxReq ? null : (
				<FormFeedback tooltip>Fragment requirement must be less than the total number of fragments, plus the tolerance value</FormFeedback>
			)) : (
				<FormFeedback tooltip>Fragment requirement must be greater than 0</FormFeedback>
			)			
			return (
				<Row className="p-1 justify-content-center">
					<Col xs="4" className="text-center pt-1 border">
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
				<Row className="p-1 justify-content-center">
					<Col xs="6">
						<Button block color="warning" outline={!this.state.warmthFragsEnabled} onClick={onWarmthClick}>{this.state.warmthFragsEnabled ? "Disable" : "Enable"} Warmth Fragments</Button>
					</Col>
				</Row>
				<Row className="p-1 justify-content-center">
					<Col xs="4" className="text-center pt-1 border">
						<span class="align-middle">Warmth Fragment Count</span>
					</Col><Col xs="4">
						<Input type="number" value={this.state.fragCount} disabled={!this.state.warmthFragsEnabled} invalid={!fragCountValid} onChange={(e) => this.setState({fragCount: e.target.value})}/> 
						{fragCountFeedback}
					</Col>
				</Row>
				{fragRows}
				<Row className="p-1 justify-content-center">
					<Col xs="4" className="text-center pt-1 border">
						<span class="align-middle">Logic Tolerance</span>
					</Col><Col xs="4">
						<Input type="number" value={this.state.fragTol} disabled={!this.state.warmthFragsEnabled} invalid={this.state.fragTol <= 0} onChange={(e) => this.setState({fragTol: e.target.value})}/> 
						<FormFeedback tooltip>Tolerance cannot be negative</FormFeedback>
					</Col>
				</Row>
				<Row className="p-1 justify-content-center">
					<Col xs="4" className="text-center pt-1 border">
						<span class="align-middle">Exp Pool</span>
					</Col><Col xs="4">
						<Input type="number" value={this.state.expPool} invalid={this.state.expPool < 100} onChange={(e) => this.setState({expPool: e.target.value})}/> 
						<FormFeedback tooltip>Experience Pool must be at least 100</FormFeedback>
					</Col>
				</Row>
			</TabPane>
		)
	}

	
	getMultiplayerTab = () => {
		let multiplayerButtons = ["Skills", "Dungeon Keys", "Teleporters", "Upgrades", "World Events"].map(stype => (
			<Col xs="4" className="p-2">
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
				<Row className="p-1 justify-content-center">
					<Col xs="4" className="text-center pt-1 border">
						<span class="align-middle">Players</span>
					</Col><Col xs="4">
						<Input type="number" value={this.state.players} disabled={!this.state.tracking} invalid={!playerNumValid} onChange={(e) => this.setState({players: e.target.value})}/> 
						{playerNumFeedback }
					</Col>
				</Row>
				<Row className="p-1 justify-content-center">
					<Col xs="4" className="text-center pt-1 border">
						<span class="align-middle">Seed Sync Mode</span>
					</Col><Col xs="4">
						<UncontrolledButtonDropdown className="w-100">
							<DropdownToggle disabled={this.state.players < 2} color={this.state.players > 1 ? "primary" : "secondary"} caret block> {this.state.coopGenMode} </DropdownToggle>
							<DropdownMenu>
								<DropdownItem active={"Cloned Seeds"===this.state.coopGenMode} onClick={()=> this.setState({coopGenMode: "Cloned Seeds"})}>Cloned Seeds</DropdownItem>
								<DropdownItem active={"Seperate Seeds"===this.state.coopGenMode} onClick={()=> this.setState({coopGenMode: "Seperate Seeds"})}>Seperate Seeds</DropdownItem>
							</DropdownMenu>
						</UncontrolledButtonDropdown>
					</Col>
				</Row>
				<Row className="p-1 justify-content-center">
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
				<Collapse isOpen={this.state.user !== ""}>
					<Row className="p-1 justify-content-center">
						<Col xs="4" className="text-center pt-1 border">
							<span class="align-middle">SyncId (leave blank)</span>
						</Col><Col xs="4">
							<Input type="number" value={this.state.syncId} invalid={!(this.state.syncId === "" || this.state.syncId > 0)} onChange={(e) => this.setState({syncId: e.target.value})}/>
							<FormFeedback tooltip>syncId must be positive</FormFeedback>
						</Col>
					</Row>
				</Collapse>
				<Collapse isOpen={this.state.players > 1 && this.state.coopGameMode === "Co-op"}>
					<Row className="p-2">
						{multiplayerButtons}
						<Col xs="4" className="p-2">
							<Button block outline={!this.state.hints} disabled={this.state.coopGenMode!=="Cloned Seeds"} onClick={() => this.setState({hints: !this.state.hints})}>Show Hints</Button>
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
		urlParams.push("seed=" + (this.state.seed === "" ? Math.round(Math.random() * 1000000000) : this.state.seed))
		
		let url = base_url + "/mkseed?" + urlParams.join("&")
		console.log(url)
		window.location.href = url

	}

	constructor(props) {
		super(props);
		let user = get_param("user");
		let dllTime = get_param("dll_last_update");
		let keymode_options = ["None", "Shards", "Limitkeys", "Clues"];
		this.state = {user: user, activeTab: 'variations', coopGenMode: "Cloned Seeds", coopGameMode: "Co-op", players: 1, tracking: true, dllTime: dllTime, variations: ["forcetrees"], 
					 paths: presets["standard"], keyMode: "Shards", oldKeyMode: "Shards", pathMode: "standard", pathDiff: "Normal", helpTitle: noneTitle, helpSub: noneSub, helpText: noneText, helpExtra: null,
					 keymodeOptions: keymode_options, customSyncId: "", seed: "", fillAlg: "Balanced", shared: ["Skills", "Dungeon Keys", "Teleporters", "World Events"], hints: false,
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

	
	onMode = (mode) => () => {
		let vars = this.state.variations
		if(varPaths.hasOwnProperty(this.state.pathMode))
			vars = listSwap(vars, varPaths[this.state.pathMode])
		if(varPaths.hasOwnProperty(mode))
			vars = listSwap(vars, varPaths[mode])
		
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
		let keyModeOptions = this.state.keymodeOptions.map(mode => (
			<DropdownItem active={mode===this.state.keyMode} onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("keyModes", mode)} onClick={()=> this.setState({keyMode: mode})}>{mode}</DropdownItem>
		))
		let pathDiffOptions = ["Easy", "Normal", "Hard"].map(mode => (
			<DropdownItem active={mode===this.state.pathDiff} onClick={()=> this.setState({pathDiff: mode})}>{mode}</DropdownItem>
		))
		let variationButtons = Object.keys(variations).map(v=> {
			let name = variations[v];
			return (
			<Col xs="4" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("variations", v)} className="p-2">
				<Button block outline={!this.state.variations.includes(v)} onClick={this.onVar(v)}>{name}</Button>
			</Col>
			)		
		})
		let pathButtons = presets["glitched"].map(path=> (
			<Col xs="3" onMouseLeave={this.helpLeave} onMouseEnter={this.helpEnter("logicPaths", path)}  className="p-2">
				<Button block outline={!this.state.paths.includes(path)} disabled={this.pathDisabled(path)} className="text-capitalize" onClick={this.onPath(path)}>{path}</Button>
			</Col>
		))
		let multiplayerTab = this.getMultiplayerTab()
		let warmthFragsTab = this.getWarmthFragsTab()
		
		return (
 		<Container className="pl-4 pr-4 pb-4 pt-2 mt-5">
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
						<Col xs="6">
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
							<span class="align-middle">Mode</span>
						</Col>
						<Col xs="6">
							<UncontrolledButtonDropdown className="w-100">
								<DropdownToggle color="primary" caret block> {this.state.keyMode} </DropdownToggle>
								<DropdownMenu>
									{keyModeOptions}
									<DropdownItem active={this.state.keyMode==="Warmth Frags"} disabled={!this.state.warmthFragsEnabled} onClick={()=> this.setState({keyMode: "Warmth Frags"})}>Warmth Frags</DropdownItem>
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
					<NavItem>
						<NavLink active={this.state.activeTab === 'variations'} onClick={() => { this.setState({activeTab: 'variations'})}}>
						Variations
						</NavLink>
					</NavItem>
					<NavItem>
						<NavLink active={this.state.activeTab === 'logic paths'} onClick={() => { this.setState({activeTab: 'logic paths'})}}>
						Logic Paths
						</NavLink>
					</NavItem>
					<NavItem>
						<NavLink active={this.state.activeTab === 'multiplayer'} onClick={() => { this.setState({activeTab: 'multiplayer'})}}>
						Multiplayer Options
						</NavLink>
					</NavItem>
					<NavItem>
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
					<Card><CardBody>
						<CardTitle className="text-center">{this.state.helpTitle}</CardTitle>
							<CardSubtitle className="p-1 text-center">{this.state.helpSub}</CardSubtitle>
						<CardText>{this.state.helpText}</CardText>
						{this.state.helpExtra}
					</CardBody></Card>
				</Col>
			</Row>

			</Container>
		)

	}
};


