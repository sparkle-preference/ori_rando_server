import './index.css';
import React from 'react';
import he from 'he';
import { ZoomControl, Map, Tooltip, TileLayer} from 'react-leaflet';
import Leaflet from 'leaflet';
import {NotificationContainer, NotificationManager} from 'react-notifications';
import 'react-notifications/lib/notifications.css';
import {Checkbox, CheckboxGroup} from 'react-checkbox-group';
import {get_param, get_flag, get_int, get_list, get_seed, presets, get_preset, logic_paths, pickup_name, PickupSelect, stuff_by_type} from './common.js';
import {download, picks_by_type, picks_by_loc, picks_by_zone, picks_by_area, zones, PickupMarkersList, get_icon, 
        getMapCrs, hide_opacity, select_wrap, is_match, str_ids, select_styles} from './shared_map.js';
import NumericInput from 'react-numeric-input';
import Select from 'react-select'
import {Creatable} from 'react-select';
import {Alert, Button, Collapse,  Container, Row, Col} from 'reactstrap';
import Control from 'react-leaflet-control';
import {Helmet} from 'react-helmet';
import Toggle from 'react-bootstrap-toggle';

NumericInput.style.input.width = '100%';
NumericInput.style.input.height = '36px';

const relevantCodes = ["HC", "AC", "EC", "KS", "MS", "TP", "RB", "EV", "SK"];
const DUNGEON_KEYS = ["EV|0", "EV|2", "EV|4"]
const DEFAULT_DATA = {
    '-280256': {label: "Energy Cell", value: "EC|1"},
    '-1680104': {label: "100 Experience", value: "EX|100"},
    '-12320248': {label: "Nothing", value: "NO|1"}
}

const DEFAULT_REACHABLE = {'SunkenGladesRunaway': [["Free"]]};
const DEFAULT_VIEWPORT = {
      center: [0, 0],
      zoom: 4,
    }
const keyNames = {"EV|0": "Water Vein", "EV|2": "Gumon Seal", "EV|4": "Sunstone"}
const mkClueOrderLabel = (clueOrder) => clueOrder.map(key => keyNames[key]).join(", ")
const CLUE_ORDERS = [
     ["EV|0", "EV|2", "EV|4"],
     ["EV|0", "EV|4", "EV|2"],
     ["EV|2", "EV|0", "EV|4"],
     ["EV|2", "EV|4", "EV|0"],
     ["EV|4", "EV|2", "EV|0"],
     ["EV|4", "EV|0", "EV|2"],
].map(clueOrder => {return {label: mkClueOrderLabel(clueOrder), value: clueOrder}})

const VALID_VARS = ["0XP", "NonProgressMapStones", "NoAltR", "ForceMaps", "ForceTrees", "Hard", "WorldTour", "OpenWorld", "ClosedDungeons", "OHKO", "Starved", "BonusPickups", "NoExtraExp"]
const VALID_KEYMODES = ["Shards", "Clues", "Limitkeys", "Free"];
const SEED_FLAGS = VALID_VARS.concat(VALID_KEYMODES);
const FLAG_CASEFIX = {};

SEED_FLAGS.forEach(flag => FLAG_CASEFIX[flag.toLowerCase()] = flag);

const modes_by_key = {"Shared": "Shared", "None": "Solo", "Split": "Shards Race"}
const COOP_MODES = Object.keys(modes_by_key).map((k) => { return {label: modes_by_key[k], value: k} });
const SHARE_TYPES = ["WorldEvents", "Misc", "Upgrades", "Teleporters", "Skills"]
const crs = getMapCrs();
const DANGEROUS = [-280256, -1680104, -12320248]
const paths = Object.keys(presets);

const dev = window.document.URL.includes("devshell")

function getPickupMarkers(state, setSelected, searchStr) {
    let pickupTypes = state.pickups
    let placements = state.placements
    let reachable = Object.keys(state.reachable)
    let flags = state.flags
    let hide_unreachable = flags.includes("hide_unreachable")
    let skip_danger = flags.includes("hide_softlockable")
    let skip_assigned = flags.includes("hide_assigned")
    let markers = []
    pickupTypes.forEach((pre) => {
        picks_by_type[pre].forEach((pick) => {
            let {x, y} = pick
            let icon = get_icon(pick)
            let show = !(skip_danger && DANGEROUS.includes(pick.loc));
            if(hide_unreachable && !reachable.includes(pick.area))
                        show = false;
            if(skip_assigned && placements[state.player].hasOwnProperty(pick.loc))
                        show = false;
            if(show)
            {
                let highlight = searchStr ? false : true;
                let rows = null;
                if(pick.name === "MapStone") {
                    rows = picks_by_type["MP"].map((ms) => {
                        let cols = Object.keys(placements).map((pid) => {
                            if(!placements[pid][ms.loc])
                                return null
                            if(!highlight && searchStr && is_match(placements[pid][ms.loc], searchStr))
                                highlight = true
                            return (
                                <td style={{color:'black'}}>
                                ({pid}) {placements[pid][ms.loc].label}
                                </td>
                            )
                        });
                        return (
                        <tr><td style={{color:'black'}}>{ms.area} :</td>
                        {cols}
                        </tr>
                        )
                    });
                } else {
                      rows = Object.keys(placements).map((pid) => {
                        if(!highlight && searchStr && placements[pid][pick.loc] && is_match(placements[pid][pick.loc], searchStr))
                            highlight = true
                          return (
                            <tr><td style={{color:'black'}}>
                                  {pid}: {placements[pid][pick.loc] ? placements[pid][pick.loc].label : ""}
                            </td></tr>
                          )
                      });
                }
                let inner = (
                    <Tooltip>
                        <table>{rows}</table>
                    </Tooltip>
                );
                let opacity = highlight ? 1  : hide_opacity
                let name = pick.name+"("+pick.x + "," + pick.y +")"
                let onclick = setSelected({label: name, value: pick})
                markers.push({key: name, position: [y, x], inner: inner, icon: icon, opacity: opacity, onClick: onclick});
            }

        });
    });
    return markers
};

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
  let i = 0, j = 0, temp = null;

  for (i = array.length - 1; i > 0; i -= 1) {
    j = Math.floor(Math.random() * (i + 1))
    temp = array[i]
    array[i] = array[j]
    array[j] = temp
  }
}

function get_manual_reach() {
    let HC = get_int("HC", 0);
    let EC = get_int("EC", 0);
    let KS = get_int("KS", 0);
    let MS = get_int("MS", 0);
    let AC = get_int("AC", 0);
    let skills = get_list("SK"," ").map(skill => { let parts = skill.split("|"); return {label: pickup_name(parts[0], parts[1]), value: skill}; });
    let events = get_list("EV"," ").map(event => { let parts = event.split("|"); return {label: pickup_name(parts[0], parts[1]), value: event}; });
    let tps  = get_list("TP"," ").map(tp => {return {label: tp + " TP", value: "TP|" + tp}; });
    return {HC: HC, EC: EC, AC: AC, KS: KS, MS: MS, skills: skills, tps: tps, events: events};
}

class PlandoBuiler extends React.Component {
  constructor(props) {
    super(props)

    this.state = {seed_in: "", reachable: {...DEFAULT_REACHABLE}, new_areas: {...DEFAULT_REACHABLE}, placements: {1: {...DEFAULT_DATA}}, player: 1, saving: false,
                  fill_opts: {HC: 13, EC: 15, AC: 34, KS: 40, MS: 9, EX: 300, ex_pool: 10000, dynamic: false, dumb: false}, viewport: {center: [0, 0], zoom: 5}, searchStr: "", clueOrder: CLUE_ORDERS[0],
                  flags: ['hide_unreachable', 'hide_softlockable'], seedFlags: select_wrap(["ForceTrees"]), share_types: select_wrap(["keys"]), coop_mode: {label: "Solo", value: "None"},
                  pickups: ["EX", "Ma", "HC", "SK", "Pl", "KS", "MS", "EC", "AC", "EV", "CS"], display_fill: false, display_import: false, display_logic: false, display_coop: false, display_meta: false}
    }


     componentWillMount() {
        let pathmode = get_param("pathmode");
        let manual_reach = get_manual_reach();
        let logicMode, modes;
    
        if(pathmode && paths.includes(pathmode)) {
            logicMode = 'manual';
            modes = presets[pathmode];
        } else {
            pathmode = "standard";
            logicMode = "auto";
            modes = presets["standard"];
        }
        let zone = 'Glades';
        let lastSelected = {};
        zones.forEach((zone) => {
            let pick = picks_by_zone[zone][0];
            lastSelected[zone] = {label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}
        });
        // i hate this
        picks_by_zone['Glades'].push({"loc": 2, "name": "SPAWN", "zone": "Glades", "area": "FirstPickup", "x": 189, "y": -210})
        picks_by_area['FirstPickup'].push({"loc": 2, "name": "SPAWN", "zone": "Glades", "area": "FirstPickup", "x": 189, "y": -210})
        picks_by_loc[2] = {"loc": 2, "name": "SPAWN", "zone": "Glades", "area": "FirstPickup", "x": 189, "y": -210}

        let pick = {loc: 919772, name: "EX15", zone: "Glades", area: "FirstPickup", y: -227, x: 92};
        let pickup = {label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}
        lastSelected['Glades'] = pickup
    
        this.setState({mousePos: {lat: 0, lng: 0}, zone: zone, pickup: pickup, modes: modes, lastSelected: lastSelected, logicMode: logicMode, pathMode: pathmode,
                      manual_reach: manual_reach, stuff: {value: "NO|1", label: "Nothing"}, authed: get_flag("authed")})
    
    };

    componentDidMount() {
        setTimeout(() => {
            this.refs.map.leafletElement.invalidateSize(false);
            this.setState({viewport: DEFAULT_VIEWPORT});
        }, 100);
        if(this.state.authed)
        {
            let {seedJson, seed_name, seed_desc, user} = get_seed()
            this.setState({seed_name: seed_name, last_seed_name: seed_name, seed_desc: seed_desc, user: user})
            if(seedJson)
                this.parseSavedSeed(seedJson)
        }
        this.updateReachable()
    };

    onSelectZone = (newZone, pan=true) => {this.selectPickup(this.state.lastSelected[newZone.value], pan)};
    onPathModeChange = (n) => this.setState({modes: presets[n.value], pathMode: n.value}, this.updateReachable)
    onMode = (m) => () => this.setState(prevState => {
        let modes = prevState.modes;
        if(modes.includes(m)) {
            modes = modes.filter(x => x !== m)
        } else {
            modes.push(m)
        }
    return {modes: modes, pathMode: get_preset(modes)}}, this.updateReachable)


    logicModeChanged = (newVal) => { this.setState({logicMode: newVal}, this.updateReachable) }
    autoLogicToggle = () => this.state.logicMode === "auto" ? this.logicModeChanged("manual") : this.logicModeChanged("auto")

    updateManual = (param,val) => this.setState(prevState => {
        let manual_reach = this.state.manual_reach;
        manual_reach[param] = val;
        return {manual_reach: manual_reach}
    },() => this.updateReachable());


    updateFill = (param,val) => this.setState(prevState => {
        let fill_opts = prevState.fill_opts;
        fill_opts[param] = val;
        return {fill_opts: fill_opts}
    });
      flagsChanged = (newVal) => this.setState({flags: newVal});



    selectPickup = (pick, pan=true) => {
        let last = this.state.lastSelected;
        let newStuff = this.state.placements[this.state.player][pick.value.loc];
        last[pick.value.zone] = pick;
        let viewport = this.state.viewport;
        if(pan) {
            let {x, y} = pick.value
            viewport = {
                  center: [y, x],
                  zoom: 5,
                }
        }
        if(!newStuff || !newStuff.hasOwnProperty("value")) {
            this.setState({pickup: pick, zone: pick.value.zone, lastSelected: last, viewport: viewport}, () => this.place(this.state.stuff));
        } else {
            this.setState({pickup: pick, zone: pick.value.zone, lastSelected: last, viewport: viewport, stuff: newStuff}, () => this.refs.pickupSelect.valFromStr(newStuff.value, true));
        }
    }

    selectPickupCurry = (pick) => {
        if(pick.value.name === "MapStone")
            return () => this.onSelectZone({value: "Mapstone"}, false)
        else
            return () => this.selectPickup(pick)
    }


    place = (s) => {
        if(s.value.length < 4 || s.value[2] !== "|") {
            NotificationManager.warning("Pickup should be in the form XX|Y", "Invalid Pickup!", 1000);
            this.setState({stuff: s});
            return;
        }
        let reserved_chars = ["|"];
        let stuff_id = s.value.substr(3);
        if(reserved_chars.some(c => stuff_id.includes(c))) {
            NotificationManager.warning("'" + stuff_id + "' contains a forbidden character", "Invalid Id!", 1000);
            this.setState({stuff: s});
            return;
        }

        let r = relevantCodes.includes(this.state.stuff.value.substr(0,2)) ? {...DEFAULT_REACHABLE} : this.state.reachable;
        this.setState(prevState => {
            let plc = prevState.placements;
            // i hate this i hate this i hate this
            if((s.value.substr(0,2) === "EX") && !s.label.endsWith("Experience"))
            {
                let new_s = {...s}
                new_s.label += " Experience"
                plc[prevState.player][prevState.pickup.value.loc] = new_s;
            } else 
                plc[prevState.player][prevState.pickup.value.loc] = s;
            return {placements: plc, stuff: s, reachable: r};
        }, () => this.updateReachable());
    };

    parseUploadedSeed = (seedText) => {
        let lines = seedText.split("\n")
        let newplc = {}
        let newClueOrder = []
        let currplc = this.state.placements[this.state.player]
        for (let i = 1, len = lines.length; i < len; i++) {
            let line = lines[i].split("|")
            let loc = parseInt(line[0], 10);
            if(currplc.hasOwnProperty(loc) && currplc[loc].value !== "NO|1")
            {
                newplc[loc] = currplc[loc];
                continue;
            }
            let code = line[1];
            let id = str_ids.includes(code) ? line[2] : parseInt(line[2], 10);
            if(code === "EX" && this.state.seedFlags.some(f => f.value === "NoExtraExp"))
                id = 0
            if(code === "EV" && id % 2 === 0){
                newClueOrder.push(`${code}|${id}`)
            }
            let name = pickup_name(code, id);
            let stuff = {label: name, value:code+"|"+id};
            newplc[loc] = stuff;
            if(loc === this.state.pickup.value.loc)
                this.setState({stuff: stuff});
        }
        this.parseFlagLine(lines[0])
        this.setState(prevState => {
                let retVal = {}
                retVal.placements = prevState.placements;
                retVal.placements[prevState.player] = newplc
                if(newClueOrder.length === 3) 
                    retVal.clueOrder = {value: newClueOrder, label: mkClueOrderLabel(newClueOrder)}
                return retVal
            }, () => this.updateReachable());

    }


    parseSavedSeed = (seedJson) => {
        // help
        let newClueOrder = []
        let seedData = JSON.parse(he.decode(seedJson))
        let placements = {}
        seedData['placements'].forEach(placement => {
            let loc = parseInt(placement['loc'], 10);
            placement['stuff'].forEach(stuff => {
                let code = stuff['code']
                let id = str_ids.includes(code) ? stuff['id'] : parseInt(stuff['id'], 10);
                if(code === "EV" && id % 2 === 0){
                    newClueOrder.push(`${code}|${id}`)
                }
                let name = pickup_name(code, id);
                let stuff_obj = {label: name, value: code+"|"+id};
                let player = stuff['player']
                if(!placements.hasOwnProperty(player))
                    placements[player] = {}
                placements[player][loc] = stuff_obj
                if(loc === this.state.pickup.value.loc && player === "1")
                    this.setState({stuff: stuff_obj});
            })
        })
        this.parseFlagLine(seedData['flagline'])
        let retVal = {}
        retVal.placements = placements;
        if(newClueOrder.length === 3) 
            retVal.clueOrder = {value: newClueOrder, label: mkClueOrderLabel(newClueOrder)}
        this.setState(retVal, () => this.updateReachable());
        this.setState({placements: placements}, () => this.updateReachable());


    }

    parseFlagLine = (flagLine) => {
        let seedFlags = this.state.seedFlags.map(f => f.value)
        let coop_mode = this.state.coop_mode
        let share_types = this.state.share_types
        let display_coop = this.state.display_coop
        let [flags,seed_name] = flagLine.split("|")
        if(this.state.seed_name) // don't overwrite name on upload
            seed_name = this.state.seed_name
        flags.split(",").forEach((flag) => {
            if(SEED_FLAGS.includes(flag) && !seedFlags.includes(flag))
                seedFlags.push(flag)
            else if(flag.startsWith("mode="))
            {
                let k=flag.substring(5)
                coop_mode={label: modes_by_key[k], value: k}
            }
            else if(flag.startsWith("shared="))
            {
                display_coop = true
                share_types=select_wrap(flag.substring(7).split("+").filter((id) => SHARE_TYPES.includes(id)))
            }
        });
        this.setState({seedFlags: select_wrap(seedFlags), share_types: share_types, coop_mode: coop_mode, display_coop: display_coop, seed_name: seed_name})
    }

    buildFlagLine = () => {
        let flags = this.state.seedFlags.map(f => f.value)
        if(this.state.coop_mode.value !== "None")
        {
            if(this.state.coop_mode.value === "Shared")
            {
                let stypes = this.state.share_types.map(f => f.value)
                if(stypes.length)
                    flags.push("shared="+stypes.join("+"))
            }
            flags.push("mode="+this.state.coop_mode.value)
        }
        return flags.join(",") + "|" + this.state.seed_name
    }


    doFill  = () => {
        let players = Object.keys(this.state.placements);
        let newPlc = {...this.state.placements}
        let locs = Object.keys(picks_by_loc)
        players.forEach(player => {
            let toFill = []
            let {HC, EC, AC, KS, MS, EX} = this.state.fill_opts
            locs.forEach((loc) => {
                if(!this.state.placements[player].hasOwnProperty(loc))
                    toFill.push(loc);
            });
            shuffle(toFill);
            toFill.forEach(loc => {
                if(HC > 0) {
                    HC -= 1;
                    newPlc[player][loc] = {label: "Health Cell", value: "HC|1"}
                }
                else if(EC > 0) {
                    EC -= 1;
                    newPlc[player][loc] = {label: "Energy Cell", value: "EC|1"}
                }
                else if(AC > 0) {
                    AC -= 1;
                    newPlc[player][loc] = {label: "Ability Cell", value: "AC|1"}
                }
                else if(KS > 0) {
                    KS -= 1;
                    newPlc[player][loc] = {label: "Keystone", value: "KS|1"}
                }
                else if(MS > 0) {
                    MS -= 1;
                    newPlc[player][loc] = {label: "Mapstone", value: "MS|1"}
                }
                else
                {
                    let xp = Math.floor(Math.random() * (EX-1) + 1)
                    newPlc[player][loc] = {label: xp + " Experience", value: "EX|"+xp}
                }
            });
        })
        this.setState({placements: newPlc})
    }

    getLines = () => {
        let playerPlacements = this.state.placements[this.state.player] || {}
        let outLines = [this.buildFlagLine()]
        let locs = Object.keys(picks_by_loc).filter(loc => playerPlacements.hasOwnProperty(loc))
        let evLines = {};
        locs.forEach((loc) => {
            let lineText = loc+"|"+playerPlacements[loc].value+"|"+picks_by_loc[loc].zone;
            if(DUNGEON_KEYS.includes(playerPlacements[loc].value))
                evLines[playerPlacements[loc].value] = (lineText)
            else
                outLines.push(lineText)
        })
        this.state.clueOrder.value.forEach(ev => evLines.hasOwnProperty(ev) ? outLines.push(evLines[ev]) : null)
        return outLines;
    }


    getUploadData = () => {
        let data = {}
        data.flagLine = this.buildFlagLine()
        data.name = this.state.seed_name
        data.oldName = this.state.last_seed_name
        data.desc = this.state.seed_desc
        data.sharedMode = this.state.coop_mode.value
        data.shareTypes = this.state.share_types.map(f => f.value)
        data.flags = this.state.seedFlags.map(f => f.value);
        data.placements = [];
        let locs = Object.keys(picks_by_loc);
        let players = Object.keys(this.state.placements);
        let evStuff = {};
        locs.forEach(loc => {
            let players_at_loc = players.filter(p => this.state.placements[p].hasOwnProperty(loc))
            let keyName = "";
            let stuff = players_at_loc.map(player => {
                let rawId = this.state.placements[player][loc].value
                let [code, id] = rawId.split("|");
                if(DUNGEON_KEYS.includes(rawId)) {
                    keyName = rawId;
                }
                return {player: player, code: code, id: id};
            })
            if(players_at_loc.length > 0){
                let plcmnt = {loc: loc, zone: picks_by_loc[loc].zone, stuff: stuff};
                if(keyName !== "" && !evStuff.hasOwnProperty(keyName))
                    evStuff[keyName] = plcmnt
                 else 
                    data.placements.push(plcmnt)                
            }
        })
        this.state.clueOrder.value.forEach(ev => evStuff.hasOwnProperty(ev) && data.placements.push(evStuff[ev]))

        return data;
    }

    doFillGen = () => {
        var xmlHttp = new XMLHttpRequest();
        var parser = this.parseUploadedSeed;
        xmlHttp.onreadystatechange = function() {
            if (xmlHttp.readyState === 4)
                (function(res) {
                    if(xmlHttp.status !== 200)
                        NotificationManager.error("Unfinishable Seed", "Failed to complete seed using seedgen", 4000);
                    else
                        parser(res);
                })(xmlHttp.responseText);
        }
          let codes = []; 
          Object.keys(this.state.reachable).forEach((area) => {
              if(picks_by_area.hasOwnProperty(area))
                  picks_by_area[area].forEach((pick) => {
                      if(this.state.placements[this.state.player] && this.state.placements[this.state.player].hasOwnProperty(pick.loc)) 
                          codes.push(pick.loc+":"+this.state.placements[1][pick.loc].value.replace("|",""));
                  });
          });

        let mode = "";
        let urlParams = [];
        this.state.modes.forEach(p => urlParams.push(`path=${p}`));
        urlParams.push(`exp_pool=${this.state.fill_opts.ex_pool}`)

        this.state.seedFlags.forEach(f => {
            let flag = FLAG_CASEFIX[f.value.toLowerCase()] || f.value
            if(VALID_KEYMODES.includes(flag)) mode = flag
            else if(VALID_VARS.includes(flag)) urlParams.push(`var=${flag}`)
            else urlParams.push(`flag=${flag}`)
        });
        if(mode) urlParams.push(`key_mode=${mode}`)
        if(codes.length > 0)
            urlParams.push(`fass=${codes.join("|")}`);
        urlParams.push("tracking=Disabled");
        urlParams.push(`seed=${Math.round(Math.random() * 1000000000)}`);
        let url = `/plando/fillgen?${urlParams.join("&")}`;
        xmlHttp.open("GET", url, true);
        xmlHttp.send(null);
    }


    saveSeed = () => {
        uploadSeed(this.getUploadData(), this.saveCallback)
    }

    saveCallback = (statusCode) => {
        if(statusCode === 200)
        {
            if(this.state.last_seed_name !== this.state.seed_name)
            {
                let new_url = window.document.URL.replace(this.state.last_seed_name, this.state.seed_name);
                window.history.replaceState('',window.document.title, new_url);
                this.setState({last_seed_name: this.state.seed_name})
            }
            this.toggleMeta()
            NotificationManager.success("Seed saved", "Success!", 2500);
        }
        else if(statusCode === 404)
            NotificationManager.error("Invalid name", "Failed to save seed!", 4000);
        else if(statusCode >= 500)
            NotificationManager.error("Server error", "Failed to save seed!", 4000);
        else 
            NotificationManager.error("Unknown error", "Failed to save seed!", 4000);
        this.setState({saving: false})
        
    }

    downloadSeed = () => {
        download('randomizer.dat', this.getLines().join("\n"));
    }

      updateReachable = (lastPass=[]) => {
          let recursive = true
          if(!this.state.flags.includes("hide_unreachable"))
              return
          if(!this.state.reachable || this.state.reachable === undefined) {
              this.setState({reachable: {...DEFAULT_REACHABLE}}, () => this.updateReachable());
              return
          }
        let reachableAreas = Object.keys(this.state.reachable)
        
        // if we've seen every area we can reach in our last iteration, halt
        if(reachableAreas.every(area => lastPass.includes(area)))
            return

          let reachableStuff = {};
          if(this.state.logicMode === "auto" && this.state.player === 1)
          {
              reachableAreas.forEach((area) => {
                  if(picks_by_area.hasOwnProperty(area))
                      picks_by_area[area].forEach((pick) => {
                      if(this.state.placements[1] && this.state.placements[1].hasOwnProperty(pick.loc)) {
                          let code = this.state.placements[1][pick.loc].value;
                          if(!["SH", "NO", "EX"].includes(code.substr(0,2)))
                              if(reachableStuff.hasOwnProperty(code))
                                reachableStuff[code] += 1;
                            else
                                reachableStuff[code] = 1;
                          }
                      });
              });
        } else {
            ["HC", "EC", "KS", "MS", "AC"].forEach((code) => {
                if(this.state.manual_reach[code] > 0)
                    reachableStuff[code+"|1"] = this.state.manual_reach[code];
            });
            this.state.manual_reach.skills.forEach(skill => {
                reachableStuff[skill.value] = 1;
              });
            this.state.manual_reach.events.forEach(event => {
                reachableStuff[event.value] = 1;
              });
            this.state.manual_reach.tps.forEach(tp => {
                reachableStuff[tp.value] = 1;
              });
              recursive = false
          }
            let modes = [...this.state.modes]
            let flags = this.state.seedFlags.map(f => f.value)
            if(flags.includes("ClosedDungeon")) 
                modes.push("CLOSED_DUNGEON")
            if(flags.includes("OpenWorld")) 
                modes.push("OPEN_WORLD")


            getReachable((s, c) => this.setState(s, c), reachableStuff, modes, recursive ? () => this.updateReachable(reachableAreas) : () => null);
      };
      
    toggleImport = () => {
        if(dev)
            console.log(this.state)
        this.setState({display_import: !this.state.display_import})
    };
    toggleLogic = () => {this.setState({display_logic: !this.state.display_logic})};
    toggleCoop = () => {this.setState({display_coop: !this.state.display_coop})};
    toggleMeta = () => {this.setState({display_meta: !this.state.display_meta})};
    addPlayer = () => {
        this.setState(prevState => {
            let newPlc = prevState.placements;
            let players = Object.keys(newPlc).length;
            newPlc[players+1] = {...DEFAULT_DATA}
            return {placements: newPlc, player: players+1}
        })
    }
    dupePlayer = () => {
        this.setState(prevState => {
            let newPlc = prevState.placements;
            let players = Object.keys(newPlc).length;
            newPlc[players+1] = {...newPlc[prevState.player]}
            return {placements: newPlc, player: players+1}
        })
    }
    removePlayer = () => {
        if(Object.keys(this.state.placements).length > 1)
            this.setState(prevState => {
                let newPlc = {};
                let to_delete = prevState.player;
                Object.keys(prevState.placements).forEach((pid) => {
                    if(pid < to_delete)
                        newPlc[pid] = prevState.placements[pid]
                    if(pid > to_delete)
                        newPlc[pid-1] = prevState.placements[pid]
                });
                return {placements: newPlc, player: 1}
            })
    }
    
    resetReachable = () => this.setState({reachable: {...DEFAULT_REACHABLE}})
    
    onFlags = (n) => this.setState({seedFlags: select_wrap(n.map(flag => FLAG_CASEFIX[flag.value.toLowerCase()] || flag.value))}, this.updateReachable)


    render() {
        let {clueOrder, modes, searchStr, seedFlags, authed} = this.state;
        let page = encodeURIComponent(window.document.URL.split(".com")[1])
        const pickup_markers = ( <PickupMarkersList markers={getPickupMarkers(this.state, this.selectPickupCurry, searchStr)} />)
        const zone_opts = zones.map(zone => ({label: zone, value: zone}))
        const pickups_opts = picks_by_zone[this.state.zone].map(pick => ({label: pick.name+"("+pick.x + "," + pick.y +")",value: pick}) )
        let clue_order_picker = seedFlags.map(f => f.value).includes("Clues") ? (
            <div className="pickup-wrapper">
                <span className="label">Clue Order: </span>
                <Select styles={select_styles} options={CLUE_ORDERS} onChange={(n) => this.setState({clueOrder: n})} clearable={false} value={clueOrder}/>
            </div>
        ) : null
        let alert = authed ? null : (<Alert color="danger">Please <a href={`/login?redir=${page}`}>login</a> to enable saving.</Alert>)
        let save_if_auth = authed ? ( <Button color="primary" onClick={this.toggleMeta} >Meta/Save</Button> ) : (<Button color="disabled">Meta/Save</Button>)
        let fill_button = this.state.fill_opts.dumb ? (
            <Button color="warning" onClick={this.doFill} >Fill (Dumb)</Button>
        ) : (
            <Button color="success" onClick={this.doFillGen} >Fill</Button>
        )
        let logic_path_buttons = logic_paths.map(lp => {return (<Col className="pr-0" xs="4"><Button block size="sm" outline={!modes.includes(lp)} onClick={this.onMode(lp)}>{lp}</Button></Col>)});
        return (
            <div className="wrapper">
                <NotificationContainer/>
                <Helmet>
                    <style>{'body { background-color: black}'}</style>
                    <link rel="stylesheet" href="https://gitcdn.github.io/bootstrap-toggle/2.2.2/css/bootstrap-toggle.min.css"/>
                    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.3.1/dist/leaflet.css" integrity="sha512-Rksm5RenBEKSKFjgI3a41vrjkw4EVPlJ3+OiI65vTjIdo9brlAacEuKOiQ5OFh7cOI1bkDwLqdLw3Zg0cRJAAQ==" crossorigin=""/>
                </Helmet>

                <Map ref="map" crs={crs} onMouseMove={(ev) => this.setState({mousePos: ev.latlng})} zoomControl={false} onViewportChanged={this.onViewportChanged} viewport={this.state.viewport}>
                    <ZoomControl position="topright" />
                    <Control position="topleft" >
                    <div>
                        <Button size="sm" color="disabled">{Math.round(this.state.mousePos.lng)},{Math.round(this.state.mousePos.lat)}</Button>
                    </div>
                    </Control>    
                    <TileLayer url=' https://ori-tracker.firebaseapp.com/images/ori-map/{z}/{x}/{y}.png' noWrap='true'  />
                    {pickup_markers}
                </Map>
                <div className="controls">
                {alert}
                    <div id="file-controls">
                        <Button color="primary" onClick={this.toggleImport} >Import</Button>
                        {fill_button}
                        <Button color="primary" onClick={this.downloadSeed} >Download</Button>
                        {save_if_auth}
                    </div>
                    <Collapse id="import-wrapper" isOpen={this.state.display_meta}>
                        <textarea id="seed-name-input" className="form-control" value={this.state.seed_name} onChange={event => this.setState({seed_name: event.target.value})} />
                        <textarea id="seed-desc-input" className="form-control" placeholder="Seed Description" value={this.state.seed_desc} onChange={event => this.setState({seed_desc: event.target.value})} />
                        <Button color="primary" onClick={this.saveSeed} >Save</Button>
                        <Button color="primary" onClick={() => window.open(`/plando/${this.state.user}/${this.state.last_seed_name}/`,'_blank') } >Open Seed Page</Button>
                    </Collapse>
                    <Collapse id="import-wrapper" isOpen={this.state.display_import}>
                        <textarea id="import-seed-area" className="form-control" placeholder="Paste Seed Here" value={this.state.seed_in} onChange={event => {this.parseUploadedSeed(event.target.value) ; this.toggleImport() }} />
                    </Collapse>
                    <hr style={{ backgroundColor: 'grey', height: 2 }}/>
                    <div id="pickup-controls">
                        <div className="pickup-wrapper">
                            <span className="label">Seed Flags: </span>
                            <Creatable styles={select_styles} options={select_wrap(SEED_FLAGS)} onChange={this.onFlags} isMulti={true} value={this.state.seedFlags} label={this.state.seedFlags}/>
                        </div>
                        {clue_order_picker}
                    </div>
                    <hr style={{ backgroundColor: 'grey', height: 2 }}/>
                    <div id="pickup-controls">
                         <div className="pickup-wrapper">
                            <span className="label">Zone:</span>
                            <Select styles={select_styles} options={zone_opts} onChange={this.onSelectZone} clearable={false} value={select_wrap(this.state.zone)}></Select>
                        </div>
                        <div className="pickup-wrapper">
                            <span className="label">Location: </span>
                            <Select styles={select_styles} options={pickups_opts} onChange={this.selectPickup} clearable={false} value={this.state.pickup} label={this.state.pickup.name+"("+this.state.pickup.x + "," + this.state.pickup.y +")"}></Select>
                        </div>
                        <div className="pickup-wrapper">
                            <PickupSelect ref="pickupSelect" value={this.state.stuff.value} updater={(code, name) => this.place({label: name, value: code})}/>
                        </div>
                        <Button onClick={() => this.setState(prev => ({display_fill: !prev.display_fill}))}>Show Fill</Button>
                        <Collapse isOpen={this.state.display_fill}>
                            <div id="fill-params">
                                <div className="fill-wrapper">
                                    <span className="label">Health Cells:</span>
                                    <NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.HC} onChange={(n) => this.updateFill("HC",n)}></NumericInput>
                                    <span className="label">Energy Cells:</span>
                                    <NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.EC} onChange={(n) => this.updateFill("EC",n)}></NumericInput>
                                </div>
                                <div className="fill-wrapper">
                                    <span className="label">Ability Cells:</span>
                                    <NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.AC} onChange={(n) => this.updateFill("AC",n)}></NumericInput>
                                    <span className="label">Keystones:</span>
                                    <NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.KS} onChange={(n) => this.updateFill("KS",n)}></NumericInput>
                                </div>
                                <div className="fill-wrapper">
                                    <span className="label">Mapstones:</span>
                                    <NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.MS} onChange={(n) => this.updateFill("MS",n)}></NumericInput>
                                    <span className="label">Max EXP: </span>
                                    <NumericInput min={0} disabled={!this.state.fill_opts.dumb} value={this.state.fill_opts.EX} onChange={(n) => this.updateFill("EX",n)}></NumericInput>
                                    <span className="label">EXP Pool: </span>
                                    <NumericInput min={0} disabled={this.state.fill_opts.dumb} value={this.state.fill_opts.ex_pool} onChange={(n) => this.updateFill("ex_pool",n)}></NumericInput>
                                </div>
                                <div className="form-check-label">
                                    <label className="form-check-label"><input type="checkbox" checked={this.state.fill_opts.dynamic} onChange={() => this.updateFill("dynamic",!this.state.fill_opts.dynamic)}/>Update Automatically</label>
                                    <label className="form-check-label"><input type="checkbox" checked={this.state.fill_opts.dumb} onChange={() => this.updateFill("dumb",!this.state.fill_opts.dumb)}/>Enable Dumb Fill</label>
                                </div>
                            </div>
                        </Collapse>
                    </div>
                    <hr style={{ backgroundColor: 'grey', height: 2 }}/>
                    <div id="display-controls">
                        <CheckboxGroup id="display-flags" checkboxDepth={6} name="flags" value={this.state.flags} onChange={this.flagsChanged}>
                            <label className="form-check-label"><Checkbox value="hide_unreachable" />Hide Unreachable</label>
                            <label className="form-check-label"><Checkbox value="hide_assigned" />Hide Assigned</label>
                            <label className="form-check-label"><Checkbox value="hide_softlockable" />Hide Dangerous</label>
                        </CheckboxGroup>
                    <hr style={{ backgroundColor: 'grey', height: 2 }}/>
                        <div id="search-wrapper">
                            <label for="search">Search</label>
                            <input id="search" class="form-control" value={this.state.searchStr} onChange={(event) => this.setState({searchStr: event.target.value})} type="text" />
                        </div>
                    </div>
                    <hr style={{ backgroundColor: 'grey', height: 2 }}/>
                    <div id="logic-controls">
                        <div id="logic-mode-wrapper">
                            <span className="label">Automatic Logic:</span>
                            <Toggle
                              onClick={this.autoLogicToggle}
                              on="Enabled"
                              off="Disabled"
                              size="xs"
                              onstyle="primary"
                              offstyle="secondary"
                              active={this.state.logicMode === "auto" && Object.keys(this.state.placements).length === 1}
                              disabled={Object.keys(this.state.placements).length > 1}
                            />
                            <Collapse id="manual-controls" isOpen={this.state.logicMode === "manual" || this.state.player > 1}>
                                <div className="manual-wrapper">
                                    <span className="label">Health Cells:</span>
                                    <NumericInput min={0} value={this.state.manual_reach.HC} onChange={(n) => this.updateManual("HC",n)}></NumericInput>
                                </div>
                                <div className="manual-wrapper">
                                    <span className="label">Energy Cells:</span>
                                    <NumericInput min={0} value={this.state.manual_reach.EC} onChange={(n) => this.updateManual("EC",n)}></NumericInput>
                                </div>
                                <div className="manual-wrapper">
                                    <span className="label">Keystones:</span>
                                    <NumericInput min={0} value={this.state.manual_reach.KS} onChange={(n) => this.updateManual("KS",n)}></NumericInput>
                                </div>
                                <div className="manual-wrapper">
                                    <span className="label">Mapstones:</span>
                                    <NumericInput min={0} value={this.state.manual_reach.MS} onChange={(n) => this.updateManual("MS",n)}></NumericInput>
                                </div>
                                <div className="manual-wrapper">
                                    <Select styles={select_styles} placeholder="Skills" options={stuff_by_type["Skills"]} onChange={(n) => this.updateManual("skills", n)} isMulti={true} value={this.state.manual_reach.skills}></Select>
                                </div>
                                <div className="manual-wrapper">
                                    <Select styles={select_styles} placeholder="Teleporters" options={stuff_by_type["Teleporters"]} onChange={(n) => this.updateManual("tps", n)} isMulti={true} value={this.state.manual_reach.tps}></Select>
                                </div>
                                <div className="manual-wrapper">
                                    <Select styles={select_styles} placeholder="Events" options={stuff_by_type["Events"]} onChange={(n) => this.updateManual("events", n)} isMulti={true} value={this.state.manual_reach.events}></Select>
                                </div>
                            </Collapse>
                        </div>
                        <hr style={{ backgroundColor: 'grey', height: 2 }}/>
                        <div id="logic-mode-controls">
                            <div id="logic-presets">
                                <Button color="primary" onClick={this.toggleLogic} >Logic Paths:</Button>
                                <Select styles={select_styles} options={select_wrap(paths)} onChange={this.onPathModeChange} clearable={false} value={select_wrap(this.state.pathMode)}></Select>
                            </div>
                            <Collapse id="logic-options-wrapper" isOpen={this.state.display_logic}>
                                <Container>
                                <Row className="p-1">
                                    {logic_path_buttons}
                                </Row>
                                </Container>
                            </Collapse>
                        </div>
                    </div>
                    <div id="coop-controls">
                        <div className="basic-coop-options">
                            <Button color="primary" onClick={this.toggleCoop}>Multiplayer Controls</Button>
                            <span className="label">Player: </span>
                            <Select styles={select_styles}  options={select_wrap(Object.keys(this.state.placements))} onChange={(n) => this.setState({player: n.value})} clearable={false} value={select_wrap(this.state.player)} label={this.state.player}></Select>
                        </div>
                        <Collapse id="coop-wrapper" isOpen={this.state.display_coop}>
                             <div className="coop-select-wrapper">
                                <span className="label">Mode: </span>
                                <Select styles={select_styles}   options={COOP_MODES} onChange={(n) => this.setState({coop_mode: n})} clearable={false} value={this.state.coop_mode}></Select>
                            </div>
                             <div className="coop-select-wrapper">
                                <span className="label">Shared: </span>
                                <Select styles={select_styles}   options={select_wrap(SHARE_TYPES)} onChange={(n) => this.setState({share_types: n})} clearable={false} isMulti={true} value={this.state.share_types}></Select>
                            </div>
                            <div>
                                <Button color="primary" onClick={this.addPlayer}>Add Player</Button>
                                <Button color="primary" onClick={this.dupePlayer}>Duplicate</Button>
                                <Button color="secondary" onClick={this.removePlayer} active={Object.keys(this.state.placements).length > 1}>Remove Player</Button>
                            </div>
                        </Collapse>
                    </div>
                </div>
            </div>
        )
    }
}

function getReachable(setter, inventory, modes, callback)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState === 4 && xmlHttp.status === 200)
            (function(res) {
                    let new_reachables = JSON.parse(res);
                    setter(prevState => {
                        let reachable = prevState.reachable;
                        Object.keys(new_reachables).forEach((area) => {
                            if(!reachable.hasOwnProperty(area))
                                reachable[area] = new_reachables[area];
                            reachable[area] = reachable[area].concat(new_reachables[area]);

                        });
                        return {reachable: reachable}
                    }, callback)
            })(xmlHttp.responseText);
    }
    xmlHttp.open("POST", "/plando/reachable", true);
    xmlHttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    xmlHttp.send(encodeURI(`inventory=${JSON.stringify(inventory)}&modes=${JSON.stringify(modes)}`));
}



function uploadSeed(seedData, callback)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState === 4)
            callback(xmlHttp.status)
    }
    let url = "/plando/"+seedData.name+"/upload";
    xmlHttp.open("POST", url, true);
    xmlHttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    xmlHttp.send(encodeURI("seed="+JSON.stringify(seedData)));
}


export default PlandoBuiler;
