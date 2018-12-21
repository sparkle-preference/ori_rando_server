import React, {Component} from 'react';
import {Navbar,  NavbarBrand, Nav,  NavItem,  NavLink, Button, Modal, ModalHeader, ModalBody, ModalFooter,
        UncontrolledDropdown, DropdownToggle, DropdownMenu, DropdownItem, Container, Row, Col, Input} from 'reactstrap'
import {Cent} from './common.js';

class SiteBar extends Component {
    constructor(props) {
        super(props);
        let {user} = props;
        this.state = {user: user, settingsOpen: false, quickstartOpen: false, editName: user}
    }
    closeModals = () => this.setState({settingsOpen: false, quickstartOpen: false})
    settingsModal = () =>  { return (
        <Modal isOpen={this.state.settingsOpen} backdrop={"static"} className={"modal-dialog-centered"} toggle={this.closeModals}>
            <ModalHeader toggle={this.closeModals} centered="true">User settings</ModalHeader>
            <ModalBody>
                <Container fluid>
                    <Row className="p-1">
                        <Col xs="4" className="text-center p-1 border">
                            <Cent>Display name</Cent>
                        </Col><Col xs="4">
                            <Input type="text" value={this.state.editName}  onChange={(e) => this.setState({editName: e.target.value})}/> 
                        </Col>
                    </Row>
                    <Row className="p-1">
                        <Col xs="4" className="text-center p-1 border">
                            <Cent>color</Cent>
                        </Col><Col xs="4">
                            <Input type="text" value={this.state.userColor}  onChange={(e) => this.setState({userColor: e.target.value})}/> 
                        </Col>
                    </Row>
                </Container>
            </ModalBody>
            <ModalFooter>
                <Button disabled>Submit</Button>
            </ModalFooter>
        </Modal>
    )}
 

    render() {
        let {user} = this.state
        let logonoff = user ? [
            (<DropdownItem href="/logout">  Logout </DropdownItem>),
            // (<DropdownItem onClick={this.settingsModal}>  Settings </DropdownItem>),
        ] : (<DropdownItem href="/login"> Login </DropdownItem>)
        let myseeds = user ? (<DropdownItem href={"/plando/"+ user}> {user}'s seeds </DropdownItem>) : null 
        let settings = this.settingsModal()
        return (
            <Navbar className="border border-dark p-2" expand="md">
            {settings}
            <NavbarBrand href="/">Ori Rando</NavbarBrand>
                <Nav className="ml-auto" navbar>
                <NavItem className="pl-2 pr-1">
                    <Button color="primary" href={"/quickstart"}>Start Playing</Button>
                </NavItem>
                <NavItem className="pl-1 pr-2">
                    <Button color="info" href={"/faq"}>Help</Button>
                </NavItem>
                <UncontrolledDropdown nav inNavbar>
                    <DropdownToggle nav caret>
                    Downloads
                    </DropdownToggle>
                    <DropdownMenu right>
                        <DropdownItem href="/dll">
                            Rando dll 
                        </DropdownItem>
                        <DropdownItem href="/tracker">
                            Rando Tracker
                        </DropdownItem>
                    </DropdownMenu>
                </UncontrolledDropdown>
                <NavItem>
                    <NavLink href={"/logichelper"}>Logic Helper</NavLink>
                </NavItem>
                <UncontrolledDropdown nav inBar>
                <DropdownToggle nav caret>
                Bingo
                </DropdownToggle>
                <DropdownMenu right>
                    <DropdownItem href="/dll/bingo">
                        Bingo dll (Works with rando)
                    </DropdownItem>
                    <DropdownItem href="/bingo/board">
                        Start Bingo Game
                    </DropdownItem>
                </DropdownMenu>
                </UncontrolledDropdown>
                
                <UncontrolledDropdown nav inNavbar>
                    <DropdownToggle nav caret>
                    Misc
                    </DropdownToggle>
                    <DropdownMenu right>
                    <DropdownItem target="_blank" href="https://goo.gl/csgRUw">
                        Patch Notes
                    </DropdownItem>
                    <DropdownItem href="/rebinds">
                        Ori Keyboard Rebinding Helper
                    </DropdownItem>
                    <DropdownItem href="/vanilla">
                        Vanilla Seed
                    </DropdownItem>
                     {logonoff}
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
                    {myseeds}
                    </DropdownMenu>
                </UncontrolledDropdown>
                </Nav>
            </Navbar>
        )
    }
};
export default SiteBar;