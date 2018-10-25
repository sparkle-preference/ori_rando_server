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
                    <DropdownItem href="https://github.com/sigmasin/OriDERandomizer/raw/3.0/Assembly-CSharp.dll">
                        3.0 DLL 
                    </DropdownItem>
                    <DropdownItem href="https://github.com/turntekGodhead/OriDETracker/raw/master/OriDETracker/bin/Latest.zip">
                        3.0 Tracker (Beta)
                    </DropdownItem>
                    <DropdownItem href="/vanilla">
                        Vanilla Seed
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