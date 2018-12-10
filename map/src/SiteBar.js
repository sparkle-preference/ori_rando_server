import React from 'react';
import {Navbar,  NavbarBrand, Nav,  NavItem,  NavLink, UncontrolledDropdown, DropdownToggle, DropdownMenu, DropdownItem} from 'reactstrap'
const SiteBar = ({user, quickstartHook}) => {    
    let logonoff = user ? [
        (<DropdownItem href={"/plando/"+ user}> {user}'s seeds </DropdownItem>),
        (<DropdownItem href="/logout">  Logout </DropdownItem>)
    ] :  (<DropdownItem href="/login"> Login </DropdownItem>) 

    return (
        <Navbar className="border border-dark p-2" expand="md">
        <NavbarBrand href="/">Ori Rando</NavbarBrand>
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
                <NavLink href={"/quickstart"}>Start Playing</NavLink>
            </NavItem>
            <NavItem>
                <NavLink href={"/faq"}>Help</NavLink>
            </NavItem>
            <NavItem>
                <NavLink href={"https://goo.gl/csgRUw"}>Patch Notes</NavLink>
            </NavItem>
            <NavItem>
                <NavLink href={"/logichelper"}>Logic Helper</NavLink>
            </NavItem>
            <UncontrolledDropdown nav inNavbar>
                <DropdownToggle nav caret>
                Misc
                </DropdownToggle>
                <DropdownMenu right>
                <DropdownItem href="/rebinds">
                    Ori Keyboard Rebinding Helper
                </DropdownItem>
                <DropdownItem href="/bingo?rando=1">
                    Generate Bingo Board (rando)
                </DropdownItem>
                <DropdownItem href="/bingo">
                    Generate Bingo Board (vanilla+)
                </DropdownItem>
                <DropdownItem href="/vanillaplus">
                    Get Vanilla+ Seed
                </DropdownItem>
                <DropdownItem href="https://bingosync.com/">
                    Start Bingo Game
                </DropdownItem>
                </DropdownMenu>
            </UncontrolledDropdown>
                
            <UncontrolledDropdown nav inNavbar>
                <DropdownToggle nav caret>
                Plando
                </DropdownToggle>
                <DropdownMenu right>
                <DropdownItem href="/plando/newSeed/edit">
                    Open Plando Editor
                </DropdownItem>
                <DropdownItem href="/plandos">
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