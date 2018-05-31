import React from 'react';
import ReactDOM from 'react-dom';
import GameTracker from './GameTracker';
import SeedDisplayPage from './SeedDisplayPage';
import PlandoBuilder from './PlandoBuilder';
if(document.getElementById('gameTracker'))
	ReactDOM.render(<GameTracker />, document.getElementById('gameTracker'));
if(document.getElementById('plandoBuilder'))
	ReactDOM.render(<PlandoBuilder />, document.getElementById('plandoBuilder'));
if(document.getElementById('seedDisplay'))
	ReactDOM.render(<SeedDisplayPage/>, document.getElementById('seedDisplay'));
if(document.getElementById('MainPage'))
    ReactDOM.render(<MainPage />, document.getElementById('mainPage'));

//registerServiceWorker();
