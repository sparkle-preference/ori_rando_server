import React from 'react';
//import {Radio, RadioGroup} from 'react-radio-group';
//import registerServiceWorker from './registerServiceWorker';
import { Map, Tooltip, TileLayer} from 'react-leaflet';
import Leaflet from 'leaflet';
import {Checkbox, CheckboxGroup} from 'react-checkbox-group';
import {download, getStuffType, stuff_types, stuff_by_type, picks_by_type, picks_by_loc, picks_by_zone, presets,
		picks_by_area, zones,  pickup_name, PickupMarkersList, pickup_icons, getMapCrs,
		get_param, get_flag, get_int, get_list, get_seed} from './shared_map.js';
import NumericInput from 'react-numeric-input';
import Select from 'react-select';
import 'react-select/dist/react-select.css';
import {Alert, Button, ButtonGroup, Collapse} from 'reactstrap';
NumericInput.style.input.width = '100%';
NumericInput.style.input.height = '36px';


const DEFAULT_DATA = {
	'-280256': {label: "Energy Cell", value: "EC|1"},
	'-1680104': {label: "100 Experience", value: "EX|100"},
	'-12320248': {label: "100 Experience", value: "EX|100"},
	'-10440008': {label: "100 Experience", value: "EX|100"}
}

const DEFAULT_VIEWPORT = {
	  center: [0, 0],
	  zoom: 4,
	}

const select_wrap = (items) => items.map((item) => {return {label: item, value: item}})
const SEED_FLAGS = ["shards", "clues", "forcetrees", "ohko", "discmaps", "custom"]
const modes_by_key = {"Shared": "Shared", "None": "Solo", "Split": "Shards Race", "Swap": "Swap"}
const COOP_MODES = Object.keys(modes_by_key).map((k) => { return {label: modes_by_key[k], value: k} });
const SHARE_TYPES = ["keys", "events", "upgrades", "teleporters", "skills"]
const crs = getMapCrs();
const DANGEROUS = [-280256, -1680104, -12320248, -10440008]
const paths = Object.keys(presets);


const dev = window.document.URL.includes("devshell")


function getPickupMarkers(pickupTypes, placements, reachable, flags, setSelected, searchStr) {
	let hide_unreachable = flags.includes("hide_unreachable")
	let skip_danger = flags.includes("hide_softlockable")
	let markers = []
	pickupTypes.forEach((pre) => {
		picks_by_type[pre].forEach((pick) => {
			let x = pick.hasOwnProperty("_x") ? pick._x : pick.x
			let y = pick.hasOwnProperty("_y") ? pick._y : pick.y
			let icon = pick.hasOwnProperty("icon") ? pick.icon : pickup_icons[pre]
			let show = !(skip_danger && DANGEROUS.includes(pick.loc));
			if(hide_unreachable && !reachable.includes(pick.area))
						show = false;
			if(show)
			{
				let highlight = false
				let rows = null

				if(pick.name === "MapStone") {
				    rows = picks_by_type["MP"].map((ms) => {
				    	let cols = Object.keys(placements).map((pid) => {
				    		if(!highlight && searchStr && placements[pid][ms.loc].label.toLowerCase().includes(searchStr.toLowerCase()))
				    			highlight = true
					    	if(!placements[pid][ms.loc])
					    		return null
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
			    		if(!highlight && searchStr && placements[pid][pick.loc].label.includes(searchStr.toLowerCase()))
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
				if(highlight)
					icon = new Leaflet.Icon({iconUrl: icon.options.iconUrl, iconSize: new Leaflet.Point(icon.options.iconSize.x*2, icon.options.iconSize.y*2)})
				let name = pick.name+"("+pick.x + "," + pick.y +")"
				let onclick = setSelected({label: name, value: pick})
				markers.push({key: name, position: [y, x], inner: inner, icon: icon, onClick: onclick});
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
  var i = 0
    , j = 0
    , temp = null

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
    let AC = get_int("AC", 0);
    let KS = get_int("KS", 0);
    let MS = get_int("MS", 0);
    let skills = get_list("SK"," ").map(skill => { let parts = skill.split("|"); return {label: pickup_name(parts[0], parts[1]), value: skill}; });
    let events = get_list("EV"," ").map(event => { let parts = event.split("|"); return {label: pickup_name(parts[0], parts[1]), value: event}; });
    let tps  = get_list("TP"," ").map(tp => {return {label: tp + " TP", value: "TP|" + tp}; });
    return {HC: HC, EC: EC, AC: AC, KS: KS, MS: MS, skills: skills, tps: tps, events: events};
}

class PlandoBuiler extends React.Component {
  constructor(props) {
    super(props)

    this.state = {seed_in: "", reachable: ['SunkenGladesRunaway'], placements: {1: {...DEFAULT_DATA}}, player: 1,
    			  fill_opts: {HC: 13, EC: 15, AC: 34, KS: 40, MS: 9, EX: 300, dynamic: true}, viewport: DEFAULT_VIEWPORT, searchStr: "",
		    	  flags: ['hide_unreachable', 'hide_softlockable'], seedFlags:["forcetrees"], share_types: ["keys"], coop_mode: {label: "Solo", value: "None"},
		    	  pickups: ["EX", "Ma", "HC", "SK", "Pl", "KS", "MS", "EC", "AC", "EV"],  display_import: false, display_logic: false, display_coop: false, display_meta: false}
	}

  componentWillMount() {
    let pathmode = get_param("pathmode");
    let manual_reach = get_manual_reach();
    let logicMode, modes;

    if(pathmode && paths.includes(pathmode)) {
		logicMode = 'manual';
		modes = presets[pathmode];
    } else {
    	pathmode = "standard";
        logicMode = "auto";
        modes = ['normal', 'speed', 'dboost-light'];
    }
    let zone = 'Glades';
    let i = 7;
	let lastSelected = {};
	zones.forEach((zone) => {
		let pick = picks_by_zone[zone][0];
		lastSelected[zone] = {label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}
	});
    let pick = picks_by_zone[zone][i];
    let pickup = {label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}
    lastSelected['Glades'] = pickup

	this.setState({zone: zone, pickup: pickup, modes: modes, lastSelected: lastSelected, logicMode: logicMode, pathMode: pathmode,
		    	  manual_reach: manual_reach, stuff_type: "Cells and Stones", stuff: {value: "KS|1", label: "Keystone"}, authed: get_flag("authed")})

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

  }

	_fillToggleDynamic = (n) => this.updateFill("dynamic",!this.state.fill_opts.dynamic)
    _onSelectZone = (newZone, pan=true) => {this.selectPickup(this.state.lastSelected[newZone.value], pan)};
    _onSelectStuffType = (newStuffType) => {
    	this.setState({stuff_type: newStuffType.value});
		if(stuff_by_type[newStuffType.value])
	    	this._onSelectStuff(stuff_by_type[newStuffType.value][0]);
	    else if(newStuffType.value === "Experience")
	    	this._onChangeExp(15,"15");
    	};

    _onChangeExp = (n,s,_) => this.place({label: s, value: "EX|"+s});
	_onSelectStuff = (newStuff) => newStuff ? this.place(newStuff) : false;
	_onPathModeChange = (n) => paths.includes(n.value) ? this.setState({modes: presets[n.value], pathMode: n.value}, () => this._updateReachable()) : this.setState({pathMode: n.value}, () => this._updateReachable())


	logicModeChanged = (newVal) => { this.setState({logicMode: newVal}, () => this._updateReachable()) }


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
		if(!this.state.flags.includes("fill_on_select") && (!newStuff || !newStuff.hasOwnProperty("value"))) {
	    	this.setState({pickup: pick, zone: pick.value.zone, lastSelected: last, viewport: viewport}, () => this.place(this.state.stuff, false));
		} else {
			let newStuffType = getStuffType(newStuff,"Fill");
	    	this.setState({pickup: pick, zone: pick.value.zone, lastSelected: last, viewport: viewport, stuff: newStuff, stuff_type: newStuffType});
		}
    }

    selectPickupCurry = (pick) => {
    	if(pick.value.name === "MapStone")
    		return () => this._onSelectZone({value: "Mapstone"}, false)
    	else
    		return () => this.selectPickup(pick)
	}


    place = (s, doFill = true) => {
    	let old_stuff = this.state.stuff;
    	this.setState(prevState => {
	    	let plc = prevState.placements;
    		plc[prevState.player][prevState.pickup.value.loc] = s;
    		return {placements: plc, stuff: s};
		}, () => this._updateReachable(1));
		let fill_opts = this.state.fill_opts;
		if(fill_opts.dynamic && doFill)
		{
			let old_code = old_stuff ? old_stuff.value.split("|")[0] : "";
			let new_code = s.value.split("|")[0];
			if(old_code === new_code)
				return
			for(let x of ["HC", "AC", "EC", "KS", "MS"]) {
				if(old_code === x)
					fill_opts[x] += 1;
				if(new_code === x)
					fill_opts[x] -= 1;
			}
			this.setState({fill_opts: fill_opts})
		}

    };

    parseUploadedSeed = (seedText) => {
		let lines = seedText.split("\n")
		let newplc = {}
	    for (let i = 1, len = lines.length; i < len; i++) {
	    	let line = lines[i].split("|")
	    	let loc = parseInt(line[0]);
	    	let code = line[1];
	    	let id = (code == "TP") ? line[2] : parseInt(line[2]);
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
			}, () => this._updateReachable(15));

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
				if(code!=="TP")
					id = parseInt(id, 10)
		    	let name = pickup_name(code, id);
		    	let stuff = {label: name, value:code+"|"+id};
		    	if(!newplc.hasOwnProperty(player))
		    		newplc[player] = {}
		    	newplc[player][loc] = stuff;
	    	})
    	}
		this.parseFlagLine(lines[0])
	    this.setState({placements: newplc}, () => this._updateReachable(15));

	}

	parseFlagLine = (flagLine) => {
		let seedFlags = this.state.seedFlags
		let coop_mode = this.state.coop_mode
		let share_types = this.state.share_types
		let display_coop = this.state.display_coop
    	let [flags,seed_name] = flagLine.split("|")
    	if(this.state.seed_name) // don't overwrite name on upload
    		seed_name = this.state.seed_name
    	flags.split(",").forEach((flag) => {
    		if(SEED_FLAGS.includes(flag))
    			seedFlags.push({label: flag, value: flag})
    		else if(flag.startsWith("mode="))
    		{
				display_coop = true
    			let k=flag.substring(5)
				coop_mode={label: modes_by_key[k], value: k}
    		}
    		else if(flag.startsWith("shared="))
    			share_types=select_wrap(flag.substring(7).split("+").filter((id) => SHARE_TYPES.includes(id)))
    	});
    	this.setState({seedFlags: seedFlags, share_types: share_types, coop_mode: coop_mode, display_coop: display_coop, seed_name: seed_name})

	}

	buildFlagLine = () => {
		let flags = []
		flags.concat(this.state.seedFlags.map(f => f.value).filter(f => f))
		let stypes = this.state.share_types.map(f => f.value).filter(f => f)
		if(stypes.length > 0)
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
		this.doFill();
		let outLines = [this.buildFlagLine()]
		let locs = Object.keys(picks_by_loc)
		locs.forEach((loc) => {
			outLines.push(loc+this.state.placements[this.state.player][loc].value+"|"+picks_by_loc[loc].zone)
		})

		return outLines;
	}



	getUploadLines = () => {
		this.doFill();
		let outLines = [this.buildFlagLine()]
		let locs = Object.keys(picks_by_loc)
		let players = Object.keys(this.state.placements);
		locs.forEach((loc) => outLines.push(loc+"|"+picks_by_loc[loc].zone+":"+players.map(player => player+"."+this.state.placements[player][loc].value).join(",")))
		return outLines;
	}

	saveSeed = () => {
		uploadSeed(this.getUploadLines(), this.state.user, this.state.seed_name, this.state.seed_desc, () => this.savedSuccessful())
		this.toggleMeta()
	}

	savedSuccessful = () => {
		alert("Seed was successfully saved!")
	}

	downloadSeed = () => {
		download('randomizer.dat', this.getLines().join("\n"));

	}

  	_updateReachable = (layers=0) => {
  		if(layers<0)
  			return
  		if(!this.state.flags.includes("hide_unreachable"))
  			return
  		if(!this.state.reachable || this.state.reachable === undefined) {
  			this.setState({reachable: ["SunkenGladesRunaway"]}, () => this._updateReachable(layers));
  			return
  		}
	  	let reachableStuff = [];
  		if(this.state.logicMode === "auto" && this.state.player === 1)
  		{
	  		this.state.reachable.forEach((area) => {
	  			if(picks_by_area.hasOwnProperty(area))
		  			picks_by_area[area].forEach((pick) => {
	  				if(this.state.placements[1] && this.state.placements[1].hasOwnProperty(pick.loc))
						reachableStuff.push(this.state.placements[this.state.player][pick.loc].value)
		  			});
	  		});
		} else {
			reachableStuff.push("HC|"+this.state.manual_reach["HC"]);
			reachableStuff.push("EC|"+this.state.manual_reach["EC"]);
			reachableStuff.push("AC|"+this.state.manual_reach["AC"]);
			reachableStuff.push("KS|"+this.state.manual_reach["KS"]);
			reachableStuff.push("MS|"+this.state.manual_reach["MS"]);
			this.state.manual_reach.skills.forEach(skill => {
				reachableStuff.push(skill.value)
	  		});
			this.state.manual_reach.events.forEach(event => {
				reachableStuff.push(event.value)
	  		});
			this.state.manual_reach.tps.forEach(tp => {
				reachableStuff.push(tp.value)
	  		});
	  		layers = 0
  		}
  		  	getReachable((state,callback) => this.setState(state,callback),
	  			this.state.modes.join("+"),
	  			reachableStuff.join("+"),
	  			() => this._updateReachable(layers-1));

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


	render() {
		const pickup_markers = ( <PickupMarkersList markers={getPickupMarkers(this.state.pickups, this.state.placements, this.state.reachable, this.state.flags, this.selectPickupCurry, this.state.searchStr)} />)
		const zone_opts = zones.map(zone => ({label: zone, value: zone}))
		const pickups_opts = picks_by_zone[this.state.zone].map(pick => ({label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}) )
		let alert = this.state.authed ? null : (<Alert color="danger">Please <a href="/login">login</a> to enable saving.</Alert>)
		let save_if_auth = this.state.authed ? ( <Button color="primary" onClick={this.toggleMeta} >Meta/Save</Button> ) : (<Button color="disabled">Meta/Save</Button>)
		let stuff_select;
		if(stuff_by_type[this.state.stuff_type])
		{
			let stuff = stuff_by_type[this.state.stuff_type];
			stuff_select = (
				<div className="pickup-wrapper">
					<span className="label">Pickup: </span>
					<Select clearable={false} options={stuff} onChange={this._onSelectStuff} value={this.state.stuff.value} label={this.state.stuff.label}></Select>
				</div>
			);
		} else if(this.state.stuff_type === "Experience") {
			stuff_select = (
				<div className="pickup-wrapper">
					<span className="label">Amount: </span>
					<NumericInput min={0} value={this.state.stuff.label} onChange={this._onChangeExp}></NumericInput>
				</div>
			);
		} else if (this.state.stuff_type === "Fill") {
			stuff_select = (
				<div id="fill-params">
					<div className="fill-wrapper">
						<span className="label">Health Cells:</span>
						<NumericInput min={0} value={this.state.fill_opts.HC} onChange={(n) => this.updateFill("HC",n)}></NumericInput>
						<span className="label">Energy Cells:</span>
						<NumericInput min={0} value={this.state.fill_opts.EC} onChange={(n) => this.updateFill("EC",n)}></NumericInput>
					</div>
					<div className="fill-wrapper">
						<span className="label">Ability Cells:</span>
						<NumericInput min={0} value={this.state.fill_opts.AC} onChange={(n) => this.updateFill("AC",n)}></NumericInput>
						<span className="label">Keystones:</span>
						<NumericInput min={0} value={this.state.fill_opts.KS} onChange={(n) => this.updateFill("KS",n)}></NumericInput>
					</div>
					<div className="fill-wrapper">
						<span className="label">Mapstones:</span>
						<NumericInput min={0} value={this.state.fill_opts.MS} onChange={(n) => this.updateFill("MS",n)}></NumericInput>
						<span className="label">Max EXP: </span>
						<NumericInput min={0} value={this.state.fill_opts.EX} onChange={(n) => this.updateFill("EX",n)}></NumericInput>
					</div>
					<div className="form-check-label">
						<label className="form-check-label"><input type="checkbox" checked={this.state.fill_opts.dynamic} onChange={this._fillToggleDynamic}/>Update Automatically</label>
					</div>
				</div>
			);
		}
		return (
			<div className="wrapper">
				<Map crs={crs} onViewportChanged={this.onViewportChanged} viewport={this.state.viewport}>
					<TileLayer url=' https://ori-tracker.firebaseapp.com/images/ori-map/{z}/{x}/{y}.png' noWrap='true'  />
					{pickup_markers}
				</Map>
				<div className="controls">
				{alert}
					<div id="file-controls">
						<Button color="primary" onClick={this.toggleImport} >Import</Button>
						<Button color="primary" onClick={this.downloadSeed} >Download Seed</Button>
						{save_if_auth}
					</div>
					<Collapse id="import-wrapper" isOpen={this.state.display_meta}>
						<textarea id="seed-name-input" className="form-control" value={this.state.seed_name} onChange={event => this.setState({seed_name: event.target.value})} />
						<textarea id="seed-desc-input" className="form-control" placeholder="Seed Description" value={this.state.seed_desc} onChange={event => this.setState({seed_desc: event.target.value})} />
						<Button color="primary" onClick={this.saveSeed} >Save</Button>
					</Collapse>
					<Collapse id="import-wrapper" isOpen={this.state.display_import}>
						<textarea id="import-seed-area" className="form-control" placeholder="Paste Seed Here" value={this.state.seed_in} onChange={event => {this.parseUploadedSeed(event.target.value) ; this.toggleImport() }} />
					</Collapse>
					<div className="form-group" id="flag-controls">
						<span className="label">Seed Flags: </span>
						<Select options={select_wrap(SEED_FLAGS)} onChange={(n) => this.setState({seedFlags: n})} multi={true} value={this.state.seedFlags} label={this.state.seedFlags}></Select>
					</div>
					<div id="pickup-controls">
				 		<div className="pickup-wrapper">
							<span className="label">Zone:</span>
							<Select options={zone_opts} onChange={this._onSelectZone} clearable={false} value={this.state.zone} label={this.state.zone}></Select>
						</div>
						<div className="pickup-wrapper">
							<span className="label">Location: </span>
							<Select options={pickups_opts} onChange={this.selectPickup} clearable={false} value={this.state.pickup} label={this.state.pickup.name+"("+this.state.pickup.x + "," + this.state.pickup.y +")"}></Select>
						</div>
						<div className="pickup-wrapper">
							<span className="label">Pickup Type: </span>
							<Select options={stuff_types} style={{maxHeight: "1000px"}} onChange={this._onSelectStuffType} clearable={false} value={this.state.stuff_type} label={this.state.stuff_type}></Select>
						</div>
						{stuff_select}
					</div>
					<div id="display-controls">
						<CheckboxGroup id="display-flags" checkboxDepth={6} name="flags" value={this.state.flags} onChange={this.flagsChanged}>
							<label className="form-check-label"><Checkbox value="hide_unreachable" />Hide Unreachable</label>
							<label className="form-check-label"><Checkbox value="hide_softlockable" />Hide Dangerous</label>
						</CheckboxGroup>
						<div id="search-wrapper">
							<label for="search">Search</label>
							<input id="search" class="form-control" value={this.state.searchStr} onChange={(event) => this.setState({searchStr: event.target.value})} type="text" />
						</div>
					</div>
					<div id="logic-controls">
						<div id="logic-mode-wrapper">
							<span className="label">Logic Mode:</span>
							<ButtonGroup>
								<Button color="secondary" onClick={() => this.logicModeChanged("auto")} active={this.state.logicMode === "auto" && Object.keys(this.state.placements).length === 1}>Auto</Button>
								<Button color="secondary" onClick={() => this.logicModeChanged("manual")} active={this.state.logicMode === "manual" || Object.keys(this.state.placements).length > 1}>Manual</Button>
							</ButtonGroup>
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
									<span className="label">Ability Cells:</span>
									<NumericInput min={0} value={this.state.manual_reach.AC} onChange={(n) => this.updateManual("AC",n)}></NumericInput>
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
									<span className="label">Skills:</span>
									<Select options={stuff_by_type["Skills"]} onChange={(n) => this.updateManual("skills", n)} multi={true} value={this.state.manual_reach.skills} label={this.state.manual_reach.skills}></Select>
								</div>
								<div className="manual-wrapper">
									<span className="label">Teleporters:</span>
									<Select options={stuff_by_type["Teleporters"]} onChange={(n) => this.updateManual("tps", n)} multi={true} value={this.state.manual_reach.tps} label={this.state.manual_reach.tps}></Select>
								</div>
								<div className="manual-wrapper">
									<span className="label">Events:</span>
									<Select options={stuff_by_type["Events"]} onChange={(n) => this.updateManual("events", n)} multi={true} value={this.state.manual_reach.events} label={this.state.manual_reach.events}></Select>
								</div>
							</Collapse>
						</div>
						<div id="logic-mode-controls">
							<div id="logic-presets">
								<Button color="primary" onClick={this.toggleLogic} >Logic Paths:</Button>
								<Select options={paths.map((n) => {return {label: n, value: n}})} onChange={this._onPathModeChange} clearable={false} value={this.state.pathMode} label={this.state.pathMode}></Select>
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
							<Select className="player-select" options={select_wrap(Object.keys(this.state.placements))} onChange={(n) => this.setState({player: n.value})} clearable={false} value={this.state.player} label={this.state.player}></Select>
						</div>
						<Collapse id="coop-wrapper" isOpen={this.state.display_coop}>
				 			<div className="coop-select-wrapper">
								<span className="label">Mode: </span>
								<Select options={COOP_MODES} onChange={(n) => this.setState({coop_mode: n})} clearable={false} value={this.state.coop_mode.value} label={this.state.coop_mode.label}></Select>
							</div>
				 			<div className="coop-select-wrapper">
								<span className="label">Shared: </span>
								<Select options={select_wrap(SHARE_TYPES)} onChange={(n) => this.setState({share_types: n})} clearable={false} multi={true} value={this.state.share_types} label={this.state.share_types}></Select>
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
            	if(res && res.includes("|"))
					setter({reachable: res.split("|")}, callback)
            })(xmlHttp.responseText);
    }
    xmlHttp.open("GET", "/reachable?modes="+modes+"&codes="+codes, true);
    xmlHttp.send(null);
}

function uploadSeed(seedLines, author, seedName, description, callback)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState === 4 && xmlHttp.status === 200)
        	callback()
    }

    xmlHttp.open("POST", "/"+author+"/"+seedName+"/upload", true);
    xmlHttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    xmlHttp.send("seed="+seedLines.join("!")+"&desc="+description);
    let [http, _, oldurl] = window.document.URL.split('/')
    window.history.replaceState('',window.document.title, http+"//"+oldurl+"/"+author+"/"+seedName+"/edit");

}


export default PlandoBuiler;
