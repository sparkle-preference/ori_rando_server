import React from 'react';
import ReactDOM from 'react-dom';
import './index.css';
import './bootstrap.cyborg.min.css';
import registerServiceWorker from './registerServiceWorker';
import { Map, Tooltip, Popup, ImageOverlay, TileLayer, Marker} from 'react-leaflet';
import {Checkbox, CheckboxGroup} from 'react-checkbox-group';
import Control from 'react-leaflet-control';
import Leaflet from 'leaflet';
import { withRouter, Route } from 'react-router';
import { BrowserRouter, Link } from 'react-router-dom';
import uuid from 'uuid-encoded';
import {picks_by_type, PickupMarker, PickupMarkersList, pickup_icons, getMapCrs} from './shared_map.js';

const game_id = document.getElementsByClassName("game-id-holder")[0].id;

function parse_seed(raw) {
	let out = {}
	let lines = raw.split("\n")
    for (let i = 0, len = lines.length; i < len; i++) {
    	let line = lines[i].split(":")
    	out[line[0]] = line[1]
	}
	return out
 }

function player_icons(id)  {
	let img = 	'../sprites/ori-white.png';
	if (id == 1)  img = '../sprites/ori-blue.png';
	else if (id == 2)  img = '../sprites/ori-red.png';
	else if (id == 3)  img = '../sprites/ori-green.png';
	else if (id == 4)  img = '../sprites/ori-purple.png';
	else if (id == 5)  img = '../sprites/ori-yellow.png';
	else if (id == 200)  img = '../sprites/ori-skul.png';
	let ico = new Leaflet.Icon({iconUrl: img, iconSize: new Leaflet.Point(48, 48)});
	return ico
};


const PlayerMarker = ({ map, position, icon}) => ( <Marker map={map} position={position} icon={icon} /> );
const PlayerMarkersList = ({map, players}) => {
	const items = Object.keys(players).map((id) => (
		<PlayerMarker  key={"player_"+id} map={map} position={players[id].pos} icon={player_icons(id)}  /> 
	));
	return <div style={{display: 'none'}}>{items}</div>;
}

function getLocInfo(pick, players, spoiler) {
	let loc = ""+pick.loc;
	let info = "";
	Object.keys(players).map((id) => {
		if(spoiler || players[id].seen.includes(loc))
			info += id + ":" + players[id].seed[loc] + "  ";
		else
			info += id + ":" + "(hidden) "
	});
	info = info.slice(0, -2)
	return info;
}

function getPickupMarkers(players, pickupTypes, flags) {
	let spoiler = flags.includes("show_spoiler")
	let hide_found = flags.includes("hide_found")
	let hide_unreachable = flags.includes("hide_unreachable")
	let markers = []
	for(let i in pickupTypes) {
		let pre = pickupTypes[i];
		for(let p in picks_by_type[pre]) {
			let pick = picks_by_type[pre][p]
			let show = true;
			if(hide_found && Object.keys(players).length > 0) {
				show = false;
				Object.keys(players).map((id) => {
					if(!players[id].seen.includes(""+pick.loc)) 
						show = true;
				});				
			}
			if(hide_unreachable && Object.keys(players).length > 0) {
				Object.keys(players).map((id) => {
					if(!players[id].areas.includes(pick.area)) 
						show = false;
				});				
			}


			if(show)
			{
				let loc_info = getLocInfo(pick, players, spoiler);
				if(!loc_info)
					loc_info = "N/A";
				let inner = (
				<Tooltip>
					<span>
						{loc_info} 
					</span> 
				</Tooltip>
				);
				markers.push({key: pick.name+"|"+pick.x+","+pick.y, opacity:1, position: [pick.y, pick.x], inner: inner, icon: pickup_icons[pre]});								
			}
	
		}
	}
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

const DEFAULT_VIEWPORT = {
	  center: [0, 0],
	  zoom: 3,
	}
const crs = getMapCrs();
class GameTracker extends React.Component {
  constructor(props) {
    super(props)
    this.state = {players: {}, done: false, check_seen: 1, modes: ['normal', 'speed'], flags: ['show_players', 'hide_found', 'show_pickups'], viewport: DEFAULT_VIEWPORT, pickups: ["EX", "HC", "SK", "Pl", "KS", "MS", "EC", "AC"] }
  };
  componentDidMount() {
	  this.interval = setInterval(() => this.tick(this), 1000);
  };
  
  tick(s) {
  	if((!document.hasFocus() && !s.state.flags.includes("update_in_bg") )|| s.state.done) return;
  	if(s.state.check_seen == 0) {
	  	s.setState({check_seen: 5});
		getSeen((p) => s.setState(p));
		getReachable((p) => s.setState(p),s.state.modes.join("+"));
  	} else 
	  	s.setState({check_seen: s.state.check_seen -1});
	if(s.state.check_seen < 10)
		getPlayerPos((p) => s.setState(p));

	Object.keys(s.state.players).map((id) => {
		if(Object.keys(s.state.players[id].seed).length === 0)
			getSeed((p) => s.setState(p), id);
	})
  }

  componentWillUnmount() {
    clearInterval(this.interval);
  }
  flagsChanged = (newVal) => { this.setState({flags: newVal}) }
  pickupsChanged = (newVal) => { this.setState({pickups: newVal}) }
  modesChanged = (newVal) => {
  	this.setState({modes: newVal});
	getReachable((p) => this.setState(p),this.state.modes.join("+"));
  
  }
  onViewportChanged = viewport => { this.setState({ viewport }) }


    render() {
	const pickups = this.state.flags.includes('show_pickups') ? ( <PickupMarkersList markers={getPickupMarkers(this.state.players, this.state.pickups, this.state.flags)} />) : null
	const players = this.state.flags.includes('show_players') ? ( <PlayerMarkersList players={this.state.players} />) : null

    return (
          <div style={{ textAlign: 'center' }}> 
        <button  onClick={ () => this.setState({ viewport: DEFAULT_VIEWPORT }) } >
          Reset View
        </button>
		<CheckboxGroup checkboxDepth={2} name="flags" value={this.state.flags} onChange={this.flagsChanged}> 
        <label><Checkbox value="show_players"/> Players</label>
        <label><Checkbox value="show_spoiler"/> Spoiler</label>
        <label><Checkbox value="show_pickups"/> Pickups</label>
        <label><Checkbox value="hide_found"/> Hide found</label>
        <label><Checkbox value="hide_unreachable"/> Hide unreachable</label>
        <label><Checkbox value="update_in_bg"/> Always Update</label>
       </CheckboxGroup>
		<CheckboxGroup checkboxDepth={2} name="modes" value={this.state.modes} onChange={this.modesChanged}> 
			<label><Checkbox value="lure" /> lure</label>
			<label><Checkbox value="extended" /> extended</label>
			<label><Checkbox value="normal" /> normal</label>
			<label><Checkbox value="dboost-light" /> dboost-light</label>
			<label><Checkbox value="dboost" /> dboost</label>
			<label><Checkbox value="glitched" /> glitched</label>
			<label><Checkbox value="cdash-farming" /> cdash-farming</label>
			<label><Checkbox value="cdash" /> cdash</label>
			<label><Checkbox value="timed-level" /> timed-level</label>
			<label><Checkbox value="speed-lure" /> speed-lure</label>
			<label><Checkbox value="lure-hard" /> lure-hard</label>
			<label><Checkbox value="extended-damage" /> extended-damage</label>
			<label><Checkbox value="dbash" /> dbash</label>
			<label><Checkbox value="speed" /> speed</label>
			<label><Checkbox value="dboost-hard" /> dboost-hard</label>
			<label><Checkbox value="extreme" /> extreme</label>
       </CheckboxGroup>
		<CheckboxGroup checkboxDepth={2} name="options" value={this.state.pickups} onChange={this.pickupsChanged}> 
			<label><Checkbox value="EX" />EX</label>
			<label><Checkbox value="SK" />SK</label>
			<label><Checkbox value="Pl" />Pl</label>
			<label><Checkbox value="KS" />KS</label>
			<label><Checkbox value="HC" />HC</label>
			<label><Checkbox value="MS" />MS</label>
			<label><Checkbox value="EC" />EC</label>
			<label><Checkbox value="AC" />AC</label>
       </CheckboxGroup>
        <Map crs={crs} onViewportChanged={this.onViewportChanged} viewport={this.state.viewport}>

     <TileLayer url=' https://ori-tracker.firebaseapp.com/images/ori-map/{z}/{x}/{y}.png' noWrap='true'  />
		{pickups}
		{players}
     </Map>
     </div>
	)
  }
}

function getSeed(setter, pid)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() { 
        if (xmlHttp.readyState === 4 && xmlHttp.status === 200)
            (function(res) {
				setter((prevState, props) => {
					let retVal = prevState.players
						retVal[pid].seed = parse_seed(res)
					return {players:retVal}
				});

            })(xmlHttp.responseText);
    }
    xmlHttp.open("GET", "/"+game_id+"."+pid+"/seed", true); // true for asynchronous 
    xmlHttp.send(null);
}

function getReachable(setter, modes)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() { 
        if (xmlHttp.readyState === 4 && xmlHttp.status === 200)
            (function(res) {
            	if(res == "Stop")
            	{
            		setter({done: true});
					return;
            	}
            	let areas = {};
            	let raw = res.split("|");
            	for (let i = 0, len = raw.length; i < len; i++) {
            		let withid = raw[i].split(":");
            		if(withid[1] == "") 
            			continue;
            		let id = withid[0];
					areas[id] = withid[1].split(",");
				}
				setter((prevState, props) => {
					let retVal = prevState.players
					Object.keys(areas).map((id) => {
						if(!retVal.hasOwnProperty(id)){
							retVal[id] = {seed: {}, pos: [0,0], seen: []};
						}
						retVal[id].areas = areas[id]
					})
					return {players:retVal}
				})
            })(xmlHttp.responseText);
    }
    xmlHttp.open("GET", "/"+game_id+"/reachable?modes="+modes, true); // true for asynchronous 
    xmlHttp.send(null);
}

function getSeen(setter)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() { 
        if (xmlHttp.readyState === 4 && xmlHttp.status === 200)
            (function(res) {
            	if(res == "Stop")
            	{
            		setter({done: true});
					return;
            	}
            	if(!res.includes(':')) {
            		setter({check_seen: 60})
            		return;
            	}
            	let seens = {};
            	let raw = res.split("|");
            	for (let i = 0, len = raw.length; i < len; i++) {
            		let withid = raw[i].split(":");
            		if(withid[1] == "") 
            			continue;
            		let id = withid[0];
					seens[id] = withid[1].split(",");
				}
				setter((prevState, props) => {
					let retVal = prevState.players
					Object.keys(seens).map((id) => {
						if(!retVal.hasOwnProperty(id)){
							retVal[id] = {seed: {}, pos: [0,0], areas: []};
						}
						retVal[id].seen = seens[id]
					})
					return {players:retVal}
				})
            })(xmlHttp.responseText);
    }
    xmlHttp.open("GET", "/"+game_id+"/seen", true); // true for asynchronous 
    xmlHttp.send(null);
}


function getPlayerPos(setter)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() { 
        if (xmlHttp.readyState === 4 && xmlHttp.status === 200)
            (function(res) {
            	if(res == "Stop")
            	{
            		setter({done: true})
					return
            	}
            	if(!res.includes(':')) {
            		setter({check_seen: 60})
            		return;
            	}
            	let player_positions = {};
            	let rawpos = res.split("|");
            	for (let i = 0, len = rawpos.length; i < len; i++) {
            		let withid = rawpos[i].split(":");
            		let id = withid[0];
            		let pos = withid[1].split(",");
					player_positions[id] = [pos[1], pos[0]];
				}
				setter((prevState, props) => {
					let retVal = prevState.players
					Object.keys(player_positions).map((id) => {
						if(!retVal.hasOwnProperty(id)) 
							retVal[id] = {seed: {}, seen: [], areas: []};
						retVal[id].pos = player_positions[id]
					})
					return {players:retVal}
				})
            })(xmlHttp.responseText);
    }
    xmlHttp.open("GET", "/"+game_id+"/getPos", true); // true for asynchronous 
    xmlHttp.send(null);
}


export default GameTracker;