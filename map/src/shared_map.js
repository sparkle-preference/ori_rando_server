import React from 'react';
import Leaflet from 'leaflet';
import {Marker} from 'react-leaflet';



const point = (x, y) => {return {x: x, y: y}; } 
const distance = (x1, y1, x2, y2) => Math.sqrt((x2-x1) ** 2 + (y2-y1) ** 2);

function download(filename, text) {
  let element = document.createElement('a');
  element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(text));
  element.setAttribute('download', filename);
  element.style.display = 'none';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
}

const dev = window.document.URL.includes("devshell")
const base_url = dev ?  "https://8080-dot-3616814-dot-devshell.appspot.com" : "https://orirando.com"

const pickup_icons = {
    "SK": new Leaflet.Icon({iconUrl: '/sprites/skill-tree.png', iconSize: new Leaflet.Point(32, 32), iconAnchor: new Leaflet.Point(0, 32)}),
    "HC": new Leaflet.Icon({iconUrl: '/sprites/health-cell.png', iconSize: new Leaflet.Point(24, 24)}),
    "AC": new Leaflet.Icon({iconUrl: '/sprites/ability-cell.png', iconSize: new Leaflet.Point(24, 24)}),
    "EC": new Leaflet.Icon({iconUrl: '/sprites/energy-cell.png', iconSize: new Leaflet.Point(24, 24)}),
    "MS": new Leaflet.Icon({iconUrl: '/sprites/map-fragment.png', iconSize: new Leaflet.Point(24, 24)}),
    "Ma": new Leaflet.Icon({iconUrl: '/sprites/map-stone.png', iconSize: new Leaflet.Point(24, 24)}),
    "EX": new Leaflet.Icon({iconUrl: '/sprites/xp.png', iconSize: new Leaflet.Point(24, 24)}),
    "Pl": new Leaflet.Icon({iconUrl: '/sprites/plant.png', iconSize: new Leaflet.Point(16, 16)}),
    "TP": new Leaflet.Icon({iconUrl: '/sprites/teleporter.png', iconSize: new Leaflet.Point(32, 32)}),
    "KS": new Leaflet.Icon({iconUrl: '/sprites/keystone.png', iconSize: new Leaflet.Point(24, 24)}),
    "CS": new Leaflet.Icon({iconUrl: '/sprites/WarmthReturned.png', iconSize: new Leaflet.Point(20, 20)}),
    "EVGinsoKey": new Leaflet.Icon({iconUrl: '/sprites/WaterVein.png', iconSize: new Leaflet.Point(24, 24)}),
    "EVWater": new Leaflet.Icon({iconUrl: '/sprites/CleanWater.png', iconSize: new Leaflet.Point(24, 24)}),
    "EVForlornKey": new Leaflet.Icon({iconUrl: '/sprites/GumonSeal.png', iconSize: new Leaflet.Point(24, 24)}),
    "EVWind": new Leaflet.Icon({iconUrl: '/sprites/WindRestored.png', iconSize: new Leaflet.Point(24, 24)}),
    "EVHoruKey": new Leaflet.Icon({iconUrl: '/sprites/Sunstone.png', iconSize: new Leaflet.Point(24, 24)}),
    "EVWarmth": new Leaflet.Icon({iconUrl: '/sprites/WarmthReturned.png', iconSize: new Leaflet.Point(24, 24)}),
};

const blank_icon = new Leaflet.Icon({iconUrl: '/sprites/blank.png', iconSize: new Leaflet.Point(24, 24)});

const icon_color = {
    blue: {
        "SK": new Leaflet.Icon({iconUrl: '/sprites/colors/skill-tree-blue.png', iconSize: new Leaflet.Point(32, 32), iconAnchor: new Leaflet.Point(0, 32)}),
        "HC": new Leaflet.Icon({iconUrl: '/sprites/colors/health-cell-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "AC": new Leaflet.Icon({iconUrl: '/sprites/colors/ability-cell-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "EC": new Leaflet.Icon({iconUrl: '/sprites/colors/energy-cell-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "MS": new Leaflet.Icon({iconUrl: '/sprites/colors/map-fragment-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "Ma": new Leaflet.Icon({iconUrl: '/sprites/colors/map-stone-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "EX": new Leaflet.Icon({iconUrl: '/sprites/colors/xp-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "Pl": new Leaflet.Icon({iconUrl: '/sprites/colors/plant-blue.png', iconSize: new Leaflet.Point(20, 20)}),
        "KS": new Leaflet.Icon({iconUrl: '/sprites/colors/keystone-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "CS": new Leaflet.Icon({iconUrl: '/sprites/colors/WarmthReturned-blue.png', iconSize: new Leaflet.Point(16, 16)}),
        "EVGinsoKey": new Leaflet.Icon({iconUrl: '/sprites/colors/WaterVein-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVWater": new Leaflet.Icon({iconUrl: '/sprites/colors/CleanWater-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVForlornKey": new Leaflet.Icon({iconUrl: '/sprites/colors/GumonSeal-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVWind": new Leaflet.Icon({iconUrl: '/sprites/colors/WindRestored-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVHoruKey": new Leaflet.Icon({iconUrl: '/sprites/colors/Sunstone-blue.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVWarmth": new Leaflet.Icon({iconUrl: '/sprites/colors/WarmthReturned-blue.png', iconSize: new Leaflet.Point(24, 24)}),
    },
    red: {
        "SK": new Leaflet.Icon({iconUrl: '/sprites/colors/skill-tree-red.png', iconSize: new Leaflet.Point(32, 32), iconAnchor: new Leaflet.Point(0, 32)}),
        "HC": new Leaflet.Icon({iconUrl: '/sprites/colors/health-cell-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "AC": new Leaflet.Icon({iconUrl: '/sprites/colors/ability-cell-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "EC": new Leaflet.Icon({iconUrl: '/sprites/colors/energy-cell-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "MS": new Leaflet.Icon({iconUrl: '/sprites/colors/map-fragment-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "Ma": new Leaflet.Icon({iconUrl: '/sprites/colors/map-stone-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "EX": new Leaflet.Icon({iconUrl: '/sprites/colors/xp-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "Pl": new Leaflet.Icon({iconUrl: '/sprites/colors/plant-red.png', iconSize: new Leaflet.Point(16, 16)}),
        "KS": new Leaflet.Icon({iconUrl: '/sprites/colors/keystone-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "CS": new Leaflet.Icon({iconUrl: '/sprites/colors/WarmthReturned-red.png', iconSize: new Leaflet.Point(20, 20)}),
        "EVGinsoKey": new Leaflet.Icon({iconUrl: '/sprites/colors/WaterVein-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVWater": new Leaflet.Icon({iconUrl: '/sprites/colors/CleanWater-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVForlornKey": new Leaflet.Icon({iconUrl: '/sprites/colors/GumonSeal-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVWind": new Leaflet.Icon({iconUrl: '/sprites/colors/WindRestored-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVHoruKey": new Leaflet.Icon({iconUrl: '/sprites/colors/Sunstone-red.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVWarmth": new Leaflet.Icon({iconUrl: '/sprites/colors/WarmthReturned-red.png', iconSize: new Leaflet.Point(24, 24)}),
    },
    green: {
        "SK": new Leaflet.Icon({iconUrl: '/sprites/colors/skill-tree-green.png', iconSize: new Leaflet.Point(32, 32), iconAnchor: new Leaflet.Point(0, 32)}),
        "HC": new Leaflet.Icon({iconUrl: '/sprites/colors/health-cell-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "AC": new Leaflet.Icon({iconUrl: '/sprites/colors/ability-cell-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "EC": new Leaflet.Icon({iconUrl: '/sprites/colors/energy-cell-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "MS": new Leaflet.Icon({iconUrl: '/sprites/colors/map-fragment-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "Ma": new Leaflet.Icon({iconUrl: '/sprites/colors/map-stone-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "EX": new Leaflet.Icon({iconUrl: '/sprites/colors/xp-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "Pl": new Leaflet.Icon({iconUrl: '/sprites/colors/plant-green.png', iconSize: new Leaflet.Point(16, 16)}),
        "KS": new Leaflet.Icon({iconUrl: '/sprites/colors/keystone-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "CS": new Leaflet.Icon({iconUrl: '/sprites/colors/WarmthReturned-green.png', iconSize: new Leaflet.Point(20, 20)}),
        "EVGinsoKey": new Leaflet.Icon({iconUrl: '/sprites/colors/WaterVein-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVWater": new Leaflet.Icon({iconUrl: '/sprites/colors/CleanWater-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVForlornKey": new Leaflet.Icon({iconUrl: '/sprites/colors/GumonSeal-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVWind": new Leaflet.Icon({iconUrl: '/sprites/colors/WindRestored-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVHoruKey": new Leaflet.Icon({iconUrl: '/sprites/colors/Sunstone-green.png', iconSize: new Leaflet.Point(24, 24)}),
        "EVWarmth": new Leaflet.Icon({iconUrl: '/sprites/colors/WarmthReturned-green.png', iconSize: new Leaflet.Point(24, 24)}),
    }
};


function get_icon(pick, color = null) {
    let iconGroup = pickup_icons;

    if(color && icon_color.hasOwnProperty(color))
        iconGroup = icon_color[color];

    if(iconGroup.hasOwnProperty(pick.name))
        return iconGroup[pick.name];

    let prefix = pick.name.substr(0, 2);
    if(iconGroup.hasOwnProperty(prefix))
        return iconGroup[prefix];

    console.log("no icon found for "+ pick.name + "!");
    return blank_icon;
}

function getMapCrs(x = .0001, y = -.0005, a = 0, b = -.2) {
    let swampTeleporter = point(493.719818, -74.31961);
    let gladesTeleporter = point(109.90181, -257.681549);
    
    // Pretty close, not exact
    let swampTeleporterOnMap = point(15258, 9587);
    let gladesTeleporterOnMap = point(11897, 11185);
    
    let map1 = gladesTeleporterOnMap;
    let map2 = swampTeleporterOnMap;
    let game1 = gladesTeleporter;
    let game2 = swampTeleporter;
    
    let mapRightSide = 20480;
    let mapBottomSide = 14592;
    
    let gameLeftSide = game2.x - ((map2.x / (map2.x - map1.x)) * (game2.x - game1.x));
    let gameTopSide = game2.y - ((map2.y / (map2.y - map1.y)) * (game2.y - game1.y));
    
    let gameRightSide = mapRightSide / map1.x * (game1.x - gameLeftSide) + gameLeftSide;
    let gameBottomSide = mapBottomSide / map1.y * (game1.y - gameTopSide) + gameTopSide;
    
    let leafletTileSize = 256;
    let maxZoom = 7;
    
    let gameTileSizeX = (2 ** maxZoom * leafletTileSize) / mapRightSide * (gameRightSide - gameLeftSide);
    let scaleX = leafletTileSize / gameTileSizeX;
    
    let gameTileSizeY = (2 ** maxZoom * leafletTileSize) / mapBottomSide * (gameBottomSide - gameTopSide);
    let scaleY = leafletTileSize / gameTileSizeY;
    
    let mapOriginX = (0 - gameLeftSide) / (game1.x - gameLeftSide) * map1.x / (2 ** maxZoom);
    let mapOriginY = (0 + gameTopSide) / (gameTopSide - game1.y) * map1.y / (2 ** maxZoom);
    
    Leaflet.CRS.MySimple = Leaflet.extend({}, Leaflet.CRS.Simple, {
      transformation: new Leaflet.Transformation(scaleX + x, mapOriginX + a, scaleY + y, mapOriginY + b)
    });

    return Leaflet.CRS.MySimple;
};

const PickupMarker = ({inner, map, position, icon, ...props}) => (
  <Marker map={map} position={position} icon={icon} {...props}>
  {inner}
  </Marker>
);

const PickupMarkersList = ({ map, markers }) => {
  let items = markers.map(({ key, ...props }) => (
      <PickupMarker key={key} map={map} {...props} />
  ));
  return <div style={{display: 'none'}}>{items}</div>;
};


const stuff_types = [{value: "Skills", label: "Skills"}, {value: "Events", label: "Events"}, {value: "Upgrades", label: "Upgrades"}, {value: "Teleporters", label: "Teleporters"}, {value: "Experience", label: "Experience"}, 
                     {value: "Cells/Stones", label: "Cells/Stones"}, {value: "Messages", label: "Messages"}, {value: "Custom", label: "Custom"}, {value: "Fill", label: "Fill"}];

const getStuffType = (stuff) => {
    if(!stuff || !stuff.hasOwnProperty("value"))
        return "Fill"
    switch(stuff.value.split("|")[0]) {
        case "SK":
            return "Skills"
        case "EV":
            return "Events"
        case "RB":
            return "Upgrades"
        case "TP":
            return "Teleporters"
        case "EX":
            return "Experience"
        case "HC":
        case "AC":
        case "EC":
        case "KS":
        case "MS":
            return "Cells/Stones"
        case "SH":
            return "Messages"
        default:
            return "Custom"
    }
}


let request = new XMLHttpRequest()
request.open('GET', '/pickupandlocinfo', false)
request.send(null)
if (request.status !== 200) alert("critical error! pickupandlocinfo could not generate")


const {picks_by_type, str_ids} = JSON.parse(request.responseText);
const pickups = [];
const picks_by_loc = {};
const locs = [];
const picks_by_zone = {};
const picks_by_area = {};
const zones = [];
const areas = [];
let ks = Object.keys(picks_by_type)
ks.forEach((pre) => {
    picks_by_type[pre].forEach((pick) => {
        if(pick.name !== "MapStone") {
            pickups.push(pick);
            if(!picks_by_zone.hasOwnProperty(pick.zone))
            {
                picks_by_zone[pick.zone] = [];
                zones.push(pick.zone);
            }
            if(!picks_by_area.hasOwnProperty(pick.area))
            {
                picks_by_area[pick.area] = [];
                areas.push(pick.area);
            }
            locs.push(pick.loc);
            picks_by_loc[pick.loc] = pick;
            picks_by_area[pick.area].push(pick);
            picks_by_zone[pick.zone].push(pick);
        }
    });
});



function is_match(pickup, searchstr) {
    searchstr = searchstr.toLowerCase();
    return pickup.label.toLowerCase().includes(searchstr) || pickup.value.toLowerCase().includes(searchstr);
} 

function uniq(array) {
    let seen = [];
    return array.filter(item => seen.includes(item) ? false : (seen.push(item) && true));
}
 
const hide_opacity = .2;
const seed_name_regex = new RegExp("^[^ ?=/]+$");
const select_styles = {
  option: (base, _) => ({
    ...base,
    borderBottom: '1px dotted pink',
    color: 'black',
  }),
//   multiValue: (base, _) => ({
//     ...base,
//     color: 'black',
//   }),
  }
const select_wrap = x => Array.isArray(x) ? x.map(select_wrap) : {label: x, value: x}
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
const goToCurry = (url) => () => { window.location.href = url } 

export {PickupMarker, PickupMarkersList, download, getStuffType, locs, picks_by_loc, getMapCrs, pickups, distance, get_icon, select_wrap,
        point, picks_by_type, picks_by_zone, zones, stuff_types, areas, picks_by_area, select_styles,
        is_match, str_ids, hide_opacity, seed_name_regex, uniq, listSwap, goToCurry, base_url, pickup_icons};