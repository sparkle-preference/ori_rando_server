import 'bootstrap/dist/css/bootstrap.css';
import React from 'react';
import ReactDOM from 'react-dom';
const apps = ['MainPage', 'GameTracker', 'SeedDisplayPage', 'PlandoBuilder', 'SeedAnalysis', 'RebindingsEditor', 'LogicHelper', 'SeedDisplayPage'];

(() => {
    apps.forEach(async (app) => {
        if(document.getElementById(app))
        {
            let mod = await import(`./${app}`);
            let Content = mod.default;
            ReactDOM.render(<Content />, document.getElementById(app));
        }
    })    
})()