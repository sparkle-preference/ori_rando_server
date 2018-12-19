import React, { Component, Fragment } from 'react';
import Leaflet from 'leaflet';
import {
    BeatLoader, BounceLoader, CircleLoader, ClipLoader, ClimbingBoxLoader, DotLoader, GridLoader, HashLoader, MoonLoader,
    PacmanLoader, PulseLoader, RingLoader, RiseLoader, RotateLoader, SyncLoader, FadeLoader, ScaleLoader
} from 'react-spinners';
import { Badge } from 'reactstrap';
import CreatableSelect from 'react-select/lib/Creatable';
import { colors } from 'react-select/lib/theme';


function name_from_str(pick) {
    if(!pick)
        return ""
    let parts = pick.split("|");
    return pickup_name(parts[0], parts[1])
}

function pickup_name(code, id) {
    let upgrade_names = {};
    stuff_by_type["Upgrades"].forEach(s => {
        upgrade_names[s.value.substr(3)] = s.label;
    });
    let names = {
        "SK": { 0: "Bash", 2: "Charge Flame", 3: "Wall Jump", 4: "Stomp", 5: "Double Jump", 8: "Charge Jump", 12: "Climb", 14: "Glide", 15: "Spirit Flame", 50: "Dash", 51: "Grenade" },
        "EV": { 0: "Water Vein", 1: "Clean Water", 2: "Gumon Seal", 3: "Wind Restored", 4: "Sunstone", 5: "Warmth Returned" },
        "RB": upgrade_names,
    };
    if (names.hasOwnProperty(code) && names[code][id])
        return names[code][id];
    switch (code) {
        case "MU":
        case "RP":
            let parts = id.split("/");
            let names = [];
            while (parts.length > 1) {
                names.push(pickup_name(parts.shift(), parts.shift()))
            }
            if (code === "RP")
                return "Repeatable: " + names.join(", ")
            return names.join(", ")
        case "TP":
            return id + "TP";
        case "EX":
            return id + " Experience";
        case "HC":
            return "Health Cell";
        case "AC":
            return "Ability Cell";
        case "EC":
            return "Energy Cell";
        case "KS":
            return "Keystone";
        case "MS":
            return "Mapstone";
        case "SH":
            return 'Print "' + id + '"';
        case "WT":
            return "Relic: " + id;
        case "HN":
            let hintParts = id.split('-');
            if (hintParts.length > 2)
                return "Hint: " + hintParts[1] + " for " + hintParts[2];
            else
                return "Hint"
        case "WS":
        case "WP":
            return "Warp to " + id + (code === "WS" ? " and save" : "")
        case "NO":
            return "Nothing"
        default:
            return code + "|" + id;
    }

}

const stuff_by_type = {
    "Skills": [
        { label: "Bash", value: "SK|0" },
        { label: "Charge Flame", value: "SK|2" },
        { label: "Wall Jump", value: "SK|3" },
        { label: "Stomp", value: "SK|4" },
        { label: "Double Jump", value: "SK|5" },
        { label: "Charge Jump", value: "SK|8" },
        { label: "Climb", value: "SK|12" },
        { label: "Glide", value: "SK|14" },
        { label: "Spirit Flame", value: "SK|14" },
        { label: "Dash", value: "SK|50" },
        { label: "Grenade", value: "SK|51" }
    ],
    "Cells/Stones": [
        { label: "Health Cell", value: "HC|1" },
        { label: "Energy Cell", value: "EC|1" },
        { label: "Ability Cell", value: "AC|1" },
        { label: "Keystone", value: "KS|1" },
        { label: "Mapstone", value: "MS|1" }
    ],
    "Teleporters": [
        { label: "Grotto TP", value: "TP|Grotto" },
        { label: "Grove TP", value: "TP|Grove" },
        { label: "Forlorn TP", value: "TP|Forlorn" },
        { label: "Valley TP", value: "TP|Valley" },
        { label: "Sorrow TP", value: "TP|Sorrow" },
        { label: "Swamp TP", value: "TP|Swamp" },
        { label: "Ginso TP", value: "TP|Ginso" },
        { label: "Horu TP", value: "TP|Horu" },
    ],
    "Events": [
        { label: "Water Vein", value: "EV|0" },
        { label: "Clean Water", value: "EV|1" },
        { label: "Gumon Seal", value: "EV|2" },
        { label: "Wind Restored", value: "EV|3" },
        { label: "Sunstone", value: "EV|4" },
        { label: "Warmth Returned", value: "EV|5" }
    ],
    "Upgrades": [
        { label: "Mega Health", value: "RB|0", desc: "Restores health to full, then grants 5 temporary health above the maximum. Will overwrite current temporary health, if any exists (most commonly from an earlier Mega Health)."},
        { label: "Mega Energy", value: "RB|1", desc: "Restores energy to full, then grants 5 temporary energy above the maximum. Will overwrite current temporary energy, if any exists (most commonly from an earlier Mega Energy)."},
        { label: "Attack Upgrade", value: "RB|6", desc: "Increases Spirit Flame's damage and maximum number of targets by 1. Increases Charge Flame damage by 6. Increases Grenade damage by 3 and explosion radius by 1. Stacks."},
        { label: "Explosion Power Upgrade", value: "RB|8", desc: "Increases Charge Flame damage by 6, Grenade damage by 6 and Grenade explosion radius by 1."},
        { label: "Spirit Light Efficiency", value: "RB|9", desc: "Doubles all incoming experience. Stacks multiplicatively with the purple tree ability of the same name: having both results in 4x experience."},
        { label: "Extra Air Dash", value: "RB|10", desc: "Grants a second Air Dash. Requires Dash (the skill) and Air Dash (the ability) to function."},
        { label: "Charge Dash Efficiency", value: "RB|11", desc: "Reduces the cost of Charge Dash from 1 energy to .5 energy."},
        { label: "Extra Double Jump", value: "RB|12", desc: "Grants an extra Double Jump. Requires the Double Jump skill to function. Stacks, both with itself and the Triple Jump ability."},
        { label: "Health Regeneration", value: "RB|13", desc: "Continuously restores health at a rate of 1 per 60 seconds. Stacks."},
        { label: "Energy Regeneration", value: "RB|15", desc: "Continuously restores energy at a rate of 1 per 60 seconds. Stacks."},
        { label: "Water Vein Shard", value: "RB|17", desc: "A piece of the Water Vein. Only present in the Shards Keymode. 3 (out of 5) are needed to enter the Ginso Tree via the front door, and 2 are needed to use the Ginso Teleporter."},
        { label: "Gumon Seal Shard", value: "RB|19", desc: "A piece of the Gumon Seal. Only present in the Shards Keymode. 3 (out of 5) are needed to enter the Forlorn Ruins via the front door, and 2 are needed to use the Forlorn Teleporter."},
        { label: "Sunstone Shard", value: "RB|21", desc: "A piece of the Sunstone. Only present in the Shards Keymode. 3 (out of 5) are needed to enter Mount Horu via the front door, and 2 are needed to use the Horu Teleporter."},
        { label: "Warmth Fragment", value: "RB|28", desc: "A fragment of Warmth. Only present in the Warmth Fragments Goal Mode. A variable number (default 20, out of 30) are needed to enter the final escape."},
        { label: "Bleeding", value: "RB|30", desc: "Continuously removes health at a rate of 1 per 60 seconds. Stacks."},
        { label: "Health Drain", value: "RB|31", desc: "Restores health equal to a percentage of damage dealt to enemies."},
        { label: "Energy Drain", value: "RB|32", desc: "Restores energy equal to a percentage of damage dealt to enemies."},
        { label: "Skill Velocity Upgrade", value: "RB|33", desc: "Increases the velocity of Dash, Bash, Stomp, and Charge Jump. Stacks."},
        { label: "Disable Alt+R", value: "RB|34", desc: "Disables the Return to Start functionality."},
        { label: "Enable Alt+R", value: "RB|35", desc: "Re-enables the Return to Start functionality."},
        { label: "Underwater Skill Usage", value: "RB|36", desc: "Allows Ori to Dash and throw Grenades while underwater."},
        { label: "Remove Wall Jump", value: "RB|40", desc: "Removes Wall Jump."},
        { label: "Remove Charge Flame", value: "RB|41", desc: "Removes Charge Flame"},
        { label: "Remove Double Jump", value: "RB|42", desc: "Removes Double Jump"},
        { label: "Remove Bash", value: "RB|43", desc: "Removes Bash"},
        { label: "Remove Stomp", value: "RB|44", desc: "Removes Stomp"},
        { label: "Remove Glide", value: "RB|45", desc: "Removes Glide"},
        { label: "Remove Climb", value: "RB|46", desc: "Removes Climb"},
        { label: "Remove Charge Jump", value: "RB|47", desc: "Remove Charges Jump"},
        { label: "Remove Dash", value: "RB|48", desc: "Removes Dash"},
        { label: "Remove Grenade", value: "RB|49", desc: "Removes Grenade"},
        { label: "Stompnade Hint", value: "RB|81", desc: "Displays a hint showing which Zones contain the Stomp and Grenade skills"},
        { label: "Polarity Shift", value: "RB|101", desc: "On use: swap your current health and energy. Maximum values for both are ignored."},
        { label: "Gravity Swap", value: "RB|102", desc: "Toggle: inverts gravity, and drains energy at a rate of 3.5 per minute."},
        { label: "Extreme Speed", value: "RB|103", desc: "Toggle: massively increases Ori's horizontal speed, and drains energy at a rate of 3.5 per minute."},
        { label: "Teleport: Last AltR", value: "RB|104", desc: "On use: Pay .5 energy to teleport to your last Alt+R location."},
        { label: "Teleport: Soul Link", value: "RB|105", desc: "On use: Pay .5 energy to teleport to your most recent Soul Link location."},
        { label: "Respec", value: "RB|106", desc: "On use: Refund all your spent AP."},
        { label: "Level Explosion", value: "RB|107", desc: "On use: Pay 1 energy to create a level-up explosion."},
    ],
};

const compareOption = (inputValue, option) => {
    let candidate = inputValue.toLowerCase();
    return (option.value.toLowerCase() === candidate || option.label.toLowerCase() === candidate);
};

const all_opts = [];
const grouped_opts = Object.keys(stuff_by_type).map(t => {
    all_opts.push(...stuff_by_type[t]);
    return { label: t, options: stuff_by_type[t] };
});
grouped_opts.push({
    label: "Misc",
    options: [
        { label: "Repeatable", value: "RP" },
        { label: 'Print "Your text here"', value: "SH|Your text here", fake: true },
        { label: 'Warp to 0,0', value: "WP|0,0", fake: true },
        { label: 'Warp to 0,0 and save', value: "WS|0,0", fake: true },
        { label: '15 Experience', value: "EX|15", fake: true },
    ]
});

class PickupSelect extends Component {
  valFromStr = (input, update = false) => {
    let value = []
    if (input && input.includes("|") && input !== "NO|1") {
      let [code, id] = input.split("|");
      if (code === "RP")
        value.push({ label: "Repeatable", value: "RP" })
      if (code === "MU" || code === "RP") {
        let seen = []
        let parts = id.split("/")
        while (parts.length > 1) {
          let part = `${parts.shift()}|${parts.shift()}`
          while (seen.includes(part))
            part += "|"
          seen.push(part)
          value.push({ label: name_from_str(part), value: part })
        }
      } else {
        value.push({ label: name_from_str(input), value: input })
      }
      if (update)
        this.setState({ value: value })
    }
    return value
  }

  constructor(props) {
    super(props);
    let value = []
    if (props.value) 
      value = this.valFromStr(props.value);
    
    let styles = props.styles || {
        option: (base, data) => {
          let { isDisabled, isFocused } = data
          let bgc = isDisabled ? colors.dangerLight : isFocused ? colors.primary25 : 'transparent'
          return ({
          ...base,
          backgroundColor: bgc,
          color: 'black',
        })},
      }

    this.state = {
      options: grouped_opts,
      value: value,
      menuOpen: false,
      inputValue: "",
      styles: styles, 
      updater: props.updater || console.log
    };
  }
  handleInputChange = inputValue => {
    this.setState({ inputValue });
  };

  handleChange = (newValue, actionMeta) => {
    let last = newValue[newValue.length - 1];
    if (last && last.fake && actionMeta.action === "select-option") {
      let val = last.value
      while (val.endsWith("|") && val.length > 3)
        val = val.slice(0, -1)      
      this.setState({ inputValue: val, menuOpen: true }, this.updatePickup);
    } else {
      this.setState({ value: newValue }, this.updatePickup);
    }
  };
  updatePickup = () => {
    let pickup = "";
    let values = []
    let repeat = false;
    this.state.value.forEach(v => {
      let val = v.value
      while(val.endsWith("|"))
      {
        val = val.slice(0, -1)
      }
      if (val === "RP")
        repeat = true;
      else
        values.push(val);
    });
    if (values.length === 0)
      pickup = "NO|1"
    else if (!repeat && values.length === 1)
      pickup = values[0]
    else {
      pickup = repeat ? "RP|" : "MU|"
      pickup += values.join("/").replace(/\|/g, "/")
    }
    this.state.updater(pickup, name_from_str(pickup))
  }

  isValidNewOption = (input, _) => {
    if (!input) return false;
    if (all_opts.some(option => compareOption(input, option))) return false;
    return true;
  };

  onCreateOption = option => {
    option = this.correct(option);
    if (option.includes("|")) {
      let opt = { value: option, label: name_from_str(option) };
      this.setState(prev => ({ value: prev.value.concat([opt]) }), this.updatePickup);
    }
  };
  correct = raw => {
    let corrected = raw;
    let cleaned = raw.toLowerCase().trim();
    if (cleaned.startsWith("print"))
      corrected = `SH|${raw.substring(5).trim()}`;
    else if (cleaned.startsWith("message"))
      corrected = `SH|${raw.substring(7).trim()}`;
    return corrected;
  };

  filterFunc = (option, rawInput) => {
    const trimString = str => str.replace(/^\s+|\s+$/g, "");
    if (option.data.fake && rawInput.includes("|")) return false;
    if (option.data.__isNew__) return this.correct(rawInput).includes("|");
    let input = trimString(rawInput);
    let candidate = `${option.label} ${option.value}`;
    input = input.toLowerCase();
    candidate = candidate.toLowerCase();
    return candidate.indexOf(input) > -1;
  };
  getNewOptionData = raw => {
    let input = this.correct(raw)
    if (
      input.includes("|") &&
      (raw.length === 3 || input.split("|")[1].trim())
    )
      return {
        value: input,
        label: name_from_str(input),
        __isNew__: true
      };
  };
  selectOption = (that) => (newValue) => {
    let { blurInputOnSelect } = that.props;
    let { selectValue } = that.state;
    let values = selectValue.map(v => v.value);
    let mutVal = {...newValue}
    while (values.includes(mutVal.value))
    {
      mutVal.value += "|"
    }
    that.setValue([...selectValue, mutVal], 'select-option', mutVal);
    that.announceAriaLiveSelection({event: 'select-option', context: { value: that.getOptionLabel(mutVal) },});
    if (blurInputOnSelect) {
      that.blurInput();
    }
  };

  optionDisabled = (opt) => {
    if(!opt.__isNew__)
      return false;
    if (opt.value.startsWith("WP|") || opt.value.startsWith("WS|"))
    {
      let parts = opt.value.substr(3).split(",");
      if(parts.length !== 2 || !parts.every(x => !isNaN(x)))
      {
        if (parts.length === 1) 
          if (parts[0] === "")
            opt.label = (<Fragment>Warp to <b>X</b>,Y</Fragment>)
          else if (isNaN(parts[0]))
            opt.label = (<Fragment>Warp to <s>{parts[0]}</s><i> (invalid number)</i></Fragment>)
          else
            opt.label = (<Fragment>Warp to {parts[0]}<b>,Y</b></Fragment>)
        else if(parts.length > 2)
          opt.label = (<Fragment>Warp to {parts[0]},{parts[1]}<s>,{parts.slice(2).join(",")}</s> <i>(remove extra chars)</i></Fragment>)
        else if(parts[1] === "")
            opt.label = (<Fragment>Warp to {parts[0]},<b>Y</b></Fragment>)
        else
          opt.label = (<Fragment>Warp to {parts[0]},<s>{parts[1]}</s><i> (invalid number)</i></Fragment>)
      return true
      }
     }
    return false
  }

  componentDidMount() {
    this.cref.select.select.isOptionSelected = (opt, values) => opt.value === "RP" && values.some(v => v.value === "RP")
    this.cref.select.select.selectOption = this.selectOption(this.cref.select.select)
  }
  render() {
    const { options, value, inputValue, menuOpen, styles } = this.state;
    return (
      <CreatableSelect
        ref={ref => { this.cref = ref; }}
        isOptionDisabled={this.optionDisabled}
        isClearable
        isMulti
        onMenuOpen={() => this.setState({ menuOpen: true })}
        onMenuClose={() => this.setState({ menuOpen: false })}
        menuIsOpen={menuOpen}
        inputValue={inputValue}
        filterOption={this.filterFunc}
        onInputChange={this.handleInputChange}
        onChange={this.handleChange}
        isValidNewOption={this.isValidNewOption}
        getNewOptionData={this.getNewOptionData}
        onCreateOption={this.onCreateOption}
        options={options}
        value={value}
        styles={styles}
      />
    );
  }
}

const loaders = [
    (<BeatLoader loading />),
    (<BounceLoader loading />),
    (<CircleLoader loading />),
    (<ClipLoader loading />),
    (<ClimbingBoxLoader loading />),
    (<DotLoader loading />),
    (<GridLoader loading />),
    (<HashLoader loading />),
    (<MoonLoader loading />),
    (<PacmanLoader loading />),
    (<PulseLoader loading />),
    (<RingLoader loading />),
    (<RiseLoader loading />),
    (<RotateLoader loading />),
    (<FadeLoader loading />),
    (<ScaleLoader loading />),
    (<SyncLoader loading />)
]

const Blabel = (props) => {

    return (<Badge style={{ fontWeight: 400, fontSize: "100%", display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }} {...props} />)
}
const Cent = (props) => {
    let className = "justify-content-center text-center align-items-center d-flex w-100 h-100"
    if(props.hasOwnProperty("className"))
        className += props.className;
    let spanProps = {...props}
    spanProps.className = className
    
    return (<span {...spanProps} />)
}
function get_random_loader() {
    return loaders[Math.floor(Math.random() * loaders.length)]
}

function get_param(name) {
    let retVal = document.getElementsByClassName(name)[0].id
    return (retVal !== "" && retVal !== "None") ? retVal : null
}

function get_flag(name) {
    let p = get_param(name);
    return p !== null && !p.toLowerCase().includes("false")
}

function get_int(name, orElse) {
    return parseInt(get_param(name), 10) || orElse
}

function get_list(name, sep) {
    let raw = get_param(name)
    if (raw)
        return raw.split(sep)
    else
        return []
}


function get_seed() {
    let authed = get_flag("authed")
    let user = get_param("user")
    let name = get_param("seed_name") || "new seed"
    let desc = get_param("seed_desc") || ""
    let hidden = get_flag("seed_hidden")
    let seedJson = get_param("seed_data")
    return { seedJson: seedJson, user: user, authed: authed, seed_name: name, seed_desc: desc, hidden: hidden }
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
        'glitched', 'timed-level'
    ]
};

const logic_paths = presets['master'].concat('glitched', 'timed-level', 'insane');
const get_preset = (paths) => {
    for (let preset of Object.keys(presets)) {
        let p = presets[preset];
        if (paths.length === p.length && paths.every(path => p.includes(path)))
            return preset;
    }
    return "custom"
}

function player_icons(id, as_leaflet = true) {
    id = parseInt(id, 10);
    let img = '/sprites/ori-white.png';
    if (id === 1) img = '/sprites/ori-blue.png';
    else if (id === 2) img = '/sprites/ori-red.png';
    else if (id === 3) img = '/sprites/ori-green.png';
    else if (id === 4) img = '/sprites/ori-cyan.png';
    else if (id === 5) img = '/sprites/ori-yellow.png';
    else if (id === 6) img = '/sprites/ori-magenta.png';
    else if (id === 7) img = '/sprites/ori-multi-1.png';
    else if (id === 8) img = '/sprites/ori-multi-2.png';
    else if (id === 9) img = '/sprites/ori-multi-3.png';
    else if (id === 10) img = '/sprites/ori-skul.png';

    if (!as_leaflet) return img;

    let ico = new Leaflet.Icon({ iconUrl: img, iconSize: new Leaflet.Point(48, 48) });
    return ico
};

function doNetRequest(url, onRes) {
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState === 4) {
            onRes(xmlHttp);
        }
    }
    xmlHttp.open("GET", url, true); // true for asynchronous
    xmlHttp.send(null);
}

export {
    player_icons, doNetRequest, get_param, get_flag, get_int, get_list, get_preset, presets, get_seed, logic_paths, get_random_loader, Blabel,
    pickup_name, stuff_by_type, name_from_str, PickupSelect, Cent
};