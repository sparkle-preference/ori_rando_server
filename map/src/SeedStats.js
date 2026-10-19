import React from 'react';
import {Container, Row, Col, Button, Input, Table, Progress} from 'reactstrap';
import Select from 'react-select';
import SiteBar from "./SiteBar.js"
import SiteFooter from "./SiteFooter.js"
import {doNetRequest, pickup_name, select_theme} from './common.js';
import {picks_by_loc, select_styles} from './shared_map.js';

// An unlisted dev page: roll one preset many times on the server and tally where each item lands.
const BATCH = 10;

const locName = (loc) => {
    const pick = picks_by_loc[loc];
    if(pick)
        return `${pick.area} ${pick.name} (${pick.zone})`;
    // mapstone turn-ins are 24, 28, ... in seed order
    const n = (parseInt(loc, 10) - 20) / 4;
    return Number.isInteger(n) && n >= 1 && n <= 9 ? `Mapstone ${n}` : `${loc}`;
};
const itemName = (key) => {
    const [code, ...rest] = key.split("|");
    return pickup_name(code, rest.join("|")) || key;
};
const pct = (n, d) => d ? `${(100 * n / d).toFixed(1)}%` : "";
const sorted = (counts) => Object.keys(counts).sort((a, b) => counts[b] - counts[a]);

export default class SeedStats extends React.Component {
    state = {presets: [], owner: null, choice: null, link: "", count: 100, running: false, rolled: 0, failed: 0,
             byItem: {}, byLoc: {}, item: null, loc: null, error: ""}

    componentDidMount() {
        doNetRequest("/preset/list", ({status, responseText}) => {
            if(status !== 200)
                return;
            const res = JSON.parse(responseText);
            this.setState({owner: res.owner, presets: res.settings || []});
        });
    }

    // a share link (".../?preset=owner:name") or "owner:name" wins over the dropdown
    settings = (done) => {
        const m = /(?:preset=)?([^:/?&=]+):([^&]+)$/.exec(this.state.link.trim());
        if(m) {
            doNetRequest(`/preset/${encodeURIComponent(m[1])}/${encodeURIComponent(decodeURIComponent(m[2]))}`, ({status, responseText}) =>
                status === 200 ? done(JSON.parse(responseText).settings) : this.setState({error: "No such preset: " + this.state.link}));
            return;
        }
        const hit = this.state.presets.find(p => p.name === (this.state.choice || {}).value);
        if(!hit)
            return this.setState({error: "Pick one of your presets or paste a preset link."});
        done(hit.blob);
    }

    start = () => this.settings(blob => {
        this.setState({running: true, rolled: 0, failed: 0, byItem: {}, byLoc: {}, error: ""}, () => this.batch(blob, this.state.count));
    })

    batch = (blob, left) => {
        if(!this.state.running || left <= 0)
            return this.setState({running: false});
        const seeds = [...Array(Math.min(BATCH, left)).keys()].map(() => `stats${Math.floor(Math.random() * 1e9)}`);
        const req = new XMLHttpRequest();
        req.onreadystatechange = () => {
            if(req.readyState !== 4)
                return;
            if(req.status !== 200)
                return this.setState({running: false, error: req.responseText || `The server said ${req.status}.`});
            this.tally(JSON.parse(req.responseText).rolls);
            this.batch(blob, left - seeds.length);
        };
        req.open("POST", "/seedstats/roll", true);
        req.setRequestHeader("Content-type", "application/json");
        req.send(JSON.stringify({settings: blob, seeds: seeds}));
    }

    tally = (rolls) => this.setState(prev => {
        const byItem = {...prev.byItem}, byLoc = {...prev.byLoc};
        let rolled = prev.rolled, failed = prev.failed;
        rolls.forEach(r => {
            if(!r.placements)
                return failed++;
            rolled++;
            r.placements.forEach(([loc, code, id]) => {
                const key = `${code}|${id}`;
                byItem[key] = {...(byItem[key] || {}), [loc]: ((byItem[key] || {})[loc] || 0) + 1};
                byLoc[loc] = {...(byLoc[loc] || {}), [key]: ((byLoc[loc] || {})[key] || 0) + 1};
            });
        });
        return {byItem, byLoc, rolled, failed};
    })

    table = (counts, label, head) => (
        <Table size="sm" bordered>
            <thead><tr><th>{head}</th><th>Seeds</th><th>Share</th></tr></thead>
            <tbody>{sorted(counts).map(k => (
                <tr key={k}><td>{label(k)}</td><td>{counts[k]}</td><td>{pct(counts[k], this.state.rolled)}</td></tr>
            ))}</tbody>
        </Table>
    )

    render() {
        const {presets, owner, choice, link, count, running, rolled, failed, byItem, byLoc, item, loc, error} = this.state;
        const itemOptions = sorted(Object.fromEntries(Object.keys(byItem).map(k => [k, Object.values(byItem[k]).reduce((a, b) => a + b, 0)])))
            .map(k => ({value: k, label: itemName(k)}));
        const locOptions = Object.keys(byLoc).map(l => ({value: l, label: locName(l)})).sort((a, b) => a.label.localeCompare(b.label));
        return (
            <Container className="pl-4 pr-4 pb-4 pt-2 mt-2">
                <SiteBar user={owner}/>
                <h3 className="mt-3">Seed stats</h3>
                <p>Rolls one preset many times and counts where each item lands. Each roll is a new seed string; nothing is saved.</p>
                <Row className="align-items-center mb-2">
                    <Col xs="4">
                        <Select styles={select_styles} theme={select_theme} placeholder={owner ? "One of your presets" : "Log in to use your presets"}
                                options={presets.map(p => ({value: p.name, label: p.name}))} value={choice} onChange={c => this.setState({choice: c})}/>
                    </Col>
                    <Col xs="4"><Input placeholder="or a preset link / owner:name" value={link} onChange={e => this.setState({link: e.target.value})}/></Col>
                    <Col xs="1"><Input type="number" min="1" max="2000" value={count} onChange={e => this.setState({count: parseInt(e.target.value, 10) || 0})}/></Col>
                    <Col xs="3">
                        {running ? <Button color="secondary" onClick={() => this.setState({running: false})}>Stop</Button>
                                 : <Button color="primary" disabled={!owner} onClick={this.start}>Roll {count} seeds</Button>}
                    </Col>
                </Row>
                {error ? <p className="text-danger">{error}</p> : null}
                {rolled + failed > 0 ? (
                    <div className="mb-3">
                        <Progress value={100 * (rolled + failed) / Math.max(count, 1)}/>
                        <small>{rolled} rolled{failed ? `, ${failed} failed to generate` : ""}</small>
                    </div>) : null}
                {rolled > 0 ? (
                    <Row>
                        <Col xs="6">
                            <h5>Where an item lands</h5>
                            <Select styles={select_styles} theme={select_theme} options={itemOptions} value={item} onChange={i => this.setState({item: i})}/>
                            {item && byItem[item.value] ? this.table(byItem[item.value], locName, "Location") : null}
                        </Col>
                        <Col xs="6">
                            <h5>What a location holds</h5>
                            <Select styles={select_styles} theme={select_theme} options={locOptions} value={loc} onChange={l => this.setState({loc: l})}/>
                            {loc && byLoc[loc.value] ? this.table(byLoc[loc.value], itemName, "Item") : null}
                        </Col>
                    </Row>) : null}
                <SiteFooter/>
            </Container>
        );
    }
}
