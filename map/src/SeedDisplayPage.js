import './bootstrap.cyborg.min.css';
import './index.css';
import React from 'react';
import {get_param, get_int, get_seed, seed_name_regex } from './shared_map.js';
import 'react-select/dist/react-select.css';
import { confirmAlert } from 'react-confirm-alert'; // Import
import 'react-confirm-alert/src/react-confirm-alert.css' // Import css
import {Button} from 'reactstrap';


export default class SeedDisplayPage extends React.Component {
  constructor(props) {
    super(props);
    let {rawSeed, user, authed, seed_name, hidden, seed_desc} = get_seed();
    let author = get_param("author")
    let gid = get_param("game-id")
    let complain_message = get_param("error_msg")
	if(complain_message)
		alert(complain_message);
    let players = get_int("players",1)
    let isOwner =  author === user;
    this.state = {rawSeed: rawSeed, user: user, author: author, isOwner: isOwner, authed: authed, seed_name: seed_name,
    			  players: players, seed_desc: seed_desc, gid: gid, rename_to: seed_name, hidden: hidden || false};
}
  conf_delete = () => {
    confirmAlert({
      title: 'Confirm Delete?',
      message: 'Your seed will be lost!',
      buttons: [
        {
          label: 'Yes, it is time :C',
          onClick: () => { window.location.href = "/plando/"+this.state.author+"/"+this.state.seed_name + "/delete"; }
        },
        {
          label: 'No wait! I still love you!',
          onClick: () => { return; }
        }
      ]
    })
  };

	
	render = () => {
		let download_links = []
		let url = "/plando/"+this.state.author+"/"+this.state.seed_name;
	    for (let i = 1; i <= this.state.players; i++) {
	    	let purl = url + "/download?gid="+this.state.gid+"&pid="+i;
	    	download_links.push((<div><a href={purl}>Player {i}</a></div>))
    	}
    	let rename_copy = ((this.state.rename_to !== this.state.seed_name) && (seed_name_regex.test(this.state.rename_to))) ? (
			<div>
				<Button color="primary" onClick={() => { window.location.href = url + "/rename/" + this.state.rename_to }} >Rename</Button>
	 			<Button color="primary" onClick={() => { window.location.href = url + "/rename/" + this.state.rename_to + "?cp=1"}} >Copy</Button>
				<input type="text" value={this.state.rename_to} onChange={event => this.setState({rename_to: event.target.value})} />
			</div>
    	) : (
			<div>
				<Button color="disabled" onClick={() => { alert("Please enter a new name"); }} >Rename</Button>
	 			<Button color="disabled" onClick={() => { alert("Please enter a new name"); }} >Copy</Button>
				<input type="text" value={this.state.rename_to} onChange={event => this.setState({rename_to: event.target.value})} />
			</div>
    	)
    	let hide_button = this.state.hidden ? (
    		<Button color="success" onClick={() => { window.location.href = url + "/hideToggle" }} >Show Seed</Button>
    	) : (
    		<Button color="info" onClick={() => { window.location.href = url + "/hideToggle" }} >Hide Seed</Button>
    	)
		let owner_box = this.state.isOwner ? (
		<div>
				{rename_copy}
			<div>
				<Button color="danger" onClick={() => this.conf_delete()} >Delete</Button>
				<Button color="primary" onClick={() => { window.location.href = url + "/edit"}} >Edit</Button>
				{hide_button}
			</div>
		</div>	
			) : null

		return (
		<div>
		<h4>{this.state.seed_name} (by {this.state.author + (this.state.hidden ? " (Hidden)" : "")})</h4>
		<div>Flags: {this.state.rawSeed}</div>
		<div>Summary: {this.state.seed_desc}</div>
		{download_links}
		{owner_box}
		</div>
	)

	}
};

