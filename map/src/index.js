import React from 'react';
import ReactDOM from 'react-dom';
import {get_param, get_flag, gotoUrl} from './common.js';

const apps = ['ItemTracker', 'MainPage', 'GameTracker', 'PlandoBuilder', 'SeedAnalysis', 'RebindingsEditor', 'LogicHelper', 'SeedDisplayPage', "HelpAndGuides", "Bingo"];
const dark_apps = ["GameTracker", "PlandoBuilder", "LogicHelper"];
const VALID_THEMES = ["cerulean", "cosmo", "cyborg", "darkly", "flatly", "journal", "litera", "lumen", "lux", "materia", "minty", "pulse", "sandstone", "simplex", "sketchy", "slate", "solar", "spacelab", "superhero", "united", "yeti"];

(() => {
    if(localStorage.getItem("rememberMe") && !get_param('user'))
        return gotoUrl(`/login?redir=${encodeURIComponent(window.document.URL.split(".com")[1])}`)
    let dark = get_flag("dark") || localStorage.getItem("dark")
    let theme = get_param("theme") || localStorage.getItem("theme")
    if(theme && !localStorage.getItem("theme"))
        localStorage.setItem("theme", theme)
    if(dark)
        localStorage.setItem("dark", "true")
    else
        localStorage.removeItem("dark")
    apps.forEach(async (app) => {
        if(document.getElementById(app)) {
            let link = document.createElement("link");
            link.id = "css_switcher"
            link.type = "text/css";
            link.rel = "stylesheet";
            let css = 'https://maxcdn.bootstrapcdn.com/bootswatch/4.2.1/flatly/bootstrap.min.css'
            if(VALID_THEMES.includes(theme)) {
                css = `https://maxcdn.bootstrapcdn.com/bootswatch/4.2.1/${theme}/bootstrap.min.css`
            }
            else if(dark || dark_apps.includes(app)) {
                css = 'https://maxcdn.bootstrapcdn.com/bootswatch/4.2.1/darkly/bootstrap.min.css'
            }
            link.href = css;
            document.getElementsByTagName("head")[0].appendChild(link);
            let mod = await import(`./${app}`);
            let Content = mod.default;
            ReactDOM.render(<Content />, document.getElementById(app));
        }
    })
})()