import React, {Component} from 'react';
import {Container, Row, Col, Collapse, Button, ButtonGroup, Modal, ModalHeader, Popover, PopoverBody,
        ModalBody, ModalFooter, Input, Card, CardBody, CardFooter, Media, UncontrolledButtonDropdown, DropdownToggle, DropdownMenu, DropdownItem} from 'reactstrap';
import {NotificationContainer, NotificationManager} from 'react-notifications';
import {Helmet} from 'react-helmet';

import {download} from './shared_map.js'
import {Cent, doNetRequest, player_icons, get_random_loader, PickupSelect, get_flag, get_param} from './common.js'
import SiteBar from "./SiteBar.js";

import 'react-notifications/lib/notifications.css';

const colors = {
    footerDark: "#292929",
    cardDark: "#333333",
    darkComplete: "#1ba06e",
    darkSubgoal: "#0d4f34",
    complete: "#ccffcc",
    subgoal: "#88cc88"
}



const make_icons = players => players.map(p => (<Media key={`playerIcon${p}`} object style={{width: "25px", height: "25px"}} src={player_icons(p, false)} alt={"Icon for player "+p} />))
const BingoCard = ({card, progress, players, help, dark}) => {
    let cardStyles = {width: '18vh', height: '18vh', minWidth: '120px', maxWidth: '160px', minHeight: '120px', maxHeight: '160px', flexGrow: 1}
    let footerStyles = {}
    if(dark)
    {
        cardStyles.background = colors.cardDark
        cardStyles.border = '1px solid rgba(255,255,255,.25)'
        footerStyles.background = colors.footerDark
    }
    let {open, toggle, i} = help
    let {disp_name, help_lines, subgoals, target} = card
    subgoals = subgoals || {}
    let helpLink = null, popover = null
    if(Object.keys(subgoals).length > 0)
        disp_name += ":";
    let text = [(<div className="w-100" key={`card-line-0`}>{disp_name}</div>)]
    let j = 1;

    Object.keys(subgoals).forEach(subgoal => {
        let styles = {};
        if(progress.subgoals && progress.subgoals.includes(subgoal))
        {
            if(progress.completed) 
                styles.background = dark ?  colors.darkSubgoal: colors.subgoal 
            else
                styles.background = dark ? colors.darkComplete : colors.complete
        }
        text.push((<div className="w-100" key={`card-line-${j++}`} style={styles}>{subgoals[subgoal].disp_name}</div>))
    })
    if(target) {
        text.push((<div className="w-100" key={`card-line-${j++}`}>({progress.count ? `${progress.count}/` : ""}{target})</div>))
    }
    let className = "px-0 pb-0 justify-content-center text-center align-items-center d-flex " + ((text.length > 1) ? "pt-0 flex-column" : "pt-1")

    if(help_lines.length > 0) {
        let helpText = help_lines.map(l => (<div>{l}</div>))
        helpLink = (
            <div className="m-0 p-0 float-left"><Button color="link" className="pl-1 pt-1 pb-0 pr-0 m-0" id={"help-"+i} onClick={toggle}>?</Button></div>
            )
        popover = (
            <Popover placement="top" isOpen={open} target={"help-"+i} toggle={toggle}>
            <PopoverBody>{helpText}</PopoverBody>
            </Popover>
        )
    }
    
    if(progress.completed)
        cardStyles.background = dark ? colors.darkComplete : colors.complete
    return (
        <Card inverse={dark} style={cardStyles}>
                <CardBody style={{fontSize: "1.5vh", fontWeight: "bold"}} className={className}>
                    {text}
                </CardBody>
                <CardFooter style={footerStyles} className="p-0 text-center">
                {helpLink}
                {popover}
                {make_icons(players)}
                </CardFooter>
        </Card>

)}



class BingoBoard extends Component {
    constructor(props) {
        super(props);
        let {cards} = props
        this.state = {helpOpen: cards.map(_ => false)}
    }
    helpToggle = (cardNum) => () => this.setState(prev => {
        prev.helpOpen[cardNum]  = !prev.helpOpen[cardNum]
        return {helpOpen: prev.helpOpen}
    })
    render() {
        let {cards, activePlayer, dark, hiddenPlayers} = this.props
        if(!cards || cards.length < 25) {
            return null
        }
        let rows = [], i = 0;
        let rowStyle = {height: "20px"}
        let colStyle = {width: "20px"}
        while(rows.length < 5) {
            let row = []
            while(row.length < 5) {
                let card = cards[i];
                let players = Object.keys(card.progress).filter(p => card.progress[p].completed && !hiddenPlayers.includes(p));
                let progress = card.progress.hasOwnProperty(activePlayer) ? card.progress[activePlayer] : {'completed': false, 'count': 0, 'subgoals': []}
                row.push((<td key={i}><BingoCard dark={dark} card={card} progress={progress} help={{i: i, open: this.state.helpOpen[i], toggle: this.helpToggle(i)}} players={players} /></td>))
                i++
            }
            rows.push((<tr key={`row-${rows.length}`}><td><div style={colStyle}>{rows.length + 1}</div></td>{row}</tr>))
        }
        return (<table>
                    <tbody>
                        <tr style={{textAlign: 'center'}}>
                            <td></td>
                            <td><div style={rowStyle}>A</div></td> 
                            <td><div style={rowStyle}>B</div></td>
                            <td><div style={rowStyle}>C</div></td>
                            <td><div style={rowStyle}>D</div></td>
                            <td><div style={rowStyle}>E</div></td>
                        </tr>
                        {rows}
                    </tbody>
                </table>);
    }
}

const PlayerList = ({activePlayer, teams, viewOnly, onPlayerListAction, dark}) => {
    if(!teams)
        return null
    let dropdownStyle = {}
    if(dark)
        dropdownStyle.backgroundColor = "#666"
    let players = teams.map(({hidden, cap, teammates, name, bingos}) => {
            if(hidden)
                return null
            let hasTeam = teammates.length > 1
            let number = (bingos && bingos.length) || 0
            let text = `${name} (${number})`
            let active = activePlayer === cap
            let joinButton = viewOnly ? null : ( 
                <DropdownItem onClick={onPlayerListAction("joinTeam", cap)}>
                    Join Team
                </DropdownItem>
            )
            if(active)
                text = (<b>{text}</b>)
            let rows = [(
                <Row key={`player-list-${cap}`} className="px-2 text-center pb-2">
                    <Col className="p-0">
                    <UncontrolledButtonDropdown className="w-100 px-1">
                        <Button color="secondary" active={active} block onClick={onPlayerListAction("selectPlayer", cap)}>
                            <Cent>{make_icons([cap])} {text}</Cent>
                        </Button>
                        <DropdownToggle caret color="secondary" />
                        <DropdownMenu style={dropdownStyle} right>
                            {joinButton}
                            <DropdownItem onClick={onPlayerListAction("hidePlayer", cap)}>
                                Hide Player
                            </DropdownItem>
                        </DropdownMenu>
                        </UncontrolledButtonDropdown>
                    </Col>
                </Row>
            )]
            if(hasTeam)
                rows = rows.concat(teammates.map(({pid, name}) => (
                    <Row key={`subplayer-list-${pid}`} className="px-2 text-center pb-2">
                        <Col xs={{offset: 2, size: 8}} className="p-0">
                            <UncontrolledButtonDropdown className="w-100 px-1">
                                <Button size="sm" color="secondary" active={pid === activePlayer} block onClick={onPlayerListAction("selectPlayer", pid)}>
                                    <Cent>{name}</Cent>
                                </Button>
                                <DropdownToggle size="sm" caret color="secondary" />
                                <DropdownMenu style={dropdownStyle} right>
                                    <DropdownItem onClick={onPlayerListAction("hidePlayer", pid)}>
                                        Hide Player
                                    </DropdownItem>
                                </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                )))

            return [number, rows]
        })

    let hiddenButton = teams.some(t => t["hidden"]) ? (
        <Row className="pb-2">
            <Button block size="sm" color="link" onClick={onPlayerListAction("showHidden", 0)}>
                Show all hidden
            </Button>
        </Row>
    ): null
    
    players = players.filter(p => p != null).sort((a, b) => b[0] - a[0]).map(p => p[1])

    return (
        <Col style={{maxWidth: '420px'}} className="border border-info">
            <Row  className="px-2 pb-2"><Cent><h4>Players</h4></Cent></Row>
            {players}
            {hiddenButton}
        </Col>
    );
}

export default class Bingo extends React.Component {
    constructor(props) {
        super(props);
        let url = new URL(window.document.URL);
        let viewOnly = url.href.includes("bingo/spectate")
        let gameId = parseInt(url.searchParams.get("game_id") || -1, 10);
        let dark = get_flag("dark") || url.searchParams.has("dark")
        
        this.state = {
                      cards: [], currentRecord: 0, haveGame: false, creatingGame: false, createModalOpen: true, 
                      activePlayer: 1, showInfo: false, bingos: {}, user: get_param("user"), loading: true, 
                      dark: dark, specLink: window.document.location.href.replace("board", "spectate"),
                      fails: 0, gameId: gameId, startSkills: 3, startCells: 4, startMisc: "MU|TP/Swamp/TP/Valley",
                      start_with: "", difficulty: "normal", isRandoBingo: false, randoGameId: -1, viewOnly: viewOnly,
                      events: [], gameOwner: false, startTime: (new Date())
                    };
        if(gameId > 0)
        {
            let url = `/bingo/game/${gameId}/fetch?first=1`
            doNetRequest(url, this.createCallback)
            this.state.creatingGame = true
            this.state.createModalOpen = false
            this.state.loader = get_random_loader()
        }
    }
    componentWillMount() {
        this.tick()
        this.interval = setInterval(() => this.tick(), 5000);
  };
    updateUrl = () => {
        let {gameId} = this.state;
        let url = new URL(window.document.URL);
        if(gameId && gameId > 0)
            url.searchParams.set("game_id", gameId)
        else
            url.searchParams.delete("game_id")
        
        window.history.replaceState('',window.document.title, url.href);
        this.setState({specLink: window.document.location.href.replace("board", "spectate")})
    }

    joinGame = (joinTeam) => {
        joinTeam = joinTeam || false
        let {gameId, seed, activePlayer, haveGame} = this.state;
        if(!haveGame) return;
        let nextPlayer = activePlayer;
        let players = this.state.teams.map(({pid}) => pid)
        while(players.includes(String(nextPlayer)))
            nextPlayer++;
        seed = `Sync${gameId}.${nextPlayer},` + seed
        download("randomizer.dat", seed)
        this.setState({activePlayer: nextPlayer})
        let url = `/bingo/game/${gameId}/add/${nextPlayer}`
        if(joinTeam) {
            url += `?joinTeam=${joinTeam}`
        }
        doNetRequest(url, this.tickCallback)
    }
    tick = () => {
        let {gameId, haveGame} = this.state;
        if(gameId && gameId > 0 && haveGame && this.state.fails < 50)
        {
            doNetRequest(`/bingo/game/${gameId}/fetch`, this.tickCallback)
        }
    }
    tickCallback = ({status, responseText}) => {
        if(status !== 200)
        {
            if((this.state.fails - 1) % 5 === 0)
                NotificationManager.error(`error ${status}: ${responseText}`, "error", 5000)
            this.setState({fails: this.state.fails + 1})
        } else {
            let res = JSON.parse(responseText)
            let teams = res.teams
            teams.map(t => {
                let maybe_old = this.state.teams.filter(old => t.cap === old.cap)
                if(maybe_old.length > 0)
                {
                    t.hidden = maybe_old[0].hidden
                }
                return t
            })
            this.setState({teams: teams, cards: res.cards, events: res.events, reqsrs: res.required_squares}, this.updateUrl)
        }
    }
    createGame = () => {
        let {isRandoBingo, randoGameId, startSkills, startCells, startMisc, showInfo, difficulty} = this.state;
        if(isRandoBingo)
        {
            let url = `/bingo/from_game/${randoGameId}?difficulty=${difficulty}`
            doNetRequest(url, this.createCallback)
            this.setState({creatingGame: true, createModalOpen: false, loader: get_random_loader()})
        } else {
            let url = `/bingo/new?skills=${startSkills}&cells=${startCells}&misc=${startMisc}&difficulty=${difficulty}`
            if(showInfo)
                url += "&showInfo=1"
            doNetRequest(url, this.createCallback)
            this.setState({creatingGame: true, createModalOpen: false, loader: get_random_loader()})
        }
    }
    createCallback = ({status, responseText}) => {
        if(status !== 200)
        {
            NotificationManager.error(`error ${status}: ${responseText}`, "error creating seed", 5000)
            this.setState({createModalOpen: false, haveGame: false, creatingGame: false}, this.updateUrl)
            return
        } else {
            let res = JSON.parse(responseText)
            this.setState({subtitle: res.subtitle, gameId: res.gameId, createModalOpen: false, creatingGame: false, haveGame: true, fails: 0, dispDiff: res.difficulty || this.state.difficulty,
                          seed: res.seed, teams: res.teams, currentRecord: 0, cards: res.cards, events: res.events, reqsrs: res.required_squares}, this.updateUrl)
        }
    }
    onPlayerListAction = (action, player) => () =>  {
        switch(action) {
            case "hidePlayer":
                this.setState(prev => {
                    prev.teams[player].hidden = true
                    return {teams: prev.teams}
                })
                break;
            case "selectPlayer":
                this.setState({activePlayer: player})
                break;
            case "showHidden":
                this.setState(prev => {
                    Object.keys(prev.teams).forEach(p => prev.teams[p].teams = false)
                    return {teams: prev.teams}
                })
                break;
            case "joinTeam":
                this.joinGame(player)
                break;
            default:
                console.log("Unknown action: " + action)
                break
        }
    }

    toggleCreate = () => this.setState({createModalOpen: !this.state.createModalOpen})
    getTeam = (pid) => {
        return this.state.teams.filter(t => t.cap === pid)[0]
    }
    getSquareName = (sq) => this.state.cards[sq].disp_name
    render = () => {
        let {specLink, viewOnly, dark, activePlayer, subtitle, cards, haveGame, bingos, gameId, user, dispDiff, teams} = this.state
        
        let pageStyle, inputStyle
        if(dark) {
            pageStyle = 'body { background-color: #333; color: white }';
            inputStyle = {'backgroundColor': '#333', 'color': 'white'}
        } else {
           pageStyle = 'body { background-color: white; color: black }';
           inputStyle = {'backgroundColor': 'white', 'color': 'black'}
        }  
        let fmt = ({square, loss, time, type, player, bingo}) => {
            let name = this.getTeam(player).name
            switch(type) {
                case "square":
                    return  loss ? `${time}: ${name} lost square ${this.getSquareName(square)}!` : `${time}: ${name} completed square ${this.getSquareName(square)}`
                case "bingo":
                    return  loss ? `${time}: ${name} lost bingo ${bingo}!` : `${time}: ${name} got bingo ${bingo}`
                default:
                    return ""
            }
        }
        let eventlog = haveGame  ? (
            <Row className="py-2">
            <Col>
                <textarea style={inputStyle} className="w-100" rows={15} disabled value={this.state.events.map(ev => fmt(ev)).reverse().join("\n")}/>
            </Col>
            </Row>
        ) : null
        let headerText = haveGame && dispDiff ? `Bingo Game ${gameId} (${dispDiff})` : "Bingo!"
        let subheader = (haveGame && subtitle !== "") ? (
            <Row>
                <Col>
                    <Cent><h6>{subtitle}</h6></Cent>
                </Col>
            </Row>
        ) : null
        let bingoContent = haveGame ? (
            <Row className="align-items-center">
                <Col>
                    <BingoBoard dark={dark} cards={cards} activePlayer={activePlayer} hiddenPlayers={Object.keys(teams).filter(p => teams[p].hidden)}/>
                </Col>
                <PlayerList dark={dark} viewOnly={viewOnly} teams={teams} bingos={bingos} activePlayer={activePlayer} onPlayerListAction={this.onPlayerListAction}/>
            </Row>
            ) : null

        if(viewOnly) {
            if(headerText === "Bingo!")
                headerText = "Game not found"
            return (
                <Container className="pl-4 pr-4 pb-4 pt-2 mt-2 w-100">
                    <Helmet>
                        <style type="text/css">{pageStyle}</style>
                    </Helmet>
                    <NotificationContainer/>
                    <Row className="p-1">
                        <Col>
                            <Cent><h3>{headerText}</h3></Cent>
                        </Col>
                    </Row>
                    {subheader}
                    {bingoContent}
                    {eventlog}
                </Container>
            )
        }
        let spectatorLink = haveGame ? (<small> spectator link: {specLink}</small>) : null

        return (
            <Container className="pl-4 pr-4 pb-4 pt-2 mt-2 w-75">
            <Helmet>
                <style type="text/css">{pageStyle}</style>
            </Helmet>
                <NotificationContainer/>
                <SiteBar dark={dark} user={user}/>
                {this.createModal(inputStyle)}
                {this.loadingModal(inputStyle)}
                <Row className="p-1">
                    <Col>
                        <Cent><h3>{headerText}</h3></Cent>
                    </Col>
                </Row>
                {subheader}
                <Row className="align-items-center pt-1 pb-1">
                    <Col xs="auto">
                        <Button block color="primary" onClick={this.toggleCreate}>Create New Game</Button>
                    </Col><Col xs="auto">
                        <Button block onClick={() => this.joinGame()} disabled={!haveGame}>Join Game / Download Seed</Button>
                    </Col><Col xs="auto">
                        <Row className="align-items-left py-0 px-1 m-0">
                            <Col xs="auto"><Cent>
                                Player:
                            </Cent></Col>
                            <Col xs="5"><Cent>
                                <Input style={inputStyle} type="number" disabled={!haveGame} min="1" value={activePlayer} onChange={(e) => this.setState({activePlayer: parseInt(e.target.value, 10)})}/>
                            </Cent></Col>
                            <Col xs="auto"><Cent>
                                {activePlayer > 0 ? make_icons([activePlayer]) : null}
                            </Cent></Col>
                        </Row>
                    </Col>
                </Row>
                {bingoContent}
                {eventlog}
                <Row className="align-items-center pt-3">
                    {spectatorLink}
                </Row>
            </Container>
        )
    }
    loadingModal = (style) => { return (
        <Modal size="sm" isOpen={this.state.creatingGame } backdrop={"static"} className={"modal-dialog-centered"}>
            <ModalHeader style={style}><Cent>Please wait...</Cent></ModalHeader>
            <ModalBody style={style}>
                <Container fluid>
                    <Row className="p-2 justify-content-center align-items-center">
                        <Col xs="auto" className="align-items-center justify-content-center p-2">{this.state.loader}</Col>
                    </Row>
                </Container>
            </ModalBody>
        </Modal>
    )}
    createModal = (style) => { 
        return (
        <Modal size="lg" isOpen={this.state.createModalOpen} backdrop={"static"} className={"modal-dialog-centered"} toggle={this.toggleCreate}>
            <ModalHeader style={style} toggle={this.toggleCreate}><Cent>Bingo options</Cent></ModalHeader>
            <ModalBody style={style}>
                <Container fluid>
                    <Row className="p-1">
                        <Col xs="4" className="p1 border">
                            <Cent>Difficulty</Cent>
                        </Col><Col xs="6">
                            <ButtonGroup>
                                <Button active={this.state.difficulty === "easy"} outline={this.state.difficulty !== "easy"} onClick={() => this.setState({difficulty: "easy"})}>Easy</Button>
                                <Button active={this.state.difficulty === "normal"} outline={this.state.difficulty !== "normal"} onClick={() =>this.setState({difficulty: "normal"})}>Normal</Button>
                                <Button active={this.state.difficulty === "hard"} outline={this.state.difficulty !== "hard"} onClick={() => this.setState({difficulty: "hard"})}>Hard</Button>
                            </ButtonGroup>
                        </Col>
                    </Row>
                    <Row className="p-1">
                        <Col xs="4" className="p-1 border">
                            <Cent>Bingo Type</Cent>
                        </Col>
                        <Col xs="6">
                            <ButtonGroup>
                                <Button active={!this.state.isRandoBingo} outline={this.state.isRandoBingo} onClick={() => this.setState({isRandoBingo: false})}>Vanilla+</Button>
                                <Button active={this.state.isRandoBingo} outline={!this.state.isRandoBingo} onClick={() => this.setState({isRandoBingo: true})}>Rando</Button>
                            </ButtonGroup>
                        </Col>
                    </Row>
                    <Collapse isOpen={this.state.isRandoBingo}>
                        <Row className="p-1">
                            <Col xs="12" className="text-center p-1">
                                <Cent>Please generate a normal rando seed and input the game id below. (Don't download the generated seed! Use the join game link on this page)</Cent>
                            </Col>
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Rando Game ID</Cent>
                            </Col><Col xs="4">
                                <Input style={style} type="number" value={this.state.randoGameId}  onChange={(e) => this.setState({randoGameId: parseInt(e.target.value, 10)})}/>
                            </Col>
                        </Row>
                    </Collapse>
                    <Collapse isOpen={!this.state.isRandoBingo}>
                        <Row className="p-1">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Random Free Skill Count</Cent>
                            </Col><Col xs="4">
                                <Input style={style} type="number" value={this.state.startSkills}  onChange={(e) => this.setState({startSkills: parseInt(e.target.value, 10)})}/>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="p-1 border">
                                <Cent>Random Free Cell Count</Cent>
                            </Col><Col xs="4">
                                <Input style={style} type="number" value={this.state.startCells} onChange={(e) => this.setState({startCells: parseInt(e.target.value, 10)})}/>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Additional Pickups</Cent>
                            </Col><Col xs="8">
                                <PickupSelect style={style} value={this.state.startMisc} updater={(code, _) => this.setState({startMisc: code})}/>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center pt-1 border">
                                <Cent>Random Starting Items</Cent>
                            </Col><Col xs="4">
                                <ButtonGroup>
                                    <Button active={this.state.showInfo} outline={!this.state.showInfo} onClick={() => this.setState({showInfo: true})}>Show</Button>
                                    <Button active={!this.state.showInfo} outline={this.state.showInfo} onClick={() => this.setState({showInfo: false})}>Hide</Button>
                                </ButtonGroup>
                            </Col>
                        </Row>
                    </Collapse>
                </Container>
            </ModalBody>
            <ModalFooter style={style}>
                <Button color="primary" onClick={this.createGame}>Create Game</Button>
                <Button color="secondary" onClick={this.toggleCreate}>Cancel</Button>
            </ModalFooter>
        </Modal>
    )}
};
