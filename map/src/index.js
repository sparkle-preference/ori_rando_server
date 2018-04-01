import React from 'react';
import ReactDOM from 'react-dom';
import './index.css';
import GameTracker from './GameTracker';
import PlandoBuilder from './PlandoBuilder';
if(document.getElementById('gameTracker'))
	ReactDOM.render(<GameTracker />, document.getElementById('gameTracker'));
if(document.getElementById('plandoBuilder'))
	ReactDOM.render(<PlandoBuilder />, document.getElementById('plandoBuilder'));

//registerServiceWorker();
