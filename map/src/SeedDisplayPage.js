import React from 'react';
//import {Radio, RadioGroup} from 'react-radio-group';
//import registerServiceWorker from './registerServiceWorker';
import { Map, Tooltip, TileLayer} from 'react-leaflet';
import Leaflet from 'leaflet';
import {Checkbox, CheckboxGroup} from 'react-checkbox-group';
import {download, getStuffType, stuff_types, stuff_by_type, picks_by_type, picks_by_loc, picks_by_zone, presets,
		picks_by_area, zones,  pickup_name, PickupMarkersList, pickup_icons, getMapCrs, 
		get_param, get_flag, get_int, get_list, get_seed} from './shared_map.js';
import NumericInput from 'react-numeric-input';
import Select from 'react-select';
import 'react-select/dist/react-select.css';
import {Alert, Button, ButtonGroup, Collapse} from 'reactstrap';


export default class SeedDisplayPage extends React.Component {
  constructor(props) {
    super(props);
    let {rawSeed, user, authed, seed_name, seed_desc} = get_seed();
    let author = get_param("author")
    let gid = get_param("game-id")
    let players = get_int("players",1)
    let isOwner =  author === user;
    this.state = {rawSeed: rawSeed, user: user, author: author, isOwner: isOwner, authed: authed, seed_name: seed_name, players: players, seed_desc: seed_desc, gid: gid};
	}
	
	render = () => {
		let download_links = []
	    for (let i = 1; i <= this.state.players; i++) {
	    	let url="/"+this.state.author+"/"+this.state.seed_name + "/download?gid="+this.state.gid+"&pid="+i 
	    	download_links.push((<div>Player {i}: <a href={url}>{url}</a></div>))
    	}

		return (
		<div>
		<h4>{this.state.seed_name} (by {this.state.author})</h4>
		<div>Flags: {this.state.rawSeed}</div>
		<div>Summary: {this.state.seed_desc}</div>
		{download_links}
		</div>
	)

	}
};

