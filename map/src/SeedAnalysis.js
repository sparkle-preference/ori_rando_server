import React from 'react';
import {doNetRequest, stuff_by_type, picks_by_zone, picks_by_loc} from './shared_map.js';
import {ButtonDropdown, Button, Container, Row, Col, Input} from 'reactstrap';
import {Helmet} from 'react-helmet';

const textStyle = {color: "black", textAlign: "center"}
// one day I'll figure out why I left progressive mapstones out of picks_by_[zone|loc|area]
// by default. But not today!

const EMPTY_COUNTS = {"RB|17": 0, "RB|19": 0, "RB|21": 0, "TOTAL": 0};
const ALPHA_ZONES = ["Blackroot", "Forlorn", "Ginso", "Glades", "Grotto", "Grove", "Horu", "Mapstone", "Misty", "Sorrow", "Swamp", "Valley"];
const COL_NAMES = ["Location", "Zone", "Total", "WallJump", "ChargeFlame", "DoubleJump", "Bash", "Stomp", "Glide", "Climb", "ChargeJump", "Dash", "Grenade", "GinsoKey", "ForlornKey", "HoruKey", "Water", "Wind", "TPForlorn", "TPGrotto", "TPSorrow", "TPGrove", "TPSwamp", "TPValley"];
const COL_ORDER = ["TOTAL", "SK|3", "SK|2", "SK|5", "SK|0", "SK|4", "SK|12", "SK|14", "SK|8", "SK|50", "SK|51", "EV|0", "EV|2", "EV|4", "EV|1", "EV|3", "TP|Forlorn", "TP|Grotto", "TP|Sorrow", "TP|Grove", "TP|Swamp", "TP|Valley"];
["Skills", "Events", "Teleporters"].forEach(stuff_type => {
	stuff_by_type[stuff_type].forEach(stuff => EMPTY_COUNTS[stuff.value] = 0 )
	})
delete EMPTY_COUNTS["EV|5"] // not that interested in warmth locations tbh

export default class SeedAnalysis extends React.Component {
  	constructor(props) {
    	super(props);
    	let seed_data = {};
    	Object.keys(picks_by_loc).forEach(loc => seed_data[loc] = {...EMPTY_COUNTS})
    	this.state = {seed_data: seed_data, fill_alg: "Balanced", key_mode: "Clues", vars: ["ForceTrees"], 
    					paths: ["normal", "speed", "lure", "dboost-light"], count: 0, fails: 0, limit: 50};
	}
	
    parseSeed = (seed) => {
		let lines = seed.split("\n")
		let new_locs = {}
	    for (let i = 1, len = lines.length; i < len; i++) {
	    	let [loc, code, id] = lines[i].split("|");
	    	let codeid = code+"|"+id
	    	if(COL_ORDER.includes(codeid)) new_locs[loc] = codeid
    	}
    	this.setState(prev => {
	    		let data = prev.seed_data;
		    	Object.keys(new_locs).forEach(loc => {
		    		if(Object.keys(data).includes(loc))
		    		{
			    		data[loc][new_locs[loc]] += 1
			    		data[loc]["TOTAL"] += 1		    			
		    		} else {
		    			console.log(loc, Object.keys(data))
		    		}
		    		
		    	})
		    	return {seed_data: data, count: this.state.count+1}
			},this.getSeed);
	}
	
	getSeed = () => {
		if(this.state.count >= this.state.limit)
			return
		let params = ["tracking=Disabled"];
		params.push("key_mode="+this.state.key_mode)
		params.push("gen_mode="+this.state.fill_alg)
		this.state.vars.forEach(v => params.push("var="+v))
		this.state.paths.forEach(p => params.push("path="+p))
		params.push("seed="+Math.round(Math.random() * 1000000000));
		let url = "/generator/json?" + params.join("&");
		doNetRequest(url,this.urlCallback)
	}
	
	urlCallback = ({status, response}) => {
		if(status !== 200)
		{
			this.setState({fails: this.state.fails+1},this.getSeed)
		}
		let res = JSON.parse(response);
		this.parseSeed(res.players[0].seed);
	}



	render = () => {
		
		let rows = ALPHA_ZONES.map(zone => {
			return picks_by_zone[zone].sort((a,b) => this.state.seed_data[b.loc]["TOTAL"] - this.state.seed_data[a.loc]["TOTAL"]).map(pick => {
				let counts = this.state.seed_data[pick.loc];
				if(!counts) {
					console.log(pick.loc,Object.keys(this.state.seed_data))
				}
				let loc_zone = [
					(<td class="border">{[pick.area, pick.name, "("+(pick.x / 4)*4, (pick.y / 4)*4+")"].join(" ")}</td>),
					(<td class="border">{pick.zone}</td>)
				];
				let cols = COL_ORDER.map(key => (<td class="border">{counts[key]}</td>))
				return (
				<tr class="border-top border-dark">
					{loc_zone}
					{cols}
				</tr>
				)
			})
		})
		let header = COL_NAMES.map(name => (<td class="border pl-1 pr-1">{name}</td>))
		
		return (
			<div class="w-100">
            <Helmet>
                <style>{'body { background-color: white}'}</style>
            </Helmet>
            <Container fluid className="w-80">
            <Row>
	            <Col xs="1">
		            <Button onClick={this.getSeed}>Get Seeds</Button>
		        </Col>
	            <Col xs="1">
		            {this.state.count}/{this.state.limit} seeds ({this.state.fails} failed)
		        </Col>
	            <Col xs="2"><Row>
					<Col>Limit</Col>
					<Col xs="8"><Input type="number" value={this.state.limit} onChange={(n) => this.setState({limit: parseInt(n.target.value, 10)})}/></Col>
		        </Row></Col>
	            <Col xs="2"><Row>
					<Col>Mode</Col>
					<Col xs="8"><Input type="text" value={this.state.key_mode} onChange={(n) => this.setState({key_mode: n.target.value})}/></Col>
		        </Row></Col>
	            <Col xs="3"><Row>
					<Col>Paths</Col>
					<Col xs="10"><Input type="text" value={this.state.paths.join(",")} onChange={(n) => this.setState({paths: n.target.value.split(",")})}/></Col>
		        </Row></Col>
	            <Col xs="2"><Row>
					<Col>Vars</Col>
					<Col xs="10"><Input type="text" value={this.state.vars.join(",")} onChange={(n) => this.setState({vars: n.target.value.split(",")})}/></Col>
		        </Row></Col>
	        </Row>
	        </Container>

            <table class="border"><tbody>
				<tr>{header}</tr>
				{rows}
			</tbody></table>
			</div>
	)

	}
};

