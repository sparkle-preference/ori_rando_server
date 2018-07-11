import './index.css';
import React from 'react';
import { ZoomControl, Map, Tooltip, TileLayer} from 'react-leaflet';
import Leaflet from 'leaflet';
import {Checkbox, CheckboxGroup} from 'react-checkbox-group';
import {stuff_by_type, picks_by_type, presets, picks_by_area, pickup_name, PickupMarkersList, get_icon, getMapCrs, 
		name_from_str, get_param, get_int, get_list, str_ids, select_styles, select_wrap, listSwap} from './shared_map.js';
import NumericInput from 'react-numeric-input';
import Select from 'react-select';
import {Button, ButtonGroup, Collapse} from 'reactstrap';
import Control from 'react-leaflet-control';
import Dropzone from 'react-dropzone'
import {Helmet} from 'react-helmet';

NumericInput.style.input.width = '100%';
NumericInput.style.input.height = '36px';


const crs = getMapCrs();
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

const paths = Object.keys(presets);
const releveant_picks = ["RB|15","RB|17","RB|19","RB|21", "HC|1", "EC|1", "KS|1", "MS|1", 'SK|0', 'SK|51', 'SK|2', 'SK|3', 'SK|4', 'SK|5', 'SK|8', 'SK|12', 'SK|50', 'SK|14', 'TP|Lost', 'TP|Grotto', 'TP|Grove', 'TP|Forlorn', 'TP|Sorrow', 'TP|Swamp', 'TP|Valley', 'EV|0', 'EV|1', 'EV|2', 'EV|3', 'EV|4']

// patch picks_by_area to include mapstone areas because haha fuck
picks_by_type["Ma"].forEach(pick => {
	picks_by_area[pick.area] = [pick]
})

const xml_name_to_code = {
'KS': 'KS|1',
'MS': 'MS|1',
'EC': 'EC|1',
'HC': 'HC|1',
'TPSwamp': 'TP|Swamp',
'TPGrove': 'TP|Grove',
'TPGrotto': 'TP|Grotto',
'TPValley': 'TP|Valley',
'TPSorrow': 'TP|Sorrow',
'TPForlorn': 'TP|Forlorn',
'Bash': 'SK|0',
'ChargeFlame': 'SK|2',
'WallJump': 'SK|3',
'Stomp': 'SK|4',
'DoubleJump': 'SK|5',
'ChargeJump': 'SK|8',
'Climb': 'SK|12',
'Glide': 'SK|14',
'Dash': 'SK|50',
'Grenade': 'SK|51',
'GinsoKey': 'EV|0',
'Water': 'EV|1',
'ForlornKey': 'EV|2',
'Wind': 'EV|3',
'HoruKey': 'EV|4'
}

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


const code_to_group = {};
Object.keys(stuff_by_type).forEach(group => {
	stuff_by_type[group].forEach(stuff => {
		code_to_group[stuff.value] = group
	});
});

function getInventory(state) {
	let activeAreas = state.reachable;
	let placements = state.placements;
	let inventory = {"Cells and Stones": {"HC|1": ["Free", "Free", "Free"]}}
	Object.keys(activeAreas).forEach(area => {
		if(picks_by_area[area])
			picks_by_area[area].forEach(pick => {
				if(placements[pick.loc])
				{					
					let item = placements[pick.loc].value;
					let group = code_to_group[item];
  					if(releveant_picks.includes(item))
  					{
  						if(!Object.keys(inventory).includes(group))
  							inventory[group] = {};
						if(!Object.keys(inventory[group]).includes(item))
							inventory[group][item] = [];
						inventory[group][item].push(pick);  						
  					}
				}
			});
	});
	return inventory;
}


function getInventoryPane(inventory, that) {
	let groups = Object.keys(inventory).map(group => {
		let items = Object.keys(inventory[group]).map(code => {			
			let picks = inventory[group][code];
			let count = picks.length;
			let name = name_from_str(code);
			let buttontext = name + (count > 1 ? " x" + count : "")

			return (
				<span><Button color={"danger"} disabled={picks.every(pick => pick === "Free")} outline={that.state.selected !== name} onClick={() => that.onGroupClick(picks, name)}>{buttontext}</Button></span>
			)
		});
		return (
		<div>
			<div>{group}:</div>
			{items}
			<hr style={{ backgroundColor: 'grey', height: 1 }}/>
		</div>
		) 
	});
	return (
	<div>
		<div style={{textAlign: 'center', fontSize: '1.2em' }}>Inventory</div>
		{groups}
	</div>
	)
}

function getAreasPane(inventory, that) {

		let area_groups = Object.keys(that.state.new_areas).filter(area => area.substr(0,2) !== "MS").map((area) => {
			let is_selected = that.state.selected_area === area;
			let paths = that.state.new_areas[area];
			let path_rows = is_selected ? paths.map(reqs => {
				if(reqs.length === 1 && reqs[0] === "Free")
					return null;
					
				
				let buttons = reqs.map(req => {
					let count = 1;
					if(req.includes("(")) {
						count = req.substr(3,req.indexOf(")")-3)
						req = req.substr(0,2)
					}
					if(!xml_name_to_code.hasOwnProperty(req))
						return null;
					let code = xml_name_to_code[req]
					if(!code_to_group.hasOwnProperty(code))
						return null;
					let group = code_to_group[code]
					let picks = inventory[group][code]
					let name = name_from_str(code)+ (count > 1 ? " x" + count : "")
					return (
						<Button color={"danger"} outline={that.state.selected !== name} size="sm" onClick={() => that.onGroupClick(picks, name)}>{name}</Button>
					)
				}).reduce((accu, elem) => accu === null ? [elem] : [...accu, <span>+</span>, elem] , null);
				return ( 
					<li>
					{buttons}
					</li>
				);
			}) : []; 
			let area_name = area.split(/(?=[A-Z])/).join(" ");
			let unlocked_with = path_rows.filter(x => x !== null).length > 0 ? (<div>unlocked with:</div>) : null
			if(!picks_by_area.hasOwnProperty(area))
				return null
			return (
			<div>
				<Button color={is_selected ? "warning" : "danger"} outline={that.state.selected !== area}  onClick={() => that.setState({selected_area: area}, () => that.onGroupClick(picks_by_area[area], area))}>{area_name}</Button>
				<Collapse isOpen={is_selected}>
					{unlocked_with}
					<ul>
					{path_rows}
					</ul> 
				</Collapse>
			</div>
			)  
		});
		return (
			<div>
				<div style={{textAlign: 'center', fontSize: '1.2em' }}>New Reachable Areas</div>
				{area_groups}
			</div>
		)
}

const marker_types = Object.keys(picks_by_type).filter(t => t !== "MP");
function getPickupMarkers(state, setSelected) {
	let placements = state.placements;
	let reachable = Object.keys(state.reachable)
	let markers = []
	marker_types.forEach(pre => {
		picks_by_type[pre].forEach(pick => {
			let x = pick.hasOwnProperty("_x") ? pick._x : pick.x
			let y = pick.hasOwnProperty("_y") ? pick._y : pick.y
			let icon = get_icon(pick, state.highlight_picks.includes(pick.loc) ? "red" : null)
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
	
	    this.state = {mousePos: {lat: 0, lng: 0}, seed_in: "", reachable: {...DEFAULT_REACHABLE}, new_areas: {...DEFAULT_REACHABLE}, selected: "", selected_area: "", history: {}, 
	    			  step: 0, placements: {...DEFAULT_DATA}, viewport: DEFAULT_VIEWPORT, seedRecieved: false, highlight_picks: [], logicMode: 'manual'}
	}
  	

 	componentWillMount() {
	    let pathmode = get_param("pathmode");
	    let manual_reach = get_manual_reach();
	    let modes;
	
	    if(pathmode && paths.includes(pathmode)) {
			modes = presets[pathmode];
	    } else {
	    	pathmode = "standard";
	        modes = ['normal', 'speed', 'dboost-light'];
	    }
		this.setState({modes: modes, pathMode: {label: pathmode, value: pathmode}, manual_reach: manual_reach,})
	
	};

	onDragEnter = () => this.setState({dropzoneActive: true});

	onDragLeave = () => this.setState({dropzoneActive: false});
	
	onDrop = (files) => {
		let file = files.pop();
		if(file) {
		    let reader = new FileReader();
		    reader.onload = () => {
		        let text = reader.result;
		        this.parseUploadedSeed(text);
		        this.setState({dropzoneActive: false, seedRecieved: true, logicMode: "auto"})
		        window.URL.revokeObjectURL(file.preview);
		        // do whatever you want with the file content
		    };
		    reader.onabort = () => console.log('file reading was aborted');
		    reader.onerror = () => console.log('file reading has failed');
	
		    reader.readAsText(file);			
		} else {
			this.setState({dropzoneActive: false})
		}
	}


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

	onGroupClick = (picks, clickedName) =>  {
		let activated = (clickedName !== this.state.selected)
		let selected = "";
		let viewport = this.state.prev_viewport;
		let highlight_picks = [];
	    let map = this.refs.map.leafletElement;
		picks = picks.filter(pick => pick !== "Free");
		if(activated)
		{
			selected = clickedName;
			highlight_picks = picks.map(pick => pick.loc);
			let coords = picks.map(pick => { return {x: pick.hasOwnProperty("_x") ? pick._x : pick.x, y: pick.hasOwnProperty("_y") ? pick._y : pick.y}; })
			let center = coords.reduce((acc, coord) => { return {x: (coord.x / coords.length)+acc.x,y: (coord.y / coords.length)+acc.y} ; }, {x: 0, y: 0});
			if(coords.length > 1)
			{
				let xmin = Math.min(...coords.map(coord => coord.x));
				let xmax = Math.max(...coords.map(coord => coord.x));
				let ymin = Math.min(...coords.map(coord => coord.y));
				let ymax = Math.max(...coords.map(coord => coord.y));
				map.flyToBounds([[ymin, xmin], [ymax, xmax]], {maxZoom: 6, padding: [10, 10]})
			} else {
				map.flyTo([center.y, center.x], 6)
			}			
		} else
			map.flyTo(viewport.center, viewport.zoom)
		
		this.setState({highlight_picks: highlight_picks, selected: selected, prev_viewport: this.state.viewport})
	}
	
	updateManual = (param,val) => this.setState(prevState => {
		let manual_reach = this.state.manual_reach;
		manual_reach[param] = val;
		return {manual_reach: manual_reach}
	}, this._updateReachable)
	
  	_updateReachable = (layers=0) => {
  		if(layers<0)
  			return
  		if(!this.state.reachable || this.state.reachable === undefined) {
  			this.setState({reachedWith: {}, reachable: {...DEFAULT_REACHABLE}}, () => this._updateReachable(layers));
  			return
  		}
	  	let reachableStuff = {};
  		if(this.state.logicMode === "auto")
  		{
  			if(!this.state.seedRecieved)
  				return;
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
	  		layers = 0;
  		}
  		  	getReachable((state,callback) => this.setState(state,callback),
	  			this.state.modes.join("+"),
	  			Object.keys(reachableStuff).map((key) => key+":"+reachableStuff[key]).join("+"),
	  			() => this._updateReachable(layers-1));

  	};

	onViewportChanged= (viewport) => this.setState({viewport: viewport})

	_onPathModeChange = (n) => paths.includes(n.value) ? this.setState({modes: presets[n.value], pathMode: n}, this.resetReachable) : this.setState({pathMode: n}, this.resetReachable)
	toggleLogic = () => {this.setState({display_logic: !this.state.display_logic})};
	resetReachable = () => this.setState({ reachable: {...DEFAULT_REACHABLE}, new_areas: {...DEFAULT_REACHABLE}, selected: "", selected_area: "", highlight_picks: [], history: {}, step: 0})
	rewind = () => {
		if(dev)
			console.log(this.state)

		if(this.state.step>0)
			this.setState(prevState => {
				let hist = prevState.history[prevState.step-1];
				return {
					highlight_picks: [],
					selected: "",
					selected_area: "",
					reachable: {...hist.reachable}, 
					new_areas: {...hist.new_areas}, 
					step: prevState.step-1};
				}, () => dev ? console.log(this.state) : null)
	}

	render() {
	    let { accept, files, dropzoneActive } = this.state;
	    let overlayStyle = { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, padding: '10em 0', background: 'rgba(0,0,0,0.5)', textAlign: 'center', color: '#fff' };
		let inventory = getInventory(this.state);
		let inv_pane = getInventoryPane(inventory, this)
		let pickup_markers = ( <PickupMarkersList markers={getPickupMarkers(this.state, this.selectPickup)} />)
		let new_areas_report = getAreasPane(inventory, this)

		return (
	      <Dropzone className="wrapper" disableClick onDrop={this.onDrop} onDragEnter={this.onDragEnter} onDragLeave={this.onDragLeave} >
          { dropzoneActive && <div style={overlayStyle}>Import your randomizer.dat to begin analysis</div> }
	            <Helmet>
	                <style>{'body { background-color: black}'}</style>
					<link rel="stylesheet" href="https://unpkg.com/leaflet@1.3.1/dist/leaflet.css" integrity="sha512-Rksm5RenBEKSKFjgI3a41vrjkw4EVPlJ3+OiI65vTjIdo9brlAacEuKOiQ5OFh7cOI1bkDwLqdLw3Zg0cRJAAQ==" crossorigin=""/>
	            </Helmet>

				<Map crs={crs} ref="map" zoomControl={false} onMouseMove={(ev) => this.setState({mousePos: ev.latlng})} onViewportChanged={this.onViewportChanged} viewport={this.state.viewport}>
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
					<h6>Drag and drop your seed file onto the map to get started!</h6>
					<div id="file-controls">
						<Button color="primary" onClick={this.resetReachable} >Reset</Button> 
						<Button color="primary" onClick={() => this.rewind()} >{"Back"}</Button> 
						<Button color="disabled" disabled={true}>{this.state.step}</Button>
						<Button color="primary" onClick={() => this._updateReachable(0)} >{"Next"}</Button> 
					</div>
					{inv_pane}
					<div id="logic-controls">
						<div id="logic-mode-wrapper">
							<span className="label">Logic Mode:</span>
							<ButtonGroup>
								<Button color="secondary" onClick={() => this.setState({logicMode: "auto"}, this.resetReachable)} active={this.state.logicMode === "auto"}>Auto</Button>
								<Button color="secondary" onClick={() => this.setState({logicMode: "manual"}, this.resetReachable)} active={this.state.logicMode === "manual"}>Manual</Button>
							</ButtonGroup>
							<Collapse id="manual-controls" isOpen={this.state.logicMode === "manual"}>
								<hr style={{ backgroundColor: 'grey', height: 2 }}/>
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
								<Select styles={select_styles}  options={select_wrap(paths)} onChange={this._onPathModeChange} isClearable={false} value={this.state.pathMode}></Select>
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
						<hr style={{ backgroundColor: 'grey', height: 2 }}/>
						{new_areas_report}
					</div>
				</div>
			</Dropzone>

		)
	}
}

function uniq(array) {
    let seen = [];
    return array.filter(item => seen.includes(item.join("")) ? false : (seen.push(item.join("")) && true));
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
							history[step] = {reachable: {...prevState.reachable}, new_areas: {...prevState.new_areas}}
							let new_areas = {};
							Object.keys(reachable).forEach((area) => {
								if(!old_reachable.hasOwnProperty(area))
								{
									new_areas[area] = uniq(reachable[area]);
									old_reachable[area] = reachable[area];
								}
								old_reachable[area] = uniq(old_reachable[area].concat(reachable[area]));
							});
							return {reachable: old_reachable, new_areas: new_areas, history: history, step: step+1, highlight_picks: []}
						}, callback)
            		}
            })(xmlHttp.responseText);
    }
    xmlHttp.open("GET", "/plando/reachable?modes="+modes+"&codes="+codes, true);
    xmlHttp.send(null);
}



export default LogicHelper;
