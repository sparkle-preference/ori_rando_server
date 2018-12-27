import React, {Component} from 'react';
import {Navbar,  NavbarBrand, Nav,  NavItem,  NavLink, Button, Modal, ModalHeader, ModalBody, ModalFooter, FormFeedback, 
        UncontrolledDropdown, DropdownToggle, DropdownMenu, DropdownItem, Container, Row, Col, Input, UncontrolledAlert} from 'reactstrap'
import {Cent, doNetRequest, get_random_loader} from './common.js';

class SiteBar extends Component {
    constructor(props) {
        super(props);
        let {user} = props;
        this.state = {user: user, settingsOpen: false, quickstartOpen: false, editName: user, loadedNames: false, saveInProgress: false, loader: get_random_loader(), saveStatus: 0}
    }
    componentDidMount() {
        if(this.state.user) 
            this.getUsedNames()
    }
    getUsedNames = () => {
        this.setState({loadedNames: false})
        doNetRequest("/users/names", ({responseText}) => {
            this.setState({usedNames: JSON.parse(responseText).map(name => name.toLowerCase()), loadedNames: true})
        })
    }
    validateName = (usedNames, user, editName) => {
        if(editName === "") 
            return {valid: false, feedback: (<FormFeedback tooltip>Name cannot be blank</FormFeedback>)}
        if(editName === user)
            return {valid: false, feedback: (<FormFeedback tooltip>New name must be different</FormFeedback>)}
        if(usedNames.includes(editName.toLowerCase()))
            return {valid: false, feedback: (<FormFeedback tooltip>Name '{editName}' is already in use!</FormFeedback>)}
        let forbiddenChars = ["@", "/", "\\", "?", "#", "&", "=", '"', "'"].filter(c => editName.includes(c));
        if(forbiddenChars.length > 0) 
            return {valid: false, feedback: (<FormFeedback tooltip>Invalid symbol(s): {forbiddenChars.join(", ")}</FormFeedback>)}
        return {valid: true, feedback: (<FormFeedback valid tooltip>Name is available and valid</FormFeedback>)}
    }
    closeModals = () => this.setState({settingsOpen: false, quickstartOpen: false})
    submitSettings = () => {
        doNetRequest(`/rename/${this.state.editName}`, ({status}) => {
            if(status === 200)
                this.setState({saveStatus: status, user: this.state.editName}, this.getUsedNames)
            else
                this.setState({saveStatus: status}, this.getUsedNames)
    
        })
    }
    settingsModal = () =>  {
        let {saveInProgress, loadedNames, settingsOpen, loader, usedNames, user, editName, saveStatus} = this.state
        if(saveInProgress || !loadedNames)
            return (
                <Modal size="sm" isOpen={settingsOpen} backdrop={"static"} className={"modal-dialog-centered"}>
                    <ModalHeader centered="true">{loadedNames ? "Saving..." : "Loading Settings..."}</ModalHeader>
                    <ModalBody>
                        <Container fluid>
                            <Row className="p-2 justify-content-center align-items-center">
                                <Col xs="auto" className="align-items-center justify-content-center p-2">{loader}</Col>
                            </Row>
                        </Container>
                    </ModalBody>
                </Modal>
            )
        let {valid, feedback} = this.validateName(usedNames, user, editName)
        let alert = null
        if(saveStatus > 0)
        {
            if(saveStatus === 200)
                alert = (<UncontrolledAlert color="success">Name changed successfully!</UncontrolledAlert>)
            else
                alert = (<UncontrolledAlert color="danger">Save failed...</UncontrolledAlert>)
        }
        return (
            <Modal isOpen={settingsOpen} backdrop={"static"} className={"modal-dialog-centered"} toggle={this.closeModals}>
                <ModalHeader toggle={this.closeModals} centered="true">User settings</ModalHeader>
                <ModalBody>
                    {alert}
                    <Container fluid>
                        <Row className="p-1">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Display name</Cent>
                            </Col><Col xs="8">
                                <Input type="text" value={editName} className="w-50" valid={valid} invalid={!valid} onChange={e => this.setState({editName: e.target.value})}/> 
                                {feedback}
                            </Col>
                        </Row>
                        {/*
                        <Row className="p-1">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>color</Cent>
                            </Col><Col xs="4">
                                <Input type="text" value={this.state.userColor}  onChange={(e) => this.setState({userColor: e.target.value})}/> 
                            </Col>
                        </Row>
                        */}
                    </Container>
                </ModalBody>
                <ModalFooter>
                    <Button disabled={!valid} onClick={this.submitSettings}>Submit</Button>
                </ModalFooter>
            </Modal>
        )
    }
 

    render() {
        let {user} = this.state;
        let page = encodeURIComponent(window.document.URL.split(".com")[1])
        let logonoff = user ? [
            (<DropdownItem key="username" disabled>(Logged in as {user}) </DropdownItem>),
            (<DropdownItem key="settings" onClick={() => this.setState({settingsOpen: true})}> Settings </DropdownItem>),
            (<DropdownItem key="logout" href={"/logout?redir="+page}>  Logout </DropdownItem>),
        ] : (<DropdownItem href={"/login?redir="+page}> Login </DropdownItem>)
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
                <UncontrolledDropdown nav inNavbar>
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