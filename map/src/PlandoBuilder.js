import React from 'react';
//import {Radio, RadioGroup} from 'react-radio-group';
//import registerServiceWorker from './registerServiceWorker';
import { Map, Tooltip, TileLayer} from 'react-leaflet';
import Leaflet from 'leaflet';
import {Checkbox, CheckboxGroup} from 'react-checkbox-group';
import {download, getStuffType, stuff_types, stuff_by_type, picks_by_type, picks_by_loc, picks_by_zone, presets,
		picks_by_area, zones,  pickup_name, PickupMarkersList, pickup_icons, getMapCrs} from './shared_map.js';
import NumericInput from 'react-numeric-input';
import Select from 'react-select';
import 'react-select/dist/react-select.css';
import {Button, ButtonGroup, Collapse} from 'reactstrap';
NumericInput.style.input.width = '100%';
NumericInput.style.input.height = '30px';



const DEFAULT_VIEWPORT = {
	  center: [0, 0],
	  zoom: 4,
	}

const crs = getMapCrs();

const paths = Object.keys(presets);



function getPickupMarkers(pickupTypes, placements, reachable, flags, setSelected) {
	let hide_unreachable = flags.includes("hide_unreachable")
	let markers = []
	pickupTypes.forEach((pre) => {
		picks_by_type[pre].forEach((pick) => {
			let x = pick.hasOwnProperty("_x") ? pick._x : pick.x
			let y = pick.hasOwnProperty("_y") ? pick._y : pick.y
			let icon = pick.hasOwnProperty("icon") ? pick.icon : pickup_icons[pre]
			let show = true;
			if(hide_unreachable && !reachable.includes(pick.area))
						show = false;
			if(show)
			{
				let inner = null

				if(pick.name === "MapStone") {
				    let rows = picks_by_type["MP"].map((ms) => {
				    	if(!placements[ms.loc])
				    		return null
				    	return (
				    		<tr><td style={{color:'black'}}>
				    		{ms.area + ": " + placements[ms.loc].label}
				    		</td></tr>
				    	)
				    });
					inner = (
					<Tooltip>
					<table>{rows}</table>
					</Tooltip>
					)
				} else {
					let text = placements[pick.loc] ? placements[pick.loc].label : "";
					inner = (
					<Tooltip>
						<span>{text}</span>
					</Tooltip>
					);
				}
				let name = pick.name+"("+pick.x + "," + pick.y +")"
				let onclick = setSelected({label: name, value: pick})
				markers.push({key: name, position: [y, x], inner: inner, icon: icon, onClick: onclick});
			}

		});
	});
	return markers
};

// Work-around for lines between tiles on fractional zoom levels
// https://github.com/Leaflet/Leaflet/issues/3575
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


class PlandoBuiler extends React.Component {
  constructor(props) {
    super(props)
    let pathmode = document.getElementsByClassName("pathmode-holder")[0].id;
    let HC = parseInt(document.getElementsByClassName("HC-holder")[0].id) || 0;
    let EC = parseInt(document.getElementsByClassName("EC-holder")[0].id) || 0;
    let AC = parseInt(document.getElementsByClassName("AC-holder")[0].id) || 0;
    let KS = parseInt(document.getElementsByClassName("KS-holder")[0].id) || 0;
    let skillsRaw = document.getElementsByClassName("SK-holder")[0].id
    let skills = (skillsRaw !== "None") ? skillsRaw.split(" ").map(skill => {
    	let parts = skill.split("|")
    	return {label: pickup_name(parts[0], parts[1]), value: skill}
    }) : [];
	let tpsRaw = document.getElementsByClassName("TP-holder")[0].id;
    let tps  = (tpsRaw !== "None") ? tpsRaw.split(" ").map(tp => {return {label: tp + " TP", value: "TP|" + tp}; }) : [];
    let manual_reach = {HC: HC, EC: EC, AC: AC, KS: KS, MS: 9, skills: skills, tps: tps};
    let logicMode = "auto";
    let modes = ['normal', 'speed', 'dboost-light'];
    if(paths.includes(pathmode)) {
		logicMode = 'manual';
		modes = presets[pathmode];
    } else {
    	pathmode = "standard";
    }
    let zone = 'Glades';
    let i = 7;
		let display_import: false;
		let display_logic: false;
	let lastSelected = {};
	zones.forEach((zone) => {
		let pick = picks_by_zone[zone][0];
		lastSelected[zone] = {label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}
	});
    let pick = picks_by_zone[zone][i];
    let pickup = {label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}
    lastSelected['Glades'] = pickup
    this.state = {zone: zone, pickup: pickup, seed_in: "", reachable: ['SunkenGladesRunaway'], modes: modes,
    			  lastSelected: lastSelected, placements: {}, stuff_type: "Cells and Stones", stuff: {value: "KS|1", label: "Keystone"},
    			  fill_opts: {HC: 13, EC: 15, AC: 34, KS: 40, MS: 9, EX: 300, dynamic: true}, viewport: DEFAULT_VIEWPORT,
		    	  flags: ['show_pickups', 'hide_unreachable'], seedFlags:"shards,forcetrees,Sync1002.1,mode=4,Custom|Plando",
		    	  pickups: ["EX", "Ma", "HC", "SK", "Pl", "KS", "MS", "EC", "AC", "EV"], logicMode: logicMode, pathMode: pathmode,
		    	  manual_reach: manual_reach, display_import: display_import, display_logic: display_logic}
	this._updateReachable()
  };

	_onSeedFlags = (event) => { this.setState({seedFlags: event.target.value}) }

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
    	let newStuff = this.state.placements[pick.value.loc];
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
    		plc[prevState.pickup.value.loc] = s;
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

	tryParseSeed = (event) => {
		let seedText = event.target.value
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
    		{
				this.setState({stuff_type: getStuffType(stuff), stuff: stuff});
    		}
    	}
    	this.setState(prevState => {
	    	let oldplc = prevState.placements;
			let plc = Object.assign(newplc, oldplc);
    		return {placements: plc, seedFlags: lines[0]}
		}, () => this._updateReachable(15));
	}

	downloadSeed = () => {
		let outLines = [this.state.seedFlags, "-280256|EC|1|Glades", "-1680104|EX|100|Grove", "-12320248|EX|100|Forlorn", "-10440008|EX|100|Misty"]
		let locs = Object.keys(picks_by_loc)
		console.log(locs)
		let toFill = []
		let {HC, EC, AC, KS, MS, EX} = this.state.fill_opts
		locs.forEach((loc) => {
			if(this.state.placements.hasOwnProperty(loc))
				outLines.push(loc+"|"+this.state.placements[loc].value+"|"+picks_by_loc[loc].zone);
			else
				toFill.push(loc);

		});
		console.log(toFill);
		shuffle(toFill);
		toFill.forEach((loc) => {
			if(HC > 0) {
				HC -= 1;
				outLines.push(loc+"|HC|1|"+picks_by_loc[loc].zone);
			}
			else if(EC > 0) {
				EC -= 1;
				outLines.push(loc+"|EC|1|"+picks_by_loc[loc].zone);
			}
			else if(AC > 0) {
				AC -= 1;
				outLines.push(loc+"|AC|1|"+picks_by_loc[loc].zone);
			}
			else if(KS > 0) {
				KS -= 1;
				outLines.push(loc+"|KS|1|"+picks_by_loc[loc].zone);
			}
			else if(MS > 0) {
				MS -= 1;
				outLines.push(loc+"|MS|1|"+picks_by_loc[loc].zone);
			}
			else
				outLines.push(loc+"|EX|"+ Math.floor(Math.random() * (EX-1) + 1)+"|"+picks_by_loc[loc].zone);
		});
		download('randomizer.dat', outLines.join("\n"));

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
  		if(this.state.logicMode === "auto")
  		{
	  		this.state.reachable.forEach((area) => {
	  			if(picks_by_area.hasOwnProperty(area))
		  			picks_by_area[area].forEach((pick) => {
		  				if(this.state.placements.hasOwnProperty(pick.loc))
							reachableStuff.push(this.state.placements[pick.loc].value)
		  			});
	  		});
		} else {
			reachableStuff.push("HC|"+this.state.manual_reach["HC"]);
			reachableStuff.push("EC|"+this.state.manual_reach["EC"]);
			reachableStuff.push("AC|"+this.state.manual_reach["AC"]);
			reachableStuff.push("KS|"+this.state.manual_reach["KS"]);
			this.state.manual_reach.skills.forEach(skill => {
				reachableStuff.push(skill.value)
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

	toggleImport = () => {this.setState({display_import: !this.state.display_import})};
	toggleLogic = () => {this.setState({display_logic: !this.state.display_logic})};

	render() {
		const pickup_markers = this.state.flags.includes('show_pickups') ? ( <PickupMarkersList markers={getPickupMarkers(this.state.pickups, this.state.placements, this.state.reachable, this.state.flags, this.selectPickupCurry )} />) : null
		const zone_opts = zones.map(zone => ({label: zone, value: zone}))
		const pickups_opts = picks_by_zone[this.state.zone].map(pick => ({label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}) )

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
					<div id="file-controls">
						<Button color="primary" onClick={this.toggleImport} >Import</Button>
						<Button color="primary" onClick={this.downloadSeed} >Download Seed</Button>
						<Button color="primary">Save</Button>
					</div>
					<Collapse id="import-wrapper" isOpen={this.state.display_import}>
						<textarea id="import-seed-area" className="form-control" placeholder="Paste Seed Here" value={this.state.seed_in} onChange={this.tryParseSeed} />
					</Collapse>
					<div className="form-group" id="flag-controls">
						<label for="seed-flags" className="textinput-label">Seed Flags</label>
						<input type="text" id="seed-flags" class="form-control" value={this.state.seedFlags} onChange={this._onSeedFlags} />
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
							<label className="form-check-label"><Checkbox value="hide_unreachable" /> Hide Unreachable</label>
							<label className="form-check-label"><Checkbox value="show_pickups" /> Show Pickups</label>
							<label className="form-check-label"><Checkbox value="fill_on_select" /> Fill on Select</label>
						</CheckboxGroup>
						<div id="search-wrapper">
							<label for="search">Search</label>
							<input id="search" class="form-control" type="text" />
						</div>
					</div>
					<div id="logic-controls">
						<div id="logic-mode-wrapper">
							<span className="label">Logic Mode:</span>
							<ButtonGroup>
								<Button color="secondary" onClick={() => this.logicModeChanged("auto")} active={this.state.logicMode === "auto"}>Auto</Button>
								<Button color="secondary" onClick={() => this.logicModeChanged("manual")} active={this.state.logicMode === "manual"}>Manual</Button>
							</ButtonGroup>
							<Collapse id="manual-controls" isOpen={this.state.logicMode === "manual"}>
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
									<span className="label">Skills:</span>
									<Select options={stuff_by_type["Skills"]} onChange={(n) => this.updateManual("skills", n)} multi={true} value={this.state.manual_reach.skills} label={this.state.manual_reach.skills}></Select>
								</div>
								<div className="manual-wrapper">
									<span className="label">Teleporters:</span>
									<Select options={stuff_by_type["Teleporters"]} onChange={(n) => this.updateManual("tps", n)} multi={true} value={this.state.manual_reach.tps} label={this.state.manual_reach.tps}></Select>
								</div>
							</Collapse>
						</div>
						<div id="logic-mode-controls">
							<div id="logic-presets">
								<Button color="primary" onClick={this.toggleLogic} >Logic Paths:</Button>
								<Select options={paths.map((n) => {return {label: n, value: n}})} onChange={this._onPathModeChange} clearable={false} value={this.state.pathMode} label={this.state.pathMode}></Select>
							</div>
							<Collapse id="logic-options-wrapper" isOpen={this.state.display_logic}>
								<CheckboxGroup id="logic-options" checkboxDepth={4} name="modes" value={this.state.modes} onChange={this.modesChanged}>
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
    xmlHttp.open("GET", "/reachable?modes="+modes+"&codes="+codes, true); // true for asynchronous
    xmlHttp.send(null);
}


export default PlandoBuiler;
