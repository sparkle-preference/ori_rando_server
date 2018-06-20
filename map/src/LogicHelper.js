import './bootstrap.cyborg.min.css';
import './index.css';
import React from 'react';
import { ZoomControl, Map, Tooltip, TileLayer} from 'react-leaflet';
import Leaflet from 'leaflet';
import {NotificationContainer, NotificationManager} from 'react-notifications';
import {Checkbox, CheckboxGroup} from 'react-checkbox-group';
import {download, getStuffType, stuff_types, stuff_by_type, picks_by_type, picks_by_loc, picks_by_zone, presets,
		picks_by_area, zones,  pickup_name, PickupMarkersList, pickup_icons, getMapCrs, hide_opacity, uniq, name_from_str,
		get_param, get_flag, get_int, get_list, get_seed, is_match, str_ids} from './shared_map.js';
import NumericInput from 'react-numeric-input';
import Select from 'react-select';
import 'react-select/dist/react-select.css';
import 'react-notifications/lib/notifications.css';
import {Alert, Button, ButtonGroup, Collapse} from 'reactstrap';
NumericInput.style.input.width = '100%';
NumericInput.style.input.height = '36px';


const crs = getMapCrs();
const DANGEROUS = [-280256, -1680104, -12320248, -10440008]
const DEFAULT_DATA = {
	'-280256': {label: "Energy Cell", value: "EC|1"},
	'-1680104': {label: "100 Experience", value: "EX|100"},
	'-12320248': {label: "100 Experience", value: "EX|100"},
	'-10440008': {label: "100 Experience", value: "EX|100"}
}

const DEFAULT_REACHABLE = {'SunkenGladesRunaway': [["Free"]]};
const DEFAULT_VIEWPORT = {
	  center: [0, 0],
	  zoom: 4,
}

const select_wrap = (items) => items.map((item) => {return {label: item, value: item}})
const paths = Object.keys(presets);
const releveant_picks = ["RB|15","RB|17","RB|19","RB|21", "HC|1", "EC|1", "KS|1", "MS|1", 'SK|0', 'SK|51', 'SK|2', 'SK|3', 'SK|4', 'SK|5', 'SK|8', 'SK|12', 'SK|50', 'SK|14', 'TP|Lost', 'TP|Grotto', 'TP|Grove', 'TP|Forlorn', 'TP|Sorrow', 'TP|Swamp', 'TP|Valley', 'EV|0', 'EV|1', 'EV|2', 'EV|3', 'EV|4']


const consumed_picks = ["KS|1", "MS|1"]
const dev = window.document.URL.includes("devshell")
const base_url = dev ?  "https://8080-dot-3616814-dot-devshell.appspot.com" : "http://orirandocoopserver.appspot.com"


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


function getInventory(state) {
	let activeAreas = state.reachable;
	let placements = state.placements;
	let inventory = {"HC|1": ["Free", "Free", "Free"]}
	Object.keys(activeAreas).forEach(area => {
		if(picks_by_area[area])
			picks_by_area[area].forEach(pick => {
				if(placements[pick.loc])
				{					
					let item = placements[pick.loc].value;
  					if(releveant_picks.includes(item))
  					{
						if(!Object.keys(inventory).includes(item))
							inventory[item] = [];
						inventory[item].push(pick.loc);  						
  					}
				}
			});
	});
	return inventory;
}

function listSwap(list, items)
{
	items.forEach(item => {
		if(list.includes(item))
			list = list.filter(i => i !== item);
		else
			list = list.concat(item);
	})
	return list
}

function getInventoryPane(inventory, that) {
	let items = Object.keys(inventory).map(code => {
		let picklocs = inventory[code];
		let count = picklocs.length;
		let name = name_from_str(code);
		let buttontext = name + (picklocs.length > 1 ? " x" + count : "")
		let color = picklocs.every(elem => that.state.highlight_picks.indexOf(elem) > -1) ? "disabled" : "primary";

		return (
			<div><Button color={color} size="sm" onClick={() => that.setState({highlight_picks: listSwap(that.state.highlight_picks, picklocs.filter(loc => loc !== "Free"))})}>{buttontext}</Button></div>
		)
	})
	return (
	<div>
		<h5>Inventory</h5>
		{items}
	</div>
	)
}

function getPickupMarkers(state, setSelected) {
	let placements = state.placements
	let reachable = Object.keys(state.reachable)
	let markers = []
	Object.keys(picks_by_type).forEach(pre => {
		if(pickup_icons.hasOwnProperty(pre))
			picks_by_type[pre].forEach(pick => {
				let x = pick.hasOwnProperty("_x") ? pick._x : pick.x
				let y = pick.hasOwnProperty("_y") ? pick._y : pick.y
				let icon = pick.hasOwnProperty("icon") ? pick.icon : pickup_icons[pre]
				if(state.highlight_picks.includes(pick.loc))
					icon = new Leaflet.Icon({iconUrl: '/sprites/ori-skul.png', iconSize: new Leaflet.Point(24, 24)})
				let rows = null;
				if(reachable.includes(pick.area))
				{
					if(pick.name === "MapStone") {
					    rows = picks_by_type["MP"].map((ms) => {				    	
					    	return placements[ms.loc] ? (
					    		<tr><td style={{color:'black'}}>
						    		{placements[ms.loc].label}
					    		</td></tr>
					    	) : null
				    	});
					} else if(placements[pick.loc]) {
					  	rows =  (
				    		<tr><td style={{color:'black'}}>
						  		{placements[pick.loc].label}
				    		</td></tr>
					  	)
					}
					let inner = (
						<Tooltip>
							<table>{rows}</table>
						</Tooltip>
					);
					let name = pick.name+"("+pick.x + "," + pick.y +")"
					markers.push({key: name, position: [y, x], inner: inner, icon: icon, onClick: () => setSelected({label: name, value: pick}) });
				}
			});
	});
	return markers
};


class LogicHelper extends React.Component {
  constructor(props) {
    super(props)

    this.state = {seed_in: "", reachable: {...DEFAULT_REACHABLE}, new_areas: {...DEFAULT_REACHABLE}, selected_areas: {...DEFAULT_REACHABLE}, history: {}, step: 0, placements: {...DEFAULT_DATA}, viewport: DEFAULT_VIEWPORT, seedRecieved: false, highlight_picks: []}
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
		this.setState({modes: modes, logicMode: logicMode, pathMode: pathmode, manual_reach: manual_reach,})
	
	};


    selectPickup = (pick, pan=true) => {
		let viewport = this.state.viewport;
		if(pan) {
			let x = pick.value.hasOwnProperty("_x") ? pick.value._x : pick.value.x
			let y = pick.value.hasOwnProperty("_y") ? pick.value._y : pick.value.y
			viewport = {
				  center: [y, x],
				  zoom: 5,
				}
	    	this.setState({viewport: viewport});
	    }
    }

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
    	}
    	this.setState({placements: newplc});

	}

  	_updateReachable = (layers=0) => {
  		if(layers<0 || !this.state.seedRecieved)
  			return
  		if(!this.state.reachable || this.state.reachable === undefined) {
  			this.setState({reachedWith: {}, reachable: {...DEFAULT_REACHABLE}}, () => this._updateReachable(layers));
  			return
  		}
	  	let reachableStuff = {};
  		if(this.state.logicMode === "auto")
  		{
	  		Object.keys(this.state.reachable).forEach((area) => {
	  			if(picks_by_area.hasOwnProperty(area))
		  			picks_by_area[area].forEach((pick) => {
			  			if(this.state.placements[pick.loc])
			  			{
		  					let code = this.state.placements[pick.loc].value;
		  					if(!["SH", "NO","EX"].includes(code.substr(0,2)))
		  						if(reachableStuff.hasOwnProperty(code))
									reachableStuff[code] += 1;
								else
									reachableStuff[code] = 1;
		  				}
  					});
	  		});
		} else {
			["HC", "EC", "AC", "KS", "MS"].forEach((code) => {
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
	  		layers = 0
  		}
  		  	getReachable((state,callback) => this.setState(state,callback),
	  			this.state.modes.join("+"),
	  			Object.keys(reachableStuff).map((key) => key+":"+reachableStuff[key]).join("+"),
	  			() => this._updateReachable(layers-1));

  	};

	
	_onPathModeChange = (n) => paths.includes(n.value) ? this.setState({modes: presets[n.value], pathMode: n.value}) : this.setState({pathMode: n.value})
	toggleLogic = () => {this.setState({display_logic: !this.state.display_logic})};
	resetReachable = () => this.setState({ reachable: {...DEFAULT_REACHABLE}, new_areas: {...DEFAULT_REACHABLE}, selected_areas: {...DEFAULT_REACHABLE}, history: {}, step: 0})
	rewind = () => {
		if(dev)
			console.log(this.state)

		if(this.state.step>0)
			this.setState(prevState => {
				let hist = prevState.history[prevState.step-1];
				return {
					highlight_picks: [],
					reachable: {...hist.reachable}, 
					selected_areas: {...hist.selected_areas}, 
					new_areas: {...hist.new_areas}, 
					step: prevState.step-1};
				}, () => console.log(this.state))
	}

	render() {
		let inventory = getInventory(this.state);
		let inv_pane = getInventoryPane(inventory, this)
		const pickup_markers = ( <PickupMarkersList markers={getPickupMarkers(this.state, this.selectPickup)} />)
		const new_areas_report = Object.keys(this.state.new_areas).map((area) => {
			// new_areas: Map<string,list[list[string]]> 
			// paths: list[list[string]]
			// reqs: list[string]
			// Sunken Glades:
			// > Free
			// > S
			let paths = this.state.new_areas[area];
			let path_rows = paths.map(reqs => ( 
			<li>
				{reqs.join("+")}
			</li>
			));
			return (
			<div>
				<label>{area}</label>
				<ul>
				{path_rows}
				</ul> 
			</div>
			)  
		});
		return (
			<div className="wrapper">
				<Map crs={crs} zoomControl={false} onViewportChanged={this.onViewportChanged} viewport={this.state.viewport}>
			        <ZoomControl position="topright" />
	
					<TileLayer url=' https://ori-tracker.firebaseapp.com/images/ori-map/{z}/{x}/{y}.png' noWrap='true'  />
					{pickup_markers}
			        <NotificationContainer/>
				</Map> 
				<div className="controls">
					<Collapse id="import-wrapper" isOpen={!this.state.seedRecieved}>
						<textarea id="import-seed-area" className="form-control" placeholder="Open your randomizer.dat file with a text editor and paste the full file here" value={this.state.seed_in} onChange={event => {this.parseUploadedSeed(event.target.value) ; this.setState({seedRecieved: true}) }} />
					</Collapse>	
					<div id="file-controls">
						<Button color="primary" onClick={this.resetReachable} >Reset</Button> 
						<Button color="primary" onClick={() => this.rewind()} >{"<"}</Button> 
						<label>{this.state.step}</label>
						<Button color="primary" onClick={() => this._updateReachable(0)} >{">"}</Button> 
					</div>
					{inv_pane}
					<div id="search-wrapper">
						<label for="search">Search</label>
						<input id="search" class="form-control" value={this.state.searchStr} onChange={(event) => this.setState({searchStr: event.target.value})} type="text" />
					</div> 
					<hr style={{ backgroundColor: 'grey', height: 2 }}/>
					{new_areas_report}
					<hr style={{ backgroundColor: 'grey', height: 2 }}/>
					<div id="logic-controls">
						<div id="logic-mode-wrapper">
							<span className="label">Logic Mode:</span>
							<ButtonGroup>
								<Button color="secondary" onClick={() => this.logicModeChanged("auto")} active={this.state.logicMode === "auto" && Object.keys(this.state.placements).length === 1}>Auto</Button>
								<Button color="secondary" onClick={() => this.logicModeChanged("manual")} active={this.state.logicMode === "manual" || Object.keys(this.state.placements).length > 1}>Manual</Button>
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
						<hr style={{ backgroundColor: 'grey', height: 2 }}/>
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
            		{
	            		let reachable = {};
	            		res.split("|").forEach((areaRaw) => {
	            			let areaSplit = areaRaw.split("#");
	            			let name = areaSplit[0];
	            			let reachedWith = areaSplit[1].split("/").map((reqs) => reqs === "" ? ["Free"] : reqs.split('&'));
	            			reachable[name] = reachedWith;
            		});
						setter(prevState => {
		            		if(Object.keys(reachable).filter(area => !Object.keys(prevState.reachable).includes(area)).length === 0)
			            		return {}
							let history = prevState.history;
							let step = prevState.step;
							let old_reachable = prevState.reachable;
							let old_selected = prevState.selected_areas;
							history[step] = {reachable: {...prevState.reachable}, selected_areas: {...prevState.selected_areas}, new_areas: {...prevState.new_areas}}
							let new_areas = {};
							let selected_areas = {};
							Object.keys(reachable).forEach((area) => {
								if(!old_reachable.hasOwnProperty(area))
								{
									old_selected[area] = reachable[area];
									new_areas[area] = reachable[area];
									old_reachable[area] = reachable[area];
								}
								old_reachable[area] = uniq(old_reachable[area].concat(reachable[area]));
								old_selected[area] = uniq(old_selected[area].concat(reachable[area]))
							});
							return {reachable: old_reachable, new_areas: new_areas, selected_areas: old_selected, history: history, step: step+1, highlight_picks: []}
						}, callback)
            		}
            })(xmlHttp.responseText);
    }
    xmlHttp.open("GET", "/plando/reachable?modes="+modes+"&codes="+codes, true);
    xmlHttp.send(null);
}



export default LogicHelper;
