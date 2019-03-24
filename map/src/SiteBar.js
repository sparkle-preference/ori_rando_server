import React, {Component} from 'react';
import {Navbar,  NavbarBrand, Nav,  NavItem, Button, Modal, ModalHeader, ModalBody, ModalFooter, FormFeedback,
        UncontrolledDropdown, DropdownToggle, DropdownMenu, DropdownItem, Container, Row, Col, Input, UncontrolledAlert} from 'reactstrap'
import {Cent, doNetRequest, get_random_loader} from './common.js';
const BAD_CHARS = ["@", "/", "\\", "?", "#", "&", "=", '"', "'"]
class SiteBar extends Component {
    constructor(props) {
        super(props);
        let {user, dark} = props;
        this.state = {user: user, dark: dark, teamName: "", settingsOpen: false, quickstartOpen: false, editName: user, loadedNames: false, saveInProgress: false, loader: get_random_loader(), saveStatus: 0}
    }
    componentDidMount() {
        if(this.state.user)
            this.getUsedNames()
    }
    getUsedNames = () => {
        this.setState({loadedNames: false})
        doNetRequest("/user/settings", ({responseText}) => {
            let res = JSON.parse(responseText)
            this.setState({teamName: res.teamname, usedNames: res.names, loadedNames: true})
        })
    }
    validateName = (usedNames, user, editName) => {
        if(editName === "")
            return {valid: false, feedback: (<FormFeedback tooltip>Name cannot be blank</FormFeedback>)}
        if(editName === user)
            return {valid: true, feedback: null}
        if(usedNames.includes(editName.toLowerCase()))
            return {valid: false, feedback: (<FormFeedback tooltip>Name '{editName}' is already in use!</FormFeedback>)}
        let forbiddenChars = BAD_CHARS.filter(c => editName.includes(c));
        if(forbiddenChars.length > 0)
            return {valid: false, feedback: (<FormFeedback tooltip>Invalid symbol(s): {forbiddenChars.join(", ")}</FormFeedback>)}
        return {valid: true, feedback: (<FormFeedback valid tooltip>Name is available and valid</FormFeedback>)}
    }
    closeModals = () => this.setState({settingsOpen: false, quickstartOpen: false})
    submitSettings = () => {
        doNetRequest(`/user/settings/update?name=${this.state.editName}&teamname=${encodeURIComponent(this.state.teamName)}`, ({status}) => {
            if(status === 200)
                this.setState({saveStatus: status, user: this.state.editName}, this.getUsedNames)
            else
                this.setState({saveStatus: status}, this.getUsedNames)

        })
    }
    settingsModal = () =>  {
        let {saveInProgress, loadedNames, settingsOpen, loader, usedNames, user, editName, teamName, saveStatus, dark} = this.state
        let styles = dark ? {'backgroundColor': '#333', 'color': 'white'} : {}
        if(saveInProgress || !loadedNames)
            return (
                <Modal size="sm" isOpen={settingsOpen} backdrop={"static"} className={"modal-dialog-centered"}>
                    <ModalHeader style={styles} centered="true">{loadedNames ? "Saving..." : "Loading Settings..."}</ModalHeader>
                    <ModalBody style={styles}>
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
                <ModalHeader style={styles} toggle={this.closeModals} centered="true">User settings</ModalHeader>
                <ModalBody style={styles}>
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
                        <Row className="p-1">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Team Name</Cent>
                            </Col><Col xs="8">
                                <Input type="text" value={teamName} className="w-50" invalid={teamName === undefined || teamName === null || teamName === ""} onChange={e => this.setState({teamName: e.target.value})}/>
                                <FormFeedback tooltip>Team name can't be empty</FormFeedback>
                            </Col>
                        </Row>
                    </Container>
                </ModalBody>
                <ModalFooter style={styles}>
                    <Button disabled={!valid} onClick={this.submitSettings}>Submit</Button>
                </ModalFooter>
            </Modal>
        )
    }
    themeToggle = () => {
        let {user, dark} = this.state;
        let url = new URL(window.document.URL)
        let page = encodeURIComponent(url.pathname + url.search)
        if(user) {
            let redirTarget = new URL(url.protocol + "//" + url.host + `/theme/toggle`)
            redirTarget.searchParams.append("redir", page)
            window.location.replace(redirTarget.href)
        } else {
            if(dark && url.searchParams.has("dark"))
                url.searchParams.delete("dark")
            else
                url.searchParams.append("dark", 1)
            window.location.replace(url.href)
        }
    }

    render() {
        let {user, dark} = this.state;
        let url = new URL(window.document.URL)
        let page = encodeURIComponent(url.pathname + url.search)
        let xMode = dark ? "Light Mode" : "Dark Mode"
        let logonoff = user ? [
            (<DropdownItem key="settings" onClick={() => this.setState({settingsOpen: true})}> Rename </DropdownItem>),
            (<DropdownItem key="logout" href={"/logout?redir="+page}>  Logout </DropdownItem>),
        ] : [
            (<DropdownItem href={"/login?redir="+page}> Login </DropdownItem>)
        ]
        let myseeds = user ? (<DropdownItem href={"/plando/"+ user}> {user}'s seeds </DropdownItem>) : null
        let settings = this.settingsModal()
        let dropdownStyle = {}, navClass = "border border-dark p-2"
        if(dark)
        {
            dropdownStyle.backgroundColor = "#666"
            navClass = "border border-light p-2"
        }
        let nameorlogin = user ? user : "Login"
        return (
            <Navbar style={{maxWidth: '1074px'}} className={navClass} expand="md">
            {settings}
            <NavbarBrand href={"/" + (dark && !user ? "?dark=1" : "")}>Ori Rando</NavbarBrand>
                <Nav className="ml-auto" navbar>
                <NavItem className="pl-2 pr-1">
                    <Button color="primary" href={"/quickstart" + (dark && !user ? "?dark=1" : "")}>Start Playing</Button>
                </NavItem>
                <NavItem className="pl-1 pr-2">
                    <Button color="info" href={"/faq"}>Help</Button>
                </NavItem>
                <UncontrolledDropdown nav inNavbar>
                    <DropdownToggle nav caret>
                    Downloads
                    </DropdownToggle>
                    <DropdownMenu style={dropdownStyle} right>
                        <DropdownItem href="/vanilla">
                            Vanilla Seed
                        </DropdownItem>
                        <DropdownItem href="/dll">
                            Rando dll (3.1)
                        </DropdownItem>
                        <DropdownItem href="/tracker">
                            Rando Tracker
                        </DropdownItem>
                    </DropdownMenu>
                </UncontrolledDropdown>
                <UncontrolledDropdown nav inNavbar>
                    <DropdownToggle nav caret>
                        Tools
                    </DropdownToggle>
                    <DropdownMenu style={dropdownStyle} right>
                        <DropdownItem href="/logichelper">
                            Logic Helper
                        </DropdownItem>
                        <DropdownItem href="/rebinds">
                            Ori Keyboard Rebinding Editor
                        </DropdownItem>
                    </DropdownMenu>
                </UncontrolledDropdown>
                <UncontrolledDropdown nav inNavbar>
                    <DropdownToggle nav caret>
                    Misc
                    </DropdownToggle>
                    <DropdownMenu style={dropdownStyle} right>
                    <DropdownItem target="_blank" href="https://goo.gl/csgRUw">
                        Patch Notes
                    </DropdownItem>
                    <DropdownItem href={"/bingo/board" + (dark && !user ? "?dark=1" : "")}>
                        Start Bingo Game
                    </DropdownItem>
                   </DropdownMenu>
                </UncontrolledDropdown>
                <UncontrolledDropdown nav inNavbar>
                    <DropdownToggle nav caret>
                    {nameorlogin}
                    </DropdownToggle>
                    <DropdownMenu style={dropdownStyle} right>
                    <DropdownItem onClick={this.themeToggle}>
                        {xMode}
                    </DropdownItem>
                    {logonoff}
                    </DropdownMenu>
                </UncontrolledDropdown>
                <UncontrolledDropdown nav inNavbar>
                    <DropdownToggle nav caret>
                    Plando
                    </DropdownToggle>
                    <DropdownMenu style={dropdownStyle} right>
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
