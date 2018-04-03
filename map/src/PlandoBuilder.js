import React from 'react';
import './index.css';
import './bootstrap.cyborg.min.css';
//import registerServiceWorker from './registerServiceWorker';
import { Map, Tooltip, TileLayer} from 'react-leaflet';
import Leaflet from 'leaflet';

import {download, getStuffType, stuff_types, stuff_by_type, picks_by_type, picks_by_loc, picks_by_zone, zones,  pickup_name, PickupMarkersList, pickup_icons, getMapCrs} from './shared_map.js';
import NumericInput from 'react-numeric-input';
import Select from 'react-select';
import 'react-select/dist/react-select.css';



const DEFAULT_VIEWPORT = {
	  center: [0, 0],
	  zoom: 3,
	}
const crs = getMapCrs();


function getPickupMarkers(pickupTypes, placements, reachable, flags, setSelected) {
	let hide_unreachable = flags.includes("hide_unreachable")
	let markers = []
	pickupTypes.forEach((pre) => {
		picks_by_type[pre].forEach((pick) => {
			let show = true;
			if(hide_unreachable && !reachable.includes(pick.area)) 
						show = false;
			if(show)
			{
				let raw = placements[pick.loc];
				if(!raw)
					raw = "";
				else 
					{
						let pieces = raw.value.split("|");
						raw = pickup_name(pieces[0], pieces[1]) || raw;
					}
				let inner = (
				<Tooltip>
					<span>
						{raw}
					</span> 
				</Tooltip>
				);
				let name = pick.name+"("+pick.x + "," + pick.y +")"
				let onclick = setSelected({label: name, value: pick})
				markers.push({key: name, opacity:1, position: [pick.y, pick.x], inner: inner, icon: pickup_icons[pre], onClick: onclick});								
			}
	
		});
	});
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

function shuffle (array) {
  var i = 0
    , j = 0
    , temp = null

  for (i = array.length - 1; i > 0; i -= 1) {
    j = Math.floor(Math.random() * (i + 1))
    temp = array[i]
    array[i] = array[j]
    array[j] = temp
  }
}


class PlandoBuiler extends React.Component {
  constructor(props) {
    super(props)
    let zone = 'Glades';
    let i = 8;
	let lastSelected = {};
	zones.forEach((zone) => {
		let pick = picks_by_zone[zone][0];
		lastSelected[zone] = {label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}
	});
    let pick = picks_by_zone[zone][i];
    let pickup = {label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}
    lastSelected['Glades'] = pickup
    this.state = {zone: zone, pickup: pickup, seed_in: "", lastSelected: lastSelected, placements: {}, stuff_type: "Skills", stuff: {value: "SK|0", label: "Bash"}, fill_opts: {HC: 13, EC: 15, AC: 34, KS: 40, MS: 9, EX: 300, dynamic: true}, 
		    reachable: {}, flags: ['show_pickups'], locations: [], viewport: DEFAULT_VIEWPORT, seedFlags:"Shards,Sync5.1,mode=4,Custom|Plando", pickups: ["EX", "HC", "SK", "Pl", "KS", "MS", "EC", "AC"] }
  };

	_fillUpdateHC = (n) => this.updateFill("HC",n)
	_fillUpdateEC = (n) => this.updateFill("EC",n)
	_fillUpdateAC = (n) => this.updateFill("AC",n)
	_fillUpdateKS = (n) => this.updateFill("KS",n)
	_fillUpdateMS = (n) => this.updateFill("MS",n)
	_fillUpdateEX = (n) => this.updateFill("EX",n)
	_onSeedFlags = (newVal) => { this.setState({seedFlags: newVal}) }

	_fillToggleDynamic = (n) => this.updateFill("dynamic",!this.state.fill_opts.dynamic)
    _onSelectZone = (newZone) => {this.selectPickup(this.state.lastSelected[newZone.value])};
    _onSelectStuffType = (newStuffType) => {
    	this.setState({stuff_type: newStuffType.value});
		if(stuff_by_type[newStuffType.value])
	    	this._onSelectStuff(stuff_by_type[newStuffType.value][0]);
	    else if(newStuffType.value === "Experience")
	    	this._onChangeExp(15,"15");
    	};
    _onChangeExp = (n,s,_) => this.place({label: s, value: "EX|"+s});
	_onSelectStuff = (newStuff) => this.place(newStuff);
	
	updateFill = (param,val) => this.setState(prevState => {
		console.log(param, val)
		let fill_opts = this.state.fill_opts;
		fill_opts[param] = val;
		return {fill_opts: fill_opts}
	});

    selectPickup = (pick) => {
    	let last = this.state.lastSelected;
    	let newStuff = this.state.placements[pick.value.loc];
		last[pick.value.zone] = pick;
		let new_viewport = {
			  center: [pick.value.y, pick.value.x],
			  zoom: 5,
			}
		let newStuffType = getStuffType(newStuff);
    	this.setState({pickup: pick, zone: pick.value.zone, lastSelected: last, viewport: new_viewport, stuff: newStuff, stuff_type: newStuffType});
    }

    selectPickupCurry = (pick) => () => this.selectPickup(pick)

    place = (s) => {
    	let old_stuff = this.state.stuff;
    	this.setState(prevState => {
	    	let plc = prevState.placements;
    		plc[prevState.pickup.value.loc] = s;
    		return {placements: plc, stuff: s};
		});
		let fill_opts = this.state.fill_opts;
		if(fill_opts.dynamic)
		{
			let old_code = old_stuff ? old_stuff.value.split("|")[0] : "";
			let new_code = s.value.split("|")[0];
			if(old_code === new_code)
				return
			for(let x of ["HC", "AC", "EC", "KS", "MS"]) {
				if(old_code === x)
					fill_opts[x] += 1;
				if(new_code === x)
					fill_opts[x] -= 1;
			}
			this.setState({fill_opts: fill_opts})
		}

    };

	tryParseSeed = (event) => {
		let seedText = event.target.value
		let lines = seedText.split("\n")
	    for (let i = 1, len = lines.length; i < len; i++) {
	    	let line = lines[i].split("|")
	    	let loc = line[0]*1;
	    	let code = line[1];
	    	let id = line[2]*1;
	    	let name = pickup_name(code, id);
	    	let stuff = {label: name, value:code+"|"+id};
	    	this.setState(prevState => {
		    	let plc = prevState.placements;
	    		plc[loc] = stuff;	    			
	    		return {placements: plc}
    		});	    	
    		if(loc === this.state.pickup.value.loc)
    		{
    			console.log(getStuffType(stuff), stuff)
				this.setState({stuff_type: getStuffType(stuff), stuff: stuff});
    		}
    	}
		this._onSeedFlags(lines[0]);
	}

	downloadSeed = () => {
		let seed = [this.state.seedFlags]
		let locs = Object.keys(picks_by_loc)
		let toFill = []
		let {HC, EC, AC, KS, MS, EX} = this.state.fill_opts
		locs.forEach((loc) => {
			if(this.state.placements.hasOwnProperty(loc)) 
				seed.push(loc+"|"+this.state.placements[loc]+"|"+picks_by_loc[loc].zone);
			else
				toFill.push(loc);
		});
		shuffle(toFill);
		toFill.forEach((loc) => {
			if(HC > 0) {
				HC -= 1;
				seed.push(loc+"|HC|1|"+picks_by_loc[loc].zone);				
			}						
			if(EC > 0) {
				EC -= 1;
				seed.push(loc+"|EC|1|"+picks_by_loc[loc].zone);				
			}						
			if(AC > 0) {
				AC -= 1;
				seed.push(loc+"|AC|1|"+picks_by_loc[loc].zone);				
			}						
			if(KS > 0) {
				KS -= 1;
				seed.push(loc+"|KS|1|"+picks_by_loc[loc].zone);				
			}						
			if(MS > 0) {
				MS -= 1;
				seed.push(loc+"|MS|1|"+picks_by_loc[loc].zone);				
			}
			seed.push(loc+"|EX|"+ Math.floor(Math.random() * EX)+"|"+picks_by_loc[loc].zone);				
		});
		download('randomizer.dat', seed.join("\n")); 	

	}	
	

	render() {
		const pickup_markers = this.state.flags.includes('show_pickups') ? ( <PickupMarkersList markers={getPickupMarkers(this.state.pickups, this.state.placements, this.state.reachable, this.state.flags, this.selectPickupCurry )} />) : null
		const zone_opts = zones.map(zone => ({label: zone, value: zone}))
		const pickups_opts = picks_by_zone[this.state.zone].map(pick => ({label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}) )
		let stuff_select;
		console.log(this.state);
		if(stuff_by_type[this.state.stuff_type]) 
		{
			let stuff = stuff_by_type[this.state.stuff_type];
			stuff_select = (<label style={{width: '100%'}}>Pickup: <Select options={stuff} onChange={this._onSelectStuff} value={this.state.stuff.value} label={this.state.stuff.label}/></label>)
		} else if(this.state.stuff_type === "Experience") {
			stuff_select = (<label style={{width: '100%'}}>Amount: <NumericInput min={0} value={this.state.stuff.label} onChange={this._onChangeExp}/></label> ) 
		} else if (this.state.stuff_type === "Fill") {
			stuff_select = (
			<table><tbody>
			<tr><td>
				Every pickup not explicitly assigned will be filled by default, using the numbers here. Experience (a random amount between 2 and the value you enter) will be assigned to the remaining pickups.
			</td></tr>
			<tr><td>
 	    	    <label>Automatically change these values when placing pickups (Highly Recommended!) <input type="checkbox" checked={this.state.fill_opts.dynamic} onChange={this._fillToggleDynamic}/>	</label>
			</td></tr>
			<tr><td><label>Health Cells: <NumericInput min={0} value={this.state.fill_opts.HC} onChange={this._fillUpdateHC}/></label></td></tr>
			<tr><td><label>Energy Cells: <NumericInput min={0} value={this.state.fill_opts.EC} onChange={this._fillUpdateEC}/></label></td></tr>
			<tr><td><label>Ability Cells: <NumericInput min={0} value={this.state.fill_opts.AC} onChange={this._fillUpdateAC}/></label></td></tr>
			<tr><td><label>Keystones: <NumericInput min={0} value={this.state.fill_opts.KS} onChange={this._fillUpdateKS}/></label></td></tr>
			<tr><td><label>Mapstones: <NumericInput min={0} value={this.state.fill_opts.MS} onChange={this._fillUpdateMS}/></label></td></tr>
			<tr><td><label>Experience Range: <NumericInput min={0} value={this.state.fill_opts.EX} onChange={this._fillUpdateEX}/></label></td></tr>

			</tbody></table>
			)
		}
		
		return (
		<table style={{width: '100%'}}><tbody>
		<tr><td style={{width: '80%'}}>

        <Map crs={crs} onViewportChanged={this.onViewportChanged} viewport={this.state.viewport}>
	     <TileLayer url=' https://ori-tracker.firebaseapp.com/images/ori-map/{z}/{x}/{y}.png' noWrap='true'  />
			{pickup_markers}
	     </Map></td>
		<td style={{width: '20%'}}>
			<table style={{width: '100%'}}><tbody>
				<tr><td><p>Import a seed by pasting it here</p></td></tr>
				<tr><td><textarea value={this.state.seed_in} onChange={this.tryParseSeed} /></td></tr>
				<tr><td><label style={{width: '100%'}}>Zone <Select options={zone_opts} onChange={this._onSelectZone} value={this.state.zone} label={this.state.zone}/></label></td></tr>
				<tr><td><label style={{width: '100%'}}>Location<Select options={pickups_opts} onChange={this.selectPickup} value={this.state.pickup} label={this.state.pickup.name+"("+this.state.pickup.x + "," + this.state.pickup.y +")"} /></label></td></tr>
				<tr><td><label style={{width: '100%'}}>Pickup Type<Select options={stuff_types} onChange={this._onSelectStuffType} value={this.state.stuff_type} label={this.state.stuff_type}/></label></td></tr>
				<tr><td>{stuff_select}</td></tr>
				<tr><td><label style={{width: '100%'}}>seed flags<input type="text" style={{width: '100%'}} value={this.state.seedFlags} onChange={this._onSeedFlags} /></label></td></tr>
				<tr><td><label style={{width: '100%'}}><button onClick={this.downloadSeed} >Download Seed</button></label></td></tr>

			</tbody></table>
		</td></tr>
		</tbody></table>
		)

	}


};



export default PlandoBuiler;










