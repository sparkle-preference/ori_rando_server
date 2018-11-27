import './index.css';
import React from 'react';
import {LayerGroup, ZoomControl, Map, Tooltip, TileLayer} from 'react-leaflet';
import Leaflet from 'leaflet';
import {get_int, get_list, presets, logic_paths, Blabel} from './common.js';
import {stuff_by_type,  str_ids, picks_by_type, picks_by_area, pickup_name, PickupMarkersList, get_icon, getMapCrs, 
        name_from_str, select_styles, select_wrap} from './shared_map.js';
import Select from 'react-select';
import {Row, Input, Col, Container, Button, Collapse} from 'reactstrap';
import Control from 'react-leaflet-control';
import Dropzone from 'react-dropzone'
import {Helmet} from 'react-helmet';


const crs = getMapCrs();

const DEFAULT_REACHABLE = {'SunkenGladesRunaway': [["Free"]]};
const DEFAULT_VIEWPORT = {
      center: [0, 0],
      zoom: 4,
}

const paths = Object.keys(presets);
const relevant_picks = ["RB|6", "RB|8", "RB|9", "RB|10", "RB|11", "RB|12", "RB|13", "RB|15","RB|17","RB|19", "RB|21", "HC|1", "EC|1", "KS|1", "MS|1", "AC|1", 'SK|0', 'SK|51', 'SK|2', 'SK|3', 'SK|4', 'SK|5', 'SK|8', 'SK|12', 'SK|50', 'SK|14', 'TP|Ginso', 'TP|Horu', 'TP|Grotto', 'TP|Grove', 'TP|Forlorn', 'TP|Sorrow', 'TP|Swamp', 'TP|Valley', 'EV|0', 'EV|1', 'EV|2', 'EV|3', 'EV|4']

// patch picks_by_area to include mapstone areas because haha fuck
picks_by_type["Ma"].forEach(pick => {
    picks_by_area[pick.area] = [pick]
})

const xml_name_to_code = {
'KS': 'KS|1',
'MS': 'MS|1',
'EC': 'EC|1',
'HC': 'HC|1',
'AC': 'AC|1',
'TPSwamp': 'TP|Swamp',
'TPGrove': 'TP|Grove',
'TPGrotto': 'TP|Grotto',
'TPValley': 'TP|Valley',
'TPSorrow': 'TP|Sorrow',
'TPForlorn': 'TP|Forlorn',
'TPGinso': 'TP|Ginso',
'TPHoru': 'TP|Horu',
'Bash': 'SK|0',
'ChargeFlame': 'SK|2',
'WallJump': 'SK|3',
'Stomp': 'SK|4',
'DoubleJump': 'SK|5',
'ChargeJump': 'SK|8',
'Climb': 'SK|12',
'Glide': 'SK|14',
'Dash': 'SK|50',
'Grenade': 'SK|51',
'GinsoKey': 'EV|0',
'Water': 'EV|1',
'ForlornKey': 'EV|2',
'Wind': 'EV|3',
'HoruKey': 'EV|4'
}

const dev = window.document.URL.includes("devshell")

function get_manual_reach() {
    let HC = get_int("HC", 0);
    let EC = get_int("EC", 0);
    let AC = get_int("AC", 0);
    let KS = get_int("KS", 0);
    let MS = get_int("MS", 0);
    let skills = get_list("SK"," ").map(skill => { let parts = skill.split("|"); return {label: pickup_name(parts[0], parts[1]), value: skill}; });
    let evs = get_list("EV"," ").map(event => { let parts = event.split("|"); return {label: pickup_name(parts[0], parts[1]), value: event}; });
    let tps  = get_list("TP"," ").map(tp => {return {label: tp.substr(3) + " TP", value: tp}; });
    return {HC: HC, EC: EC, AC: AC, KS: KS, MS: MS, skills: skills, tps: tps, evs: evs};
}

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


const code_to_group = {};
Object.keys(stuff_by_type).forEach(group => {
    stuff_by_type[group].forEach(stuff => {
        code_to_group[stuff.value] = group
    });
});

const marker_types = Object.keys(picks_by_type).filter(t => t !== "MP");
const int = (s) => parseInt(s,10)
const rnd = (x) => Math.floor(int(x)/4.0) * 4.0

function getPickupMarkers(state, setSelected) {
    let placements = state.placements;
    let reachable = Object.keys(state.reachable)
    let markers = []
    let search = state.searchStr ? state.searchStr.toLowerCase() : false
    marker_types.forEach(pre => {
        picks_by_type[pre].forEach(pick => {
            let x = pick.hasOwnProperty("_x") ? pick._x : pick.x
            let y = pick.hasOwnProperty("_y") ? pick._y : pick.y
            let icon = get_icon(pick, state.highlight_picks.includes(pick.loc) ? "red" : null)
            let rows = null;
            let base_name = pick.area + " " +pick.name + " ("+rnd(pick.x)+" "+rnd(pick.y)+")";
            let name = "";
            if(reachable.includes(pick.area) || (search && base_name.toLowerCase().includes(search)))
            {
                if(pick.name === "MapStone") {
                    rows = picks_by_type["MP"].map(ms => {
                        name = placements[ms.loc] ? placements[ms.loc].label : base_name
                        return (
                            <tr><td style={{color:'black'}}>
                                {name}
                            </td></tr>
                        )
                    });
                } else {
                    name = placements[pick.loc] ? placements[pick.loc].label : base_name;
                      rows =  (
                        <tr><td style={{color:'black'}}>
                              {name}
                        </td></tr>
                      )
                }
                let inner = (
                    <Tooltip>
                        <table>{rows}</table>
                    </Tooltip>
                );
                if(search && (name.toLowerCase().includes(search) || base_name.toLowerCase().includes(search)))
                    icon = get_icon(pick, "green");
                markers.push({key: x+","+y, position: [y, x], inner: inner, icon: icon, onClick: () => setSelected({label: name, value: pick}) });
            }
        });
    });
    return markers
};


class LogicHelper extends React.Component {
  constructor(props) {
        super(props)
    
        this.state = {mousePos: {lat: 0, lng: 0}, seed_in: "", reachable: {...DEFAULT_REACHABLE}, new_areas: {...DEFAULT_REACHABLE}, selected: "", selected_area: "", history: {}, open_world: false,
                      step: 0, placements: {}, viewport: {center: [0, 0], zoom: 5}, hasSeed: false, highlight_picks: [], logicMode: 'manual', searchStr: "", noMarkers: false, closed_dungeons: false}
    }

     getInventory = () => {
        let activeAreas = this.state.reachable;
        let placements = this.state.placements;
        let inventory = {"Cells/Stones": {"HC|1": ["Free", "Free", "Free"]}}
        let addToInventory = (item, pick) => {
            let group = code_to_group[item];
            if(relevant_picks.includes(item))
            {
                if(!Object.keys(inventory).includes(group))
                    inventory[group] = {};
                if(!Object.keys(inventory[group]).includes(item))
                    inventory[group][item] = [];
                inventory[group][item].push(pick);                          
            }            
        }
        Object.keys(activeAreas).forEach(area => {
            if(picks_by_area[area])
                picks_by_area[area].forEach(pick => {
                    if(placements[pick.loc])
                    {                    
                        let item = placements[pick.loc].value;
                        if(item.startsWith("MU")) {
                            let parts = item.substr(3).split("/");
                            while(parts.length > 1) {
                                addToInventory(parts.shift()+"|"+parts.shift(), pick)
                            }
                        } else {
                            addToInventory(item, pick);
                        }
                    } 
                });
        });
        return inventory;
    }
      
    getInventoryPane = (inventory) => {
        if(!this.state.hasSeed)
            return null
        let groups = Object.keys(inventory).map(group => {
            let items = Object.keys(inventory[group]).map(code => {            
                let picks = inventory[group][code];
                let count = picks.length;
                let name = name_from_str(code);
                let buttontext = name + (count > 1 ? " x" + count : "")

                return (
                    <Col xs="auto" className="pr-0"><Button size="sm" color={"danger"} disabled={picks.every(pick => pick === "Free")} outline={this.state.selected !== name} onClick={() => this.onGroupClick(picks, name)}>{buttontext}</Button></Col>
                )
            });
            return (
            <Row className="p-1 border-bottom border-left border-right border-warning">
                <Col className="pl-0 pr-0" xs="3"><Blabel>{group}:</Blabel></Col>
                <Col xs="9"><Row>
                {items}
                </Row></Col>
            </Row>
            )
        });
        return [(
            <Row className="pt-2 border-bottom border-warning">
                <Col xs={{size:6, offset:3}} className="pt-2 pb-2"> <Blabel outline color="warning">Inventory</Blabel></Col>
            </Row>
            ),groups]
    }

    getAreasPane = (inventory) => {
        let area_groups = Object.keys(this.state.new_areas).filter(area => area.substr(0,2) !== "MS").map((area) => {
            let is_selected = this.state.hasSeed && this.state.selected_area === area;
            let paths = this.state.new_areas[area];
            let path_rows = is_selected ? paths.map(reqs => {
                if(reqs.length === 1 && reqs[0] === "Free")
                    return null;
                    
                
                let buttons = reqs.map(req => {
                    let count = 1;
                    if(req.includes("(")) {
                        count = req.substr(3,req.indexOf(")")-3)
                        req = req.substr(0,2)
                    }
                    if(!xml_name_to_code.hasOwnProperty(req))
                        return null;
                    let code = xml_name_to_code[req]
                    if(!code_to_group.hasOwnProperty(code))
                        return null;
                    let group = code_to_group[code]
                    if(!inventory.hasOwnProperty(group) || !inventory[group].hasOwnProperty(code)) {
                        return null;
                    }
                    let picks = inventory[group][code]
                    let name = name_from_str(code)+ (count > 1 ? " x" + count : "")
                    return (
                        <Button color={"danger"} outline={this.state.selected !== name} size="sm" onClick={() => this.onGroupClick(picks, name)}>{name}</Button>
                    )
                }).reduce((accu, elem) => accu === null ? [elem] : [...accu, <span>+</span>, elem] , null);
                return ( 
                    <li>
                    {buttons}
                    </li>
                );
            }) : []; 
            let area_name = area.split(/(?=[A-Z])/).join(" ");
            let unlocked_with = path_rows.filter(x => x !== null).length > 0 ? (<div>unlocked with:</div>) : null
            if(!picks_by_area.hasOwnProperty(area))
                return null
            return (
            <div>
                <Button color={is_selected ? "warning" : "danger"} outline={this.state.selected !== area}  onClick={() => this.setState({selected_area: area}, () => this.onGroupClick(picks_by_area[area], area))}>{area_name}</Button>
                <Collapse isOpen={is_selected}>
                    {unlocked_with}
                    <ul>
                    {path_rows}
                    </ul> 
                </Collapse>
            </div>
            )  
        });
        return (
            <div>
                <div style={{textAlign: 'center', fontSize: '1.2em' }}>{this.state.hasSeed ? "New Reachable Areas" : "Reachable Areas"}</div>
                {area_groups}
            </div>
        )
    }


    getManualLogicControls = () => {
        let numInputData = {HC: "Health Cells:", EC: "Energy Cells:", KS: "Keystones:", MS: "Mapstones:", AC: "Ability Cells:"};
        let numInputs  = Object.keys(numInputData).map(code => (
            <Row className="p-1">
                <Col xs="4" className="pr-0">
                    <Blabel >{numInputData[code]}</Blabel>
                </Col>
                <Col xs="8">
                        <Input type="number" value={this.state.manual_reach[code]} onChange={e => {
                            let newVal = parseInt(e.target.value, 10);
                            if(newVal >= 0)
                                this.updateManual(code, newVal);   
                            else
                                this.updateManual(code, 0);   
                            }}/>
                </Col>
            </Row>
        ))
        return (
            <Collapse className="border-info border rounded" isOpen={this.state.logicMode === "manual"}>
                {numInputs}
                <Row className="p-1"><Col xs="12">
                    <Select styles={select_styles} placeholder="Skills" options={stuff_by_type["Skills"]} onChange={(n) => this.updateManual("skills", n)} isMulti={true} value={this.state.manual_reach.skills}></Select>
                </Col></Row>
                <Row className="p-1"><Col xs="12">
                    <Select styles={select_styles} placeholder="Teleporters" options={stuff_by_type["Teleporters"]} onChange={(n) => this.updateManual("tps", n)} isMulti={true} value={this.state.manual_reach.tps}></Select>
                </Col></Row>
                <Row className="p-1"><Col xs="12">
                    <Select styles={select_styles} placeholder="Events" options={stuff_by_type["Events"]} onChange={(n) => this.updateManual("evs", n)} isMulti={true} value={this.state.manual_reach.evs}></Select>
                </Col></Row>
                <Row className="p-1">
                    <Col xs="6">
                        <Button block outline={!this.state.open_world} color="primary" onClick={() => this.setState({open_world: !this.state.open_world}, this.resetReachable)}>Open World</Button>
                    </Col>
                    <Col xs="6">
                        <Button block outline={!this.state.closed_dungeons} color="warning" onClick={() => this.setState({closed_dungeons: !this.state.closed_dungeons}, this.resetReachable)}>Closed Dungeons</Button>
                    </Col>
                </Row>
            </Collapse>
        )
    }


    componentWillMount() {
        let url = new URL(window.document.location.href); // TODO: get all non-proccessed url params this way instead of via template (it's easier)
        let pathmode = url.searchParams.get("pathmode");
        let search = url.searchParams.get("search") || "";
        let manual_reach = get_manual_reach();
        let modes;
        let a = parseFloat(url.searchParams.get("a") || 0)
        let b = parseFloat(url.searchParams.get("b") || 0)
        let x = parseFloat(url.searchParams.get("x") || 0)
        let y = parseFloat(url.searchParams.get("y") || 0)
    
        if(pathmode && paths.includes(pathmode)) {
            modes = presets[pathmode];
        } else {
            pathmode = "standard";
            modes = presets['standard'];
        }

        this.setState({a:a, b:b, x:x, y:y, modes: modes, search: search, pathMode: {label: pathmode, value: pathmode}, manual_reach: manual_reach}, () => {this.updateReachable() ; this.updateURL()})
    };
    componentDidMount() {
         setTimeout(() => {
        this.refs.map.leafletElement.invalidateSize(false);
        this.setState({viewport: DEFAULT_VIEWPORT});
         }, 100);
    }


    onDragEnter = () => this.setState({dropzoneActive: true});

    onDragLeave = () => this.setState({dropzoneActive: false});
    
    onDrop = (files) => {
        let file = files.pop();
        if(file) {
            let reader = new FileReader();
            reader.onload = () => {
                let text = reader.result;
                let {closed_dungeons, open_world, plc} = this.parseUploadedSeed(text);
                this.setState({placements: plc, open_world: open_world, closed_dungeons: closed_dungeons, dropzoneActive: false, hasSeed: true, logicMode: "auto"}, this.resetReachable)
                window.URL.revokeObjectURL(file.preview);
                // do whatever you want with the file content
            };
            reader.onabort = () => console.log('file reading was aborted');
            reader.onerror = () => console.log('file reading has failed');
    
            reader.readAsText(file);            
        } else {
            this.setState({dropzoneActive: false})
        }
    }


    selectPickup = (pick, pan=true) => {
        let viewport = this.state.viewport;
        if(pan) {
            let x = pick.value.hasOwnProperty("_x") ? pick.value._x : pick.value.x
            let y = pick.value.hasOwnProperty("_y") ? pick.value._y : pick.value.y
            viewport = {
                  center: [y, x],
                  zoom: 5,
                }
            this.setState({viewport: viewport});
        }
    }

    parseUploadedSeed = (seedText) => {
        let lines = seedText.split("\n")
        let newplc = {}
        let open_world = false;
        let closed_dungeons = false;
        lines[0].split(",").forEach(flag => {
            if(Object.keys(presets).includes(flag.toLowerCase()))
                this.onPathModeChange({label: flag, value: flag.toLowerCase()})
            if(flag.toLowerCase() === "openworld")
                open_world = true;            
            if(flag.toLowerCase() === "closeddungeons")
                closed_dungeons = true;            
        })
        for (let i = 1, len = lines.length; i < len; i++) {
            let line = lines[i].split("|")
            let loc = parseInt(line[0], 10);
            let code = line[1];
            let id = str_ids.includes(code) ? line[2] : parseInt(line[2], 10);
            let name = pickup_name(code, id);
            let stuff = {label: name, value:code+"|"+id};
            newplc[loc] = stuff;
        }
        return {plc: newplc, open_world: open_world, closed_dungeons: closed_dungeons};
    }

    onGroupClick = (picks, clickedName) =>  {
        let activated = (clickedName !== this.state.selected)
        let selected = "";
        let viewport = this.state.prev_viewport;
        let highlight_picks = [];
        let map = this.refs.map.leafletElement;
        picks = picks.filter(pick => pick !== "Free");
        if(activated)
        {
            selected = clickedName;
            highlight_picks = picks.map(pick => pick.loc);
            let coords = picks.map(pick => { return {x: pick.hasOwnProperty("_x") ? pick._x : pick.x, y: pick.hasOwnProperty("_y") ? pick._y : pick.y}; })
            let center = coords.reduce((acc, coord) => { return {x: (coord.x / coords.length)+acc.x,y: (coord.y / coords.length)+acc.y} ; }, {x: 0, y: 0});
            if(coords.length > 1)
            {
                let xmin = Math.min(...coords.map(coord => coord.x));
                let xmax = Math.max(...coords.map(coord => coord.x));
                let ymin = Math.min(...coords.map(coord => coord.y));
                let ymax = Math.max(...coords.map(coord => coord.y));
                map.flyToBounds([[ymin, xmin], [ymax, xmax]], {maxZoom: 6, padding: [10, 10]})
            } else {
                map.flyTo([center.y, center.x], 6)
            }            
        } else
            map.flyTo(viewport.center, viewport.zoom)
        
        this.setState({highlight_picks: highlight_picks, selected: selected, prev_viewport: this.state.viewport})
    }
    
    updateURL = () => { 
        if(this.state.logicMode === "auto")
            return
        let reach = this.state.manual_reach
        let args = Object.keys(reach).filter(key => Array.isArray(reach[key]) ? reach[key].length > 0 : reach[key] > 0 ).map(key => key + "=" + (Array.isArray(reach[key]) ? reach[key].map(i => i.value).join("+") : reach[key]))
        args.unshift("pathmode="+this.state.pathMode.value)
        if(this.state.searchStr) args.push("search="+this.state.searchStr)
        window.history.replaceState('',window.document.title, window.document.URL.split("?")[0]+"?"+args.join("&"));        
    }
    
    updateManual = (param, val) => this.setState(prevState => {
        let manual_reach = prevState.manual_reach;
        manual_reach[param] = val;
        return {manual_reach: manual_reach}
    }, () => {this.resetReachable() ; this.updateURL()})
    
      updateReachable = () => {
          if(!this.state.reachable || this.state.reachable === undefined) {
              this.resetReachable();
              return
          }
          
          let reachableStuff = {};
          if(this.state.logicMode === "auto")
          {
              if(!this.state.hasSeed)
                  return;
              Object.keys(this.state.reachable).forEach((area) => {
                  if(picks_by_area.hasOwnProperty(area))
                      picks_by_area[area].forEach((pick) => {
                          if(this.state.placements[pick.loc])
                          {
                              let code = this.state.placements[pick.loc].value;
                              if(!["SH", "NO", "EX", "WT", "HN"].includes(code.substr(0,2)))
                                  if(reachableStuff.hasOwnProperty(code))
                                    reachableStuff[code] += 1;
                                else
                                    reachableStuff[code] = 1;
                          }
                      });
              });
        } else {
            ["HC", "EC", "AC", "KS", "MS"].forEach((code) => {
                if(this.state.manual_reach[code] > 0)
                    reachableStuff[code+"|1"] = this.state.manual_reach[code];
            });
            this.state.manual_reach.skills.forEach(skill => {
                reachableStuff[skill.value] = 1;
              });
            this.state.manual_reach.evs.forEach(event => {
                reachableStuff[event.value] = 1;
              });
            this.state.manual_reach.tps.forEach(tp => {
                reachableStuff[tp.value] = 1;
              });
          }
        let modes = this.state.modes.join("+");
        if(this.state.closed_dungeons) 
            modes +="+CLOSED_DUNGEON"
        if(this.state.open_world) 
            modes +="+OPEN_WORLD"
        getReachable((s) => this.setState(s), modes, Object.keys(reachableStuff).map(key => key+":"+reachableStuff[key]).join("+"));
      };

    onViewportChanged= (viewport) => this.setState({viewport: viewport})
    onSearch = (e) => this.setState({searchStr: e.target.value}, this.updateURL)
    onMode = (m) => () => this.setState(prevState => {
        if(prevState.modes.includes(m))
            return {modes: prevState.modes.filter(x => x !== m)}
        return {modes: prevState.modes.concat(m)}
    }, () => { this.updateURL() ; this.resetReachable()});
    onPathModeChange = (n) => this.setState({modes: presets[n.value], pathMode: n}, () => { this.updateURL() ; this.resetReachable()});
    resetReachable = () => this.setState({ reachable: {...DEFAULT_REACHABLE}, new_areas: {...DEFAULT_REACHABLE}, selected: "", selected_area: "", highlight_picks: [], history: {}, step: 0}, () => (this.state.logicMode === "auto") ? null : this.updateReachable())
    unloadSeed = () => this.setState({hasSeed: false, placements: {}, logicMode: "manual"}, this.resetReachable)
    rewind = () => {
        if(dev)
            console.log(this.state)

        if(this.state.step>0)
            this.setState(prevState => {
                let hist = prevState.history[prevState.step-1];
                return {
                    highlight_picks: [],
                    selected: "",
                    selected_area: "",
                    reachable: {...hist.reachable}, 
                    new_areas: {...hist.new_areas}, 
                    step: prevState.step-1};
                }, () => dev ? console.log(this.state) : null)
    }

    render() {
        let { dropzoneActive } = this.state;
        let overlay_style = { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, padding: '10em 0', background: 'rgba(0,0,0,0.5)', textAlign: 'center', color: '#fff' };
        let inventory = this.getInventory();
        let inv_pane = this.getInventoryPane(inventory);
        let new_areas_report = null //this.getAreasPane(inventory); disabled until path compression exists
        let manual_controls = this.getManualLogicControls();
        let logic_auto_toggle = (
            <Collapse isOpen={this.state.hasSeed}>
            <Row  className="p-1">
                <Col xs="4">
                <Blabel >Logic Mode:</Blabel>
                </Col>
                <Col xs="4">
                    <Button block color="primary" onClick={() => this.setState({logicMode: "auto"}, this.resetReachable)} outline={this.state.logicMode !== "auto"}>Auto</Button>
                </Col>
                <Col xs="4">
                    <Button block color="primary" onClick={() => this.setState({logicMode: "manual"}, this.resetReachable)} outline={this.state.logicMode !== "manual"}>Manual</Button>
                </Col>
            </Row>
            </Collapse>
        ) 
        let step_buttons = (
            <Collapse isOpen={this.state.hasSeed}>
                <Row className="p-1">
                    <Col xs={{size: "5", offset: 1}}>
                        <Button block color="primary" onClick={this.unloadSeed} >Unload Seed</Button> 
                    </Col>
                    <Col xs={{size: "5", offset: 1}}>
                        <Button block color="primary" onClick={this.resetReachable} >Reset Steps</Button>
                    </Col>
                </Row>
                <Row className="p-1">
                    <Col xs={{size: "4", offset: 1}}>
                        <Button block color="primary" onClick={() => this.rewind()} >{"Back"}</Button>
                    </Col>
                    <Col xs="2">
                        <Blabel >{this.state.step}</Blabel>
                    </Col>
                    <Col xs="4">
                        <Button block color="primary" onClick={this.updateReachable} >{"Next"}</Button>
                    </Col>
                </Row>
            </Collapse>
        )
        let logic_path_buttons = logic_paths.map(lp => {return (<Col className="pr-0 pb-1" xs="4"><Button block size="sm" outline={!this.state.modes.includes(lp)} onClick={this.onMode(lp)}>{lp}</Button></Col>)});
        return (
          <Dropzone className="wrapper" disableClick onDrop={this.onDrop} onDragEnter={this.onDragEnter} onDragLeave={this.onDragLeave} >
          { dropzoneActive && <div style={overlay_style}>Import your randomizer.dat to begin analysis</div> }
                <Helmet>
                    <style type="text/css">{`
                        body {
                            background-color: black;
                            text-color: white;
                        }
                    `}</style>
                    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.3.1/dist/leaflet.css" integrity="sha512-Rksm5RenBEKSKFjgI3a41vrjkw4EVPlJ3+OiI65vTjIdo9brlAacEuKOiQ5OFh7cOI1bkDwLqdLw3Zg0cRJAAQ==" crossorigin=""/>
                </Helmet>

                <Map ref="map" crs={dev ? getMapCrs(this.state.x, this.state.y, this.state.a, this.state.b): crs} zoomControl={false} onMouseMove={(ev) => this.setState({mousePos: ev.latlng})} onViewportChanged={this.onViewportChanged} viewport={this.state.viewport}>
                    <ZoomControl position="topright" />
                    <Control position="topleft" >
                    <div>
                        <Blabel className="p-2">{Math.round(this.state.mousePos.lng)}, {Math.round(this.state.mousePos.lat)}</Blabel>
                    </div>
                    </Control>
                    <LayerGroup>
                        <PickupMarkersList markers={getPickupMarkers(this.state, this.selectPickup)} />
                    </LayerGroup>
                    <TileLayer url=' https://ori-tracker.firebaseapp.com/images/ori-map/{z}/{x}/{y}.png' noWrap='true'  />
                </Map> 
                <div className="controls">
                <Container fluid>
                    <Collapse isOpen={!this.state.hasSeed}>
                        <Row className="p-1"><Col xs="12">
                            <Blabel className="pt-2 pb-2" >Drag and drop your seed file onto the map to upload</Blabel>
                        </Col></Row>
                    </Collapse>
                    {step_buttons}
                    <Row className="p-1 border-top pb-3 pt-3">
                        <Col xs="4" className="pr-0">
                            <Blabel >Search</Blabel>
                        </Col>
                        <Col xs="8">
                            <Input type="text" value={this.state.searchStr} onChange={this.onSearch} />
                        </Col>
                    </Row>
                    {inv_pane}
                    {logic_auto_toggle}
                    {manual_controls}
                    <Row className="border-top border-bottom p-1">
                        <Col xs="4">
                            <Button color="primary" block active={this.state.display_logic} onClick={() => this.setState({display_logic: !this.state.display_logic})} >Logic Paths:</Button>
                        </Col>
                        <Col xs="8">
                            <Select styles={select_styles}  options={select_wrap(paths)} onChange={this.onPathModeChange} isClearable={false} value={this.state.pathMode}></Select>
                        </Col>
                    </Row>
                    <Collapse id="logic-options-wrapper" isOpen={this.state.display_logic}>
                    <Row className="p-1">
                        {logic_path_buttons}
                    </Row>
                    </Collapse>
                    {new_areas_report}
                </Container>
                </div>
            </Dropzone>

        )
    }
}

function uniq(array) {
    let seen = [];
    return array.filter(item => seen.includes(item.join("")) ? false : (seen.push(item.join("")) && true));
}


function getReachable(setter, modes, codes)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState === 4 && xmlHttp.status === 200)
            (function(res) {
                let reachable = JSON.parse(res);
                setter(prevState => {
                    let prevReachable = Object.keys(prevState.reachable);
                    if(Object.keys(reachable).filter(area => !prevReachable.includes(area)).length === 0)
                        return {}
                    let history = prevState.history;
                    let step = prevState.step;
                    let old_reachable = prevState.reachable;
                    history[step] = {reachable: {...prevState.reachable}, new_areas: {...prevState.new_areas}}
                    let new_areas = {};
                    Object.keys(reachable).forEach((area) => {
                        let paths = reachable[area].map(reqSet => Object.keys(reqSet))
                        if(!old_reachable.hasOwnProperty(area))
                        {
                            new_areas[area] = uniq(paths);
                            old_reachable[area] = [];
                        }
                        old_reachable[area] = uniq(old_reachable[area].concat(paths));
                    });
                    if(Object.keys(old_reachable).length >= 455) {
                        old_reachable["FinalEscape"] = [];
                    }
                    return {reachable: old_reachable, new_areas: new_areas, history: history, step: step+1, highlight_picks: []}                    
                });
            })(xmlHttp.responseText);
    }
    xmlHttp.open("GET", "/plando/reachable?modes="+modes+"&codes="+codes, true);
    xmlHttp.send(null);
}



export default LogicHelper;
