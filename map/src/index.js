import 'bootstrap/dist/css/bootstrap.css';
import React from 'react';
import ReactDOM from 'react-dom';
import GameTracker from './GameTracker';
import SeedDisplayPage from './SeedDisplayPage';
import PlandoBuilder from './PlandoBuilder';
import LogicHelper from './LogicHelper';
import MainPage from './MainPage';
import SeedAnalysis from './SeedAnalysis';
if(document.getElementById('gameTracker'))
	ReactDOM.render(<GameTracker />, document.getElementById('gameTracker'));
if(document.getElementById('plandoBuilder'))
	ReactDOM.render(<PlandoBuilder />, document.getElementById('plandoBuilder'));
if(document.getElementById('logicHelper'))
	ReactDOM.render(<LogicHelper/>, document.getElementById('logicHelper'));
if(document.getElementById('seedDisplay'))
	ReactDOM.render(<SeedDisplayPage/>, document.getElementById('seedDisplay'));
if(document.getElementById('mainPage'))
    ReactDOM.render(<MainPage />, document.getElementById('mainPage'));
if(document.getElementById('seedAnalysis'))
    ReactDOM.render(<SeedAnalysis />, document.getElementById('seedAnalysis'));

//registerServiceWorker();
