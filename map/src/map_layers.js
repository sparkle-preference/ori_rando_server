import React, {Component, Fragment} from 'react';
import Leaflet from 'leaflet';
import {ImageOverlay, Pane} from 'react-leaflet';
import Control from 'react-leaflet-control';
import {Badge, Button, ButtonGroup} from 'reactstrap';

// the pictures the game fetches; the branch moves when the client's does
const SOURCE = "https://cdn.jsdelivr.net/gh/sparkle-preference/ori_rando_server@4.3/map_layers/";
const SETS = ["misty", "forlorn_escape", "horu_escape"];
// hides the tiles' own Misty picture, so it sits where the tiles draw Misty, not at world coords
const COVER = "/static/map_layers/misty_cover.png";
const COVER_BOUNDS = [[-39.57, -1092.94], [26.93, -594.44]];
const STORE_KEY = "misty_layout";

function parse_sheet(set, text) {
    let sheet = {set: set, order: [], bounds: {}, names: {}, whole: {}};
    let rect = (pic, [x0, y0, x1, y1]) => { sheet.bounds[pic] = [[+y0, +x0], [+y1, +x1]] };
    text.split("\n").forEach(line => {
        let p = line.trim().split(/\s+/);
        if(/^\d+$/.test(p[0])) {
            sheet.order.push(p[0]);
            rect(p[0], p.slice(1, 5));
        }
        else if(p[0] === "picture") rect(p[1], p.slice(2, 6));
        else if(p[0] === "name") sheet.names[p[1]] = p.slice(2).join(" ");
        else if(p[0] === "whole") sheet.whole[p[2]] = p[1];
    });
    return sheet;
}

const stem = (sheet, pic) => `${sheet.set}_${String(pic).padStart(2, "0")}`;

// the game tells these two apart by the save; with no save they are one picture, shown once
const MERGED = {drop: "8", keep: "9", name: "Completed"};

// only while the manifest says they are the same files: if they ever differ, both names return
function merge_same(sheet, sums) {
    let files = (layer) => [".jpg", "_alpha.png"].map(end => sums[stem(sheet, sheet.whole[layer] || layer) + end]);
    let kept = files(MERGED.keep);
    if(!files(MERGED.drop).every((sum, i) => sum && sum === kept[i]))
        return;
    sheet.order = sheet.order.filter(layer => layer !== MERGED.drop);
    sheet.names[MERGED.keep] = MERGED.name;
}

const parse_sums = (text) => text.split("\n").reduce((sums, line) => {
    let [file, sum] = line.trim().split(/\s+/);
    if(sum)
        sums[file] = sum;
    return sums;
}, {});

const get_text = (name) => fetch(SOURCE + name).then(res => res.ok ? res.text() : Promise.reject(res.status));

let sheets = null;
const get_sheets = () => sheets || (sheets = Promise.all([
    get_text("manifest.txt").then(parse_sums).catch(() => ({})),
    ...SETS.map(set => get_text(`${set}_layers.txt`).then(text => parse_sheet(set, text)).catch(() => null))
]).then(([sums, misty, ...escapes]) => {
    if(misty)
        merge_same(misty, sums);
    return [misty, ...escapes];
}));

const load_image = (url) => new Promise((done, fail) => {
    let img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => done(img);
    img.onerror = fail;
    img.src = url;
});

// a layer is a JPEG plus a gray mask: one decoded image with the mask as its alpha
function join_alpha([rgb, alpha]) {
    let canvas = document.createElement("canvas");
    let w = canvas.width = rgb.naturalWidth, h = canvas.height = rgb.naturalHeight;
    let ctx = canvas.getContext("2d");
    ctx.drawImage(alpha, 0, 0, w, h);
    let mask = ctx.getImageData(0, 0, w, h).data;
    ctx.drawImage(rgb, 0, 0);
    let pixels = ctx.getImageData(0, 0, w, h);
    for(let i = 0; i < mask.length; i += 4)
        pixels.data[i + 3] = mask[i];
    ctx.putImageData(pixels, 0, 0);
    return new Promise(done => canvas.toBlob(done)).then(blob => {
        let img = new Image();
        img.src = URL.createObjectURL(blob);
        return img.decode().then(() => img);
    });
}

const pictures = {};
function get_picture(file) {
    if(!pictures[file])
        pictures[file] = Promise.all([load_image(file + ".jpg"), load_image(file + "_alpha.png")]).then(join_alpha)
            .catch(err => { delete pictures[file]; throw err; });
    return pictures[file];
}

const file_of = (sheet, pic) => SOURCE + stem(sheet, pic);

function recall(sheet) {
    let layer = null;
    try { layer = localStorage.getItem(STORE_KEY) } catch(e) {}
    // a choice of the merged-away layout is a choice of the one that stands for it
    return layer === MERGED.drop && !sheet.order.includes(layer) ? MERGED.keep : layer;
}
function remember(layer) {
    try { localStorage.setItem(STORE_KEY, layer) } catch(e) {}
}

// keeps its own state: a layout step must not re-render the page around the map
class MapLayers extends Component {
    // any validator will do: naming the key is what hands over react-leaflet's map
    static contextTypes = {map: () => null}

    state = {misty: null, at: 0, named: 0, ready: {}, shown: null, near: false}

    componentDidMount() {
        this.mounted = true;
        get_sheets().then(([misty, ...escapes]) => {
            if(!this.mounted)
                return;
            escapes.forEach(sheet => sheet && this.load(sheet, sheet.order[0]).catch(() => {}));
            if(!misty || !misty.order.length)
                return;
            let at = Math.max(0, misty.order.indexOf(recall(misty)));
            this.area = Leaflet.latLngBounds(Object.values(misty.bounds).reduce((all, rect) => all.concat(rect), []));
            this.context.map.on("move", this.look);
            this.setState({misty: misty, at: at, named: at}, () => {
                this.look();
                this.show();
                this.fetch_ahead(1);
            });
        });
    }
    componentWillUnmount() {
        this.mounted = false;
        this.context.map.off("move", this.look);
    }
    // a hidden control must not swallow clicks meant for the map
    componentDidUpdate() {
        if(this.box && this.box.parentNode)
            this.box.parentNode.style.pointerEvents = this.state.near ? "" : "none";
    }

    load = (sheet, pic) => {
        let file = file_of(sheet, pic);
        return get_picture(file).then(img => {
            if(this.mounted && !this.state.ready[file])
                this.setState(prev => ({ready: {...prev.ready, [file]: {img: img, bounds: sheet.bounds[pic], set: sheet.set}}}));
            return file;
        });
    }
    // the site has no save to read, so a layout shows its fullest picture
    picture = (i) => {
        let {misty} = this.state;
        return misty.whole[misty.order[i]] || misty.order[i];
    }
    show = () => {
        let at = this.state.at;
        this.load(this.state.misty, this.picture(at)).then(file => {
            // the name moves with the picture, and a later press may have moved on meanwhile
            if(this.mounted && at === this.state.at)
                this.setState({shown: file, named: at});
        }).catch(() => {});
    }
    // the rest, one at a time and in order from the one shown, so a press finds its picture in
    fetch_ahead = (n) => {
        let {misty, at} = this.state;
        if(!this.mounted || n >= misty.order.length)
            return;
        let next = () => this.fetch_ahead(n + 1);
        this.load(misty, this.picture((at + n) % misty.order.length)).then(next, next);
    }
    step = (by) => {
        let count = this.state.misty.order.length;
        this.setState(prev => ({at: (prev.at + by + count) % count}), () => {
            remember(this.state.misty.order[this.state.at]);
            this.show();
        });
    }
    back = () => this.step(-1)
    next = () => this.step(1)
    // only while Misty is in view
    look = () => {
        let near = this.context.map.getBounds().intersects(this.area);
        if(near !== this.state.near)
            this.setState({near: near});
    }
    // a double click on an arrow would zoom the map under it
    quiet = (el) => {
        this.box = el;
        if(el)
            Leaflet.DomEvent.disableClickPropagation(el);
    }

    render() {
        let {misty, named, ready, shown, near} = this.state;
        // every layout stays mounted, hidden, so a step is a fade between two loaded pictures
        let overlays = Object.keys(ready).map(file => {
            let {img, bounds, set} = ready[file];
            return (<ImageOverlay key={file} url={img} bounds={bounds} zIndex={2} className="layout-picture" opacity={set !== "misty" || file === shown ? 1 : 0} />);
        });
        let cycle = misty ? (
            <Control position="topleft">
                <div ref={this.quiet} className={"layout-cycle" + (near ? "" : " away")}>
                    <ButtonGroup vertical size="sm">
                        <Button color="secondary" title="Previous Misty layout" onClick={this.back}>▲</Button>
                        <Button color="secondary" title="Next Misty layout" onClick={this.next}>▼</Button>
                    </ButtonGroup>
                    <Badge color="secondary" className="layout-label" title="Currently displayed Misty layout">
                        {/* every name shares the one cell, unseen, so the box is always as wide as the longest */}
                        {misty.order.map(layer => (<i key={layer}>{misty.names[layer] || layer}</i>))}
                        <span className="layout-name">{misty.names[misty.order[named]] || misty.order[named]}</span>
                    </Badge>
                </div>
            </Control>
        ) : null;
        return (
            <Fragment>
                {/* over the tiles, under every shape and marker */}
                <Pane name="map-layers" style={{zIndex: 250}}>
                    {shown ? (<ImageOverlay url={COVER} bounds={COVER_BOUNDS} zIndex={1} />) : null}
                    {overlays}
                </Pane>
                {cycle}
            </Fragment>
        );
    }
}

export default MapLayers;
