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
	"EV": false
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

const PickupMarker = ({inner, map, position, icon, ...props}) => (
  <Marker map={map} position={position} icon={icon} {...props}>
  {inner}
  </Marker>
);

const PickupMarkersList = ({ map, markers }) => {
  const items = markers.map(({ key, ...props }) => (
      <PickupMarker key={key} map={map} {...props} />
  ));
  return <div style={{display: 'none'}}>{items}</div>;
};




const picks_by_type = {
"AC": [
	{'loc': -2080116, 'name': 'AC', 'zone': 'Valley', 'area': 'ValleyEntry', 'y': -113, 'x': -205},
	{'loc': -3559936, 'name': 'AC', 'zone': 'Valley', 'area': 'ValleyRight', 'y': 65, 'x': -355},
	{'loc': -2919980, 'name': 'AC', 'zone': 'Valley', 'area': 'BirdStompCell', 'y': 20, 'x': -292},
	{'loc': -4160080, 'name': 'AC', 'zone': 'Valley', 'area': 'ValleyMainFACS', 'y': -80, 'x': -415},
	{'loc': -4600188, 'name': 'AC', 'zone': 'Valley', 'area': 'OutsideForlornGrenade', 'y': -187, 'x': -460},
	{'loc': -3520100, 'name': 'AC', 'zone': 'Valley', 'area': 'LowerValley', 'y': -98, 'x': -350},
	{'loc': -5119796, 'name': 'AC', 'zone': 'Sorrow', 'area': 'Sorrow', 'y': 204, 'x': -510},
	{'loc': -6719712, 'name': 'AC', 'zone': 'Sorrow', 'area': 'LeftSorrow', 'y': 289, 'x': -671},
	{'loc': -6479528, 'name': 'AC', 'zone': 'Sorrow', 'area': 'AboveChargeJump', 'y': 473, 'x': -646},
	{'loc': -10760004, 'name': 'AC', 'zone': 'Misty', 'area': 'Misty', 'y': -2, 'x': -1075},
	{'loc': 799804, 'name': 'AC', 'zone': 'Glades', 'area': 'SunkenGladesNadeTree', 'y': -196, 'x': 82},
	{'loc': -480168, 'name': 'AC', 'zone': 'Glades', 'area': 'AboveFourthHealth', 'y': -166, 'x': -48},
	{'loc': -2160176, 'name': 'AC', 'zone': 'Glades', 'area': 'SpiritCavernsAC', 'y': -176, 'x': -216},
	{'loc': -1680140, 'name': 'AC', 'zone': 'Glades', 'area': 'GladesLaserGrenade', 'y': -140, 'x': -165},
	{'loc': 639888, 'name': 'AC', 'zone': 'Grove', 'area': 'SpiderSacEnergyDoor', 'y': -109, 'x': 64},
	{'loc': 919908, 'name': 'AC', 'zone': 'Grove', 'area': 'SpiderSacGrenadeDoor', 'y': -92, 'x': 93},
	{'loc': 1799708, 'name': 'AC', 'zone': 'Blackroot', 'area': 'DashArea', 'y': -291, 'x': 183},
	{'loc': 2519668, 'name': 'AC', 'zone': 'Blackroot', 'area': 'UpperGrenadeArea', 'y': -331, 'x': 252},
	{'loc': 2759624, 'name': 'AC', 'zone': 'Blackroot', 'area': 'LowerBlackRootCell', 'y': -375, 'x': 279},
	{'loc': 3879576, 'name': 'AC', 'zone': 'Blackroot', 'area': 'FarRightBlackRoot', 'y': -423, 'x': 391},
	{'loc': 2079568, 'name': 'AC', 'zone': 'Blackroot', 'area': 'LeftBlackRoot', 'y': -431, 'x': 208},
	{'loc': 4559492, 'name': 'AC', 'zone': 'Blackroot', 'area': 'FinalBlackRoot', 'y': -506, 'x': 459},
	{'loc': 5239456, 'name': 'AC', 'zone': 'Blackroot', 'area': 'BlackRootWater', 'y': -544, 'x': 527},
	{'loc': 6999916, 'name': 'AC', 'zone': 'Grotto', 'area': 'MoonGrotto', 'y': -82, 'x': 703},
	{'loc': 3319936, 'name': 'AC', 'zone': 'Grove', 'area': 'HollowGroveTree', 'y': -61, 'x': 333},
	{'loc': 3519820, 'name': 'AC', 'zone': 'Grove', 'area': 'GroveWaterStomp', 'y': -178, 'x': 354},
	{'loc': 4079964, 'name': 'AC', 'zone': 'Swamp', 'area': 'LeftGinsoCell', 'y': -34, 'x': 409},
	{'loc': 3359784, 'name': 'AC', 'zone': 'Grove', 'area': 'DeathWater', 'y': -216, 'x': 339},
	{'loc': 4999892, 'name': 'AC', 'zone': 'Swamp', 'area': 'MortarCell', 'y': -108, 'x': 502},
	{'loc': 4479704, 'name': 'AC', 'zone': 'Grotto', 'area': 'SideFallCell', 'y': -296, 'x': 451},
	{'loc': 4479568, 'name': 'AC', 'zone': 'Grotto', 'area': 'GumoHideoutRedirectAC', 'y': -430, 'x': 449},
	{'loc': 6399872, 'name': 'AC', 'zone': 'Swamp', 'area': 'DrainlessCell', 'y': -127, 'x': 643},
	{'loc': 1759964, 'name': 'AC', 'zone': 'Grove', 'area': 'BelowHoruFields', 'y': -34, 'x': 176},
], "Ma": [
	{'loc': 3479880, 'name': 'MapStone', 'zone': 'Grove', 'area': 'HollowGroveMapStone', 'y': -119, 'x': 351},
	{'loc': -4080172, 'name': 'MapStone', 'zone': 'Valley', 'area': 'ValleyMapStone', 'y': -170, 'x': -408},
	{'loc': -8440308, 'name': 'MapStone', 'zone': 'Forlorn', 'area': 'ForlornMapStone', 'y': -308, 'x': -843},
	{'loc': -4519716, 'name': 'MapStone', 'zone': 'Sorrow', 'area': 'SorrowMapStone', 'y': 284, 'x': -451},
	{'loc': -840248, 'name': 'MapStone', 'zone': 'Glades', 'area': 'WallJumpMapStone', 'y': -248, 'x': -81},
	{'loc': 4159708, 'name': 'MapStone', 'zone': 'Blackroot', 'area': 'BlackrootMapStone', 'y': -291, 'x': 418},
	{'loc': 4759608, 'name': 'MapStone', 'zone': 'Grotto', 'area': 'GumoHideoutMapStone', 'y': -389, 'x': 477},
	{'loc': 6759868, 'name': 'MapStone', 'zone': 'Swamp', 'area': 'SwampMapStone', 'y': -129, 'x': 677},
	{'loc': 560340, 'name': 'MapStone', 'zone': 'Horu', 'area': 'HoruMapStone', 'y': 343, 'x': 56},
], "EC": [
	{'loc': 2719900, 'name': 'EC', 'zone': 'Grove', 'area': 'UpperGroveSpiderEnergy', 'y': -97, 'x': 272},
	{'loc': -3200164, 'name': 'EC', 'zone': 'Valley', 'area': 'ValleyGrenadeWater', 'y': -162, 'x': -320},
	{'loc': -6279608, 'name': 'EC', 'zone': 'Sorrow', 'area': 'LeftSorrow', 'y': 393, 'x': -627},
	{'loc': -280256, 'name': 'EC', 'zone': 'Glades', 'area': 'SunkenGladesRunaway', 'y': -256, 'x': -28},
	{'loc': -400240, 'name': 'EC', 'zone': 'Glades', 'area': 'SunkenGladesMainPoolDeep', 'y': -239, 'x': -40},
	{'loc': -3360288, 'name': 'EC', 'zone': 'Glades', 'area': 'LeftWallJump', 'y': -288, 'x': -336},
	{'loc': -1560188, 'name': 'EC', 'zone': 'Glades', 'area': 'GladesLaser', 'y': -186, 'x': -155},
	{'loc': 599844, 'name': 'EC', 'zone': 'Grove', 'area': 'SpiderSacEnergy', 'y': -155, 'x': 60},
	{'loc': 4199828, 'name': 'EC', 'zone': 'Grotto', 'area': 'MoonGrotto', 'y': -169, 'x': 423},
	{'loc': 5439640, 'name': 'EC', 'zone': 'Grotto', 'area': 'MobileGumoHideout', 'y': -357, 'x': 545},
	{'loc': 5119556, 'name': 'EC', 'zone': 'Grotto', 'area': 'HideoutRedirect', 'y': -441, 'x': 515},
	{'loc': 5360432, 'name': 'EC', 'zone': 'Ginso', 'area': 'UpperGinsoFloors', 'y': 434, 'x': 536},
	{'loc': 7199904, 'name': 'EC', 'zone': 'Swamp', 'area': 'SwampEnergy', 'y': -95, 'x': 722},
	{'loc': 1720000, 'name': 'EC', 'zone': 'Grove', 'area': 'HoruFieldsEnergy', 'y': 1, 'x': 175},
	{'loc': 2480400, 'name': 'EC', 'zone': 'Horu', 'area': 'Horu', 'y': 403, 'x': 249},
], "EX": [
	{'loc': 1719892, 'name': 'EX200', 'zone': 'Grove', 'area': 'UpperGroveSpiderArea', 'y': -105, 'x': 174},
	{'loc': 919772, 'name': 'EX15', 'zone': 'Glades', 'area': 'SunkenGladesRunaway', 'y': -227, 'x': 92},
	{'loc': -1560272, 'name': 'EX15', 'zone': 'Glades', 'area': 'SunkenGladesRunaway', 'y': -271, 'x': -154},
	{'loc': 559720, 'name': 'EX200', 'zone': 'Glades', 'area': 'SunkenGladesNadePool', 'y': -280, 'x': 59},
	{'loc': 39756, 'name': 'EX100', 'zone': 'Glades', 'area': 'SunkenGladesMainPool', 'y': -241, 'x': 5},
	{'loc': 2559800, 'name': 'EX200', 'zone': 'Glades', 'area': 'FronkeyWalkRoof', 'y': -199, 'x': 257},
	{'loc': -2840236, 'name': 'EX15', 'zone': 'Glades', 'area': 'WallJump', 'y': -236, 'x': -283},
	{'loc': 2999808, 'name': 'EX100', 'zone': 'Grove', 'area': 'DeathGauntlet', 'y': -190, 'x': 303},
	{'loc': -2480280, 'name': 'EX200', 'zone': 'Glades', 'area': 'RightWallJump', 'y': -277, 'x': -245},
	{'loc': -2480208, 'name': 'EX15', 'zone': 'Glades', 'area': 'LeftWallJump', 'y': -207, 'x': -247},
	{'loc': 39804, 'name': 'EX100', 'zone': 'Glades', 'area': 'ChargeFlameOrb', 'y': -196, 'x': 4},
	{'loc': -160096, 'name': 'EX100', 'zone': 'Grove', 'area': 'ChargeFlameTree', 'y': -95, 'x': -14},
	{'loc': 1519708, 'name': 'EX100', 'zone': 'Blackroot', 'area': 'DashArea', 'y': -291, 'x': 154},
	{'loc': 1959768, 'name': 'EX100', 'zone': 'Blackroot', 'area': 'DashArea', 'y': -229, 'x': 197},
	{'loc': 3039696, 'name': 'EX100', 'zone': 'Blackroot', 'area': 'RazielNo', 'y': -303, 'x': 304},
	{'loc': 4319676, 'name': 'EX100', 'zone': 'Blackroot', 'area': 'BoulderExp', 'y': -324, 'x': 432},
	{'loc': 2239640, 'name': 'EX100', 'zone': 'Blackroot', 'area': 'RightGrenadeArea', 'y': -359, 'x': 224},
	{'loc': 3359580, 'name': 'EX100', 'zone': 'Blackroot', 'area': 'RightBlackRoot', 'y': -418, 'x': 339},
	{'loc': 4599508, 'name': 'EX100', 'zone': 'Blackroot', 'area': 'FinalBlackRoot', 'y': -489, 'x': 462},
	{'loc': 3039472, 'name': 'EX100', 'zone': 'Blackroot', 'area': 'FinalBlackRoot', 'y': -525, 'x': 307},
	{'loc': 6159900, 'name': 'EX100', 'zone': 'Swamp', 'area': 'MoonGrotto', 'y': -98, 'x': 618},
	{'loc': 6639952, 'name': 'EX200', 'zone': 'Swamp', 'area': 'RightGinsoOrb', 'y': -48, 'x': 666},
	{'loc': 1839836, 'name': 'EX100', 'zone': 'Grove', 'area': 'GroveWater', 'y': -163, 'x': 187},
	{'loc': -1680104, 'name': 'EX100', 'zone': 'Grove', 'area': 'SpritTreeRefined', 'y': -104, 'x': -168},
	{'loc': 3559792, 'name': 'EX200', 'zone': 'Grotto', 'area': 'DeathStomp', 'y': -207, 'x': 356},
	{'loc': 4759860, 'name': 'EX100', 'zone': 'Grotto', 'area': 'UpperGrottoOrbs', 'y': -140, 'x': 477},
	{'loc': 4319892, 'name': 'EX100', 'zone': 'Grotto', 'area': 'UpperGrottoOrbs', 'y': -108, 'x': 432},
	{'loc': 3639888, 'name': 'EX100', 'zone': 'Grove', 'area': 'UpperGrottoOrbs', 'y': -109, 'x': 365},
	{'loc': 4479832, 'name': 'EX200', 'zone': 'Grotto', 'area': 'UpperGrotto200', 'y': -166, 'x': 449},
	{'loc': 5919864, 'name': 'EX200', 'zone': 'Swamp', 'area': 'SwampGrottoWater', 'y': -136, 'x': 595},
	{'loc': 4199724, 'name': 'EX100', 'zone': 'Grotto', 'area': 'MoonGrottoEnergyWater', 'y': -274, 'x': 423},
	{'loc': 5519856, 'name': 'EX100', 'zone': 'Grotto', 'area': 'MoonGrottoAirOrb', 'y': -141, 'x': 552},
	{'loc': 5719620, 'name': 'EX100', 'zone': 'Grotto', 'area': 'GumoHideout', 'y': -378, 'x': 572},
	{'loc': 4959628, 'name': 'EX15', 'zone': 'Grotto', 'area': 'GumoHideoutPartialMobile', 'y': -369, 'x': 496},
	{'loc': 4639628, 'name': 'EX15', 'zone': 'Grotto', 'area': 'GumoHideoutPartialMobile', 'y': -369, 'x': 467},
	{'loc': 7559600, 'name': 'EX100', 'zone': 'Grotto', 'area': 'MobileDoubleJumpArea', 'y': -398, 'x': 759},
	{'loc': 5639752, 'name': 'EX100', 'zone': 'Grotto', 'area': 'MobileGumoHideout', 'y': -246, 'x': 567},
	{'loc': 4039612, 'name': 'EX100', 'zone': 'Grotto', 'area': 'MobileGumoHideout', 'y': -386, 'x': 406},
	{'loc': 3279644, 'name': 'EX100', 'zone': 'Grotto', 'area': 'MobileGumoHideout', 'y': -353, 'x': 328},
	{'loc': 3959588, 'name': 'EX100', 'zone': 'Grotto', 'area': 'GumoHideoutWater', 'y': -411, 'x': 397},
	{'loc': 5039560, 'name': 'EX200', 'zone': 'Grotto', 'area': 'HideoutRedirect', 'y': -439, 'x': 505},
	{'loc': 5200140, 'name': 'EX100', 'zone': 'Ginso', 'area': 'LowerGinsoTree', 'y': 142, 'x': 523},
	{'loc': 5160336, 'name': 'EX100', 'zone': 'Ginso', 'area': 'UpperGinsoTree', 'y': 339, 'x': 518},
	{'loc': 5160384, 'name': 'EX100', 'zone': 'Ginso', 'area': 'UpperGinsoFloors', 'y': 384, 'x': 517},
	{'loc': 5280404, 'name': 'EX100', 'zone': 'Ginso', 'area': 'UpperGinsoFloors', 'y': 407, 'x': 530},
	{'loc': 4560564, 'name': 'EX100', 'zone': 'Ginso', 'area': 'TopGinsoTree', 'y': 566, 'x': 456},
	{'loc': 4680612, 'name': 'EX100', 'zone': 'Ginso', 'area': 'TopGinsoTree', 'y': 614, 'x': 471},
	{'loc': 6080608, 'name': 'Plant', 'zone': 'Ginso', 'area': 'TopGinsoTreePlant', 'y': 611, 'x': 610},
	{'loc': 5320660, 'name': 'EX200', 'zone': 'Ginso', 'area': 'GinsoEscape', 'y': 661, 'x': 534},
	{'loc': 5360732, 'name': 'EX100', 'zone': 'Ginso', 'area': 'GinsoEscape', 'y': 733, 'x': 537},
	{'loc': 5320824, 'name': 'EX100', 'zone': 'Ginso', 'area': 'GinsoEscape', 'y': 827, 'x': 533},
	{'loc': 5160864, 'name': 'EX100', 'zone': 'Ginso', 'area': 'GinsoEscape', 'y': 867, 'x': 519},
	{'loc': 6359836, 'name': 'EX100', 'zone': 'Swamp', 'area': 'DrainExp', 'y': -162, 'x': 636},
	{'loc': 7599824, 'name': 'EX100', 'zone': 'Swamp', 'area': 'SwampWater', 'y': -173, 'x': 761},
	{'loc': 7679852, 'name': 'EX100', 'zone': 'Swamp', 'area': 'SwampStomp', 'y': -148, 'x': 770},
	{'loc': 9119928, 'name': 'EX200', 'zone': 'Swamp', 'area': 'RightSwampCJump', 'y': -71, 'x': 914},
	{'loc': 8839900, 'name': 'EX100', 'zone': 'Swamp', 'area': 'RightSwampStomp', 'y': -98, 'x': 884},
	{'loc': 8719856, 'name': 'EX200', 'zone': 'Swamp', 'area': 'RightSwampGrenade', 'y': -143, 'x': 874},
	{'loc': 959960, 'name': 'EX200', 'zone': 'Grove', 'area': 'HoruFields', 'y': -37, 'x': 97},
	{'loc': 1920384, 'name': 'EX100', 'zone': 'Horu', 'area': 'Horu', 'y': 384, 'x': 193},
	{'loc': 1880164, 'name': 'EX200', 'zone': 'Horu', 'area': 'HoruStomp', 'y': 165, 'x': 191},
	{'loc': 2520192, 'name': 'EX200', 'zone': 'Horu', 'area': 'HoruStomp', 'y': 194, 'x': 253},
	{'loc': 1600136, 'name': 'EX200', 'zone': 'Horu', 'area': 'HoruStomp', 'y': 136, 'x': 163},
	{'loc': -1919808, 'name': 'EX200', 'zone': 'Horu', 'area': 'HoruStomp', 'y': 194, 'x': -191},
	{'loc': -319852, 'name': 'EX200', 'zone': 'Horu', 'area': 'HoruStomp', 'y': 148, 'x': -29},
	{'loc': 120164, 'name': 'EX200', 'zone': 'Horu', 'area': 'HoruStomp', 'y': 164, 'x': 13},
	{'loc': 1280164, 'name': 'EX200', 'zone': 'Horu', 'area': 'HoruStomp', 'y': 165, 'x': 129},
	{'loc': 960128, 'name': 'EX200', 'zone': 'Horu', 'area': 'HoruStomp', 'y': 130, 'x': 98},
	{'loc': 1040112, 'name': 'EX200', 'zone': 'Horu', 'area': 'DoorWarp', 'y': 112, 'x': 106},
	{'loc': -2240084, 'name': 'EX100', 'zone': 'Valley', 'area': 'ValleyEntryTree', 'y': -84, 'x': -221},
	{'loc': -4199936, 'name': 'EX100', 'zone': 'Valley', 'area': 'ValleyRight', 'y': 67, 'x': -418},
	{'loc': -5479948, 'name': 'EX200', 'zone': 'Sorrow', 'area': 'ValleyMain', 'y': 54, 'x': -546},
	{'loc': -8240012, 'name': 'EX100', 'zone': 'Misty', 'area': 'ValleyMain', 'y': -9, 'x': -822},
	{'loc': -6800032, 'name': 'EX100', 'zone': 'Misty', 'area': 'ValleyMain', 'y': -29, 'x': -678},
	{'loc': -5719844, 'name': 'EX200', 'zone': 'Sorrow', 'area': 'PreSorrowOrb', 'y': 157, 'x': -572},
	{'loc': -3600088, 'name': 'EX100', 'zone': 'Valley', 'area': 'ValleyWater', 'y': -87, 'x': -359},
	{'loc': -5400104, 'name': 'EX100', 'zone': 'Valley', 'area': 'LowerValley', 'y': -104, 'x': -538},
	{'loc': -4600256, 'name': 'EX100', 'zone': 'Valley', 'area': 'OutsideForlornTree', 'y': -255, 'x': -460},
	{'loc': -5160280, 'name': 'EX100', 'zone': 'Valley', 'area': 'OutsideForlornWater', 'y': -277, 'x': -514},
	{'loc': -5400236, 'name': 'EX200', 'zone': 'Valley', 'area': 'OutsideForlornCliff', 'y': -234, 'x': -538},
	{'loc': -7040392, 'name': 'EX200', 'zone': 'Forlorn', 'area': 'Forlorn', 'y': -390, 'x': -703},
	{'loc': -8440352, 'name': 'EX100', 'zone': 'Forlorn', 'area': 'Forlorn', 'y': -350, 'x': -841},
	{'loc': -6799732, 'name': 'EX200', 'zone': 'Sorrow', 'area': 'LeftSorrowGrenade', 'y': 269, 'x': -677},
	{'loc': -5479592, 'name': 'EX100', 'zone': 'Sorrow', 'area': 'UpperSorrow', 'y': 409, 'x': -545},
	{'loc': -9799980, 'name': 'EX100', 'zone': 'Misty', 'area': 'Misty', 'y': 23, 'x': -979},
	{'loc': -10839992, 'name': 'EX100', 'zone': 'Misty', 'area': 'Misty', 'y': 8, 'x': -1082},
	{'loc': -10120036, 'name': 'EX100', 'zone': 'Misty', 'area': 'Misty', 'y': -35, 'x': -1009},
	{'loc': -8400124, 'name': 'EX100', 'zone': 'Misty', 'area': 'MistyPostClimb', 'y': -123, 'x': -837},
	{'loc': -7960144, 'name': 'EX200', 'zone': 'Misty', 'area': 'MistyPostClimb', 'y': -144, 'x': -796},
	{'loc': -6720040, 'name': 'EX200', 'zone': 'Misty', 'area': 'MistyEndGrenade', 'y': -39, 'x': -671},
], "HC": [
	{'loc': -6280316, 'name': 'HC', 'zone': 'Forlorn', 'area': 'RightForlorn', 'y': -315, 'x': -625},
	{'loc': -6119704, 'name': 'HC', 'zone': 'Sorrow', 'area': 'SorrowHealth', 'y': 299, 'x': -609},
	{'loc': -800192, 'name': 'HC', 'zone': 'Glades', 'area': 'WallJump', 'y': -189, 'x': -80},
	{'loc': 5799932, 'name': 'HC', 'zone': 'Swamp', 'area': 'UpperGrottoOrbs', 'y': -67, 'x': 581},
	{'loc': 1479880, 'name': 'HC', 'zone': 'Grove', 'area': 'SpiderSacHealth', 'y': -117, 'x': 151},
	{'loc': 3919688, 'name': 'HC', 'zone': 'Blackroot', 'area': 'BlackrootGrottoConnection', 'y': -309, 'x': 394},
	{'loc': 2599880, 'name': 'HC', 'zone': 'Grove', 'area': 'UpperGroveSpiderArea', 'y': -117, 'x': 261},
	{'loc': 5399808, 'name': 'HC', 'zone': 'Grotto', 'area': 'RightGrottoHealth', 'y': -189, 'x': 543},
	{'loc': 4239780, 'name': 'HC', 'zone': 'Grotto', 'area': 'MoonGrottoEnergyTop', 'y': -220, 'x': 424},
	{'loc': 3919624, 'name': 'HC', 'zone': 'Grotto', 'area': 'MobileGumoHideout', 'y': -375, 'x': 393},
	{'loc': 3199820, 'name': 'HC', 'zone': 'Grove', 'area': 'DeathGauntletRoof', 'y': -179, 'x': 321},
	{'loc': 1599920, 'name': 'HC', 'zone': 'Grove', 'area': 'HoruFieldsStomp', 'y': -78, 'x': 160},
], "EV": [
	{'loc': 0, 'name': 'EVGinsoKey', 'zone': 'Grotto', 'area': 'MobileGumoHideout', 'y': 0, 'x': 0, 'icon': new Leaflet.Icon({iconUrl: '/sprites/WaterVein.png', iconSize: new Leaflet.Point(24,24)}), '_x': 500, '_y': -244},
	{'loc': 4, 'name': 'EVWater', 'zone': 'Ginso', 'area': 'GinsoEscape', 'y': 4, 'x': 0, 'icon': new Leaflet.Icon({iconUrl: '/sprites/CleanWater.png', iconSize: new Leaflet.Point(24,24)}), '_x': 525, '_y': 980},
	{'loc': 12, 'name': 'EVWind', 'zone': 'Forlorn', 'area': 'RightForlorn', 'y': 12, 'x': 0, 'icon': new Leaflet.Icon({iconUrl: '/sprites/WindRestored.png', iconSize: new Leaflet.Point(24,24)}), '_x': -735, '_y': -225},
	{'loc': 8, 'name': 'EVForlornKey', 'zone': 'Misty', 'area': 'MistyEnd', 'y': 8, 'x': 0, 'icon': new Leaflet.Icon({iconUrl: '/sprites/GumonSeal.png', iconSize: new Leaflet.Point(24,24)}), '_x': -720, '_y': -20},
	{'loc': 16, 'name': 'EVHoruKey', 'zone': 'Sorrow', 'area': 'Sunstone', 'y': 16, 'x': 0, 'icon': new Leaflet.Icon({iconUrl: '/sprites/Sunstone.png', iconSize: new Leaflet.Point(24,24)}), '_x':-560, '_y':  607},
	{'loc': 20, 'name': 'EVWarmth', 'zone': 'Horu', 'area': 'End', 'y': 20, 'x': 0, 'icon': new Leaflet.Icon({iconUrl: '/sprites/WarmthReturned.png', iconSize: new Leaflet.Point(24,24)}), '_x': -220, '_y': 504},
], "Pl": [
	{'loc': 1240020, 'name': 'Plant', 'zone': 'Grove', 'area': 'HoruFieldsEnergyPlant', 'y': 21, 'x': 124},
	{'loc': 4439632, 'name': 'Plant', 'zone': 'Grotto', 'area': 'MobileGumoHideoutPlants', 'y': -368, 'x': 447},
	{'loc': 4359656, 'name': 'Plant', 'zone': 'Grotto', 'area': 'MobileGumoHideoutPlants', 'y': -344, 'x': 439},
	{'loc': 4919600, 'name': 'Plant', 'zone': 'Grotto', 'area': 'MobileGumoHideoutPlants', 'y': -400, 'x': 492},
	{'loc': 3119768, 'name': 'Plant', 'zone': 'Blackroot', 'area': 'DashAreaPlant', 'y': -232, 'x': 313},
	{'loc': 3639880, 'name': 'Plant', 'zone': 'Grove', 'area': 'HollowGrovePlants', 'y': -119, 'x': 365},
	{'loc': 3279920, 'name': 'Plant', 'zone': 'Grove', 'area': 'HollowGrovePlants', 'y': -78, 'x': 330},
	{'loc': 6279880, 'name': 'Plant', 'zone': 'Swamp', 'area': 'SwampPlant', 'y': -120, 'x': 628},
	{'loc': 4319860, 'name': 'Plant', 'zone': 'Grotto', 'area': 'MoonGrottoStompPlant', 'y': -140, 'x': 435},
	{'loc': 5119900, 'name': 'Plant', 'zone': 'Swamp', 'area': 'SwampMortarPlant', 'y': -100, 'x': 515},
	{'loc': 5399780, 'name': 'Plant', 'zone': 'Grotto', 'area': 'UpperGrottoOrbsPlant', 'y': -220, 'x': 540},
	{'loc': 5359824, 'name': 'Plant', 'zone': 'Grotto', 'area': 'MoonGrottoAirOrbPlant', 'y': -176, 'x': 537},
	{'loc': 3399820, 'name': 'Plant', 'zone': 'Grove', 'area': 'DeathGauntletRoofPlant', 'y': -179, 'x': 342},
	{'loc': 5400100, 'name': 'Plant', 'zone': 'Ginso', 'area': 'LowerGinsoTreePlant', 'y': 101, 'x': 540},
	{'loc': -11040068, 'name': 'Plant', 'zone': 'Misty', 'area': 'MistyPlant', 'y': -67, 'x': -1102},
	{'loc': -6319752, 'name': 'Plant', 'zone': 'Sorrow', 'area': 'LeftSorrowPlant', 'y': 249, 'x': -630},
	{'loc': -8160268, 'name': 'Plant', 'zone': 'Forlorn', 'area': 'ForlornPlant', 'y': -266, 'x': -815},
	{'loc': -4799416, 'name': 'Plant', 'zone': 'Sorrow', 'area': 'SunstonePlant', 'y': 586, 'x': -478},
	{'loc': 3160244, 'name': 'Plant', 'zone': 'Horu', 'area': 'HoruStompPlant', 'y': 245, 'x': 318},
	{'loc': -1800088, 'name': 'Plant', 'zone': 'Valley', 'area': 'ValleyEntryTreePlant', 'y': -88, 'x': -179},
	{'loc': -4680068, 'name': 'Plant', 'zone': 'Valley', 'area': 'ValleyMainPlant', 'y': -67, 'x': -468},
	{'loc': 399844, 'name': 'Plant', 'zone': 'Grove', 'area': 'ChargeFlamePlant', 'y': -156, 'x': 43},
	{'loc': -12320248, 'name': 'Plant', 'zone': 'Forlorn', 'area': 'RightForlornPlant', 'y': -248, 'x': -1232},
	{'loc': -6080316, 'name': 'Plant', 'zone': 'Forlorn', 'area': 'RightForlornPlant', 'y': -314, 'x': -607},
], "KS": [
	{'loc': -8600356, 'name': 'KS', 'zone': 'Forlorn', 'area': 'Forlorn', 'y': -353, 'x': -858},
	{'loc': -8920328, 'name': 'KS', 'zone': 'Forlorn', 'area': 'Forlorn', 'y': -328, 'x': -892},
	{'loc': -8880252, 'name': 'KS', 'zone': 'Forlorn', 'area': 'Forlorn', 'y': -251, 'x': -888},
	{'loc': -8720256, 'name': 'KS', 'zone': 'Forlorn', 'area': 'Forlorn', 'y': -255, 'x': -869},
	{'loc': -4879680, 'name': 'KS', 'zone': 'Sorrow', 'area': 'Sorrow', 'y': 323, 'x': -485},
	{'loc': -5039728, 'name': 'KS', 'zone': 'Sorrow', 'area': 'Sorrow', 'y': 274, 'x': -503},
	{'loc': -5159700, 'name': 'KS', 'zone': 'Sorrow', 'area': 'Sorrow', 'y': 303, 'x': -514},
	{'loc': -5959772, 'name': 'KS', 'zone': 'Sorrow', 'area': 'Sorrow', 'y': 229, 'x': -596},
	{'loc': -6079672, 'name': 'KS', 'zone': 'Sorrow', 'area': 'LeftSorrow', 'y': 329, 'x': -608},
	{'loc': -6119656, 'name': 'KS', 'zone': 'Sorrow', 'area': 'LeftSorrow', 'y': 347, 'x': -612},
	{'loc': -6039640, 'name': 'KS', 'zone': 'Sorrow', 'area': 'LeftSorrow', 'y': 361, 'x': -604},
	{'loc': -6159632, 'name': 'KS', 'zone': 'Sorrow', 'area': 'LeftSorrow', 'y': 371, 'x': -613},
	{'loc': -4559584, 'name': 'KS', 'zone': 'Sorrow', 'area': 'UpperSorrow', 'y': 419, 'x': -456},
	{'loc': -4159572, 'name': 'KS', 'zone': 'Sorrow', 'area': 'UpperSorrow', 'y': 429, 'x': -414},
	{'loc': -5159576, 'name': 'KS', 'zone': 'Sorrow', 'area': 'UpperSorrow', 'y': 427, 'x': -514},
	{'loc': -5919556, 'name': 'KS', 'zone': 'Sorrow', 'area': 'UpperSorrow', 'y': 445, 'x': -592},
	{'loc': -10759968, 'name': 'KS', 'zone': 'Misty', 'area': 'Misty', 'y': 32, 'x': -1076},
	{'loc': -10440008, 'name': 'KS', 'zone': 'Misty', 'area': 'Misty', 'y': 8, 'x': -1044},
	{'loc': -9120036, 'name': 'KS', 'zone': 'Misty', 'area': 'MistyPostClimb', 'y': -36, 'x': -912},
	{'loc': -7680144, 'name': 'KS', 'zone': 'Misty', 'area': 'MistyPostClimb', 'y': -144, 'x': -768},
	{'loc': 799776, 'name': 'KS', 'zone': 'Glades', 'area': 'SunkenGladesRunaway', 'y': -222, 'x': 83},
	{'loc': -120208, 'name': 'KS', 'zone': 'Glades', 'area': 'SunkenGladesRunaway', 'y': -206, 'x': -11},
	{'loc': -600244, 'name': 'KS', 'zone': 'Glades', 'area': 'WallJump', 'y': -244, 'x': -59},
	{'loc': -2400212, 'name': 'KS', 'zone': 'Glades', 'area': 'LeftWallJump', 'y': -212, 'x': -238},
	{'loc': -1840196, 'name': 'KS', 'zone': 'Glades', 'area': 'SpiritCaverns', 'y': -193, 'x': -182},
	{'loc': -2200184, 'name': 'KS', 'zone': 'Glades', 'area': 'SpiritCaverns', 'y': -183, 'x': -217},
	{'loc': -1800156, 'name': 'KS', 'zone': 'Glades', 'area': 'SpiritCaverns', 'y': -154, 'x': -177},
	{'loc': -2200148, 'name': 'KS', 'zone': 'Glades', 'area': 'SpiritCavernsTopLeft', 'y': -146, 'x': -217},
	{'loc': 6199596, 'name': 'KS', 'zone': 'Grotto', 'area': 'GumoHideout', 'y': -404, 'x': 620},
	{'loc': 5879616, 'name': 'KS', 'zone': 'Grotto', 'area': 'GumoHideout', 'y': -384, 'x': 590},
	{'loc': 5280264, 'name': 'KS', 'zone': 'Ginso', 'area': 'LowerGinsoTree', 'y': 267, 'x': 531},
	{'loc': 5400276, 'name': 'KS', 'zone': 'Ginso', 'area': 'LowerGinsoTree', 'y': 277, 'x': 540},
	{'loc': 5080304, 'name': 'KS', 'zone': 'Ginso', 'area': 'LowerGinsoTree', 'y': 304, 'x': 508},
	{'loc': 5280296, 'name': 'KS', 'zone': 'Ginso', 'area': 'LowerGinsoTree', 'y': 297, 'x': 529},
	{'loc': 5040476, 'name': 'KS', 'zone': 'Ginso', 'area': 'UpperGinsoTree', 'y': 476, 'x': 507},
	{'loc': 5320488, 'name': 'KS', 'zone': 'Ginso', 'area': 'UpperGinsoTree', 'y': 488, 'x': 535},
	{'loc': 5280500, 'name': 'KS', 'zone': 'Ginso', 'area': 'UpperGinsoTree', 'y': 502, 'x': 531},
	{'loc': 5080496, 'name': 'KS', 'zone': 'Ginso', 'area': 'UpperGinsoTree', 'y': 498, 'x': 508},
	{'loc': 6839792, 'name': 'KS', 'zone': 'Swamp', 'area': 'SwampWater', 'y': -205, 'x': 684},
	{'loc': 7639816, 'name': 'KS', 'zone': 'Swamp', 'area': 'SwampWater', 'y': -183, 'x': 766},
], "SK": [
	{'loc': -4600020, 'name': 'SKGlide', 'zone': 'Valley', 'area': 'ValleyMain', 'y': -20, 'x': -460},
	{'loc': -6959592, 'name': 'SKChargeJump', 'zone': 'Sorrow', 'area': 'ChargeJump', 'y': 408, 'x': -696},
	{'loc': -3160308, 'name': 'SKWallJump', 'zone': 'Glades', 'area': 'WallJump', 'y': -308, 'x': -316},
	{'loc': -560160, 'name': 'SKChargeFlame', 'zone': 'Grove', 'area': 'ChargeFlame', 'y': -160, 'x': -56},
	{'loc': 2919744, 'name': 'SKDash', 'zone': 'Blackroot', 'area': 'DashArea', 'y': -256, 'x': 292},
	{'loc': 719620, 'name': 'SKGrenade', 'zone': 'Blackroot', 'area': 'GrenadeArea', 'y': -380, 'x': 72},
	{'loc': 7839588, 'name': 'SKDoubleJump', 'zone': 'Grotto', 'area': 'DoubleJumpArea', 'y': -412, 'x': 784},
	{'loc': 5320328, 'name': 'SKBash', 'zone': 'Ginso', 'area': 'BashTree', 'y': 328, 'x': 532},
	{'loc': 8599904, 'name': 'SKStomp', 'zone': 'Swamp', 'area': 'RightSwamp', 'y': -96, 'x': 860},
	{'loc': -11880100, 'name': 'SKClimb', 'zone': 'Misty', 'area': 'Misty', 'y': -100, 'x': -1188},
], "MP": [
	{'loc': 24, 'name': 'Mapstone 1', 'zone': 'Mapstone', 'area': 'MS1', 'x': 0, 'y': 1},
	{'loc': 28, 'name': 'Mapstone 2', 'zone': 'Mapstone', 'area': 'MS2', 'x': 0, 'y': 2},
	{'loc': 32, 'name': 'Mapstone 3', 'zone': 'Mapstone', 'area': 'MS3', 'x': 0, 'y': 3},
	{'loc': 36, 'name': 'Mapstone 4', 'zone': 'Mapstone', 'area': 'MS4', 'x': 0, 'y': 4},
	{'loc': 40, 'name': 'Mapstone 5', 'zone': 'Mapstone', 'area': 'MS5', 'x': 0, 'y': 5},
	{'loc': 44, 'name': 'Mapstone 6', 'zone': 'Mapstone', 'area': 'MS6', 'x': 0, 'y': 6},
	{'loc': 48, 'name': 'Mapstone 7', 'zone': 'Mapstone', 'area': 'MS7', 'x': 0, 'y': 7},
	{'loc': 52, 'name': 'Mapstone 8', 'zone': 'Mapstone', 'area': 'MS8', 'x': 0, 'y': 8},
	{'loc': 56, 'name': 'Mapstone 9', 'zone': 'Mapstone', 'area': 'MS9', 'x': 0, 'y': 9},
], "MS": [
	{'loc': 1480360, 'name': 'MS', 'zone': 'Horu', 'area': 'Horu', 'y': 363, 'x': 148},
	{'loc': -5640092, 'name': 'MS', 'zone': 'Valley', 'area': 'LowerValley', 'y': -89, 'x': -561},
	{'loc': -4440152, 'name': 'MS', 'zone': 'Valley', 'area': 'OutsideForlornMS', 'y': -152, 'x': -443},
	{'loc': -4359680, 'name': 'MS', 'zone': 'Sorrow', 'area': 'SorrowMapFragment', 'y': 322, 'x': -435},
	{'loc': 3439744, 'name': 'MS', 'zone': 'Blackroot', 'area': 'BlackrootMap', 'y': -255, 'x': 346},
	{'loc': -1840228, 'name': 'MS', 'zone': 'Glades', 'area': 'LeftWallJump', 'y': -227, 'x': -184},
	{'loc': 2999904, 'name': 'MS', 'zone': 'Grove', 'area': 'HollowGrove', 'y': -94, 'x': 300},
	{'loc': 5119584, 'name': 'MS', 'zone': 'Grotto', 'area': 'GumoHideout', 'y': -413, 'x': 513},
	{'loc': 7959788, 'name': 'MS', 'zone': 'Swamp', 'area': 'SwampWater', 'y': -210, 'x': 796},
]};
const stuff_types = [{value: "Skills", label: "Skills"}, {value: "Events", label: "Events"}, {value: "Upgrades", label: "Upgrades"}, {value: "Teleporters", label: "Teleporters"}, {value: "Experience", label: "Experience"}, 
					 {value: "Cells and Stones", label: "Cells and Stones"}, {value: "Messages", label: "Messages"}, {value: "Custom", label: "Custom"}, {value: "Fill", label: "Fill"}];
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
			return "Cells and Stones"
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
		{label: "Polarity Shift", value: "RB|101"},
		{label: "Gravity Swap", value: "RB|102"},
		{label: "ExtremeSpeed", value: "RB|103"},
		{label: "Energy Jump", value: "RB|104"},
	],
	"Teleporters": [
		{label: "Grotto TP", value: "TP|Grotto"},
		{label: "Grove TP", value: "TP|Grove"},
		{label: "Forlorn TP", value: "TP|Forlorn"},
		{label: "Valley TP", value: "TP|Valley"},
		{label: "Sorrow TP", value: "TP|Sorrow"},
		{label: "Swamp TP", value: "TP|Swamp"}
	],
	"Cells and Stones": [
		{label: "Health Cell", value: "HC|1"},
		{label: "Energy Cell", value: "EC|1"},
		{label: "Ability Cell", value: "AC|1"},
		{label: "Keystone", value: "KS|1"},
		{label: "Mapstone", value: "MS|1"}
	]
};
const presets = {
        "casual": ["normal", "dboost-light"],
        "standard": ["normal", "speed", "lure", "dboost-light"],
        "dboost": ["normal", "speed", "lure", "dboost", "dboost-light"],
        "expert": ["normal", "speed", "lure", "speed-lure", "dboost", "dboost-light", "cdash", "extended", "extended-damage"],
        "master": ["normal", "speed", "lure", "speed-lure", "dboost", "dboost-light", "dboost-hard", "cdash", "dbash", "extended", "extended-damage", "lure-hard", "extreme"],
        "hard": ["normal", "speed", "lure",  "dboost-light", "cdash", "dbash", "extended"],
        "ohko": ["normal", "speed", "lure", "cdash", "dbash", "extended"],
        "0xp": ["normal", "speed", "lure", "dboost-light"],
        "glitched": ["normal", "speed", "lure", "speed-lure", "dboost", "dboost-light", "dboost-hard", "cdash", "dbash", "extended", "lure-hard", "timed-level", "glitched", "extended-damage", "extreme"]
    };

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

function get_param(name) {
	let retVal = document.getElementsByClassName(name)[0].id
	return (retVal !== "" && retVal !== "None") ? retVal : null
}

function get_flag(name) {
	return get_param(name) !== null
}

function get_int(name, orElse) {
	return parseInt(get_param(name), 10) || orElse
}

function get_list(name, sep) {
	let raw = get_param(name)
	if(raw)
		return raw.split(sep)
	else
		return []
}


function get_seed() {
    let authed = get_flag("authed")
    if(authed)
    {
    	let user = get_param("user")
    	let name = get_param("seed_name") || "new seed"
    	let desc = get_param("seed_desc") || ""
    	let hidden = get_flag("seed_hidden") 
    	let rawSeed = get_param("seed_data")
	    return {rawSeed: rawSeed, user: user, authed: authed, seed_name: name, seed_desc: desc, hidden: hidden}
    }
    else
    	return {authed:false}
    
}


function is_match(pickup, searchstr) {
	searchstr = searchstr.toLowerCase();
	return pickup.label.toLowerCase().includes(searchstr) || pickup.value.toLowerCase().includes(searchstr);
} 
 
const str_ids = ["TP", "NO", "SH"];
const hide_opacity = .2;
const seed_name_regex = new RegExp("^[^ ?=/]+$");
export {PickupMarker, PickupMarkersList, download, pickup_icons, getStuffType, locs, picks_by_loc, getMapCrs, pickups, distance,
		point, picks_by_type, picks_by_zone, zones, pickup_name, stuff_types, stuff_by_type, areas, picks_by_area, presets,
		get_param, get_flag, get_int, get_list, get_seed, is_match, str_ids, hide_opacity, seed_name_regex };
