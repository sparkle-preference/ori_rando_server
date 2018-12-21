import React from 'react';
import {Container, Row, Col, Collapse, Button, ButtonGroup, Modal, ModalHeader, 
        ModalBody, ModalFooter, Input, Card, CardBody, CardFooter, Media} from 'reactstrap';
import {NotificationContainer, NotificationManager} from 'react-notifications';
import {Helmet} from 'react-helmet';

import {download} from './shared_map.js'
import {Cent, doNetRequest, player_icons, get_random_loader, PickupSelect} from './common.js'
import SiteBar from "./SiteBar.js";

import 'react-notifications/lib/notifications.css';

const textStyle = {color: "black", textAlign: "center"}
const niceTPNames = {
    "sunkenGlades": "Sunken Glades",
    "moonGrotto": "Moon Grotto", 
    "mangroveFalls": "Blackroot Burrows", 
    "valleyOfTheWind": "Sorrow Pass", 
    "spiritTree": "Hollow Grove",
    "mangroveB": "Lost Grove", 
    "horuFields": "Horu Fields",
    "ginsoTree": "Ginso Tree", 
    "forlorn": "Forlorn Ruins",
    "mountHoru": "Mount Horu",
    "swamp": "Thornfelt Swamp", 
    "sorrowPass": "Valley of the Wind"
}
const niceLocNames = {
    "LostGroveLongSwim" : "Lost Grove Long Swim",
    "ValleyEntryGrenadeLongSwim": "Valley Long Swim" ,
    "SpiderSacEnergyDoor" : "Spider Energy Door",
    "SorrowHealthCell" : "Sorrow HC",
    "SunstonePlant" : "Sunstone Plant",
    "GladesLaser" : "Gladzer EC",
    "LowerBlackrootLaserAbilityCell": "BRB Right Laser AC",
    "MistyGrenade" : "Misty Grenade EX",
    "LeftSorrowGrenade": "Sorrow Grenade EX",
    "DoorWarpExp" : "Door Warp EX",
    "HoruR3Plant" : "R3 Plant",
    "RightForlornHealthCell" : "Right Forlorn HC",
    "ForlornEscapePlant" : "Forlorn Escape Plant"
}
const handleCard = (card, playerData, activePlayer) => {
    let {name, type} = card;
    let text = name
    let help = ""
    let extraLines = []
    let players = [];
    let valid = (p) => playerData.hasOwnProperty(p) && playerData[p].bingoData.hasOwnProperty(name)
    let pData = {}
    let validPs = Object.keys(playerData).filter(p => valid(p));
    validPs.forEach(p => pData[p] = playerData[p].bingoData[name])
    let apData = valid(activePlayer) ? pData[activePlayer] : null
    try {
        switch(type) {
            case "bool":
                players = validPs.filter(p => pData[p].value)
                switch(name) {
                    case "FastStompless":
                        text = "Fast Stompless"
                        help = "Break the rocks above Kuro's head in the Valley of the Wind with a long-distance spider shot"
                    break;
                    case "CoreSkip":
                        text = "Core Skip"
                        help = "Skip one of the Ginso core rooms by destroying both sets of brambles with a well-timed level-up."
                    break;
                    case "DrownFrog":
                        text = "Drown an amphibian"
                        help = "The amphibians native to Nibel are fronkeys, red spitters, and green spitters"
                    break;
                    case "DrainSwamp":
                        text = "Drain the Swamp"
                        help = "Drain the pool in the area above and to the right of the Grotto Teleporter by breaking the blue barrier there."
                    break;
                    case "WilhelmScream":
                        text = "Make Wilhelm Scream"
                        help = "Throw Wilhelm (a green spitter on the top left cliff in the main Valley of the Wind room) off his cliff. Note: Wilhelm does not spawn unless you have the Sunstone."
                    break;
                    default:
                        text = name;
                        help = "???";
                    break;
                }
            break;
            case "int":
                let target = card.target
                players = validPs.filter(p => pData[p].value >= target)
                let progress = apData ? `(${Math.min(apData.value, target)}/${target})` : `(${target})`
                switch(name) {
                    case "CollectMapstones":
                        text = `Collect mapstones ${progress}`
                        help = "You do not need to turn them in."
                        break;
                    case "ActivateMaps":
                        text = `Activate map altars ${progress}`
                        help = ""
                        break;
                    case "OpenKSDoors":
                        text = `Open keystone doors ${progress}`
                        help = "The already-opened door in Sunken Glades does not count."
                        break;
                    case "OpenEnergyDoors":
                        text = `Open energy doors ${progress}`
                        help = "There are 2 energy doors in Grotto, 2 in Glades, 1 in Grove, and 1 in Sorrow."
                        break;
                    case "BreakFloors":
                        text = `Break floors or ceilings. ${progress}`
                        help = "Any horizontal barrier that can be broken with a skill counts."
                        break;
                    case "BreakWalls":
                        text = `Break walls ${progress}`
                        help = "Any vertical barrier that can be broken with a skill counts."
                        break;
                    case "UnspentKeystones":
                        text = `Get ${progress} keystones in your inventory`
                        help = "Keyduping is allowed, and you can spend them after completing this goal."
                        break;
                    case "BreakPlants":
                        text = `Break plants ${progress}`
                        help = "Petrified plants are the large blue bulbs that can only be broken with Charge Flame, Grenade, or Charge Dash"
                        break;
                    case "TotalPickups":
                        text = `Collect pickups ${progress}`
                        help = "This includes petrified plants, mapstone turnins, world events, and horu rooms."
                        break;
                    case "UnderwaterPickups":
                        text = `Collect underwater pickups ${progress}`
                        help = "The pickup itself must be underwater, not just the path to reach it."
                        break;
                    case "HealthCells":
                        text = `Collect Health Cells ${progress}`
                        help = "Any bonus health cells you spawn with will not count."
                        break;
                    case "EnergyCells":
                        text = `Collect Energy Cells ${progress}`
                        help = "Any bonus energy cells you spawn with will not count."
                        break;
                    case "AbilityCells":
                        text = `Collect Ability Cells ${progress}`
                        help = "Any bonus ability cells you spawn with will not count."
                        break;
                    case "HealthCellLocs":
                        text = `Get pickups from Health Cells ${progress}`
                        help = "Collect pickups from this many vanilla health cell locations."
                        break;
                    case "EnergyCellLocs":
                        text = `Get pickups from Energy Cells ${progress}`
                        help = "Collect pickups from this many vanilla energy cell locations."
                        break;
                    case "AbilityCellLocs":
                        text = `Get pickups from Ability Cells ${progress}`
                        help = "Collect pickups from this many vanilla ability cell locations."
                        break;
                    case "LightLanterns":
                        text = `Use Grenade to light Lanterns ${progress}`
                        help = "The lanterns in the pre-dash area of BRB do not count."
                        break;
                    case "SpendPoints":
                        text = `Spend Ability Points ${progress}`
                        help = "What you spend them on is up to you."
                        break;
                    case "GainExperience":
                        text = `Gain spirit light ${progress}`
                        help = "bonus experience gained from the Spirit Light Efficiency ability counts"
                        break;
                    case "KillEnemies":
                        text = `Kill enemies ${progress}`
                        help = "Large swarms count as 3 enemies (the initial swarm and the first split)."
                        break;
                    default:
                       break;
                }
            break;
            case "multi":
                let infix = "";
                let suffix = ":";
                let optionNames = []
                let s = card.parts && card.parts.length > 1 ? "s" : ""
                let yies = card.parts && card.parts.length > 1 ? "ies" : "y"
                switch(card.method) {
                    case "and":
                        players = validPs.filter(p => card.parts.every(part => pData[p].value[part.name].value))
                        infix = card.parts.length > 1 ? ( card.parts.length > 2 ? "all of these " : "both of these ") : "this "
                        break;
                    case "or":
                        players = validPs.filter(p => card.parts.some(part => pData[p].value[part.name].value))
                        infix = card.parts.length > 1 ? "any of these " : "this "
                        break;
                    case "count":
                        players = validPs.filter(p => pData[p].total >= card.target)
                        suffix = apData ? ` (${Math.min(apData.total, card.target)}/${card.target})` : ` (${card.target})`
                        s = "s"
                        yies = "ies"
                        break;
                    default:
                        break;
                }
                switch(name) {
                    case "CompleteHoruRoom":
                        text = `Complete ${infix}Horu room${s+suffix}`
                        if(card.parts) 
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "CompleteEscape":
                        text = `Escape ${infix}dungeon${s+suffix}`
                        if(card.parts) 
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "ActivateTeleporter":
                        text = `Activate ${infix}spirit well${s+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {niceName: niceTPNames[part.name], partname: part.name}})
                    break;
                    case "EnterArea":
                        text = `Enter ${infix}area${s+suffix}`
                        if(card.parts) 
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "GetItemAtLoc":
                        text = `Get the pickup${s} at ${infix}location${s+suffix}`
                        if(card.parts) 
                            optionNames = card.parts.map(part => {return {niceName: niceLocNames[part.name], partname: part.name}})
                    break;
                    case "VisitTree":
                        text = `Visit ${infix}tree${s+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "GetAbility":
                        text = `Level up ${infix}abilit${yies+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "GetEvent":
                        text = `Unlock ${infix}event${s+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "StompPeg":
                        text = `Stomp ${infix}post${s+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    case "HuntEnemies":
                        text = `Defeat ${infix}Miniboss encounter${s+suffix}`
                        if(card.parts)
                            optionNames = card.parts.map(part => {return {partname: part.name}})
                    break;
                    default:
                        break;
                    }
                extraLines = optionNames.map(({partname, niceName}) => 
                {
                    niceName = niceName || partname
                    let checked = "☐";
                    if(apData && apData.value[partname].value)
                        checked = "☑"
                    return `᛫ ${niceName} ${checked}`
                })
                break;
            default:
                break;
        }
        let i = 0;
        text = [text].concat(extraLines).map(t => (<div key={`card-line-${i++}`}>{t}</div>))
        return {text: text, help: help, players: players}
    }
    catch(error)
    {
        console.log(error, card, playerData)
        return {text: text, help: help, players: players}
    }
}

const make_icons = players => players.map(p => (<Media key={`playerIcon${p}`} object style={{width: "25px", height: "25px"}} src={player_icons(p, false)} alt={"Icon for player "+p} />))
const BingoCard = ({text, players, tinted}) => {
    let className = "pl-1 pr-1 pb-0 justify-content-center text-center align-items-center d-flex " + ((text.length > 1) ? "pt-0 flex-column" : "pt-1")
    let cardStyles = {width: 160, height: 160}
    if(tinted)
        cardStyles.background = "#cfc"
    return (
        <Card style={cardStyles}>
            <CardBody style={{fontSize: ".8rem"}} className={className}>{text}</CardBody>
            <CardFooter className="p-0 justify-content-center d-flex">{make_icons(players)}</CardFooter>
        </Card>
)}

// board: rows[cols[players]]
const bingos = (board, players) => {
    let ret = {}
    players.forEach(p => ret[p] = [])
    let dim = board.length
    players.forEach(p => {
        let tlbr = true;
        let bltr = true;
        for(let i = 0; i < dim; i++) {
            tlbr = tlbr && board[i][i].includes(p);
            bltr = bltr && board[dim-i-1][i].includes(p);
            if(board[i].every(card => card.includes(p)))
                ret[p].push(`row ${i+1}`)
            if(board.every(col => col[i].includes(p)))
                ret[p].push(`col ${i+1}`)
        }
        if(tlbr) ret[p].push("tlbr")
        if(bltr) ret[p].push("bltr")
    })
    return ret;
}

const BingoBoard = ({cards, playerData, activePlayer, bingoUpdater}) => {
    cards = [...cards]
    if(cards.length < 25) {
        return null
    }
    let board = []
    let rows = []
    while(rows.length < 5) {
        let row = []
        let row_comp = []
        while(row.length < 5) {
            let card = cards.shift()
            let {text, players} = handleCard(card, playerData, activePlayer)
            row_comp.push(players)
            let key=`${row.length}, ${rows.length}`
            row.push((<Col key={key}><BingoCard tinted={players.includes("" + activePlayer)} text={text} players={players} /></Col>))
        }
        board.push(row_comp)
        rows.push((<Row key={`row-${rows.length}`} className="justify-content-center align-items-center w-100">{row}</Row>))
    }
    bingoUpdater(bingos(board, Object.keys(playerData)))
    return (<Container>{rows}</Container>);
}


export default class Bingo extends React.Component {
    constructor(props) {
        super(props);
        let url = new URL(window.document.location.href);
        let gameId = parseInt(url.searchParams.get("game_id") || -1, 10);
        this.state = {cards: [], haveGame: false, creatingGame: false, createModalOpen: true, playerData: {}, activePlayer: 1, showInfo: false, bingos: {},
                      gameId: gameId, startSkills: 3, startCells: 4, startMisc: "MU|TP/Swamp/TP/Valley", start_with: "", isRandoBingo: false, randoGameId: -1};
 
        if(gameId > 0)
        {
            let url = `/bingo/game/${gameId}/fetch`
            doNetRequest(url, this.createCallback)
            this.state.creatingGame = true
            this.state.createModalOpen = false
            this.state.loader = get_random_loader()
        }
    }
    componentDidMount() {
        this.interval = setInterval(() => this.tick(), 5000);
  };
    updateUrl = () => {
        let {gameId} = this.state;
        let url = window.document.URL.split("?")[0];
        if(gameId && gameId > 0)
            url += `?game_id=${gameId}`
        window.history.replaceState('',window.document.title, url);
    }

    joinGame = () => {
        let {gameId, seed, activePlayer, haveGame} = this.state;
        if(!haveGame) return;
        let nextPlayer = activePlayer;
        let players = Object.keys(this.state.playerData)
        while(players.includes("" + nextPlayer))
            nextPlayer++;

        seed = `Sync${gameId}.${nextPlayer},` + seed
        download("randomizer.dat", seed)
        this.setState({activePlayer: nextPlayer})
        doNetRequest(`/bingo/game/${gameId}/add/${nextPlayer}`, this.tickCallback)
    }
    tick = () => {
        let {gameId, haveGame} = this.state;
        if(gameId && gameId > 0 && haveGame && this.state.fails < 50)
            doNetRequest(`/bingo/game/${gameId}/fetch`, this.tickCallback)
    }

    tickCallback = ({status, responseText}) => {
        if(status !== 200)
        {
            if((this.state.fails - 1) % 5 === 0)
                NotificationManager.error(`error ${status}: ${responseText}`, "error", 5000)
            this.setState({fails: this.state.fails + 1})
        } else {
            let res = JSON.parse(responseText)
            this.setState({playerData: res.playerData, fails: 0})
        }
    }



    loadingModal = () => { return (
        <Modal size="sm" isOpen={this.state.creatingGame } backdrop={"static"} className={"modal-dialog-centered"}>
            <ModalHeader centered="true">Please wait...</ModalHeader>
            <ModalBody>
                <Container fluid>
                    <Row className="p-2 justify-content-center align-items-center">
                        <Col xs="auto" className="align-items-center justify-content-center p-2">{this.state.loader}</Col>
                    </Row>
                </Container>
            </ModalBody>
        </Modal>
    )}
    createModal = () =>  { return (
        <Modal size="lg" isOpen={this.state.createModalOpen} backdrop={"static"} className={"modal-dialog-centered"} toggle={this.toggleCreate}>
            <ModalHeader toggle={this.toggleCreate} centered="true">Bingo options</ModalHeader>
            <ModalBody>
                <Container fluid>
                    <Row className="p-1">
                        <Col xs="4" className="p-1 border">
                            <Cent>Random Starting Items:</Cent>
                        </Col><Col xs="4" className="text-center p-1">
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
                                <Cent>Rando game id:</Cent>
                            </Col><Col xs="4">
                                <Input type="number" value={this.state.randoGameId}  onChange={(e) => this.setState({randoGameId: parseInt(e.target.value, 10)})}/> 
                            </Col>
                        </Row>
                    </Collapse>
                    <Collapse isOpen={!this.state.isRandoBingo}>
                        <Row className="p-1">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>random free skill count</Cent>
                            </Col><Col xs="4">
                                <Input type="number" value={this.state.startSkills}  onChange={(e) => this.setState({startSkills: parseInt(e.target.value, 10)})}/> 
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>random free cell count</Cent>
                            </Col><Col xs="4">
                                <Input type="number" value={this.state.startCells} onChange={(e) => this.setState({startCells: parseInt(e.target.value, 10)})}/> 
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center p-1 border">
                                <Cent>Also start with</Cent>
                            </Col><Col xs="8">
                                <PickupSelect value={this.state.startMisc} updater={(code, _) => this.setState({startMisc: code})}/> 
                            </Col>
                        </Row>
                        <Row className="p-1">
                            <Col xs="4" className="text-center pt-1 border">
                                <Cent>Random Starting Items:</Cent>
                            </Col><Col xs="4" className="text-center p-1">
                                <ButtonGroup>
                                    <Button active={this.state.showInfo} outline={!this.state.showInfo} onClick={() => this.setState({showInfo: true})}>Show</Button>
                                    <Button active={!this.state.showInfo} outline={this.state.showInfo} onClick={() => this.setState({showInfo: false})}>Hide</Button>
                                </ButtonGroup>
                            </Col>
                        </Row>
                    </Collapse>
                </Container>
            </ModalBody>
            <ModalFooter>
                <Button color="primary" onClick={this.createGame}>Create Game</Button>
                <Button color="secondary" onClick={this.toggleCreate}>Cancel</Button>
            </ModalFooter>
        </Modal>
    )}
    toggleCreate = () => this.setState({createModalOpen: !this.state.createModalOpen})
    createGame = () => {
        let {isRandoBingo, randoGameId, startSkills, startCells, startMisc, showInfo} = this.state
        if(isRandoBingo)
        {
            let url = `/bingo/from_game/${randoGameId}`
            doNetRequest(url, this.createCallback)
            this.setState({creatingGame: true, createModalOpen: false, loader: get_random_loader()})
        } else {
            let url = `/bingo/new?skills=${startSkills}&cells=${startCells}&misc=${startMisc}`
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
            this.setState({startWith: res.startWith, gameId: res.gameId, createModalOpen: false, creatingGame: false, haveGame: true, 
                          seed: res.seed, playerData: res.playerData, cards: res.cards, fails: 0}, this.updateUrl)
        }
    }
    updateBingos = (bingos) =>  {
        if(!Object.keys(bingos).every(p => bingos[p].every(b => this.state.bingos[p] && this.state.bingos[p].includes(b))))
            this.setState({bingos: bingos})
    }
    render = () => {
        let {activePlayer, playerData, startWith, cards, haveGame, gameId, user} = this.state
        let headerText = haveGame ? `Bingo Game ${gameId}` : "Bingo!"
        let subheader = (haveGame && startWith !== "") ? (
            <Row>
                <Col>
                    <Cent><h6 style={textStyle}>{startWith}</h6></Cent>
                </Col>
            </Row>
        ) : null 
        return (
            <Container className="pl-4 pr-4 pb-4 pt-2 mt-2 w-75">
                <Helmet>
                    <style>{'body { background-color: white}'}</style>
                </Helmet>
                <NotificationContainer/>
                <SiteBar user={user}/>
                {this.createModal()}
                {this.loadingModal()}
                <Row className="p-1">
                    <Col>
                        <Cent><h3 style={textStyle}>{headerText}</h3></Cent>
                    </Col>
                </Row>
                {subheader}
                <BingoBoard cards={cards} playerData={playerData} activePlayer={activePlayer} bingoUpdater={(bingos) => this.updateBingos(bingos)}/>
                <Row className="align-items-center pt-2">
                    <Col xs="4">
                        <Button onClick={this.toggleCreate}>Create New Game</Button>
                    </Col><Col xs="4">
                        <Button onClick={this.joinGame} disabled={!haveGame}>Join Game / Download Seed</Button>
                    </Col><Col xs="3">
                        {activePlayer > 0 ? make_icons([activePlayer]) : null}
                        Player Number: <Input type="number" value={activePlayer} onChange={(e) => this.setState({activePlayer: parseInt(e.target.value, 10)})}/> 
                    </Col>
                </Row>
            </Container>
        )
    }
};

