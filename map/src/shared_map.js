import React from 'react';
import Leaflet from 'leaflet';
import {Marker} from 'react-leaflet';
function point(x, y) {
  return {x: x, y: y};
};

function download(filename, text) {
  var element = document.createElement('a');
  element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(text));
  element.setAttribute('download', filename);

  element.style.display = 'none';
  document.body.appendChild(element);

  element.click();

  document.body.removeChild(element);
}


const pickup_icons = {
	"SK": new Leaflet.Icon({iconUrl: '../sprites/skill-tree.png', iconSize: new Leaflet.Point(32, 32), iconAnchor: new Leaflet.Point(0, 32)}),
	"HC": new Leaflet.Icon({iconUrl: '../sprites/health-cell.png', iconSize: new Leaflet.Point(24, 24)}),
	"AC": new Leaflet.Icon({iconUrl: '../sprites/ability-cell.png', iconSize: new Leaflet.Point(24, 24)}),
	"EC": new Leaflet.Icon({iconUrl: '../sprites/energy-cell.png', iconSize: new Leaflet.Point(24, 24)}),
	"MS": new Leaflet.Icon({iconUrl: '../sprites/map-fragment.png', iconSize: new Leaflet.Point(24, 24)}),
	"EX": new Leaflet.Icon({iconUrl: '../sprites/xp.png', iconSize: new Leaflet.Point(24, 24)}),
	"Pl": new Leaflet.Icon({iconUrl: '../sprites/xp.png', iconSize: new Leaflet.Point(30, 10)}),
	"KS": new Leaflet.Icon({iconUrl: '../sprites/keystone.png', iconSize: new Leaflet.Point(24, 24)}),
};

function getMapCrs() {
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
	  transformation: new Leaflet.Transformation(scaleX, mapOriginX, scaleY, mapOriginY)
	});

	return Leaflet.CRS.MySimple;
};

const PickupMarker = ({ map, position, inner, icon, onClick}) => (
  <Marker map={map} position={position} icon={icon} onClick={onClick}>
  {inner}
  </Marker>
);

const PickupMarkersList = ({ map, markers }) => {
  const items = markers.map(({ key, ...props }) => (
      <PickupMarker key={key} map={map} {...props} />
  ));
  return <div style={{display: 'none'}}>{items}</div>;
};

function pickup_name(code, id) {
	let names = {
		"SK": {0:"Bash", 2:"Charge Flame", 3:"Wall Jump", 4:"Stomp", 5:"Double Jump",8:"Charge Jump",12:"Climb",14:"Glide",50:"Dash",51:"Grenade"},
		"EV": {0:"Water Vein", 1:"Clean Water", 2:"Gumon Seal", 3:"Wind Restored", 4:"Sunstone", 5:"Warmth Returned"},
		"RB":  {17:"Water Vein Shard", 19: "Gumon Seal Shard", 21: "Sunstone Shard", 6: "Spirit Flame Upgrade", 13: "Health Regeneration", 15: "Energy Regeneration", 8: "Explosion Power Upgrade", 9:  "Spirit Light Efficiency", 10: "Extra Air Dash", 11:  "Charge Dash Efficiency", 12:  "Extra Double Jump", 0: "Mega Health", 1: "Mega Energy"}	
	};
	if(names.hasOwnProperty(code) && names[code][1*id])
		return names[code][1*id];
	 
	if(code === "EX") 
		return id+ " Experience";
	if(code === "HC") 
		return "Health Cell";
	if(code === "EC") 
		return "Energy Cell";
	if(code === "AC") 
		return "Ability Cell";
	if(code === "MS") 
		return "Mapstone";
	if(code === "KS") 
		return "Keystone";
}



const pickups = {
"SK": [
	{"loc": -4600020, "zone": "ValleyMain", "name": "SKGlide", "x": -460, "y": -20},
	{"loc": -6959592, "zone": "ChargeJump", "name": "SKChargeJump", "x": -696, "y": 408},
	{"loc": -3160308, "zone": "WallJump", "name": "SKWallJump", "x": -316, "y": -308},
	{"loc": -560160, "zone": "ChargeFlame", "name": "SKChargeFlame", "x": -56, "y": -160},
	{"loc": 2919744, "zone": "DashArea", "name": "SKDash", "x": 292, "y": -256},
	{"loc": 719620, "zone": "GrenadeArea", "name": "SKGrenade", "x": 72, "y": -380},
	{"loc": 7839588, "zone": "DoubleJumpArea", "name": "SKDoubleJump", "x": 784, "y": -412},
	{"loc": 5320328, "zone": "BashTree", "name": "SKBash", "x": 532, "y": 328},
	{"loc": 8599904, "zone": "RightSwamp", "name": "SKStomp", "x": 860, "y": -96},
	{"loc": -11880100, "zone": "Misty", "name": "SKClimb", "x": -1188, "y": -100}
],"AC": [
	{"loc": -2080116, "zone": "ValleyEntry", "name": "AC", "x": -205, "y": -113},
	{"loc": -3559936, "zone": "ValleyRight", "name": "AC", "x": -355, "y": 65},
	{"loc": -2919980, "zone": "BirdStompCell", "name": "AC", "x": -292, "y": 20},
	{"loc": -4160080, "zone": "ValleyMainFACS", "name": "AC", "x": -415, "y": -80},
	{"loc": -4600188, "zone": "OutsideForlornGrenade", "name": "AC", "x": -460, "y": -187},
	{"loc": -3520100, "zone": "LowerValley", "name": "AC", "x": -350, "y": -98},
	{"loc": -5119796, "zone": "Sorrow", "name": "AC", "x": -510, "y": 204},
	{"loc": -6719712, "zone": "LeftSorrow", "name": "AC", "x": -671, "y": 289},
	{"loc": -6479528, "zone": "AboveChargeJump", "name": "AC", "x": -646, "y": 473},
	{"loc": -10760004, "zone": "Misty", "name": "AC", "x": -1075, "y": -2},
	{"loc": 799804, "zone": "SunkenGladesNadeTree", "name": "AC", "x": 82, "y": -196},
	{"loc": -480168, "zone": "AboveFourthHealth", "name": "AC", "x": -48, "y": -166},
	{"loc": -2160176, "zone": "SpiritCavernsAC", "name": "AC", "x": -216, "y": -176},
	{"loc": -1680140, "zone": "GladesLaserGrenade", "name": "AC", "x": -165, "y": -140},
	{"loc": 639888, "zone": "SpiderSacEnergyDoor", "name": "AC", "x": 64, "y": -109},
	{"loc": 919908, "zone": "SpiderSacGrenadeDoor", "name": "AC", "x": 93, "y": -92},
	{"loc": 1799708, "zone": "DashArea", "name": "AC", "x": 183, "y": -291},
	{"loc": 2519668, "zone": "UpperGrenadeArea", "name": "AC", "x": 252, "y": -331},
	{"loc": 2759624, "zone": "LowerBlackRootCell", "name": "AC", "x": 279, "y": -375},
	{"loc": 3879576, "zone": "FarRightBlackRoot", "name": "AC", "x": 391, "y": -423},
	{"loc": 2079568, "zone": "LeftBlackRoot", "name": "AC", "x": 208, "y": -431},
	{"loc": 4559492, "zone": "FinalBlackRoot", "name": "AC", "x": 459, "y": -506},
	{"loc": 5239456, "zone": "BlackRootWater", "name": "AC", "x": 527, "y": -544},
	{"loc": 6999916, "zone": "MoonGrotto", "name": "AC", "x": 703, "y": -82},
	{"loc": 3319936, "zone": "HollowGroveTree", "name": "AC", "x": 333, "y": -61},
	{"loc": 3519820, "zone": "GroveWaterStomp", "name": "AC", "x": 354, "y": -178},
	{"loc": 4079964, "zone": "LeftGinsoCell", "name": "AC", "x": 409, "y": -34},
	{"loc": 3359784, "zone": "DeathWater", "name": "AC", "x": 339, "y": -216},
	{"loc": 4999892, "zone": "MortarCell", "name": "AC", "x": 502, "y": -108},
	{"loc": 4479704, "zone": "SideFallCell", "name": "AC", "x": 451, "y": -296},
	{"loc": 4479568, "zone": "GumoHideoutRedirectAC", "name": "AC", "x": 449, "y": -430},
	{"loc": 6399872, "zone": "DrainlessCell", "name": "AC", "x": 643, "y": -127},
	{"loc": 1759964, "zone": "BelowHoruFields", "name": "AC", "x": 176, "y": -34}
], "MP": [
	{"loc": 24, "zone": "Progressive", "name": "MS1", "x": 0, "y": 1},
	{"loc": 28, "zone": "Progressive", "name": "MS2", "x": 0, "y": 2},
	{"loc": 32, "zone": "Progressive", "name": "MS3", "x": 0, "y": 3},
	{"loc": 36, "zone": "Progressive", "name": "MS4", "x": 0, "y": 4},
	{"loc": 40, "zone": "Progressive", "name": "MS5", "x": 0, "y": 5},
	{"loc": 44, "zone": "Progressive", "name": "MS6", "x": 0, "y": 6},
	{"loc": 48, "zone": "Progressive", "name": "MS7", "x": 0, "y": 7},
	{"loc": 52, "zone": "Progressive", "name": "MS8", "x": 0, "y": 8},
	{"loc": 56, "zone": "Progressive", "name": "MS9", "x": 0, "y": 9}
 ], "Ma": [
	{"loc": 3479880, "zone": "HollowGroveMapStone", "name": "MapStone", "x": 351, "y": -119},
	{"loc": -4080172, "zone": "ValleyMapStone", "name": "MapStone", "x": -408, "y": -170},
	{"loc": -8440308, "zone": "ForlornMapStone", "name": "MapStone", "x": -843, "y": -308},
	{"loc": -4519716, "zone": "SorrowMapStone", "name": "MapStone", "x": -451, "y": 284},
	{"loc": -840248, "zone": "WallJumpMapStone", "name": "MapStone", "x": -81, "y": -248},
	{"loc": 4159708, "zone": "BlackrootMapStone", "name": "MapStone", "x": 418, "y": -291},
	{"loc": 4759608, "zone": "GumoHideoutMapStone", "name": "MapStone", "x": 477, "y": -389},
	{"loc": 6759868, "zone": "SwampMapStone", "name": "MapStone", "x": 677, "y": -129},
	{"loc": 560340, "zone": "HoruMapStone", "name": "MapStone", "x": 56, "y": 343}
 ], "EC": [
	{"loc": 2719900, "zone": "UpperGroveSpiderEnergy", "name": "EC", "x": 272, "y": -97},
	{"loc": -3200164, "zone": "ValleyGrenadeWater", "name": "EC", "x": -320, "y": -162},
	{"loc": -6279608, "zone": "LeftSorrow", "name": "EC", "x": -627, "y": 393},
	{"loc": -400240, "zone": "SunkenGladesMainPoolDeep", "name": "EC", "x": -40, "y": -239},
	{"loc": -3360288, "zone": "LeftWallJump", "name": "EC", "x": -336, "y": -288},
	{"loc": -1560188, "zone": "GladesLaser", "name": "EC", "x": -155, "y": -186},
	{"loc": 599844, "zone": "SpiderSacEnergy", "name": "EC", "x": 60, "y": -155},
	{"loc": 4199828, "zone": "MoonGrotto", "name": "EC", "x": 423, "y": -169},
	{"loc": 5439640, "zone": "MobileGumoHideout", "name": "EC", "x": 545, "y": -357},
	{"loc": 5119556, "zone": "HideoutRedirect", "name": "EC", "x": 515, "y": -441},
	{"loc": 5360432, "zone": "UpperGinsoFloors", "name": "EC", "x": 536, "y": 434},
	{"loc": 7199904, "zone": "SwampEnergy", "name": "EC", "x": 722, "y": -95},
	{"loc": 1720000, "zone": "HoruFieldsEnergy", "name": "EC", "x": 175, "y": 1},
	{"loc": 2480400, "zone": "Horu", "name": "EC", "x": 249, "y": 403}
 ], "KS": [
	{"loc": -8600356, "zone": "Forlorn", "name": "KS", "x": -858, "y": -353},
	{"loc": -8920328, "zone": "Forlorn", "name": "KS", "x": -892, "y": -328},
	{"loc": -8880252, "zone": "Forlorn", "name": "KS", "x": -888, "y": -251},
	{"loc": -8720256, "zone": "Forlorn", "name": "KS", "x": -869, "y": -255},
	{"loc": -4879680, "zone": "Sorrow", "name": "KS", "x": -485, "y": 323},
	{"loc": -5039728, "zone": "Sorrow", "name": "KS", "x": -503, "y": 274},
	{"loc": -5159700, "zone": "Sorrow", "name": "KS", "x": -514, "y": 303},
	{"loc": -5959772, "zone": "Sorrow", "name": "KS", "x": -596, "y": 229},
	{"loc": -6079672, "zone": "LeftSorrow", "name": "KS", "x": -608, "y": 329},
	{"loc": -6119656, "zone": "LeftSorrow", "name": "KS", "x": -612, "y": 347},
	{"loc": -6039640, "zone": "LeftSorrow", "name": "KS", "x": -604, "y": 361},
	{"loc": -6159632, "zone": "LeftSorrow", "name": "KS", "x": -613, "y": 371},
	{"loc": -4559584, "zone": "UpperSorrow", "name": "KS", "x": -456, "y": 419},
	{"loc": -4159572, "zone": "UpperSorrow", "name": "KS", "x": -414, "y": 429},
	{"loc": -5159576, "zone": "UpperSorrow", "name": "KS", "x": -514, "y": 427},
	{"loc": -5919556, "zone": "UpperSorrow", "name": "KS", "x": -592, "y": 445},
	{"loc": -10759968, "zone": "Misty", "name": "KS", "x": -1076, "y": 32},
	{"loc": -9120036, "zone": "MistyPostClimb", "name": "KS", "x": -912, "y": -36},
	{"loc": -7680144, "zone": "MistyPostClimb", "name": "KS", "x": -768, "y": -144},
	{"loc": 799776, "zone": "SunkenGladesRunaway", "name": "KS", "x": 83, "y": -222},
	{"loc": -120208, "zone": "SunkenGladesRunaway", "name": "KS", "x": -11, "y": -206},
	{"loc": -600244, "zone": "WallJump", "name": "KS", "x": -59, "y": -244},
	{"loc": -2400212, "zone": "LeftWallJump", "name": "KS", "x": -238, "y": -212},
	{"loc": -1840196, "zone": "SpiritCaverns", "name": "KS", "x": -182, "y": -193},
	{"loc": -2200184, "zone": "SpiritCaverns", "name": "KS", "x": -217, "y": -183},
	{"loc": -1800156, "zone": "SpiritCaverns", "name": "KS", "x": -177, "y": -154},
	{"loc": -2200148, "zone": "SpiritCavernsTopLeft", "name": "KS", "x": -217, "y": -146},
	{"loc": 6199596, "zone": "GumoHideout", "name": "KS", "x": 620, "y": -404},
	{"loc": 5879616, "zone": "GumoHideout", "name": "KS", "x": 590, "y": -384},
	{"loc": 5280264, "zone": "LowerGinsoTree", "name": "KS", "x": 531, "y": 267},
	{"loc": 5400276, "zone": "LowerGinsoTree", "name": "KS", "x": 540, "y": 277},
	{"loc": 5080304, "zone": "LowerGinsoTree", "name": "KS", "x": 508, "y": 304},
	{"loc": 5280296, "zone": "LowerGinsoTree", "name": "KS", "x": 529, "y": 297},
	{"loc": 5040476, "zone": "UpperGinsoTree", "name": "KS", "x": 507, "y": 476},
	{"loc": 5320488, "zone": "UpperGinsoTree", "name": "KS", "x": 535, "y": 488},
	{"loc": 5280500, "zone": "UpperGinsoTree", "name": "KS", "x": 531, "y": 502},
	{"loc": 5080496, "zone": "UpperGinsoTree", "name": "KS", "x": 508, "y": 498},
	{"loc": 6839792, "zone": "SwampWater", "name": "KS", "x": 684, "y": -205},
	{"loc": 7639816, "zone": "SwampWater", "name": "KS", "x": 766, "y": -183}
], "EX": [
	{"loc": 1719892, "zone": "UpperGroveSpiderArea", "name": "EX200", "x": 174, "y": -105},
	{"loc": 919772, "zone": "SunkenGladesRunaway", "name": "EX15", "x": 92, "y": -227},
	{"loc": -1560272, "zone": "SunkenGladesRunaway", "name": "EX15", "x": -154, "y": -271},
	{"loc": 559720, "zone": "SunkenGladesNadePool", "name": "EX200", "x": 59, "y": -280},
	{"loc": 39756, "zone": "SunkenGladesMainPool", "name": "EX100", "x": 5, "y": -241},
	{"loc": 2559800, "zone": "FronkeyWalkRoof", "name": "EX200", "x": 257, "y": -199},
	{"loc": -2840236, "zone": "WallJump", "name": "EX15", "x": -283, "y": -236},
	{"loc": 2999808, "zone": "DeathGauntlet", "name": "EX100", "x": 303, "y": -190},
	{"loc": -2480280, "zone": "RightWallJump", "name": "EX200", "x": -245, "y": -277},
	{"loc": -2480208, "zone": "LeftWallJump", "name": "EX15", "x": -247, "y": -207},
	{"loc": 39804, "zone": "ChargeFlameOrb", "name": "EX100", "x": 4, "y": -196},
	{"loc": -160096, "zone": "ChargeFlameTree", "name": "EX100", "x": -14, "y": -95},
	{"loc": 1519708, "zone": "DashArea", "name": "EX100", "x": 154, "y": -291},
	{"loc": 1959768, "zone": "DashArea", "name": "EX100", "x": 197, "y": -229},
	{"loc": 3039696, "zone": "RazielNo", "name": "EX100", "x": 304, "y": -303},
	{"loc": 4319676, "zone": "BoulderExp", "name": "EX100", "x": 432, "y": -324},
	{"loc": 2239640, "zone": "RightGrenadeArea", "name": "EX100", "x": 224, "y": -359},
	{"loc": 3359580, "zone": "RightBlackRoot", "name": "EX100", "x": 339, "y": -418},
	{"loc": 4599508, "zone": "FinalBlackRoot", "name": "EX100", "x": 462, "y": -489},
	{"loc": 3039472, "zone": "FinalBlackRoot", "name": "EX100", "x": 307, "y": -525},
	{"loc": 6159900, "zone": "MoonGrotto", "name": "EX100", "x": 618, "y": -98},
	{"loc": 6639952, "zone": "RightGinsoOrb", "name": "EX200", "x": 666, "y": -48},
	{"loc": 1839836, "zone": "GroveWater", "name": "EX100", "x": 187, "y": -163},
	{"loc": 3559792, "zone": "DeathStomp", "name": "EX200", "x": 356, "y": -207},
	{"loc": 4759860, "zone": "UpperGrottoOrbs", "name": "EX100", "x": 477, "y": -140},
	{"loc": 4319892, "zone": "UpperGrottoOrbs", "name": "EX100", "x": 432, "y": -108},
	{"loc": 3639888, "zone": "UpperGrottoOrbs", "name": "EX100", "x": 365, "y": -109},
	{"loc": 4479832, "zone": "UpperGrotto200", "name": "EX200", "x": 449, "y": -166},
	{"loc": 5919864, "zone": "SwampGrottoWater", "name": "EX200", "x": 595, "y": -136},
	{"loc": 4199724, "zone": "MoonGrottoEnergyWater", "name": "EX100", "x": 423, "y": -274},
	{"loc": 5519856, "zone": "MoonGrottoAirOrb", "name": "EX100", "x": 552, "y": -141},
	{"loc": 5719620, "zone": "GumoHideout", "name": "EX100", "x": 572, "y": -378},
	{"loc": 4959628, "zone": "GumoHideoutPartialMobile", "name": "EX15", "x": 496, "y": -369},
	{"loc": 4639628, "zone": "GumoHideoutPartialMobile", "name": "EX15", "x": 467, "y": -369},
	{"loc": 7559600, "zone": "MobileDoubleJumpArea", "name": "EX100", "x": 759, "y": -398},
	{"loc": 5639752, "zone": "MobileGumoHideout", "name": "EX100", "x": 567, "y": -246},
	{"loc": 4039612, "zone": "MobileGumoHideout", "name": "EX100", "x": 406, "y": -386},
	{"loc": 3279644, "zone": "MobileGumoHideout", "name": "EX100", "x": 328, "y": -353},
	{"loc": 3959588, "zone": "GumoHideoutWater", "name": "EX100", "x": 397, "y": -411},
	{"loc": 5039560, "zone": "HideoutRedirect", "name": "EX200", "x": 505, "y": -439},
	{"loc": 5200140, "zone": "LowerGinsoTree", "name": "EX100", "x": 523, "y": 142},
	{"loc": 5160336, "zone": "UpperGinsoTree", "name": "EX100", "x": 518, "y": 339},
	{"loc": 5160384, "zone": "UpperGinsoFloors", "name": "EX100", "x": 517, "y": 384},
	{"loc": 5280404, "zone": "UpperGinsoFloors", "name": "EX100", "x": 530, "y": 407},
	{"loc": 4560564, "zone": "TopGinsoTree", "name": "EX100", "x": 456, "y": 566},
	{"loc": 4680612, "zone": "TopGinsoTree", "name": "EX100", "x": 471, "y": 614},
	{"loc": 6080608, "zone": "TopGinsoTreePlant", "name": "Plant", "x": 610, "y": 611},
	{"loc": 5320660, "zone": "GinsoEscape", "name": "EX200", "x": 534, "y": 661},
	{"loc": 5360732, "zone": "GinsoEscape", "name": "EX100", "x": 537, "y": 733},
	{"loc": 5320824, "zone": "GinsoEscape", "name": "EX100", "x": 533, "y": 827},
	{"loc": 5160864, "zone": "GinsoEscape", "name": "EX100", "x": 519, "y": 867},
	{"loc": 6359836, "zone": "DrainExp", "name": "EX100", "x": 636, "y": -162},
	{"loc": 7599824, "zone": "SwampWater", "name": "EX100", "x": 761, "y": -173},
	{"loc": 7679852, "zone": "SwampStomp", "name": "EX100", "x": 770, "y": -148},
	{"loc": 9119928, "zone": "RightSwampCJump", "name": "EX200", "x": 914, "y": -71},
	{"loc": 8839900, "zone": "RightSwampStomp", "name": "EX100", "x": 884, "y": -98},
	{"loc": 8719856, "zone": "RightSwampGrenade", "name": "EX200", "x": 874, "y": -143},
	{"loc": 959960, "zone": "HoruFields", "name": "EX200", "x": 97, "y": -37},
	{"loc": 1920384, "zone": "Horu", "name": "EX100", "x": 193, "y": 384},
	{"loc": 1880164, "zone": "HoruStomp", "name": "EX200", "x": 191, "y": 165},
	{"loc": 2520192, "zone": "HoruStomp", "name": "EX200", "x": 253, "y": 194},
	{"loc": 1600136, "zone": "HoruStomp", "name": "EX200", "x": 163, "y": 136},
	{"loc": -1919808, "zone": "HoruStomp", "name": "EX200", "x": -191, "y": 194},
	{"loc": -319852, "zone": "HoruStomp", "name": "EX200", "x": -29, "y": 148},
	{"loc": 120164, "zone": "HoruStomp", "name": "EX200", "x": 13, "y": 164},
	{"loc": 1280164, "zone": "HoruStomp", "name": "EX200", "x": 129, "y": 165},
	{"loc": 960128, "zone": "HoruStomp", "name": "EX200", "x": 98, "y": 130},
	{"loc": 1040112, "zone": "DoorWarp", "name": "EX200", "x": 106, "y": 112},
	{"loc": -2240084, "zone": "ValleyEntryTree", "name": "EX100", "x": -221, "y": -84},
	{"loc": -4199936, "zone": "ValleyRight", "name": "EX100", "x": -418, "y": 67},
	{"loc": -5479948, "zone": "ValleyMain", "name": "EX200", "x": -546, "y": 54},
	{"loc": -8240012, "zone": "ValleyMain", "name": "EX100", "x": -822, "y": -9},
	{"loc": -5719844, "zone": "PreSorrowOrb", "name": "EX200", "x": -572, "y": 157},
	{"loc": -3600088, "zone": "ValleyWater", "name": "EX100", "x": -359, "y": -87},
	{"loc": -5400104, "zone": "LowerValley", "name": "EX100", "x": -538, "y": -104},
	{"loc": -4600256, "zone": "OutsideForlornTree", "name": "EX100", "x": -460, "y": -255},
	{"loc": -5160280, "zone": "OutsideForlornWater", "name": "EX100", "x": -514, "y": -277},
	{"loc": -5400236, "zone": "OutsideForlornCliff", "name": "EX200", "x": -538, "y": -234},
	{"loc": -7040392, "zone": "Forlorn", "name": "EX200", "x": -703, "y": -390},
	{"loc": -8440352, "zone": "Forlorn", "name": "EX100", "x": -841, "y": -350},
	{"loc": -6799732, "zone": "LeftSorrowGrenade", "name": "EX200", "x": -677, "y": 269},
	{"loc": -5479592, "zone": "UpperSorrow", "name": "EX100", "x": -545, "y": 409},
	{"loc": -9799980, "zone": "Misty", "name": "EX100", "x": -979, "y": 23},
	{"loc": -10839992, "zone": "Misty", "name": "EX100", "x": -1082, "y": 8},
	{"loc": -10120036, "zone": "Misty", "name": "EX100", "x": -1009, "y": -35},
	{"loc": -8400124, "zone": "MistyPostClimb", "name": "EX100", "x": -837, "y": -123},
	{"loc": -7960144, "zone": "MistyPostClimb", "name": "EX200", "x": -796, "y": -144},
	{"loc": -6720040, "zone": "MistyEndGrenade", "name": "EX200", "x": -671, "y": -39}
], "MS": [
	{"loc": 1480360, "zone": "Horu", "name": "MS", "x": 148, "y": 363},
	{"loc": -5640092, "zone": "LowerValley", "name": "MS", "x": -561, "y": -89},
	{"loc": -4440152, "zone": "OutsideForlornMS", "name": "MS", "x": -443, "y": -152},
	{"loc": -4359680, "zone": "SorrowMapFragment", "name": "MS", "x": -435, "y": 322},
	{"loc": 3439744, "zone": "BlackrootMap", "name": "MS", "x": 346, "y": -255},
	{"loc": -1840228, "zone": "LeftWallJump", "name": "MS", "x": -184, "y": -227},
	{"loc": 2999904, "zone": "HollowGrove", "name": "MS", "x": 300, "y": -94},
	{"loc": 5119584, "zone": "GumoHideout", "name": "MS", "x": 513, "y": -413},
	{"loc": 7959788, "zone": "SwampWater", "name": "MS", "x": 796, "y": -210}
 ], "HC": [
	{"loc": -6280316, "zone": "RightForlorn", "name": "HC", "x": -625, "y": -315},
	{"loc": -6119704, "zone": "SorrowHealth", "name": "HC", "x": -609, "y": 299},
	{"loc": -800192, "zone": "WallJump", "name": "HC", "x": -80, "y": -189},
	{"loc": 5799932, "zone": "UpperGrottoOrbs", "name": "HC", "x": 581, "y": -67},
	{"loc": 1479880, "zone": "SpiderSacHealth", "name": "HC", "x": 151, "y": -117},
	{"loc": 3919688, "zone": "BlackrootGrottoConnection", "name": "HC", "x": 394, "y": -309},
	{"loc": 2599880, "zone": "UpperGroveSpiderArea", "name": "HC", "x": 261, "y": -117},
	{"loc": 5399808, "zone": "RightGrottoHealth", "name": "HC", "x": 543, "y": -189},
	{"loc": 4239780, "zone": "MoonGrottoEnergyTop", "name": "HC", "x": 424, "y": -220},
	{"loc": 3919624, "zone": "MobileGumoHideout", "name": "HC", "x": 393, "y": -375},
	{"loc": 3199820, "zone": "DeathGauntletRoof", "name": "HC", "x": 321, "y": -179},
	{"loc": 1599920, "zone": "HoruFieldsStomp", "name": "HC", "x": 160, "y": -78}
], "EV": [
	{"loc": 20, "zone": "End", "name": "EVWarmth", "x": 0, "y": 20},
	{"loc": 16, "zone": "Sunstone", "name": "EVHoruKey", "x": 0, "y": 16},
	{"loc": 8, "zone": "MistyEnd", "name": "EVForlornKey", "x": 0, "y": 8},
	{"loc": 12, "zone": "RightForlorn", "name": "EVWind", "x": 0, "y": 12},
	{"loc": 0, "zone": "MobileGumoHideout", "name": "EVGinsoKey", "x": 0, "y": 0},
	{"loc": 4, "zone": "GinsoEscape", "name": "EVWater", "x": 0, "y": 4}
], "Pl": [
	{"loc": 1240020, "zone": "HoruFieldsEnergyPlant", "name": "Plant", "x": 124, "y": 21},
	{"loc": 4439632, "zone": "MobileGumoHideoutPlants", "name": "Plant", "x": 447, "y": -368},
	{"loc": 4359656, "zone": "MobileGumoHideoutPlants", "name": "Plant", "x": 439, "y": -344},
	{"loc": 4919600, "zone": "MobileGumoHideoutPlants", "name": "Plant", "x": 492, "y": -400},
	{"loc": 3119768, "zone": "DashAreaPlant", "name": "Plant", "x": 313, "y": -232},
	{"loc": 3639880, "zone": "HollowGrovePlants", "name": "Plant", "x": 365, "y": -119},
	{"loc": 3279920, "zone": "HollowGrovePlants", "name": "Plant", "x": 330, "y": -78},
	{"loc": 6279880, "zone": "SwampPlant", "name": "Plant", "x": 628, "y": -120},
	{"loc": 4319860, "zone": "MoonGrottoStompPlant", "name": "Plant", "x": 435, "y": -140},
	{"loc": 5119900, "zone": "SwampMortarPlant", "name": "Plant", "x": 515, "y": -100},
	{"loc": 5399780, "zone": "UpperGrottoOrbsPlant", "name": "Plant", "x": 540, "y": -220},
	{"loc": 5359824, "zone": "MoonGrottoAirOrbPlant", "name": "Plant", "x": 537, "y": -176},
	{"loc": 3399820, "zone": "DeathGauntletRoofPlant", "name": "Plant", "x": 342, "y": -179},
	{"loc": 5400100, "zone": "LowerGinsoTreePlant", "name": "Plant", "x": 540, "y": 101},
	{"loc": -11040068, "zone": "MistyPlant", "name": "Plant", "x": -1102, "y": -67},
	{"loc": -6319752, "zone": "LeftSorrowPlant", "name": "Plant", "x": -630, "y": 249},
	{"loc": -8160268, "zone": "ForlornPlant", "name": "Plant", "x": -815, "y": -266},
	{"loc": -4799416, "zone": "SunstonePlant", "name": "Plant", "x": -478, "y": 586},
	{"loc": 3160244, "zone": "HoruStompPlant", "name": "Plant", "x": 318, "y": 245},
	{"loc": -1800088, "zone": "ValleyEntryTreePlant", "name": "Plant", "x": -179, "y": -88},
	{"loc": -4680068, "zone": "ValleyMainPlant", "name": "Plant", "x": -468, "y": -67},
	{"loc": 399844, "zone": "ChargeFlamePlant", "name": "Plant", "x": 43, "y": -156},
	{"loc": -6080316, "zone": "RightForlornPlant", "name": "Plant", "x": -607, "y": -314}
]};
 

export {PickupMarker, PickupMarkersList, download, pickup_icons, getMapCrs, pickups, pickup_name};
