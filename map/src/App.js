import React from 'react';
import ReactDOM from 'react-dom';
import './index.css';
import './bootstrap.cyborg.min.css';
import registerServiceWorker from './registerServiceWorker';
import { Map, Popup, ImageOverlay, TileLayer, Marker} from 'react-leaflet';
import Leaflet from 'leaflet';
import pickups from './pickup_locs.js';
import { withRouter, Route } from 'react-router';
import { BrowserRouter, Link } from 'react-router-dom';
import uuid from 'uuid-encoded';
import { Button } from 'reactstrap';


function point(x, y) {
  return {x: x, y: y};
}
let swampTeleporter = point(493.719818, -74.31961);
let gladesTeleporter = point(109.90181, -257.681549);

// Pretty close, not exact
let swampTeleporterOnMap = point(15215, 9576);
let gladesTeleporterOnMap = point(11854, 11174);

var map1 = gladesTeleporterOnMap;
var map2 = swampTeleporterOnMap;
var game1 = gladesTeleporter;
var game2 = swampTeleporter;

var mapRightSide = 20480;
var mapBottomSide = 14592;

var gameLeftSide = game2.x - ((map2.x / (map2.x - map1.x)) * (game2.x - game1.x));
var gameTopSide = game2.y - ((map2.y / (map2.y - map1.y)) * (game2.y - game1.y));


var gameRightSide = mapRightSide / map1.x * (game1.x - gameLeftSide) + gameLeftSide
var gameBottomSide = mapBottomSide / map1.y * (game1.y - gameTopSide) + gameTopSide

function distance(a, b) {
  return Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)
}

const maxZoom = 7;
const bounds = [[gameBottomSide, gameLeftSide], [gameTopSide, gameRightSide]];

function player_icons(id)  {
	let img = 	require('./sprites/ori-white.png');
	if (id == 1)  img = require('./sprites/ori-blue.png');
	else if (id == 2)  img = require('./sprites/ori-red.png');
	else if (id == 3)  img = require('./sprites/ori-green.png');
	else if (id == 4)  img = require('./sprites/ori-purple.png');
	else if (id == 5)  img = require('./sprites/ori-yellow.png');
	else if (id == 200)  img = require('./sprites/ori-skul.png');
	let ico = new Leaflet.Icon({iconUrl: img, iconSize: new Leaflet.Point(48, 48)});
	return ico
};

const pickup_icons = {
	"SK": new Leaflet.Icon({iconUrl: require('./sprites/skill-tree.png'), iconSize: new Leaflet.Point(32, 32), iconAnchor: new Leaflet.Point(0, 32)}),
	"HC": new Leaflet.Icon({iconUrl: require('./sprites/health-cell.png'), iconSize: new Leaflet.Point(24, 24)}),
	"AC": new Leaflet.Icon({iconUrl: require('./sprites/ability-cell.png'), iconSize: new Leaflet.Point(24, 24)}),
	"EC": new Leaflet.Icon({iconUrl: require('./sprites/energy-cell.png'), iconSize: new Leaflet.Point(24, 24)}),
	"MS": new Leaflet.Icon({iconUrl: require('./sprites/map-fragment.png'), iconSize: new Leaflet.Point(24, 24)}),
	"EX": new Leaflet.Icon({iconUrl: require('./sprites/xp.png'), iconSize: new Leaflet.Point(24, 24)}),
	"KS": new Leaflet.Icon({iconUrl: require('./sprites/keystone.png'), iconSize: new Leaflet.Point(24, 24)}),
}

const PickupMarker = ({ map, position, info, icon}) => (
  <Marker map={map} position={position} icon={icon}>
    <Popup> <span>{info}</span> </Popup>
  </Marker>
);

const PickupMarkersList = ({ map, markers }) => {
  const items = markers.map(({ key, ...props }) => (
      <PickupMarker key={key} map={map} {...props} />
  ));
  return <div style={{display: 'none'}}>{items}</div>;
};

const PlayerMarker = ({ map, position, icon}) => ( <Marker map={map} position={position} icon={icon} /> );
const PlayerMarkersList = ({map, players}) => {
	const items = Object.keys(players).map((id) => (
		<PlayerMarker  key={"player_"+id} map={map} position={players[id]} icon={player_icons(id)}  /> 
	));
	return <div style={{display: 'none'}}>{items}</div>;
}

function getPickupMarkers() {
	let markers = []
	for(let pre in pickup_icons) {
		for(let p in pickups[pre]) {
			let pick = pickups[pre][p]
			markers.push({key: pick.name+"|"+pick.x+","+pick.y, position: [pick.y, pick.x], info: pick.name, icon: pickup_icons[pre]})
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

var leafletTileSize = 256;

var gameTileSizeX = (2 ** maxZoom * leafletTileSize) / mapRightSide * (gameRightSide - gameLeftSide)
var scaleX = leafletTileSize / gameTileSizeX

var gameTileSizeY = (2 ** maxZoom * leafletTileSize) / mapBottomSide * (gameBottomSide - gameTopSide)
var scaleY = leafletTileSize / gameTileSizeY

var mapOriginX = (0 - gameLeftSide) / (game1.x - gameLeftSide) * map1.x / (2 ** maxZoom)
var mapOriginY = (0 + gameTopSide) / (gameTopSide - game1.y) * map1.y / (2 ** maxZoom)

Leaflet.CRS.MySimple = Leaflet.extend({}, Leaflet.CRS.Simple, {
  transformation: new Leaflet.Transformation(scaleX, mapOriginX, scaleY, mapOriginY)
});


var game_id = document.getElementsByClassName("game-id-holder")[0].id;

class App extends React.Component {
  constructor() {
    super()
    this.state = {players: {}}
  };
  componentDidMount() {
	  this.interval = setInterval(() => this.tick(this), 1000);
  };
  
  tick(s) {
	setPlayerPos((p) => s.setState({players: p}));
  }

  componentWillUnmount() {
    clearInterval(this.interval);
  }
  render() {
    return <Map
      minZoom={0} maxZoom={7} zoom={4} center={[0,0]} 
    crs={Leaflet.CRS.MySimple}
    >
      
     <TileLayer url=' https://ori-tracker.firebaseapp.com/images/ori-map/{z}/{x}/{y}.png' noWrap='true'  />
	 <PickupMarkersList markers={getPickupMarkers()} />
	 <PlayerMarkersList players={this.state.players} />
     </Map>
  }
}

function setPlayerPos(setter)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() { 
        if (xmlHttp.readyState === 4 && xmlHttp.status === 200)
            (function(res) {
            	let player_positions = {};
            	let rawpos = res.split("|");
            	for (let i = 0, len = rawpos.length; i < len; i++) {
            		let withid = rawpos[i].split(":");
            		let id = withid[0];
            		let pos = withid[1].split(",");
					player_positions[id] = [pos[1], pos[0]];
				}
				setter(player_positions)
            })(xmlHttp.responseText);
    }
    xmlHttp.open("GET", "/"+game_id+"/getPos", true); // true for asynchronous 
    xmlHttp.send(null);
}


export default App;