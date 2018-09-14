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
				<DropdownItem href="https://github.com/sigmasin/OriDERandomizer/raw/master/Assembly-CSharp.dll">
					2.6 (Tournament) DLL
				</DropdownItem>
				<DropdownItem href="https://github.com/sigmasin/OriDERandomizer/raw/master/OriDERandoDecoder.dll">
					Decoder DLL (required for 2.6: place in same folder)				
				</DropdownItem>
				<DropdownItem href="/vanilla">
					Vanilla Seed
				</DropdownItem>
				<DropdownItem href="https://github.com/sigmasin/OriDERandomizer/raw/3.0/Assembly-CSharp.dll">
					3.0 Beta DLL
				</DropdownItem>
				<DropdownItem href="https://github.com/david-c-miller/OriDETracker/releases/download/v3.0-beta/OriDETracker-v3.0-beta.zip">
					3.0 Beta Skill Tracker
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