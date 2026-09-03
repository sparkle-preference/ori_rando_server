import React, {Component} from 'react';
import {Navbar,  NavbarBrand, Nav,  NavItem, Button, Modal, ModalHeader, ModalBody, ModalFooter, FormFeedback,
        UncontrolledDropdown, DropdownToggle, DropdownMenu, DropdownItem, Container, Row, Col, Input, UncontrolledAlert} from 'reactstrap'
import {FaSun, FaMoon} from 'react-icons/fa';
import {Cent, doNetRequest, postNetForm, get_random_loader, get_param, loginLogoutUrl, resolve_dark, save_dark, theme_href} from './common.js';

const VERSION = get_param("version");
// the three modes; every other theme the server sends is a bootswatch skin
const MODES = {system: "Follow browser", light: "Light", dark: "Dark"}
const theme_label = t => MODES[t] || t[0].toUpperCase() + t.slice(1)
const NAME_DEBOUNCE_MS = 400

class SiteBar extends Component {
    constructor(props) {
        super(props);
        let user = get_param("user");
        let dark = resolve_dark()
        // the page already rendered with a theme, so the switch never waits to know
        this.state = {user, dark, teamName: "", theme: get_param("theme") || "system", verbose: false, themes: [],
                      restoreLastSeed: true, hidePlayButton: false,
                      badChars: [], nameFree: null, settingsOpen: false, editName: user,
                      loaded: false, saveInProgress: false,
                      loader: get_random_loader(), saveStatus: 0, saveError: ""}
    }

    componentDidMount() {
        if(this.state.user)
            this.loadSettings()
    }
    componentWillUnmount() {
        clearTimeout(this.nameTimer)
    }
    loadSettings = () => {
        this.setState({loaded: false})
        doNetRequest("/user/settings", ({responseText}) => {
            let res = JSON.parse(responseText)
            // pristine is what Save Changes compares against, so it holds every editable field
            let clean = {editName: res.name || this.state.user, teamName: res.teamname,
                         theme: res.theme || "system", verbose: !!res.verbose,
                         restoreLastSeed: res.restoreLastSeed !== false, hidePlayButton: !!res.hidePlayButton}
            this.setState({...clean, pristine: clean, loaded: true,
                           badChars: res.badChars || [], themes: res.themes || []})
        })
    }
    isDirty = () => {
        let {pristine, editName, teamName, theme, verbose, restoreLastSeed, hidePlayButton} = this.state
        return !!pristine && (editName !== pristine.editName || teamName !== pristine.teamName
                              || theme !== pristine.theme || verbose !== pristine.verbose
                              || restoreLastSeed !== pristine.restoreLastSeed
                              || hidePlayButton !== pristine.hidePlayButton)
    }
    // local rules answer without asking; only "is it taken" needs the server
    localNameProblem = (name) => {
        if(name === "")
            return (<FormFeedback tooltip>Name cannot be blank</FormFeedback>)
        let forbidden = this.state.badChars.filter(c => name.includes(c))
        if(forbidden.length > 0)
            return (<FormFeedback tooltip>Invalid symbol(s): {forbidden.join(", ")}</FormFeedback>)
        return null
    }
    onNameChange = (name) => {
        clearTimeout(this.nameTimer)
        this.setState({editName: name, nameFree: null})
        if(name !== this.state.user && !this.localNameProblem(name))
            this.nameTimer = setTimeout(() => this.checkName(name), NAME_DEBOUNCE_MS)
    }
    checkName = (name) => {
        doNetRequest(`/user/settings/name-free?name=${encodeURIComponent(name)}`, ({responseText}) => {
            let res = JSON.parse(responseText)
            // a slow reply for an earlier keystroke must not answer for the current one
            if(res.name === this.state.editName)
                this.setState({nameFree: !!res.free})
        })
    }
    validateName = (user, editName, nameFree) => {
        let problem = this.localNameProblem(editName)
        if(problem)
            return {valid: false, feedback: problem}
        if(editName === user)
            return {valid: true, feedback: null}
        if(nameFree === false)
            return {valid: false, feedback: (<FormFeedback tooltip>Name '{editName}' is already in use!</FormFeedback>)}
        if(nameFree === null)  // still asking; the save rejects a collision anyway
            return {valid: true, feedback: null}
        return {valid: true, feedback: (<FormFeedback valid tooltip>Name is available and valid</FormFeedback>)}
    }
    // what index.js will pick for this theme, so the preview matches the reload
    previewHref = (theme) => {
        if(!MODES[theme])
            return theme_href(theme)
        let dark = theme === "dark" || (theme === "system" && window.matchMedia
                   && window.matchMedia("(prefers-color-scheme: dark)").matches)
        return theme_href(dark ? "darkly" : "flatly")
    }
    onThemeChange = (theme) => {
        this.setState({theme})
        let link = document.getElementById("css_switcher")
        if(!link)
            return
        if(this.themeBeforePreview === undefined)
            this.themeBeforePreview = link.href
        link.href = this.previewHref(theme)
    }
    closeModals = () => {
        // a preview the user walked away from is not a choice they made
        let link = document.getElementById("css_switcher")
        if(link && this.themeBeforePreview !== undefined)
            link.href = this.themeBeforePreview
        this.themeBeforePreview = undefined
        clearTimeout(this.nameTimer)
        // every edit goes back, so reopening does not show what was cancelled
        this.setState({...this.state.pristine, settingsOpen: false, saveStatus: 0, nameFree: null})
    }
    submitSettings = () => {
        let {editName, teamName, theme, verbose, restoreLastSeed, hidePlayButton} = this.state
        let fields = {name: editName, teamname: teamName, theme: theme, verbose: verbose ? "1" : "0",
                      restoreLastSeed: restoreLastSeed ? "1" : "0", hidePlayButton: hidePlayButton ? "1" : "0"}
        this.setState({saveInProgress: true}, () => postNetForm("/user/settings/update", fields, ({status, responseText}) => {
            // a rejected save keeps the dialog, so the edits that caused it are still there to fix
            if(status !== 200) {
                this.setState({saveStatus: status, saveError: responseText, saveInProgress: false})
                return
            }
            // a skin has to clear dark_apps and the mode rules, so let the page redo it
            if((JSON.parse(responseText).changed || []).includes("theme")) {
                window.location.reload()
                return
            }
            this.themeBeforePreview = undefined
            // pages that render off a setting (the seed tab's Play button) follow without a reload
            window.dispatchEvent(new CustomEvent("userSettingsSaved", {detail: fields}))
            this.setState({saveInProgress: false, settingsOpen: false, user: editName}, this.loadSettings)
        }))
    }
    settingsModal = () =>  {
        let {saveInProgress, loaded, settingsOpen, loader, nameFree, user, editName, teamName,
             theme, themes, verbose, restoreLastSeed, hidePlayButton, saveStatus, saveError} = this.state
        if(saveInProgress || !loaded)
            return (
                <Modal size="sm" isOpen={settingsOpen} backdrop={"static"} className={"modal-dialog-centered settings-modal"}>
                    <ModalHeader centered="true">{loaded ? "Saving..." : "Loading Settings..."}</ModalHeader>
                    <ModalBody>
                        <Container fluid>
                            <Row className="p-2 justify-content-center align-items-center">
                                <Col xs="auto" className="align-items-center justify-content-center p-2">{loader}</Col>
                            </Row>
                        </Container>
                    </ModalBody>
                </Modal>
            )
        let {valid, feedback} = this.validateName(user, editName, nameFree)
        let alert = saveStatus > 0
            ? (<UncontrolledAlert color="danger">{saveError || "Save failed..."}</UncontrolledAlert>)
            : null
        return (
            <Modal isOpen={settingsOpen} backdrop={"static"} className={"modal-dialog-centered settings-modal"} toggle={this.closeModals}>
                <ModalHeader toggle={this.closeModals} centered="true">User settings</ModalHeader>
                <ModalBody >
                    {alert}
                    <Container fluid>
                        <Row className="p-1 justify-content-center">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Display name</Cent>
                            </Col><Col xs="6">
                                <Input type="text" value={editName} className="w-100" valid={valid} invalid={!valid} onChange={e => this.onNameChange(e.target.value)}/>
                                {feedback}
                            </Col>
                        </Row>
                        <Row className="p-1 justify-content-center">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Team name</Cent>
                            </Col><Col xs="6">
                                <Input type="text" value={teamName} className="w-100" invalid={teamName === undefined || teamName === null || teamName === ""} onChange={e => this.setState({teamName: e.target.value})}/>
                                <FormFeedback tooltip>Team name can't be empty</FormFeedback>
                            </Col>
                        </Row>
                        <Row className="p-1 justify-content-center">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Theme</Cent>
                            </Col><Col xs="6">
                                <Input type="select" value={theme} className="w-100" onChange={e => this.onThemeChange(e.target.value)}>
                                    {themes.map(t => (<option key={t} value={t}>{theme_label(t)}</option>))}
                                </Input>
                                <a className="small text-muted" href="https://bootswatch.com/4/" target="_blank" rel="noopener noreferrer">see them all</a>
                            </Col>
                        </Row>
                        <Row className="p-1 justify-content-center">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Verbose spoilers</Cent>
                            </Col><Col xs="6" className="d-flex align-items-center">
                                <div className="custom-control custom-switch">
                                    <input type="checkbox" className="custom-control-input" id="verboseSwitch" checked={verbose} onChange={e => this.setState({verbose: e.target.checked})}/>
                                    <label className="custom-control-label" htmlFor="verboseSwitch"> </label>
                                </div>
                            </Col>
                        </Row>
                        <Row className="p-1 justify-content-center">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Remember seedgen settings</Cent>
                            </Col><Col xs="6" className="d-flex align-items-center">
                                <div className="custom-control custom-switch">
                                    <input type="checkbox" className="custom-control-input" id="lastSeedSwitch" checked={restoreLastSeed} onChange={e => this.setState({restoreLastSeed: e.target.checked})}/>
                                    <label className="custom-control-label" htmlFor="lastSeedSwitch">
                                        <small className="text-muted">Open the seed generator on your last seed's options</small>
                                    </label>
                                </div>
                            </Col>
                        </Row>
                        <Row className="p-1 justify-content-center">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Hide Play button</Cent>
                            </Col><Col xs="6" className="d-flex align-items-center">
                                <div className="custom-control custom-switch">
                                    <input type="checkbox" className="custom-control-input" id="hidePlaySwitch" checked={hidePlayButton} onChange={e => this.setState({hidePlayButton: e.target.checked})}/>
                                    <label className="custom-control-label" htmlFor="hidePlaySwitch">
                                        <small className="text-muted">If you don't use the Rando App, the seed tab only offers Download</small>
                                    </label>
                                </div>
                            </Col>
                        </Row>
                    </Container>
                </ModalBody>
                <ModalFooter>
                    <Button color="secondary" onClick={this.closeModals}>Cancel</Button>
                    <Button color="primary" disabled={!valid || !this.isDirty()} onClick={this.submitSettings}>Save Changes</Button>
                </ModalFooter>
            </Modal>
        )
    }
    themeToggle = () => {
        let {user, dark} = this.state;
        let url = new URL(window.document.URL)
        let page = encodeURIComponent(url.pathname + url.search)
        let want = !dark
        if(user) {
            let redirTarget = new URL(url.protocol + "//" + url.host + `/theme/toggle`)
            redirTarget.searchParams.append("redir", page)
            // the server can't see the browser preference, so it can't work
            // out what we're switching away from -- tell it the target
            redirTarget.searchParams.append("dark", want ? "1" : "0")
            window.location.replace(redirTarget.href)
        } else {
            save_dark(want)
            document.getElementById("css_switcher").href = theme_href(want ? "darkly" : "flatly")
            this.setState({dark: want})
        }
    }

    render() {
        if(this.props.hidden)
            return null
        let {user, dark, theme} = this.state;
        // a skin decides its own brightness, so the light/dark switch has nothing to say
        let brightnessSwitch = MODES[theme] ? (
            <NavItem className="pl-2 pr-2 d-flex align-items-center">
                <FaSun/>
                <div className="custom-control custom-switch ml-2 mr-1">
                    <input type="checkbox" className="custom-control-input" id="brightnessSwitch"
                           checked={dark} onChange={this.themeToggle}/>
                    <label className="custom-control-label" htmlFor="brightnessSwitch"
                           title={dark ? "Switch to light mode" : "Switch to dark mode"}> </label>
                </div>
                <FaMoon/>
            </NavItem>
        ) : null
        let logonoff = user ? [
            (<DropdownItem key="name" disabled><i>Logged in as {user}</i></DropdownItem>),
            (<DropdownItem key="settings" onClick={() => this.setState({settingsOpen: true})}> Settings </DropdownItem>),
            (<DropdownItem key="my games" href={"/myGames"}>  My Games </DropdownItem>),
            (<DropdownItem key="logout" href={loginLogoutUrl(false)}>  Logout </DropdownItem>),
        ] : [
            (<DropdownItem key="login" href={loginLogoutUrl(true)}> Login </DropdownItem>)
        ]
        let myseeds = user ? (<DropdownItem href={"/plando/"+ user}> {user}'s seeds </DropdownItem>) : null
        let settings = this.settingsModal()
        let navClass = "border border-dark p-2"
        return (
            <Navbar style={{maxWidth: '1074px'}} className={navClass} expand="md">
            {settings}
            <NavbarBrand href="/">Ori Rando</NavbarBrand>
                <Nav className="ml-auto" navbar>
                {brightnessSwitch}
                <NavItem className="pl-2 pr-1">
                    <Button color="primary" href="/quickstart">Start Playing</Button>
                </NavItem>
                <NavItem className="pl-1 pr-2">
                    <Button color="info" href={"/faq"}>Help</Button>
                </NavItem>
                <UncontrolledDropdown nav inNavbar>
                    <DropdownToggle nav caret>
                    Downloads
                    </DropdownToggle>
                    <DropdownMenu right>
                        <DropdownItem href="/vanilla">
                            Vanilla Seed
                        </DropdownItem>
                        <DropdownItem href="/app">
                            Rando App
                        </DropdownItem>
                        <DropdownItem href="/dll">
                            Rando dll ({VERSION})
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
                    <DropdownMenu right>
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
                    <DropdownMenu right>
                    <DropdownItem target="_blank" href="/league/rules">
                        Ori Rando League
                    </DropdownItem>
                    <DropdownItem target="_blank" href="trickglossary">
                        Trick Glossary
                    </DropdownItem>
                    <DropdownItem target="_blank" href="/patchnotes">
                        Patch Notes
                    </DropdownItem>
                    <DropdownItem href="/bingo/board">
                        Vanilla+ Bingo
                    </DropdownItem>
                   </DropdownMenu>
                </UncontrolledDropdown>
                <UncontrolledDropdown nav inNavbar>
                    <DropdownToggle nav caret>
                        User
                    </DropdownToggle>
                    <DropdownMenu right>
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
