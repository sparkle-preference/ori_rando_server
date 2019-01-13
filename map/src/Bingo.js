import React, {Component} from 'react';
import {Container, Row, Col, Collapse, Button, ButtonGroup, Modal, ModalHeader, Popover, PopoverBody, Badge,
        ModalBody, ModalFooter, Input, Card, CardBody, CardFooter, Media, UncontrolledButtonDropdown, DropdownToggle, DropdownMenu, DropdownItem} from 'reactstrap';
import {NotificationContainer, NotificationManager} from 'react-notifications';
import Countdown from 'react-countdown-now';
import {Helmet} from 'react-helmet';
import { confirmAlert } from 'react-confirm-alert'; 
import 'react-confirm-alert/src/react-confirm-alert.css' 

import {download} from './shared_map.js'
import {Cent, ordinal_suffix, doNetRequest, player_icons, get_random_loader, PickupSelect, get_flag, get_param} from './common.js'
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
                            <td><div style={rowStyle}>D1</div></td> 
                            <td><div style={rowStyle}>A</div></td> 
                            <td><div style={rowStyle}>B</div></td>
                            <td><div style={rowStyle}>C</div></td>
                            <td><div style={rowStyle}>D</div></td>
                            <td><div style={rowStyle}>E</div></td>
                        </tr>
                        {rows}
                        <tr style={{textAlign: 'center'}}>
                            <td><div style={rowStyle}>D2</div></td> 
                        </tr>
                    </tbody>
                </table>);
    }
}

const PlayerList = ({activePlayer, teams, viewOnly, onPlayerListAction, dark, teamsDisabled}) => {
    if(!teams)
        return null
    let dropdownStyle = {}
    let team_list = Object.keys(teams).map(cid => teams[cid])
    if(dark)
        dropdownStyle.backgroundColor = "#666"
    let players = team_list.map(({hidden, cap, teammates, name, bingos, place}) => {
            if(hidden)
                return null
            place = place || 0
            let hasTeam = teammates.length > 1
            let number = (bingos && bingos.length) || 0
            let text = `${name} (${number} lines)`
            let badge = place > 0 ? (<Badge color='primary'>{ordinal_suffix(place)}</Badge>) : null
            let active = activePlayer === cap
            let joinButton = viewOnly || teamsDisabled ? null : ( 
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
                            <Cent>{badge}{" "}{make_icons([cap])} {text}</Cent>
                        </Button>
                        <DropdownToggle caret color="secondary" />
                        <DropdownMenu style={dropdownStyle} right>
                            {joinButton}
                            <DropdownItem onClick={onPlayerListAction("hidePlayer", cap)}>
                                Hide Player
                            </DropdownItem>
                            <DropdownItem onClick={onPlayerListAction("redownloadSeed", cap)}>
                                Redownload seed
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
                                <DropdownToggle caret color="secondary" />
                                <DropdownMenu style={dropdownStyle} right>
                                    <DropdownItem onClick={onPlayerListAction("redownloadSeed", pid)}>
                                        Redownload seed
                                    </DropdownItem>
                                </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                )))
            if(place > 0)
                number += (team_list.length - place) * 12
            return [number, rows]
        })
                            // <UncontrolledButtonDropdown className="w-100 px-1">
                            //     <DropdownToggle size="sm" caret color="secondary" />
                            //     <DropdownMenu style={dropdownStyle} right>
                            //         <DropdownItem onClick={onPlayerListAction("hidePlayer", pid)}>
                            //             Hide Player
                            //         </DropdownItem>
                            //     </DropdownMenu>
                            // </UncontrolledButtonDropdown>


    let hiddenButton = team_list.some(t => t["hidden"]) ? (
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
                      activePlayer: 1, showInfo: false, user: get_param("user"), loadingText: "Building game...",
                      dark: dark, specLink: window.document.location.href.replace("board", "spectate"), lockout: false, squareCount: 13, 
                      fails: 0, gameId: gameId, startSkills: 3, startCells: 4, startMisc: "MU|TP/Swamp/TP/Valley", goalMode: "bingos",
                      start_with: "", difficulty: "normal", isRandoBingo: false, randoGameId: -1, viewOnly: viewOnly, buildingPlayer: false,
                      events: [], startTime: (new Date()), countdownActive: false, isOwner: false, targetCount: 3, reqsqrs: [],
                      teamsDisabled: true
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
        this.interval = setInterval(() => this.tick(), 2000);
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
    downloadSeedForPlayer = (player) => download("randomizer.dat", `Sync${this.state.gameId}.${player},${this.state.seed}`)
    joinGame = (joinTeam) => {
        joinTeam = joinTeam || false
        let {gameId, activePlayer, haveGame} = this.state;
        if(!haveGame) return;
        let nextPlayer = activePlayer;
        let players = Object.keys(this.state.teams)
        while(players.includes(String(nextPlayer)))
            nextPlayer++;
        this.setState({activePlayer: nextPlayer})
        let url = `/bingo/game/${gameId}/add/${nextPlayer}`
        if(joinTeam) 
            url += `?joinTeam=${joinTeam}`
        this.setState({buildingPlayer: true, loadingText: "Joining game..."}, doNetRequest(url, this.tickCallback))
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
            this.setState({fails: this.state.fails + 1, buildingPlayer: false})
        } else {
            let res = JSON.parse(responseText)
            let teams = res.teams
            Object.keys(teams).forEach(t => {
                let maybe_old = Object.keys(this.state.teams).filter(old => teams[t].cap === this.state.teams[old].cap)
                if(maybe_old.length > 0)
                    teams[t].hidden = this.state.teams[maybe_old[0]].hidden
            })
            if(res.gameId !== this.state.gameId)
            {
                console.log("Got pre-switch response. Ignoring it.")
                return;
            }
            let newState = {teams: teams, cards: res.cards, events: res.events, startTime: res.start_time_posix, countdownActive: res.countdown, isOwner: res.is_owner}
            if(!res.is_owner)
                newState.reqsqrs = res.required_squares || this.state.reqsqrs
            if(res.player_download)
            {
                this.downloadSeedForPlayer(res.player_download)
                newState.buildingPlayer = false;
            }
            this.setState(newState, this.updateUrl)
        }
    }
    createGame = () => {
        let {isRandoBingo, lockout, targetCount, goalMode, squareCount, reqsqrs, randoGameId, startSkills, startCells, startMisc, showInfo, difficulty, teamsDisabled} = this.state;
        let url
        if(isRandoBingo)
        {
            url = `/bingo/from_game/${randoGameId}?difficulty=${difficulty}`
        } else {
            url = `/bingo/new?skills=${startSkills}&cells=${startCells}&misc=${startMisc}&difficulty=${difficulty}`
            if(showInfo)
                url += "&showInfo=1"
        }
        if(goalMode === "bingos")
            url += `&lines=${targetCount}`
        else if(goalMode === "squares")
            url += `&squares=${squareCount}`
        if(reqsqrs.length > 0)
            url += `&squares=${reqsqrs.join(",")}`
        if(!teamsDisabled)
            url += "&teams=1"
        if(lockout)
            url += "&lockout=1"

        doNetRequest(url, this.createCallback)
        this.setState({creatingGame: true, loadingText: "Building game...", createModalOpen: false, loader: get_random_loader()})
    }
    createCallback = ({status, responseText}) => {
        if(status !== 200)
        {
            NotificationManager.error(`error ${status}: ${responseText}`, "error creating seed", 5000)
            this.setState({createModalOpen: false, haveGame: false, creatingGame: false}, this.updateUrl)
            return
        } else {
            let res = JSON.parse(responseText)
            this.setState({subtitle: res.subtitle, gameId: res.gameId, createModalOpen: false, creatingGame: false, haveGame: true, 
                          fails: 0, dispDiff: res.difficulty || this.state.difficulty, seed: res.seed, teams: res.teams, 
                          currentRecord: 0, cards: res.cards, events: res.events, reqsqrs: res.required_squares, targetCount: res.bingo_count, 
                          startTime: res.start_time_posix, isOwner: res.is_owner, countdownActive: res.countdown, teamsDisabled: !res.teams_allowed}, this.updateUrl)
        }
    }
    onPlayerListAction = (action, player) => () => {
        let cpid = this.getCap(player)
        switch(action) {
            case "hidePlayer":
                this.setState(prev => {
                    prev.teams[cpid].hidden = true
                    return {teams: prev.teams}
                })
                break;
            case "selectPlayer":
                this.setState({activePlayer: player})
                break;
            case "showHidden":
                this.setState(prev => {
                    Object.keys(prev.teams).forEach(p => prev.teams[p].hidden = false)
                    return {teams: prev.teams}
                })
                break;
            case "joinTeam":
                if(!this.state.teamsDisabled)
                    this.joinGame(player)
                break;
            case "deleteTeam":
                // if(this.state.startTime)
                    confirmAlert({
                        title: 'Remove player/team?',
                        message: `Really remove ${this.state.teams[cpid].name}?`,
                        buttons: [
                            {
                            label: 'Yeah',
                            onClick: () => { doNetRequest(`/bingo/game/${this.state.gameId}/remove/${cpid}`, this.tickCallback); }
                            },
                            {
                            label: 'Just kidding',
                            onClick: () => { return; }
                            }
                        ]
                    })
                // else 
                //     doNetRequest(`/bingo/game/${this.state.gameId}/remove/${cpid}`, this.tickCallback)
                break;
            case "redownloadSeed":
                this.downloadSeedForPlayer(player)
            break;
            default:
                console.log("Unknown action: " + action)
                break
        }
    }

    toggleCreate = () => this.setState({createModalOpen: !this.state.createModalOpen})
    getCap = (pid) => {
        if(this.state.teams.hasOwnProperty(pid))
            return pid
        let teams = Object.keys(this.state.teams).filter(cpid => this.state.teams[cpid].teammates.includes(pid))
        if(teams.length > 1)
            console.log(`Multiple teams found for player ${pid}! ${teams}`)
        return teams[0]
    }
    getSquareName = (sq) => this.state.cards[sq].disp_name
    render = () => {
        let {specLink, viewOnly, isOwner, dark, activePlayer, teamsDisabled, startTime, subtitle, cards, haveGame, gameId, user, dispDiff, teams, loadingText} = this.state
        let pageStyle, inputStyle
        if(dark) {
            pageStyle = 'body { background-color: #333; color: white }';
            inputStyle = {'backgroundColor': '#333', 'color': 'white'}
        } else {
           pageStyle = 'body { background-color: white; color: black }';
           inputStyle = {'backgroundColor': 'white', 'color': 'black'}
        }
        let creatorControls = isOwner && !startTime ? (
            <Row>
                <Col xs="4">
                    <Button block onClick={() => doNetRequest(`/bingo/game/${gameId}/start`, this.tickCallback)} disabled={!!startTime}>Start game</Button>
                </Col>
            </Row>
        ) : null
        let fmt = ({square, first, loss, time, type, player, bingo}) => {
            let cpid = this.getCap(player)
            if (!cpid) return ""
            let name = this.state.teams[cpid].name
            switch(type) {
                case "square":
                    return  loss ? `${time}: ${name} lost square ${this.getSquareName(square)}!` : `${time}: ${name} completed square ${this.getSquareName(square)}`
                case "bingo":
                    let txt =  loss ? `${time}: ${name} lost bingo ${bingo}!` : `${time}: ${name} got bingo ${bingo}`
                    if(!loss && first)
                    {
                        let cnt = this.state.teams[cpid].bingos.length
                        txt += `\n${name} is the first to ${cnt} bingo${cnt === 1 ? '' : 's'}`
                    }
                    return txt
                case "win":
                    return `${time}: ${name} finished in ${ordinal_suffix(this.state.teams[cpid].place)} place`
                default:
                    return ""
            }
        }
        let eventlog = haveGame  ? (
            <Row className="py-2">
            <Col>
                <textarea style={inputStyle} className="w-100" rows={15} disabled value={this.state.events.map(ev => fmt(ev)).reverse().filter(l => l !== "").join("\n")}/>
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
                    <PlayerList dark={dark} teamsDisabled={teamsDisabled} viewOnly={viewOnly} teams={teams} activePlayer={activePlayer} onPlayerListAction={this.onPlayerListAction}/>
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
                {this.loadingModal(inputStyle, loadingText)}
                {this.countdownModal(inputStyle)}
                <Row className="p-1">
                    <Col>
                        <Cent><h3>{headerText}</h3></Cent>
                    </Col>
                </Row>
                {subheader}
                {creatorControls}
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
    loadingModal = (style, text) => { return (
        <Modal size="sm" isOpen={this.state.creatingGame || this.state.buildingPlayer} backdrop={"static"} className={"modal-dialog-centered"}>
            <ModalHeader style={style}><Cent>{text}</Cent></ModalHeader>
            <ModalBody style={style}>
                <Container fluid>
                    <Row className="p-2 justify-content-center align-items-center">
                        <Col xs="auto" className="align-items-center justify-content-center p-2">{this.state.loader}</Col>
                    </Row>
                </Container>
            </ModalBody>
        </Modal>
    )}
    countdownModal = (style) => { 
        let {countdownActive, startTime} = this.state
        // let d = new Date()
        // let time = (startTime - (d.getTime())/1000);
        // if (!isNaN(time) && time >= -2 && time <= 100000) {
        //     countdownActive = true;
        // } else {
        //     countdownActive = false;
        // }
        return (
        <Modal size="sm" isOpen={countdownActive} backdrop={"static"} className={"modal-dialog-centered"}>
            <ModalHeader style={style}><Cent>Game Starting!</Cent></ModalHeader>
            <ModalBody style={style}>
                <Container fluid>
                    <Countdown
                        date={startTime*1000}
                        precision={3}
                        intervalDelay={2}
                        now={() => (new Date()).getTime()}
                        renderer={({ seconds, milliseconds, completed }) =>
                            completed ? (<Cent><h3>Go!</h3></Cent>) : (<Cent><h3>{seconds}:{milliseconds}</h3></Cent>)
                        }
                    />
            </Container>
            </ModalBody>
        </Modal>
    )}
    createModal = (style) => { 
        let {difficulty, isRandoBingo, randoGameId, targetCount, startSkills, startCells, startMisc, showInfo, teamsDisabled, lockout, squareCount, goalMode} = this.state
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
                                <Button active={difficulty === "easy"} outline={difficulty !== "easy"} onClick={() => this.setState({difficulty: "easy"})}>Easy</Button>
                                <Button active={difficulty === "normal"} outline={difficulty !== "normal"} onClick={() =>this.setState({difficulty: "normal"})}>Normal</Button>
                                <Button active={difficulty === "hard"} outline={difficulty !== "hard"} onClick={() => this.setState({difficulty: "hard"})}>Hard</Button>
                            </ButtonGroup>
                        </Col>
                    </Row>

                    <Row className="p-1">
                        <Col xs="4" className="p-1 border">
                            <Cent>Teams?</Cent>
                        </Col>
                        <Col xs="6">
                            <ButtonGroup>
                                <Button active={teamsDisabled} outline={!teamsDisabled} onClick={() => this.setState({teamsDisabled: true})}>Solo</Button>
                                <Button active={!teamsDisabled} outline={teamsDisabled} onClick={() => this.setState({teamsDisabled: false})}>Teams</Button>
                            </ButtonGroup>
                        </Col>
                    </Row>
                    <Row className="p-1">
                        <Col xs="4" className="p-1 border">
                            <Cent>Lockout?</Cent>
                        </Col>
                        <Col xs="6">
                            <ButtonGroup>
                                <Button active={!lockout} outline={lockout} onClick={() => this.setState({lockout: false})}>Standard</Button>
                                <Button active={lockout} outline={!lockout} onClick={() => this.setState({lockout: true})}>Lockout</Button>
                            </ButtonGroup>
                        </Col>
                    </Row>
                    <Row className="p-1">
                        <Col xs="4" className="p-1 border">
                            <Cent>Goal Modes</Cent>
                        </Col>
                        <Col xs="6">
                            <ButtonGroup>
                                <Button active={goalMode === "bingos"} outline={goalMode !== "bingos"} onClick={() => this.setState({goalMode: "bingos"})}>Lines</Button>
                                <Button active={goalMode === "squares"} outline={goalMode !== "squares"} onClick={() => this.setState({goalMode: "squares"})}>Squares</Button>
                            </ButtonGroup>
                        </Col>
                    </Row>
                    <Collapse isOpen={goalMode === "squares"}>
                        <Row className="p-1">
                            <Col xs="4" className="p1 border">
                                <Cent>Squares to win</Cent>
                            </Col><Col xs="4">
                                <Input style={style} type="number" value={squareCount}  onChange={(e) => this.setState({squareCount: parseInt(e.target.value, 10)})}/>
                            </Col>
                        </Row>
                    </Collapse>
                    <Collapse isOpen={goalMode === "bingos"}>
                        <Row className="p-1">
                            <Col xs="4" className="p1 border">
                                <Cent>Bingos to win</Cent>
                            </Col><Col xs="4">
                                <Input style={style} type="number" value={targetCount}  onChange={(e) => this.setState({targetCount: parseInt(e.target.value, 10)})}/>
                            </Col>
                        </Row>
                    </Collapse>
                    <Row className="p-1">
                        <Col xs="4" className="p-1 border">
                            <Cent>Bingo Type</Cent>
                        </Col>
                        <Col xs="6">
                            <ButtonGroup>
                                <Button active={!isRandoBingo} outline={isRandoBingo} onClick={() => this.setState({isRandoBingo: false})}>Vanilla+</Button>
                                <Button active={isRandoBingo} outline={!isRandoBingo} onClick={() => this.setState({isRandoBingo: true})}>Rando</Button>
                            </ButtonGroup>
                        </Col>
                    </Row>
                    <Collapse isOpen={isRandoBingo}>
                        <Row className="p-1">
                            <Col xs="12" className="text-center p-1">
                                <Cent>Make a rando seed {" "} <a href="/" target="_blank">here</a> {" "} with web tracking on, then paste the game id from the url into the box below.</Cent>
                            </Col>
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Rando Game ID</Cent>
                            </Col><Col xs="4">
                                <Input style={style} type="number" value={randoGameId}  onChange={(e) => this.setState({randoGameId: parseInt(e.target.value, 10)})}/>
                            </Col>
                        </Row>
                    </Collapse>
                    <Collapse isOpen={!isRandoBingo}>
                        <Row className="p-1">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Random Free Skill Count</Cent>
                            </Col><Col xs="4">
                                <Input style={style} type="number" value={startSkills}  onChange={(e) => this.setState({startSkills: parseInt(e.target.value, 10)})}/>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="p-1 border">
                                <Cent>Random Free Cell Count</Cent>
                            </Col><Col xs="4">
                                <Input style={style} type="number" value={startCells} onChange={(e) => this.setState({startCells: parseInt(e.target.value, 10)})}/>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Additional Pickups</Cent>
                            </Col><Col xs="8">
                                <PickupSelect style={style} value={startMisc} updater={(code, _) => this.setState({startMisc: code})}/>
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center pt-1 border">
                                <Cent>Random Starting Items</Cent>
                            </Col><Col xs="4">
                                <ButtonGroup>
                                    <Button active={showInfo} outline={!showInfo} onClick={() => this.setState({showInfo: true})}>Show</Button>
                                    <Button active={!showInfo} outline={showInfo} onClick={() => this.setState({showInfo: false})}>Hide</Button>
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
