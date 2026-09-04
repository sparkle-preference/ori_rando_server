import React from 'react';
import ReactDOM from 'react-dom';
import {get_param, report_error, resolve_dark, save_dark, theme_href} from './common.js';

import ItemTracker from './ItemTracker';
import MainPage from './MainPage';
import GameTracker from './GameTracker';
import PlandoBuilder from './PlandoBuilder';
import RebindingsEditor from './RebindingsEditor';
import LogicHelper from './LogicHelper';
import SeedDisplayPage from './SeedDisplayPage';
import HelpAndGuides from './HelpAndGuides';
import PatchNotes from './PatchNotes';
import Bingo from './Bingo';

const mods = {
    ItemTracker,
    MainPage,
    GameTracker,
    PlandoBuilder,
    RebindingsEditor,
    LogicHelper,
    SeedDisplayPage,
    HelpAndGuides,
    PatchNotes,
    Bingo
};

// A render crash used to leave a white page. This shows what broke, reports it, and offers
// the two ways back in. The buttons are plain: the theme may be part of the problem.
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props)
        this.state = {error: null}
    }

    static getDerivedStateFromError(error) {
        return {error: error}
    }

    componentDidCatch(error, info) {
        report_error("render", error, info)
    }

    render() {
        if(!this.state.error)
            return this.props.children
        const fresh = window.location.pathname + "?fresh=1"
        const style = {fontFamily: "sans-serif", maxWidth: "40em", margin: "4em auto", padding: "1em 2em", border: "1px solid #999", borderRadius: "6px", background: "#fff", color: "#222"}
        const button = {margin: "0.5em 1em 0.5em 0", padding: "0.5em 1em", fontSize: "1em"}
        return (
            <div style={style}>
                <h2>The page hit an error</h2>
                <p>It has been reported. Reloading usually works; if it doesn't, the second button opens the page without your last seed's settings.</p>
                <button style={button} onClick={() => window.location.reload()}>Reload</button>
                <button style={button} onClick={() => { window.location.href = fresh }}>Reload without last seed</button>
                <pre style={{whiteSpace: "pre-wrap", fontSize: "0.8em", color: "#666"}}>{String(this.state.error && this.state.error.stack || this.state.error)}</pre>
            </div>
        )
    }
}

window.addEventListener("error", e => report_error("window", e.error || e.message))
window.addEventListener("unhandledrejection", e => report_error("promise", e.reason))

const dark_apps = ["GameTracker", "PlandoBuilder", "LogicHelper"];
const MODES = ["system", "light", "dark"];

(async () => {
    let dark = resolve_dark();
    // one server-validated value; a mode defers to resolve_dark, anything else is a skin
    let theme = get_param("theme");

    // mirror the account setting into this browser, but never persist a
    // browser preference: storing it would freeze the theme against the OS
    if(get_param("dark") != null){
        save_dark(dark);
    }

    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.type = "text/css";
    link.id = "css_switcher";
    link.href = theme_href((theme && !MODES.includes(theme)) ? theme : (dark ? "darkly" : "flatly"));
    document.getElementsByTagName("head")[0].appendChild(link);
    
    const root = document.getElementById("root");

    const app = root.dataset.app;

    if(dark_apps.includes(app)) {
        link.href = theme_href("darkly")
    }
    const Content = mods[app];
    ReactDOM.render(<ErrorBoundary><Content /></ErrorBoundary>, root);
})()
