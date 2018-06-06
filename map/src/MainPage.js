import './bootstrap.cyborg.min.css';
import './index.css';
import React from 'react';
import Helmet from 'react-helmet';



export default class MainPage extends React.Component {
  constructor(props) {
    super(props);
    this.state = {};
	}
	
	render = () => {
		let latest_dll = ""
		let plando_version = ""
		return (
		<div style={{color: "black"}}>
		<Helmet bodyAttributes={{style: 'background-color : white'}}/>
		<table><tbody><tr>
	    <td><a href="https://github.com/turntekGodhead/OriDERandomizer/raw/master/Assembly-CSharp.dll">latest dll (last updated {{latest_dll}})</a></td>
        <td><a href="/activeGames">Games list</a></td>
        <td><a href="/plando/simple">Plandomizer Editor! ({{plando_version}})</a></td>
		<td><a href="/plando/all">Plando Repository</a></td>
		<td><a href="/login">Login</a></td>
	</tr></tbody></table>
		Hi Friends!
		<table>
		<tbody><tr><td>
		TEST TESTESTTESTTEST TEST TESTTEST!
		</td></tr></tbody>
		</table>
		</div>
	)

	}
};

