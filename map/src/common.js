import Leaflet from 'leaflet';

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

const presets = {
    casual: ['casual-core', 'casual-dboost'],
    standard: [
        'casual-core', 'casual-dboost', 
        'standard-core', 'standard-dboost', 'standard-lure', 'standard-abilities'
        ],
    expert: [
        'casual-core', 'casual-dboost', 
        'standard-core', 'standard-dboost', 'standard-lure', 'standard-abilities',
        'expert-core', 'expert-dboost', 'expert-lure', 'expert-abilities', 'dbash'
        ],
    master: [
        'casual-core', 'casual-dboost', 
        'standard-core', 'standard-dboost', 'standard-lure', 'standard-abilities',
        'expert-core', 'expert-dboost', 'expert-lure', 'expert-abilities', 'dbash',
        'master-core', 'master-dboost', 'master-lure', 'master-abilities', 'gjump'
        ],
    glitched: [
        'casual-core', 'casual-dboost', 
        'standard-core', 'standard-dboost', 'standard-lure', 'standard-abilities',
        'expert-core', 'expert-dboost', 'expert-lure', 'expert-abilities', 'dbash',
        'master-core', 'master-dboost', 'master-lure', 'master-abilities', 'gjump',
        'glitched', 'timed-level'
        ]
};

const logic_paths = presets['glitched'].concat('insane');
const get_preset = (paths) => {
    for (let preset of Object.keys(presets)) {
        let p = presets[preset];
        if(paths.length === p.length && paths.every(path => p.includes(path)))
            return preset;
    }
    return "custom"
}

function player_icons(id, as_leaflet=true)  {
	id = parseInt(id, 10);
	let img = 	'/sprites/ori-white.png';
	if (id === 1)  img = '/sprites/ori-blue.png';
	else if (id === 2)  img = '/sprites/ori-red.png';
	else if (id === 3)  img = '/sprites/ori-green.png';
	else if (id === 4)  img = '/sprites/ori-cyan.png';
	else if (id === 5)  img = '/sprites/ori-yellow.png';
	else if (id === 6)  img = '/sprites/ori-magenta.png';
	else if (id === 7)  img = '/sprites/ori-multi-1.png';
	else if (id === 8)  img = '/sprites/ori-multi-2.png';
	else if (id === 9)  img = '/sprites/ori-multi-3.png';
	else if (id === 10) img = '/sprites/ori-skul.png';

	if(!as_leaflet) return img;

	let ico = new Leaflet.Icon({iconUrl: img, iconSize: new Leaflet.Point(48, 48)});
	return ico
};

function doNetRequest(url, onRes)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState === 4) {
        	 onRes(xmlHttp);
        }
	}
    xmlHttp.open("GET", url, true); // true for asynchronous
    xmlHttp.send(null);
}

export {player_icons, doNetRequest, get_param, get_flag, get_int, get_list, get_preset, presets, get_seed, logic_paths};