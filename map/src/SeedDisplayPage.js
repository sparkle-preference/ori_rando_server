import React from 'react';
import he from 'he';
import {get_param, get_int, get_seed} from './common.js';
import {goToCurry, seed_name_regex } from './shared_map.js';
import { confirmAlert } from 'react-confirm-alert'; 
import 'react-confirm-alert/src/react-confirm-alert.css' 
import {Button, Container, Row, Col, Input, Badge} from 'reactstrap';
import SiteBar from "./SiteBar.js"

const textStyle = {textAlign: "center"}
export default class SeedDisplayPage extends React.Component {
  constructor(props) {
    super(props);
    let {seedJson, authed, seed_name, hidden, seed_desc} = get_seed();
    let seedData = JSON.parse(he.decode(seedJson))
    let author = get_param("author")
    let gid = get_param("game-id")
    let complain_message = get_param("error_msg")
    
	if(complain_message)
		alert(complain_message);
    let players = get_int("players", 1)
    this.state = {flags: seedData["flagline"].split("|")[0].split(","), author: author, authed: authed, seed_name: seed_name, tracking: true,
    			  players: players, seed_desc: seed_desc, gid: gid, rename_to: seed_name, hidden: hidden || false, dropdownOpen: false};
}
  conf_delete = () => {
    confirmAlert({
      title: 'Confirm Delete?',
      message: 'Your seed will be lost!',
      buttons: [
        {
          label: 'Yes, it is time :C',
          onClick: () => { window.location.href = `/plando/${this.state.seed_name}/delete`; }
        },
        {
          label: 'No wait! I still love you!',
          onClick: () => { return; }
        }
      ]
    })
  };

	render = () => {
		let url = `/plando/${this.state.seed_name}`;
    	let rename_enabled = (this.state.rename_to !== this.state.seed_name) && (seed_name_regex.test(this.state.rename_to))
    	let rename_copy = (
			<Row key="rename/copy" className="p-3 border border-danger border-bottom-0 justify-content-center">
				<Col xs="4">
					<Button color="primary" block disabled={!rename_enabled} onClick={rename_enabled ? goToCurry(`${url}/rename/${this.state.rename_to}`) : () => { alert("Please enter a new name")}}>Rename</Button>
				</Col><Col xs="4">
		 			<Button color="primary" block disabled={!rename_enabled} onClick={rename_enabled ? goToCurry(`${url}/rename/${this.state.rename_to}?cp=1`) : () => { alert("Please enter a new name")}}>Copy</Button>
				</Col><Col xs="4">
					<Input type="text" value={this.state.rename_to} onChange={event => this.setState({rename_to: event.target.value})} />
				</Col>
			</Row>
    	) 
    	let hide_button = this.state.hidden ? (
    		<Button color="success" block href={`${url}/hideToggle`} >Show Seed</Button>
    	) : (
    		<Button color="info" block href={`${url}/hideToggle`} >Hide Seed</Button>
    	)
		let owner_box = this.state.authed ? [
            rename_copy, 
            (
                <Row key="spoiler/desc"  className="p-3 border border-danger border-top-0 border-bottom-0 justify-content-center">
				<Col xs="4">
					<Button block onClick={this.updateDesc}>Update</Button>
				</Col>
                <Col xs="8">
					<Input type="textarea" value={this.state.seed_desc} onChange={e => this.setState({seed_desc: e.target.value})}/>
				</Col>
                </Row>

            ),
            (
			<Row key="delete/edit/hide" className="p-3 border border-danger border-top-0 justify-content-center">
				<Col xs="4">
					<Button block color="danger" onClick={() => this.conf_delete()} >Delete</Button>
				</Col><Col xs="4">
					<Button block color="primary" onClick={goToCurry(`${url}/edit`)} >Edit</Button>
				</Col><Col xs="4">
					{hide_button}
				</Col>
			</Row>
			), 
            ] : null
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
			<Container className="pl-4 pr-4 pb-4 pt-2 mt-5 w-75 border border-dark">
                <SiteBar/>
				<Row className="p-1">
					<Col>
						<span><h3 style={textStyle}>{this.state.seed_name} <Badge outline href={"/plando/"+this.state.author} color="dark">by {this.state.author}</Badge> {(this.state.hidden ? " (Hidden)" : "")}</h3></span>
					</Col>
				</Row>
				<Row className="p-3 border">
					<Col xs="2" className="text-right">
						<span style={textStyle}>Flags: </span>
					</Col><Col xs="10">
						<span style={textStyle}>{this.state.flags.join(", ")}</span>
					</Col>
				</Row>
				{summary}
				<Row className="p-3 justify-content-center">
					<Col xs={{size: 3, offset: 3}}>
                        <Button block color="primary" href={`/plando/${this.state.author}/${this.state.seed_name}/download${this.state.tracking ? "?tracking=1" : ""}`}>Start Seed</Button>
					</Col>
                    <Col xs="3">
                        <Button color="info" block outline={!this.state.tracking} onClick={()=>this.setState({tracking: !this.state.tracking})}>Web Tracking {this.state.tracking ? "Enabled" : "Disabled"}</Button>
                    </Col>
				</Row>
			{owner_box}
			</Container>
	)

	}
    updateDesc = () => {
        let xmlHttp = new XMLHttpRequest();
        let url = "/plando/"+this.state.seed_name+"/upload";
        xmlHttp.open("POST", url, true);
        xmlHttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
        let res = {}
        res.desc = this.state.seed_desc
        res.name = this.state.seed_name
        res.oldName = this.state.seed_name
        xmlHttp.send(encodeURI("seed="+JSON.stringify(res)));

    }
};

