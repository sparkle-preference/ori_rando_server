import React from 'react';
import {Container, Row, Col, Card, CardBody, CardHeader, Badge, Button, ButtonGroup, Collapse} from 'reactstrap';
import {Helmet} from 'react-helmet';

import './patchnotes.css';
import {get_param} from "./common.js"
import SiteBar from "./SiteBar.js"
import {RELEASES, CATEGORIES} from "./patchnotes_data.js"

const TYPE_LABELS = {feature: "Feature", fix: "Bugfix"};
const TYPE_COLORS = {feature: "success", fix: "secondary"};
const TAG_COLORS = {Archipelago: "primary", Multiworld: "info"};

const isOn = (change, everything) => everything || change.importance === "major";

// Within a category: Features, then Bugfixes, then changes that are neither
// (credits, an event ending, an option being retired). Archipelago sinks to the
// bottom of whichever section it lands in -- it's still alpha.
const TYPE_RANK = {feature: 0, fix: 1};
const sortKey = (c) => [
    (c.tags || []).includes("Archipelago") ? 1 : 0,
    c.type in TYPE_RANK ? TYPE_RANK[c.type] : 2,
    c.importance === "major" ? 0 : 1,
];
const byTagCombo = (a, b) => {
    let ka = sortKey(a), kb = sortKey(b)
    for(let i = 0; i < ka.length; i++)
        if(ka[i] !== kb[i])
            return ka[i] - kb[i]
    return 0
};

const Change = ({change, everything}) => (
    <div className={"pn-item" + (isOn(change, everything) ? "" : " pn-off")}>
        <div className="pn-inner">
            {change.type ? (
                <Badge className="mr-1" color={TYPE_COLORS[change.type]}>{TYPE_LABELS[change.type]}</Badge>
            ) : null}
            {(change.tags || []).map(t => (
                <Badge key={t} pill className="mr-1" color={TAG_COLORS[t] || "secondary"}>{t}</Badge>
            ))}
            {change.text}
            {change.sub ? (
                <div className="pn-sub mt-1">
                    {change.sub.map((s, i) => <div key={i}><small>{s}</small></div>)}
                </div>
            ) : null}
        </div>
    </div>
)

class Spoilers extends React.Component {
    state = {shown: false}
    render = () => {
        let {label, changes} = this.props
        let {shown} = this.state
        return (
            <div className="mt-3 p-2 border rounded">
                <Button size="sm" color="secondary" onClick={() => this.setState({shown: !shown})}>
                    {shown ? "Hide" : "Show"} {label}
                </Button>
                <Collapse isOpen={shown}>
                    <div className="mt-2">
                        {changes.map((c, i) => <Change key={i} change={c} everything={true}/>)}
                    </div>
                </Collapse>
            </div>
        )
    }
}

const Release = ({release, everything, latest, onShowEverything}) => {
    let groups = CATEGORIES
        .map(cat => ({cat, items: release.changes.filter(c => c.category === cat).sort(byTagCombo)}))
        .filter(g => g.items.length > 0)
    let anyVisible = release.changes.some(c => isOn(c, everything))

    return (
        <Card className={"mb-3" + (latest ? " border-primary pn-latest" : "")} id={release.version}>
            <CardHeader tag="h5" className="d-flex align-items-center flex-wrap">
                <a href={"#" + release.version} className="mr-2" title="Link to this release">
                    {release.version}
                </a>
                {latest ? <Badge color="primary" className="mr-2">Latest</Badge> : null}
                {release.title ? <span className="mr-2 font-weight-normal">{release.title}</span> : null}
                <small className="ml-auto text-muted font-weight-normal">{release.date}</small>
            </CardHeader>
            <CardBody>
                {release.headline ? <p>{release.headline}</p> : null}
                {!anyVisible ? (
                    <p className="text-muted mb-0">
                        <small>Just small fixes in this one. </small>
                        <Button color="link" size="sm" className="p-0 align-baseline" onClick={onShowEverything}>
                            <small>Show everything</small>
                        </Button>
                    </p>
                ) : null}
                {groups.map(({cat, items}) => {
                    let on = items.some(c => isOn(c, everything))
                    return (
                        <div key={cat} className={"pn-group" + (on ? "" : " pn-off")}>
                            <div className="pn-inner">
                                <h6 className="text-muted text-uppercase">{cat}</h6>
                                {items.map((c, i) => <Change key={i} change={c} everything={everything}/>)}
                            </div>
                        </div>
                    )
                })}
                {release.spoilers ? <Spoilers {...release.spoilers}/> : null}
            </CardBody>
        </Card>
    )
}

// versions grouped by their major.minor line, for the jump list
const versionLines = () => {
    let lines = []
    RELEASES.forEach(r => {
        let line = r.version.split(".").slice(0, 2).join(".")
        let last = lines[lines.length - 1]
        if(!last || last.line !== line)
            lines.push({line, versions: [r.version]})
        else
            last.versions.push(r.version)
    })
    return lines
}

export default class PatchNotes extends React.Component {
    state = {user: get_param("user"), everything: false}

    componentDidMount() {
        // deep links from discord land on a specific version
        let target = decodeURIComponent(window.location.hash.replace("#", ""))
        if(target && RELEASES.some(r => r.version === target))
            this.scrollTo(target)
    }

    scrollTo = (version) => {
        let el = document.getElementById(version)
        if(el)
            setTimeout(() => window.scrollTo({top: el.offsetTop, behavior: "smooth"}), 100)
    }

    jumpTo = (version) => (e) => {
        e.preventDefault()
        this.scrollTo(version)
        window.history.replaceState(null, "", "#" + version)
    }

    render = () => {
        let {user, everything} = this.state
        return (
            <Container className="pl-4 pr-4 pb-4 pt-2 mt-2 w-75 border">
                <Helmet><title>Patch Notes</title></Helmet>
                <SiteBar user={user}/>
                <Card className="w-100 mb-3">
                    <CardBody>
                        <CardHeader tag="h2" className="mb-3 text-center">Patch Notes</CardHeader>
                        <Row className="align-items-center">
                            <Col xs="12" md="auto" className="mb-2 mb-md-0">
                                <ButtonGroup>
                                    <Button
                                        color="primary"
                                        outline={everything}
                                        onClick={() => this.setState({everything: false})}
                                    >
                                        Highlights
                                    </Button>
                                    <Button
                                        color="primary"
                                        outline={!everything}
                                        onClick={() => this.setState({everything: true})}
                                    >
                                        Everything
                                    </Button>
                                </ButtonGroup>
                            </Col>
                            <Col className="text-md-right">
                                <small className="text-muted">
                                    {everything
                                        ? "Every change that shipped, down to the small fixes."
                                        : "The changes worth knowing about."}
                                </small>
                            </Col>
                        </Row>
                    </CardBody>
                </Card>
                <Row>
                    <Col xs="12" md="9">
                        {RELEASES.map((r, i) => (
                            <Release
                                key={r.version}
                                release={r}
                                everything={everything}
                                latest={i === 0}
                                onShowEverything={() => this.setState({everything: true})}
                            />
                        ))}
                    </Col>
                    <Col xs="12" md="3" className="d-none d-md-block">
                        <div style={{position: 'sticky', top: '1rem'}}>
                            <Card>
                                <CardBody className="p-2">
                                    <h6 className="text-muted text-uppercase mb-2">Versions</h6>
                                    {versionLines().map(({line, versions}) => (
                                        <div key={line} className="pn-version-line">
                                            <small className="text-muted">{line}</small>
                                            <div className="pn-versions">
                                                {versions.map(v => (
                                                    <a
                                                        key={v}
                                                        href={"#" + v}
                                                        onClick={this.jumpTo(v)}
                                                    >
                                                        <small>{v}</small>
                                                    </a>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </CardBody>
                            </Card>
                        </div>
                    </Col>
                </Row>
            </Container>
        );
    };
}
