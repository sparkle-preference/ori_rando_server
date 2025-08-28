import React, { Component, Fragment } from 'react';
import Leaflet from 'leaflet';
import {
    BeatLoader, BounceLoader, CircleLoader, ClipLoader, ClimbingBoxLoader, DotLoader, GridLoader, HashLoader, MoonLoader,
    PacmanLoader, PulseLoader, RingLoader, RiseLoader, RotateLoader, SyncLoader, FadeLoader, ScaleLoader
} from 'react-spinners';
import { Badge } from 'reactstrap';
//import { components } from 'react-select';
import CreatableSelect from 'react-select/lib/Creatable';

const select_theme = (theme) => {
    let style = getComputedStyle(document.body);
    return ({
      ...theme,
      colors: {
      ...theme.colors,
      primary: style.getPropertyValue("--success"), // selected
      primary25: style.getPropertyValue("--info"),  // hover
      dangerLight: style.getPropertyValue("--warning"), // disabled
      neutral0: style.getPropertyValue("background-color"), // background
      neutral10: style.getPropertyValue("--secondary"), // multi background
      neutral80: style.getPropertyValue("color")
    },
    })
}
function ordinal_suffix(i) {
    let j = i % 10,
        k = i % 100;
    if (j === 1 && k !== 11) {
        return i + "st";
    }
    if (j === 2 && k !== 12) {
        return i + "nd";
    }
    if (j === 3 && k !== 13) {
        return i + "rd";
    }
    return i + "th";
}
function name_from_str(pick) {
    if(!pick)
        return ""
    let parts = pick.split("|");
    return pickup_name(parts[0], parts[1])
}

function pickup_name(code, id) {
    let upgrade_names = {};
    stuff_by_type["Upgrades"].forEach(s => {
        upgrade_names[s.value.substring(3)] = s.label;
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
            if(id === "*")
                return "Random Bonus Warp"
            if(id.endsWith(",force"))
                return "Warp (forced) to " + id.slice(0, id.length-6) + (code === "WS" ? " and save" : "")
            else
                return "Warp (optional) to " + id + (code === "WS" ? " and save" : "")
        case "NO":
            return "Nothing"
        case "BS":
            if(id === "*")
                return "Random bonus skill"
            return code + "|" + id;
        case "TW":
          const subparts = id.split(",");
          return `${subparts[0]} (${subparts[1]}, ${subparts[2]})`;
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
        { label: "Spirit Flame", value: "SK|15" },
        { label: "Dash", value: "SK|50" },
        { label: "Grenade", value: "SK|51" }
    ],
    "Cells/Stones": [
        { label: "Health Cell", value: "HC|1" },
        { label: "Energy Cell", value: "EC|1", min: 3},
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
        { label: "Blackroot TP", value: "TP|Blackroot" },
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
        { label: "Mega Health", value: "RB|0", desc: "Restores health to full, then grants 5 temporary health. Does not stack with other sources of temporary health."},
        { label: "Mega Energy", value: "RB|1", desc: "Restores energy to full, then grants 5 temporary energy. Does not stack with other sources of temporary energy."},
        { label: "Attack Upgrade", value: "RB|6", desc: "Increases Spirit Flame's damage and maximum number of targets by 1. Increases Charge Flame damage by 6. Increases Grenade damage by 3 and explosion radius by 1. Stacks."},
        { label: "Explosion Power Upgrade", value: "RB|8", desc: "Deprecated. Increases Charge Flame damage by 6, Grenade damage by 6 and Grenade explosion radius by 1."},
        { label: "Spirit Light Efficiency", value: "RB|9", desc: "Doubles all incoming experience. Stacks additively, both with itself and with the purple tree ability of the same name."},
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
        { label: "Health Drain", value: "RB|31", desc: "Restores health equal to 5% of the damage dealt to enemies. Attacks that deal more than 20 damage are treated as though they had dealt 20"},
        { label: "Energy Drain", value: "RB|32", desc: "Restores energy equal to 5% of the damage dealt to enemies. Attacks that deal more than 20 damage are treated as though they had dealt 20"},
        { label: "Skill Velocity Upgrade", value: "RB|33", desc: "Increases the velocity of Dash, Bash, Stomp, Climb and Charge Jump. Stacks. Can be toggled off via an automatically-granted bonus skill."},
        { label: "Disable Alt+R", value: "RB|34", desc: "Disables the Return to Start functionality."},
        { label: "Enable Alt+R", value: "RB|35", desc: "Re-enables the Return to Start functionality."},
        { label: "Underwater Skill Usage", value: "RB|36", desc: "Allows Ori to Dash and throw Grenades while underwater."},
        { label: "Jump Upgrade", value: "RB|37", desc: "Increases the height of Jumps, including Wall Jump and Double Jump. Stacks. Can be toggled off via an automatically-granted bonus skill."},
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
        { label: "Enable Frag Sense", value: "RB|1100", desc: "Allows sense to be triggered by mapstone fragments once it's been triggered by a MS turnin."},
        { label: "Polarity Shift", value: "RB|101", desc: "On use: swap your current health and energy. Maximum values for both are ignored. Can't be used with 0 Energy."},
        { label: "Gravity Swap", value: "RB|102", desc: "Toggle: inverts gravity, and drains energy at a rate of 4 per minute."},
        { label: "Extreme Speed", value: "RB|103", desc: "Toggle: massively increases Ori's horizontal speed, and drains energy at a rate of 4 per minute."},
        { label: "Teleport: Last AltR", value: "RB|104", desc: "On use: Pay .5 energy to teleport to your last Alt+R location."},
        { label: "Teleport: Soul Link", value: "RB|105", desc: "On use: Pay .5 energy to teleport to your most recent Soul Link location."},
        { label: "Respec", value: "RB|106", desc: "On use: Refund all your spent AP. Only works at a Soul Link."},
        { label: "Level Explosion", value: "RB|107", desc: "On use: Pay 1 energy to create a level-up explosion."},
        { label: "Timewarp", value: "RB|109", desc: "Toggle: Slows time for everything but Ori, and drains energy at a rate of 4 per minute."},
        { label: "Invincibility", value: "RB|110", desc: "Toggle: Makes Ori Invincible. Costs 1 energy per second, +.5 to activate."},
        { label: "Wither", value: "RB|111", desc: "On Use: kills Ori (no cost)"},
        { label: "Bash/Stomp Damage", value: "RB|113", desc: "Toggle: prevents any damage Stomp and Bash would deal to enemies. (no cost)"},
        {label: "Quick Flame", value: "RB|200"}, 
        {label: "Spark Flame", value: "RB|201"}, 
        {label: "Charge Flame Burn", value: "RB|202"}, 
        {label: "Split Flame", value: "RB|203"}, 
        {label: "Ultra Light Burst", value: "RB|204"}, 
        {label: "Cinder Flame", value: "RB|205"}, 
        {label: "Ultra Stomp", value: "RB|206"}, 
        {label: "Rapid Flame", value: "RB|207"}, 
        {label: "Charge Flame Blast", value: "RB|208"}, 
        {label: "Ultra Split Flame", value: "RB|209"}, 
        {label: "Spirit Magnet", value: "RB|210"}, 
        {label: "Map Markers", value: "RB|211"}, 
        {label: "Life Efficiency", value: "RB|212"}, 
        {label: "Ultra Spirit Magnet", value: "RB|213"}, 
        {label: "Energy Efficiency", value: "RB|214"}, 
        {label: "Spirit Efficiency", value: "RB|215"}, 
        {label: "Spirit Potency", value: "RB|216"}, 
        {label: "Life Regen (Ability)", value: "RB|217"}, 
        {label: "Energy Regen (Ability", value: "RB|218"}, 
        {label: "Sense", value: "RB|219"}, 
        {label: "Rekindle", value: "RB|220"}, 
        {label: "Regroup", value: "RB|221"}, 
        {label: "Charge Flame Efficiency", value: "RB|222"}, 
        {label: "Air Dash", value: "RB|223"}, 
        {label: "Ultra Soul Link", value: "RB|224"}, 
        {label: "Charge Dash", value: "RB|225"}, 
        {label: "Water Breath", value: "RB|226"}, 
        {label: "Soul Link Efficiency", value: "RB|227"}, 
        {label: "Triple Jump", value: "RB|228"}, 
        {label: "Ultra Defense", value: "RB|229"}, 
        {label: "Remove Quick Flame", value: "RB|230"}, 
        {label: "Remove Spark Flame", value: "RB|231"}, 
        {label: "Remove Charge Flame Burn", value: "RB|232"}, 
        {label: "Remove Split Flame", value: "RB|233"}, 
        {label: "Remove Ultra Light Burst", value: "RB|234"}, 
        {label: "Remove Cinder Flame", value: "RB|235"}, 
        {label: "Remove Ultra Stomp", value: "RB|236"}, 
        {label: "Remove Rapid Flame", value: "RB|237"}, 
        {label: "Remove Charge Flame Blast", value: "RB|238"}, 
        {label: "Remove Ultra Split Flame", value: "RB|239"}, 
        {label: "Remove Spirit Magnet", value: "RB|240"}, 
        {label: "Remove Map Markers", value: "RB|241"}, 
        {label: "Remove Life Efficiency", value: "RB|242"}, 
        {label: "Remove Ultra Spirit Magnet", value: "RB|243"}, 
        {label: "Remove Energy Efficiency", value: "RB|244"}, 
        {label: "Remove Spirit Efficiency", value: "RB|245"}, 
        {label: "Remove Spirit Potency", value: "RB|246"}, 
        {label: "Remove Life Regen (Ability)", value: "RB|247"}, 
        {label: "Remove Energy Regen (Ability)", value: "RB|248"}, 
        {label: "Remove Sense", value: "RB|249"}, 
        {label: "Remove Rekindle", value: "RB|250"}, 
        {label: "Remove Regroup", value: "RB|251"}, 
        {label: "Remove Charge Flame Efficiency", value: "RB|252"}, 
        {label: "Remove Air Dash", value: "RB|253"}, 
        {label: "Remove Ultra Soul Link", value: "RB|254"}, 
        {label: "Remove Charge Dash", value: "RB|255"}, 
        {label: "Remove Water Breath", value: "RB|256"}, 
        {label: "Remove Soul Link Efficiency", value: "RB|257"}, 
        {label: "Remove Triple Jump", value: "RB|258"}, 
        {label: "Remove Ultra Defense", value: "RB|259"},         
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


class PickupSelect extends Component {
  clear = () => this.setState({value: []})
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
    
    let s = getComputedStyle(document.body);

    let styles = props.styles || {
        option: (base, data) => {
          let { isDisabled, isFocused } = data
          let bgc = isDisabled ? s.getPropertyValue("--warning") : isFocused ? s.getPropertyValue("--info") : s.getPropertyValue("background-color")
          return ({
          ...base,
          backgroundColor: bgc,
          color: s.getPropertyValue("color"),
        })},
      }
    
    let options = [...grouped_opts]
    if(!props.noMisc) {
        let misc = {
            label: "Misc",
            options: [
                { label: '15 Experience', value: "EX|15", fake: true },
                { label: "Repeatable", value: "RP" },
                { label: 'Print "Your text here"', value: "SH|Your text here", fake: true },
                { label: 'Warp to 0,0', value: "WP|0,0", fake: true },
                { label: 'Warp (forced) to 0,0', value: "WP|0,0,force", fake: true },
                { label: 'Warp (forced) to 0,0 and save', value: "WS|0,0,force", fake: true },
                { label: 'Warp to 0,0 and save', value: "WS|0,0", fake: true },
            ]
        }
        if(props.allowPsuedo) {
            misc.options.splice(0, 0, {label: "Random Bonus Skill", value: "BS|*", desc: "A random bonus skill", max: 6})
            misc.options.splice(0, 0, {label: "Random Bonus Warp", value: "WP|*"})
        }
        options.push(misc)
    }

    this.state = {
      options: options,
      value: value,
      lastPropVal: props.value,
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
    else if(raw.startsWith("WP|") || raw.startsWith("WS|")) {
        let parts = raw.split(",")
        if(parts.length === 3 && "force".startsWith(parts[2]))
        {
            parts[2] = "force"
            corrected = parts.join(",")
        }
    }
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
    if (input.includes("|") && (raw.length === 3 || input.split("|")[1].trim()))
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
            opt.label = (<Fragment>Warp (optional) to <b>X</b>,Y</Fragment>)
          else if (isNaN(parts[0]))
            opt.label = (<Fragment>Warp (optional) to <s>{parts[0]}</s><i> (invalid number)</i></Fragment>)
          else
            opt.label = (<Fragment>Warp (optional) to {parts[0]}<b>,Y</b></Fragment>)
        else if(parts.length > 2)
          if(parts.length === 3)
              if(isNaN(parts[0]) || isNaN(parts[1]))
              {
                if(!isNaN(parts[1]))
                    opt.label = (<Fragment>Warp (optional) to <s>{parts[0]}</s>,{parts[1]},{parts[2]} <i>(invalid number)</i></Fragment>)
                else if(!isNaN(parts[0]))
                    opt.label = (<Fragment>Warp (optional) to {parts[0]},<s>{parts[1]}</s>,{parts[2]} <i>(invalid number)</i></Fragment>)
                else
                    opt.label = (<Fragment>Warp (optional) to <s>{parts[0]},{parts[1]}</s>,{parts[2]} <i>(invalid numbers)</i></Fragment>)
              }
              else if("force".startsWith(parts[2])) {
                  return false
              }
              else
                opt.label = (<Fragment>Warp (optional) to {parts[0]},{parts[1]}<s>,{parts.slice(2).join(",")}</s> <i>(the only currently supported 3rd parameter is 'force')</i></Fragment>)
          else
              opt.label = (<Fragment>Warp (optional) to {parts[0]},{parts[1]}<s>,{parts.slice(2).join(",")}</s> <i>(remove extra chars)</i></Fragment>)
        else if(parts[1] === "")
            opt.label = (<Fragment>Warp (optional) to {parts[0]},<b>Y</b></Fragment>)
        else if(isNaN(parts[1]))
            opt.label = (<Fragment>Warp (optional) to {parts[0]},<s>{parts[1]}</s> <i>(invalid number)</i></Fragment>)
        else
          opt.label = (<Fragment>Warp (optional) to {parts[0]},<s>{parts[1]}</s><i> (invalid number)</i></Fragment>)
      return true
      }
     }
    return false
  }

  componentDidMount() {
    this.cref.select.select.isOptionSelected = (opt, values) => opt.value === "RP" && values.some(v => v.value === "RP")
    this.cref.select.select.selectOption = this.selectOption(this.cref.select.select)
  }
  componentDidUpdate() {
      if(this.state.lastPropVal !== this.props.value)
      {
        this.setState({lastPropVal: this.props.value, value: this.valFromStr(this.props.value)})
      }
  }
  render() {

    const { options, value, inputValue, menuOpen, styles } = this.state;
    return (
      <CreatableSelect
        ref={ref => { this.cref = ref; }}
        isOptionDisabled={this.optionDisabled}
        isClearable={this.props.isClearable}
        isDisabled={this.props.isDisabled || this.props.disabled || false}
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
        theme={select_theme}
      />
    );
  }
}

const loaders = (color) => [
    (<BeatLoader color={color} />),
    (<BounceLoader color={color} />),
    (<CircleLoader color={color} />),
    (<ClipLoader color={color} />),
    (<ClimbingBoxLoader color={color} />),
    (<DotLoader color={color} />),
    (<GridLoader color={color} />),
    (<HashLoader color={color} />),
    (<MoonLoader color={color} />),
    (<PacmanLoader color={color} />),
    (<PulseLoader color={color} />),
    (<RingLoader color={color} />),
    (<RiseLoader color={color} />),
    (<RotateLoader color={color} />),
    (<FadeLoader color={color} />),
    (<ScaleLoader color={color} />),
    (<SyncLoader color={color} />)
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
function get_random_loader(color) {
    color = color || ["#f55", "#5f5", "#55f", "#ff5", "#f5f", "#5ff"][Math.floor(Math.random() * 6)]
    return loaders(color)[Math.floor(Math.random() * 17)]
}

function get_param(name) {
    let retVal = document.getElementById("templateData").dataset[name];
    return (retVal !== "" && retVal !== "None") ? retVal : null
}

function get_flag(name) {
    let p = get_param(name);
    return p != null && !p.toLowerCase().includes("false")
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
    let name = get_param("seed_name") || "newSeed"
    let desc = get_param("seed_desc") || ""
    let hidden = get_flag("seed_hidden")
    let seedJson = get_param("seed_data")
    return { seedJson: seedJson, user: user, authed: authed, seed_name: name, seed_desc: desc, hidden: hidden }
}
    // health, energy, skills: 3, 1, 0 by default
const spawn_defaults = {
    "Glades": {
    },
    "Grove": {
        "Casual": [3, 1, 1], 
        "Standard": [3, 1, 1], 
        "Expert": [3, 1, 1], 
    },
    "Swamp": {
        "Casual": [4, 2, 1], 
        "Standard": [3, 2, 1], 
        "Expert": [3, 1, 1], 
    },
    "Grotto": {
        "Casual": [4, 2, 1],
        "Standard": [3, 2, 1],
    },
    "Forlorn": {
        "Casual": [5, 3, 2],
        "Standard": [4, 2, 1],
        "Expert": [4, 2, 1],
        "Master": [3, 2, 1],
    },
    "Valley": {
        "Casual": [5, 3, 2],
        "Standard": [4, 2, 2],
        "Expert": [4, 2, 1],
        "Master": [3, 2, 1],
    },
    "Horu": {
        "Casual": [5, 3, 3],
        "Standard": [4, 2, 3],
        "Expert": [4, 2, 2],
        "Master": [4, 2, 2],
    },
    "Ginso": {
        "Casual": [5, 3, 2],
        "Standard": [4, 2, 2],
        "Expert": [4, 2, 1],
        "Master": [3, 2, 1],
    },
    "Sorrow": {
        "Casual": [6, 3, 3],
        "Standard": [5, 2, 3],
        "Expert": [5, 2, 2],
        "Master": [4, 2, 2],
    },
    "Blackroot": {
        "Casual": [4, 2, 2],
        "Standard": [4, 2, 2],
        "Expert": [3, 1, 2],
        "Master": [3, 1, 2],
    },
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
    let img = '/static/sprites/ori-white.png';
    if (id === 1) img = '/static/sprites/ori-blue.png';
    else if (id === 2) img = '/static/sprites/ori-red.png';
    else if (id === 3) img = '/static/sprites/ori-green.png';
    else if (id === 4) img = '/static/sprites/ori-cyan.png';
    else if (id === 5) img = '/static/sprites/ori-yellow.png';
    else if (id === 6) img = '/static/sprites/ori-magenta.png';
    else if (id === 7) img = '/static/sprites/ori-multi-1.png';
    else if (id === 8) img = '/static/sprites/ori-multi-2.png';
    else if (id === 9) img = '/static/sprites/ori-multi-3.png';
    else if (id === 10) img = '/static/sprites/ori-skul.png';
    else if (id === 11) img = '/static/sprites/ori-peach.png';
    else if (id === 12) img = '/static/sprites/ori-orange.png';
    else if (id === 13) img = '/static/sprites/ori-arctic.png';
    else if (id === 14) img = '/static/sprites/ori-paum.png';
    else if (id === 15) img = '/static/sprites/ori-pika.png';
    else if (id === 100) img = '/static/sprites/kuro.png';
    else if (id === 101) img = '/static/sprites/gumo.png';
    else if (id === 102) img = '/static/sprites/ori-eph.png';
    else if (id === 103) img = '/static/sprites/boulder_smol.png';
    else if (id === 221) img = '/static/sprites/ori-eiko.png';
    else if (id === 333) img = '/static/sprites/ori-blorple.png';
    else if (id === 385) img = '/static/sprites/ori-poogle.png';

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

function gotoUrl(url, newWindow) {
    newWindow = newWindow || false
    let element = document.createElement('a');
    element.setAttribute('href', url);
    if(newWindow)
    {
        element.setAttribute('rel', 'noopener noreferrer');
        element.setAttribute('target', '_blank');
    }
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
}

function loginLogoutUrl(isLogin) {
    let url = new URL(window.document.URL);
    let page = encodeURIComponent(url.pathname + url.search + url.hash);

    let endpoint = isLogin ? 'login' : 'logout';
    return `/${endpoint}?next=${page}`;
}


const dev = window.document.URL.includes("cloudshell.dev");
const randInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;


const cyrb128 = (str) => {
  let h1 = 1779033703, h2 = 3144134277,
      h3 = 1013904242, h4 = 2773480762;
  for (let i = 0, k; i < str.length; i++) {
      k = str.charCodeAt(i);
      h1 = h2 ^ Math.imul(h1 ^ k, 597399067);
      h2 = h3 ^ Math.imul(h2 ^ k, 2869860233);
      h3 = h4 ^ Math.imul(h3 ^ k, 951274213);
      h4 = h1 ^ Math.imul(h4 ^ k, 2716044179);
  }
  h1 = Math.imul(h3 ^ (h1 >>> 18), 597399067);
  h2 = Math.imul(h4 ^ (h2 >>> 22), 2869860233);
  h3 = Math.imul(h1 ^ (h3 >>> 17), 951274213);
  h4 = Math.imul(h2 ^ (h4 >>> 19), 2716044179);
  h1 ^= (h2 ^ h3 ^ h4); h2 ^= h1; h3 ^= h1; h4 ^= h1;
  return [h1>>>0, h2>>>0, h3>>>0, h4>>>0];
}


const sfc32 = (a, b, c, d) => {
  return () => {
    a |= 0; b |= 0; c |= 0; d |= 0;
    let t = (a + b | 0) + d | 0;
    d = d + 1 | 0;
    a = b ^ (b >>> 9);
    b = c + (c << 3) | 0;
    c = ((c << 21) | (c >>> 11));
    c = c + t | 0;
    return (t >>> 0) / 4294967296;
  }
}


const prng = (strIn) => sfc32(...cyrb128(strIn));
 

export {
    player_icons, doNetRequest, prng, get_param, get_flag, get_int, get_list, get_preset, presets, get_seed, logic_paths, get_random_loader, Blabel,
    pickup_name, stuff_by_type, name_from_str, PickupSelect, Cent, ordinal_suffix, dev, gotoUrl, loginLogoutUrl, select_theme, randInt, spawn_defaults
};
