import React from 'react';
import ReactDOM from 'react-dom';
import {get_param, get_flag, gotoUrl} from './common.js';

import ItemTracker from './ItemTracker';
import MainPage from './MainPage';
import GameTracker from './GameTracker';
import PlandoBuilder from './PlandoBuilder';
import SeedAnalysis from './SeedAnalysis';
import RebindingsEditor from './RebindingsEditor';
import LogicHelper from './LogicHelper';
import SeedDisplayPage from './SeedDisplayPage';
import HelpAndGuides from './HelpAndGuides';
import Bingo from './Bingo';

const mods = {
    ItemTracker,
    MainPage,
    GameTracker,
    PlandoBuilder,
    SeedAnalysis, 
    RebindingsEditor,
    LogicHelper,
    SeedDisplayPage,
    HelpAndGuides,
    Bingo  
};

const dark_apps = ["GameTracker", "PlandoBuilder", "LogicHelper"];
const VALID_THEMES = ["cerulean", "cosmo", "cyborg", "darkly", "flatly", "journal", "litera", "lumen", "lux", "materia", "minty", "pulse", "sandstone", "simplex", "sketchy", "slate", "solar", "spacelab", "superhero", "united", "yeti"];

(async () => {
    if(localStorage.getItem("rememberMe") && !get_param('user'))
        return gotoUrl(`/login?redir=${encodeURIComponent(window.document.URL.split(".com")[1])}`);
    let dark = get_param("dark") != null ? get_flag("dark") : localStorage.getItem("dark");
    let theme = get_param("theme") || localStorage.getItem("theme");
    if(theme && !localStorage.getItem("theme")){
        localStorage.setItem("theme", theme);
    }
        
    if(dark){
        localStorage.setItem("dark", "true");
    }else{
        localStorage.removeItem("dark");
    }

    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.type = "text/css";
    link.id = "css_switcher";
    let css = 'https://maxcdn.bootstrapcdn.com/bootswatch/4.2.1/flatly/bootstrap.min.css'
    if(VALID_THEMES.includes(theme)) {
        css = `https://maxcdn.bootstrapcdn.com/bootswatch/4.2.1/${theme}/bootstrap.min.css`
    }
    else if(dark) {
        css = 'https://maxcdn.bootstrapcdn.com/bootswatch/4.2.1/darkly/bootstrap.min.css'
    }
    link.href = css;
    document.getElementsByTagName("head")[0].appendChild(link);
    
    const root = document.getElementById("root");

    const app = root.dataset.app;

    if(dark_apps.includes(app)) {
        link.href = 'https://maxcdn.bootstrapcdn.com/bootswatch/4.2.1/darkly/bootstrap.min.css'
    }
    const Content = mods[app];
    ReactDOM.render(<Content />, root);
})()
