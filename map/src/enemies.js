// The plando editor's enemy panel: one row per placeholder, the seed's //EnemyRolls= line as its state.
import React from 'react';
import Leaflet from 'leaflet';
import {Tooltip} from 'react-leaflet';
import Select from 'react-select';
import {Button, Input} from 'reactstrap';
import TABLE from './enemies.json';

const PREFIX = "//EnemyRolls=";

const KIND_COLORS = {Bonus: "#bbbbbb", Fronkeys: "#8bc34a", Frogs: "#2e7d32", Slimes: "#9c27b0", Banelings: "#ff5722", DropSlugs: "#795548",
                     Worms: "#ff9800", Rhinos: "#b71c1c", Birds: "#03a9f4", Elementals: "#ffeb3b", Swarms: "#78909c",
                     Spiders: "#e91e63", Fish: "#00bcd4", Sharks: "#3f51b5"};

const placements = TABLE.placements.map((p, i) => ({...p, i}));
const variants = TABLE.variants.map((v, i) => ({...v, i}));
const by_kind = {};
variants.forEach(v => { (by_kind[v.kind] = by_kind[v.kind] || []).push(v) });

const scene_label = (scene) => scene.replace(/([a-z])([A-Z0-9])/g, "$1 $2").replace(/^./, c => c.toUpperCase());
const row_label = (p) => `${scene_label(p.scene)} (${p.x}, ${p.y})`;

const parse_rolls = (line) => {
    if(typeof line !== "string" || !line.startsWith(PREFIX))
        return null
    let [version, body] = line.slice(PREFIX.length).split(":")
    if(version !== TABLE.version)
        return null
    // "b<N>": the game reads bonus N when the placeholder spawns and takes variant N - 1
    let rolls = (body || "").split(",").map(r => r === "" ? null : /^b\d+$/.test(r) ? r : parseInt(r, 10))
    return rolls.length === placements.length && rolls.every(r => r === null || typeof r === "string" || (r >= 0 && r < variants.length)) ? rolls : null
};
const is_bonus = (r) => typeof r === "string";
const bonus_id = (r) => parseInt(r.slice(1), 10);
const rolls_line = (rolls) => PREFIX + TABLE.version + ":" + rolls.map(r => r === null ? "" : r).join(",");
const vanilla_rolls = () => placements.map(() => null);
const roll_kind = (p, r) => r === null ? p.kind : is_bonus(r) ? "Bonus" : variants[r].kind;
// what may stand at a spot by the table alone; the server's finer rules are the author's to mind
const kinds_for = (p) => TABLE.kinds.filter(k => k.spots.includes(p.spot) || (p.spot === "rhino" && k.spots.includes("floor"))).map(k => k.name);
const random_variant = (kind) => by_kind[kind][Math.floor(Math.random() * by_kind[kind].length)].i;
const next_variant = (r, step) => {
    let vs = by_kind[variants[r].kind]
    return vs[(vs.findIndex(v => v.i === r) + step + vs.length) % vs.length].i
};
const changed_count = (rolls) => rolls ? rolls.filter(r => r !== null).length : 0;

const marker_icon = (kind, selected) => Leaflet.divIcon({
    className: "enemy-marker" + (selected ? " enemy-marker-selected" : ""), iconSize: [14, 14],
    html: `<span style="background:${KIND_COLORS[kind] || "#fff"}"></span>`,
});

function enemy_markers(rolls, selected, onSelect) {
    rolls = rolls || vanilla_rolls()
    return placements.map(p => {
        let kind = roll_kind(p, rolls[p.i])
        return {
            key: `enemy-${p.i}`, position: [p.y, p.x], icon: marker_icon(kind, p.i === selected), opacity: rolls[p.i] === null ? 0.6 : 1,
            inner: <Tooltip><span>{row_label(p)}: {is_bonus(rolls[p.i]) ? `from bonus ${bonus_id(rolls[p.i])}` : kind}{rolls[p.i] === null || is_bonus(rolls[p.i]) ? "" : ` #${rolls[p.i] + 1}`}</span></Tooltip>,
            onClick: () => onSelect(p.i),
        }
    })
}

class EnemyRow extends React.PureComponent {
    ref = React.createRef()
    componentDidUpdate(prev) {
        if(this.props.selected && !prev.selected && this.ref.current)
            this.ref.current.scrollIntoView({block: "nearest"})
    }
    setKind = (opt) => {
        let {p, r, onChange} = this.props
        if(opt.value === "vanilla")
            onChange(p.i, null)
        else if(opt.value === "bonus")
            onChange(p.i, is_bonus(r) ? r : "b100")
        else if(roll_kind(p, r) !== opt.value || r === null)
            onChange(p.i, random_variant(opt.value))
    }
    setBonus = (ev) => {
        let n = parseInt(ev.target.value, 10)
        this.props.onChange(this.props.p.i, isNaN(n) || n < 0 ? "b0" : `b${n}`)
    }
    render() {
        let {p, r, selected, onSelect, onChange, styles} = this.props
        let kind = roll_kind(p, r)
        let options = [{label: `Vanilla (${p.kind})`, value: "vanilla"}].concat(kinds_for(p).map(k => ({label: k, value: k})), {label: "From a bonus", value: "bonus"})
        return (
            <div className={"enemy-row" + (selected ? " enemy-row-selected" : "")} ref={this.ref} onClick={() => onSelect(p.i)}>
                <span className="enemy-num" title={`placeholder ${p.i}`}>{p.i}</span>
                <span className="enemy-swatch" style={{background: KIND_COLORS[kind]}}/>
                <span className="enemy-where" title={p.scene}>({p.x}, {p.y}) {p.spot}{p.arena ? ", miniboss room" : ""}</span>
                <Select className="enemy-kind" styles={styles} isSearchable={false} onChange={this.setKind}
                        options={options} value={r === null ? options[0] : is_bonus(r) ? options[options.length - 1] : {label: kind, value: kind}}/>
                {is_bonus(r) ? (
                    <span className="enemy-variant" title="In play, this bonus id's value picks the variant by its number here; 0, unset or past the last number stays vanilla">
                        RB|<Input type="number" bsSize="sm" className="enemy-bonus" min={0} value={bonus_id(r)} onChange={this.setBonus} onClick={e => e.stopPropagation()}/>
                    </span>
                ) : r !== null ? (
                    <span className="enemy-variant" title="Which of this kind's variants: health and damage differ, the look may too">
                        <Button size="sm" color="secondary" outline onClick={e => { e.stopPropagation(); onChange(p.i, next_variant(r, -1)) }}>◀</Button>
                        #{r + 1}
                        <Button size="sm" color="secondary" outline onClick={e => { e.stopPropagation(); onChange(p.i, next_variant(r, 1)) }}>▶</Button>
                    </span>
                ) : null}
            </div>
        )
    }
}

class EnemyPanel extends React.Component {
    state = {filter: "", open: {}}
    setRoll = (i, r) => {
        let rolls = [...(this.props.rolls || vanilla_rolls())]
        rolls[i] = r
        this.props.onChange(rolls)
    }
    toggleScene = (scene) => this.setState(prev => ({open: {...prev.open, [scene]: !prev.open[scene]}}))
    render() {
        let {rolls, selected, onSelect, onDone, styles, player_select} = this.props
        let {filter} = this.state
        let match = filter.trim().toLowerCase()
        let shown = placements.filter(p => !match || row_label(p).toLowerCase().includes(match) || roll_kind(p, (rolls || [])[p.i] === undefined ? null : rolls[p.i]).toLowerCase().includes(match))
        let scenes = []
        shown.forEach(p => { if(!scenes.length || scenes[scenes.length - 1].scene !== p.scene) scenes.push({scene: p.scene, rows: []}); scenes[scenes.length - 1].rows.push(p) })
        let selected_scene = selected !== null && selected !== undefined ? placements[selected].scene : null
        return (
            <div id="box-controls">
                <hr style={{backgroundColor: 'gray', height: 2}}/>
                <div className="box-panel-head">
                    <span className="box-panel-title">Enemies</span>
                    <span className="box-panel-count">{changed_count(rolls)}</span>
                    {player_select}
                    <Button color="secondary" className="box-panel-done" onClick={onDone}>Done</Button>
                </div>
                <div className="box-buttons">
                    <Button color="secondary" disabled={!changed_count(rolls)} onClick={() => this.props.onChange(vanilla_rolls())}
                            title="Every placeholder back to the enemy it has in the base game">All vanilla</Button>
                    <Input className="enemy-filter" placeholder="Filter by scene, coordinates or kind" value={filter}
                           onChange={e => this.setState({filter: e.target.value})}/>
                    <a className="enemy-list-link" href="/enemies.txt" target="_blank" rel="noopener noreferrer" title="Every variant by number, with its kind and base stats">variant list</a>
                </div>
                <div className="enemy-list">
                    {scenes.map(({scene, rows}) => {
                        let open = match || this.state.open[scene] || scene === selected_scene
                        let changed = rows.filter(p => rolls && rolls[p.i] !== null).length
                        return (
                            <div key={scene}>
                                <div className="enemy-scene" onClick={() => this.toggleScene(scene)}>
                                    <span>{open ? "▾" : "▸"} {scene_label(scene)}</span>
                                    <span className="enemy-scene-count">{changed ? `${changed} changed of ` : ""}{rows.length}</span>
                                </div>
                                {open ? rows.map(p => (
                                    <EnemyRow key={p.i} p={p} r={rolls ? rolls[p.i] : null} selected={p.i === selected}
                                              onSelect={onSelect} onChange={this.setRoll} styles={styles}/>
                                )) : null}
                            </div>
                        )
                    })}
                    {!shown.length ? <div className="box-list-empty">No placeholders match.</div> : null}
                </div>
            </div>
        )
    }
}

export {EnemyPanel, enemy_markers, parse_rolls, rolls_line, vanilla_rolls, changed_count};
