import React from 'react';
import ReactDOM from 'react-dom';
import GameTracker from './GameTracker';

it('renders without crashing', () => {
  const div = document.createElement('div');
  ReactDOM.render(<GameTracker />, div);
  ReactDOM.unmountComponentAtNode(div);
});
