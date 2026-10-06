import React from 'react';
import {presets, GOAL_VARS} from './common.js';

const KEY_FLAGS = ["Shards", "Clues", "Limitkeys", "Free", "Default"];
const MODE_NAMES = {shared: "Co-op", none: "Race", multiworld: "Multiworld", splitshards: "Split Shards"};

// the seed tab's chip for a flag: its place in line (logic, keys, goals, items, spawn,
// multiplayer, variations, the rest), its label, and a color if it decides how a seed plays
const flagChip = (flag) => {
    if(Object.keys(presets).includes(flag.replace("*", "").toLowerCase()) || /^Custom\d*$/.test(flag) || flag.startsWith("lps="))
        return {rank: 0, label: flag.startsWith("Custom") ? "Custom Logic" : flag, cls: "flag-chip-logic"}
    if(KEY_FLAGS.includes(flag))
        return {rank: 1, label: flag, cls: "flag-chip-key"}
    if(flag.startsWith("Frags/"))
        return {rank: 2, label: `Frags (${flag.slice(6)})`, cls: "flag-chip-goal"}
    if(flag.startsWith("WorldTour="))
        return {rank: 2, label: "WorldTour " + flag.slice(10), cls: "flag-chip-goal"}
    if(GOAL_VARS.includes(flag))
        return {rank: 2, label: flag, cls: "flag-chip-goal"}
    if(flag.startsWith("pool="))
        return {rank: 3, label: "Items: " + flag.slice(5), cls: "flag-chip-items"}
    if(flag.startsWith("spawn="))
        return {rank: 4, label: "Spawn: " + flag.slice(6), cls: "flag-chip-spawn"}
    if(flag.startsWith("share="))
        return {rank: 5, label: "Shared: " + flag.slice(6).split("+").join(", "), cls: "flag-chip-shared"}
    if(flag.startsWith("mode="))
        return {rank: 5, label: "Mode: " + (MODE_NAMES[flag.slice(5).toLowerCase()] || flag.slice(5)), cls: "flag-chip-plain"}
    if(flag === "DeathLink" || flag.startsWith("anti_bk_bias="))
        return {rank: 5, label: flag, cls: "flag-chip-plain"}
    if(flag.startsWith("prefer_path_difficulty="))
        return {rank: 7, label: "Path Diff: " + flag.split("=")[1], cls: "flag-chip-plain"}
    // a bare word is a variation; balanced is the fill algorithm
    return {rank: flag.includes("=") || flag === "balanced" ? 7 : 6, label: flag, cls: "flag-chip-plain"}
}

// roomy unless that runs past maxLines and the tight style saves a line
class FlagChips extends React.Component {
    state = {tight: false}
    box = React.createRef()
    componentDidMount() { window.addEventListener("resize", this.refit); this.fit() }
    componentWillUnmount() { window.removeEventListener("resize", this.refit) }
    componentDidUpdate(prev) { if(prev.sig !== this.props.sig || prev.maxLines !== this.props.maxLines) this.refit() }
    refit = () => this.setState({tight: false}, this.fit)
    lines = () => new Set([...this.box.current.children].map(c => c.offsetTop)).size
    fit = () => {
        if(!this.box.current || this.state.tight)
            return
        let roomy = this.lines()
        if(roomy > this.props.maxLines)
            this.setState({tight: true}, () => this.lines() >= roomy && this.setState({tight: false}))
    }
    render = () => (
        <div ref={this.box} className={"flag-chips" + (this.state.tight ? " tight" : "")}>{this.props.children}</div>
    )
}

export {flagChip, FlagChips};
