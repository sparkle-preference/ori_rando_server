import React from 'react';
import {get_param, get_int, get_seed, seed_name_regex } from './shared_map.js';
import { confirmAlert } from 'react-confirm-alert'; 
import 'react-confirm-alert/src/react-confirm-alert.css' 
import {DropdownToggle, DropdownMenu, DropdownItem, ButtonDropdown, Button, Container, Row, Col, Input, Badge} from 'reactstrap';
import {Helmet} from 'react-helmet';

const goToCurry = (url) => () => { window.location.href = url } 
const textStyle = {color: "black", textAlign: "center"}
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
    			  players: players, seed_desc: seed_desc, gid: gid, rename_to: seed_name, hidden: hidden || false, dropdownOpen: false};
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
		let download_button;
		let url = "/plando/"+this.state.author+"/"+this.state.seed_name;
		if(this.state.players === 1)
			download_button = (<Button color="primary" onClick={goToCurry(url + "/download?gid="+this.state.gid+"&pid=1")}>Download Seed</Button>)
		else
		{
			let players = []
		    for (let i = 1; i <= this.state.players; i++) {
		    	let purl = url + "/download?gid="+this.state.gid+"&pid="+i;
		    	players.push((<DropdownItem onClick={goToCurry(purl)}>Player {i}</DropdownItem>))
	    	}
	    	download_button=(
				<ButtonDropdown color="primary" isOpen={this.state.dropdownOpen} toggle={() => this.setState({dropdownOpen: !this.state.dropdownOpen})}>
					<DropdownToggle caret>
					  Download Seed (Select Player)
					</DropdownToggle>
					<DropdownMenu>
						{players}
	    		    </DropdownMenu>
	      		</ButtonDropdown>
      		)	    		
			
		}
    	let rename_enabled = (this.state.rename_to !== this.state.seed_name) && (seed_name_regex.test(this.state.rename_to))
    	let color = rename_enabled ? "primary" : "disabled"
    	let rename_copy = (
			<Row className="p-3 border border-danger border-bottom-0 justify-content-center">
				<Col xs="4">
					<Button color={color} block onClick={rename_enabled ? goToCurry(url + "/rename/" + this.state.rename_to) : () => { alert("Please enter a new name")}}>Rename</Button>
				</Col><Col xs="4">
		 			<Button color={color} block onClick={rename_enabled ? goToCurry(url + "/rename/" + this.state.rename_to + "?cp=1") : () => { alert("Please enter a new name")}}>Copy</Button>
				</Col><Col xs="4">
					<Input type="text" value={this.state.rename_to} onChange={event => this.setState({rename_to: event.target.value})} />
				</Col>
			</Row>
    	) 
    	let hide_button = this.state.hidden ? (
    		<Button color="success" block onClick={goToCurry(url + "/hideToggle")} >Show Seed</Button>
    	) : (
    		<Button color="info" block onClick={goToCurry(url + "/hideToggle" )} >Hide Seed</Button>
    	)
		let owner_box = this.state.isOwner ? [rename_copy, (
			<Row className="p-3 border border-danger border-top-0 justify-content-center">
				<Col xs="4">
					<Button block color="danger" onClick={() => this.conf_delete()} >Delete</Button>
				</Col><Col xs="4">
					<Button block color="primary" onClick={goToCurry(url + "/edit")} >Edit</Button>
				</Col><Col xs="4">
					{hide_button}
				</Col>
			</Row>
			)] : null
		let summary = this.state.seed_desc ? (
			<Row className="p-3 border">
				<Col xs="2" className="text-right">
					<span style={textStyle}>Summary: </span>
				</Col><Col xs="10">
					<span style={textStyle}>{this.state.seed_desc}</span>
				</Col>
			</Row>
		) : null
		return (
			<Container className="pl-4 pr-4 pb-4 pt-2 mt-5 w-50 border border-dark">
            <Helmet>
                <style>{'body { background-color: white}'}</style>
            </Helmet>
				<Row className="p-1">
					<Col>
						<span><h3 style={textStyle}>{this.state.seed_name} <Badge outline href={"/plando/"+this.state.author} color="dark">by {this.state.author}</Badge> {(this.state.hidden ? " (Hidden)" : "")}</h3></span>
					</Col>
				</Row>
				<Row className="p-3 border">
					<Col xs="2" className="text-right">
						<span style={textStyle}>Flags: </span>
					</Col><Col xs="10">
						<span style={textStyle}>{this.state.rawSeed}</span>
					</Col>
				</Row>
				{summary}
				<Row className="p-3 justify-content-center">
					<Col xs="auto">
						{download_button}
					</Col>
				</Row>
			{owner_box}
			</Container>
	)

	}
};

