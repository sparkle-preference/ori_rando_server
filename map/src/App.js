import React from 'react';
import ReactDOM from 'react-dom';
import './index.css';
import './bootstrap.cyborg.min.css';
import registerServiceWorker from './registerServiceWorker';
import { Map, ImageOverlay, TileLayer, Marker} from 'react-leaflet';
import Leaflet from 'leaflet';
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

var scalex = (swampTeleporter.x - gladesTeleporter.x) / (swampTeleporterOnMap.x - gladesTeleporterOnMap.x);
var scaley = (swampTeleporter.y - gladesTeleporter.y) / (swampTeleporterOnMap.y - gladesTeleporterOnMap.y);

var gameRightSide = mapRightSide / map1.x * (game1.x - gameLeftSide) + gameLeftSide
var gameBottomSide = mapBottomSide / map1.y * (game1.y - gameTopSide) + gameTopSide

function distance(a, b) {
  return Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)
}

const mapCenter = [0, 0];
const zoomLevel = 3;
const maxZoom = 7;
const bounds = [[gameBottomSide, gameLeftSide], [gameTopSide, gameRightSide]];

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

var player_positions = [];

class App extends React.Component {
  constructor() {
    super()
    this.state = {players: []}
  }
  componentDidMount() {
	  this.interval = setInterval(() => {updatePlayerPos() ; this.setState({players: player_positions})}, 1000);
  }
  componentWillUnmount() {
    clearInterval(this.interval);
  }
  render() {
    return <Map
      minZoom={0} maxZoom={7} zoom={4} center={[0,0]} 
    crs={Leaflet.CRS.MySimple}
    >
     	{player_positions.map((pos, idx) => <Marker key={idx} position={[pos[0], pos[1]]} />) }
      
      <TileLayer url=' https://ori-tracker.firebaseapp.com/images/ori-map/{z}/{x}/{y}.png' noWrap='true'  />
    </Map>
  }
}

function updatePlayerPos()
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() { 
        if (xmlHttp.readyState === 4 && xmlHttp.status === 200)
            (function(res) {
            	player_positions = [];
            	let rawpos = res.split("|");
            	for (let i = 0, len = rawpos.length; i < len; i++) {
            		let pos = rawpos[i].split(",");
					player_positions.push(toMapCoord(pos));
				}
				console.log(player_positions)
            })(xmlHttp.responseText);
    }
    xmlHttp.open("GET", "/"+game_id+"/getPos", true); // true for asynchronous 
    xmlHttp.send(null);
}

function toMapCoord(gameCoords) {
    gameCoords = {x: gameCoords[1], y: gameCoords[0] }
    let mapx = (gameCoords.x - gameLeftSide) / scalex;
    let mapy = (gameCoords.y - gameTopSide) / scaley;

  return [mapx, mapy]; //point(mapx, mapy)
}

export default App;