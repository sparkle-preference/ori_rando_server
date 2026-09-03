import React from 'react';
import ReactDOM from 'react-dom';
import {get_param, resolve_dark, save_dark, theme_href} from './common.js';

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
    ReactDOM.render(<Content />, root);
})()
