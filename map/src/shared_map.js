import React from 'react';
import Leaflet from 'leaflet';
import {Marker} from 'react-leaflet';
const point = (x, y) => {return {x: x, y: y}; } 
const distance = (x1, y1, x2, y2) => Math.sqrt((x2-x1) ** 2 + (y2-y1) ** 2);

function download(filename, text) {
  var element = document.createElement('a');
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

function name_from_str(pick) {
    let parts = pick.split("|");
    return pickup_name(parts[0],parts[1])
}


function pickup_name(code, id) {
    let upgrade_names = {};
    stuff_by_type["Upgrades"].forEach(s => {
        upgrade_names[s.value.substr(3)] = s.label;
    });
    let names = {
        "SK": {0:"Bash", 2:"Charge Flame", 3:"Wall Jump", 4:"Stomp", 5:"Double Jump",8:"Charge Jump",12:"Climb",14:"Glide",50:"Dash",51:"Grenade"},
        "EV": {0:"Water Vein", 1:"Clean Water", 2:"Gumon Seal", 3:"Wind Restored", 4:"Sunstone", 5:"Warmth Returned"},
        "RB": upgrade_names,
    };
    if(names.hasOwnProperty(code) && names[code][id])
        return names[code][id];
     
    switch(code) {
        case "MU":
        case "RP":
            let parts = id.split("/");
            let names = [];
            while(parts.length > 1) {
                names.push(pickup_name(parts.shift(), parts.shift()))
            }
            if(code === "RP")
                return "Repeatable: " + names.join(", ")
            return names.join(", ")
        case "TP":
            return id + "TP";
        case "EX":
            return id+ " Experience";
        case "HC":
            return "Health Cell";
        case "AC":
            return "Ability Cell";
        case "EC":
            return "Energy Cell";
        case "KS":
            return "Keystone";
        case "MS":
            return "Mapstone";
        case "SH":
            return id;
        case "WT":
            return "Relic";
        case "HN":
            let hintParts = id.split('-');
            if(hintParts.length > 2)
                return "Hint: " + hintParts[1] + " for " + hintParts[2];
            else
                return "Hint"
        case "WS":
        case "WP":
            return "Warp to " + id + (code === "WS" ? " and save" : "")
        default:
            return code + "|" + id;
    }

}

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

const stuff_by_type = {
    "Skills" : [
        {label: "Bash", value: "SK|0"},
        {label: "Charge Flame", value: "SK|2"},
        {label: "Wall Jump", value: "SK|3"},
        {label: "Stomp", value: "SK|4"},
        {label: "Double Jump", value: "SK|5"},
        {label: "Charge Jump", value: "SK|8"},
        {label: "Climb", value: "SK|12"},
        {label: "Glide", value: "SK|14"},
        {label: "Dash", value: "SK|50"},
        {label: "Grenade", value: "SK|51"}
    ], 
    "Events": [
        {label: "Water Vein", value: "EV|0"},
        {label: "Clean Water", value: "EV|1"},
        {label: "Gumon Seal", value: "EV|2"},
        {label: "Wind Restored", value: "EV|3"},
        {label: "Sunstone", value: "EV|4"},
        {label: "Warmth Returned", value: "EV|5"}
    ],
    "Upgrades": [
        {label: "Mega Health", value: "RB|0"},
        {label: "Mega Energy", value: "RB|1"},
        {label: "Go Home", value: "RB|2"},
        {label: "Spirit Flame Upgrade", value: "RB|6"},
        {label: "Explosion Power Upgrade", value: "RB|8"},
        {label: "Spirit Light Efficiency", value: "RB|9"},
        {label: "Extra Air Dash", value: "RB|10"},
        {label: "Charge Dash Efficiency", value: "RB|11"},
        {label: "Extra Double Jump", value: "RB|12"},
        {label: "Health Regeneration", value: "RB|13"},
        {label: "Energy Regeneration", value: "RB|15"},
        {label: "Water Vein Shard", value: "RB|17"},
        {label: "Gumon Seal Shard", value: "RB|19"},
        {label: "Sunstone Shard", value: "RB|21"},
        {label: "Warmth Fragment", value: "RB|28"},
        {label: "Bleeding", value: "RB|30"},
        {label: "Lifesteal", value: "RB|31"},
        {label: "Manavamp", value: "RB|32"},
        {label: "Skill Velocity Upgrade", value: "RB|33"},
        {label: "Disable Alt+R", value: "RB|34"}, 
        {label: "Enable Alt+R", value: "RB|35"}, 
        {label: "Gravity Suit", value: "RB|36"}, 
        {label: "Remove Wall Jump", value: "RB|40"}, 
        {label: "Remove Charge Flame", value: "RB|41"}, 
        {label: "Remove Double Jump", value: "RB|42"}, 
        {label: "Remove Bash", value: "RB|43"}, 
        {label: "Remove Stomp", value: "RB|44"}, 
        {label: "Remove Glide", value: "RB|45"}, 
        {label: "Remove Climb", value: "RB|46"}, 
        {label: "Remove Charge Jump", value: "RB|47"}, 
        {label: "Remove Dash", value: "RB|48"}, 
        {label: "Remove Grenade", value: "RB|49"}, 
        {label: "Stompnade Hint", value: "RB|81"}, 
        {label: "Polarity Shift", value: "RB|101"},
        {label: "Gravity Swap", value: "RB|102"},
        {label: "ExtremeSpeed", value: "RB|103"},
        {label: "Roose's Wind", value: "RB|104"},
        {label: "Respawn Without Dying", value: "RB|105"},
        {label: "Respec", value: "RB|106"},
        {label: "Level Explosion", value: "RB|107"},
    ],
    "Teleporters": [
        {label: "Grotto TP", value: "TP|Grotto"},
        {label: "Grove TP", value: "TP|Grove"},
        {label: "Forlorn TP", value: "TP|Forlorn"},
        {label: "Valley TP", value: "TP|Valley"},
        {label: "Sorrow TP", value: "TP|Sorrow"},
        {label: "Swamp TP", value: "TP|Swamp"},
        {label: "Ginso TP", value: "TP|Ginso"},
        {label: "Horu TP", value: "TP|Horu"},
    ],
    "Cells/Stones": [
        {label: "Health Cell", value: "HC|1"},
        {label: "Energy Cell", value: "EC|1"},
        {label: "Ability Cell", value: "AC|1"},
        {label: "Keystone", value: "KS|1"},
        {label: "Mapstone", value: "MS|1"}
    ]
};


let request = new XMLHttpRequest()
request.open('GET', '/picksbytype', false)
request.send(null)
if (request.status !== 200) alert("critical error! picks_by_type could not generate")


const picks_by_type = JSON.parse(request.responseText);

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
 
const str_ids = ["TP", "NO", "SH", "WT", "MU", "HN", "WP", "RP", "WS"];
const hide_opacity = .2;
const seed_name_regex = new RegExp("^[^ ?=/]+$");
const select_styles = {
  option: (base, state) => ({
    ...base,
    borderBottom: '1px dotted pink',
    color: 'black',
  }),
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
        point, picks_by_type, picks_by_zone, zones, pickup_name, stuff_types, stuff_by_type, areas, picks_by_area, select_styles,
        is_match, str_ids, hide_opacity, seed_name_regex, uniq, name_from_str, listSwap, goToCurry, base_url};