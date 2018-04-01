import React from 'react';
import './index.css';
import './bootstrap.cyborg.min.css';
//import registerServiceWorker from './registerServiceWorker';
import { Map, Tooltip, TileLayer} from 'react-leaflet';
import Leaflet from 'leaflet';

import {download, pickups, pickup_name, PickupMarkersList, pickup_icons, getMapCrs} from './shared_map.js';
import { Form, FormGroup, Label, Button, Input, Dropdown, DropdownToggle, DropdownMenu, DropdownItem } from 'reactstrap';

const locs = []

let ks = Object.keys(pickups)
for(let pre in ks) {
	pre = ks[pre];
	for(let p in pickups[pre]) {
		let pick = pickups[pre][p]
		locs.push(pick);
	}
}




function getPickupMarkers(pickupTypes, placements, reachable, flags, setSelected) {
	let hide_unreachable = flags.includes("hide_unreachable")
	let markers = []
	for(let i in pickupTypes) {
		let pre = pickupTypes[i];
		for(let p in pickups[pre]) {

			let pick = pickups[pre][p]
			let show = true;
			if(hide_unreachable && !reachable.includes(pick.zone)) 
						show = false;
			if(show)
			{
				let raw = placements[pick.loc];
				if(!raw)
					raw = "";
				else 
					{
						let pieces = raw.split("|");
						raw = pickup_name(pieces[0], pieces[1]) || raw;
					}
				let inner = (
				<Tooltip>
					<span>
						{raw}
					</span> 
				</Tooltip>
				);
				let name = pick.zone + "|" + pick.name+"|"+pick.loc
				let onclick = setSelected(name)
				markers.push({id: name, opacity:1, position: [pick.y, pick.x], inner: inner, icon: pickup_icons[pre], onClick: onclick});								
			}
	
		}
	}
	return markers
};

// Work-around for lines between tiles on fractional zoom levels
// https://github.com/Leaflet/Leaflet/issues/3575
(function(){
    var originalInitTile = Leaflet.GridLayer.prototype._initTile
    Leaflet.GridLayer.include({
        _initTile: function (tile) {
            originalInitTile.call(this, tile);

            var tileSize = this.getTileSize();

            tile.style.width = tileSize.x + 1 + 'px';
            tile.style.height = tileSize.y + 1 + 'px';
        }
    });
})()

const DEFAULT_VIEWPORT = {
	  center: [0, 0],
	  zoom: 3,
	}
const crs = getMapCrs();
class PlandoBuilder extends React.Component {
  constructor(props) {
    super(props)
    this.dropdownToggle = this.dropdownToggle.bind(this);
    this.dropdownSet = this.dropdownSet.bind(this);
    this.state = {dropdownOpen: false, placements: {}, selected: "WallJump|SKWallJump|-3160308", reachable: {}, flags: ['show_pickups'], locations: [], viewport: DEFAULT_VIEWPORT, seedFlags:"Shards,Sync5.1,mode=4,Custom|Plando", pickups: ["EX", "HC", "SK", "Pl", "KS", "MS", "EC", "AC"] }
  };

  dropdownToggle = () => { this.setState({dropdownOpen: !this.state.dropdownOpen}) }
  dropdownSet = (event) => {
  	this.setState({dropdownOpen: !this.state.dropdownOpen, selected: event.target.innerText}) }
  setSelected = (set_to) => { return (event) => this.setState({selected: set_to}) }
  updatePlacement = (event) => {
  	let placements = {...this.state.placements};
  	let coords = this.state.selected.split("|")[2];
  	placements[coords] = event.target.value;
  	this.setState({placements: placements}) }
  flagsChanged = (newVal) => { this.setState({flags: newVal}) }
  updateSeedFlags = (newVal) => { this.setState({seedFlags: newVal}) }
  onViewportChanged = viewport => { this.setState({ viewport }) }
  downloadSeed = () => {
  		let seed = [this.state.seedFlags]
		let ks = Object.keys(this.state.placements)
		for(let i in ks) {
			let loc = ks[i];
			let val = this.state.placements[loc];
			if(val === "FILL")
				val = "EX|50";
			seed.push(loc+"|"+val);
		}
		download('randomizer.dat', seed.join("\n")); 	
  	}

	
    render() {
	const pickups = this.state.flags.includes('show_pickups') ? ( <PickupMarkersList markers={getPickupMarkers(this.state.pickups, this.state.placements, this.state.reachable, this.state.flags, this.setSelected)} />) : null
	const items = locs.map(pick => {
		let color =  (!this.state.placements[pick.loc]) ? "text-success" : "text-warning";
		let text = pick.zone + "|" + pick.name+"|"+pick.loc;
		return (<DropdownItem onClick={this.dropdownSet} color={color}>{text}</DropdownItem>);	
	});
	let coords = this.state.selected.split("|")[2];
	if(!this.state.placements[coords]) 
		this.state.placements[coords] = "FILL";
	
    return (
          <div style={{ textAlign: 'center' }}> 
        <Button onClick={this.downloadSeed} >
       		 Download Seed
        </Button>
        <Button  onClick={ () => this.setState({ viewport: DEFAULT_VIEWPORT }) } >
          Reset View
        </Button>

      <Form>
        <FormGroup>
          <Label for="loc_setter">Location</Label>
		  <Dropdown name="loc_setter" isOpen={this.state.dropdownOpen} toggle={this.dropdownToggle}>
		  <DropdownToggle caret>
		  {this.state.selected}
		  </DropdownToggle>
		  <DropdownMenu>
		  {items}
		  </DropdownMenu>
		  </Dropdown>
        </FormGroup>
        {' '}
        <FormGroup>
          <Label for="pick_setter">Pickup</Label>
	      <Input type="text" name="pick_setter" value={this.state.placements[coords]} onChange={this.updatePlacement} />
        </FormGroup>
        {' '}
        <FormGroup>
          <Label for="flag_setter">Seed Flags</Label>
	      <Input type="text" name="flag_setter" value={this.state.seedFlags} onChange={this.updateSeedFlags} />
        </FormGroup>
		</Form>
	  

        <Map crs={crs} onViewportChanged={this.onViewportChanged} viewport={this.state.viewport}>

     <TileLayer url=' https://ori-tracker.firebaseapp.com/images/ori-map/{z}/{x}/{y}.png' noWrap='true'  />
		{pickups}
     </Map>
     </div>
	)
  }
}

export default PlandoBuilder;