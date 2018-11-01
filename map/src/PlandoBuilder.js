import './index.css';
import React from 'react';
import { ZoomControl, Map, Tooltip, TileLayer} from 'react-leaflet';
import Leaflet from 'leaflet';
import {NotificationContainer, NotificationManager} from 'react-notifications';
import 'react-notifications/lib/notifications.css';
import {Checkbox, CheckboxGroup} from 'react-checkbox-group';
import {get_param, get_flag, get_int, get_list, get_seed, presets} from './common.js';
import {download, getStuffType, stuff_types, stuff_by_type, picks_by_type, picks_by_loc, picks_by_zone,
		picks_by_area, zones,  pickup_name, PickupMarkersList, get_icon, getMapCrs, hide_opacity, select_wrap,
		is_match, str_ids, select_styles} from './shared_map.js';
import NumericInput from 'react-numeric-input';
import Select from 'react-select'
import {Creatable} from 'react-select';
import {Alert, Button, Collapse} from 'reactstrap';
import Control from 'react-leaflet-control';
import {Helmet} from 'react-helmet';
import Toggle from 'react-bootstrap-toggle';

NumericInput.style.input.width = '100%';
NumericInput.style.input.height = '36px';

const relevantCodes = ["HC", "AC", "EC", "KS", "MS", "TP", "RB", "EV", "SK"];

const DEFAULT_DATA = {
	'-280256': {label: "Energy Cell", value: "EC|1"},
	'-1680104': {label: "100 Experience", value: "EX|100"},
	'-12320248': {label: "100 Experience", value: "EX|100"}
}

const DEFAULT_REACHABLE = {'SunkenGladesRunaway': [["Free"]]};
const DEFAULT_VIEWPORT = {
	  center: [0, 0],
	  zoom: 4,
	}

const VALID_VARS = ["0XP", "NonProgressMapStones", "ForceMapStones", "ForceTrees", "Hard", "WorldTour", "Open", "OHKO", "Starved", "BonusPickups"]
const VALID_KEYMODES = ["Shards", "Clues", "Limitkeys", "Free"];
const SEED_FLAGS = VALID_VARS.concat(VALID_KEYMODES);
const FLAG_CASEFIX = {};

SEED_FLAGS.forEach(flag => FLAG_CASEFIX[flag.toLowerCase()] = flag);

const modes_by_key = {"Shared": "Shared", "None": "Solo", "Split": "Shards Race"}
const COOP_MODES = Object.keys(modes_by_key).map((k) => { return {label: modes_by_key[k], value: k} });
const SHARE_TYPES = ["WorldEvents", "Misc", "Upgrades", "Teleporters", "Skills"]
const crs = getMapCrs();
const DANGEROUS = [-280256, -1680104, -12320248]
const paths = Object.keys(presets);

const dev = window.document.URL.includes("devshell")
const base_url = dev ?  "https://8080-dot-3616814-dot-devshell.appspot.com" : "http://orirandocoopserver.appspot.com"

function getPickupMarkers(state, setSelected, searchStr) {
	let pickupTypes = state.pickups
	let placements = state.placements
	let reachable = Object.keys(state.reachable)
	let flags = state.flags
	let hide_unreachable = flags.includes("hide_unreachable")
	let skip_danger = flags.includes("hide_softlockable")
	let skip_assigned = flags.includes("hide_assigned")
	let markers = []
	pickupTypes.forEach((pre) => {
		picks_by_type[pre].forEach((pick) => {
			let x = pick.hasOwnProperty("_x") ? pick._x : pick.x
			let y = pick.hasOwnProperty("_y") ? pick._y : pick.y
			let icon = get_icon(pick)
			let show = !(skip_danger && DANGEROUS.includes(pick.loc));
			if(hide_unreachable && !reachable.includes(pick.area))
						show = false;
			if(skip_assigned && placements[state.player].hasOwnProperty(pick.loc))
						show = false;
			if(show)
			{
				let highlight = searchStr ? false : true;
				let rows = null;
				if(pick.name === "MapStone") {
				    rows = picks_by_type["MP"].map((ms) => {
				    	let cols = Object.keys(placements).map((pid) => {
					    	if(!placements[pid][ms.loc])
					    		return null
				    		if(!highlight && searchStr && is_match(placements[pid][ms.loc], searchStr))
				    			highlight = true
					    	return (
					    		<td style={{color:'black'}}>
					    		({pid}) {placements[pid][ms.loc].label}
					    		</td>
					    	)
				    	});
				    	return (
				    	<tr><td style={{color:'black'}}>{ms.area} :</td>
				    	{cols}
				    	</tr>
				    	)
				    });
				} else {
				  	rows = Object.keys(placements).map((pid) => {
			    		if(!highlight && searchStr && placements[pid][pick.loc] && is_match(placements[pid][pick.loc], searchStr))
			    			highlight = true
					  	return (
				    		<tr><td style={{color:'black'}}>
						  		{pid}: {placements[pid][pick.loc] ? placements[pid][pick.loc].label : ""}
				    		</td></tr>
					  	)
			  		});
				}
				let inner = (
					<Tooltip>
						<table>{rows}</table>
					</Tooltip>
				);
				let opacity = highlight ? 1  : hide_opacity
				let name = pick.name+"("+pick.x + "," + pick.y +")"
				let onclick = setSelected({label: name, value: pick})
				markers.push({key: name, position: [y, x], inner: inner, icon: icon, opacity: opacity, onClick: onclick});
			}

		});
	});
	return markers
};

(function(){
    var originalInitTile = Leaflet.GridLayer.prototype._initTile
    Leaflet.GridLayer.include({
        _initTile: function (tile) {
            originalInitTile.call(this, tile);

            var tileSize = this.getTileSize();

            tile.style.width = tileSize.x + 1 + 'px';
            tile.style.height = tileSize.y + 1 + 'px';
        }
    });
})()

function shuffle (array) {
  let i = 0, j = 0, temp = null;

  for (i = array.length - 1; i > 0; i -= 1) {
    j = Math.floor(Math.random() * (i + 1))
    temp = array[i]
    array[i] = array[j]
    array[j] = temp
  }
}

function get_manual_reach() {
	let HC = get_int("HC", 0);
    let EC = get_int("EC", 0);
    let KS = get_int("KS", 0);
    let MS = get_int("MS", 0);
    let AC = get_int("AC", 0);
    let skills = get_list("SK"," ").map(skill => { let parts = skill.split("|"); return {label: pickup_name(parts[0], parts[1]), value: skill}; });
    let events = get_list("EV"," ").map(event => { let parts = event.split("|"); return {label: pickup_name(parts[0], parts[1]), value: event}; });
    let tps  = get_list("TP"," ").map(tp => {return {label: tp + " TP", value: "TP|" + tp}; });
    return {HC: HC, EC: EC, AC: AC, KS: KS, MS: MS, skills: skills, tps: tps, events: events};
}

class PlandoBuiler extends React.Component {
  constructor(props) {
    super(props)

    this.state = {seed_in: "", reachable: {...DEFAULT_REACHABLE}, new_areas: {...DEFAULT_REACHABLE}, placements: {1: {...DEFAULT_DATA}}, player: 1,
    			  fill_opts: {HC: 13, EC: 15, AC: 34, KS: 40, MS: 9, EX: 300, dynamic: false, dumb: false}, viewport: DEFAULT_VIEWPORT, searchStr: "",
		    	  flags: ['hide_unreachable', 'hide_softlockable'], seedFlags: select_wrap(["Open", "ForceTrees"]), share_types: select_wrap(["keys"]), coop_mode: {label: "Solo", value: "None"},
		    	  pickups: ["EX", "Ma", "HC", "SK", "Pl", "KS", "MS", "EC", "AC", "EV", "CS"],  display_import: false, display_logic: false, display_coop: false, display_meta: false}
	}
	
  	

 	componentWillMount() {
 		let spoiler_mode = get_flag("spoiler");
	    let pathmode = get_param("pathmode");
	    let manual_reach = get_manual_reach();
	    let logicMode, modes;
	
	    if(pathmode && paths.includes(pathmode)) {
			logicMode = 'manual';
			modes = presets[pathmode];
	    } else {
	    	pathmode = "standard";
	        logicMode = "auto";
	        modes = presets["standard"];
	    }
	    let zone = 'Glades';
		let lastSelected = {};
		zones.forEach((zone) => {
			let pick = picks_by_zone[zone][0];
			lastSelected[zone] = {label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}
		});
	    let pick = {loc: 919772, name: "EX15", zone: "Glades", area: "SunkenGladesRunaway", y: -227, x: 92};
	    let pickup = {label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}
	    lastSelected['Glades'] = pickup
	
		this.setState({mousePos: {lat: 0, lng: 0}, zone: zone, pickup: pickup, modes: modes, lastSelected: lastSelected, logicMode: logicMode, pathMode: pathmode, logic_helper_mode: spoiler_mode,
			    	  manual_reach: manual_reach, stuff_type: "Cells/Stones", stuff: {value: "KS|1", label: "Keystone"}, authed: get_flag("authed")})
	
	};

	componentDidMount() {
	  	if(this.state.authed)
	  	{
		  	let {rawSeed, user, authed, seed_name, seed_desc} = get_seed()
			this.setState({user: user,  authed: authed, seed_name: seed_name, seed_desc: seed_desc})
			if(rawSeed)
				this.parseSavedSeed(rawSeed)  		
	  	}
		this._updateReachable()
	};

    _onSelectZone = (newZone, pan=true) => {this.selectPickup(this.state.lastSelected[newZone.value], pan)};
    _onSelectStuffType = (newStuffType) => {
    	this.setState({stuff_type: newStuffType.value});
		if(stuff_by_type[newStuffType.value])
	    	this._onSelectStuff(stuff_by_type[newStuffType.value][0]);
	    else if(newStuffType.value === "Experience")
	    	this._onChangeExp(15,"15");
	    else if(newStuffType.value === "Messages")
	    	this.place({label: "Your Message Here", value: "SH|Your Message Here"});
	    else if(newStuffType.value === "Custom")
	    	this.place({label: "NO|1", value: "NO|1"});
    	};

    _onChangeExp = (n,s,_) => this.place({label: s, value: "EX|"+n});
	_onSelectStuff = (newStuff) => newStuff ? this.place(newStuff) : false;
	_onPathModeChange = (n) => paths.includes(n.value) ? this.setState({modes: presets[n.value], pathMode: n.value}, () => this._updateReachable()) : this.setState({pathMode: n.value}, () => this._updateReachable())


	logicModeChanged = (newVal) => { this.setState({logicMode: newVal}, () => this._updateReachable()) }
	autoLogicToggle = () => this.state.logicMode === "auto" ? this.logicModeChanged("manual") : this.logicModeChanged("auto")

	updateManual = (param,val) => this.setState(prevState => {
		let manual_reach = this.state.manual_reach;
		manual_reach[param] = val;
		return {manual_reach: manual_reach}
	},() => this._updateReachable());


	updateFill = (param,val) => this.setState(prevState => {
		let fill_opts = this.state.fill_opts;
		fill_opts[param] = val;
		return {fill_opts: fill_opts}
	});
	  flagsChanged = (newVal) => this.setState({flags: newVal});

	  modesChanged = (newVal) => this.setState({modes: newVal});


    selectPickup = (pick, pan=true) => {
    	let last = this.state.lastSelected;
    	let newStuff = this.state.placements[this.state.player][pick.value.loc];
		last[pick.value.zone] = pick;
		let viewport = this.state.viewport;
		if(pan) {
			let x = pick.value.hasOwnProperty("_x") ? pick.value._x : pick.value.x
			let y = pick.value.hasOwnProperty("_y") ? pick.value._y : pick.value.y
			viewport = {
				  center: [y, x],
				  zoom: 5,
				}
		}
		if(!newStuff || !newStuff.hasOwnProperty("value")) {
	    	this.setState({pickup: pick, zone: pick.value.zone, lastSelected: last, viewport: viewport}, () => this.place(this.state.stuff));
		} else {
			let newStuffType = getStuffType(newStuff, "Experience");
	    	this.setState({pickup: pick, zone: pick.value.zone, lastSelected: last, viewport: viewport, stuff: newStuff, stuff_type: newStuffType});
		}
    }

    selectPickupCurry = (pick) => {
    	if(pick.value.name === "MapStone")
    		return () => this._onSelectZone({value: "Mapstone"}, false)
    	else
    		return () => this.selectPickup(pick)
	}


    place = (s) => {
		if(s.value.length < 4 || s.value[2] !== "|") {
			NotificationManager.warning("Pickup should be in the form XX|Y", "Invalid Pickup!",2000);
				return;
		}
		let reserved_chars = [ ",", "|", ":", ';', "!"];
		let stuff_id = s.value.substr(3);
		if(reserved_chars.some(c => stuff_id.includes(c))) {
				NotificationManager.warning("'" + stuff_id + "' contains a forbidden character", "Invalid Id!",1000);
				return;
		}

    	let r = relevantCodes.includes(this.state.stuff.value.substr(0,2)) ? {...DEFAULT_REACHABLE} : this.state.reachable;
    	this.setState(prevState => {
	    	let plc = prevState.placements;
    		// i hate this i hate this i hate this
	    	if((s.value.substr(0,2) === "EX") && !s.label.endsWith("Experience"))
	    	{
	    		let new_s = {...s}
	    		new_s.label += " Experience"
	    		plc[prevState.player][prevState.pickup.value.loc] = new_s;	    		
	    	} else 
	    		plc[prevState.player][prevState.pickup.value.loc] = s;

    		return {placements: plc, stuff: s, reachable: r};
		}, () => this._updateReachable());
    };

    parseUploadedSeed = (seedText) => {
		let lines = seedText.split("\n")
		let newplc = {}
	    for (let i = 1, len = lines.length; i < len; i++) {
	    	let line = lines[i].split("|")
	    	let loc = parseInt(line[0], 10);
	    	let code = line[1];
	    	let id = str_ids.includes(code) ? line[2] : parseInt(line[2], 10);
	    	let name = pickup_name(code, id);
	    	let stuff = {label: name, value:code+"|"+id};
	    	newplc[loc] = stuff;
    		if(loc === this.state.pickup.value.loc)
				this.setState({stuff_type: getStuffType(stuff), stuff: stuff});
    	}
    	this.parseFlagLine(lines[0])
    	this.setState(prevState => {
	    		let oldplc = prevState.placements;
		    	oldplc[this.state.player] = newplc
		    	return {placements: oldplc}
			}, () => this._updateReachable());

	}


	parseSavedSeed = (seedText) => {
		let lines = seedText.split("\n")
		let newplc = {1: {}}
	    for (let i = 1, len = lines.length; i < len; i++) {
	    	let [loc, pickups] = lines[i].split(":")
	    	loc = parseInt(loc, 10);

	    	pickups.split(",").forEach(pickup => {
				let [player, codeid] = pickup.split(".")
				let [code, id] = codeid.split("|")
				player = parseInt(player, 10)
				if(!str_ids.includes(code))
					id = parseInt(id, 10)
		    	let name = pickup_name(code, id);
		    	let stuff = {label: name, value:code+"|"+id};
		    	if(!newplc.hasOwnProperty(player))
		    		newplc[player] = {}
		    	newplc[player][loc] = stuff;
		    	if(loc === this.state.pickup.value.loc && player === this.state.player)
					this.setState({stuff_type: getStuffType(stuff), stuff: stuff});

	    	})
    	}
		this.parseFlagLine(lines[0])
	    this.setState({placements: newplc}, () => this._updateReachable());

	}

	parseFlagLine = (flagLine) => {
		let seedFlags = this.state.seedFlags.map(f => f.value)
		let coop_mode = this.state.coop_mode
		let share_types = this.state.share_types
		let display_coop = this.state.display_coop
    	let [flags,seed_name] = flagLine.split("|")
    	if(this.state.seed_name) // don't overwrite name on upload
    		seed_name = this.state.seed_name
    	flags.split(",").forEach((flag) => {
    		if(SEED_FLAGS.includes(flag) && !seedFlags.includes(flag))
    			seedFlags.push(flag)
    		else if(flag.startsWith("mode="))
    		{
				display_coop = true
    			let k=flag.substring(5)
				coop_mode={label: modes_by_key[k], value: k}
    		}
    		else if(flag.startsWith("shared="))
    			share_types=select_wrap(flag.substring(7).split("+").filter((id) => SHARE_TYPES.includes(id)))
    	});
    	this.setState({seedFlags: select_wrap(seedFlags), share_types: share_types, coop_mode: coop_mode, display_coop: display_coop, seed_name: seed_name})
	}

	buildFlagLine = () => {
		let flags = []
		flags = flags.concat(this.state.seedFlags.map(f => f.value))
		let stypes = this.state.share_types.map(f => f.value)
		if(stypes.length)
			flags.push("shared="+stypes.join("+"))
		flags.push("mode="+this.state.coop_mode.value)
		return flags.join(",") + "|" + this.state.seed_name
	}


	doFill  = () => {
		let players = Object.keys(this.state.placements);
		let newPlc = {...this.state.placements}
		let locs = Object.keys(picks_by_loc)
		players.forEach(player => {
			let toFill = []
			let {HC, EC, AC, KS, MS, EX} = this.state.fill_opts
			locs.forEach((loc) => {
				if(!this.state.placements[player].hasOwnProperty(loc))
					toFill.push(loc);
			});
			shuffle(toFill);
			toFill.forEach(loc => {
				if(HC > 0) {
					HC -= 1;
					newPlc[player][loc] = {label: "Health Cell", value: "HC|1"}
				}
				else if(EC > 0) {
					EC -= 1;
					newPlc[player][loc] = {label: "Energy Cell", value: "EC|1"}
				}
				else if(AC > 0) {
					AC -= 1;
					newPlc[player][loc] = {label: "Ability Cell", value: "AC|1"}
				}
				else if(KS > 0) {
					KS -= 1;
					newPlc[player][loc] = {label: "Keystone", value: "KS|1"}
				}
				else if(MS > 0) {
					MS -= 1;
					newPlc[player][loc] = {label: "Mapstone", value: "MS|1"}
				}
				else
				{
					let xp = Math.floor(Math.random() * (EX-1) + 1)
					newPlc[player][loc] = {label: xp + " Experience", value: "EX|"+xp}
				}
			});
		})
		this.setState({placements: newPlc})
	}

	getLines = () => {
		let outLines = [this.buildFlagLine()]
		let locs = Object.keys(picks_by_loc).filter(loc => this.state.placements[this.state.player].hasOwnProperty(loc))
		locs.forEach((loc) => {
			outLines.push(loc+"|"+this.state.placements[this.state.player][loc].value+"|"+picks_by_loc[loc].zone)
		})

		return outLines;
	}


	getUploadLines = () => {
		let outLines = [this.buildFlagLine()]
		let locs = Object.keys(picks_by_loc)
		let players = Object.keys(this.state.placements);
		locs.forEach((loc) => {
			let players_at_loc = players.filter(p => this.state.placements[p].hasOwnProperty(loc))
			if(players_at_loc.length > 0)
				outLines.push(loc+"|"+picks_by_loc[loc].zone+":"+players_at_loc.map(player => player+"."+this.state.placements[player][loc].value).join(","))
		})
		return outLines;
	}

	doFillGen = () => {
	    var xmlHttp = new XMLHttpRequest();
	    var parser = this.parseUploadedSeed;
	    xmlHttp.onreadystatechange = function() {
	        if (xmlHttp.readyState === 4)
	            (function(res) {
	            	if(xmlHttp.status !== 200)
		            	NotificationManager.error("Unfinishable Seed", "Failed to complete seed using seedgen", 4000);
					else
						parser(res);
	            })(xmlHttp.responseText);
	    }
  		let codes = []; 
  		Object.keys(this.state.reachable).forEach((area) => {
  			if(picks_by_area.hasOwnProperty(area))
	  			picks_by_area[area].forEach((pick) => {
	  				if(this.state.placements[this.state.player] && this.state.placements[this.state.player].hasOwnProperty(pick.loc)) 
	  					codes.push(pick.loc+":"+this.state.placements[1][pick.loc].value.replace("|",""));
	  			});
  		});

		let mode = "";
		let urlParams = [];
	    this.state.modes.forEach(p => urlParams.push("path="+p));

		this.state.seedFlags.forEach(f => {
			let flag = FLAG_CASEFIX[f.value.toLowerCase()] || f.value
			if(VALID_KEYMODES.includes(flag)) mode = flag
			else if(VALID_VARS.includes(flag)) urlParams.push("var="+flag)
			else urlParams.push("flag="+flag)
		});
		if(mode) urlParams.push("key_mode="+mode)
        if(codes.length > 0)
    		urlParams.push("fass="+codes.join("|"));
		urlParams.push("tracking=Disabled");
		urlParams.push("seed="+Math.round(Math.random() * 1000000000));
		let url = "/plando/fillgen?" + urlParams.join("&");
	    xmlHttp.open("GET", url, true);
	    xmlHttp.send(null);
	}


	saveSeed = () => {
		uploadSeed(this.getUploadLines(), this.state.user, this.state.seed_name, this.state.seed_desc, this.savedSuccessful)
	}

	savedSuccessful = (statusCode) => {
		if(statusCode === 200)
		{
		    window.history.replaceState('',window.document.title, base_url+"/plando/"+this.state.user+"/"+this.state.seed_name+"/edit");
			this.toggleMeta()
			NotificationManager.success("Seed saved", "Success!", 2500);
		}
		else if(statusCode === 404)
				NotificationManager.error("Invalid name", "Failed to save seed!", 4000);
		else if(statusCode >= 500)
				NotificationManager.error("Server error", "Failed to save seed!", 4000);
		else 
				NotificationManager.error("Unknown error", "Failed to save seed!", 4000);
	}

	downloadSeed = () => {
		download('randomizer.dat', this.getLines().join("\n"));
	}

  	_updateReachable = (lastPass=[]) => {
  		let recursive = true
  		if(!this.state.flags.includes("hide_unreachable"))
  			return
  		if(!this.state.reachable || this.state.reachable === undefined) {
  			this.setState({reachable: {...DEFAULT_REACHABLE}}, () => this._updateReachable());
  			return
  		}
		let reachableAreas = Object.keys(this.state.reachable)
		
		// if we've seen every area we can reach in our last iteration, halt
		if(reachableAreas.every(area => lastPass.includes(area)))
			return

	  	let reachableStuff = {};
  		if(this.state.logicMode === "auto" && this.state.player === 1)
  		{
	  		reachableAreas.forEach((area) => {
	  			if(picks_by_area.hasOwnProperty(area))
		  			picks_by_area[area].forEach((pick) => {
	  				if(this.state.placements[1] && this.state.placements[1].hasOwnProperty(pick.loc)) {
	  					let code = this.state.placements[1][pick.loc].value;
	  					if(!["SH", "NO", "EX"].includes(code.substr(0,2)))
	  						if(reachableStuff.hasOwnProperty(code))
								reachableStuff[code] += 1;
							else
								reachableStuff[code] = 1;
		  				}
		  			});
	  		});
		} else {
			["HC", "EC", "KS", "MS", "AC"].forEach((code) => {
				if(this.state.manual_reach[code] > 0)
					reachableStuff[code+"|1"] = this.state.manual_reach[code];
			});
			this.state.manual_reach.skills.forEach(skill => {
				reachableStuff[skill.value] = 1;
	  		});
			this.state.manual_reach.events.forEach(event => {
				reachableStuff[event.value] = 1;
	  		});
			this.state.manual_reach.tps.forEach(tp => {
				reachableStuff[tp.value] = 1;
	  		});
	  		recursive = false
  		}
  		  	getReachable((s, c) => this.setState(s, c),
	  			this.state.modes.join("+") + (this.state.seedFlags.map(f => f.value).includes("Open") ? "+OPEN" : ""),
	  			Object.keys(reachableStuff).map((key) => key+":"+reachableStuff[key]).join("+"),
	  			recursive ? () => this._updateReachable(reachableAreas) : () => null);
  	};

	toggleImport = () => {
		if(dev)
			console.log(this.state)
		this.setState({display_import: !this.state.display_import})
	};
	toggleLogic = () => {this.setState({display_logic: !this.state.display_logic})};
	toggleCoop = () => {this.setState({display_coop: !this.state.display_coop})};
	toggleMeta = () => {this.setState({display_meta: !this.state.display_meta})};
	addPlayer = () => {
    	this.setState(prevState => {
    		let newPlc = prevState.placements;
    		let players = Object.keys(newPlc).length;
    		newPlc[players+1] = {...DEFAULT_DATA}
    		return {placements: newPlc, player: players+1}
		})
	}
	dupePlayer = () => {
		this.setState(prevState => {
			let newPlc = prevState.placements;
			let players = Object.keys(newPlc).length;
			newPlc[players+1] = {...newPlc[prevState.player]}
			return {placements: newPlc, player: players+1}
		})
	}
	removePlayer = () => {
		if(Object.keys(this.state.placements).length > 1)
	    	this.setState(prevState => {
	    		let newPlc = {};
	    		let to_delete = prevState.player;
	    		Object.keys(prevState.placements).forEach((pid) => {
	    			if(pid < to_delete)
	    				newPlc[pid] = prevState.placements[pid]
	    			if(pid > to_delete)
	    				newPlc[pid-1] = prevState.placements[pid]
	    		});
	    		return {placements: newPlc, player: 1}
    		})
	}
	
	resetReachable = () => this.setState({reachable: {...DEFAULT_REACHABLE}})
	
	onFlags = (n) => this.setState({seedFlags: select_wrap(n.map(flag => FLAG_CASEFIX[flag.value.toLowerCase()] || flag.value))})

	render() {
		const pickup_markers = ( <PickupMarkersList markers={getPickupMarkers(this.state, this.selectPickupCurry, this.state.searchStr)} />)
		const zone_opts = zones.map(zone => ({label: zone, value: zone}))
		const pickups_opts = picks_by_zone[this.state.zone].map(pick => ({label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}) )
		let alert = this.state.authed ? null : (<Alert color="danger">Please <a href="/login">login</a> to enable saving.</Alert>)
		let save_if_auth = this.state.authed ? ( <Button color="primary" onClick={this.toggleMeta} >Meta/Save</Button> ) : (<Button color="disabled">Meta/Save</Button>)
		let fill_button = this.state.fill_opts.dumb ? (
			<Button color="warning" onClick={this.doFill} >Fill (Dumb)</Button>
		) : (
			<Button color="success" onClick={this.doFillGen} >Fill</Button>
		)
		let stuff_select;
		if(stuff_by_type[this.state.stuff_type])
		{
			let stuff = stuff_by_type[this.state.stuff_type];
			stuff_select = (
				<div className="pickup-wrapper">
					<span className="label">Pickup: </span>
					<Select styles={select_styles}  isClearable={false} options={stuff} onChange={this._onSelectStuff} value={this.state.stuff}/>
				</div>
			);
		} else if(this.state.stuff_type === "Experience") {
			stuff_select = (
				<div className="pickup-wrapper">
					<span className="label">Amount: </span>
					<NumericInput min={0} value={this.state.stuff.label} onChange={this._onChangeExp}></NumericInput>
				</div>
			);
		} else if(this.state.stuff_type === "Messages") {
			stuff_select = (
				<div className="pickup-wrapper">
					<span className="label">Message: </span>
						<input id="seed-desc-input" type="text" className="form-control" value={this.state.stuff.label} onChange={event => this.place({label: event.target.value, value: "SH|"+event.target.value})} />
				</div>
			);
		} else if(this.state.stuff_type === "Custom") {
			stuff_select = (
				<div className="pickup-wrapper">
					<span className="label">Custom: </span>
						<input id="seed-desc-input" type="text" className="form-control" value={this.state.stuff.label} onChange={event => this.place({label: event.target.value, value: event.target.value})} />
				</div>
			);
			
		} else if (this.state.stuff_type === "Fill") {
			stuff_select = (
				<div id="fill-params">
					<div className="fill-wrapper">
						<span className="label">Health Cells:</span>
						<NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.HC} onChange={(n) => this.updateFill("HC",n)}></NumericInput>
						<span className="label">Energy Cells:</span>
						<NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.EC} onChange={(n) => this.updateFill("EC",n)}></NumericInput>
					</div>
					<div className="fill-wrapper">
						<span className="label">Ability Cells:</span>
						<NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.AC} onChange={(n) => this.updateFill("AC",n)}></NumericInput>
						<span className="label">Keystones:</span>
						<NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.KS} onChange={(n) => this.updateFill("KS",n)}></NumericInput>
					</div>
					<div className="fill-wrapper">
						<span className="label">Mapstones:</span>
						<NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.MS} onChange={(n) => this.updateFill("MS",n)}></NumericInput>
						<span className="label">Max EXP: </span>
						<NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.EX} onChange={(n) => this.updateFill("EX",n)}></NumericInput>
					</div>
					<div className="form-check-label">
						<label className="form-check-label"><input type="checkbox" checked={this.state.fill_opts.dynamic} onChange={() => this.updateFill("dynamic",!this.state.fill_opts.dynamic)}/>Update Automatically</label>
						<label className="form-check-label"><input type="checkbox" checked={this.state.fill_opts.dumb} onChange={() => this.updateFill("dumb",!this.state.fill_opts.dumb)}/>Enable Dumb Fill</label>
					</div>
				</div>
			);
		}
		// 						<Button color="primary" onClick={this.downloadSeed} >Download</Button> not working for someass reason?
		return (
			<div className="wrapper">
		        <NotificationContainer/>
	            <Helmet>
	                <style>{'body { background-color: black}'}</style>
	                <link rel="stylesheet" href="https://gitcdn.github.io/bootstrap-toggle/2.2.2/css/bootstrap-toggle.min.css"/>
					<link rel="stylesheet" href="https://unpkg.com/leaflet@1.3.1/dist/leaflet.css" integrity="sha512-Rksm5RenBEKSKFjgI3a41vrjkw4EVPlJ3+OiI65vTjIdo9brlAacEuKOiQ5OFh7cOI1bkDwLqdLw3Zg0cRJAAQ==" crossorigin=""/>
	            </Helmet>

				<Map crs={crs} onMouseMove={(ev) => this.setState({mousePos: ev.latlng})} zoomControl={false} onViewportChanged={this.onViewportChanged} viewport={this.state.viewport}>
			        <ZoomControl position="topright" />
					<Control position="topleft" >
					<div>
						<Button size="sm" color="disabled">{Math.round(this.state.mousePos.lng)},{Math.round(this.state.mousePos.lat)}</Button>
					</div>
					</Control>	
					<TileLayer url=' https://ori-tracker.firebaseapp.com/images/ori-map/{z}/{x}/{y}.png' noWrap='true'  />
					{pickup_markers}
				</Map>
				<div className="controls">
				{alert}
					<div id="file-controls">
						<Button color="primary" onClick={this.toggleImport} >Import</Button>
						{fill_button}
						{save_if_auth}
					</div>
					<Collapse id="import-wrapper" isOpen={this.state.display_meta}>
						<textarea id="seed-name-input" className="form-control" value={this.state.seed_name} onChange={event => this.setState({seed_name: event.target.value})} />
						<textarea id="seed-desc-input" className="form-control" placeholder="Seed Description" value={this.state.seed_desc} onChange={event => this.setState({seed_desc: event.target.value})} />
						<Button color="primary" onClick={this.saveSeed} >Save</Button>
						<Button color="primary" onClick={() => window.open(window.document.URL.slice(0,-5),'_blank') } >Open Seed Page</Button>
					</Collapse>
					<Collapse id="import-wrapper" isOpen={this.state.display_import}>
						<textarea id="import-seed-area" className="form-control" placeholder="Paste Seed Here" value={this.state.seed_in} onChange={event => {this.parseUploadedSeed(event.target.value) ; this.toggleImport() }} />
					</Collapse>
					<hr style={{ backgroundColor: 'grey', height: 2 }}/>
					<div id="pickup-controls">
						<div className="pickup-wrapper">
							<span className="label">Seed Flags: </span>
							<Creatable styles={select_styles} options={select_wrap(SEED_FLAGS)} onChange={this.onFlags} isMulti={true} value={this.state.seedFlags} label={this.state.seedFlags}/>
						</div>
					</div>
					<hr style={{ backgroundColor: 'grey', height: 2 }}/>
					<div id="pickup-controls">
				 		<div className="pickup-wrapper">
							<span className="label">Zone:</span>
							<Select styles={select_styles} options={zone_opts} onChange={this._onSelectZone} clearable={false} value={select_wrap(this.state.zone)}></Select>
						</div>
						<div className="pickup-wrapper">
							<span className="label">Location: </span>
							<Select styles={select_styles} options={pickups_opts} onChange={this.selectPickup} clearable={false} value={this.state.pickup} label={this.state.pickup.name+"("+this.state.pickup.x + "," + this.state.pickup.y +")"}></Select>
						</div>
						<div className="pickup-wrapper">
							<span className="label">Pickup Type: </span>
							<Select styles={select_styles} options={stuff_types} onChange={this._onSelectStuffType} clearable={false} value={select_wrap(this.state.stuff_type)}></Select>
						</div>
						{stuff_select}
					</div>
					<hr style={{ backgroundColor: 'grey', height: 2 }}/>
					<div id="display-controls">
						<CheckboxGroup id="display-flags" checkboxDepth={6} name="flags" value={this.state.flags} onChange={this.flagsChanged}>
							<label className="form-check-label"><Checkbox value="hide_unreachable" />Hide Unreachable</label>
							<label className="form-check-label"><Checkbox value="hide_assigned" />Hide Assigned</label>
							<label className="form-check-label"><Checkbox value="hide_softlockable" />Hide Dangerous</label>
						</CheckboxGroup>
					<hr style={{ backgroundColor: 'grey', height: 2 }}/>
						<div id="search-wrapper">
							<label for="search">Search</label>
							<input id="search" class="form-control" value={this.state.searchStr} onChange={(event) => this.setState({searchStr: event.target.value})} type="text" />
						</div>
					</div>
					<hr style={{ backgroundColor: 'grey', height: 2 }}/>
					<div id="logic-controls">
						<div id="logic-mode-wrapper">
							<span className="label">Automatic Logic:</span>
							<Toggle
					          onClick={this.autoLogicToggle}
					          on="Enabled"
					          off="Disabled"
					          size="xs"
					          onstyle="primary"
					          offstyle="secondary"
					          active={this.state.logicMode === "auto" && Object.keys(this.state.placements).length === 1}
					          disabled={Object.keys(this.state.placements).length > 1}
					        />
							<Collapse id="manual-controls" isOpen={this.state.logicMode === "manual" || this.state.player > 1}>
								<div className="manual-wrapper">
									<span className="label">Health Cells:</span>
									<NumericInput min={0} value={this.state.manual_reach.HC} onChange={(n) => this.updateManual("HC",n)}></NumericInput>
								</div>
								<div className="manual-wrapper">
									<span className="label">Energy Cells:</span>
									<NumericInput min={0} value={this.state.manual_reach.EC} onChange={(n) => this.updateManual("EC",n)}></NumericInput>
								</div>
								<div className="manual-wrapper">
									<span className="label">Keystones:</span>
									<NumericInput min={0} value={this.state.manual_reach.KS} onChange={(n) => this.updateManual("KS",n)}></NumericInput>
								</div>
								<div className="manual-wrapper">
									<span className="label">Mapstones:</span>
									<NumericInput min={0} value={this.state.manual_reach.MS} onChange={(n) => this.updateManual("MS",n)}></NumericInput>
								</div>
								<div className="manual-wrapper">
									<Select styles={select_styles} placeholder="Skills" options={stuff_by_type["Skills"]} onChange={(n) => this.updateManual("skills", n)} isMulti={true} value={this.state.manual_reach.skills}></Select>
								</div>
								<div className="manual-wrapper">
									<Select styles={select_styles} placeholder="Teleporters" options={stuff_by_type["Teleporters"]} onChange={(n) => this.updateManual("tps", n)} isMulti={true} value={this.state.manual_reach.tps}></Select>
								</div>
								<div className="manual-wrapper">
									<Select styles={select_styles} placeholder="Events" options={stuff_by_type["Events"]} onChange={(n) => this.updateManual("events", n)} isMulti={true} value={this.state.manual_reach.events}></Select>
								</div>
							</Collapse>
						</div>
						<hr style={{ backgroundColor: 'grey', height: 2 }}/>
						<div id="logic-mode-controls">
							<div id="logic-presets">
								<Button color="primary" onClick={this.toggleLogic} >Logic Paths:</Button>
								<Select styles={select_styles}   options={select_wrap(paths)} onChange={this._onPathModeChange} clearable={false} value={select_wrap(this.state.pathMode)}></Select>
							</div>
							<Collapse id="logic-options-wrapper" isOpen={this.state.display_logic}>
								<CheckboxGroup id="logic-options" checkboxDepth={2} name="modes" value={this.state.modes} onChange={this.modesChanged}>
									<label className="checkbox-label"><Checkbox value="normal" /> normal</label>
									<label className="checkbox-label"><Checkbox value="speed" /> speed</label>
									<label className="checkbox-label"><Checkbox value="extended" /> extended</label>
									<label className="checkbox-label"><Checkbox value="speed-lure" /> speed-lure</label>
									<label className="checkbox-label"><Checkbox value="lure" /> lure</label>
									<label className="checkbox-label"><Checkbox value="lure-hard" /> lure-hard</label>
									<label className="checkbox-label"><Checkbox value="dboost-light" /> dboost-light</label>
									<label className="checkbox-label"><Checkbox value="dboost" /> dboost</label>
									<label className="checkbox-label"><Checkbox value="dboost-hard" /> dboost-hard</label>
									<label className="checkbox-label"><Checkbox value="cdash" /> cdash</label>
									<label className="checkbox-label"><Checkbox value="cdash-farming" /> cdash-farming</label>
									<label className="checkbox-label"><Checkbox value="extreme" /> extreme</label>
									<label className="checkbox-label"><Checkbox value="extended-damage" /> extended-damage</label>
									<label className="checkbox-label"><Checkbox value="timed-level" /> timed-level</label>
									<label className="checkbox-label"><Checkbox value="dbash" /> dbash</label>
									<label className="checkbox-label"><Checkbox value="glitched" /> glitched</label>
								</CheckboxGroup>
							</Collapse>
						</div>
					</div>
					<div id="coop-controls">
						<div className="basic-coop-options">
							<Button color="primary" onClick={this.toggleCoop}>Multiplayer Controls</Button>
							<span className="label">Player: </span>
							<Select styles={select_styles}   className="player-select" options={select_wrap(Object.keys(this.state.placements))} onChange={(n) => this.setState({player: n.value})} clearable={false} value={select_wrap(this.state.player)} label={this.state.player}></Select>
						</div>
						<Collapse id="coop-wrapper" isOpen={this.state.display_coop}>
				 			<div className="coop-select-wrapper">
								<span className="label">Mode: </span>
								<Select styles={select_styles}   options={COOP_MODES} onChange={(n) => this.setState({coop_mode: n})} clearable={false} value={this.state.coop_mode}></Select>
							</div>
				 			<div className="coop-select-wrapper">
								<span className="label">Shared: </span>
								<Select styles={select_styles}   options={select_wrap(SHARE_TYPES)} onChange={(n) => this.setState({share_types: n})} clearable={false} isMulti={true} value={this.state.share_types}></Select>
							</div>
							<div>
								<Button color="primary" onClick={this.addPlayer}>Add Player</Button>
								<Button color="primary" onClick={this.dupePlayer}>Duplicate</Button>
								<Button color="secondary" onClick={this.removePlayer} active={Object.keys(this.state.placements).length > 1}>Remove Player</Button>
							</div>
						</Collapse>
					</div>
				</div>
			</div>
		)
	}
}

function getReachable(setter, modes, codes, callback)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState === 4 && xmlHttp.status === 200)
            (function(res) {
                    let new_reachables = JSON.parse(res);
					setter(prevState => {
						let reachable = prevState.reachable;
						Object.keys(new_reachables).forEach((area) => {
							if(!reachable.hasOwnProperty(area))
								reachable[area] = new_reachables[area];
							reachable[area] = reachable[area].concat(new_reachables[area]);

						});
						return {reachable: reachable}
					}, callback)
            })(xmlHttp.responseText);
    }
    xmlHttp.open("GET", "/plando/reachable?modes="+modes+"&codes="+codes, true);
    xmlHttp.send(null);
}



function uploadSeed(seedLines, author, seedName, description, callback)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState === 4)
        	callback(xmlHttp.status)
    }
	let url = "/plando/"+author+"/"+seedName+"/upload";
	let old_name = window.document.URL.split("/")[5];
	if(old_name !== seedName) {
		url += "?old_name=" + old_name
	}
    xmlHttp.open("POST", url, true);
    xmlHttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    xmlHttp.send(encodeURI("seed="+seedLines.join("!")+"&desc="+description));

}


export default PlandoBuiler;
