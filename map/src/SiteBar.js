import React from 'react';
import {Navbar,  NavbarBrand, Nav,  NavItem,  NavLink, UncontrolledDropdown, DropdownToggle, DropdownMenu, DropdownItem} from 'reactstrap'
const SiteBar = ({dlltime, user}) => {	
	let logonoff = user ? [
		(<DropdownItem href={"/plando/"+ user}> {user}'s seeds </DropdownItem>),
		(<DropdownItem href="/logout">  Logout </DropdownItem>)
	] :  (<DropdownItem href="/login"> Login </DropdownItem>) 

	return (
		<Navbar className="border border-dark p-2" expand="md">
		<NavbarBrand href="/">Ori DE Randomizer</NavbarBrand>
			<Nav className="ml-auto" navbar>
			<UncontrolledDropdown nav inNavbar>
				<DropdownToggle nav caret>
				Downloads
				</DropdownToggle>
				<DropdownMenu right>
				<DropdownItem href="https://github.com/sigmasin/OriDERandomizer/blob/master/Assembly-CSharp.dll">
					Tournament 2.6 dll (Currently recommended: works for everything but bonus pickups and warmth fragments)
				</DropdownItem>
				<DropdownItem href="https://github.com/sigmasin/OriDERandomizer/blob/master/OriDERandoDecoder.dll">
					Decoder DLL (required for 2.6: place in same folder)				
				</DropdownItem>
				<DropdownItem href="/vanilla">
					Vanilla Seed
				</DropdownItem>
				<DropdownItem href="https://github.com/turntekGodhead/OriDERandomizer/raw/master/Assembly-CSharp.dll">
					Experimental dll (Not currently recommended. Last Updated {dlltime})
				</DropdownItem>
				<DropdownItem href="https://github.com/david-c-miller/OriDETracker/releases/download/v3.0-beta/OriDETracker-v3.0-beta.zip">
					Beta Tracker
				</DropdownItem>
				</DropdownMenu>
			</UncontrolledDropdown>
			<NavItem>
				<NavLink href={"/activeGames"}>Active Games</NavLink>
			</NavItem>
			<NavItem>
				<NavLink href={"/logichelper"}>Interactive Logic Helper</NavLink>
			</NavItem>
			<UncontrolledDropdown nav inNavbar>
				<DropdownToggle nav caret>
				Bingo
				</DropdownToggle>
				<DropdownMenu right>
				<DropdownItem href="/bingo">
					Generate Board
				</DropdownItem>
				<DropdownItem href="https://bingosync.com/">
					Start Bingo Game
				</DropdownItem>
				</DropdownMenu>
			</UncontrolledDropdown>
				
			<UncontrolledDropdown nav inNavbar>
				<DropdownToggle nav caret>
				Plandomizer
				</DropdownToggle>
				<DropdownMenu right>
				<DropdownItem href="/plando/simple">
					Open Plando Editor
				</DropdownItem>
				<DropdownItem href="/plando/all">
					View All Seeds
				</DropdownItem>
				<DropdownItem divider />
				{logonoff}
				</DropdownMenu>
			</UncontrolledDropdown>
			</Nav>
		</Navbar>
	)
};
export default SiteBar;