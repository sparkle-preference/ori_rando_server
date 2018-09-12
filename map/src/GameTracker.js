import './index.css';
import React from 'react';
//import registerServiceWorker from './registerServiceWorker';
import {Map, Tooltip, TileLayer, Marker, ZoomControl} from 'react-leaflet';
import {Checkbox, CheckboxGroup} from 'react-checkbox-group';
import {Radio, RadioGroup} from 'react-radio-group';
import Leaflet from 'leaflet';
import {picks_by_type, PickupMarkersList, get_icon, getMapCrs, presets, player_icons, 
		hide_opacity, select_styles, uniq, select_wrap, get_preset} from './shared_map.js';
import Select from 'react-select';
import {Button, Collapse} from 'reactstrap';
import Control from 'react-leaflet-control';
import {Helmet} from 'react-helmet';

const paths = Object.keys(presets);
const game_id = document.getElementsByClassName("game-id")[0].id;

const EMPTY_PLAYER = {seed: {}, pos: [0,0], seen:[], flags: ["show_marker", "hide_found", "hide_unreachable"], areas: []}

function parse_seed(raw) {
	let out = {}
	let lines = raw.split("\n")
    for (let i = 0, len = lines.length; i < len; i++) {
    	let line = lines[i].split(":")
    	out[parseInt(line[0], 10)] = (line[1] === "Message" ? line[2] : line[1])
	}
	return out
};


function get_inner(id) {
	return (
	<Tooltip>
	<span>{id}</span>
	</Tooltip>
	);
};

const PlayerMarker = ({ map, position, icon, inner}) => (
	<Marker map={map} position={position} icon={icon}>
		{inner}
	</Marker>
	)

const PlayerMarkersList = ({map, players}) => {
	let players_to_show = Object.keys(players).filter(id => players[id].flags.includes("show_marker"))
	const items = players_to_show.map((id) => (
		<PlayerMarker  key={"player_"+id} map={map} position={players[id].pos} inner={get_inner(id)} icon={player_icons(id)}  />
	));
	return (<div style={{display: 'none'}}>{items}</div>);
}

const PlayerUiOpts = ({players, setter}) => {
	if(!players || Object.keys(players).length === 0)
		return null;
	const items = Object.keys(players).map((id) => {
		let f = (newFlags) => setter((prevState) => {
			let retVal = prevState.players;
			retVal[id].flags = newFlags;
			return {players:retVal};
		});
		return (
			<div class="player-wrapper">
				<span class="player-name">Player {id}</span>
				<CheckboxGroup class="player-options" checkboxDepth={4} name={id+"_flags"} value={players[id].flags} onChange={f}>
					<label><Checkbox value="show_marker"/> Show on map</label>
					<label><Checkbox value="show_spoiler"/> Show spoilers</label>
					<label><Checkbox value="hide_found"/> Hide found</label>
					<label><Checkbox value="hide_unreachable"/> Hide unreachable</label>
					<label><Checkbox value="hide_remaining"/> Hide remaining</label>
			    </CheckboxGroup>
			</div>
		);
	});
	return (<div>{items}</div>);
}

function getLocInfo(pick, players) {
	let loc = pick.loc;
	let info = Object.keys(players).map((id) => {
		let show_spoiler = players[id].flags.includes("show_spoiler");
		let seen = players[id].seen.includes(loc);
		if(show_spoiler || seen)
			if(players[id].seed.hasOwnProperty(loc))
				return id + ":" + players[id].seed[loc] + ((show_spoiler && seen) ? "*" : "");
			else
				return id + ": Nothing in seed at " + loc
		else
			return id + ": (hidden)"
	});
	return info;
}

function getMapstoneToolTip(players, inHTML = true) {
	let rows = [];
	let msNum = 0;
	for(let loc = 24; loc <= 56; loc += 4) {
		msNum++;
		let row = inHTML ? [(
			<td>MS{msNum}:</td>
		)] : [];
		row = row.concat(Object.keys(players).map((id) => {
			let show_spoiler = players[id].flags.includes("show_spoiler");
			let seen = players[id].seen.includes(loc);
			if(!inHTML) 
				return (show_spoiler || seen) ? (players[id].seed[loc] || "") : "";
			let cell = "("+id+") ";
			let val = players[id].seed[loc] || "N/A"
			if(show_spoiler || seen)
				cell += val + ((show_spoiler && seen) ? "*" : "");
			else
				cell += "(hidden)";
			return (
	    		<td style={{color:'black'}}>{cell}</td>
			)			
		}));
		rows.push(inHTML ? row : row.join(","));
	}
	if(!inHTML) 
		return rows.join(",")
	let jsxRows = rows.map(row => {
		return (
			<tr>{row}</tr>
		)
	});
	return (
		<Tooltip>
			<table>
			{jsxRows}
			</table>
		</Tooltip>
	)
}

function getPickupMarkers(state) {
	let players = {};
	Object.keys(state.players).forEach((id) => {
		if(state.players[id].flags.includes("show_marker"))
			players[id] = state.players[id];
	});
	
	let hideOpt = state.hideOpt;
	let pickupTypes = (state.pickup_display === "Some") ? state.pickups : ["EX", "HC", "SK", "Pl", "KS", "MS", "EC", "AC", "EV", "Ma"];
	let searchStr = (state.searchStr || "").toLowerCase();
	let markers = []
	let msTT = getMapstoneToolTip(players);
	for(let i in pickupTypes) {
		let pre = pickupTypes[i];
		for(let p in picks_by_type[pre]) {
			let pick = picks_by_type[pre][p]
			let count = Object.keys(players).length
			let x = pick.hasOwnProperty("_x") ? pick._x : pick.x
			let y = pick.hasOwnProperty("_y") ? pick._y : pick.y
			let icon = get_icon(pick)
			if(count === 0) {
				markers.push({key: pick.name+"|"+pick.x+","+pick.y, position: [y, x], inner: null, icon: icon})
				continue
			}

			let highlight = searchStr ? false : true;
			let loc_info = getLocInfo(pick, players);
			let pick_name = loc_info.join(",").toLowerCase();
			Object.keys(players).forEach((id) => {
				let player = players[id]
				let hide_found = player.flags.includes("hide_found")
				let hide_unreachable = player.flags.includes("hide_unreachable")
				let hide_remaining = player.flags.includes("hide_remaining")
				let show_spoiler = player.flags.includes("show_spoiler");
				if(searchStr && pick.name === "MapStone")
					pick_name = getMapstoneToolTip({id: player}, false).toLowerCase();
				let found = player.seen.includes(pick.loc);
				if(!highlight && (found || show_spoiler) && (pick_name && searchStr && pick_name.includes(searchStr)))
					highlight = true;
				let reachable = players[id].areas.includes(pick.area);

				if( (found && hide_found) || (!found && hide_remaining) || (!reachable && hide_unreachable && !found))
					count -= 1;
			});

			if((hideOpt === "any") ? (count === Object.keys(players).length) : (count > 0))
			{
				let inner = null;
				if(pick.name === "MapStone") {
					inner = msTT;
				} else {
					if(loc_info)
						{
						let lines = loc_info.map((infoln) => {
							return (
							<tr><td style={{color:'black'}}>{infoln}</td></tr>
							)
						});
						inner = (
						<Tooltip>
							<table>
							{lines}
							</table>
						</Tooltip>
						);
					}					
				}
				let opacity = highlight ? 1  : hide_opacity;
				markers.push({key: pick.name+"|"+pick.x+","+pick.y, position: [y, x], inner: inner, icon: icon, opacity: opacity});
			}

		}
	}
	return markers;
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
})();

const DEFAULT_VIEWPORT = {
	  center: [0, 0],
	  zoom: 4,
	};
const RETRY_MAX = 60;
const TIMEOUT_START = 5;
const TIMEOUT_INC = 5;

const crs = getMapCrs();

class GameTracker extends React.Component {
  constructor(props) {
    super(props)
    let modeRaw = document.getElementsByClassName("logic-modes")[0].id
    let modes = ['normal', 'speed', 'dboost-light', 'lure'];
    if(modeRaw !== "None"){
        modes = modeRaw.split(" ");
    }
    this.state = {mousePos: {lat: 0, lng: 0}, players: {}, retries: 0, check_seen: 1, modes: modes, timeout: TIMEOUT_START, searchStr: "", pickup_display: "all", show_sidebar: true,
    flags: ['show_pickups', 'update_in_bg'], viewport: DEFAULT_VIEWPORT, pickups: ["EX", "HC", "SK", "Pl", "KS", "MS", "EC", "AC", "EV", "Ma"],
    pathMode: get_preset(modes), hideOpt: "all", display_logic: (modeRaw !== "None")};
  };

  componentDidMount() {
	  this.interval = setInterval(() => this.tick(), 1000);
  };

  timeout = () => {
  	return {retries: this.state.retries+1, check_seen: this.state.timeout, timeout: this.state.timeout+TIMEOUT_INC}
  };
  tick = () => {
  	if(this.state.retries >= RETRY_MAX) return;
  	if(!document.hasFocus() && !this.state.flags.includes("update_in_bg")) return;

  	if(this.state.check_seen === 0) {
	  	this.setState({check_seen: 5});
		getSeen((p) => this.setState(p), this.timeout);
		getReachable((p) => this.setState(p),this.state.modes.join("+"), this.timeout);
		Object.keys(this.state.players).forEach((id) => {
			if(Object.keys(this.state.players[id].seed).length < 50)
				getSeed((p) => this.setState(p), id, this.timeout);
		})
  	} else
	  		this.setState({check_seen: this.state.check_seen -1});
		if(this.state.check_seen < 10)
			getPlayerPos((p) => this.setState(p), this.timeout);
  };

  componentWillUnmount() {
    clearInterval(this.interval);
  };

  hideOptChanged = newVal => { this.setState({hideOpt: newVal}) }
  flagsChanged = newVal => { this.setState({flags: newVal}) }
  pickupsChanged = newVal => { this.setState({pickups: newVal}) }
  onSearch = event => { this.setState({searchStr: event.target.value}) }

  modesChanged = (paths) => this.setState(prevState => {
		let players = prevState.players
		Object.keys(players).forEach(id => {		
				players[id].areas = []
			});
		return {players: players, modes: paths, pathMode: get_preset(paths)}
		}, () => getReachable((p) => this.setState(p),this.state.modes.join("+"), this.timeout))
		
toggleLogic = () => {this.setState({display_logic: !this.state.display_logic})};

  onViewportChanged = viewport => { this.setState({ viewport }) }
 _onPathModeChange = (n) => paths.includes(n.value) ? this.modesChanged(presets[n.value]) : this.setState({pathMode: n.value})

  render() {
		const pickup_markers = (this.state.pickup_display !== "none") ? ( <PickupMarkersList markers={getPickupMarkers(this.state)} />) : null;
		const player_markers = ( <PlayerMarkersList players={this.state.players} />)
		const player_opts = ( <PlayerUiOpts players={this.state.players} setter={(p) => this.setState(p)} />)
		const show_button = !this.state.show_sidebar ? (<Button size="sm" onClick={() => this.setState({show_sidebar: true})}>Show Options</Button>) : null
		const sidebar = this.state.show_sidebar ? (
				<div className="controls">
			    	<div id="search-wrapper">
						<label for="search">Search</label>
						<input id="search" className="form-control" type="text" value={this.state.searchStr} onChange={this.onSearch} />
					</div>
					<div id="map-controls">
						<span className="control-label"><h5>Options</h5></span>
						<CheckboxGroup style={{paddingLeft: '8px', paddingRight: '8px'}} checkboxDepth={3} name="flags" value={this.state.flags} onChange={this.flagsChanged}>
							<label><Checkbox value="update_in_bg"/> Always Update</label>
				       </CheckboxGroup>
				       <Button size="sm" onClick={() => this.setState({show_sidebar: false})}>Hide Options</Button>
					</div>
					<div id="player-controls">
						<span className="control-label"><h5>Players</h5></span>
						{player_opts}
						<div style={{paddingLeft: '8px', paddingRight: '8px'}}>
							<span>Hide pickup if it would be hidden for...</span>
							<RadioGroup name="hideOpts" selectedValue={this.state.hideOpt} onChange={this.hideOptChanged}>
								<label class="radio-label"><Radio value="all"/> ...all players</label>
								<label class="radio-label"><Radio value="any"/> ...any player</label>
				       		</RadioGroup>
						</div>
					</div>
					<div id="logic-controls">
						<div id="logic-presets">
			      	<Button color="primary" onClick={this.toggleLogic} >Logic Presets:</Button>
			      	<Select styles={select_styles}  options={select_wrap(paths)} onChange={this._onPathModeChange} clearable={false} value={select_wrap(this.state.pathMode)}></Select>
						</div>
						<Collapse id="logic-options-wrapper" isOpen={this.state.display_logic}>
							<CheckboxGroup id="logic-options" checkboxDepth={2} name="modes" value={this.state.modes} onChange={this.modesChanged}>
								<label><Checkbox value="normal" /> normal</label>
								<label><Checkbox value="speed" /> speed</label>
								<label><Checkbox value="extended" /> extended</label>
								<label><Checkbox value="speed-lure" /> speed-lure</label>
								<label><Checkbox value="lure" /> lure</label>
								<label><Checkbox value="lure-hard" /> lure-hard</label>
								<label><Checkbox value="dboost-light" /> dboost-light</label>
								<label><Checkbox value="dboost" /> dboost</label>
								<label><Checkbox value="dboost-hard" /> dboost-hard</label>
								<label><Checkbox value="cdash" /> cdash</label>
								<label><Checkbox value="cdash-farming" /> cdash-farming</label>
								<label><Checkbox value="extreme" /> extreme</label>
								<label><Checkbox value="extended-damage" /> extended-damage</label>
								<label><Checkbox value="timed-level" /> timed-level</label>
								<label><Checkbox value="dbash" /> dbash</label>
								<label><Checkbox value="glitched" /> glitched</label>
						  	</CheckboxGroup>
						</Collapse>
					</div>
					<div id="pickup-controls">
						<span className="control-label"><h5>Visible Pickups</h5></span>
						<RadioGroup name="pickup_display_opts" selectedValue={this.state.pickup_display} onChange={newVal => this.setState({pickup_display: newVal})}>
							<label class="radio-label"><Radio value="all"/> All</label>
							<label class="radio-label"><Radio value="some"/>Some</label>
							<label class="radio-label"><Radio value="none"/>None</label>
			       		</RadioGroup>
						<Collapse id="logic-options-wrapper" isOpen={this.state.pickup_display === "some"}>
							<CheckboxGroup id="pickup-wrapper" checkboxDepth={2} name="options" value={this.state.pickups} onChange={this.pickupsChanged}>
								<label><Checkbox value="SK" />Skill trees</label>
								<label><Checkbox value="MS" />Mapstones</label>
								<label><Checkbox value="EV" />Events</label>
								<label><Checkbox value="AC" />Abiliy Cells</label>
								<label><Checkbox value="HC" />Health Cells</label>
								<label><Checkbox value="EC" />Energy Cells</label>
								<label><Checkbox value="Pl" />Plants</label>
								<label><Checkbox value="KS" />Keystones</label>
								<label><Checkbox value="EX" />Exp Orbs</label>
								<label><Checkbox value="Ma" />Mapstone turnins</label>
				    		</CheckboxGroup>
						</Collapse>
					</div>
				</div>
		) : null
    return (
			<div className="wrapper">
	            <Helmet>
	                <style>{'body { background-color: black}'}</style>
					<link rel="stylesheet" href="https://unpkg.com/leaflet@1.3.1/dist/leaflet.css" integrity="sha512-Rksm5RenBEKSKFjgI3a41vrjkw4EVPlJ3+OiI65vTjIdo9brlAacEuKOiQ5OFh7cOI1bkDwLqdLw3Zg0cRJAAQ==" crossorigin=""/>
	            </Helmet>
		      	<Map crs={crs} onMouseMove={(ev) => this.setState({mousePos: ev.latlng})} zoomControl={false} onViewportChanged={this.onViewportChanged} viewport={this.state.viewport}>
		      	     <ZoomControl position="topright" />

					<TileLayer url=' https://ori-tracker.firebaseapp.com/images/ori-map/{z}/{x}/{y}.png' noWrap='true' />
					<Control position="topleft" >
					<div>
						{show_button}
						<Button size="sm" onClick={() => this.setState({ viewport: DEFAULT_VIEWPORT })}>Reset View</Button>
						<Button size="sm" color="disabled">{Math.round(this.state.mousePos.lng)},{Math.round(this.state.mousePos.lat)}</Button>
					</div>
					</Control>
					{pickup_markers}
					{player_markers}
			    </Map>
			    {sidebar}
			</div>
		)
	}
};

function doNetRequest(onRes, setter, url, timeout)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState === 4) {
        	 if(xmlHttp.status === 404)
        	 	setter(timeout())
        	 else
	        	 onRes(xmlHttp.responseText);
        }
	}
    xmlHttp.open("GET", url, true); // true for asynchronous
    xmlHttp.send(null);
}

function getSeed(setter, pid, timeout)
{
     var onRes = (res) => {
				setter((prevState, props) => {
					let retVal = prevState.players;
					retVal[pid].seed = parse_seed(res);
					return {players:retVal, retries: 0, timeout: TIMEOUT_START}
				});
            }
     doNetRequest(onRes, setter, "/tracker/game/"+game_id+"/fetch/player/"+pid+"/seed", timeout)
}



function getReachable(setter, modes, timeout) {
     var onRes = (res) => {
            	let areas = {};
            	let raw = res.split("|");
            	for (let i = 0, len = raw.length; i < len; i++) {
            		let withid = raw[i].split(":");
            		if(withid[1] === "")
            			continue;
            		let id = withid[0];
					areas[id] = withid[1].split(",").map((raw) => raw.split("#")[0]);
				}
				setter((prevState) => {
					let players = prevState.players
					Object.keys(areas).forEach((id) => {
						if(!players.hasOwnProperty(id)){
							players[id] = {...EMPTY_PLAYER};
						}
						areas[id].forEach(area => {
							players[id].areas = uniq(players[id].areas.concat(area))
						});
					})
					return {players:players, retries: 0, timeout: TIMEOUT_START}
				})
    }
    doNetRequest(onRes, setter, "/tracker/game/"+game_id+"/fetch/reachable?modes="+modes, timeout)
}

function getSeen(setter, timeout)
{
     var onRes = (res) => {
            	let seens = {};
            	let raw = res.split("|");
            	for (let i = 0, len = raw.length; i < len; i++) {
            		let withid = raw[i].split(":");
            		if(withid[1] === "")
            			continue;
            		let id = withid[0];
					seens[id] = withid[1].split(",").map(i => parseInt(i, 10));
				}
				setter((prevState, props) => {
					let retVal = prevState.players
					Object.keys(seens).forEach((id) => {
						if(!retVal.hasOwnProperty(id)){
							retVal[id] = {...EMPTY_PLAYER};
						}
						retVal[id].seen = seens[id]
					})
					return {players:retVal, retries: 0, timeout: TIMEOUT_START}
				})
    }
    doNetRequest(onRes, setter, "/tracker/game/"+game_id+"/fetch/seen", timeout)
}


function getPlayerPos(setter, timeout)
{
     var onRes = (res) => {
            	let player_positions = {};
            	let rawpos = res.split("|");
            	for (let i = 0, len = rawpos.length; i < len; i++) {
            		let withid = rawpos[i].split(":");
            		let id = withid[0];
            		let pos = withid[1].split(",");
					player_positions[id] = [pos[1]*1.0, pos[0]*1.0];
				}
				setter((prevState, props) => {
					let retVal = prevState.players
					Object.keys(player_positions).forEach((id) => {
						if(!retVal.hasOwnProperty(id))
							retVal[id] = {...EMPTY_PLAYER};
						retVal[id].pos = player_positions[id]
					})
					return {players:retVal, retries: 0, timeout: TIMEOUT_START}
				})
    }
    doNetRequest(onRes, setter, "/tracker/game/"+game_id+"/fetch/pos", timeout)
}


export default GameTracker;
