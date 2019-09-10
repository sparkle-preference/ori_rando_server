import React, {Component} from 'react';
import {Container, Row, Col, Collapse, Button, ButtonGroup, Modal, ModalHeader, Popover, PopoverBody, Badge,
        ModalBody, ModalFooter, Input, Card, CardBody, CardFooter, Media, UncontrolledButtonDropdown, DropdownToggle, DropdownMenu, DropdownItem} from 'reactstrap';
import {NotificationContainer, NotificationManager} from 'react-notifications';
import Countdown from 'react-countdown-now';
import { confirmAlert } from 'react-confirm-alert';
import 'react-confirm-alert/src/react-confirm-alert.css'
import 'react-notifications/lib/notifications.css';

import {download} from './shared_map.js'
import {Cent, ordinal_suffix, doNetRequest, player_icons, get_random_loader, PickupSelect, get_flag, get_param, dev} from './common.js'
import SiteBar from "./SiteBar.js";


const iniUrl = new URL(window.document.URL);
const cardTextSize = iniUrl.searchParams.get("textSize") || "1.5vh"
const hideFooter = iniUrl.searchParams.has("hideFooter")
const hideLabels = iniUrl.searchParams.has("hideLabels")

const make_icons = players => players.map(p => (<Media key={`playerIcon${p}`} object style={{width: "25px", height: "25px"}} src={player_icons(p, false)} alt={"Icon for player "+p} />))
const BingoCard = ({card, progress, players, help, dark, selected, onSelect, colors}) => {
    let cardStyles = {width: '18vh', height: '18vh', minWidth: '120px', maxWidth: '200px', minHeight: '120px', maxHeight: '200px', flexGrow: 1}
    let footerStyles = {}
    cardStyles.border = '1px solid'
    cardStyles.borderColor = colors.border
    // footerStyles.background = colors.footer
    if(selected)
        cardStyles.background = colors.selected
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
        let line = subgoals[subgoal].disp_name
        if(progress.subgoals && progress.subgoals.includes(subgoal))
        {
            if(progress.completed)
                line = (<u>{line}</u>)
            else
                styles.background = colors.complete
        }
        text.push((<div className="w-100" key={`card-line-${j++}`} style={styles}>{line}</div>))
    })
    if(target) {
        text.push((<div className="w-100" key={`card-line-${j++}`}>({progress.count ? `${progress.count}/` : ""}{target})</div>))
    }
    let className = "px-0 pb-0 justify-content-center text-center align-items-center d-flex " + ((text.length > 1) ? "pt-0 flex-column" : "pt-1")

    if(help_lines && help_lines.length > 0) {
        let helpText = help_lines.map((l,i) => (<div key={`help-line-${i}`}>{l}</div>))
        helpLink = (
            <div className="m-0 p-0 float-left"><Button color="link" className="pl-1 pt-1 pb-0 pr-0 m-0" id={"help-"+i} key={"help-"+i} onClick={toggle}>?</Button></div>
            )
        popover = (
            <Popover placement="top" isOpen={open} target={"help-"+i} toggle={toggle}>
            <PopoverBody>{helpText}</PopoverBody>
            </Popover>
        )
    }

    if(progress.completed)
        cardStyles.background = colors.complete
    let footer = hideFooter ? null : (
        <CardFooter style={footerStyles} className="p-0 text-center">
            {helpLink}
            {popover}
            {make_icons(players)}
        </CardFooter>
    ) 
    return (
        <Card inverse={dark} style={cardStyles}>
            <CardBody onClick={onSelect} style={{fontSize: cardTextSize, fontWeight: "bold"}} className={className}>
                {text}
            </CardBody>
            {footer}
        </Card>
    )
}



class BingoBoard extends Component {
    constructor(props) {
        super(props);
        let {cards} = props
        this.state = {helpOpen: cards.map(_ => false), selected: cards.map(_ => false)}
    }
    helpToggle = (cardNum) => () => this.setState(prev => {
        prev.helpOpen[cardNum]  = !prev.helpOpen[cardNum]
        return {helpOpen: prev.helpOpen}
    })
    selectToggle = (cardNum) => () => this.setState(prev => {
        prev.selected[cardNum]  = !prev.selected[cardNum]
        return {selected: prev.selected}
    })
    render() {
        let {cards, bingos, colors, hiddenPlayers, activePlayer, activeTeam, dark} = this.props
        if(!cards || cards.length < 25) {
            return null
        }
        let rows = [], i = 0;
        let colStyle = (b) => ({height: "22px", textAlign: 'center', background: bingos.includes(b) ? colors.complete : 'inherit'})
        let rowStyle = (b) => ({textAlign: 'center', visibility: hideLabels ? 'hidden' : 'inherit', width: "22px", background: bingos.includes(b) ? colors.complete : 'inherit'})
        while(rows.length < 5) {
            let row = []
            while(row.length < 5) {
                let card = cards[i];
                let players = card.completed_by.filter(p => !hiddenPlayers.includes(parseInt(p, 10)));
                let progress = card.progress.hasOwnProperty(activePlayer) ? card.progress[activePlayer] : {'completed': false, 'count': 0, 'subgoals': []}
                // temp bullshit
                progress.completed = card.completed_by.includes(activePlayer) || card.completed_by.includes(activeTeam)
                row.push((<td key={i}><BingoCard colors={colors} selected={this.state.selected[i]} onSelect={this.selectToggle(i)} dark={dark} card={card} progress={progress} help={{i: i, open: this.state.helpOpen[i], toggle: this.helpToggle(i)}} players={players} /></td>))
                i++
            }
            let rowNum = rows.length + 1
            let rowLabel = (<td className={"rounded"} style={rowStyle(`Row ${rowNum}`)}><div>{rowNum}</div></td>)
            rows.push((<tr key={`row-${rowNum}`}>{rowLabel}{row}{rowLabel}</tr>))
        }

        return (<table>
                    <tbody>
                        <tr style={{visibility: hideLabels ? 'hidden' : 'inherit'}}>
                            <td><div className="rounded" style={colStyle("A1-E5")}>X</div></td>
                            <td><div className="rounded" style={colStyle("Col A")}>A</div></td>
                            <td><div className="rounded" style={colStyle("Col B")}>B</div></td>
                            <td><div className="rounded" style={colStyle("Col C")}>C</div></td>
                            <td><div className="rounded" style={colStyle("Col D")}>D</div></td>
                            <td><div className="rounded" style={colStyle("Col E")}>E</div></td>
                            <td><div className="rounded" style={colStyle("E1-A5")}>Y</div></td>
                        </tr>
                        {rows}
                        <tr style={{visibility: hideLabels ? 'hidden' : 'inherit', textAlign: 'center'}}>
                            <td><div className="rounded" style={colStyle("E1-A5")}>Y</div></td>
                            <td><div className="rounded" style={colStyle("Col A")}>A</div></td>
                            <td><div className="rounded" style={colStyle("Col B")}>B</div></td>
                            <td><div className="rounded" style={colStyle("Col C")}>C</div></td>
                            <td><div className="rounded" style={colStyle("Col D")}>D</div></td>
                            <td><div className="rounded" style={colStyle("Col E")}>E</div></td>
                            <td><div className="rounded" style={colStyle("A1-E5")}>X</div></td>
                        </tr>
                    </tbody>
                </table>);
    }
}

const PlayerList = ({activePlayer, teams, viewOnly, isOwner, timerTime, onPlayerListAction, userBoard, userBoardParams, gameId, teamMax, teamsDisabled}) => {
    if(!teams)
        return null
    let team_list = Object.keys(teams).map(cid => teams[cid])
    let players = team_list.map(({hidden, cap, teammates, name, bingos, place, score}) => {

            if(hidden)
                return null
            place = place || 0
            score = score || 0
            let hasTeam = teammates.length > 0
            let canJoin = teamMax === -1 ? true : teammates.length + 1 < teamMax
            let number = (bingos && bingos.length) || 0
            let text = `${name} | ${number} lines`
            if(score)
                text += `, (${score}/25)`
            let badge = place > 0 ? (<Badge color='primary'>{ordinal_suffix(place)}</Badge>) : null
            let active = activePlayer === cap.pid
            let joinButton = viewOnly || !canJoin || teamsDisabled ? null : (
                <DropdownItem onClick={onPlayerListAction("joinTeam", cap.pid)}>
                    Join Team
                </DropdownItem>
            )
            let removeButton = isOwner ? ( 
                <DropdownItem onClick={onPlayerListAction("deleteTeam", cap.pid)}>
                    Remove {teamsDisabled ? "Player" : "Team"}
                </DropdownItem>

            ) : null
            if(active)
                text = (<b>{text}</b>)
            let rows = [(
                <Row key={`player-list-${cap.pid}`} className="px-1 text-center pb-2">
                    <Col className="p-0">
                    <UncontrolledButtonDropdown className="w-100 px-1">
                        <Button color="secondary" active={active} block onClick={onPlayerListAction("selectPlayer", cap.pid)}>
                            <Cent>{badge}{" "}{make_icons([cap.pid])} {text}</Cent>
                        </Button>
                        <DropdownToggle caret color="secondary" />
                        <DropdownMenu right>
                            {joinButton}
                            {removeButton}
                            <DropdownItem onClick={onPlayerListAction("hidePlayer", cap.pid)}>
                                Hide Player
                            </DropdownItem>
                            <DropdownItem href={`/bingo/game/${gameId}/seed/${cap.pid}`} target="_blank">
                                Redownload seed
                            </DropdownItem>
                        </DropdownMenu>
                        </UncontrolledButtonDropdown>
                    </Col>
                </Row>
            )]
            if(hasTeam)
                rows = rows.concat(teammates.map(({pid, name}) => {
                let removePlayer = isOwner ? ( 
                            <DropdownItem onClick={onPlayerListAction("deleteTeam", pid, name)}>
                                Remove Player
                            </DropdownItem>
                ) : null
                    return (
                    <Row key={`subplayer-list-${pid}`} className="px-2 text-center pb-2">
                        <Col xs={{offset: 2, size: 10}} className="p-0">
                            <UncontrolledButtonDropdown className="w-100 px-1">
                                <Button size="sm" color="secondary" active={pid === activePlayer} block onClick={onPlayerListAction("selectPlayer", pid)}>
                                    <Cent>{make_icons([pid])}{name}</Cent>
                                </Button>
                                <DropdownToggle caret color="secondary" />
                                <DropdownMenu right>
                                    {removePlayer}
                                    <DropdownItem  href={`/bingo/game/${gameId}/seed/${pid}`} target="_blank">
                                        Redownload seed
                                    </DropdownItem>
                                </DropdownMenu>
                            </UncontrolledButtonDropdown>
                        </Col>
                    </Row>
                )}))
            if(place > 0)
                number += (team_list.length - place) * 12
            return [number, rows]
        })

    let hiddenButton = team_list.some(t => t.hidden) ? (
        <Row className="pb-2">
            <Button block size="sm" color="link" onClick={onPlayerListAction("showHidden", 0)}>
                Show all hidden
            </Button>
        </Row>
    ): null

    players = players.filter(p => p != null).sort((a, b) => b[0] - a[0]).map(p => p[1])

    let colStyle= {minWidth: '200px', maxWidth: '420px'}
    if(userBoard) {
        colStyle = {width: `${userBoardParams.listWidth}px`, height: `${userBoardParams.listHeight}px`}
    }
    let timerText = timerTime ? `Time Elapsed: ${timerTime}` : `Time Elapsed: 00.00`
    return (
        <Col xs="auto" style={colStyle} className="border border-info">
            <Row  className="px-1 pb-2"><h6>{timerText}</h6></Row>
            <Row  className="px-1 pb-2"><Cent><h4>Players</h4></Cent></Row>
            {players}
            {hiddenButton}
        </Col>
    );
}

export default class Bingo extends React.Component {
    constructor(props) {
        super(props);
        let viewOnly = iniUrl.href.includes("bingo/spectate")
        let userBoard = iniUrl.href.includes("bingo/userboard")
        let userBoardParams = userBoard ? {
            showLog: iniUrl.searchParams.has("eventLog") || false,
            showList: iniUrl.searchParams.has("playerList") || false,
            logWidth: parseInt(iniUrl.searchParams.get("logWidth") || 500, 10),
            logHeight: parseInt(iniUrl.searchParams.get("logHeight") || 200, 10),
            listWidth: parseInt(iniUrl.searchParams.get("listWidth") || 300, 10),
            listHeight: parseInt(iniUrl.searchParams.get("listHeight") || 400, 10),
        } : {}


        let gameId = parseInt(iniUrl.searchParams.get("game_id") || -1, 10);
        if(viewOnly && gameId)
            gameId = (gameId - 4)/7
        let fromGen = iniUrl.searchParams.has("fromGen")
        let teamMax = parseInt(iniUrl.searchParams.get("teamMax") || -1, 10);
        let seed = iniUrl.searchParams.get("seed") || String(Math.floor(Math.random() * 100000));
        let dark = get_flag("dark") || iniUrl.searchParams.has("dark")
        let user = get_param("user")
        let targetCount = fromGen && (teamMax > 1) ? 5 : 3
        this.state = {
                      cards: [], currentRecord: 0, haveGame: false, creatingGame: false, createModalOpen: true, offset: 0, noTimer: false,
                      activePlayer: parseInt(get_param("pref_num") || 1, 10), showInfo: false, user: user, loadingText: "Loading...", paramId: -1, squareCount: 13, seed: seed,
                      dark: dark, specLink: window.document.location.href.replace("board", "spectate").replace(gameId, 4 + gameId*7), 
                      fails: 0, gameId: gameId, startSkills: 3, startCells: 4, startMisc: "MU|TP/Swamp/TP/Valley", goalMode: "bingos",
                      start_with: "", difficulty: "normal", isRandoBingo: false, randoGameId: -1, viewOnly: viewOnly, buildingPlayer: false,
                      events: [], startTime: (new Date()), countdownActive: false, isOwner: false, targetCount: targetCount, userBoard: userBoard,
                      teamsDisabled: (teamMax === -1), fromGen: fromGen, teamMax: teamMax, ticksSinceLastSquare: 0, userBoardParams: userBoardParams
                    };
        if(gameId > 0)
        {
            if(fromGen)
            {
                this.state.isRandoBingo = true
                this.state.randoGameId = gameId
            }
            let url = `/bingo/game/${gameId}/fetch?first=1&time=${(new Date()).getTime()}`
            doNetRequest(url, this.createCallback)
            this.state.creatingGame = true
            this.state.createModalOpen = false
            this.state.loader = get_random_loader()
        } else if(userBoard)
        {
            doNetRequest(`/bingo/userboard/${user}/fetch/${gameId}?time=${(new Date()).getTime()}`, this.createCallback)
            this.state.creatingGame = true
            this.state.createModalOpen = false
            this.state.loader = get_random_loader()
        }

    }

    componentWillMount() {
        this.tick()
        this.interval = setInterval(() => this.tick(),  1000);
        this.timerInterval = setInterval(() => this.updateTimer(), 10);
  };
    updateUrl = () => {
        let {gameId, fromGen, viewOnly, userBoard} = this.state;
        if(userBoard)
            return
        let url = new URL(window.document.URL);
        let title = "OriDE Bingo"
        if(gameId && gameId > 0 && !viewOnly)
        {
            url.searchParams.set("game_id", gameId)
            title += `: Game ${gameId}`
        }
        else
            url.searchParams.delete("game_id")
        
        if(url.searchParams.has("fromGen") && !fromGen)
        {
            url.searchParams.delete("fromGen")
            if(url.searchParams.has("teamMax"))
                url.searchParams.delete("teamMax")
            if(url.searchParams.has("seed"))
                url.searchParams.delete("seed")
        }
        else if(!url.searchParams.has("fromGen") && fromGen)
            url.searchParams.set("fromGen", 1)

        window.history.replaceState('', title, url.href);
        document.title = title
        this.setState({specLink: window.document.location.href.replace("board", "spectate").replace(gameId, 4 + gameId*7)})
    }
    joinGame = (joinTeam) => {
        joinTeam = joinTeam || false
        let {gameId, activePlayer, haveGame} = this.state;
        if(!haveGame) return;
        let nextPlayer = activePlayer;
        let players = []
        Object.keys(this.state.teams).forEach(cap => {
            let team = this.state.teams[cap];
            players.push(team.cap.pid);
            players = players.concat(team.teammates.map(t => t.pid));
        })
        while(players.includes(nextPlayer))
            nextPlayer++;
        this.setState({activePlayer: nextPlayer})
        let url = `/bingo/game/${gameId}/add/${nextPlayer}`
        if(joinTeam)
            url += `?joinTeam=${joinTeam}`
        this.setState({buildingPlayer: true, loadingText: "Joining game..."}, doNetRequest(url, this.tickCallback))
    }
    tick = () => {
        let {fails, gameId, haveGame, ticksSinceLastSquare, user, userBoard} = this.state;
        if(fails > 50)
            return
        if((gameId && gameId > 0 && haveGame) || userBoard)
        {
            if(
                (ticksSinceLastSquare > 14400 && ticksSinceLastSquare % 60 !== 0) ||
                (ticksSinceLastSquare > 7200 && ticksSinceLastSquare % 30 !== 0) ||
                (ticksSinceLastSquare > 3600 && ticksSinceLastSquare % 15 !== 0) ||
                (ticksSinceLastSquare > 1200 && ticksSinceLastSquare % 5 !== 0)
            )
                return
            if(userBoard)
                doNetRequest(`/bingo/userboard/${user}/fetch/${gameId}`, this.tickCallback)
            else
                doNetRequest(`/bingo/game/${gameId}/fetch`, this.tickCallback)
        }
    }
    tickCallback = ({status, responseText}) => {
        if(status !== 200)
        {
            let stateUpdate = {fails: this.state.fails + 1, buildingPlayer: false}
            if(status === 409)
                stateUpdate.activePlayer = this.state.activePlayer + 1
            if(this.state.fails < 5 || (this.state.fails - 1) % 5 === 0)
                NotificationManager.error(`error ${status}: ${responseText}`, "error", 5000)
            this.setState(stateUpdate)
        } else {
            let res = JSON.parse(responseText)
            let newState = {events: res.events, startTime: res.start_time_posix, countdownActive: res.countdown, isOwner: res.is_owner}
            if(res.gameId !== this.state.gameId)
            {
                if(this.state.userBoard && this.state.user)
                    return this.createCallback({status: status, responseText: responseText})
                else {
                    console.log("Got pre-switch response. Ignoring it.")
                    return;
                }
            }
            
            let teams = res.teams
            newState.ticksSinceLastSquare = this.state.ticksSinceLastSquare + 1
            Object.keys(teams).forEach(t => {
                let maybe_old = Object.keys(this.state.teams).filter(old => teams[t].cap.pid === this.state.teams[old].cap.pid)
                if(maybe_old.length > 0)
                {
                    teams[t].hidden = this.state.teams[maybe_old[0]].hidden
                    if(teams[t].score !== this.state.teams[maybe_old[0]].score)
                        newState.ticksSinceLastSquare = 0
                }
            })
            newState.teams = teams
            newState.cards = [...this.state.cards]
            if(newState.cards.length !== res.cards.length)
                console.log("error! card array length mismatch")
            for(let i = 0; i < res.cards.length; i++) {
                if(res.cards[i].name !== newState.cards[i].name)
                    console.log(`card update mismatch! square ${i}, ${res.cards[i].name} was not ${newState.cards[i].name}`)
                newState.cards[i].progress = {...res.cards[i].progress}
                newState.cards[i].completed_by = res.cards[i].completed_by
            }
            if(res.offset)
                newState.offset = res.offset
            if(res.player_seed)
            {
                if(!dev)
                    download("randomizer.dat", res.player_seed);
                newState.buildingPlayer = false;
            }
            this.setState(newState, this.updateUrl)
        }
    }
    createGame = () => {
        let {isRandoBingo, noTimer, targetCount, goalMode, squareCount, randoGameId, startSkills, startCells, startMisc, showInfo, difficulty, teamsDisabled, seed} = this.state;
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
        if(!teamsDisabled)
            url += "&teams=1"
        if(noTimer)
            url += "&no_timer=1"
        url += `&seed=${seed}`

        doNetRequest(url+`&time=${(new Date()).getTime()}`, this.createCallback)
        this.setState({creatingGame: true, loadingText: "Building game...", createModalOpen: false, loader: get_random_loader()})
    }
    createCallback = ({status, responseText}) => {
        if(status !== 200)
        {
            if(this.state.fromGen && status === 404)
            {
                this.setState({createModalOpen: true, creatingGame: false})
                return;
            }
            NotificationManager.error(`error ${status}: ${responseText}`, "error creating seed", 5000)
            this.setState({createModalOpen: false, haveGame: false, creatingGame: false}, this.updateUrl)
            return
        } else {
            let res = JSON.parse(responseText)
            let {activePlayer, dispDiff, offset, user} = this.state
            if(user)
                Object.keys(res.teams).some(t => {
                    let team = res.teams[t]
                    if(team.cap.name === user)
                    {
                        activePlayer = team.cap.pid
                        return true
                    }
                    return team.teammates.some(tm => {
                       if(tm.name === user) {
                           activePlayer = tm.pid
                           return true
                       }
                       return false
                    })
                })
            this.setState({subtitle: res.subtitle, gameId: res.gameId, createModalOpen: false, creatingGame: false, haveGame: true, offset: res.offset || offset,
                          fails: 0, dispDiff: res.difficulty || dispDiff, teams: res.teams, paramId: res.paramId, activePlayer: activePlayer,
                          currentRecord: 0, cards: res.cards, events: res.events, targetCount: res.bingo_count, fromGen: false, teamMax: res.teamMax || -1,
                          startTime: res.start_time_posix, isOwner: res.is_owner, countdownActive: res.countdown, teamsDisabled: !res.teams_allowed}, this.updateUrl)
        }
    }
    onPlayerListAction = (action, player, name) => () => {
        let cpid = this.getCap(player)
        if(cpid === player)
            name = this.state.teams[cpid].name
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
                if(this.state.startTime)
                    confirmAlert({
                        title: 'Are you sure?',
                        message: `Really remove ${name}?`,
                        buttons: [
                            {
                            label: 'Yeah',
                            onClick: () => { doNetRequest(`/bingo/game/${this.state.gameId}/remove/${player}`, this.tickCallback); }
                            },
                            {
                            label: 'Just kidding',
                            onClick: () => { return; }
                            }
                        ]
                    })
                else
                     doNetRequest(`/bingo/game/${this.state.gameId}/remove/${cpid}`, this.tickCallback)
                break;
            default:
                console.log("Unknown action: " + action)
                break
        }
    }

    toggleCreate = () => this.setState({createModalOpen: !this.state.createModalOpen, fromGen: false, teamMax: -1}, this.updateUrl)
    getCap = (pid) => {
        if(!this.state.teams)
        {
            console.log("no teams found?")
            return pid
        }
        if(this.state.teams.hasOwnProperty(pid))
            return pid
        let teams = Object.keys(this.state.teams).filter(cpid => this.state.teams[cpid].teammates.some(t => t['pid'] === pid))
        if(teams.length > 1)
            console.log(`Multiple teams found for player ${pid}! ${teams}`)
        return parseInt(teams[0], 10)
    }
    getSquareName = (sq, withCoords) => {
        withCoords = withCoords || true
        if(withCoords)
        {
            let col = {0: "A", 1: "B", 2: "C", 3: "D", 4: "E"}[(sq % 5)]
            let row = Math.floor(sq / 5) + 1

            return `${this.state.cards[sq].disp_name} (${col}${row})`
        }
        return this.state.cards[sq].disp_name
    }
    render = () => {
        let {specLink, viewOnly, isOwner, dark, activePlayer, startTime, paramId, teamsDisabled, userBoardParams,
            subtitle, cards, haveGame, gameId, user, dispDiff, teams, loadingText, userBoard} = this.state
        let s = getComputedStyle(document.body);
        let inputStyle = {'borderColor': s.getPropertyValue('--dark'), 'backgroundColor': s.getPropertyValue("background-color"), 'color': s.getPropertyValue("color")}

        let colors = {
            complete: s.getPropertyValue("--teal"),
            selected: s.getPropertyValue("--cyan"),
            border: s.getPropertyValue("--dark")
        }

        let creatorControls = isOwner && !startTime ? (
            <Row className="align-items-center justify-content-center p-2">
                <Col xs="auto">
                    <Button block onClick={() => doNetRequest(`/bingo/game/${gameId}/start?time=${(new Date()).getTime()}`, this.tickCallback)} color="success" disabled={!!startTime}>Start game</Button>
                </Col>
            </Row>
        ) : null
        let fmt = ({square, first, loss, time, type, player, bingo}) => {
            if(type.startsWith("misc"))
                return `${time}: ${type.substr(4)}`
            let cpid = this.getCap(player)
            if (!cpid) 
            {
                return ""
            }
            let {name} = this.state.teams[cpid]
            switch(type) {
                case "square":
                    return  loss ? `${time}: ${name} lost square ${this.getSquareName(square)}!` : `${time}: ${name} completed square ${this.getSquareName(square)}`
                case "bingo":
                    let txt =  loss ? `${time}: ${name} lost bingo ${bingo}!` : `${time}: ${name} got bingo ${bingo}!`
                    if(!loss && first)
                    {
                        txt += ` (first to ${square} bingo${square === 1 ? '' : 's'}!)`
                    }
                    return txt
                case "win":
                    return `${time}: ${name} finished in ${ordinal_suffix(this.state.teams[cpid].place)} place!!!`
                default:
                    return ""
            }
        }
        let eventlog = haveGame  ? (
            <Row className="justify-content-center py-2">
            <Col style={{maxWidth: '1074px'}}>
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

        let hiddenPlayers = []
        let bingos = []
        if(teams)
        {
            Object.keys(teams).forEach(t => {
                if(teams[t].hidden)
                    hiddenPlayers.push(t)
                hiddenPlayers = hiddenPlayers.concat(teams[t].teammates.map(t => t.pid))
            })
            if(teams[activePlayer])
                bingos = teams[activePlayer].bingos
        }

        let bingoContent = haveGame ? (
            <Row className="justify-content-center align-items-center">
                <Col xs="auto">
                    <BingoBoard colors={colors} dark={dark} cards={cards} activePlayer={activePlayer} activeTeam={this.getCap(activePlayer)} bingos={bingos} hiddenPlayers={hiddenPlayers}/>
                </Col>
                    <PlayerList {...this.state} onPlayerListAction={this.onPlayerListAction}/>
            </Row>
            ) : null

        if(userBoard) {
            if(headerText === "Bingo!")
                headerText = "Waiting for game data"
            let {showLog, showList, logWidth, logHeight} = userBoardParams
            let rows = []
            if(showList) {
                rows.push((
                    <Row className="p-1 m-0">
                        <PlayerList {...this.state} onPlayerListAction={this.onPlayerListAction}/>
                    </Row>
                ))
            }
            if(showLog) {
                rows.push((
                    <Row className="p-1 m-0">
                        <Col style={{maxWidth: `${logWidth}px`, maxHeight: `${logHeight}px`}} className="w-100 p-0 m-0" xs="12">
                        <textarea style={{width: `${logWidth}px`, height: `${logHeight}px`, ...inputStyle}} disabled value={this.state.events.map(ev => fmt(ev)).reverse().filter(l => l !== "").join("\n")}/>
                        </Col>
                    </Row>
                ))
            }

            return (
                <Container className="p-0 m-0 w-100">
                    <NotificationContainer/>
                    <SiteBar hidden/>

                    <Row className="flex-nowrap p-0 m-0">
                        <Col className="p-0 m-0">
                            <BingoBoard colors={colors} dark={dark} cards={cards} activePlayer={activePlayer} activeTeam={this.getCap(activePlayer)} bingos={bingos} hiddenPlayers={hiddenPlayers}/>
                        </Col>
                        <Col>
                            {rows}
                        </Col>
                    </Row>

                </Container>
            )
        }
        if(viewOnly) {
            if(headerText === "Bingo!")
                headerText = "Game not found"
            return (
                <Container className="px-4 pb-4 pt-2 mt-2 w-100">
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
        let links = haveGame ? [
            (<Row className="justify-content-center pt-3" key="specLink"><Col xs="auto"><small> spectator link: {specLink}</small></Col></Row>)
         ] : null
         if(paramId > 0 && gameId > 0 && haveGame)
            links.push((<Row className="justify-content-center" key="gameLink"><Col xs="auto"><small><a href={`/?param_id=${paramId}&game_id=${gameId}`}>base seed</a></small></Col></Row>))
        let joinGameButton = teamsDisabled ? (
            <Button block color="primary" onClick={() => this.joinGame()} disabled={!haveGame}>Join Game</Button>
        ) : (
            <Button block color="warning" onClick={() => this.joinGame()} disabled={!haveGame}>Create Team</Button>
        )
        return (
            <Container fluid="true" className="pb-4 pt-2 mt-5">
                <NotificationContainer/>
                <Container className="">
                    <SiteBar dark={dark} user={user}/>
                </Container>
                {this.createModal(inputStyle)}
                {this.loadingModal(inputStyle, loadingText)}
                {this.countdownModal(inputStyle)}
                <Row className="p-1">
                    <Col xs={{size: 8, offset: 2}}>
                        <Cent><h3>{headerText}</h3></Cent>
                    </Col>
                </Row>
                {subheader}
                {creatorControls}
                <Row className="flex-nowrap justify-content-center align-items-center px-1">
                    <Col xs="auto">
                        <Button block onClick={this.toggleCreate}>Create New Game</Button>
                    </Col><Col xs="auto">
                        {joinGameButton}
                    </Col><Col xs="auto">
                        <Row className="flex-nowrap align-items-left pt-0 pb-2 px-1 m-0">
                            <Col xs="auto"><Cent>
                                Player:
                            </Cent></Col>
                            <Col xs="4"><Cent>
                                <Input style={inputStyle} type="number" disabled={!haveGame} min="1" value={activePlayer} onChange={e => this.setState({activePlayer: parseInt(e.target.value, 10)})}/>
                            </Cent></Col>
                            <Col xs="auto"><Cent>
                                {activePlayer > 0 ? make_icons([activePlayer]) : null}
                            </Cent></Col>
                        </Row>
                    </Col>
                </Row>
                {bingoContent}
                {eventlog}
                {links}
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

    updateTimer= () => {
        let {haveGame, creatingGame, startTime, offset, timerTime} = this.state
        if(creatingGame || !haveGame || !startTime || !offset)
        {
            if(timerTime)
                this.setState({timerTime: null})
            return
        }
        let s = (new Date()).getTime() + offset - startTime*1000;
        if(s < 0)
            return
        let pad = (n, z = 2) => ('00' + n).slice(-z);
        this.setState({timerTime: pad(s/3.6e6|0) + ':' + pad((s%3.6e6)/6e4 | 0) + ':' + pad((s%6e4)/1000|0) + '.' + pad((s%1000)/10|0)});
    }

    countdownModal = (style) => {
        let {countdownActive, startTime, offset} = this.state
        return (
        <Modal size="sm" isOpen={countdownActive} backdrop={"static"} className={"modal-dialog-centered"}>
            <ModalHeader style={style}>Game Starting!</ModalHeader>
            <ModalBody style={style}>
                <Container fluid>
                    <Countdown
                        date={startTime*1000}
                        precision={2}
                        intervalDelay={2}
                        now={() => (new Date()).getTime() + offset}
                        renderer={({seconds, milliseconds, completed}) =>
                            completed ? (<Cent><h3>Go!</h3></Cent>) : (<Cent><h3>{seconds}{`.${milliseconds}`.slice(0, -1)}</h3></Cent>)
                        }
                    />
            </Container>
            </ModalBody>
        </Modal>
    )}
    createModal = (style) => {
        let {difficulty, isRandoBingo, seed, fromGen, teamMax, randoGameId, targetCount, startSkills, startCells, startMisc, showInfo, teamsDisabled, noTimer, squareCount, goalMode, user} = this.state
        let randoInput = fromGen ? (
            <Row className="p-1">
                <Col xs="4" className="text-center p-1 border">
                    <Cent>Rando Game ID</Cent>
                </Col><Col xs="4">
                    <Input disabled style={style} type="number" value={randoGameId}  onChange={(e) => this.setState({randoGameId: parseInt(e.target.value, 10)})}/>
                </Col>
            </Row>
        ) : (
            <Row className="p-1">
                <Col xs="6" className="text-center p-1">
                    <Button block color="primary" href="/?fromBingo=1">Create New Bingo Seed</Button>
                </Col>
            </Row>
        )
        let timerrow = user ? (
            <Row className="p-1">
                <Col xs="4" className="p-1 border">
                    <Cent>Countdown Timer</Cent>
                </Col>
                <Col xs="6">
                    <ButtonGroup>
                        <Button active={!noTimer} outline={noTimer} onClick={() => this.setState({noTimer: false})}>Enabled</Button>
                        <Button active={noTimer} outline={!noTimer} onClick={() => this.setState({noTimer: true})}>Disabled</Button>
                    </ButtonGroup>
                </Col>
            </Row>
        ) : null
        let teamrow = teamMax > 0 ? (
            <Row className="p-1">
                <Col xs="4" className="p-1 border">
                    <Cent><i>Teams of {teamMax} required</i></Cent>
                </Col>
                <Col xs="6">
                    <ButtonGroup>
                        <Button active={false} outline disabled>Solo</Button>
                        <Button active disabled>Teams</Button>
                    </ButtonGroup>
                </Col>
            </Row>
            ) : (
            <Row className="p-1">
                <Col xs="4" className="p-1 border">
                    <Cent>Teams?</Cent>
                </Col>
                <Col xs="6">
                    <ButtonGroup>
                        <Button active={teamsDisabled}  outline={!teamsDisabled} onClick={() => this.setState({teamsDisabled: true})}>Solo</Button>
                        <Button active={!teamsDisabled} outline={teamsDisabled} onClick={() => this.setState({teamsDisabled: false})}>Teams</Button>
                    </ButtonGroup>
                </Col>
            </Row>
        )
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
                    {teamrow}
                    {timerrow}
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
                    <Row className="p-1">
                        <Col xs="4" className="p1 border">
                            <Cent>Seed</Cent>
                        </Col><Col xs="4">
                            <Input style={style} type="text" value={seed} onChange={(e) => this.setState({seed: e.target.value})}/>
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
                        {randoInput}
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
                <Button color="primary" onClick={this.createGame} disabled={!fromGen && isRandoBingo}>Create Game</Button>
                <Button color="secondary" onClick={this.toggleCreate}>Cancel</Button>
            </ModalFooter>
        </Modal>
    )}
};
